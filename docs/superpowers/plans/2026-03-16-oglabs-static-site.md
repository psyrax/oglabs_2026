# oglabs Static Site Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a personal static site with blog, code projects, and AI-described photography, powered by Pelican, with LLM-assisted writing and deployed to AWS S3.

**Architecture:** Pelican SSG reads from `content/` (blog, projects, photos). A `photo_pipeline.py` script processes raw camera photos, calls a vision LLM, and writes Markdown articles. An `improve_writing.py` script sends `drafts/` content through an LLM and saves the improved version to `content/`. A custom dark Jinja2 theme renders three distinct layouts: hero home, photo single-view, and minimal blog list.

**Tech Stack:** Python 3.11+, Pelican 4.9+, Pillow, piexif, Anthropic/OpenAI/Ollama SDKs, pytest, AWS CLI

---

## Chunk 1: Project Scaffold and Configuration

### Task 1: Directory structure and .gitignore

**Files:**
- Create: `drafts/blog/.gitkeep`
- Create: `drafts/projects/.gitkeep`
- Create: `drafts/images/.gitkeep`
- Create: `content/blog/.gitkeep`
- Create: `content/projects/.gitkeep`
- Create: `content/images/.gitkeep`
- Create: `content/photos/images/.gitkeep`
- Create: `photos/originals/.gitkeep`
- Create: `themes/oglabs/static/css/.gitkeep`
- Create: `themes/oglabs/static/js/.gitkeep`
- Create: `themes/oglabs/templates/.gitkeep`
- Create: `scripts/.gitkeep`
- Create: `tests/.gitkeep`
- Create: `.gitignore`

- [ ] **Step 1: Create all directories with .gitkeep files**

```bash
mkdir -p drafts/blog drafts/projects \
         content/blog content/projects content/photos/images \
         photos/originals \
         themes/oglabs/static/css themes/oglabs/static/js themes/oglabs/templates \
         scripts tests
touch drafts/blog/.gitkeep drafts/projects/.gitkeep drafts/images/.gitkeep \
      content/blog/.gitkeep content/projects/.gitkeep \
      content/images/.gitkeep content/photos/images/.gitkeep \
      photos/originals/.gitkeep \
      themes/oglabs/static/css/.gitkeep themes/oglabs/static/js/.gitkeep \
      themes/oglabs/templates/.gitkeep \
      scripts/.gitkeep tests/.gitkeep
```

- [ ] **Step 2: Create .gitignore**

```
output/
__pycache__/
*.pyc
.env
*.egg-info/
.pytest_cache/
photos/.processed_manifest.json
.superpowers/
```

- [ ] **Step 3: Commit**

```bash
git init
git add .
git commit -m "chore: initial project scaffold"
```

---

### Task 2: Python dependencies

**Files:**
- Create: `requirements.txt`
- Create: `requirements-dev.txt`

- [ ] **Step 1: Create requirements.txt**

```
pelican[markdown]>=4.9
Pillow>=10.0
piexif>=1.1
anthropic>=0.25
openai>=1.30
requests>=2.31
```

- [ ] **Step 2: Create requirements-dev.txt**

```
-r requirements.txt
pytest>=8.0
pytest-mock>=3.12
requests-mock>=1.11
```

- [ ] **Step 3: Install dependencies**

```bash
pip install -r requirements-dev.txt
```

Expected: all packages install without errors.

- [ ] **Step 4: Commit**

```bash
git add requirements.txt requirements-dev.txt
git commit -m "chore: add Python dependencies"
```

---

### Task 3: Pelican configuration

**Files:**
- Create: `pelicanconf.py`

- [ ] **Step 1: Create pelicanconf.py**

```python
SITENAME = 'oglabs'
SITEURL = ''

PATH = 'content'

TIMEZONE = 'America/Argentina/Buenos_Aires'
DEFAULT_LANG = 'es'

THEME = 'themes/oglabs'

# Content paths
ARTICLE_PATHS = ['blog', 'projects', 'photos']
ARTICLE_EXCLUDE_PATHS = ['photos/images']

# URL structure
ARTICLE_URL = '{category}/{slug}/'
ARTICLE_SAVE_AS = '{category}/{slug}/index.html'

CATEGORY_URL = '{slug}/'
CATEGORY_SAVE_AS = '{slug}/index.html'

# Static assets: fotos de galería + imágenes de posts de blog/proyectos
STATIC_PATHS = ['photos/images', 'images']

# Disable unused pages
PAGE_PATHS = []
PAGE_URL = '{slug}/'
PAGE_SAVE_AS = '{slug}/index.html'

# Feed settings (disabled for v1)
FEED_ALL_ATOM = None
CATEGORY_FEED_ATOM = None
TRANSLATION_FEED_ATOM = None
AUTHOR_FEED_ATOM = None
AUTHOR_FEED_RSS = None

# Pagination
DEFAULT_PAGINATION = False
```

