import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


@pytest.fixture(autouse=True)
def isolate_fs(tmp_path, monkeypatch):
    """Run each test in a fresh tmp_path as the working directory."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "photos/originals").mkdir(parents=True)
    (tmp_path / "content/photos/images").mkdir(parents=True)
    (tmp_path / "content/photos").mkdir(parents=True, exist_ok=True)


def make_jpeg(path: Path, width: int = 100, height: int = 100):
    img = Image.new("RGB", (width, height), color=(100, 150, 200))
    img.save(path, "JPEG")


# --- manifest ---

def test_load_manifest_missing_file():
    from photo_pipeline import load_manifest
    result = load_manifest()
    assert result == set()


def test_load_manifest_existing_file(tmp_path):
    manifest = tmp_path / "photos/.processed_manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(["DSC_001.jpg", "DSC_002.jpg"]))
    from photo_pipeline import load_manifest
    result = load_manifest()
    assert result == {"DSC_001.jpg", "DSC_002.jpg"}


def test_save_manifest(tmp_path):
    from photo_pipeline import save_manifest, load_manifest
    save_manifest({"a.jpg", "b.jpg"})
    assert load_manifest() == {"a.jpg", "b.jpg"}


# --- new_photos ---

def test_new_photos_returns_unprocessed(tmp_path):
    orig = tmp_path / "photos/originals"
    (orig / "new.jpg").write_bytes(b"x")
    (orig / "old.jpg").write_bytes(b"x")
    from photo_pipeline import new_photos
    result = new_photos({"old.jpg"})
    assert len(result) == 1
    assert result[0].name == "new.jpg"


def test_new_photos_ignores_non_images(tmp_path):
    orig = tmp_path / "photos/originals"
    (orig / "readme.txt").write_text("ignore me")
    (orig / "photo.jpg").write_bytes(b"x")
    from photo_pipeline import new_photos
    result = new_photos(set())
    assert all(p.suffix.lower() in {".jpg", ".jpeg", ".png", ".tif", ".tiff"} for p in result)
    assert len(result) == 1


# --- optimize_photo ---

def test_optimize_photo_creates_jpeg(tmp_path):
    src = tmp_path / "photos/originals/test.jpg"
    dst = tmp_path / "content/photos/images/test.jpg"
    make_jpeg(src)
    from photo_pipeline import optimize_photo
    optimize_photo(src, dst)
    assert dst.exists()
    with Image.open(dst) as img:
        assert img.format == "JPEG"


def test_optimize_photo_resizes_large_image(tmp_path):
    src = tmp_path / "photos/originals/big.jpg"
    dst = tmp_path / "content/photos/images/big.jpg"
    make_jpeg(src, width=5000, height=3000)
    from photo_pipeline import optimize_photo
    optimize_photo(src, dst)
    with Image.open(dst) as img:
        assert max(img.size) <= 2400


def test_optimize_photo_preserves_small_image(tmp_path):
    src = tmp_path / "photos/originals/small.jpg"
    dst = tmp_path / "content/photos/images/small.jpg"
    make_jpeg(src, width=800, height=600)
    from photo_pipeline import optimize_photo
    optimize_photo(src, dst)
    with Image.open(dst) as img:
        assert img.size == (800, 600)


# --- write_article ---

def test_write_article_creates_markdown(tmp_path):
    from photo_pipeline import write_article
    photo_path = tmp_path / "photos/originals/sunset.jpg"
    photo_path.write_bytes(b"x")
    web_path = tmp_path / "content/photos/images/sunset.jpg"
    exif = {"date": "2024:06:15 18:30:00", "camera": "Sony A7", "iso": 200, "aperture": 2.8, "speed": "1/500s"}
    write_article(photo_path, web_path, "Hermosa puesta de sol.", exif)
    article = tmp_path / "content/photos/sunset.md"
    assert article.exists()
    text = article.read_text()
    assert "Title: sunset" in text
    assert "Date: 2024-06-15" in text
    assert "Category: photos" in text
    assert "{static}/photos/images/sunset.jpg" in text
    assert "Hermosa puesta de sol." in text
    assert "Sony A7" in text


def test_write_article_uses_mtime_when_no_exif(tmp_path):
    from photo_pipeline import write_article
    photo_path = tmp_path / "photos/originals/nocam.jpg"
    photo_path.write_bytes(b"x")
    # Set a known modification time: 2024-01-15
    known_ts = datetime(2024, 1, 15, 12, 0, 0).timestamp()
    os.utime(photo_path, (known_ts, known_ts))
    web_path = tmp_path / "content/photos/images/nocam.jpg"
    write_article(photo_path, web_path, "Sin EXIF.", {})
    text = (tmp_path / "content/photos/nocam.md").read_text()
    assert "2024-01-15" in text
