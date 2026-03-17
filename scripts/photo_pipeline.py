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
