"""Collecte RSS/Atom generique, sans dependance a un fournisseur."""
from __future__ import annotations

import datetime as dt
import html
import math
import re
import ssl
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

from ..models import DataSourceStatus, DataState, NewsItem, SourceRef

# Contexte SSL permissif pour les sites avec certificats auto-signes ou problematiques
_SSL_CONTEXT = ssl.create_default_context()
_SSL_CONTEXT.check_hostname = False
_SSL_CONTEXT.verify_mode = ssl.CERT_NONE


def _tag(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1].lower()


def _text(element: ET.Element, names: set[str]) -> str:
    for child in element:
        if _tag(child) in names:
            value = "".join(child.itertext())
            if value:
                return " ".join(value.split())
    return ""


def _link(element: ET.Element) -> str | None:
    for child in element:
        if _tag(child) == "link":
            return child.attrib.get("href") or (child.text or "").strip() or None
    return None


def _plain(value: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", html.unescape(value or "")).split())


def _date(element: ET.Element) -> dt.datetime | None:
    value = _text(element, {"pubdate", "published", "updated", "date"})
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return parsed.astimezone() if parsed.tzinfo else parsed.astimezone()


def _payload(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    )
    with urllib.request.urlopen(request, timeout=12, context=_SSL_CONTEXT) as response:
        return response.read(2_000_000)


def collect_rss(
    feeds: list, now: dt.datetime, *, limit: int = 12, max_age_hours: int = 72,
    status_name: str = "Actualites",
) -> tuple[list[NewsItem], DataSourceStatus]:
    if not feeds:
        return [], DataSourceStatus(
            name=status_name, state=DataState.DISABLED,
            detail="Aucun flux RSS configure.",
        )
    buckets: list[list[NewsItem]] = []
    seen: set[str] = set()
    cutoff = now - dt.timedelta(hours=max_age_hours)
    future_limit = now + dt.timedelta(hours=6)
    per_feed = max(2, math.ceil(limit / max(1, len(feeds))))
    errors = 0
    for entry in feeds:
        if isinstance(entry, str):
            name, category, url = "Source", "Actualites", entry
        elif isinstance(entry, dict):
            name = str(entry.get("name") or entry.get("nom") or "Source")
            category = str(entry.get("category") or entry.get("categorie") or "Actualites")
            url = str(entry.get("url") or "")
        else:
            continue
        if not url:
            continue
        try:
            payload = _payload(url)
            try:
                root = ET.fromstring(payload)
            except ET.ParseError:
                repaired = payload.decode("utf-8", errors="replace")
                repaired = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", repaired)
                repaired = re.sub(
                    r"&(?!#\d+;|#x[0-9A-Fa-f]+;|[A-Za-z][A-Za-z0-9]+;)",
                    "&amp;", repaired,
                )
                root = ET.fromstring(repaired)
            bucket: list[NewsItem] = []
            for node in (node for node in root.iter() if _tag(node) in {"item", "entry"}):
                title = _plain(_text(node, {"title"}))
                link = _link(node) or url
                key = (link or title).casefold()
                published = _date(node)
                if not title or key in seen:
                    continue
                if published and (published < cutoff or published > future_limit):
                    continue
                seen.add(key)
                summary = _plain(_text(node, {"description", "summary", "content"}))
                bucket.append(NewsItem(
                    title=title,
                    category=category,
                    summary=summary or "Resume non fourni par le flux.",
                    expanded_summary=summary,
                    source=SourceRef(name=name, url=link, published_at=published),
                ))
                if len(bucket) >= per_feed:
                    break
            if bucket:
                buckets.append(bucket)
        except Exception:
            errors += 1
    items: list[NewsItem] = []
    while len(items) < limit and any(buckets):
        for bucket in buckets:
            if bucket and len(items) < limit:
                items.append(bucket.pop(0))
    state = DataState.LIVE if items else DataState.UNAVAILABLE
    detail = f"{len(feeds) - errors}/{len(feeds)} flux lus"
    return items, DataSourceStatus(
        name=status_name, state=state, detail=detail, item_count=len(items),
    )
