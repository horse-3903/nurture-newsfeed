from datetime import timedelta, timezone
from pathlib import Path

TARGET_URL = "https://nurture.diveanalytics.com/announcements"

AUTH_FILE = Path("auth.json")
CACHE_FILE = Path("cache.json")
FEED_FILE = Path("feed.xml")
RECIPIENTS_FILE = Path("email_recipients.txt")

MAX_FEED_ITEMS = 50
MAX_CACHE_ITEMS = 500
SCRAPE_RETRIES = 3
SCRAPE_RETRY_DELAY_SECONDS = 5
DETAIL_ENRICH_LIMIT = 10
DETAIL_ENRICH_CONCURRENCY = 4

# Nurture is a Singapore-based site; use Singapore time for relative "x hours ago"
# estimation so generated pubDate values are consistent across runs/environments.
SITE_TIMEZONE = timezone(timedelta(hours=8))
