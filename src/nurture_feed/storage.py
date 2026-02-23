import json
from dataclasses import asdict
from datetime import datetime, timezone

from .config import CACHE_FILE, MAX_CACHE_ITEMS
from .logging_utils import logger
from .models import Announcement
from .utils import make_id, normalize_whitespace


def load_cache() -> list[Announcement]:
    if not CACHE_FILE.exists():
        logger.info(
            "Cache file missing; initializing empty cache",
            extra={"event": "cache_missing", "path": str(CACHE_FILE)},
        )
        return []

    try:
        raw = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.warning(
            "Cache file is invalid JSON; treating as empty cache",
            extra={"event": "cache_invalid", "path": str(CACHE_FILE)},
        )
        return []

    items = raw["items"] if isinstance(raw, dict) and isinstance(raw.get("items"), list) else raw if isinstance(raw, list) else []
    parsed: list[Announcement] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = normalize_whitespace(item.get("title"))
        link = normalize_whitespace(item.get("link"))
        ann_id = normalize_whitespace(item.get("id"))
        if not title or not link:
            continue
        parsed.append(
            Announcement(
                id=ann_id or make_id(title, link),
                title=title,
                link=link,
                source_id=normalize_whitespace(item.get("source_id") or item.get("sourceId")),
                author=normalize_whitespace(item.get("author")),
                description=normalize_whitespace(item.get("description")),
                pub_date_raw=normalize_whitespace(item.get("pub_date_raw") or item.get("pubDateRaw")),
                pub_date=normalize_whitespace(item.get("pub_date") or item.get("pubDate")),
            )
        )
    return parsed


def save_cache(items: list[Announcement]) -> None:
    payload = {
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        "items": [asdict(item) for item in items[:MAX_CACHE_ITEMS]],
    }
    CACHE_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(
        "Cache file updated",
        extra={"event": "cache_saved", "count": len(payload["items"]), "path": str(CACHE_FILE)},
    )


def detect_new_items(current: list[Announcement], cached: list[Announcement]) -> list[Announcement]:
    cached_ids = {item.id for item in cached}
    return [item for item in current if item.id not in cached_ids]