- [ ] **Step 2: Verify Pelican can read the config without errors**

```bash
pelican content -s pelicanconf.py -o output --fatal errors 2>&1 | head -20
```

Expected: Pelican runs (may warn about empty content dirs, that's fine). No Python errors.

- [ ] **Step 3: Commit**

```bash
git add pelicanconf.py
git commit -m "chore: add Pelican configuration"
```

---

### Task 4: Makefile

**Files:**
- Create: `Makefile`

- [ ] **Step 1: Create Makefile**

```makefile
.PHONY: photos images build deploy publish clean

# Process new gallery photos (skips already-processed via manifest)
photos:
	python scripts/photo_pipeline.py

# Optimize new post images (skips already-processed via manifest)
images:
	python scripts/optimize_images.py

# Full build: process photos + images, then run Pelican
build: photos images
	pelican content -s pelicanconf.py -o output

# Deploy to S3 (S3_BUCKET must be set)
deploy:
	aws s3 sync output/ s3://$(S3_BUCKET)/ --delete

# Build + deploy in one step
publish: build deploy

# Remove generated output
clean:
	rm -rf output/
```

- [ ] **Step 2: Verify make help works**

```bash
make --dry-run build
```

Expected: prints the commands that would run without executing them.

- [ ] **Step 3: Commit**

```bash
git add Makefile
git commit -m "chore: add Makefile with build and deploy targets"
```

---

## Chunk 2: LLM Client

### Task 5: LLM client tests

**Files:**
- Create: `tests/test_llm_client.py`

- [ ] **Step 1: Write failing tests**

```python
import os
import sys
import pytest

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent / "scripts"))

from llm_client import get_client, OllamaClient, ClaudeClient, OpenAIClient, LLMClient


def test_get_client_ollama():
    client = get_client("ollama")
    assert isinstance(client, OllamaClient)


def test_get_client_claude():
    client = get_client("claude")
    assert isinstance(client, ClaudeClient)


def test_get_client_openai():
    client = get_client("openai")
    assert isinstance(client, OpenAIClient)


def test_get_client_uses_env_var(monkeypatch):
    monkeypatch.setenv("OGLABS_LLM", "ollama")
    client = get_client(None)
    assert isinstance(client, OllamaClient)


def test_get_client_invalid_backend():
    with pytest.raises(ValueError, match="Unknown LLM backend"):
        get_client("unknown")


def test_ollama_complete_calls_api(requests_mock):
    requests_mock.post(
        "http://localhost:11434/api/generate",
        json={"response": "Una foto hermosa."},
    )
    client = OllamaClient()
    result = client.complete("Describe esta foto.")
    assert result == "Una foto hermosa."


def test_ollama_complete_with_image(tmp_path, requests_mock):
    img = tmp_path / "test.jpg"
    img.write_bytes(b"fake-image-data")
    requests_mock.post(
        "http://localhost:11434/api/generate",
        json={"response": "Descripción de imagen."},
    )
    client = OllamaClient()
    result = client.complete("Describe.", image_path=str(img))
    assert result == "Descripción de imagen."
    # Verify image was sent as base64
    sent = requests_mock.last_request.json()
    assert "images" in sent


def test_claude_complete_calls_sdk(mocker):
    mock_anthropic = mocker.patch("llm_client.anthropic")
    mock_client = mock_anthropic.Anthropic.return_value
    mock_client.messages.create.return_value = mocker.Mock(
        content=[mocker.Mock(text="Texto mejorado.")]
    )
    client = ClaudeClient()
    result = client.complete("Mejora esto.")
    assert result == "Texto mejorado."
    mock_client.messages.create.assert_called_once()


def test_openai_complete_calls_sdk(mocker):
    mock_openai_module = mocker.patch("llm_client.OpenAI")
    mock_instance = mock_openai_module.return_value
    mock_instance.chat.completions.create.return_value = mocker.Mock(
        choices=[mocker.Mock(message=mocker.Mock(content="Respuesta."))]
    )
    client = OpenAIClient()
    result = client.complete("Hola.")
    assert result == "Respuesta."
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_llm_client.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError: No module named 'llm_client'`

---

### Task 6: LLM client implementation

**Files:**
- Create: `scripts/llm_client.py`

- [ ] **Step 1: Create scripts/llm_client.py**

```python
import base64
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

import anthropic
import requests
from openai import OpenAI


class LLMClient(ABC):
    @abstractmethod
    def complete(self, prompt: str, image_path: Optional[str] = None) -> str:
        pass


class OllamaClient(LLMClient):
    def __init__(self, model: str = "llava"):
        self.model = model
        self.host = os.getenv("OLLAMA_HOST", "http://localhost:11434")

    def complete(self, prompt: str, image_path: Optional[str] = None) -> str:
        payload: dict = {"model": self.model, "prompt": prompt, "stream": False}
        if image_path:
            with open(image_path, "rb") as f:
                payload["images"] = [base64.b64encode(f.read()).decode()]
        resp = requests.post(f"{self.host}/api/generate", json=payload)
        resp.raise_for_status()
        return resp.json()["response"]


class ClaudeClient(LLMClient):
    def __init__(self, model: str = "claude-opus-4-6"):
        self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = model

    def complete(self, prompt: str, image_path: Optional[str] = None) -> str:
        content: list = []
        if image_path:
            with open(image_path, "rb") as f:
                img_data = base64.b64encode(f.read()).decode()
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": "image/jpeg", "data": img_data},
            })
        content.append({"type": "text", "text": prompt})
        msg = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[{"role": "user", "content": content}],
        )
        return msg.content[0].text


class OpenAIClient(LLMClient):
    def __init__(self, model: str = "gpt-4o"):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = model

    def complete(self, prompt: str, image_path: Optional[str] = None) -> str:
        content: list = []
        if image_path:
            with open(image_path, "rb") as f:
                img_data = base64.b64encode(f.read()).decode()
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{img_data}"},
            })
        content.append({"type": "text", "text": prompt})
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": content}],
        )
        return resp.choices[0].message.content


def get_client(backend: Optional[str]) -> LLMClient:
    resolved = backend or os.getenv("OGLABS_LLM", "claude")
    if resolved == "ollama":
        return OllamaClient()
    if resolved == "claude":
        return ClaudeClient()
    if resolved == "openai":
        return OpenAIClient()
    raise ValueError(f"Unknown LLM backend: {resolved!r}. Choose ollama, claude, or openai.")
```

- [ ] **Step 2: Run tests to verify they pass**

```bash
pytest tests/test_llm_client.py -v
```

Expected: all 9 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add scripts/llm_client.py tests/test_llm_client.py
git commit -m "feat: add LLM client with Ollama, Claude, and OpenAI backends"
```

---

## Chunk 3: Photo Pipeline

### Task 7: Photo pipeline tests

**Files:**
- Create: `tests/test_photo_pipeline.py`

- [ ] **Step 1: Write failing tests**

```python
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
    import time
    photo_path = tmp_path / "photos/originals/nocam.jpg"
    photo_path.write_bytes(b"x")
    # Set a known modification time: 2024-01-15
    known_ts = datetime(2024, 1, 15, 12, 0, 0).timestamp()
    os.utime(photo_path, (known_ts, known_ts))
    web_path = tmp_path / "content/photos/images/nocam.jpg"
    write_article(photo_path, web_path, "Sin EXIF.", {})
    text = (tmp_path / "content/photos/nocam.md").read_text()
    assert "2024-01-15" in text
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_photo_pipeline.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'photo_pipeline'`

---

### Task 8: Photo pipeline implementation

**Files:**
- Create: `scripts/photo_pipeline.py`

- [ ] **Step 1: Create scripts/photo_pipeline.py**

```python
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import piexif
from PIL import Image

# Allow running from project root or scripts/
sys.path.insert(0, str(Path(__file__).parent))
from llm_client import get_client

MANIFEST_PATH = Path("photos/.processed_manifest.json")
ORIGINALS_DIR = Path("photos/originals")
WEB_DIR = Path("content/photos/images")
ARTICLES_DIR = Path("content/photos")

PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}

