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

# Full workflow reference. Surfaced verbatim by the guide() tool and the
# publish_blog_post prompt; SERVER_INSTRUCTIONS below is the short version that
# every client sees on connect.
WORKFLOW_GUIDE = """\
oglabs is a Pelican static site (blog + projects + photo galleries) deployed to
S3 + CloudFront. This MCP lets a remote agent drive the whole content lifecycle.

Key invariant: the site builds ONLY from content/. Drafts live in drafts/ and are
invisible to the build until promoted.

Typical flow to publish a post
  1. list_posts(section) + read_post(path) — study existing voice, format and
     Pelican frontmatter (Title, Date, Category, Slug; Spanish, technical, first
     person) before writing anything.
  2. create_draft(section, title) — creates drafts/<section>/<slug>.md with
     frontmatter. Returns the path.
  3. write_draft(section, slug, content) — write the full markdown (frontmatter
     included). Optionally improve_writing(section) to polish via the homelab LLM.
  4. publish_draft(section, slug) — copy the draft verbatim into content/ so the
     build can see it.
  5. build() — render the site into output/. Review for errors.
  6. CONFIRM WITH THE USER, then deploy() or publish(). These push to PRODUCTION
     (S3 + CloudFront) and have no auth — always confirm before calling them.
  One-shot after confirmation: publish_draft_live(section, slug) = promote + publish.

Removing a post
  - delete_draft(section, slug) — removes only the draft.
  - delete_post(section, slug) — removes the published content/ file (next build
    drops it).
  - delete_post_live(section, slug) — removes it AND runs publish so it disappears
    from production in one call.

Sections: blog, projects, photos. A `projects` post whose title mentions the
Mundial is auto-tagged at build and shown in the /projects/mundial/ subsection —
no manual tag needed; just put "Mundial" in the title. deploy runs a secret
scrubber over output/ before the S3 sync. The server is LAN-only and
unauthenticated by design.
"""

SERVER_INSTRUCTIONS = """\
Drive the oglabs static blog (Pelican → S3/CloudFront). The site builds ONLY from
content/; drafts in drafts/ are invisible until promoted with publish_draft.

Publish flow: list_posts/read_post (study style) → create_draft → write_draft →
publish_draft → build → (confirm with the user) → deploy/publish. Shortcut after
confirmation: publish_draft_live. Remove posts with delete_post / delete_post_live.

deploy(), publish(), publish_draft_live() and delete_post_live() push to PRODUCTION
and have no auth — always confirm with the user before calling them. Call guide()
for the full workflow, or use the publish_blog_post prompt.
"""

mcp = FastMCP(
    "oglabs",
    instructions=SERVER_INSTRUCTIONS,
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
    """Create a new draft under drafts/<section>/ with starter Pelican frontmatter.

    Step 2 of the publish flow (after studying existing posts). Returns the path;
    fill it in with write_draft. Does not publish — the draft stays out of the build.
    """
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
    """Write (overwrite) the full markdown of drafts/<section>/<slug>.md.

    `content` must include the Pelican frontmatter (Title, Date, Category, Slug).
    Still a draft afterwards: promote with publish_draft before build/deploy.
    """
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
    """List draft .md files under drafts/ (optionally one section: blog/projects/photos).

    Drafts are not part of the live site until promoted with publish_draft.
    """
    return _list_md("drafts", section)


@mcp.tool()
def list_posts(section: str | None = None) -> list[str]:
    """List published .md files under content/ (optionally one section: blog/projects/photos).

    These are what the site builds from. Read a couple with read_post to match the
    blog's voice and frontmatter before writing a new draft.
    """
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
def delete_post(section: str, slug: str) -> str:
    """Delete a published post: content/<section>/<slug>.md.

    Removes the file from the content tree so the next build drops it. The live
    site keeps serving it until a build+deploy runs — use delete_post_live to
    take it down from production in one step. Any draft under drafts/ is left
    untouched.
    """
    _validate_section(section, CONTENT_SECTIONS)
    slug = _safe_slug(slug)
    path = _repo_path("content", section, f"{slug}.md")
    if not path.is_file():
        raise ValueError(f"Post not found: content/{section}/{slug}.md")
    path.unlink()
    return f"deleted content/{section}/{slug}.md"


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
def delete_post_live(section: str, slug: str) -> dict:
    """Delete a published post and take it down from production in one step.

    Removes content/<section>/<slug>.md, then runs `make publish` (build + scrub
    + S3 sync --delete + CloudFront invalidation), so the post disappears from the
    live site. Any draft under drafts/ is left untouched. Returns the removed path
    and the structured publish result.
    """
    deleted = delete_post(section, slug)
    return {"deleted": deleted, "result": _run(["make", "publish"])}


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
    """Polish drafts in a section with an LLM (scripts/improve_writing.py).

    section: 'blog', 'projects', or 'all'. llm: 'ollama' (homelab) | 'claude'.
    Optional step after write_draft. With overwrite=True (default) it writes the
    improved version into content/, so you can skip a separate publish_draft.
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
    """Render the site into output/ (make build): photos + images + pelican.

    Builds ONLY from content/, so promote drafts with publish_draft first. Safe
    to run anytime — it does not touch production. Review the result before deploy.
    """
    return _run(["make", "build"])


@mcp.tool()
def deploy() -> dict:
    """PRODUCTION: sync output/ to S3 (--delete) and invalidate CloudFront.

    Pushes the live site and has no auth — confirm with the user before calling.
    Runs the secret scrubber over output/ first. Run build() beforehand so output/
    reflects the latest content.
    """
    return _run(["make", "deploy"])


@mcp.tool()
def publish() -> dict:
    """PRODUCTION: build then deploy in one step (make publish).

    Equivalent to build() + deploy(). Pushes the live site with no auth — confirm
    with the user before calling.
    """
    return _run(["make", "publish"])


@mcp.tool()
def guide() -> str:
    """Return the full oglabs content workflow: how to write, publish, and remove
    posts, plus the key invariants (builds from content/ only; confirm before
    production). Call this first when you are new to this server."""
    return WORKFLOW_GUIDE


@mcp.prompt()
def publish_blog_post(tema: str) -> str:
    """Guided workflow for an agent to write and publish a blog post on oglabs.

    `tema` is the topic of the post. Returns a step-by-step task prompt.
    """
    return (
        f"## Tarea: escribir y publicar un blog post en oglabs vía su MCP\n\n"
        f"**Tema del post:** {tema}\n\n"
        f"{WORKFLOW_GUIDE}\n"
        "Empieza listando posts existentes con list_posts('blog') y leyendo 1-2 "
        "con read_post(...) para captar el estilo. Propón el título al usuario, "
        "escribe el draft, y DETENTE para confirmar antes de cualquier paso de "
        "producción (deploy/publish/publish_draft_live)."
    )


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
