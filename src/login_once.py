import argparse
import base64
import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright


TARGET_URL = "https://nurture.diveanalytics.com/announcements"
DEFAULT_REPO = "horse-3903/nurture-newsfeed"
DEFAULT_SECRET_NAME = "AUTH_JSON"


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="One-time manual login helper to persist Playwright auth state."
    )
    parser.add_argument(
        "--url",
        default=TARGET_URL,
        help="Protected URL to open after login (default: announcements page).",
    )
    parser.add_argument(
        "--output",
        default="auth.json",
        help="Path to write Playwright storage state (default: auth.json).",
    )
    parser.add_argument(
        "--base64-output",
        default="auth_json_base64.txt",
        help="Path to write base64-encoded auth state (default: auth_json_base64.txt).",
    )
    parser.add_argument(
        "--browser",
        choices=["opera", "chrome", "chromium"],
        default="opera",
        help="Browser engine for manual login (default: opera, using the installed Opera GX).",
    )
    parser.add_argument(
        "--opera-path",
        default="",
        help="Path to opera.exe, if Opera GX isn't found automatically.",
    )
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=120000,
        help="Initial page navigation timeout in milliseconds (default: 120000).",
    )
    parser.add_argument(
        "--login-timeout-ms",
        type=int,
        default=300000,
        help="How long to auto-wait for login completion before giving up (default: 300000 = 5 min).",
    )
    parser.add_argument(
        "--cdp-url",
        default="",
        help=(
            "Attach to an already-running Chrome via DevTools Protocol "
            "(example: http://127.0.0.1:9222). Recommended for Google 2FA accounts."
        ),
    )
    parser.add_argument(
        "--repo",
        default=DEFAULT_REPO,
        help=f"GitHub repo to push the AUTH_JSON secret to (default: {DEFAULT_REPO}).",
    )
    parser.add_argument(
        "--secret-name",
        default=DEFAULT_SECRET_NAME,
        help=f"Name of the GitHub Actions secret to set (default: {DEFAULT_SECRET_NAME}).",
    )
    parser.add_argument(
        "--skip-secret-push",
        action="store_true",
        help="Skip pushing the base64 auth state to the GitHub secret via `gh secret set`.",
    )
    return parser.parse_args()