DESCRIPTION_PROMPT = (
    "Describe esta fotografía en un párrafo de 3-5 oraciones. "
    "Habla sobre la composición, la luz, el tema y el estado de ánimo que evoca. "
    "Escribe en español, en tercera persona."
)


def load_manifest() -> set:
    if MANIFEST_PATH.exists():
        return set(json.loads(MANIFEST_PATH.read_text()))
    return set()


def save_manifest(processed: set) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(sorted(processed), indent=2))


def new_photos(manifest: set) -> list:
    if not ORIGINALS_DIR.exists():
        return []
    return [
        p for p in ORIGINALS_DIR.iterdir()
        if p.suffix.lower() in PHOTO_EXTENSIONS and p.name not in manifest
    ]


def extract_exif(path: Path) -> dict:
    try:
        data = piexif.load(str(path))
        exif = data.get("Exif", {})
        ifd0 = data.get("0th", {})
        date_raw = exif.get(piexif.ExifIFD.DateTimeOriginal)
        camera_raw = ifd0.get(piexif.ImageIFD.Model, b"")
        aperture_raw = exif.get(piexif.ExifIFD.FNumber)
        speed_raw = exif.get(piexif.ExifIFD.ExposureTime)
        return {
            "date": date_raw.decode() if date_raw else None,
            "camera": camera_raw.decode(errors="replace").strip("\x00") if camera_raw else None,
            "iso": exif.get(piexif.ExifIFD.ISOSpeedRatings),
            "aperture": aperture_raw[0] / aperture_raw[1] if aperture_raw else None,
            "speed": f"{speed_raw[0]}/{speed_raw[1]}s" if speed_raw else None,
        }
    except Exception:
        return {}


