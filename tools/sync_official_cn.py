#!/usr/bin/env python3
"""Official CN card-list incremental sync to LOCAL, gitignored staging only.

The endpoint/method/fields were verified from the site's own public frontend:
GET https://dtcgweb-api.digimoncard.cn/gamecard/gamecardmanager/weblist
query page,limit,state=0; page.list, each card: model, id, cardGroup.

By default downloads at most three pages with global >=3s spacing. --full
allows a complete local snapshot with 4s+ spacing, checkpoints and resume.
No token/cookie, no guessed endpoints, no images and NO automatic public push.
The official Chinese text's redistribution permission must be verified first.
"""
import argparse
import datetime as dt
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

try:
    from .align_official_cards import align, aegis_ids, indexed_ids, write_alignment, printed_no
except ImportError:
    from align_official_cards import align, aegis_ids, indexed_ids, write_alignment, printed_no

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "local_data"
URL = "https://dtcgweb-api.digimoncard.cn/gamecard/gamecardmanager/weblist"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AegisChineseCommunity/0.1)",
    "Accept": "application/json,text/plain,*/*",
    "Origin": "https://www.digimoncard.cn",
    "Referer": "https://www.digimoncard.cn/cardlist"
}


def fetch_page(page, limit=40, timeout=15):
    if not (1 <= page <= 250 and 1 <= limit <= 40):
        raise ValueError("Page/size outside reviewed official frontend bounds")
    params = {"page": page, "limit": limit, "state": 0}
    url = URL + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=timeout) as reply:
        if urllib.parse.urlsplit(reply.url).hostname != "dtcgweb-api.digimoncard.cn":
            raise ValueError("Unexpected API redirect")
        data = reply.read(4_000_001)
        if len(data) > 4_000_000:
            raise ValueError("One page exceeded response cap")
        payload = json.loads(data)
    if not isinstance(payload, dict) or payload.get("code") not in (0, 200, None):
        raise ValueError("API did not return success code")
    data_page = payload.get("page", {})
    if not isinstance(data_page, dict) or not isinstance(data_page.get("list"), list):
        raise ValueError("Missing expected API page.list")
    return {
        "requestedPage": page,
        "totalPages": int(data_page.get("totalPage", 0)),
        "totalCount": int(data_page.get("totalCount", 0)),
        "returnedPage": data_page.get("currPage"),
        "records": data_page["list"],
    }


def page_signature(page):
    recs = page.get("records", [])
    if not recs:
        return None
    return (len(recs), str(recs[0].get("id", "")), str(recs[0].get("model", "")),
            str(recs[-1].get("id", "")), str(recs[-1].get("model", "")))


def checkpoint_path(directory, page):
    return Path(directory) / ("page_%04d.json" % page)


