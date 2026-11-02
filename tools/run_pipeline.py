"""Run the whole daily pipeline in order. Stops at the first failing step.

  python tools/run_pipeline.py                 # full run (needs the `claude` CLI)
  python tools/run_pipeline.py --until cluster # stop after a step (e.g. for local testing)
  python tools/run_pipeline.py --from extract  # resume from a step
"""
import argparse
import subprocess
import sys
import time

from common import ROOT

STEPS = [
    ("fetch", ["fetch_feeds.py"]),
    ("prefilter", ["prefilter.py"]),
    ("cluster", ["cluster_stories.py"]),
    ("select", ["run_claude.py", "select"]),
    ("extract", ["extract_articles.py"]),
    ("analyze", ["run_claude.py", "analyze"]),
    ("validate", ["validate_report.py"]),
    ("render", ["render_report.py"]),
    ("notify", ["notify_telegram.py"]),
]


def main() -> None:
    names = [n for n, _ in STEPS]
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", choices=names, default=names[0])
    ap.add_argument("--until", choices=names, default=names[-1])
    args = ap.parse_args()

    for name, cmd in STEPS[names.index(args.start): names.index(args.until) + 1]:
        print(f"\n=== {name} ===", flush=True)
        t0 = time.time()
        rc = subprocess.call([sys.executable, str(ROOT / "tools" / cmd[0]), *cmd[1:]], cwd=ROOT)
        print(f"--- {name} took {time.time() - t0:.0f}s", flush=True)
        if rc:
            sys.exit(f"step '{name}' failed with exit code {rc}")


if __name__ == "__main__":
    main()