def optimize_photo(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as img:
        img = img.convert("RGB")
        if max(img.size) > 2400:
            ratio = 2400 / max(img.size)
            new_size = (int(img.width * ratio), int(img.height * ratio))
            img = img.resize(new_size, Image.LANCZOS)
        img.save(dst, "JPEG", quality=92, optimize=True)


def write_article(photo_path: Path, web_path: Path, description: str, exif: dict) -> None:
    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
    slug = photo_path.stem
    date_str = exif.get("date") or ""
    try:
        dt = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
        date_fmt = dt.strftime("%Y-%m-%d")
    except ValueError:
        date_fmt = datetime.fromtimestamp(photo_path.stat().st_mtime).strftime("%Y-%m-%d")

    meta_lines = []
    if exif.get("camera"):
        meta_lines.append(f"- **Cámara:** {exif['camera']}")
    if exif.get("iso"):
        meta_lines.append(f"- **ISO:** {exif['iso']}")
    if exif.get("aperture") is not None:
        meta_lines.append(f"- **Apertura:** f/{exif['aperture']:.1f}")
    if exif.get("speed"):
        meta_lines.append(f"- **Velocidad:** {exif['speed']}")

    content = (
        f"Title: {slug}\n"
        f"Date: {date_fmt}\n"
        f"Category: photos\n"
        f"Slug: {slug}\n"
        f"Photo: {{static}}/photos/images/{web_path.name}\n\n"
        f"{description}\n\n"
        + ("\n".join(meta_lines) if meta_lines else "")
    )
    (ARTICLES_DIR / f"{slug}.md").write_text(content)


def process_photo(path: Path, llm_backend: Optional[str]) -> None:
    print(f"  Processing {path.name}...")
    exif = extract_exif(path)
    web_path = WEB_DIR / f"{path.stem}.jpg"
    optimize_photo(path, web_path)
    client = get_client(llm_backend)
    description = client.complete(DESCRIPTION_PROMPT, image_path=str(web_path))
    write_article(path, web_path, description, exif)
    print(f"  → content/photos/{path.stem}.md")


def main() -> None:
    parser = argparse.ArgumentParser(description="Process new photos for oglabs")
    parser.add_argument("--llm", default=None, choices=["ollama", "claude", "openai"])
    parser.add_argument("--force", action="store_true", help="Re-process already processed photos")
    args = parser.parse_args()

    manifest = set() if args.force else load_manifest()
    photos = (
        [p for p in ORIGINALS_DIR.iterdir() if p.suffix.lower() in PHOTO_EXTENSIONS]
        if args.force
        else new_photos(manifest)
    )

    if not photos:
        print("No new photos to process.")
        return

    print(f"Processing {len(photos)} photo(s)...")
    for photo in photos:
        process_photo(photo, args.llm)
        manifest.add(photo.name)

    save_manifest(manifest)
    print(f"\nDone. Processed {len(photos)} photo(s).")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run tests to verify they pass**

```bash
pytest tests/test_photo_pipeline.py -v
```

Expected: all 10 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add scripts/photo_pipeline.py tests/test_photo_pipeline.py
git commit -m "feat: add photo pipeline with EXIF extraction, optimization, and AI descriptions"
```

---

## Chunk 4: Writing Improvement Script

### Task 9: Writing improvement tests

**Files:**
- Create: `tests/test_improve_writing.py`

- [ ] **Step 1: Write failing tests**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_improve_writing.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'improve_writing'`

---

### Task 10: Writing improvement implementation

**Files:**
- Create: `scripts/improve_writing.py`

- [ ] **Step 1: Create scripts/improve_writing.py**

```python
import argparse
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))
from llm_client import LLMClient, get_client

DRAFTS_DIR = Path("drafts")
CONTENT_DIR = Path("content")

IMPROVE_PROMPT = """\
Eres un editor literario. Mejora la redacción del siguiente texto en Markdown.
Mantén el significado exacto, la voz del autor y el formato Markdown \
(incluyendo el frontmatter de Pelican al inicio si lo hay).
Solo devuelve el texto mejorado, sin explicaciones adicionales.

Texto:
{text}"""


def get_draft_files(section: str) -> list:
    sections = ["blog", "projects"] if section == "all" else [section]
    files = []
    for s in sections:
        draft_path = DRAFTS_DIR / s
        if draft_path.exists():
            files.extend(draft_path.glob("*.md"))
    return files


def improve_file(src: Path, section: str, client: LLMClient, no_overwrite: bool) -> bool:
    dst = CONTENT_DIR / section / src.name
    if no_overwrite and dst.exists():
        print(f"  Skipping {src.name} (already exists, use --overwrite to replace)")
        return False
    text = src.read_text()
    print(f"  Improving {src.name}...")
    improved = client.complete(IMPROVE_PROMPT.format(text=text))
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(improved)
    print(f"  → content/{section}/{src.name}")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Improve writing in drafts using an LLM")
    parser.add_argument("--section", required=True, choices=["blog", "projects", "all"])
    parser.add_argument("--llm", default=None, choices=["ollama", "claude", "openai"])
    parser.add_argument("--no-overwrite", action="store_true",
                        help="Skip files that already exist in content/")
    args = parser.parse_args()

    client = get_client(args.llm)
    sections = ["blog", "projects"] if args.section == "all" else [args.section]
    total = 0

    for section in sections:
        files = get_draft_files(section)
        if not files:
            print(f"  No drafts found in drafts/{section}/")
            continue
        for f in files:
            if improve_file(f, section, client, args.no_overwrite):
                total += 1

    print(f"\nDone. Improved {total} file(s).")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run tests to verify they pass**

```bash
pytest tests/test_improve_writing.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 3: Run all tests to confirm nothing is broken**

```bash
pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 4: Commit**

```bash
git add scripts/improve_writing.py tests/test_improve_writing.py
git commit -m "feat: add writing improvement script with multi-backend LLM support"
```

---

## Chunk 4b: Image Optimization Script

### Task 10b: Image optimization tests

**Files:**
- Create: `tests/test_optimize_images.py`

- [ ] **Step 1: Write failing tests**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_optimize_images.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'optimize_images'`

---

### Task 10c: Image optimization implementation

**Files:**
- Create: `scripts/optimize_images.py`

- [ ] **Step 1: Create scripts/optimize_images.py**

```python
import argparse
import json
from pathlib import Path

from PIL import Image

MANIFEST_PATH = Path("drafts/.images_manifest.json")
DRAFTS_DIR = Path("drafts/images")
OUTPUT_DIR = Path("content/images")

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}
MAX_SIDE = 1600
JPEG_QUALITY = 85


def load_manifest() -> set:
    if MANIFEST_PATH.exists():
        return set(json.loads(MANIFEST_PATH.read_text()))
    return set()


def save_manifest(processed: set) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(sorted(processed), indent=2))


def new_images(manifest: set) -> list:
    if not DRAFTS_DIR.exists():
        return []
    return [
        p for p in DRAFTS_DIR.iterdir()
        if p.suffix.lower() in IMAGE_EXTENSIONS and p.name not in manifest
    ]


def optimize_image(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as img:
        img = img.convert("RGB")
        if max(img.size) > MAX_SIDE:
            ratio = MAX_SIDE / max(img.size)
            new_size = (int(img.width * ratio), int(img.height * ratio))
            img = img.resize(new_size, Image.LANCZOS)
        img.save(dst, "JPEG", quality=JPEG_QUALITY, optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Optimize post images for web")
    parser.add_argument("--force", action="store_true", help="Re-process already processed images")
    args = parser.parse_args()

    manifest = set() if args.force else load_manifest()
    images = (
        [p for p in DRAFTS_DIR.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS]
        if args.force
        else new_images(manifest)
    )

    if not images:
        print("No new images to optimize.")
        return

    print(f"Optimizing {len(images)} image(s)...")
    for img_path in images:
        dst = OUTPUT_DIR / f"{img_path.stem}.jpg"
        print(f"  {img_path.name} → content/images/{dst.name}")
        optimize_image(img_path, dst)
        manifest.add(img_path.name)

    save_manifest(manifest)
    print(f"\nDone. Optimized {len(images)} image(s).")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run tests to verify they pass**

```bash
pytest tests/test_optimize_images.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 3: Run all tests to confirm nothing is broken**

```bash
pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 4: Commit**

```bash
git add scripts/optimize_images.py tests/test_optimize_images.py
git commit -m "feat: add image optimization script for blog/project posts"
```

---

## Chunk 5: Pelican Theme

### Task 11: Base template and CSS

**Files:**
- Create: `themes/oglabs/templates/base.html`
- Create: `themes/oglabs/static/css/style.css`

- [ ] **Step 1: Create themes/oglabs/templates/base.html**

```html
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}{{ SITENAME }}{% endblock %}</title>
  <link rel="stylesheet" href="{{ SITEURL }}/theme/css/style.css">