def save_local(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    os.replace(str(tmp), str(path))


def load_pages(directory):
    pages = []
    for path in sorted(Path(directory).glob("page_*.json")):
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if (isinstance(obj, dict) and isinstance(obj.get("records"), list)
                and isinstance(obj.get("requestedPage"), int)):
            pages.append(obj)
    return pages


def publish_local_snapshot(directory, output_root=STORE):
    pages = load_pages(directory)
    rows = []
    seen = set()
    duplicates = 0
    for page in pages:
        for item in page["records"]:
            if not isinstance(item, dict):
                continue
            raw_id = item.get("id")
            key = str(raw_id) if raw_id is not None else json.dumps(item, sort_keys=True)
            if key in seen:
                duplicates += 1
                continue
            seen.add(key)
            rows.append(item)

    output_root = Path(output_root)
    save_local(output_root / "official_cn_capture.json", {
        "schemaVersion": 1,
        "source": URL, "capturedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "records": rows
    })
    result = align(rows, indexed_ids(), aegis_ids())
    write_alignment(result, output_root / "official_alignment.json",
                    output_root / "official_alignment.csv")
    print("OFFICIAL CN STAGING", "downloaded_records", len(rows),
          "duplicate_server_ids", duplicates, "complete_pages", len(pages),
          "three_way_matched", result["summary"]["threeWayMatched"],
          "missing_cn", result["summary"]["awaitingOfficialCN"],
          "invalid_rows", result["summary"]["invalidOfficialRows"], flush=True)
    return result


def sync(max_pages=3, limit=40, interval=4.0, timeout=15,
         time_budget_minutes=60, directory=STORE / "official_cn_pages", full=False):
    if not (1 <= max_pages <= 250 and limit == 40 and interval >= 3
            and 5 <= timeout <= 25 and 1 <= time_budget_minutes <= 120):
        raise ValueError("Safety limits: max 250 pages, 40 cards/page, >=3 seconds/request")
    if not full and max_pages > 5:
        raise ValueError("Bulk mode requires explicit --full")
    folder = Path(directory)
    folder.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + time_budget_minutes * 60
    last_request = 0.0
    seen_pages = {}
    errors = []
    done = 0
    try:
        for number in range(1, max_pages + 1):
            path = checkpoint_path(folder, number)
            if path.exists():
                page = json.loads(path.read_text(encoding="utf-8"))
                print("CACHE", number, "records", len(page.get("records", [])), flush=True)
            else:
                if time.monotonic() > deadline - timeout - 5:
                    print("STOP: time budget reached; saved local checkpoints")
                    break
                since = time.monotonic() - last_request
                if since < interval:
                    time.sleep(interval - since)
                last_request = time.monotonic()
                try:
                    page = fetch_page(number, limit, timeout)
                except urllib.error.HTTPError as exc:
                    if exc.code == 429:
                        print("STOP: official API rate limit 429; do not retry immediately")
                        errors.append("HTTP 429")
                        break
                    if exc.code >= 500:
                        print("STOP: official API service unavailable HTTP", exc.code,
                              "; no aggressive retry", flush=True)
                        errors.append("HTTP " + str(exc.code))
                        break
                    errors.append("HTTP " + str(exc.code))
                    print("STOP: HTTP", exc.code, flush=True)
                    break
                except (urllib.error.URLError, OSError, TimeoutError, ValueError) as exc:
                    msg = type(exc).__name__ + ": " + str(exc)[:120]
                    print("STOP: official API request interrupted", msg, flush=True)
                    errors.append(msg)
                    break
                save_local(path, page)

            key = page_signature(page)
            if key and key in seen_pages and seen_pages[key] != number:
                print("STOP: API returned duplicate page; verify pagination parameters",
                      seen_pages[key], number, flush=True)
                errors.append("Duplicate pagination response")
                break
            if key:
                seen_pages[key] = number
            records = page.get("records", [])
            valid_numbers = sum(bool(printed_no(rec.get("model"))) for rec in records
                                if isinstance(rec, dict))
            print("PAGE", number, "records", len(records),
                  "printed_numbers", valid_numbers,
                  "server_total", page.get("totalCount"), flush=True)
            done += 1
            if not records or len(records) < limit:
                print("Reached final partially-filled page.", flush=True)
                break
            if page.get("totalPages") and number >= page["totalPages"]:
                print("Reached API-reported final page.", flush=True)
                break
    finally:
        result = publish_local_snapshot(folder, folder.parent)
    if errors:
        print("STOPPED WITH ERROR:", errors[-1], "; local results preserved", flush=True)
        return 2
    print("Finished this batch; local data not committed to GitHub.", flush=True)
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--full", action="store_true", help="Opt in to bounded bulk snapshot")
    p.add_argument("--max-pages", type=int, default=None)
    p.add_argument("--interval", type=float, default=4.0)
    p.add_argument("--timeout", type=int, default=15)
    p.add_argument("--time-budget-minutes", type=int, default=60)
    p.add_argument("--directory", default=str(STORE / "official_cn_pages"))
    args = p.parse_args(argv)
    count = args.max_pages if args.max_pages is not None else (250 if args.full else 3)
    try:
        return sync(max_pages=count, interval=args.interval, timeout=args.timeout,
                    time_budget_minutes=args.time_budget_minutes,
                    directory=args.directory, full=args.full)
    except (OSError, ValueError) as exc:
        print("Official CN sync error:", str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
