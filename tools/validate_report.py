"""Validate the per-story analyses and assemble the final report.

Checks every story against tools/story_schema.json and that every URL was in the
input (no invented links). Bad sources are dropped; stories that fail the schema
or end up without sources are dropped and listed.

Input:  .tmp/stories/*.json, .tmp/stories_input/*.json, .tmp/articles_raw.json
Output: .tmp/report.json, data/history.json (last 7 days of story titles)
Exit code 1 if fewer than --min-stories survive.
"""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from jsonschema import Draft202012Validator

from common import DATA, TMP, TOOLS, load_json, load_sources, save_json

SOFIA = ZoneInfo("Europe/Sofia")


def allowed_urls(story_input: dict) -> set[str]:
    urls = {a["url"] for a in story_input["articles"]}
    urls |= {a["url"] for a in story_input.get("also_covered_by", [])}
    return urls


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-stories", type=int, default=5)
    args = ap.parse_args()

    validator = Draft202012Validator(json.loads((TOOLS / "story_schema.json").read_text("utf-8")))
    stories, problems = [], []
    for path in sorted((TMP / "stories").glob("*.json")):
        story = load_json(path)
        inp = load_json(TMP / "stories_input" / path.name, {"articles": []})
        errors = [e.message for e in validator.iter_errors(story)]
        if errors:
            problems.append(f"{path.stem}: schema: {errors[0][:150]}")
            continue
        ok = allowed_urls(inp)
        bad = [s["url"] for s in story["sources"] if s["url"] not in ok]
        story["sources"] = [s for s in story["sources"] if s["url"] in ok]
        if bad:
            problems.append(f"{path.stem}: dropped {len(bad)} unknown URL(s)")
        if not story["sources"]:
            problems.append(f"{path.stem}: no valid sources left - story dropped")
            continue
        if len({s["outlet"] for s in story["sources"]}) < 2:
            story["coverage_comparison"] = None
        stories.append(story)

    order = lambda s: (-s["importance"], s["story_id"])
    world = sorted([s for s in stories if s["section"] == "world"], key=order)
    bulgaria = sorted([s for s in stories if s["section"] == "bulgaria"], key=order)

    raw = load_json(TMP / "articles_raw.json", [])
    counts = {}
    for a in raw:
        counts[a["source"]] = counts.get(a["source"], 0) + 1
    outlets = [{"id": s["id"], "name": s["name"], "region": s["region"], "ownership": s["ownership"],
                "articles_scanned": counts.get(s["id"], 0)} for s in load_sources()]

    now = datetime.now(SOFIA)
    report = {
        "date": now.strftime("%Y-%m-%d"),
        "generated_at": now.isoformat(timespec="minutes"),
        "stats": {"articles_scanned": len(raw), "outlets": len(outlets),
                  "stories": len(stories),
                  "compared": sum(1 for s in stories if s["coverage_comparison"])},
        "outlets": outlets,
        "world": world,
        "bulgaria": bulgaria,
    }
    save_json(TMP / "report.json", report)

    history = load_json(DATA / "history.json", {"stories": []})
    cutoff = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    history["stories"] = [h for h in history["stories"]
                          if h["date"] >= cutoff and h["date"] != report["date"]]
    history["stories"] += [{"date": report["date"], "title_en": s["title"]["en"]} for s in stories]
    save_json(DATA / "history.json", history)

    for p in problems:
        print("  ! " + p)
    print(f"report: {len(world)} world + {len(bulgaria)} bulgaria stories, "
          f"{report['stats']['compared']} with coverage comparison -> .tmp/report.json")
    if len(stories) < args.min_stories:
        sys.exit(f"only {len(stories)} valid stories (< {args.min_stories})")


if __name__ == "__main__":
    main()
