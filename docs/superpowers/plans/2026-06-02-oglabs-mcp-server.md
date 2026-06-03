# oglabs MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose oglabs blog operations (content management, LLM/image pipeline, build/deploy) as an MCP server reachable over the LAN so remote agents can use it.

**Architecture:** A single `mcp_server.py` at the repo root uses FastMCP with streamable-HTTP transport. Content tools are pure Python file operations; pipeline and build/deploy tools shell out to the existing `scripts/` and `Makefile`. The repo root is resolved from `OGLABS_REPO_ROOT` (default: the server file's directory) so tests can point at a temp repo. Runs as a Docker container on Unraid with the repo mounted as a volume.

**Tech Stack:** Python 3.12, `mcp` SDK (FastMCP), pytest + pytest-mock, Docker / docker-compose.

**Environment note:** All `python` / `pip` / `pytest` / `make` commands run inside the conda env `oglabs`. Prefix with `conda run -n oglabs` (per project convention).

---

## File Structure

- Create: `mcp_server.py` — the MCP server: config, helpers, and all tools.
- Create: `tests/test_mcp_server.py` — unit tests (content + subprocess tools).
- Create: `Dockerfile` — image with make + awscli + python deps.
- Create: `docker-compose.yml` — run config for Unraid (volume + env_file).
- Modify: `requirements.txt` — add `mcp>=1.2`.
- Modify: `Makefile` — add `mcp` target.
- Modify: `.env` (host only, gitignored) — add AWS credentials (manual, documented).

---

### Task 1: Project setup — dependency, skeleton, make target

**Files:**
- Modify: `requirements.txt`
- Create: `mcp_server.py`
- Modify: `Makefile`

- [ ] **Step 1: Add the mcp dependency**

Append to `requirements.txt`:

```
mcp>=1.2
```

- [ ] **Step 2: Install it**

Run: `conda run -n oglabs pip install -r requirements.txt`
Expected: installs `mcp` and its deps (e.g. `starlette`, `uvicorn`) without error.

- [ ] **Step 3: Create the server skeleton**

Create `mcp_server.py`:

```python
"""MCP server for the oglabs static site.

Exposes content management, the LLM/image pipeline, and build/deploy over
streamable-HTTP so remote agents on the LAN can drive the blog.
"""
import os
import re
import subprocess
from datetime import date
from pathlib import Path

from mcp.server.fastmcp import FastMCP

CONTENT_SECTIONS = {"blog", "projects", "photos"}
PIPELINE_SECTIONS = {"blog", "projects", "all"}

mcp = FastMCP(
    "oglabs",
    host="0.0.0.0",
    port=int(os.getenv("OGLABS_MCP_PORT", "8765")),
)


def _repo_root() -> Path:
    """Resolve the repo root. Override with OGLABS_REPO_ROOT (used in tests)."""
    return Path(os.getenv("OGLABS_REPO_ROOT", Path(__file__).resolve().parent))


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
```

- [ ] **Step 4: Verify it imports and starts cleanly**

Run: `conda run -n oglabs python -c "import mcp_server; print('ok', mcp_server.mcp.name)"`
Expected: prints `ok oglabs`.

- [ ] **Step 5: Add the make target**

Add to `Makefile` `.PHONY` line (append ` mcp`) and a new target:

```makefile
# Run the MCP server in the foreground (local dev; Docker is used in prod)
mcp:
	python mcp_server.py
```

- [ ] **Step 6: Commit**

```bash
git add requirements.txt mcp_server.py Makefile
git commit -m "feat: scaffold oglabs MCP server (FastMCP, streamable-http)"
```

---

### Task 2: Path and section validation helpers

**Files:**
- Modify: `mcp_server.py`
- Create: `tests/test_mcp_server.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_mcp_server.py`:

```python
import importlib

import pytest

import mcp_server


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """Point the server at a temp repo and reload module state."""
    monkeypatch.setenv("OGLABS_REPO_ROOT", str(tmp_path))
    return tmp_path


def test_repo_root_honors_env(repo):
    assert mcp_server._repo_root() == repo


def test_repo_path_joins_within_root(repo):
    p = mcp_server._repo_path("drafts", "blog", "x.md")
    assert p == repo / "drafts" / "blog" / "x.md"


def test_repo_path_rejects_escape(repo):
    with pytest.raises(ValueError, match="escapes repo root"):
        mcp_server._repo_path("..", "etc", "passwd")


def test_validate_content_section_ok():
    assert mcp_server._validate_section("blog", mcp_server.CONTENT_SECTIONS) == "blog"


def test_validate_content_section_rejects():
    with pytest.raises(ValueError, match="Invalid section"):
        mcp_server._validate_section("nope", mcp_server.CONTENT_SECTIONS)


def test_slugify():
    assert mcp_server._slugify("Mi Primer Post!") == "mi-primer-post"
    assert mcp_server._slugify("  Hola --- Mundo  ") == "hola-mundo"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `conda run -n oglabs pytest tests/test_mcp_server.py -v`
Expected: FAIL — `AttributeError: module 'mcp_server' has no attribute '_repo_path'` (etc.).

- [ ] **Step 3: Implement the helpers**

Add to `mcp_server.py` (after `_repo_root`):

```python
def _repo_path(*parts: str) -> Path:
    """Resolve a path inside the repo, rejecting anything that escapes it."""
    root = _repo_root().resolve()
    p = (root / Path(*parts)).resolve()
    if p != root and root not in p.parents:
        raise ValueError(f"Path {p} escapes repo root {root}.")
    return p


def _validate_section(section: str, allowed: set) -> str:
    if section not in allowed:
        raise ValueError(
            f"Invalid section {section!r}. Choose from {sorted(allowed)}."
        )
    return section


def _slugify(title: str) -> str:
    s = re.sub(r"[^a-z0-9]", "-", title.lower())
    s = re.sub(r"-+", "-", s).strip("-")
    return s
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `conda run -n oglabs pytest tests/test_mcp_server.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add mcp_server.py tests/test_mcp_server.py
git commit -m "feat: add path/section validation helpers to MCP server"
```

---

### Task 3: Content tools (pure Python)

**Files:**
- Modify: `mcp_server.py`
- Modify: `tests/test_mcp_server.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_mcp_server.py`:

```python
def test_create_draft_writes_frontmatter(repo):
    rel = mcp_server.create_draft("blog", "Mi Primer Post!")
    assert rel == "drafts/blog/mi-primer-post.md"
    text = (repo / rel).read_text()
    assert "Title: Mi Primer Post!" in text
    assert "Category: blog" in text
    assert "Slug: mi-primer-post" in text


def test_create_draft_rejects_bad_section(repo):
    with pytest.raises(ValueError, match="Invalid section"):
        mcp_server.create_draft("bogus", "x")


def test_write_draft_overwrites(repo):
    mcp_server.create_draft("blog", "Hola")
    rel = mcp_server.write_draft("blog", "hola", "Title: Hola\n\nCuerpo nuevo")
    assert (repo / rel).read_text() == "Title: Hola\n\nCuerpo nuevo"


def test_list_drafts_and_posts(repo):
    mcp_server.create_draft("blog", "Uno")
    (repo / "content" / "blog").mkdir(parents=True)
    (repo / "content" / "blog" / "pub.md").write_text("Title: Pub\n")
    assert mcp_server.list_drafts("blog") == ["drafts/blog/uno.md"]
    assert mcp_server.list_posts("blog") == ["content/blog/pub.md"]


def test_read_post_parses_frontmatter(repo):
    mcp_server.write_draft("blog", "p", "Title: P\nCategory: blog\n\nEl cuerpo.")
    result = mcp_server.read_post("drafts/blog/p.md")
    assert result["frontmatter"] == {"Title": "P", "Category": "blog"}
    assert result["body"] == "El cuerpo."


def test_read_post_missing_raises(repo):
    with pytest.raises(ValueError, match="File not found"):
        mcp_server.read_post("drafts/blog/nope.md")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `conda run -n oglabs pytest tests/test_mcp_server.py -v -k "draft or post"`
Expected: FAIL — `create_draft` / `write_draft` / `list_drafts` / `read_post` not defined.

- [ ] **Step 3: Implement the content tools**

Add to `mcp_server.py`:

```python
def _parse_frontmatter(text: str) -> dict:
    """Split Pelican-style 'Key: value' frontmatter from the body."""
    fm: dict = {}
    lines = text.splitlines()
    body_start = 0
    for i, line in enumerate(lines):
        if not line.strip():
            body_start = i + 1
            break
        m = re.match(r"^([A-Za-z][\w-]*):\s*(.*)$", line)
        if not m:
            body_start = i
            break
        fm[m.group(1)] = m.group(2)
        body_start = i + 1
    body = "\n".join(lines[body_start:]).strip("\n")
    return {"frontmatter": fm, "body": body}


@mcp.tool()
def create_draft(section: str, title: str) -> str:
    """Create a new draft under drafts/<section>/ with Pelican frontmatter."""
    _validate_section(section, CONTENT_SECTIONS)
    slug = _slugify(title)
    path = _repo_path("drafts", section, f"{slug}.md")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"Title: {title}\nDate: {date.today():%Y-%m-%d}\n"
        f"Category: {section}\nSlug: {slug}\n\n"
    )
    return str(path.relative_to(_repo_root()))


