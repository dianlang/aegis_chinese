#!/usr/bin/env python3
"""Incremental non-commercial DigiCamoe sync; single-threaded, fail-closed. Python 3.9+."""
import argparse
import datetime as dt
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
STATE_PATH = DATA / "sync-state.json"
HEADERS = {"User-Agent": "AegisChineseCommunity/0.3 (+https://github.com/dianlang/aegis_chinese)",
           "Accept": "text/html"}
SECTIONS = {"能力": "main", "进化源能力": "inherited", "安防能力": "security"}
END = {"收录信息", "卡片裁定", "相关卡片"}

def timestamp():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def elapsed_days(iso):
    if not iso: return 999999
    try:
        return (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))).total_seconds() / 86400
    except ValueError: return 999999

def load(path, fallback):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else fallback

def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    contents = json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if not path.exists() or path.read_text(encoding="utf-8") != contents:
        path.write_text(contents, encoding="utf-8")

def shard(card_id):
    if re.fullmatch(r"(?:P|LM)-\d{3}", card_id): return card_id.split("-")[0]
    m = re.fullmatch(r"((?:BT|EX|ST|AD|RB)\d{1,2})-\d{2,3}", card_id)
    if not m: raise ValueError("Invalid card ID " + card_id)
    return re.sub(r"\d+", lambda n: str(int(n.group())), m.group(1))

def parse(html, card_id, url):
    doc = BeautifulSoup(html, "html.parser")
    for el in doc.select("script,style,noscript,svg,template"): el.decompose()
    title = doc.find("h1")
    if not title: raise ValueError("Missing card h1")
    name = title.get_text(" ", strip=True)
    words = list((doc.body or doc).stripped_strings)
    full_text = "\n".join(words)
    if not re.search(r"(?:编\s*号|编号)\s*[:：]?\s*" + re.escape(card_id) + r"(?![\da-zA-Z-])", full_text, re.I):
        raise ValueError("Page card number mismatch")
    try: start = words.index(name)
    except ValueError: start = 0
    result = {"cardId": card_id, "name": name, "url": url}
    active = None
    for text in words[start:]:
        trimmed = re.sub(r"\s+", "", text)
        if trimmed in END: break
        if trimmed in SECTIONS:
            active = SECTIONS[trimmed]
            continue
        if active:
            result[active] = result.get(active, "") + ("\n" if result.get(active) else "") + text
        else:
            for key, label in (("form", "形态"), ("attribute", "属性"), ("types", "类型")):
                m = re.match(label + r"\s*[:：]?\s*(.+)", text)
                if m and len(m.group(1)) <= 100: result[key] = m.group(1).strip()
    if not any(result.get(key) for key in SECTIONS.values()): raise ValueError("No effect sections")
    if not re.search(r"[\u3400-\u9fff]", "".join(result.get(key, "") for key in SECTIONS.values())):
        raise ValueError("No Chinese effect")
    if len(name) > 100 or any(len(result.get(k, "")) > 9000 for k in SECTIONS.values()):
        raise ValueError("Unreasonable text size")
    return result

def fetch(url, timeout):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read(1_500_001)
        if len(data) > 1_500_000: raise ValueError("Page too large")
        return data.decode("utf-8", "replace")

def indexed_cards():
    mapping = {}
    for path in sorted((DATA / "index").glob("*.json")):
        for card_id, urls in load(path, {}).get("cards", {}).items():
            shard(card_id)
            target = mapping.setdefault(card_id, [])
            for url in urls:
                parsed = urlsplit(url)
                if (parsed.scheme == "https" and parsed.netloc == "app.digicamoe.cn"
                    and re.fullmatch(r"/Cards/[^/]+/" + re.escape(card_id) + r"/[^/]+/?", parsed.path)
                    and url not in target):
                    target.append(url)
    return mapping

def sync(args):
    if args.limit < 1 or args.limit > 100 or args.delay < 5:
        raise SystemExit("Safety limits: limit 1..100, delay >= 5 seconds")
    index = indexed_cards()
    state = load(STATE_PATH, {"version": 1, "cards": {}})
    status = state.setdefault("cards", {})
    shards = {shard(c): load(DATA / "cards" / (shard(c) + ".json"), {}) for c in index}
    pending = []
    for card_id, urls in index.items():
        if args.card and card_id != args.card: continue
        record = shards[shard(card_id)].get(card_id)
        last = status.get(card_id, {})
        if not args.force and last.get("status") == "failed" and elapsed_days(last.get("checkedAt")) < 7: continue
        if not args.force and record and elapsed_days(last.get("checkedAt")) < args.recheck_days: continue
        if urls: pending.append((record is not None, card_id, urls))
    pending.sort(key=lambda row: (row[0], row[1]))
    pending = pending[:args.limit]
    print("Indexed:", len(index), "This run:", len(pending), "Dry-run:", args.dry_run)
    if args.dry_run:
        for _, card_id, urls in pending: print(card_id, urls[0])
        return 0
    last_request = 0
    changed = 0
    blocked = False

    def persist():
        save(STATE_PATH, state)
        for name, records in shards.items():
            save(DATA / "cards" / (name + ".json"), dict(sorted(records.items())))
        manifest_path = DATA / "manifest.json"
        manifest = load(manifest_path, {"schemaVersion": 1})
        manifest["updatedAt"] = timestamp()
        manifest["cardShards"] = sorted(path.stem for path in (DATA / "cards").glob("*.json"))
        manifest["publishedCardCount"] = sum(len(load(path, {})) for path in (DATA / "cards").glob("*.json"))
        save(manifest_path, manifest)

    try:
        for _, card_id, urls in pending:
            reason = "Not found"
            for url in urls[:2]:
                wait = args.delay - (time.monotonic() - last_request)
                if wait > 0: time.sleep(wait)
                last_request = time.monotonic()
                try:
                    record = parse(fetch(url, args.timeout), card_id, url)
                    old = shards[shard(card_id)].get(card_id, {})
                    if old.get("reviewStatus") == "verified":
                        record = old  # never overwrite a manually reviewed entry
                    elif old != record:
                        shards[shard(card_id)][card_id] = record
                        changed += 1
                    status[card_id] = {"status": "ok", "checkedAt": timestamp(), "url": url}
                    print("OK", card_id)
                    reason = ""
                    break
                except urllib.error.HTTPError as e:
                    reason = "HTTP " + str(e.code)
                    if e.code == 429 or e.code >= 500: blocked = True; break
                except (urllib.error.URLError, TimeoutError, OSError) as e:
                    reason = type(e).__name__
                    blocked = True
                    break
                except (ValueError, UnicodeError) as e:
                    reason = str(e)[:110]
            if reason:
                status[card_id] = {"status": "failed", "checkedAt": timestamp(), "reason": reason}
                print("MISS", card_id, reason)
            persist()  # checkpoint each card
            if blocked:
                print("STOP: upstream throttling / network failure", file=sys.stderr)
                return 2
    finally:
        persist()
    print("Changed:", changed)
    return 0

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--delay", type=float, default=6.0)
    p.add_argument("--timeout", type=int, default=12)
    p.add_argument("--recheck-days", type=int, default=45)
    p.add_argument("--card", type=str)
    p.add_argument("--force", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    sys.exit(sync(p.parse_args()))
