import argparse
import hashlib
import subprocess
import sys
from pathlib import Path


DEFAULT_RECIPIENTS_FILE = Path("email_recipients.txt")
DEFAULT_SECRET_NAME = "EMAIL_RECIPIENTS"
STATE_FILE = Path(".git") / ".email_recipients_secret_sync.sha256"


def parse_recipients_file(path: Path) -> list[str]:
    recipients: list[str] = []
    seen: set[str] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        normalized = line.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        recipients.append(line)
    return recipients


def content_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_last_synced_hash() -> str | None:
    try:
        return STATE_FILE.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def save_last_synced_hash(value: str) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(value + "\n", encoding="utf-8")


def run_gh_secret_set(secret_name: str, secret_value: str) -> None:
    try:
        subprocess.run(
            ["gh", "secret", "set", secret_name],
            input=secret_value,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        raise RuntimeError("GitHub CLI (`gh`) is not installed or not on PATH.")
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"`gh secret set` failed with exit code {exc.returncode}.") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync local email recipients file to a GitHub Actions secret.")
    parser.add_argument("--file", default=str(DEFAULT_RECIPIENTS_FILE), help="Path to local recipients file.")
    parser.add_argument("--secret", default=DEFAULT_SECRET_NAME, help="GitHub Actions secret name.")
    parser.add_argument(
        "--skip-if-unchanged",
        action="store_true",
        help="Skip syncing if the recipients content hash matches the last synced value.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Reduce non-error output (useful for git hooks).",
    )
    args = parser.parse_args()

    recipients_path = Path(args.file)
    if not recipients_path.exists():
        if not args.quiet:
            print(f"Recipients file not found: {recipients_path}. Skipping secret sync.")
        return 0

    try:
        recipients = parse_recipients_file(recipients_path)
    except OSError as exc:
        print(f"Failed to read recipients file: {exc}", file=sys.stderr)
        return 1

    if not recipients:
        if not args.quiet:
            print("Recipients file is empty after filtering comments/blank lines. Skipping secret sync.")
        return 0

    # Store multiline secret value so GitHub UI remains easy to edit later.
    secret_value = "\n".join(recipients) + "\n"
    current_hash = content_hash(secret_value)
    if args.skip_if_unchanged and load_last_synced_hash() == current_hash:
        if not args.quiet:
            print("Recipients secret already up to date. Skipping.")
        return 0

    try:
        run_gh_secret_set(args.secret, secret_value)
    except RuntimeError as exc:
        print(f"Email recipients secret sync skipped: {exc}", file=sys.stderr)
        return 1

    save_last_synced_hash(current_hash)
    if not args.quiet:
        print(f"Synced {len(recipients)} recipient(s) to GitHub secret `{args.secret}`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
