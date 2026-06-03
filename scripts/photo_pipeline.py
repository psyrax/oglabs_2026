import argparse
import base64
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import piexif
import requests
from dotenv import load_dotenv
from PIL import Image

load_dotenv(Path(__file__).parent.parent / ".env")

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


def _decode_exif_value(val):
    if isinstance(val, bytes):
        return val.decode(errors="replace").strip("\x00")
    if isinstance(val, tuple) and len(val) == 2 and val[1] != 0:
        return f"{val[0]}/{val[1]}"
    return val


def extract_exif(path: Path) -> dict:
    try:
        data = piexif.load(str(path))
        exif = data.get("Exif", {})
        ifd0 = data.get("0th", {})
        gps = data.get("GPS", {})

        # Structured fields used internally
        date_raw = exif.get(piexif.ExifIFD.DateTimeOriginal)
        camera_raw = ifd0.get(piexif.ImageIFD.Model, b"")
        aperture_raw = exif.get(piexif.ExifIFD.FNumber)
        speed_raw = exif.get(piexif.ExifIFD.ExposureTime)

        # All readable fields for display
        label_map = {
            "0th": {v: k for k, v in piexif.ImageIFD.__dict__.items() if isinstance(v, int)},
            "Exif": {v: k for k, v in piexif.ExifIFD.__dict__.items() if isinstance(v, int)},
            "GPS": {v: k for k, v in piexif.GPSIFD.__dict__.items() if isinstance(v, int)},
        }
        all_fields = {}
        for ifd_name, ifd_data in [("0th", ifd0), ("Exif", exif), ("GPS", gps)]:
            for tag, val in ifd_data.items():
                label = label_map[ifd_name].get(tag, str(tag))
                decoded = _decode_exif_value(val)
                if decoded not in (None, "", b""):
                    all_fields[label] = decoded

        return {
            "date": date_raw.decode() if date_raw else None,
            "camera": camera_raw.decode(errors="replace").strip("\x00") if camera_raw else None,
            "iso": exif.get(piexif.ExifIFD.ISOSpeedRatings),
            "aperture": aperture_raw[0] / aperture_raw[1] if aperture_raw else None,
            "speed": f"{speed_raw[0]}/{speed_raw[1]}s" if speed_raw else None,
            "all_fields": all_fields,
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


OLLAMA_REMOTE = os.getenv("OLLAMA_HOST", "http://192.168.50.113:11434")
PROMPT_TEXT_PATH = Path("prompts/photo_memory.txt")

# Cloud models served by the homelab Ollama (same /api/generate API as local
# models). The "three fake memories" use three distinct cloud models.
VISION_MODEL = "qwen3-vl:235b-cloud"       # photo description + one memory
MEMORY_VISION_MODEL = "gemma4:31b-cloud"   # one memory (vision)
MEMORY_TEXT_MODEL = "kimi-k2.6:cloud"      # one memory (text, from the description)


def call_ollama_prompt(model: str, prompt_text: str, image_path: Optional[str] = None, think: bool = True) -> str:
    payload: dict = {"model": model, "prompt": prompt_text, "stream": False}
    if image_path:
        with open(image_path, "rb") as f:
            payload["images"] = [base64.b64encode(f.read()).decode()]
    if not think:
        payload["think"] = False
    resp = requests.post(f"{OLLAMA_REMOTE}/api/generate", json=payload)
    if not resp.ok:
        raise RuntimeError(f"Ollama {model} error {resp.status_code}: {resp.text}")
    return resp.json()["response"]


def write_article(photo_path: Path, web_path: Path, description: str,
                  mem_qwen: str, mem_gemma: str, mem_kimi: str, exif: dict) -> None:
    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
    slug = photo_path.stem
    date_str = exif.get("date") or ""
    try:
        dt = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
        date_fmt = dt.strftime("%Y-%m-%d")
    except ValueError:
        date_fmt = datetime.fromtimestamp(photo_path.stat().st_mtime).strftime("%Y-%m-%d")

    meta_lines = [
        f"- **{k}:** {v}"
        for k, v in exif.get("all_fields", {}).items()
    ]

    meta_block = ("\n".join(meta_lines) + "\n\n") if meta_lines else ""
    disclaimer = (
        "_Lo siguiente es una memoria falsa generada por tres modelos de lenguaje (qwen3-vl, gemma4:31b y kimi-k2.6) "
        "a partir de la imagen, usando [este prompt](https://github.com/psyrax/oglabs_2026/blob/master/prompts/photo_memory.txt). "
        "Ninguno de los recuerdos ocurrió._"
    )
    content = (
        f"Title: {slug}\n"
        f"Date: {date_fmt}\n"
        f"Category: photos\n"
        f"Slug: {slug}\n"
        f"Photo: photos/images/{web_path.name}\n\n"
        f"{description}\n\n"
        f"{meta_block}"
        f"{disclaimer}\n\n"
        f"*qwen3-vl:235b*\n\n{mem_qwen}\n\n"
        f"*gemma4:31b*\n\n{mem_gemma}\n\n"
        f"*kimi-k2.6*\n\n{mem_kimi}\n"
    )
    (ARTICLES_DIR / f"{slug}.md").write_text(content)


def process_photo(path: Path) -> None:
    print(f"  Processing {path.name}...")
    exif = extract_exif(path)
    web_path = WEB_DIR / f"{path.stem}.jpg"
    optimize_photo(path, web_path)
    prompt_text = PROMPT_TEXT_PATH.read_text()

    print(f"    Describing with {VISION_MODEL} (Ollama)...")
    description = call_ollama_prompt(VISION_MODEL, DESCRIPTION_PROMPT, str(web_path), think=False)
    print(f"    Memory via {VISION_MODEL} (Ollama)...")
    mem_qwen = call_ollama_prompt(VISION_MODEL, prompt_text, str(web_path), think=False)
    print(f"    Memory via {MEMORY_VISION_MODEL} (Ollama)...")
    mem_gemma = call_ollama_prompt(MEMORY_VISION_MODEL, prompt_text, str(web_path), think=False)
    print(f"    Memory via {MEMORY_TEXT_MODEL} (Ollama)...")
    kimi_prompt = f"Descripción de la imagen:\n{description}\n\n---\n\n{prompt_text}"
    mem_kimi = call_ollama_prompt(MEMORY_TEXT_MODEL, kimi_prompt, image_path=None, think=False)

    write_article(path, web_path, description, mem_qwen, mem_gemma, mem_kimi, exif)
    print(f"  → content/photos/{path.stem}.md")


def main() -> None:
    parser = argparse.ArgumentParser(description="Process new photos for oglabs")
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
        process_photo(photo)
        manifest.add(photo.name)

    save_manifest(manifest)
    print(f"\nDone. Processed {len(photos)} photo(s).")


if __name__ == "__main__":
    main()
