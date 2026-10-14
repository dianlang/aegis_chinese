#!/usr/bin/env python3
"""Windows-friendly local launcher for the incremental Chinese card database.

Read the already indexed card URLs, stream logs to console and an on-disk file,
and validate all saved JSON, including after network failure. No auto retry loop:
HTTP 429 and persistent 5xx need human review before attempting another run.
Python 3.9+.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def count_indexed():
    all_ids = set()
    for path in (DATA / "index").glob("*.json"):
        content = json.loads(path.read_text(encoding="utf-8"))
        all_ids.update(content.get("cards", {}))
    return len(all_ids)


def published():
    path = DATA / "manifest.json"
    if not path.exists():
        return 0
    return int(json.loads(path.read_text(encoding="utf-8")).get("publishedCardCount", 0))


def stream_command(argv, logfile, env):
    print("\n$ " + " ".join(argv), flush=True)
    with subprocess.Popen(
        argv,
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    ) as child:
        for line in child.stdout:
            print(line, end="", flush=True)
            logfile.write(line)
            logfile.flush()
        return child.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minutes", type=int, default=110)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--min-interval", type=float, default=1.0)
    parser.add_argument("--refresh-index", action="store_true",
                        help="Explicitly scan missing package URLs before importing")
    parser.add_argument("--dry-run", action="store_true")
    opts = parser.parse_args()
    if not 5 <= opts.minutes <= 112 or not 1 <= opts.workers <= 4 or opts.min_interval < 1:
        parser.error("minutes 5..112, workers 1..4, interval >=1 second")

    before = published()
    count = count_indexed()
    logdir = ROOT / "logs"
    logdir.mkdir(parents=True, exist_ok=True)
    filename = "local_bootstrap_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + ".log"
    logpath = logdir / filename
    print("Aegis Chinese database - Local bootstrap")
    print("Indexed card numbers:", count, "| Published Chinese cards:", before)
    print("Saved log:", logpath)
    print("Start interval: >= %.1fs; workers: %d; runtime budget: %d min"
          % (opts.min_interval, opts.workers, opts.minutes))
    print("Preserves old cards, checkpoints progress, respects upstream 429/5xx.")

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    with logpath.open("a", encoding="utf-8") as log:
        if (count < 4000 or opts.refresh_index) and not opts.dry_run:
            print("Index count is low / requested refresh; scanning a small set of packages.")
            cmd = [sys.executable, "-u", "tools/index_packages.py",
                   "--limit", "175", "--delay", str(opts.min_interval),
                   "--time-budget-seconds", "180"]
            if stream_command(cmd, log, env):
                print("Package discovery interrupted. Check logs; saved index is retained.")
                if count == 0:
                    return 2
            count = count_indexed()

        if count == 0:
            print("No local index. Clone/download the entire repository, including data/index/.")
            return 2

        cmd = [sys.executable, "-u", "tools/fast_bootstrap.py",
               "--max-cards", "6000", "--workers", str(opts.workers),
               "--min-interval", str(opts.min_interval),
               "--time-budget-minutes", str(opts.minutes),
               "--mode", "all"]
        if opts.dry_run:
            cmd.append("--dry-run")

        result = stream_command(cmd, log, env)
        if not opts.dry_run:
            check = stream_command([sys.executable, "-u", "tools/validate_database.py"], log, env)
        else:
            check = 0
        if result == 0 and check == 0 and not opts.dry_run:
            # Only mark initial bootstrap complete if index coverage is truly complete.
            stream_command([sys.executable, "-u", "tools/check_bootstrap.py"], log, env)
    after = published()
    print("\nChinese cards published locally: %d -> %d (+%d)"
          % (before, after, after - before))
    print("Log:", logpath)
    if check != 0:
        print("ERROR: Local data validation failed. Review logs before publishing.")
        return 3
    if result != 0:
        print("PAUSED: source/network failure. Local checkpoint is saved.")
        print("If errors mention 429/500/502/503, wait and investigate before starting again.")
        return result
    print("Batch finished or reached its time budget. Inspect cards and use git commit/push.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
