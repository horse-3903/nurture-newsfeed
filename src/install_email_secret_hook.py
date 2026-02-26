import argparse
from pathlib import Path


HOOK_FILE = Path(".git/hooks/post-commit")
START_MARKER = "# BEGIN nurture-newsfeed email secret sync"
END_MARKER = "# END nurture-newsfeed email secret sync"

HOOK_BLOCK = f"""{START_MARKER}
if command -v python >/dev/null 2>&1; then
  python src/sync_email_recipients_secret.py --skip-if-unchanged --quiet || true
elif command -v python3 >/dev/null 2>&1; then
  python3 src/sync_email_recipients_secret.py --skip-if-unchanged --quiet || true
fi
{END_MARKER}
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Install a local post-commit hook to sync EMAIL_RECIPIENTS secret.")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace the existing post-commit hook instead of appending a managed block.",
    )
    args = parser.parse_args()

    HOOK_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not HOOK_FILE.exists():
        content = "#!/bin/sh\nset -e\n\n" + HOOK_BLOCK
        HOOK_FILE.write_text(content, encoding="utf-8", newline="\n")
    else:
        existing = HOOK_FILE.read_text(encoding="utf-8")
        if START_MARKER in existing and END_MARKER in existing:
            print("Managed hook block already installed.")
            return 0
        if args.overwrite:
            content = "#!/bin/sh\nset -e\n\n" + HOOK_BLOCK
            HOOK_FILE.write_text(content, encoding="utf-8", newline="\n")
        else:
            newline = "" if existing.endswith("\n") else "\n"
            HOOK_FILE.write_text(existing + newline + HOOK_BLOCK, encoding="utf-8", newline="\n")

    try:
        HOOK_FILE.chmod(0o755)
    except OSError:
        pass

    print(f"Installed post-commit hook at {HOOK_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
