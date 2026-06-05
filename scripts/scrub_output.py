"""Redact sensitive strings from the built site before uploading to S3.

Runs over output/ (the Pelican build) and replaces sensitive matches with
descriptive placeholders, in place. output/ is a disposable build dir, so the
source content under content/ is never touched.

Toggle categories below. The site is public, so this is a safety net against
accidentally publishing secrets — not a substitute for not committing them.
"""
import argparse
import re
from pathlib import Path

# --- category toggles (flip to enable) ---
SCRUB_SECRETS = True           # .env values + known key/token formats
SCRUB_ENV_ASSIGNMENTS = True   # NAME=value where NAME looks like a credential
SCRUB_IPS_AND_PATHS = False    # private IPs and local paths (off: blog uses them on purpose)
SCRUB_EMAILS = False           # email addresses (off: legitimate mentions)

OUTPUT_DIR = Path("output")
TEXT_SUFFIXES = {".html", ".htm", ".xml", ".txt"}

# Env var names containing any of these are treated as secrets.
SECRET_NAME_HINTS = ("KEY", "SECRET", "TOKEN", "PASSWORD", "PASSWD")
SECRET_NAME_EXTRA = {"PROMPT_ID"}

# (compiled regex, placeholder) for known high-confidence credential formats.
SECRET_PATTERNS = [
    (re.compile(r"AKIA[0-9A-Z]{16}"), "[REDACTED:AWS_KEY]"),
    (re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}"), "[REDACTED:API_KEY]"),
    (re.compile(r"pmpt_[A-Za-z0-9]{8,}"), "[REDACTED:PROMPT_ID]"),
    (re.compile(r"ghp_[A-Za-z0-9]{20,}"), "[REDACTED:TOKEN]"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{20,}"), "[REDACTED:TOKEN]"),
    (re.compile(r"xox[baprs]-[A-Za-z0-9-]{8,}"), "[REDACTED:TOKEN]"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL),
     "[REDACTED:PRIVATE_KEY]"),
]

# NAME=value where NAME is an all-caps credential-looking identifier.
ENV_ASSIGN_RE = re.compile(
    r"\b([A-Z][A-Z0-9_]*(?:KEY|SECRET|TOKEN|PASSWORD|PASSWD))\s*=\s*['\"]?[^\s'\"<>]+"
)

PRIVATE_IP_RE = re.compile(
    r"\b(?:192\.168\.\d{1,3}\.\d{1,3}"
    r"|10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b"
)
PATH_RE = re.compile(r"(?:/mnt/user|/home/|/Users/|/root)[^\s'\"<>]*")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def load_env_secrets(env_path: Path) -> list:
    """Return the values of credential-looking vars from a .env file."""
    secrets = []
    if not env_path.exists():
        return secrets
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name, value = name.strip(), value.strip().strip("'\"")
        if len(value) < 8:
            continue
        is_secret = name in SECRET_NAME_EXTRA or any(h in name for h in SECRET_NAME_HINTS)
        if is_secret:
            secrets.append(value)
    return secrets


def scrub_text(text: str, secrets: list = None, *, secrets_on: bool = None,
               env_on: bool = None, ip_path_on: bool = None, email_on: bool = None) -> tuple:
    """Return (scrubbed_text, findings). findings is a list of category labels.

    Category flags default to the module toggles; pass them to override.
    """
    secrets_on = SCRUB_SECRETS if secrets_on is None else secrets_on
    env_on = SCRUB_ENV_ASSIGNMENTS if env_on is None else env_on
    ip_path_on = SCRUB_IPS_AND_PATHS if ip_path_on is None else ip_path_on
    email_on = SCRUB_EMAILS if email_on is None else email_on
    findings = []

    def sub(pattern, repl, label, s):
        new, n = pattern.subn(repl, s)
        if n:
            findings.extend([label] * n)
        return new

    if secrets_on:
        for value in sorted(secrets or [], key=len, reverse=True):
            if value and value in text:
                findings.extend(["env-secret"] * text.count(value))
                text = text.replace(value, "[REDACTED:SECRET]")
        for pattern, placeholder in SECRET_PATTERNS:
            text = sub(pattern, placeholder, "secret-format", text)
    if env_on:
        text = sub(ENV_ASSIGN_RE, lambda m: m.group(1) + "=[REDACTED]", "env-assignment", text)
    if ip_path_on:
        text = sub(PRIVATE_IP_RE, "[IP omitida]", "private-ip", text)
        text = sub(PATH_RE, "[ruta omitida]", "local-path", text)
    if email_on:
        text = sub(EMAIL_RE, "[email omitido]", "email", text)

    return text, findings


def scrub_dir(out_dir: Path, secrets: list = None) -> dict:
    """Scrub all text files under out_dir in place. Returns {relpath: findings}."""
    report = {}
    for path in sorted(out_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        original = path.read_text(encoding="utf-8", errors="ignore")
        scrubbed, findings = scrub_text(original, secrets)
        if findings:
            path.write_text(scrubbed, encoding="utf-8")
            report[str(path.relative_to(out_dir))] = findings
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Redact secrets from output/ before deploy")
    parser.add_argument("--dir", default=str(OUTPUT_DIR), help="Build output directory")
    parser.add_argument("--env", default=".env", help="Path to .env for secret values")
    args = parser.parse_args()

    secrets = load_env_secrets(Path(args.env))
    report = scrub_dir(Path(args.dir), secrets)

    if not report:
        print("Scrub: no sensitive strings found in output/.")
        return

    total = sum(len(v) for v in report.values())
    print(f"Scrub: redacted {total} match(es) across {len(report)} file(s):")
    for rel, findings in sorted(report.items()):
        counts = {}
        for f in findings:
            counts[f] = counts.get(f, 0) + 1
        summary = ", ".join(f"{k}:{v}" for k, v in sorted(counts.items()))
        print(f"  {rel}  ({summary})")


if __name__ == "__main__":
    main()
