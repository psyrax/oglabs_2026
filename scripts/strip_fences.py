"""Remove ```markdown ... ``` wrappers that LLMs sometimes add to their output."""
import re
from pathlib import Path

CONTENT_DIR = Path("content")


def strip_fences(text: str) -> str:
    text = re.sub(r"```markdown\n([\s\S]*?)```", r"\1", text)
    text = re.sub(r"<think>[\s\S]*?</think>", "", text)
    return text


def main() -> None:
    changed = 0
    for f in CONTENT_DIR.rglob("*.md"):
        text = f.read_text()
        cleaned = strip_fences(text)
        if cleaned != text:
            f.write_text(cleaned)
            print(f"  Stripped fences: {f}")
            changed += 1
    if changed:
        print(f"Done. Cleaned {changed} file(s).")


if __name__ == "__main__":
    main()
