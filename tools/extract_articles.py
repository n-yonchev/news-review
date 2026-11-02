"""Fetch full article text for the stories chosen in the Claude selection step.

Input:  .tmp/selection.json, .tmp/clusters.json
Output: .tmp/stories_input/<story_id>.json  — one file per story for the analysis step
Usage:  python tools/extract_articles.py [--per-story 6] [--max-chars 6000]
"""
import argparse
import shutil
from concurrent.futures import ThreadPoolExecutor

import trafilatura

from common import TMP, load_json, save_json, session

NO_FETCH = {"reuters", "ap"}  # block scrapers; Google News gives only title + link


def resolve_google(url: str) -> str:
    """Turn a news.google.com redirect into the publisher URL when possible."""
    if "news.google.com" not in url:
        return url
    try:
        from googlenewsdecoder import gnewsdecoder

        res = gnewsdecoder(url, interval=0.5)
        if res.get("status") or res.get("success"):  # key name differs between versions
            return res["decoded_url"]
    except Exception:
        pass
    return url


def fetch_text(art: dict, max_chars: int) -> dict:
    art = dict(art)
    art["url"] = resolve_google(art["url"])
    text = ""
    # Undecoded Google links lead to a consent page (EU IPs), never the article.
    if art["source"] not in NO_FETCH and "news.google.com" not in art["url"]:
        try:
            r = session().get(art["url"], timeout=25)
            if r.ok:
                text = trafilatura.extract(r.text, include_comments=False, favor_precision=True) or ""
        except Exception:
            pass
    if len(text) > 300:
        art["text"], art["text_source"] = text[:max_chars], "full"
    elif art.get("summary"):
        art["text"], art["text_source"] = art["summary"], "summary"
    else:
        art["text"], art["text_source"] = "", "title_only"
    return art


def pick_articles(arts: list[dict], n: int) -> list[dict]:
    """One article per outlet, alternating world/bg so both perspectives get in."""
    by_outlet: dict[str, dict] = {}
    for a in sorted(arts, key=lambda a: a["published"] or ""):  # earliest per outlet
        by_outlet.setdefault(a["source"], a)
    world = [a for a in by_outlet.values() if a["region"] == "world"]
    bg = [a for a in by_outlet.values() if a["region"] == "bg"]
    world.sort(key=lambda a: a["source"] in NO_FETCH)  # fetchable outlets first
    picked = []
    while len(picked) < n and (world or bg):
        for pool in (world, bg):
            if pool and len(picked) < n:
                picked.append(pool.pop(0))
    return picked


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-story", type=int, default=6)
    ap.add_argument("--max-chars", type=int, default=6000)
    args = ap.parse_args()

    selection = load_json(TMP / "selection.json")
    clusters = {c["id"]: c for c in load_json(TMP / "clusters.json", [])}
    out_dir = TMP / "stories_input"
    shutil.rmtree(out_dir, ignore_errors=True)

    for story in selection["stories"]:
        drop = set(story.get("drop_article_titles", []))
        arts = [a for cid in story["cluster_ids"] for a in clusters[cid]["articles"]
                if a["title"] not in drop]
        picked = pick_articles(arts, args.per_story)
        with ThreadPoolExecutor(max_workers=6) as pool:
            full = list(pool.map(lambda a: fetch_text(a, args.max_chars), picked))
        picked_ids = {a["id"] for a in picked}
        also = [{"source_name": a["source_name"], "title": a["title"], "url": resolve_google(a["url"])}
                for a in arts if a["id"] not in picked_ids]
        save_json(out_dir / f"{story['story_id']}.json", {
            "story_id": story["story_id"],
            "section": story["section"],
            "working_title": story.get("working_title", ""),
            "articles": [
                {k: a[k] for k in ("source_name", "region", "lang", "ownership", "title", "url",
                                   "published", "text", "text_source")}
                for a in full
            ],
            "also_covered_by": also[:12],
        })
        kinds = ",".join(a["text_source"][0] for a in full)
        print(f"{story['story_id']:5} {len(full)} articles [{kinds}] {story.get('working_title', '')[:70]}")


if __name__ == "__main__":
    main()
