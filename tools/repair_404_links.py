#!/usr/bin/env python3
"""Check a few previously-404 card packages for real current links (not guessed URLs).

Never bypass rate limits. A single package listing is requested per pack and
each package is checked at most once per 24 hours by this program. Automatically
updates the existing AUTO index with discovered links. The original indexed
links are preserved for auditing and alternate printings.
"""
import argparse
import re
import sys
import time
import urllib.error
from collections import Counter, defaultdict
from urllib.parse import urlsplit, quote

try:
    from .index_packages import fetch, list_cards, URL_BASE, INDEX_FILE, STATE_FILE, now, read, write
    from .sync_cards import DATA
except ImportError:
    from index_packages import fetch, list_cards, URL_BASE, INDEX_FILE, STATE_FILE, now, read, write
    from sync_cards import DATA

PACK = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def targets(index, statuses, repair_state, max_packs=4, max_age_days=1):
    ids_by_pack = defaultdict(set)
    for cid, record in statuses.items():
        if record.get("status") != "failed" or not record.get("reason", "").startswith("HTTP 404"):
            continue
        for url in index.get("cards", {}).get(cid, []):
            parts = urlsplit(url)
            segments = parts.path.strip("/").split("/")
            if (parts.scheme != "https" or parts.netloc != "app.digicamoe.cn"
                    or len(segments) != 4 or segments[0] != "Cards"
                    or segments[2] != cid or not PACK.fullmatch(segments[1])):
                continue
            ids_by_pack[segments[1]].add(cid)
    eligible = []
    for pack, ids in ids_by_pack.items():
        checked = repair_state.get(pack)
        if checked:
            try:
                from .sync_cards import elapsed_days
            except ImportError:
                from sync_cards import elapsed_days
            if elapsed_days(checked) < max_age_days:
                continue
        eligible.append((pack, ids))
    return sorted(eligible, key=lambda x: (-len(x[1]), x[0]))[:max_packs]


def repair(max_packs=4, interval=4.0, timeout=15, dry_run=False):
    if not (1 <= max_packs <= 8 and interval >= 4 and 3 <= timeout <= 20):
        raise ValueError("Safety limits: <=8 package pages, >=4 seconds/request")
    index = read(INDEX_FILE, {"version": 1, "cards": {}})
    state = read(STATE_FILE, {"version": 1, "scanned": {}, "errors": {}})
    failures = read(DATA / "sync-state.json", {"cards": {}}).get("cards", {})
    repairs = state.setdefault("repairChecks", {})
    pending = targets(index, failures, repairs, max_packs)
    print("404 REPAIR: failed-card packages eligible", len(pending),
          "dry_run", dry_run, flush=True)
    if dry_run:
        for pack, ids in pending:
            print("PACKAGE", pack, "failed cards", len(ids))
        return 0
    next_start = 0.0
    updated = 0
    for pack, bad_ids in pending:
        if next_start > time.monotonic():
            time.sleep(next_start - time.monotonic())
        next_start = time.monotonic() + interval
        url = URL_BASE + "/Package/" + quote(pack)
        try:
            found = list_cards(fetch(url, timeout), pack)
        except urllib.error.HTTPError as exc:
            print("REPAIR ERROR", pack, "HTTP", exc.code, flush=True)
            if exc.code == 429 or exc.code >= 500:
                print("STOP: upstream unavailable, wait for the site to recover",
                      file=sys.stderr)
                return 2
            repairs[pack] = now()
            write(STATE_FILE, state)
            continue
        except (urllib.error.URLError, OSError, TimeoutError, ValueError) as exc:
            print("STOP: repair network error", pack, type(exc).__name__,
                  str(exc)[:100], file=sys.stderr)
            return 2
        repairs[pack] = now()
        for cid in bad_ids:
            discovered = found.get(cid, [])
            if not discovered:
                continue
            old = index["cards"].get(cid, [])
            refreshed = list(dict.fromkeys(discovered + old))
            if refreshed != old:
                index["cards"][cid] = refreshed
                updated += 1
                failures[cid]["status"] = "pending_recheck"
                print("REPAIRED", cid, "current URLs", len(discovered),
                      "previous URLs", len(old), flush=True)
        write(INDEX_FILE, index)
        write(STATE_FILE, state)
    if updated:
        # Only the status fields of specifically repaired cards are changed.
        path = DATA / "sync-state.json"
        obj = read(path, {"version": 1, "cards": {}})
        for cid, value in failures.items():
            if value.get("status") == "pending_recheck" and cid in obj.get("cards", {}):
                obj["cards"][cid]["status"] = "pending_recheck"
        write(path, obj)
    print("404 REPAIR RESULT", updated, "card indexes updated", flush=True)
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--max-packs", type=int, default=4)
    p.add_argument("--interval", type=float, default=4.0)
    p.add_argument("--timeout", type=int, default=15)
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    sys.exit(repair(a.max_packs, a.interval, a.timeout, a.dry_run))
