import hashlib
import re
from pathlib import Path
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

try:
    import dateparser
except ImportError:  # pragma: no cover - fallback path when dependency not installed yet
    dateparser = None

from .config import RECIPIENTS_FILE, SITE_TIMEZONE
from .models import Announcement


def normalize_whitespace(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split())
    return normalized or None


def make_id(title: str, link: str) -> str:
    return hashlib.sha256(f"{title}|{link}".encode("utf-8")).hexdigest()


_RELATIVE_TIME_RE = re.compile(
    r"^(?P<count>\d+|a|an)\s+(?P<unit>minute|hour|day|week|month|year)s?\s+ago$",
    re.IGNORECASE,
)


def estimate_pub_datetime(raw_date: str | None, *, now: datetime | None = None) -> str | None:
    if not raw_date:
        return None

    text = normalize_whitespace(raw_date)
    if not text:
        return None

    if now is None:
        now = datetime.now(SITE_TIMEZONE)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=SITE_TIMEZONE)

    lowered = text.lower()
    if lowered in {"just now", "moments ago"}:
        return now.isoformat()
    if lowered == "yesterday":
        return (now - timedelta(days=1)).isoformat()
    if lowered == "today":
        return now.isoformat()

    # Try to preserve already-parseable absolute/ISO strings.
    candidates = [text]
    if text.endswith("Z"):
        candidates.append(text.replace("Z", "+00:00"))
    for value in candidates:
        try:
            dt = datetime.fromisoformat(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=SITE_TIMEZONE)
            return dt.isoformat()
        except ValueError:
            continue

    # Prefer a library parser for broader relative-date handling.
    if dateparser is not None:
        try:
            parsed = dateparser.parse(
                text,
                settings={
                    "RELATIVE_BASE": now,
                    "RETURN_AS_TIMEZONE_AWARE": True,
                    "TIMEZONE": "Asia/Singapore",
                    "TO_TIMEZONE": "Asia/Singapore",
                },
            )
            if parsed is not None:
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=SITE_TIMEZONE)
                return parsed.isoformat()
        except Exception:
            # Fall back to the limited parser below.
            pass

    match = _RELATIVE_TIME_RE.match(lowered)
    if not match:
        return text

    count_raw = match.group("count")
    count = 1 if count_raw in {"a", "an"} else int(count_raw)
    unit = match.group("unit")

    # month/year are estimated using fixed day counts.
    if unit == "minute":
        delta = timedelta(minutes=count)
    elif unit == "hour":
        delta = timedelta(hours=count)
    elif unit == "day":
        delta = timedelta(days=count)
    elif unit == "week":
        delta = timedelta(weeks=count)
    elif unit == "month":
        delta = timedelta(days=30 * count)
    else:  # year
        delta = timedelta(days=365 * count)

    estimated = now - delta
    return estimated.isoformat()


def to_rfc2822(raw_date: str | None) -> str | None:
    if not raw_date:
        return None

    candidates = [raw_date]
    if raw_date.endswith("Z"):
        candidates.append(raw_date.replace("Z", "+00:00"))

    for value in candidates:
        try:
            dt = datetime.fromisoformat(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return format_datetime(dt)
        except ValueError:
            continue
    return raw_date


def parse_recipients(value: str | None) -> list[str]:
    if not value:
        return []

    parts = re.split(r"[\n,;]+", value)
    recipients: list[str] = []
    seen: set[str] = set()
    for part in parts:
        email = part.strip()
        if not email or email.startswith("#"):
            continue
        normalized = email.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        recipients.append(email)
    return recipients


def load_recipients(env_value: str | None, *, file_path: str | Path | None = None) -> list[str]:
    recipients = parse_recipients(env_value)
    if recipients:
        return recipients

    path = Path(file_path) if file_path else RECIPIENTS_FILE
    candidate_paths = [path]
    if not path.is_absolute():
        candidate_paths.append(Path(__file__).resolve().parents[2] / path)

    text: str | None = None
    for candidate in candidate_paths:
        try:
            text = candidate.read_text(encoding="utf-8")
            break
        except FileNotFoundError:
            continue
        except OSError:
            continue

    if text is None:
        return []

    return parse_recipients(text)


def sort_announcements_for_feed(items: list[Announcement]) -> list[Announcement]:
    dated: list[tuple[datetime, int, Announcement]] = []
    undated: list[Announcement] = []

    for index, item in enumerate(items):
        if not item.pub_date:
            undated.append(item)
            continue

        parsed: datetime | None = None
        candidates = [item.pub_date]
        if item.pub_date.endswith("Z"):
            candidates.append(item.pub_date.replace("Z", "+00:00"))

        for value in candidates:
            try:
                parsed = datetime.fromisoformat(value)
                break
            except ValueError:
                continue

        if parsed is None:
            undated.append(item)
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        dated.append((parsed, index, item))

    dated.sort(key=lambda row: (row[0], -row[1]), reverse=True)
    return [row[2] for row in dated] + undated
