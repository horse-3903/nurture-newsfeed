import html
import os
import smtplib
from email.message import EmailMessage

from .config import TARGET_URL
from .logging_utils import logger
from .models import Announcement
from .utils import load_recipients


def _truncate_email_text(value: str | None, max_len: int = 260) -> str:
    if not value:
        return ""
    text = " ".join(value.split())
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def send_email_notification(new_items: list[Announcement]) -> bool:
    sender = os.getenv("EMAIL_SENDER")
    password = os.getenv("EMAIL_PASSWORD")
    recipients = load_recipients(
        os.getenv("EMAIL_RECIPIENTS"),
        file_path=os.getenv("EMAIL_RECIPIENTS_FILE"),
    )

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
        safe_date_raw = html.escape(item.pub_date_raw) if item.pub_date_raw else ""
        safe_author = html.escape(item.author) if item.author else ""
        safe_desc = html.escape(item.description) if item.description else ""
        safe_desc = html.escape(_truncate_email_text(item.description))

        meta_parts = []
        if safe_date_raw:
            meta_parts.append(f"Posted: {safe_date_raw}")
        elif safe_date:
            meta_parts.append(f"Posted: {safe_date}")
        if safe_author:
            meta_parts.append(f"By: {safe_author}")
        meta_html = " | ".join(meta_parts)

        date_line = (
            f"<div style=\"margin:6px 0 0;color:#667085;font-size:12px;line-height:1.4;\">{meta_html}</div>"
            if meta_html
            else ""
        )
        desc_html = (
            f"<div style=\"margin:8px 0 0;color:#344054;font-size:13px;line-height:1.5;\">{safe_desc}</div>"
            if safe_desc
            else ""
        )
        html_rows.append(
            (
                "<tr><td style=\"padding:0 0 10px 0;\">"
                "<table role=\"presentation\" width=\"100%\" cellspacing=\"0\" cellpadding=\"0\" "
                "style=\"border-collapse:separate;border-spacing:0;background:#ffffff;border:1px solid #eaecf0;"
                "border-radius:12px;\">"
                "<tr><td style=\"padding:14px 16px;\">"
                f"<div style=\"font-size:15px;line-height:1.35;font-weight:700;color:#101828;\">"
                f"<a href=\"{safe_link}\" style=\"color:#101828;text-decoration:none;\">{safe_title}</a></div>"
                f"{date_line}"
                f"{desc_html}"
                f"<div style=\"margin-top:10px;\"><a href=\"{safe_link}\" "
                "style=\"color:#155eef;font-size:13px;font-weight:600;text-decoration:none;\">Open announcement →</a></div>"
                "</td></tr></table>"
                "</td></tr>"
            )
        )

    msg = EmailMessage()
    msg["Subject"] = f"[Nurture] {len(new_items)} new announcement(s)"
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg.set_content("\n".join(plain_lines))
    msg.add_alternative(
        (
            "<!doctype html><html><body style=\"margin:0;padding:0;background:#f2f4f7;\">"
            "<table role=\"presentation\" width=\"100%\" cellspacing=\"0\" cellpadding=\"0\" "
            "style=\"border-collapse:collapse;background:#f2f4f7;\">"
            "<tr><td align=\"center\" style=\"padding:20px 12px;\">"
            "<table role=\"presentation\" width=\"100%\" cellspacing=\"0\" cellpadding=\"0\" "
            "style=\"max-width:700px;border-collapse:collapse;\">"
            "<tr><td style=\"padding:0 0 12px 0;\">"
            "<table role=\"presentation\" width=\"100%\" cellspacing=\"0\" cellpadding=\"0\" "
            "style=\"border-collapse:separate;border-spacing:0;background:linear-gradient(135deg,#155eef,#0ea5e9);"
            "border-radius:16px;\">"
            "<tr><td style=\"padding:18px 20px;color:#ffffff;\">"
            "<div style=\"font-size:12px;letter-spacing:.08em;text-transform:uppercase;opacity:.9;\">Nurture Feed</div>"
            f"<div style=\"margin-top:6px;font-size:22px;line-height:1.2;font-weight:700;\">"
            f"{len(new_items)} new announcement(s)</div>"
            "<div style=\"margin-top:6px;font-size:13px;line-height:1.4;opacity:.95;\">"
            "This notification was generated by your GitHub Actions RSS monitor.</div>"
            "</td></tr></table>"
            "</td></tr>"
            "<tr><td style=\"padding:0 0 10px 0;\">"
            "<table role=\"presentation\" width=\"100%\" cellspacing=\"0\" cellpadding=\"0\" "
            "style=\"border-collapse:separate;border-spacing:0;background:#ffffff;border:1px solid #eaecf0;"
            "border-radius:12px;\">"
            "<tr><td style=\"padding:12px 16px;color:#475467;font-size:13px;line-height:1.5;\">"
            "Announcements are listed below. Click any item to open the original Nurture page."
            "</td></tr></table>"
            "</td></tr>"
            f"{''.join(html_rows)}"
            "<tr><td style=\"padding-top:4px;\">"
            "<div style=\"color:#667085;font-size:12px;line-height:1.5;padding:6px 2px;\">"
            f"Source: <a href=\"{TARGET_URL}\" style=\"color:#155eef;text-decoration:none;\">{TARGET_URL}</a>"
            "</div></td></tr>"
            "</table>"
            "</td></tr></table>"
            "</body></html>"
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
