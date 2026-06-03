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


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