@mcp.tool()
def write_draft(section: str, slug: str, content: str) -> str:
    """Write (overwrite) the full content of drafts/<section>/<slug>.md."""
    _validate_section(section, CONTENT_SECTIONS)
    path = _repo_path("drafts", section, f"{slug}.md")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return str(path.relative_to(_repo_root()))


def _list_md(base: str, section: str | None) -> list[str]:
    sections = [section] if section else sorted(CONTENT_SECTIONS)
    out: list[str] = []
    for s in sections:
        d = _repo_path(base, s)
        if d.exists():
            out.extend(
                str(p.relative_to(_repo_root())) for p in sorted(d.glob("*.md"))
            )
    return out


@mcp.tool()
def list_drafts(section: str | None = None) -> list[str]:
    """List draft .md files under drafts/ (optionally one section)."""
    return _list_md("drafts", section)


@mcp.tool()
def list_posts(section: str | None = None) -> list[str]:
    """List published .md files under content/ (optionally one section)."""
    return _list_md("content", section)


@mcp.tool()
def read_post(path: str) -> dict:
    """Read a .md file (relative to repo root); returns frontmatter + body."""
    p = _repo_path(path)
    if not p.exists():
        raise ValueError(f"File not found: {path}")
    return _parse_frontmatter(p.read_text())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `conda run -n oglabs pytest tests/test_mcp_server.py -v`
