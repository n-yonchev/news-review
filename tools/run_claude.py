"""Run the judgement steps through Claude Code in headless mode (`claude -p`).

Uses whatever auth the CLI has: in GitHub Actions that is CLAUDE_CODE_OAUTH_TOKEN
(your Claude subscription, created with `claude setup-token`).

  python tools/run_claude.py select    # .tmp/candidates.json      -> .tmp/selection.json
  python tools/run_claude.py analyze   # .tmp/stories_input/*.json -> .tmp/stories/*.json

Env: CLAUDE_MODEL (default "sonnet"), N_WORLD (15), N_BG (10), CLAUDE_PARALLEL (3)
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

from common import TMP, TOOLS, load_json, save_json

MODEL = os.environ.get("CLAUDE_MODEL", "sonnet")
CLAUDE = shutil.which("claude") or "claude"

# Prompts contain untrusted article text (prompt-injection risk), so Claude gets no tools:
# it can only read the prompt and answer. It also runs in an empty directory and
# without our other secrets in its environment.
NO_TOOLS = ("Bash,Read,Write,Edit,MultiEdit,Glob,Grep,LS,WebFetch,WebSearch,NotebookEdit,"
            "NotebookRead,Task,TodoWrite")
PASS_ENV = ("PATH", "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "SYSTEMROOT", "TEMP", "TMP",
            "LANG", "CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY")


def ask_claude(prompt: str, timeout: int = 900) -> dict:
    """Send a prompt, return the JSON object Claude answers with. Retries once."""
    env = {k: v for k, v in os.environ.items() if k in PASS_ENV}
    last_err = None
    for _ in range(2):
        with tempfile.TemporaryDirectory() as sandbox:
            proc = subprocess.run(
                [CLAUDE, "-p", "--model", MODEL, "--output-format", "json",
                 "--disallowedTools", NO_TOOLS],
                input=prompt, capture_output=True, text=True, encoding="utf-8", timeout=timeout,
                cwd=sandbox, env=env,
            )
        try:
            envelope = json.loads(proc.stdout)
            if envelope.get("is_error"):
                raise ValueError(envelope.get("result"))
            text = envelope["result"]
            return json.loads(text[text.index("{"): text.rindex("}") + 1])
        except (ValueError, KeyError) as exc:
            last_err = f"{str(exc)[:300]} | stderr: {proc.stderr[-300:]}"
    raise RuntimeError(f"Claude call failed twice: {last_err}")


def select() -> None:
    template = (TOOLS / "prompts" / "select.md").read_text(encoding="utf-8")
    candidates = load_json(TMP / "candidates.json")
    prompt = template.format(
        n_world=os.environ.get("N_WORLD", "15"),
        n_bg=os.environ.get("N_BG", "10"),
        candidates=json.dumps(candidates, ensure_ascii=False, indent=1),
    )
    selection = ask_claude(prompt)
    valid_ids = {c["id"] for c in candidates}
    for s in selection["stories"]:
        s["cluster_ids"] = [c for c in s["cluster_ids"] if c in valid_ids]
    selection["stories"] = [s for s in selection["stories"]
                            if s["cluster_ids"] and s.get("section") in ("world", "bulgaria")]
    # Claude sometimes invents ids like "b01x"; renumber deterministically, keeping its order.
    counters = {"world": 0, "bulgaria": 0}
    for s in selection["stories"]:
        counters[s["section"]] += 1
        s["story_id"] = f"{s['section'][0]}{counters[s['section']]:02d}"
    save_json(TMP / "selection.json", selection)
    print(f"selected {len(selection['stories'])} stories -> .tmp/selection.json")


def analyze_one(path, template: str) -> str:
    story = load_json(path)
    prompt = template.format(
        story_id=story["story_id"], section=story["section"],
        story=json.dumps(story, ensure_ascii=False, indent=1),
    )
    try:
        result = ask_claude(prompt)
    except Exception as exc:
        return f"{story['story_id']}: FAILED {exc}"
    save_json(TMP / "stories" / path.name, result)
    return f"{story['story_id']}: ok"


def analyze() -> None:
    template = (TOOLS / "prompts" / "analyze.md").read_text(encoding="utf-8")
    shutil.rmtree(TMP / "stories", ignore_errors=True)
    paths = sorted((TMP / "stories_input").glob("*.json"))
    workers = int(os.environ.get("CLAUDE_PARALLEL", "3"))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for line in pool.map(lambda p: analyze_one(p, template), paths):
            print(line)


if __name__ == "__main__":
    {"select": select, "analyze": analyze}[sys.argv[1]]()
