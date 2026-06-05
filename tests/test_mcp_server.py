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
    mcp_server.process_photos(force=True)
    run.assert_called_once_with(
        ["python", "scripts/photo_pipeline.py", "--force"]
    )


# --- security hardening regression tests ---

def test_read_post_rejects_dotenv(repo):
    (repo / ".env").write_text("SECRET=shhh")
    with pytest.raises(ValueError):
        mcp_server.read_post(".env")


def test_read_post_rejects_non_md(repo):
    with pytest.raises(ValueError, match="Only .md files"):
        mcp_server.read_post("content/blog/secret.txt")


def test_read_post_rejects_outside_bases(repo):
    with pytest.raises(ValueError, match="Path must be"):
        mcp_server.read_post("scripts/llm_client.md")


def test_read_post_rejects_dotdot_traversal(repo):
    # A .md file inside the repo but outside drafts/ or content/.
    (repo / "secret.md").write_text("Title: Secret\n")
    with pytest.raises(ValueError, match="Path must be"):
        mcp_server.read_post("drafts/../secret.md")


def test_write_draft_rejects_traversal_slug(repo):
    with pytest.raises(ValueError, match="Invalid slug"):
        mcp_server.write_draft("blog", "../../content/blog/pwned", "x")


def test_list_md_rejects_bad_section(repo):
    with pytest.raises(ValueError, match="Invalid section"):
        mcp_server.list_drafts("../")


def test_publish_draft_copies_to_content(repo):
    mcp_server.write_draft("blog", "mi-post", "Title: Mi Post\n\nCuerpo.")
    rel = mcp_server.publish_draft("blog", "mi-post")
    assert rel == "content/blog/mi-post.md"
    assert (repo / "content/blog/mi-post.md").read_text() == "Title: Mi Post\n\nCuerpo."
    # original draft is left in place
    assert (repo / "drafts/blog/mi-post.md").exists()


def test_publish_draft_missing_raises(repo):
    with pytest.raises(ValueError, match="Draft not found"):
        mcp_server.publish_draft("blog", "no-existe")


def test_publish_draft_rejects_bad_slug(repo):
    with pytest.raises(ValueError, match="Invalid slug"):
        mcp_server.publish_draft("blog", "../../etc/passwd")


@pytest.mark.parametrize("tool,target", [
    ("build", "build"), ("deploy", "deploy"), ("publish", "publish"),
])
def test_build_deploy_tools(repo, mocker, tool, target):
    run = mocker.patch("mcp_server._run", return_value={"ok": True})
    getattr(mcp_server, tool)()
    run.assert_called_once_with(["make", target])
