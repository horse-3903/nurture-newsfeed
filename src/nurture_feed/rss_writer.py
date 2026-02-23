from datetime import datetime, timezone
from email.utils import format_datetime

from feedgen.feed import FeedGenerator

from .config import FEED_FILE, MAX_FEED_ITEMS, TARGET_URL
from .logging_utils import logger
from .models import Announcement
from .utils import to_rfc2822


def generate_rss_feed(items: list[Announcement]) -> None:
    fg = FeedGenerator()
    fg.title("Nurture Announcements")
    fg.link(href=TARGET_URL, rel="alternate")
    fg.description("Announcements feed generated from nurture.diveanalytics.com")
    fg.language("en")
    fg.lastBuildDate(format_datetime(datetime.now(timezone.utc)))

    for item in items[:MAX_FEED_ITEMS]:
        fe = fg.add_entry(order="append")
        fe.guid(item.id, permalink=False)
        fe.title(item.title)
        fe.link(href=item.link, rel="alternate")
        if item.author:
            fe.author({"name": item.author})
        if item.description:
            fe.description(item.description)
        pub_date = to_rfc2822(item.pub_date)
        if pub_date:
            fe.pubDate(pub_date)

    FEED_FILE.write_bytes(fg.rss_str(pretty=True))
    logger.info(
        "RSS feed written",
        extra={"event": "feed_written", "count": min(len(items), MAX_FEED_ITEMS), "path": str(FEED_FILE)},
    )
