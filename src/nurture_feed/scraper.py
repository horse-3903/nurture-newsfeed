import asyncio
import time
from urllib.parse import urlparse

from playwright.async_api import Error as AsyncPlaywrightError
from playwright.async_api import TimeoutError as AsyncPlaywrightTimeoutError
from playwright.async_api import async_playwright
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from .config import (
    AUTH_FILE,
    DETAIL_ENRICH_CONCURRENCY,
    DETAIL_ENRICH_LIMIT,
    SCRAPE_RETRIES,
    SCRAPE_RETRY_DELAY_SECONDS,
    TARGET_URL,
)
from .extractors import extract_announcements_from_html, extract_detail_fields_from_html
from .logging_utils import logger
from .models import Announcement


def looks_like_login_or_expired(url: str) -> bool:
    lowered = url.lower()
    host = urlparse(url).netloc.lower()
    return (
        "accounts.google.com" in host
        or "/login" in lowered
        or "signin" in lowered
        or "oauth" in lowered
    )


def scrape_announcements_once(
    *,
    headless: bool = True,
    slow_mo_ms: int = 0,
    debug_hold_seconds: int = 0,
) -> list[Announcement]:
    if not AUTH_FILE.exists():
        raise FileNotFoundError(
            f"Missing {AUTH_FILE}. Restore it from the AUTH_JSON GitHub secret before running."
        )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, slow_mo=slow_mo_ms)
        context = browser.new_context(storage_state=str(AUTH_FILE))
        page = context.new_page()
        try:
            logger.info("Navigating to announcements page", extra={"event": "navigate", "url": TARGET_URL})
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_load_state("networkidle", timeout=60000)
        except PlaywrightTimeoutError:
            logger.warning(
                "Timed out waiting for network idle; continuing with current DOM",
                extra={"event": "network_timeout", "url": page.url},
            )
        except PlaywrightError as exc:
            raise RuntimeError(f"Playwright navigation failed: {exc}") from exc

        current_url = page.url
        if looks_like_login_or_expired(current_url):
            browser.close()
            raise PermissionError(
                f"Authenticated session appears expired; redirected to login page: {current_url}"
            )

        if not headless and debug_hold_seconds > 0:
            logger.info(
                "Headed debug hold before extraction",
                extra={"event": "debug_hold", "count": debug_hold_seconds, "url": current_url},
            )
            time.sleep(debug_hold_seconds)

        html = page.content()
        browser.close()

    announcements = extract_announcements_from_html(html, base_url=current_url)
    if not announcements:
        logger.warning(
            "No announcements were extracted. Selectors may need adjustment.",
            extra={"event": "empty_extract", "url": current_url},
        )
    logger.info(
        "Extracted announcements",
        extra={"event": "extract_complete", "count": len(announcements), "url": current_url},
    )
    return announcements


def scrape_announcements_with_retry(
    *,
    headless: bool = True,
    slow_mo_ms: int = 0,
    debug_hold_seconds: int = 0,
) -> list[Announcement]:
    last_error: Exception | None = None
    for attempt in range(1, SCRAPE_RETRIES + 1):
        try:
            logger.info("Scrape attempt started", extra={"event": "scrape_attempt", "attempt": attempt})
            return scrape_announcements_once(
                headless=headless,
                slow_mo_ms=slow_mo_ms,
                debug_hold_seconds=debug_hold_seconds,
            )
        except PermissionError:
            raise
        except (FileNotFoundError, RuntimeError, PlaywrightError) as exc:
            last_error = exc
            logger.warning(
                "Scrape attempt failed",
                extra={"event": "scrape_failed", "attempt": attempt},
                exc_info=True,
            )
            if attempt < SCRAPE_RETRIES:
                time.sleep(SCRAPE_RETRY_DELAY_SECONDS)
    assert last_error is not None
    raise RuntimeError(f"All scrape attempts failed: {last_error}") from last_error


def enrich_announcements_with_detail_pages(
    items: list[Announcement],
    limit: int = DETAIL_ENRICH_LIMIT,
    *,
    headless: bool = True,
    slow_mo_ms: int = 0,
    concurrency: int = DETAIL_ENRICH_CONCURRENCY,
) -> None:
    if not items:
        return
    to_enrich = items[: max(limit, 0)]
    if not to_enrich:
        return
    if not AUTH_FILE.exists():
        logger.warning(
            "Auth file missing; skipping detail enrichment",
            extra={"event": "detail_enrich_skipped", "path": str(AUTH_FILE)},
        )
        return

    logger.info(
        "Starting detail enrichment (concurrent tabs)",
        extra={"event": "detail_enrich_start", "count": len(to_enrich)},
    )
    try:
        asyncio.run(
            _enrich_announcements_with_detail_pages_async(
                to_enrich,
                headless=headless,
                slow_mo_ms=slow_mo_ms,
                concurrency=max(1, concurrency),
            )
        )
    except PermissionError:
        raise
    except Exception:
        logger.warning(
            "Detail enrichment failed; continuing with list-page data",
            extra={"event": "detail_enrich_failed"},
            exc_info=True,
        )
        return

    logger.info(
        "Detail enrichment completed",
        extra={"event": "detail_enrich_done", "count": len(to_enrich)},
    )


async def _enrich_announcements_with_detail_pages_async(
    items: list[Announcement],
    *,
    headless: bool,
    slow_mo_ms: int,
    concurrency: int,
) -> None:
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless, slow_mo=slow_mo_ms)
        context = await browser.new_context(storage_state=str(AUTH_FILE))

        async def enrich_one(index: int, item: Announcement) -> Exception | None:
            async with semaphore:
                page = await context.new_page()
                try:
                    logger.info(
                        "Opening announcement detail page",
                        extra={"event": "detail_open", "attempt": index, "url": item.link},
                    )
                    try:
                        await page.goto(item.link, wait_until="domcontentloaded", timeout=45000)
                        await page.wait_for_load_state("networkidle", timeout=30000)
                    except AsyncPlaywrightTimeoutError:
                        logger.warning(
                            "Detail page network idle timeout; parsing current DOM",
                            extra={"event": "detail_timeout", "url": page.url or item.link},
                        )
                    except AsyncPlaywrightError as exc:
                        logger.warning(
                            "Failed to load detail page",
                            extra={"event": "detail_failed", "url": item.link},
                            exc_info=True,
                        )
                        return exc

                    if looks_like_login_or_expired(page.url):
                        return PermissionError(
                            f"Authenticated session appears expired while opening detail page: {page.url}"
                        )

                    detail = extract_detail_fields_from_html(await page.content())
                    if detail.get("title"):
                        item.title = detail["title"] or item.title
                    if detail.get("author"):
                        item.author = detail["author"]
                    if detail.get("description"):
                        item.description = detail["description"]
                    if detail.get("pub_date_raw"):
                        item.pub_date_raw = detail["pub_date_raw"]
                    if detail.get("pub_date"):
                        item.pub_date = detail["pub_date"]
                    return None
                finally:
                    await page.close()

        results = await asyncio.gather(
            *(enrich_one(index, item) for index, item in enumerate(items, start=1)),
            return_exceptions=False,
        )

        await context.close()
        await browser.close()

    for result in results:
        if isinstance(result, PermissionError):
            raise result
