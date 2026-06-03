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