def find_opera_executable(explicit_path: str = "") -> str:
    if explicit_path:
        return explicit_path

    which_path = shutil.which("opera")
    if which_path:
        return which_path

    candidates = [
        Path(os.path.expandvars(r"%LOCALAPPDATA%\Programs\Opera GX\opera.exe")),
        Path(os.path.expandvars(r"%PROGRAMFILES%\Opera GX\opera.exe")),
        Path(os.path.expandvars(r"%PROGRAMFILES(X86)%\Opera GX\opera.exe")),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return ""


def target_path_segment(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    return path.rsplit("/", 1)[-1] if path else ""


def has_reached_target(current_url: str, target_url: str) -> bool:
    target = urlparse(target_url)
    current = urlparse(current_url)
    if current.netloc != target.netloc:
        return False
    segment = target_path_segment(target_url)
    if not segment:
        return True
    return segment in current.path.strip("/").split("/")


def wait_for_login(page, target_url: str, timeout_ms: int, poll_ms: int = 3000) -> bool:
    logging.info(
        "Waiting to reach %s (checking every %.0fs, up to %.0fs)...",
        target_url,
        poll_ms / 1000,
        timeout_ms / 1000,
    )
    context = page.context
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        page.bring_to_front()
        url = page.url
        matched = has_reached_target(url, target_url)
        logging.info("Watched page: %s (matched=%s)", url, matched)
        other_pages = [p for p in context.pages if p is not page]
        if other_pages:
            logging.info(
                "Other open tabs: %s", [p.url for p in other_pages]
            )
        if matched:
            logging.info("Reached target page: %s", url)
            return True
        for other in other_pages:
            if has_reached_target(other.url, target_url):
                logging.info("Target reached in a different tab: %s", other.url)
                return True
        time.sleep(poll_ms / 1000)
    logging.warning("Timed out waiting to reach %s.", target_url)
    return False


def write_base64_auth_file(auth_path: Path, base64_output_path: Path) -> None:
    encoded = base64.b64encode(auth_path.read_bytes()).decode("ascii")
    base64_output_path.write_text(encoded, encoding="ascii")


def push_secret(base64_output_path: Path, repo: str, secret_name: str) -> bool:
    logging.info("Pushing %s to GitHub secret %s on %s", base64_output_path, secret_name, repo)
    try:
        subprocess.run(
            ["gh", "secret", "set", secret_name, "--repo", repo],
            stdin=base64_output_path.open("rb"),
            check=True,
        )
    except FileNotFoundError:
        logging.error("`gh` CLI not found. Install it or run with --skip-secret-push.")
        return False
    except subprocess.CalledProcessError as exc:
        logging.error("`gh secret set` failed (%s). Run `gh auth login` and retry.", exc)
        return False
    logging.info("Secret %s updated on %s.", secret_name, repo)
    return True


def try_attach_via_cdp(cdp_url: str, target_url: str, output_path: Path, login_timeout_ms: int) -> int:
    logging.info("Attaching to existing Chrome via CDP: %s", cdp_url)
    logging.info("Make sure Chrome was started with remote debugging enabled.")
    logging.info("If not logged in yet, complete Google login + 2FA in that Chrome window first.")

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(cdp_url)
        if not browser.contexts:
            raise RuntimeError("No browser contexts found after CDP attach.")
        context = browser.contexts[0]

        page = context.new_page()
        try:
            page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
        except PlaywrightError:
            logging.info(
                "Initial navigation via Playwright failed; you can still navigate manually in Chrome."
            )

        if not wait_for_login(page, target_url, login_timeout_ms):
            logging.warning("Saving state anyway, but it may be invalid.")

        context.storage_state(path=str(output_path))
        browser.close()
    return 0


def main() -> int:
    configure_logging()
    args = parse_args()
    output_path = Path(args.output)
    base64_output_path = Path(args.base64_output)

    if args.cdp_url:
        try:
            rc = try_attach_via_cdp(args.cdp_url, args.url, output_path, args.login_timeout_ms)
            write_base64_auth_file(output_path, base64_output_path)
        except PlaywrightError as exc:
            logging.error("Playwright CDP attach failed: %s", exc)
            return 1
        except (RuntimeError, KeyboardInterrupt) as exc:
            logging.error("%s", exc)
            return 1
        logging.info("Saved Playwright storage state to %s", output_path)
        logging.info("Saved base64-encoded auth state to %s", base64_output_path)
        logging.info("Do not commit these files.")
        if not args.skip_secret_push:
            if not push_secret(base64_output_path, args.repo, args.secret_name):
                return 1
        return rc

    logging.info("Launching browser for manual login: %s", args.url)
    logging.info("Preferred browser: %s", args.browser)
    logging.info("Complete Google OAuth in the opened browser window.")

    try:
        with sync_playwright() as p:
            try:
                if args.browser == "opera":
                    opera_path = find_opera_executable(args.opera_path)
                    if not opera_path:
                        raise PlaywrightError(
                            "Opera GX not found. Pass --opera-path to point at opera.exe."
                        )
                    browser = p.chromium.launch(headless=False, executable_path=opera_path)
                elif args.browser == "chrome":
                    browser = p.chromium.launch(headless=False, channel="chrome")
                else:
                    browser = p.chromium.launch(headless=False)
            except PlaywrightError as exc:
                if args.browser in ("opera", "chrome"):
                    logging.warning(
                        "Failed to launch %s (%s). Falling back to Playwright Chromium.",
                        args.browser,
                        exc,
                    )
                    browser = p.chromium.launch(headless=False)
                else:
                    raise
            context = browser.new_context()
            page = context.new_page()
            page.goto(args.url, wait_until="domcontentloaded", timeout=args.timeout_ms)

            if not wait_for_login(page, args.url, args.login_timeout_ms):
                logging.warning("Saving state anyway, but it may be invalid.")

            context.storage_state(path=str(output_path))
            browser.close()
    except PlaywrightError as exc:
        logging.error("Playwright failed during manual login: %s", exc)
        return 1
    except KeyboardInterrupt:
        logging.error("Interrupted before saving auth state.")
        return 1

    write_base64_auth_file(output_path, base64_output_path)

    logging.info("Saved Playwright storage state to %s", output_path)
    logging.info("Saved base64-encoded auth state to %s", base64_output_path)
    logging.info("Do not commit these files.")
    if not args.skip_secret_push:
        if not push_secret(base64_output_path, args.repo, args.secret_name):
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
