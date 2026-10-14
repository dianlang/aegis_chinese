#!/usr/bin/env python3
"""Time-boxed DigiCamoe initial card text import. Never bypass upstream throttling.

Existing public package indexes are prerequisites. Runs with a single shared
rate limiter (no burst) and a small number of in-flight requests; persists
validated results in checkpoints for safe resumption after interruption.
"""
import argparse
import concurrent.futures as cf
import datetime as dt
import sys
import threading
import time
import urllib.error
from pathlib import Path

try:
    from .sync_cards import (DATA, PARSER_VERSION, STATE_PATH, elapsed_days, fetch,
                             indexed_cards, load, parse, save, shard, timestamp)
except ImportError:
    from sync_cards import (DATA, PARSER_VERSION, STATE_PATH, elapsed_days, fetch,
                            indexed_cards, load, parse, save, shard, timestamp)


class StartRateLimiter:
    """Globally pace starts of HTTP requests, independently of worker count."""
    def __init__(self, interval):
        self.interval = interval
        self.lock = threading.Lock()
        self.next_start = 0.0

    def wait_slot(self, stop, deadline):
        with self.lock:
            now = time.monotonic()
            reserved = max(now, self.next_start)
            if reserved >= deadline:
                return False
            self.next_start = reserved + self.interval
        while True:
            remaining = reserved - time.monotonic()
            if remaining <= 0:
                return not stop.is_set() and time.monotonic() < deadline
            if stop.wait(min(remaining, 0.25)):
                return False


def build_pending(index, shards, state, mode, force=False, recheck_days=45):
    jobs = []
    stats = state.get("cards", {})
    for card_id, urls in index.items():
        current = shards[shard(card_id)].get(card_id)
        old = bool(current) and current.get("parserVersion", 0) < PARSER_VERSION
        if current and current.get("reviewStatus") == "verified":
            continue
        if mode == "new" and current:
            continue
        if mode == "enrich" and not old:
            continue
        last = stats.get(card_id, {})
        if not force:
            if last.get("status") == "failed" and elapsed_days(last.get("checkedAt")) < 7:
                continue
            if current and not old and elapsed_days(last.get("checkedAt")) < recheck_days:
                continue
        if urls:
            jobs.append((0 if old else (1 if not current else 2), card_id, urls))
    jobs.sort(key=lambda item: (item[0], item[1]))
    return jobs


def fetch_card(card_id, urls, limiter, stop, deadline, timeout):
    reason = "No valid source"
    for url in urls[:2]:
        if not limiter.wait_slot(stop, deadline):
            return "paused", card_id, None, reason
        try:
            result = parse(fetch(url, timeout), card_id, url)
            return "ok", card_id, result, ""
        except urllib.error.HTTPError as exc:
            reason = "HTTP " + str(exc.code)
            if exc.code == 429 or exc.code >= 500:
                stop.set()
                return "blocked", card_id, None, reason
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            reason = type(exc).__name__
            stop.set()
            return "blocked", card_id, None, reason
        except (ValueError, UnicodeError) as exc:
            reason = str(exc)[:110]
        if stop.is_set():
            return "paused", card_id, None, reason
    return "failed", card_id, None, reason


