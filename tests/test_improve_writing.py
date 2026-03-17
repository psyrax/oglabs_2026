import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


@pytest.fixture(autouse=True)
def isolate_fs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "drafts/blog").mkdir(parents=True)
    (tmp_path / "drafts/projects").mkdir(parents=True)
    (tmp_path / "content/blog").mkdir(parents=True)
    (tmp_path / "content/projects").mkdir(parents=True)


def write_draft(section: str, filename: str, content: str, tmp_path: Path):
    (tmp_path / f"drafts/{section}/{filename}").write_text(content)


def test_get_draft_files_returns_blog_files(tmp_path):
    write_draft("blog", "post1.md", "# Post 1", tmp_path)
    write_draft("blog", "post2.md", "# Post 2", tmp_path)
    from improve_writing import get_draft_files
    files = get_draft_files("blog")
    names = {f.name for f in files}
    assert names == {"post1.md", "post2.md"}


def test_get_draft_files_all_returns_both_sections(tmp_path):
    write_draft("blog", "b.md", "blog", tmp_path)
    write_draft("projects", "p.md", "project", tmp_path)
    from improve_writing import get_draft_files
    files = get_draft_files("all")
    sections = {f.parent.name for f in files}
    assert sections == {"blog", "projects"}


def test_get_draft_files_returns_empty_for_missing_section(tmp_path):
    from improve_writing import get_draft_files
    files = get_draft_files("blog")
    assert files == []


def test_improve_file_creates_output(tmp_path, mocker):
    write_draft("blog", "post.md", "# Draft post\nContenido.", tmp_path)
    mock_client = mocker.Mock()
    mock_client.complete.return_value = "# Post mejorado\nContenido mejorado."
    from improve_writing import improve_file
    src = tmp_path / "drafts/blog/post.md"
    result = improve_file(src, "blog", mock_client, no_overwrite=False)
    assert result is True
    out = tmp_path / "content/blog/post.md"
    assert out.exists()
    assert out.read_text() == "# Post mejorado\nContenido mejorado."


def test_improve_file_no_overwrite_skips_existing(tmp_path, mocker):
    write_draft("blog", "post.md", "# Original", tmp_path)
    (tmp_path / "content/blog/post.md").write_text("# Ya existe")
    mock_client = mocker.Mock()
    from improve_writing import improve_file
    src = tmp_path / "drafts/blog/post.md"
    result = improve_file(src, "blog", mock_client, no_overwrite=True)
    assert result is False
    mock_client.complete.assert_not_called()
    assert (tmp_path / "content/blog/post.md").read_text() == "# Ya existe"


def test_improve_file_overwrite_replaces_existing(tmp_path, mocker):
    write_draft("blog", "post.md", "# Original", tmp_path)
    (tmp_path / "content/blog/post.md").write_text("# Anterior")
    mock_client = mocker.Mock()
    mock_client.complete.return_value = "# Nuevo mejorado"
    from improve_writing import improve_file
    src = tmp_path / "drafts/blog/post.md"
    improve_file(src, "blog", mock_client, no_overwrite=False)
    assert (tmp_path / "content/blog/post.md").read_text() == "# Nuevo mejorado"


def test_improve_file_sends_full_text_to_llm(tmp_path, mocker):
    draft_text = "Title: Mi Post\nDate: 2026-01-01\n\n# Contenido raw"
    write_draft("blog", "post.md", draft_text, tmp_path)
    mock_client = mocker.Mock()
    mock_client.complete.return_value = "improved"
    from improve_writing import improve_file
    src = tmp_path / "drafts/blog/post.md"
    improve_file(src, "blog", mock_client, no_overwrite=False)
    call_args = mock_client.complete.call_args[0][0]
    assert draft_text in call_args