Expected: PASS (all content + helper tests).

- [ ] **Step 5: Commit**

```bash
git add mcp_server.py tests/test_mcp_server.py
git commit -m "feat: add content management tools to MCP server"
```

---

### Task 4: Subprocess helper

**Files:**
- Modify: `mcp_server.py`
- Modify: `tests/test_mcp_server.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_mcp_server.py`:

```python
def test_run_returns_structured_result(repo, mocker):
    fake = mocker.Mock(returncode=0, stdout="done\n", stderr="")
    run = mocker.patch("mcp_server.subprocess.run", return_value=fake)
    result = mcp_server._run(["make", "build"])
    assert result == {"ok": True, "returncode": 0, "stdout": "done\n", "stderr": ""}
    run.assert_called_once_with(
        ["make", "build"], cwd=mcp_server._repo_root(),
        capture_output=True, text=True,
    )


def test_run_marks_failure(repo, mocker):
    fake = mocker.Mock(returncode=2, stdout="", stderr="boom")
    mocker.patch("mcp_server.subprocess.run", return_value=fake)
    result = mcp_server._run(["make", "deploy"])
    assert result["ok"] is False
    assert result["returncode"] == 2
    assert result["stderr"] == "boom"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `conda run -n oglabs pytest tests/test_mcp_server.py -v -k run`
Expected: FAIL — `_run` not defined.

- [ ] **Step 3: Implement `_run`**

Add to `mcp_server.py`:

```python
def _run(cmd: list[str]) -> dict:
    """Run a command from the repo root, returning a structured result."""
    proc = subprocess.run(
        cmd, cwd=_repo_root(), capture_output=True, text=True
    )
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `conda run -n oglabs pytest tests/test_mcp_server.py -v -k run`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add mcp_server.py tests/test_mcp_server.py
git commit -m "feat: add subprocess helper to MCP server"
```

---

### Task 5: Pipeline tools

**Files:**
- Modify: `mcp_server.py`
- Modify: `tests/test_mcp_server.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_mcp_server.py`:

```python
def test_improve_writing_builds_command(repo, mocker):
    run = mocker.patch("mcp_server._run", return_value={"ok": True})
    mcp_server.improve_writing("blog", llm="claude", overwrite=False)
    run.assert_called_once_with(
        ["python", "scripts/improve_writing.py", "--section", "blog",
         "--llm", "claude", "--no-overwrite"]
    )


