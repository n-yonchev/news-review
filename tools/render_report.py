"""Render .tmp/report.json into the static site.

Output: site/index.html, site/archive/<date>.html, site/archive/index.html
"""
from datetime import date
from html import escape

from jinja2 import Environment, FileSystemLoader, select_autoescape

from common import SITE, TMP, TOOLS, load_json

MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July", "August",
             "September", "October", "November", "December"]
MONTHS_BG = ["януари", "февруари", "март", "април", "май", "юни", "юли", "август",
             "септември", "октомври", "ноември", "декември"]
DAYS_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DAYS_BG = ["понеделник", "вторник", "сряда", "четвъртък", "петък", "събота", "неделя"]


def bi(en: str, bg: str) -> dict:
    return {"en": en, "bg": bg}


LABELS = {
    "title": bi("Daily News Review", "Дневен новинарски преглед"),
    "world": bi("World", "Свят"),
    "bulgaria": bi("Bulgaria", "България"),
    "sources": bi("Sources", "Източници"),
    "sources_scanned": bi("Outlets scanned", "Проверени медии"),
    "archive": bi("Archive", "Архив"),
    "outlet": bi("outlet", "медия"),
    "outlets": bi("outlets", "медии"),
    "articles": bi("Articles", "Статии"),
    "articles_from": bi("articles from", "статии от"),
    "compared": bi("stories compared across outlets", "истории със сравнение на отразяването"),
    "region": bi("Region", "Регион"),
    "ownership": bi("Ownership", "Собственост"),
    "how_covered": bi("How the outlets covered it", "Как медиите го отразиха"),
    "generated": bi("Generated", "Генериран"),
    "method": bi(
        "Articles from the last 24 hours are collected from public RSS feeds and sitemaps, grouped "
        "into stories by meaning, ranked by how many outlets cover them, and analysed by Claude. "
        "Summaries can contain mistakes — follow the links for the original reporting.",
        "Статиите от последните 24 часа се събират от публични RSS канали и карти на сайтовете, "
        "групират се в истории по смисъл, подреждат се според броя медии, които ги отразяват, и се "
        "анализират от Claude. Резюметата може да съдържат грешки — следвайте връзките към "
        "оригиналните публикации.",
    ),
    "own_public": bi("public", "обществена"),
    "own_state-funded": bi("state-funded", "държавно финансирана"),
    "own_commercial": bi("commercial", "търговска"),
    "asp_framing": bi("Framing", "Рамкиране"),
    "asp_emphasis": bi("Emphasis", "Акцент"),
    "asp_omission": bi("Omission", "Пропуск"),
    "asp_tone": bi("Tone", "Тон"),
    "asp_sources_quoted": bi("Who is quoted", "Кой е цитиран"),
    "asp_context": bi("Context", "Контекст"),
    "asp_facts": bi("Conflicting facts", "Разминаващи се факти"),
    "cat_politics": bi("Politics", "Политика"),
    "cat_conflict": bi("Conflict", "Конфликт"),
    "cat_diplomacy": bi("Diplomacy", "Дипломация"),
    "cat_economy": bi("Economy", "Икономика"),
    "cat_justice": bi("Justice", "Правосъдие"),
    "cat_society": bi("Society", "Общество"),
    "cat_environment": bi("Environment", "Околна среда"),
    "cat_disaster": bi("Disaster", "Бедствие"),
    "cat_health": bi("Health", "Здраве"),
    "cat_science_tech": bi("Science & tech", "Наука и технологии"),
}


def long_date(iso: str) -> dict:
    d = date.fromisoformat(iso)
    return bi(f"{DAYS_EN[d.weekday()]}, {d.day} {MONTHS_EN[d.month - 1]} {d.year}",
              f"{DAYS_BG[d.weekday()]}, {d.day} {MONTHS_BG[d.month - 1]} {d.year} г.")


def write_archive_index() -> None:
    pages = sorted((p.stem for p in (SITE / "archive").glob("????-??-??.html")), reverse=True)
    items = "\n".join(f'<li><a href="{p}.html">{p}</a></li>' for p in pages)
    (SITE / "archive" / "index.html").write_text(
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        "<title>News Review Archive</title><style>body{font:17px/1.6 Georgia,serif;max-width:640px;"
        "margin:40px auto;padding:0 16px;background:#f7f5f0;color:#1c1b19}a{color:#1d4f91}"
        "@media(prefers-color-scheme:dark){body{background:#131312;color:#ecebe7}a{color:#8ab4f8}}"
        "</style></head><body><h1>Archive · Архив</h1><p><a href=\"../index.html\">"
        f"&larr; Latest · Последен</a></p><ul>{items}</ul></body></html>",
        encoding="utf-8",
    )


def main() -> None:
    report = load_json(TMP / "report.json")
    env = Environment(loader=FileSystemLoader(TOOLS / "templates"),
                      autoescape=select_autoescape(["html", "j2"]))
    template = env.get_template("report.html.j2")
    ctx = {"report": report, "labels": LABELS, "date_long": long_date(report["date"])}

    (SITE / "archive").mkdir(parents=True, exist_ok=True)
    (SITE / "index.html").write_text(
        template.render(**ctx, archive_href="archive/index.html"), encoding="utf-8")
    (SITE / "archive" / f"{report['date']}.html").write_text(
        template.render(**ctx, archive_href="index.html"), encoding="utf-8")
    write_archive_index()
    print(f"rendered site/index.html and site/archive/{escape(report['date'])}.html")


if __name__ == "__main__":
    main()
