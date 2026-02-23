import argparse
import json
import sys
from dataclasses import asdict

from nurture_feed.logging_utils import configure_logging
from nurture_feed.scraper import enrich_announcements_with_detail_pages, scrape_announcements_with_retry


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Locally test announcement extraction and print JSON.")
    parser.add_argument("--limit", type=int, default=5, help="How many extracted items to print (default: 5)")
    parser.add_argument(
        "--enrich-details",
        action="store_true",
        help="Open announcement detail pages for the printed items to extract full content.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable structured scraper logs while testing extraction.",
    )
    parser.add_argument(
        "--headed-debug",
        action="store_true",
        help="Run Playwright headed so you can watch the announcements page load.",
    )
    parser.add_argument(
        "--slow-mo-ms",
        type=int,
        default=0,
        help="Slow down Playwright actions in milliseconds (useful with --headed-debug).",
    )
    parser.add_argument(
        "--debug-hold-seconds",
        type=int,
        default=10,
        help="When using --headed-debug, keep the list page open this many seconds before extraction.",
    )
    parser.add_argument(
        "--detail-concurrency",
        type=int,
        default=0,
        help="Max concurrent tabs for detail-page enrichment (0 = use config default).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.verbose or args.headed_debug:
        configure_logging()
    items = scrape_announcements_with_retry(
        headless=not args.headed_debug,
        slow_mo_ms=max(args.slow_mo_ms, 0),
        debug_hold_seconds=max(args.debug_hold_seconds, 0) if args.headed_debug else 0,
    )
    items = items[: max(args.limit, 0)]
    if args.enrich_details and items:
        enrich_kwargs = {
            "headless": not args.headed_debug,
            "slow_mo_ms": max(args.slow_mo_ms, 0),
        }
        if args.detail_concurrency > 0:
            enrich_kwargs["concurrency"] = args.detail_concurrency
        enrich_announcements_with_detail_pages(
            items,
            limit=len(items),
            **enrich_kwargs,
        )
    print(json.dumps([asdict(item) for item in items], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
