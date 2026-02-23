from .config import DETAIL_ENRICH_LIMIT
from .emailer import send_email_notification
from .logging_utils import configure_logging, logger
from .rss_writer import generate_rss_feed
from .scraper import enrich_announcements_with_detail_pages, scrape_announcements_with_retry
from .storage import detect_new_items, load_cache, save_cache
from .utils import sort_announcements_for_feed


def run_pipeline(*, enable_email: bool = True) -> int:
    configure_logging()

    try:
        current_items = scrape_announcements_with_retry()
    except PermissionError as exc:
        logger.error(str(exc), extra={"event": "session_expired"})
        return 2
    except Exception:
        logger.error("Failed to scrape announcements", extra={"event": "scrape_fatal"}, exc_info=True)
        return 1

    if not current_items:
        logger.warning("No announcements found; writing empty feed and cache", extra={"event": "no_items"})

    ordered_items = sort_announcements_for_feed(current_items)
    cached_items = load_cache()
    new_items = detect_new_items(ordered_items, cached_items)

    if new_items:
        try:
            enrich_announcements_with_detail_pages(new_items, limit=DETAIL_ENRICH_LIMIT)
        except PermissionError as exc:
            logger.error(str(exc), extra={"event": "session_expired"})
            return 2
        ordered_items = sort_announcements_for_feed(ordered_items)
        new_items = detect_new_items(ordered_items, cached_items)

    logger.info("Change detection complete", extra={"event": "diff_complete", "count": len(new_items)})
    generate_rss_feed(ordered_items)
    save_cache(ordered_items)
    if enable_email:
        send_email_notification(new_items)
    else:
        logger.info("Email sending disabled for this run", extra={"event": "email_disabled"})
    return 0


def main() -> int:
    return run_pipeline(enable_email=True)
