"""Fetch the last N hours of articles from every source in sources.yaml.

Output: .tmp/articles_raw.json  — list of normalised article dicts.
Usage:  python tools/fetch_feeds.py [--hours 26]
"""
import argparse
import hashlib
import html
import re
import defusedxml.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit, urlunsplit

import feedparser

from common import TMP, load_sources, save_json, session

NS = {
    "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
    "news": "http://www.google.com/schemas/sitemap-news/0.9",
}
TAG_RE = re.compile(r"<[^>]+>")


def clean(text: str, limit: int = 600) -> str:
    text = html.unescape(TAG_RE.sub(" ", text or ""))
    return re.sub(r"\s+", " ", text).strip()[:limit]


def normalise_url(url: str) -> str:
    parts = urlsplit(url.strip())
    if "news.google.com" in parts.netloc:
        return url.strip()  # query string is part of the article id
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path.rstrip("/"), "", ""))


def parse_date(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, tuple):  # feedparser struct_time
        return datetime(*value[:6], tzinfo=timezone.utc)
    value = value.strip()
    try:
        return parsedate_to_datetime(value).astimezone(timezone.utc)
    except (TypeError, ValueError):
        pass
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:  # date-only sitemap entries (e.g. BNT): assume Sofia local noon
        dt = dt.replace(hour=12, tzinfo=timezone(timedelta(hours=2)))
    return dt.astimezone(timezone.utc)


def expand_url(template: str, now: datetime) -> list[str]:
    if "{year}" not in template:
        return [template]
    months = [now]
    if now.day <= 2:
        months.append(now.replace(day=1) - timedelta(days=1))
    return [template.format(year=m.year, month=m.month) for m in months]


def from_rss(content: bytes, google: bool, source_name: str) -> list[dict]:
    feed = feedparser.parse(content)
    out = []
    for e in feed.entries:
        title = clean(e.get("title", ""), 300)
        if google:  # Google News appends " - Publisher"
            title = re.sub(r"\s+-\s+[^-]+$", "", title)
        tags = [t.get("term", "") for t in e.get("tags", [])]
        out.append({
            "title": title,
            "summary": "" if google else clean(e.get("summary", "")),
            "url": e.get("link", ""),
            "published": parse_date(e.get("published_parsed") or e.get("updated_parsed")),
            "category": ", ".join(t for t in tags if t)[:120],
        })
    return out


def from_sitemap(content: bytes) -> list[dict]:
    root = ET.fromstring(content)
    out = []
    for url in root.findall("sm:url", NS):
        news = url.find("news:news", NS)
        if news is None:
            continue
        out.append({
            "title": clean(news.findtext("news:title", "", NS), 300),
            "summary": "",
            "url": url.findtext("sm:loc", "", NS),
            "published": parse_date(news.findtext("news:publication_date", "", NS)),
            "category": "",
        })
    return out


def fetch_source(src: dict, since: datetime, now: datetime) -> tuple[str, list[dict], list[str]]:
    http = session()
    items, errors = [], []
    # Some BG sites block data-centre IPs (GitHub Actions) with 403; `fallback` feeds
    # (usually a Google News site: query) are only tried when the primary ones give nothing.
    for feeds in (src["feeds"], src.get("fallback", [])):
        if items:
            break
        for feed in feeds:
            for url in expand_url(feed["url"], now):
                try:
                    r = http.get(url, timeout=25)
                    r.raise_for_status()
                    if feed["method"] == "sitemap":
                        items += from_sitemap(r.content)
                    else:
                        items += from_rss(r.content, feed["method"] == "google_news", src["name"])
                except Exception as exc:  # one dead feed must not kill the run
                    errors.append(f"{url}: {exc}")
    if items and errors and src.get("fallback"):
        errors.append("-> used fallback feed")

    seen, articles = set(), []
    for it in items:
        if not it["title"] or not it["url"]:
            continue
        key = normalise_url(it["url"])
        title_key = it["title"].lower()  # Google News lists one article under several URLs
        if key in seen or title_key in seen:
            continue
        seen.update((key, title_key))
        pub = it["published"]
        if pub and (pub < since or pub > now + timedelta(hours=1)):
            continue
        articles.append({
            "id": hashlib.sha1(key.encode()).hexdigest()[:12],
            "source": src["id"],
            "source_name": src["name"],
            "region": src["region"],
            "lang": src["lang"],
            "ownership": src["ownership"],
            "title": it["title"],
            "summary": it["summary"],
            "url": it["url"],
            "category": it["category"],
            "published": pub.isoformat() if pub else None,
        })
    articles.sort(key=lambda a: a["published"] or "", reverse=True)
    return src["id"], articles[: src.get("max_items", 60)], errors


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=26)
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=args.hours)
    sources = load_sources()

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda s: fetch_source(s, since, now), sources))

    all_articles, empty = [], []
    for sid, arts, errs in results:
        all_articles += arts
        flag = "  <-- EMPTY" if not arts else ""
        print(f"{sid:16} {len(arts):4}{flag}")
        for e in errs:
            print(f"    ! {e}")
        if not arts:
            empty.append(sid)

    save_json(TMP / "articles_raw.json", all_articles)
    print(f"\n{len(all_articles)} articles from {len(sources) - len(empty)}/{len(sources)} sources "
          f"-> .tmp/articles_raw.json")
    if empty:
        print(f"WARNING: no articles from: {', '.join(empty)}")


if __name__ == "__main__":
    main()