</head>
<body>
  <nav class="site-nav">
    <a class="site-name" href="{{ SITEURL }}/">{{ SITENAME }}</a>
    <ul>
      <li><a href="{{ SITEURL }}/blog/" {% if active_section == 'blog' %}class="active"{% endif %}>blog</a></li>
      <li><a href="{{ SITEURL }}/projects/" {% if active_section == 'projects' %}class="active"{% endif %}>proyectos</a></li>
      <li><a href="{{ SITEURL }}/photos/" {% if active_section == 'photos' %}class="active"{% endif %}>fotos</a></li>
    </ul>
  </nav>
  <main>
    {% block content %}{% endblock %}
  </main>
</body>
</html>
```

- [ ] **Step 2: Create themes/oglabs/static/css/style.css**

```css
:root {
  --bg: #0d0d0d;
  --bg-subtle: #111111;
  --text: #cccccc;
  --text-dim: #555555;
  --accent: #888888;
  --border: #1e1e1e;
  --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html { font-size: 16px; }

body {
  background: var(--bg);
  color: var(--text);
  font-family: var(--font);
  min-height: 100vh;
}

a { color: var(--text); text-decoration: none; }
a:hover { color: #fff; }

/* --- Navigation --- */
.site-nav {
  position: fixed;
  top: 0; left: 0; right: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.25rem 2rem;
  background: linear-gradient(to bottom, rgba(13,13,13,0.95), transparent);
}

.site-name {
  font-size: 1rem;
  font-weight: 500;
  letter-spacing: 0.05em;
  color: #fff;
}

.site-nav ul {
  list-style: none;
  display: flex;
  gap: 2rem;
}

.site-nav ul a {
  font-size: 0.8rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-dim);
  transition: color 0.2s;
}

.site-nav ul a:hover,
.site-nav ul a.active { color: var(--text); }

/* --- Hero (home) --- */
.hero {
  position: relative;
  width: 100%;
  height: 100vh;
  overflow: hidden;
  display: flex;
  align-items: flex-end;
}

.hero-image {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center;
}

.hero-overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(to top, rgba(13,13,13,0.7) 0%, transparent 50%);
}

