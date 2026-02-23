from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .models import Announcement
from .selectors import get_selector_config
from .utils import estimate_pub_datetime, make_id, normalize_whitespace


def parse_pub_date_from_node(node: Any, selector_cfg: dict[str, list[str]]) -> tuple[str | None, str | None]:
    for selector in selector_cfg["date_nodes"]:
        date_el = node.select_one(selector)
        if not date_el:
            continue
        raw = date_el.get("datetime") or date_el.get_text(" ", strip=True)
        raw = normalize_whitespace(raw)
        if raw:
            return raw, estimate_pub_datetime(raw)
    return None, None


def parse_description_from_node(
    node: Any, selector_cfg: dict[str, list[str]], title_text: str
) -> str | None:
    for selector in selector_cfg["description_nodes"]:
        desc_el = node.select_one(selector)
        if not desc_el:
            continue
        text = normalize_whitespace(desc_el.get_text(" ", strip=True))
        if text and text != title_text:
            return text

    fallback_text = normalize_whitespace(node.get_text(" ", strip=True))
    if not fallback_text:
        return None
    if fallback_text.startswith(title_text):
        fallback_text = normalize_whitespace(fallback_text[len(title_text) :])
    return fallback_text


def parse_announcement_from_node(
    node: Any, base_url: str, selector_cfg: dict[str, list[str]]
) -> Announcement | None:
    title_text: str | None = None
    link: str | None = None
    source_id = normalize_whitespace(node.get("data-id")) if hasattr(node, "get") else None

    for selector in selector_cfg["title_nodes"]:
        candidate = node.select_one(selector)
        if not candidate:
            continue
        text = normalize_whitespace(candidate.get_text(" ", strip=True))
        href = None
        if candidate.has_attr("href"):
            href = candidate.get("href")
        else:
            parent_link = candidate.find_parent("a", href=True)
            if parent_link:
                href = parent_link.get("href")
        if text:
            title_text = text
            if href:
                link = urljoin(base_url, href)
            break

    if not title_text:
        return None

    if not link:
        fallback_anchor = node.select_one("a[href]")
        if fallback_anchor and fallback_anchor.get("href"):
            link = urljoin(base_url, fallback_anchor["href"])
        else:
            link = base_url

    pub_date_raw, pub_date_estimated = parse_pub_date_from_node(node, selector_cfg)

    return Announcement(
        id=make_id(title_text, link),
        title=title_text,
        link=link,
        source_id=source_id,
        author=None,
        description=parse_description_from_node(node, selector_cfg, title_text),
        pub_date_raw=pub_date_raw,
        pub_date=pub_date_estimated,
    )


def extract_announcements_from_html(html: str, base_url: str) -> list[Announcement]:
    selector_cfg = get_selector_config()
    soup = BeautifulSoup(html, "html.parser")

    candidates: list[Any] = []
    seen_nodes: set[int] = set()
    for selector in selector_cfg["item_nodes"]:
        for node in soup.select(selector):
            key = id(node)
            if key in seen_nodes:
                continue
            seen_nodes.add(key)
            candidates.append(node)

    if not candidates:
        for node in soup.select("main li, li, div, section"):
            if node.select_one("a[href]"):
                candidates.append(node)
            if len(candidates) >= 200:
                break

    announcements: list[Announcement] = []
    seen_ids: set[str] = set()
    for node in candidates:
        ann = parse_announcement_from_node(node, base_url=base_url, selector_cfg=selector_cfg)
        if not ann or ann.id in seen_ids:
            continue
        seen_ids.add(ann.id)
        announcements.append(ann)
    return announcements


def extract_detail_fields_from_html(html: str) -> dict[str, str | None]:
    soup = BeautifulSoup(html, "html.parser")
    title_el = soup.select_one(".card .card-body h5")
    body_el = soup.select_one(".card .card-body .tx-14.text-muted.my-3")
    author_el = soup.select_one(".card .card-body .ml-2 > p")
    rel_date_el = soup.select_one(".card .card-body .ml-2 .tx-11.text-muted")

    description = None
    if body_el:
        body_text = body_el.get_text("\n", strip=True)
        lines = [line.strip() for line in body_text.splitlines() if line.strip()]
        description = "\n".join(lines) if lines else None

    raw_rel_date = normalize_whitespace(rel_date_el.get_text(" ", strip=True)) if rel_date_el else None

    return {
        "title": normalize_whitespace(title_el.get_text(" ", strip=True)) if title_el else None,
        "description": description,
        "pub_date_raw": raw_rel_date,
        "pub_date": estimate_pub_datetime(raw_rel_date),
        "author": normalize_whitespace(author_el.get_text(" ", strip=True)) if author_el else None,
    }
