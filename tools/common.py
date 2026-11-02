"""Shared helpers for the news pipeline: paths, JSON I/O, HTTP session."""
import json
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
TMP = ROOT / ".tmp"
DATA = ROOT / "data"
SITE = ROOT / "site"
TOOLS = ROOT / "tools"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)

# Windows consoles default to cp1252; Cyrillic output would crash print().
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en,bg;q=0.8"})
    return s


def load_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_sources(include_disabled: bool = False) -> list[dict]:
    import yaml

    cfg = yaml.safe_load((TOOLS / "sources.yaml").read_text(encoding="utf-8"))
    return [s for s in cfg["sources"] if include_disabled or s.get("enabled", True)]
