import html
import os
import smtplib
from email.message import EmailMessage

from .config import TARGET_URL
from .logging_utils import logger
from .models import Announcement
from .utils import parse_recipients


def send_email_notification(new_items: list[Announcement]) -> bool:
    sender = os.getenv("EMAIL_SENDER")
    password = os.getenv("EMAIL_PASSWORD")
    recipients = parse_recipients(os.getenv("EMAIL_RECIPIENTS"))

    if not new_items:
        return False
    if not sender or not password or not recipients:
        logger.info("Email settings incomplete; skipping notification", extra={"event": "email_skipped"})
        return False

    plain_lines = [f"{len(new_items)} new announcement(s) detected on Nurture:", ""]
    for item in new_items:
        plain_lines.append(f"- {item.title}")
        plain_lines.append(f"  {item.link}")
        if item.pub_date:
            plain_lines.append(f"  Date: {item.pub_date}")
        plain_lines.append("")
    plain_lines.append(f"Source: {TARGET_URL}")

    html_rows: list[str] = []
    for item in new_items:
        safe_title = html.escape(item.title)
        safe_link = html.escape(item.link, quote=True)
        safe_date = html.escape(item.pub_date) if item.pub_date else ""
        safe_desc = html.escape(item.description) if item.description else ""
        date_html = f"<div><small>{safe_date}</small></div>" if item.pub_date else ""
        desc_html = f"<div>{safe_desc}</div>" if item.description else ""
        html_rows.append(f"<li><a href=\"{safe_link}\">{safe_title}</a>{date_html}{desc_html}</li>")

    msg = EmailMessage()
    msg["Subject"] = f"[Nurture] {len(new_items)} new announcement(s)"
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg.set_content("\n".join(plain_lines))
    msg.add_alternative(
        (
            f"<p>{len(new_items)} new announcement(s) detected on Nurture.</p>"
            f"<ul>{''.join(html_rows)}</ul>"
            f"<p>Source: <a href=\"{TARGET_URL}\">{TARGET_URL}</a></p>"
        ),
        subtype="html",
    )

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(sender, password)
            smtp.send_message(msg)
        logger.info("Notification email sent", extra={"event": "email_sent", "count": len(new_items)})
        return True
    except Exception:
        logger.error(
            "Email notification failed; continuing without crashing",
            extra={"event": "email_failed", "count": len(new_items)},
            exc_info=True,
        )
        return False