def test_improve_writing_defaults(repo, mocker):
    run = mocker.patch("mcp_server._run", return_value={"ok": True})
    mcp_server.improve_writing("all")
    run.assert_called_once_with(
        ["python", "scripts/improve_writing.py", "--section", "all"]
    )


def test_improve_writing_rejects_bad_section(repo):
    with pytest.raises(ValueError, match="Invalid section"):
        mcp_server.improve_writing("photos")


def test_optimize_images_force(repo, mocker):
    run = mocker.patch("mcp_server._run", return_value={"ok": True})
    mcp_server.optimize_images(force=True)
    run.assert_called_once_with(
        ["python", "scripts/optimize_images.py", "--force"]
    )


def test_process_photos_builds_command(repo, mocker):
    run = mocker.patch("mcp_server._run", return_value={"ok": True})
    mcp_server.process_photos(llm="ollama", force=True)
    run.assert_called_once_with(
        ["python", "scripts/photo_pipeline.py", "--llm", "ollama", "--force"]
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `conda run -n oglabs pytest tests/test_mcp_server.py -v -k "improve or optimize or photos"`
Expected: FAIL — pipeline tools not defined.

- [ ] **Step 3: Implement the pipeline tools**

Add to `mcp_server.py`:

```python
@mcp.tool()
def improve_writing(
    section: str, llm: str | None = None, overwrite: bool = True
) -> dict:
    """Improve drafts in a section with an LLM (scripts/improve_writing.py).

    section: 'blog', 'projects', or 'all'. llm: 'ollama'|'claude'|'openai'.
    """
    _validate_section(section, PIPELINE_SECTIONS)
    cmd = ["python", "scripts/improve_writing.py", "--section", section]
    if llm:
        cmd += ["--llm", llm]
    if not overwrite:
        cmd.append("--no-overwrite")
    return _run(cmd)


@mcp.tool()
def optimize_images(force: bool = False) -> dict:
    """Optimize new post images for web (scripts/optimize_images.py)."""
    cmd = ["python", "scripts/optimize_images.py"]
    if force:
        cmd.append("--force")
    return _run(cmd)


@mcp.tool()
def process_photos(llm: str | None = None, force: bool = False) -> dict:
    """Process new gallery photos (scripts/photo_pipeline.py).

    llm: 'ollama'|'claude'|'openai' for the description backend.
    """
    cmd = ["python", "scripts/photo_pipeline.py"]
    if llm:
        cmd += ["--llm", llm]
    if force:
        cmd.append("--force")
    return _run(cmd)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `conda run -n oglabs pytest tests/test_mcp_server.py -v -k "improve or optimize or photos"`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add mcp_server.py tests/test_mcp_server.py
git commit -m "feat: add LLM/image pipeline tools to MCP server"
```

---

### Task 6: Build & deploy tools

**Files:**
- Modify: `mcp_server.py`
- Modify: `tests/test_mcp_server.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_mcp_server.py`:

```python
@pytest.mark.parametrize("tool,target", [
    ("build", "build"), ("deploy", "deploy"), ("publish", "publish"),
])
def test_build_deploy_tools(repo, mocker, tool, target):
    run = mocker.patch("mcp_server._run", return_value={"ok": True})
    getattr(mcp_server, tool)()
    run.assert_called_once_with(["make", target])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `conda run -n oglabs pytest tests/test_mcp_server.py -v -k "build_deploy"`
Expected: FAIL — `build`/`deploy`/`publish` not defined.

- [ ] **Step 3: Implement the build/deploy tools**

Add to `mcp_server.py`:

```python
@mcp.tool()
def build() -> dict:
    """Build the site (photos + images + strip-fences + pelican): make build."""
    return _run(["make", "build"])


@mcp.tool()
def deploy() -> dict:
    """Deploy output/ to S3 and invalidate CloudFront: make deploy."""
    return _run(["make", "deploy"])


@mcp.tool()
def publish() -> dict:
    """Build then deploy in one step: make publish."""
    return _run(["make", "publish"])
```

- [ ] **Step 4: Run the full test suite**

Run: `conda run -n oglabs pytest tests/test_mcp_server.py -v`
Expected: PASS (all tests).

- [ ] **Step 5: Commit**

```bash
git add mcp_server.py tests/test_mcp_server.py
git commit -m "feat: add build/deploy tools to MCP server"
```

---

### Task 7: Dockerize for Unraid

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.dockerignore`

- [ ] **Step 1: Create the Dockerfile**

Create `Dockerfile`:

```dockerfile
FROM python:3.12-slim

# make + awscli are needed by the build/deploy tools
RUN apt-get update \
    && apt-get install -y --no-install-recommends make awscli \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps in a cached layer (the repo itself is mounted at runtime)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8765
CMD ["python", "mcp_server.py"]
```

- [ ] **Step 2: Create the .dockerignore**

Create `.dockerignore`:

```
.git/
output/
__pycache__/
*.pyc
.pytest_cache/
.venv/
venv/
photos/originals/
```

- [ ] **Step 3: Create docker-compose.yml**

Create `docker-compose.yml`:

```yaml
services:
  oglabs-mcp:
    build: .
    container_name: oglabs-mcp
    ports:
      - "8765:8765"
    # Set OGLABS_REPO_PATH to the repo location on the Unraid host.
    # Defaults to the compose file's directory.
    volumes:
      - "${OGLABS_REPO_PATH:-.}:/app"
    env_file:
      - .env
    environment:
      - OGLABS_MCP_PORT=8765
    restart: unless-stopped
```

- [ ] **Step 4: Build the image**

Run: `docker compose build`
Expected: image builds; `pip install` pulls `mcp` and deps; no errors.

- [ ] **Step 5: Add AWS credentials to .env (host only — manual)**

The `.env` is gitignored. On the Unraid host, add (real values):

```
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_DEFAULT_REGION=us-east-1
ANTHROPIC_API_KEY=...
```

(Uncomment/fill `ANTHROPIC_API_KEY` if the Claude backend is used; `OPENAI_API_KEY` is already present.)

- [ ] **Step 6: Smoke-test the running container**

Run: `docker compose up -d && sleep 3 && docker compose logs --tail 20`
Expected: logs show the streamable-HTTP server listening on `0.0.0.0:8765`.

Then verify the endpoint responds:
Run: `curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8765/mcp`
Expected: an HTTP status (e.g. `400`/`406` for a bare GET, not connection refused) — confirms the server is up.

Run: `docker compose down`

- [ ] **Step 7: Commit**

```bash
git add Dockerfile docker-compose.yml .dockerignore
git commit -m "feat: dockerize MCP server for Unraid deployment"
```

---

### Task 8: Connection docs

**Files:**
- Create: `docs/mcp-server.md`

- [ ] **Step 1: Write usage docs**

Create `docs/mcp-server.md`:

```markdown
# oglabs MCP server

Exposes oglabs blog operations over MCP (streamable-HTTP) for remote agents.

## Run (Unraid / Docker)

1. Put the repo on the Unraid host. Set `OGLABS_REPO_PATH` to its path
   (or run `docker compose` from inside the repo).
2. Ensure `.env` has LLM keys and AWS credentials
   (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`,
   `S3_BUCKET`, `CLOUDFRONT_DISTRIBUTION_ID`).
