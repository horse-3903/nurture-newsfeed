import sys
from datetime import datetime, timezone

from nurture_feed.emailer import send_email_notification
from nurture_feed.logging_utils import configure_logging, logger
from nurture_feed.models import Announcement


def main() -> int:
    configure_logging()

    now = datetime.now(timezone.utc).isoformat()
    sample_items = [
        Announcement(
            id="test-email-1",
            title="Test Email: Nurture Feed Notifications Are Working",
            link="https://nurture.diveanalytics.com/announcements",
            author="GitHub Actions Test",
            description=(
                "This is a test notification sent by the GitHub Actions test-email workflow. "
                "No real announcement was detected."
            ),
            pub_date=now,
            pub_date_raw="just now (test)",
        )
    ]

    ok = send_email_notification(sample_items)
    if not ok:
        logger.error("Test email was not sent", extra={"event": "test_email_failed"})
        return 1

    logger.info("Test email sent successfully", extra={"event": "test_email_ok"})
    return 0


if __name__ == "__main__":
    sys.exit(main())