def bootstrap(args):
    if not (1 <= args.max_cards <= 10000 and 1 <= args.workers <= 4
            and args.min_interval >= 1.0 and 1 <= args.time_budget_minutes <= 112
            and 3 <= args.timeout <= 20 and args.checkpoint >= 1):
        raise SystemExit("Safety limits: <=4 workers, >=1.0 seconds/request, <=112 min")
    started = time.monotonic()
    deadline = started + args.time_budget_minutes * 60
    index = indexed_cards()
    if not index:
        print("STOP: No card links indexed. Run index_packages.py first.", file=sys.stderr)
        return 2
    status = load(STATE_PATH, {"version": 1, "cards": {}})
    status.setdefault("cards", {})
    names = {shard(card_id) for card_id in index}
    shards = {name: load(DATA / "cards" / (name + ".json"), {}) for name in names}
    jobs = build_pending(index, shards, status, args.mode, args.force)
    jobs = jobs[:args.max_cards]
    print("Indexed:", len(index), "Pending this run:", len(jobs),
          "Parallel waits:", args.workers, "Request interval:", args.min_interval,
          "Deadline (min):", args.time_budget_minutes, flush=True)
    if args.dry_run:
        for _, card_id, urls in jobs[:30]:
            print(card_id, urls[0])
        return 0

    stop = threading.Event()
    limiter = StartRateLimiter(args.min_interval)
    dirty = set()
    counter = {"ok": 0, "failed": 0, "paused": 0}
    processed = 0
    reason_stopped = ""

    def checkpoint():
        for name in list(dirty):
            save(DATA / "cards" / (name + ".json"), dict(sorted(shards[name].items())))
        dirty.clear()
        save(STATE_PATH, status)
        manifest_file = DATA / "manifest.json"
        manifest = load(manifest_file, {"schemaVersion": 1})
        manifest["updatedAt"] = timestamp()
        manifest["cardShards"] = sorted(p.stem for p in (DATA / "cards").glob("*.json"))
        manifest["publishedCardCount"] = sum(
            len(load(p, {})) for p in (DATA / "cards").glob("*.json")
        )
        manifest["note"] = "Incremental Chinese card database; see sync-state.json for failures"
        save(manifest_file, manifest)

    iterator = iter(jobs)
    inflight = {}
    try:
        with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
            def submit_until_full():
                while (len(inflight) < args.workers and not stop.is_set()
                       and time.monotonic() < deadline - args.timeout - 5):
                    try:
                        _, card_id, urls = next(iterator)
                    except StopIteration:
                        return
                    future = pool.submit(fetch_card, card_id, urls, limiter, stop,
                                         deadline, args.timeout)
                    inflight[future] = card_id

            submit_until_full()
            while inflight:
                done, _ = cf.wait(inflight, timeout=1, return_when=cf.FIRST_COMPLETED)
                for future in done:
                    card_id = inflight.pop(future)
                    try:
                        result, _, card, error = future.result()
                    except Exception as exc:
                        stop.set()
                        result, card, error = "blocked", None, type(exc).__name__
                    if result == "ok":
                        current = shards[shard(card_id)].get(card_id)
                        if current and current.get("reviewStatus") == "verified":
                            card = current
                        if card != current:
                            shards[shard(card_id)][card_id] = card
                            dirty.add(shard(card_id))
                        status["cards"][card_id] = {
                            "status": "ok", "checkedAt": timestamp(),
                            "url": card["url"], "parserVersion": PARSER_VERSION
                        }
                        counter["ok"] += 1
                    elif result == "failed":
                        status["cards"][card_id] = {
                            "status": "failed", "checkedAt": timestamp(), "reason": error
                        }
                        counter["failed"] += 1
                    elif result == "blocked":
                        stop.set()
                        reason_stopped = error
                    else:
                        counter["paused"] += 1
                    if result in ("ok", "failed"):
                        processed += 1
                        if processed % 25 == 0:
                            elapsed = (time.monotonic() - started) / 60
                            print("PROGRESS", processed, "/", len(jobs), "OK", counter["ok"],
                                  "FAILED", counter["failed"], "elapsed_min",
                                  round(elapsed, 1), flush=True)
                        if processed % args.checkpoint == 0:
                            checkpoint()
                if not stop.is_set():
                    submit_until_full()
                if time.monotonic() >= deadline - args.timeout - 5:
                    stop.set()
            checkpoint()
    finally:
        checkpoint()
    print("RESULT: indexed", len(index), "new_ok", counter["ok"],
          "failed", counter["failed"], "paused", counter["paused"],
          "total_published", sum(len(v) for v in shards.values()),
          "elapsed_minutes", round((time.monotonic() - started) / 60, 1), flush=True)
    if reason_stopped:
        print("STOP: upstream throttling/network", reason_stopped,
              "All completed records saved for later resumption", file=sys.stderr)
        return 2
    if stop.is_set():
        print("STOP: time budget reached; checkpoint saved", flush=True)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-cards", type=int, default=6000)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--min-interval", type=float, default=1.0)
    parser.add_argument("--timeout", type=int, default=10)
    parser.add_argument("--time-budget-minutes", type=int, default=110)
    parser.add_argument("--checkpoint", type=int, default=40)
    parser.add_argument("--mode", choices=("all", "new", "enrich"), default="all")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    sys.exit(bootstrap(parser.parse_args()))
