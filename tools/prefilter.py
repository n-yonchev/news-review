"""Cheap rule-based removal of obviously irrelevant articles (sport, lifestyle, weather...).

Semantic "is this local?" judgement happens later in the Claude selection step;
this only strips the noise so clustering and selection stay small.

Input:  .tmp/articles_raw.json
Output: .tmp/articles_filtered.json
"""
import re
from collections import Counter
from urllib.parse import urlsplit

from common import TMP, load_json, save_json

# URL path segments (lowercase) that mark non-news sections.
BAD_PATH = {
    "sport", "sports", "football", "soccer", "tennis", "formula1", "f1", "cricket", "rugby", "golf",
    "lifestyle", "life-style", "entertainment", "celebrity", "showbiz", "style", "fashion", "beauty",
    "travel", "food", "recipes", "horoscope", "horoscopes", "astrology", "weather", "games", "puzzles",
    "crosswords", "underscored", "cnn-underscored", "shopping", "deals", "coupons", "podcasts",
    "podcast", "video", "videos", "gallery", "galleries", "photos", "in-pictures", "live-tv",
    "tv-and-radio", "music", "film", "books", "stage", "culture", "arts", "lifeandstyle", "wellness",
    # Bulgarian site sections
    "shou", "zvezdi", "horoskop", "horoskopi", "vremeto", "lyubopitno", "lubopitno", "zdrave",
    "kuhnya", "recepti", "avtomobili", "auto", "tehnologii-i-nauka", "sportni", "futbol",
    "lifestyle-bg", "galeria", "video-bg", "tv-shou",
}
# Category / tag words (any language) that mark non-news.
BAD_CATEGORY = re.compile(
    r"\b(sport|sports|football|soccer|lifestyle|entertainment|celebrit|showbiz|horoscope|weather|"
    r"спорт|футбол|шоу|звезди|хороскоп|времето|любопитно|лайфстайл|здраве|рецепт|кухня|авто)\b",
    re.I,
)
BAD_TITLE = re.compile(
    r"(horoscope|wordle|crossword|quiz:|recipe|best deals|how to watch|live stream|"
    r"хороскоп|прогноза за времето|времето днес|рецепта|тото|лотария|"
    r"новините на nova|сюжети от деня|^новините в \d|"
    r"\b(premier league|champions league|nba|nfl|mlb|nhl)\b)",
    re.I,
)


def reason_to_drop(a: dict) -> str | None:
    segments = {s for s in urlsplit(a["url"]).path.lower().split("/") if s}
    if segments & BAD_PATH:
        return "path"
    if a.get("category") and BAD_CATEGORY.search(a["category"]):
        return "category"
    if BAD_TITLE.search(a["title"]):
        return "title"
    if len(a["title"].split()) < 4:  # Google News also lists topic hubs ("Benjamin Netanyahu")
        return "short"
    return None


def main() -> None:
    articles = load_json(TMP / "articles_raw.json", [])
    kept, dropped = [], Counter()
    for a in articles:
        why = reason_to_drop(a)
        if why:
            dropped[(a["source"], why)] += 1
        else:
            kept.append(a)

    save_json(TMP / "articles_filtered.json", kept)
    per_source = Counter()
    for (src, _), n in dropped.items():
        per_source[src] += n
    print(f"kept {len(kept)} / {len(articles)}; dropped per source: {dict(per_source)}")


if __name__ == "__main__":
    main()
