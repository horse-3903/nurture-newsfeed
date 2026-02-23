import argparse
import logging
import sys
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright


TARGET_URL = "https://nurture.diveanalytics.com/announcements"


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
        "--browser",
        choices=["chrome", "chromium"],
        default="chrome",
        help="Browser engine for manual login (default: chrome for better Google OAuth compatibility).",
    )
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=120000,
        help="Initial page navigation timeout in milliseconds (default: 120000).",
    )
    parser.add_argument(
        "--cdp-url",
        default="",
        help=(
            "Attach to an already-running Chrome via DevTools Protocol "
            "(example: http://127.0.0.1:9222). Recommended for Google 2FA accounts."
        ),
    )
    return parser.parse_args()


def try_attach_via_cdp(cdp_url: str, target_url: str, output_path: Path) -> int:
    logging.info("Attaching to existing Chrome via CDP: %s", cdp_url)
    logging.info("Make sure Chrome was started with remote debugging enabled.")
    logging.info("If not logged in yet, complete Google login + 2FA in that Chrome window first.")
    logging.info("Press Enter here after you can view the announcements page in Chrome.")

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

        input()

        current_url = page.url
        if "accounts.google.com" in current_url or "login" in current_url.lower():
            logging.warning(
                "Current page still looks like a login page (%s). Saving state anyway, but it may be invalid.",
                current_url,
            )

        context.storage_state(path=str(output_path))
        browser.close()
    return 0


def main() -> int:
    configure_logging()
    args = parse_args()
    output_path = Path(args.output)

    if args.cdp_url:
        try:
            rc = try_attach_via_cdp(args.cdp_url, args.url, output_path)
        except PlaywrightError as exc:
            logging.error("Playwright CDP attach failed: %s", exc)
            return 1
        except (RuntimeError, KeyboardInterrupt) as exc:
            logging.error("%s", exc)
            return 1
        logging.info("Saved Playwright storage state to %s", output_path)
        logging.info("Do not commit this file. Base64 encode it and store as GitHub secret AUTH_JSON.")
        return rc

    logging.info("Launching browser for manual login: %s", args.url)
    logging.info("Preferred browser: %s", args.browser)
    logging.info("Complete Google OAuth in the opened browser window.")
    logging.info("Press Enter in this terminal only after you can view the announcements page.")

    try:
        with sync_playwright() as p:
            try:
                if args.browser == "chrome":
                    browser = p.chromium.launch(headless=False, channel="chrome")
                else:
                    browser = p.chromium.launch(headless=False)
            except PlaywrightError as exc:
                if args.browser == "chrome":
                    logging.warning(
                        "Failed to launch installed Chrome (%s). Falling back to Playwright Chromium.",
                        exc,
                    )
                    browser = p.chromium.launch(headless=False)
                else:
                    raise
            context = browser.new_context()
            page = context.new_page()
            page.goto(args.url, wait_until="domcontentloaded", timeout=args.timeout_ms)

            input()

            current_url = page.url
            if "accounts.google.com" in current_url or "login" in current_url.lower():
                logging.warning(
                    "Current page still looks like a login page (%s). Saving state anyway, but it may be invalid.",
                    current_url,
                )

            context.storage_state(path=str(output_path))
            browser.close()
    except PlaywrightError as exc:
        logging.error("Playwright failed during manual login: %s", exc)
        return 1
    except KeyboardInterrupt:
        logging.error("Interrupted before saving auth state.")
        return 1

    logging.info("Saved Playwright storage state to %s", output_path)
    logging.info("Do not commit this file. Base64 encode it and store as GitHub secret AUTH_JSON.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
