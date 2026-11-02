"""Send the morning Telegram message with the top headlines and the report link.

Env (.env locally, GitHub secrets in CI): TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, REPORT_URL
Skips quietly when the token is not set.
"""
import os
from html import escape

from dotenv import load_dotenv

from common import ROOT, TMP, load_json, session


def main() -> None:
    load_dotenv(ROOT / ".env")
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    url = os.environ.get("REPORT_URL", "")
    if not token or not chat:
        print("TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID not set - skipping notification")
        return

    report = load_json(TMP / "report.json")
    lines = [f"<b>📰 Новинарски преглед · {report['date']}</b>", ""]
    for label, key in (("🌍 Свят", "world"), ("🇧🇬 България", "bulgaria")):
        lines.append(f"<b>{label}</b>")
        lines += [f"• {escape(s['title']['bg'])}" for s in report[key][:3]]
        lines.append("")
    s = report["stats"]
    lines.append(f"{s['stories']} истории · {s['compared']} със сравнение · {s['articles_scanned']} статии")
    if url:
        lines.append(f'\n<a href="{escape(url)}">Отвори прегледа / Open the report</a>')

    try:
        r = session().post(f"https://api.telegram.org/bot{token}/sendMessage", timeout=20, json={
            "chat_id": chat, "text": "\n".join(lines), "parse_mode": "HTML",
            "disable_web_page_preview": True,
        })
    except Exception as exc:  # connection errors include the URL, i.e. the token
        raise SystemExit(f"telegram request failed: {type(exc).__name__}")
    if not r.ok:  # don't raise: the exception text would contain the URL with the bot token
        raise SystemExit(f"telegram error {r.status_code}: {r.text[:200]}")
    print("telegram message sent")


if __name__ == "__main__":
    main()