3. `docker compose up -d`

The server listens on `0.0.0.0:8765`.

## Connect a remote agent

Point the agent's MCP client at:

    http://<unraid-host-ip>:8765/mcp

Transport: streamable-HTTP. No authentication (LAN only).

## Tools

- Content: `list_drafts`, `list_posts`, `read_post`, `create_draft`, `write_draft`
- Pipeline: `improve_writing`, `optimize_images`, `process_photos`
- Build/deploy: `build`, `deploy`, `publish`

## Local dev (no Docker)

    conda run -n oglabs make mcp
```

- [ ] **Step 2: Commit**

```bash
git add docs/mcp-server.md
git commit -m "docs: add MCP server usage guide"
```

---

## Self-Review Notes

- **Spec coverage:** content tools (Task 3), pipeline tools (Task 5), build/deploy
  without guard (Task 6), FastMCP/streamable-HTTP on 8765 (Task 1), path/section
  safety (Task 2), structured subprocess results (Task 4), Docker/Unraid with
  volume mount + env_file (Task 7), `mcp>=1.2` + `make mcp` (Tasks 1) — all present.
- **Section validation:** content tools use `CONTENT_SECTIONS` (blog/projects/photos);
  `improve_writing` uses `PIPELINE_SECTIONS` (blog/projects/all) to match the script's
  argparse choices. Intentional difference, consistent across tasks.
- **Naming consistency:** `_repo_root`, `_repo_path`, `_validate_section(section, allowed)`,
  `_slugify`, `_run`, `_parse_frontmatter`, `_list_md` used consistently in defs and tests.
- **No placeholders:** every code/command step is complete.
```