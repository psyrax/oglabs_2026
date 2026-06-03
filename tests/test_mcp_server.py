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