.hero-caption {
  position: relative;
  padding: 2.5rem 2.5rem;
  max-width: 600px;
}

.hero-caption p {
  font-size: 0.9rem;
  color: rgba(204, 204, 204, 0.8);
  line-height: 1.6;
  margin-bottom: 1rem;
}

.hero-caption a.view-photo {
  font-size: 0.75rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--accent);
  border-bottom: 1px solid var(--border);
  padding-bottom: 2px;
  transition: color 0.2s, border-color 0.2s;
}

.hero-caption a.view-photo:hover {
  color: #fff;
  border-color: #555;
}

/* --- Photo single view --- */
.photo-view {
  display: flex;
  min-height: 100vh;
  padding-top: 4rem;
}

.photo-view__image-side {
  flex: 1.4;
  position: sticky;
  top: 4rem;
  height: calc(100vh - 4rem);
  overflow: hidden;
}

.photo-view__image-side img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  object-position: center;
  background: #000;
}

.photo-view__text-side {
  flex: 1;
  padding: 3rem 2.5rem;
  overflow-y: auto;
  max-height: calc(100vh - 4rem);
  border-left: 1px solid var(--border);
}

.photo-view__description {
  font-size: 0.95rem;
  line-height: 1.75;
  color: var(--text);
  margin-bottom: 2rem;
}

.photo-view__meta {
  font-size: 0.75rem;
  color: var(--text-dim);
  line-height: 1.8;
  margin-bottom: 2.5rem;
}

.photo-view__meta strong { color: var(--accent); }

.photo-nav {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-dim);
  border-top: 1px solid var(--border);
  padding-top: 1.5rem;
}

.photo-nav a { color: var(--text-dim); transition: color 0.2s; }
.photo-nav a:hover { color: var(--text); }

