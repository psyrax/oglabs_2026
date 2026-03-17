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
