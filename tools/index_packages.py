#!/usr/bin/env python3
"""Discover actual card-detail links from DigiCamoe package pages; checkpointed and rate-limited."""
import argparse
import datetime as dt
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urljoin, urlsplit, unquote

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
URL_BASE = "https://app.digicamoe.cn"
CATALOG = URL_BASE + "/package"
STATE_FILE = DATA / "index-state.json"
INDEX_FILE = DATA / "index" / "AUTO.json"
AGENT = {"User-Agent": "AegisChineseCommunity/0.3 (+https://github.com/dianlang/aegis_chinese)",
         "Accept": "text/html"}
CARD_ID = re.compile(r"^(?:(?:BT|EX|ST|AD|RB)\d{1,2}-\d{2,3}|(?:P|LM)-\d{3})$")
PACK_PATH = re.compile(r"^/[Pp]ackage/([^/?#]+?)/?$")
CARD_PATH = re.compile(r"^/[Cc]ards/([^/]+)/([^/]+)/([^/]+)/?$")
PRIMARY = re.compile(r"^(?:BT-\d+|EX-\d+|ST-\d+|AD-\d+|RB-\d+|LM-\d+)(?:CN)?$", re.I)

def now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def read(path, fallback):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else fallback

def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if not path.exists() or path.read_text(encoding="utf-8") != serialized:
        path.write_text(serialized, encoding="utf-8")

def allowed(url):
    parts = urlsplit(url)
    return parts.scheme == "https" and parts.netloc.lower() == "app.digicamoe.cn" and not parts.query and not parts.fragment

def list_packs(html):
    packs = set()
    doc = BeautifulSoup(html, "html.parser")
    for tag in doc.select("a[href]"):
        url = urljoin(CATALOG, tag["href"])
        if allowed(url):
            match = PACK_PATH.fullmatch(urlsplit(url).path)
            if match:
                packs.add(unquote(match.group(1)))
    return sorted(packs, key=lambda x: (0 if PRIMARY.fullmatch(x) else 1, x))

def list_cards(html, pack):
    result = {}
    doc = BeautifulSoup(html, "html.parser")
    for tag in doc.select("a[href]"):
        url = urljoin(URL_BASE + "/Package/" + pack, tag["href"])
        if not allowed(url):
            continue
        match = CARD_PATH.fullmatch(urlsplit(url).path)
        if not match or match.group(1).lower() != pack.lower():
            continue
        card_id = unquote(match.group(2)).upper()
        if not CARD_ID.fullmatch(card_id):
            continue
        result.setdefault(card_id, [])
        if url not in result[card_id]:
            result[card_id].append(url)
    return result

def fetch(url, timeout):
    req = urllib.request.Request(url, headers=AGENT)
    with urllib.request.urlopen(req, timeout=timeout) as reply:
        data = reply.read(5_000_001)
        if len(data) > 5_000_000:
            raise ValueError("Oversized package HTML")
        return data.decode("utf-8", "replace")

def discover(limit=175, delay=6, timeout=15, dry_run=False):
    if limit < 1 or limit > 200 or delay < 5:
        raise ValueError("Safety limits: 1..200 package pages per run, delay >= 5s")
    state = read(STATE_FILE, {"version": 1, "scanned": {}, "errors": {}})
    index = read(INDEX_FILE, {"version": 1, "cards": {}, "source": "DigiCamoe package listings"})
    index.setdefault("cards", {})
    limiter = [0.0]
    def paced_request(url):
        wait = delay - (time.monotonic() - limiter[0])
        if wait > 0:
            time.sleep(wait)
        limiter[0] = time.monotonic()
        return fetch(url, timeout)
    try:
        packs = list_packs(paced_request(CATALOG))
    except Exception as exc:
        print("STOP: could not read package catalogue:", str(exc)[:150], file=sys.stderr)
        return 2
    pending = [pack for pack in packs if pack not in state.get("scanned", {})]
    # A previous 404 is not retried repeatedly, but can be cleared manually in index-state.json.
    pending = [pack for pack in pending if pack not in state.get("errors", {})]
    pending = pending[:limit]
    print("Catalogue packages:", len(packs), "Already scanned:", len(state["scanned"]),
          "To check:", len(pending), "Dry run:", dry_run, flush=True)
    if dry_run:
        print("\n".join(pending))
        return 0
    for pack in pending:
        try:
            cards = list_cards(paced_request(URL_BASE + "/Package/" + pack), pack)
            if not cards:
                raise ValueError("No card-detail URLs in package page")
            for cid, urls in cards.items():
                existing = index["cards"].setdefault(cid, [])
                for url in urls:
                    if url not in existing:
                        existing.append(url)
            state["scanned"][pack] = {"count": len(cards), "checkedAt": now()}
            state["errors"].pop(pack, None)
            print("INDEX", pack, len(cards), flush=True)
        except urllib.error.HTTPError as exc:
            if exc.code == 429 or exc.code >= 500:
                print("STOP: upstream HTTP", exc.code, flush=True)
                write(INDEX_FILE, index); write(STATE_FILE, state)
                return 2
            state["errors"][pack] = "HTTP " + str(exc.code)
            print("SKIP", pack, exc.code, flush=True)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            print("STOP: connection failure", pack, type(exc).__name__, flush=True)
            write(INDEX_FILE, index); write(STATE_FILE, state)
            return 2
        except ValueError as exc:
            state["errors"][pack] = str(exc)[:100]
            print("SKIP", pack, str(exc)[:100], flush=True)
        write(INDEX_FILE, index)
        write(STATE_FILE, state)
    print("Indexed distinct card IDs:", len(index["cards"]), flush=True)
    return 0

if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--limit", type=int, default=175)
    cli.add_argument("--delay", type=float, default=6)
    cli.add_argument("--timeout", type=int, default=15)
    cli.add_argument("--dry-run", action="store_true")
    args = cli.parse_args()
    sys.exit(discover(args.limit, args.delay, args.timeout, args.dry_run))