/* --- Blog / Projects list --- */
.post-list {
  max-width: 680px;
  margin: 0 auto;
  padding: 7rem 2rem 4rem;
}

.post-list__title {
  font-size: 0.7rem;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  color: var(--text-dim);
  margin-bottom: 3rem;
}

.post-list__item {
  border-bottom: 1px solid var(--border);
  padding: 1.5rem 0;
}

.post-list__item:last-child { border-bottom: none; }

.post-list__item-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 0.5rem;
}

.post-list__item-title {
  font-size: 1rem;
  font-weight: 400;
  color: var(--text);
}

.post-list__item-date {
  font-size: 0.75rem;
  color: var(--text-dim);
  white-space: nowrap;
  margin-left: 2rem;
}

.post-list__item-excerpt {
  font-size: 0.875rem;
  color: var(--text-dim);
  line-height: 1.6;
}

/* --- Article (blog/project post) --- */
.article {
  max-width: 680px;
  margin: 0 auto;
  padding: 7rem 2rem 4rem;
}

.article__header { margin-bottom: 3rem; }

.article__title {
  font-size: 1.6rem;
  font-weight: 400;
  color: var(--text);
  margin-bottom: 0.5rem;
  line-height: 1.3;
}

.article__date {
  font-size: 0.75rem;
  color: var(--text-dim);
}

.article__content {
  font-size: 0.975rem;
  line-height: 1.8;
  color: var(--text);
}

.article__content h1,
.article__content h2,
.article__content h3 {
  margin: 2rem 0 0.75rem;
  font-weight: 500;
  color: #e0e0e0;
}

.article__content p { margin-bottom: 1.25rem; }
.article__content code {
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  border-radius: 3px;
  padding: 0.1em 0.4em;
  font-size: 0.875em;
}

.article__content pre {
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 1.25rem;
  overflow-x: auto;
  margin-bottom: 1.25rem;
}

.article__content pre code {
  background: none;
  border: none;
  padding: 0;
  font-size: 0.85rem;
}
```

- [ ] **Step 3: Commit**

```bash
git add themes/
git commit -m "feat: add theme base template and dark CSS"
```

---

### Task 12: Home page template

**Files:**
- Create: `themes/oglabs/templates/index.html`

- [ ] **Step 1: Create themes/oglabs/templates/index.html**

```html
{% extends "base.html" %}

{% block content %}
{% set photo_articles = articles | selectattr("category.slug", "equalto", "photos") | sort(attribute="date", reverse=True) | list %}
{% if photo_articles %}
  {% set hero = photo_articles[0] %}
  <section class="hero">
    <img class="hero-image" src="{{ SITEURL }}/{{ hero.photo }}" alt="{{ hero.title }}">
    <div class="hero-overlay"></div>
    <div class="hero-caption">
      <p>{{ hero.summary }}</p>
      <a class="view-photo" href="{{ SITEURL }}/{{ hero.url }}">Ver foto →</a>
    </div>
  </section>
{% else %}
  <section class="hero" style="align-items:center;justify-content:center">
    <div style="text-align:center">
      <p style="color:var(--text-dim);font-size:0.9rem">Aún no hay fotos publicadas.</p>
    </div>
  </section>
{% endif %}
{% endblock %}
```

- [ ] **Step 2: Commit**

```bash
git add themes/oglabs/templates/index.html
git commit -m "feat: add home page template with hero photo"
```

---

### Task 13: Category template (blog/projects list + photos index)

**Files:**
- Create: `themes/oglabs/templates/category.html`

- [ ] **Step 1: Create themes/oglabs/templates/category.html**

```html
{% extends "base.html" %}
{% set active_section = category.slug %}

{% block title %}{{ category.name }} — {{ SITENAME }}{% endblock %}

