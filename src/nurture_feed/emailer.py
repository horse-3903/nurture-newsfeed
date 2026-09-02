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
    for index, item in enumerate(new_items):
        is_last = index == len(new_items) - 1
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
        row_style = "padding:0 0 18px 0;" if is_last else "padding:0 0 18px 0;border-bottom:1px solid #eaecf0;"
        html_rows.append(
            (
                f"<tr><td style=\"{row_style}\">"
                f"<div style=\"font-size:15px;line-height:1.4;font-weight:600;color:#101828;\">"
                f"<a href=\"{safe_link}\" style=\"color:#101828;text-decoration:none;\">{safe_title}</a></div>"
                f"{date_line}"
                f"{desc_html}"
                f"<div style=\"margin-top:8px;\"><a href=\"{safe_link}\" "
                "style=\"color:#155eef;font-size:13px;text-decoration:none;\">Read more</a></div>"
                "</td></tr>"
            )
        )
        if not is_last:
            html_rows.append("<tr><td style=\"height:18px;line-height:18px;font-size:1px;\">&nbsp;</td></tr>")

    msg = EmailMessage()
    msg["Subject"] = f"[Nurture] {len(new_items)} new announcement(s)"
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg.set_content("\n".join(plain_lines))
    msg.add_alternative(
        (
            "<!doctype html><html><body style=\"margin:0;padding:0;background:#ffffff;"
            "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;\">"
            "<table role=\"presentation\" width=\"100%\" cellspacing=\"0\" cellpadding=\"0\" "
            "style=\"border-collapse:collapse;\">"
            "<tr><td align=\"center\" style=\"padding:32px 16px;\">"
            "<table role=\"presentation\" width=\"100%\" cellspacing=\"0\" cellpadding=\"0\" "
            "style=\"max-width:560px;border-collapse:collapse;\">"
            "<tr><td style=\"padding:0 0 20px 0;\">"
            "<div style=\"font-size:13px;font-weight:600;color:#667085;\">Nurture</div>"
            f"<div style=\"margin-top:4px;font-size:19px;line-height:1.3;font-weight:600;color:#101828;\">"
            f"{len(new_items)} new announcement{'s' if len(new_items) != 1 else ''}</div>"
            "</td></tr>"
            f"{''.join(html_rows)}"
            "<tr><td style=\"padding-top:24px;\">"
            "<div style=\"color:#98a2b3;font-size:12px;line-height:1.5;\">"
            f"<a href=\"{TARGET_URL}\" style=\"color:#98a2b3;text-decoration:underline;\">{TARGET_URL}</a>"
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
