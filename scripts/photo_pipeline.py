import argparse
import base64
import json
import os
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


OLLAMA_REMOTE = "http://192.168.50.113:11434"
PROMPT_TEXT_PATH = Path("prompts/photo_memory.txt")


def call_stored_prompt(prompt_id: str, image_path: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    with open(image_path, "rb") as f:
        img_data = base64.b64encode(f.read()).decode()
    response = client.responses.create(
        prompt={"id": prompt_id},
        input=[{
            "role": "user",
            "content": [{"type": "input_image", "image_url": f"data:image/jpeg;base64,{img_data}"}],
        }],
    )
    return response.output_text


def call_ollama_prompt(model: str, prompt_text: str, image_path: str, think: bool = True) -> str:
    with open(image_path, "rb") as f:
        img_data = base64.b64encode(f.read()).decode()
    payload: dict = {"model": model, "prompt": prompt_text, "images": [img_data], "stream": False}
    if not think:
        payload["think"] = False
    resp = requests.post(f"{OLLAMA_REMOTE}/api/generate", json=payload)
    resp.raise_for_status()
    return resp.json()["response"]


def write_article(photo_path: Path, web_path: Path, description: str, extra: str,
                  gemma: str, lfm: str, exif: dict) -> None:
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

    meta_block = ("\n".join(meta_lines) + "\n\n") if meta_lines else ""
    disclaimer = "_Lo siguiente es una memoria falsa creada por un LLM a partir de la imagen._"
    content = (
        f"Title: {slug}\n"
        f"Date: {date_fmt}\n"
        f"Category: photos\n"
        f"Slug: {slug}\n"
        f"Photo: photos/images/{web_path.name}\n\n"
        f"{description}\n\n"
        f"{meta_block}"
        f"{disclaimer}\n\n"
        f"*gpt-4o*\n\n{extra}\n\n"
        f"*gemma3:4b*\n\n{gemma}\n\n"
        f"*lfm2.5-thinking*\n\n{lfm}\n"
    )
    (ARTICLES_DIR / f"{slug}.md").write_text(content)


STORED_PROMPT_ID = os.getenv("PROMPT_ID", "")


def process_photo(path: Path, llm_backend: Optional[str]) -> None:
    print(f"  Processing {path.name}...")
    exif = extract_exif(path)
    web_path = WEB_DIR / f"{path.stem}.jpg"
    optimize_photo(path, web_path)
    client = get_client(llm_backend)
    description = client.complete(DESCRIPTION_PROMPT, image_path=str(web_path))
    print(f"    Calling stored prompt (OpenAI)...")
    extra = call_stored_prompt(STORED_PROMPT_ID, str(web_path))
    prompt_text = PROMPT_TEXT_PATH.read_text()
    print(f"    Calling gemma3:4b (Ollama)...")
    gemma = call_ollama_prompt("gemma3:4b", prompt_text, str(web_path))
    print(f"    Calling lfm2.5-thinking:latest (Ollama)...")
    lfm = call_ollama_prompt("lfm2.5-thinking:latest", prompt_text, str(web_path), think=False)
    write_article(path, web_path, description, extra, gemma, lfm, exif)
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
