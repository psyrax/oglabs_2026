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


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