{% block content %}
{% if category.slug == 'photos' %}
  {# Photos category: redirect to most recent photo #}
  {% set sorted = articles | sort(attribute="date", reverse=True) | list %}
  {% if sorted %}
    <p style="padding:8rem 2rem;text-align:center;color:var(--text-dim)">
      Redirigiendo a la última foto…
      <a href="{{ SITEURL }}/{{ sorted[0].url }}">click aquí</a>
    </p>
    <script>window.location.replace("{{ SITEURL }}/{{ sorted[0].url }}");</script>
  {% endif %}
{% else %}
  <div class="post-list">
    <p class="post-list__title">{{ category.name }}</p>
    {% for article in articles | sort(attribute="date", reverse=True) %}
    <div class="post-list__item">
      <div class="post-list__item-header">
        <a class="post-list__item-title" href="{{ SITEURL }}/{{ article.url }}">{{ article.title }}</a>
        <span class="post-list__item-date">{{ article.date.strftime('%b %Y') }}</span>
      </div>
      {% if article.summary %}
      <p class="post-list__item-excerpt">{{ article.summary | striptags | truncate(160) }}</p>
      {% endif %}
    </div>
    {% endfor %}
  </div>
{% endif %}
{% endblock %}
```

- [ ] **Step 2: Commit**

```bash
git add themes/oglabs/templates/category.html
git commit -m "feat: add category template for blog/projects lists and photos redirect"
```

---

### Task 14: Article template (photo single view + blog/project post)

**Files:**
- Create: `themes/oglabs/templates/article.html`

- [ ] **Step 1: Create themes/oglabs/templates/article.html**

```html
{% extends "base.html" %}
{% set active_section = article.category.slug %}

{% block title %}{{ article.title }} — {{ SITENAME }}{% endblock %}

{% block content %}
{% if article.category.slug == 'photos' %}
  {# --- Photo single view --- #}
  {% set photo_articles = articles | selectattr("category.slug", "equalto", "photos") | sort(attribute="date", reverse=True) | list %}
  {% set ns = namespace(idx=0) %}
  {% for a in photo_articles %}
    {% if a.slug == article.slug %}{% set ns.idx = loop.index0 %}{% endif %}
  {% endfor %}
  {% set prev_photo = photo_articles[ns.idx + 1] if ns.idx + 1 < photo_articles | length else None %}
  {% set next_photo = photo_articles[ns.idx - 1] if ns.idx > 0 else None %}

  <div class="photo-view">
    <div class="photo-view__image-side">
      <img src="{{ SITEURL }}/{{ article.photo }}" alt="{{ article.title }}">
    </div>
    <div class="photo-view__text-side">
      <div class="photo-view__description">
        {{ article.content }}
      </div>
      <div class="photo-nav">
        {% if prev_photo %}
          <a href="{{ SITEURL }}/{{ prev_photo.url }}">← anterior</a>
        {% else %}
          <span></span>
        {% endif %}
        {% if next_photo %}
          <a href="{{ SITEURL }}/{{ next_photo.url }}">siguiente →</a>
        {% else %}
          <span></span>
        {% endif %}
      </div>
    </div>
  </div>

{% else %}
  {# --- Blog / Project post --- #}
  <article class="article">
    <header class="article__header">
      <h1 class="article__title">{{ article.title }}</h1>
      <p class="article__date">{{ article.date.strftime('%d %b %Y') }}</p>
    </header>
    <div class="article__content">
      {{ article.content }}
    </div>
  </article>
{% endif %}
{% endblock %}
```

- [ ] **Step 2: Commit**

```bash
git add themes/oglabs/templates/article.html
git commit -m "feat: add article template for photo single view and blog/project posts"
```

---

### Task 15: End-to-end smoke test

**Files:**
- Create: `content/blog/hola-mundo.md`
- Create: `content/projects/primer-proyecto.md`

- [ ] **Step 1: Create a sample blog post**

```markdown
Title: Hola mundo
Date: 2026-03-16
Category: blog
Slug: hola-mundo

Este es el primer post del blog. Un espacio para pensamientos random, notas y reflexiones.

El sitio está construido con Pelican y un tema custom oscuro.
```

- [ ] **Step 2: Create a sample project post**

```markdown
Title: oglabs
Date: 2026-03-16
Category: projects
Slug: oglabs

El sitio en el que estás parado ahora mismo.

Pelican + Python + tema Jinja2 custom. Deploy en AWS S3.
```

- [ ] **Step 3: Run Pelican build**

```bash
pelican content -s pelicanconf.py -o output
```

Expected: build completes without errors. Output printed to terminal.

- [ ] **Step 4: Verify output structure**

```bash
ls output/
ls output/blog/
ls output/projects/
```

Expected:
- `output/blog/hola-mundo/index.html` exists
- `output/projects/oglabs/index.html` exists
- `output/blog/index.html` exists
- `output/index.html` exists

- [ ] **Step 5: Serve locally and verify visually**

```bash
python -m http.server 8000 --directory output
```

Open `http://localhost:8000` in a browser. Verify:
- Home page loads with dark background
- Nav shows `blog · proyectos · fotos`
- `/blog/` shows the minimal list with "Hola mundo"
- `/blog/hola-mundo/` shows the post content
- No console errors

- [ ] **Step 6: Commit sample content and verify output is gitignored**

```bash
git status  # output/ should NOT appear
git add content/blog/hola-mundo.md content/projects/primer-proyecto.md
git commit -m "chore: add sample content for smoke test"
```

---
