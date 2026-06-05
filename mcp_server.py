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
# Top-level dirs that read_post is allowed to read from.
CONTENT_BASES = {"drafts", "content"}

mcp = FastMCP(
    "oglabs",
    host="0.0.0.0",
    port=int(os.getenv("OGLABS_MCP_PORT", "8765")),
)


def _repo_root() -> Path:
    """Resolve the repo root. Override with OGLABS_REPO_ROOT (used in tests)."""
    return Path(os.getenv("OGLABS_REPO_ROOT", Path(__file__).resolve().parent))


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


def _safe_slug(slug: str) -> str:
    """Reject slugs with path separators or other unsafe characters."""
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", slug):
        raise ValueError(
            f"Invalid slug {slug!r}. Use lowercase letters, digits, and hyphens."
        )
    return slug


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
    slug = _safe_slug(slug)
    path = _repo_path("drafts", section, f"{slug}.md")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return str(path.relative_to(_repo_root()))


def _list_md(base: str, section: str | None) -> list[str]:
    if section is not None:
        _validate_section(section, CONTENT_SECTIONS)
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
def publish_draft(section: str, slug: str) -> str:
    """Promote a draft to the published tree so the build picks it up.

    Copies drafts/<section>/<slug>.md to content/<section>/ verbatim (no LLM).
    The site is built from content/, so a draft must be published before build.
    """
    _validate_section(section, CONTENT_SECTIONS)
    slug = _safe_slug(slug)
    src = _repo_path("drafts", section, f"{slug}.md")
    if not src.is_file():
        raise ValueError(f"Draft not found: drafts/{section}/{slug}.md")
    dst = _repo_path("content", section, f"{slug}.md")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(src.read_text())
    return str(dst.relative_to(_repo_root()))


@mcp.tool()
def delete_draft(section: str, slug: str) -> str:
    """Delete drafts/<section>/<slug>.md.

    Only removes the draft; a published copy under content/ is left untouched.
    """
    _validate_section(section, CONTENT_SECTIONS)
    slug = _safe_slug(slug)
    path = _repo_path("drafts", section, f"{slug}.md")
    if not path.is_file():
        raise ValueError(f"Draft not found: drafts/{section}/{slug}.md")
    path.unlink()
    return f"deleted drafts/{section}/{slug}.md"


@mcp.tool()
def publish_draft_live(section: str, slug: str) -> dict:
    """Promote a draft and push the site live in one step (production).

    Promotes drafts/<section>/<slug>.md to content/, then runs `make publish`
    (build + scrub + S3 sync + CloudFront invalidation). Returns the promoted
    path and the structured publish result.
    """
    published = publish_draft(section, slug)
    return {"published": published, "result": _run(["make", "publish"])}


@mcp.tool()
def read_post(path: str) -> dict:
    """Read a content/draft .md file (relative to repo root).

    Restricted to .md files under drafts/ or content/ so the tool cannot be
    used to disclose other repo files (e.g. .env).
    """
    if not path.endswith(".md"):
        raise ValueError("Only .md files are readable.")
    parts = Path(path).parts
    if (not parts or parts[0] not in CONTENT_BASES
            or ".." in parts or any(Path(x).is_absolute() for x in parts)):
        raise ValueError(
            "Path must be a relative .md path under drafts/ or content/."
        )
    base = _repo_path(parts[0])
    p = _repo_path(*parts)
    try:
        p.relative_to(base)
    except ValueError:
        raise ValueError(f"Path escapes allowed base: {path}")
    if not p.is_file():
        raise ValueError(f"File not found: {path}")
    return _parse_frontmatter(p.read_text())


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


@mcp.tool()
def improve_writing(
    section: str, llm: str | None = None, overwrite: bool = True
) -> dict:
    """Improve drafts in a section with an LLM (scripts/improve_writing.py).

    section: 'blog', 'projects', or 'all'. llm: 'ollama'|'claude'.
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
def process_photos(force: bool = False) -> dict:
    """Process new gallery photos with cloud Ollama models (scripts/photo_pipeline.py)."""
    cmd = ["python", "scripts/photo_pipeline.py"]
    if force:
        cmd.append("--force")
    return _run(cmd)


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


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
