import json
import os
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


@pytest.fixture(autouse=True)
def isolate_fs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "drafts/images").mkdir(parents=True)
    (tmp_path / "content/images").mkdir(parents=True)


def make_jpeg(path: Path, width: int = 100, height: int = 100):
    img = Image.new("RGB", (width, height), color=(100, 150, 200))
    img.save(path, "JPEG")


def test_load_manifest_missing():
    from optimize_images import load_manifest
    assert load_manifest() == set()


def test_save_and_load_manifest(tmp_path):
    from optimize_images import save_manifest, load_manifest
    save_manifest({"a.jpg", "b.png"})
    assert load_manifest() == {"a.jpg", "b.png"}


def test_new_images_returns_unprocessed(tmp_path):
    (tmp_path / "drafts/images/new.jpg").write_bytes(b"x")
    (tmp_path / "drafts/images/old.jpg").write_bytes(b"x")
    from optimize_images import new_images
    result = new_images({"old.jpg"})
    assert len(result) == 1
    assert result[0].name == "new.jpg"


def test_new_images_ignores_non_images(tmp_path):
    (tmp_path / "drafts/images/readme.txt").write_text("ignore")
    (tmp_path / "drafts/images/photo.jpg").write_bytes(b"x")
    from optimize_images import new_images
    result = new_images(set())
    assert len(result) == 1
    assert result[0].name == "photo.jpg"


def test_optimize_image_creates_jpeg(tmp_path):
    src = tmp_path / "drafts/images/test.jpg"
    dst = tmp_path / "content/images/test.jpg"
    make_jpeg(src)
    from optimize_images import optimize_image
    optimize_image(src, dst)
    assert dst.exists()
    with Image.open(dst) as img:
        assert img.format == "JPEG"


def test_optimize_image_resizes_large(tmp_path):
    src = tmp_path / "drafts/images/big.jpg"
    dst = tmp_path / "content/images/big.jpg"
    make_jpeg(src, width=3000, height=2000)
    from optimize_images import optimize_image
    optimize_image(src, dst)
    with Image.open(dst) as img:
        assert max(img.size) <= 1600


def test_optimize_image_preserves_small(tmp_path):
    src = tmp_path / "drafts/images/small.jpg"
    dst = tmp_path / "content/images/small.jpg"
    make_jpeg(src, width=800, height=600)
    from optimize_images import optimize_image
    optimize_image(src, dst)
    with Image.open(dst) as img:
        assert img.size == (800, 600)
