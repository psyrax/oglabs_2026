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
