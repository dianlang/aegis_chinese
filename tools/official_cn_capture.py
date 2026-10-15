#!/usr/bin/env python3
"""Record public JSON card records loaded by the official Chinese cardlist UI.

Uses an ordinary Chromium browser and its own public page requests. It does
not guess private endpoints, log in, collect cookies/tokens, or crawl hidden
URLs. Interact with the cardlist search UI yourself while it records results.
Outputs stay under local_data/ and MUST NOT be published without permission.
Python 3.9+. Optional dependency: pip install playwright; playwright install chromium.
"""
import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

OFFICIAL_PAGE = "https://www.digimoncard.cn/cardlist"
HOSTS = {"digimoncard.cn", "www.digimoncard.cn"}
ID_KEYS = (
    "cardNo", "cardNO", "cardNum", "cardNumber", "card_number",
    "cardCode", "card_code", "cardId", "card_id", "cardid",
    "number", "code", "卡牌编号", "卡号", "编号",
)
CARD_NO = re.compile(r"^(?:BT|EX|ST|AD|RB|BTC|EXC|STC|LM|P)-?\d{1,3}-\d{2,3}$|^(?:P|LM)-\d{3}$", re.I)


def candidate_number(value):
    if not isinstance(value, str):
        return ""
    value = value.strip().upper().replace("—", "-").replace("－", "-")
    return value if CARD_NO.fullmatch(value) else ""


def collect_cards(payload, limit=500):
    """Only extract individual card dictionaries with an explicit printed ID."""
    found = []
    seen = set()
    def visit(obj, depth=0):
        if depth > 12 or len(found) >= limit:
            return
        if isinstance(obj, dict):
            number = next((candidate_number(obj.get(key)) for key in ID_KEYS
                           if candidate_number(obj.get(key))), "")
            if number:
                safe = {key: value for key, value in obj.items()
                        if isinstance(value, (str, int, float, bool, list, dict, type(None)))
                        and key.lower() not in {"cookie", "token", "authorization", "session", "password"}}
                identifier = number + ":" + json.dumps(safe, ensure_ascii=False, sort_keys=True)[:200]
                if identifier not in seen:
                    found.append(safe)
                    seen.add(identifier)
                return
            for value in obj.values():
                visit(value, depth+1)
        elif isinstance(obj, list):
            for value in obj:
                visit(value, depth+1)
    visit(payload)
    return found


def capture(page_url=OFFICIAL_PAGE, path="local_data/official_cn_capture.json", seconds=0):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Install optional browser tools: py -3 -m pip install playwright")
        print("Then: py -3 -m playwright install chromium")
        return 2
    result = []
    seen = set()
    diagnostics = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        def response_handler(response):
            parsed = urlsplit(response.url)
            if (parsed.hostname not in HOSTS or response.status != 200
                    or response.request.resource_type not in ("xhr", "fetch")):
                return
            if "json" not in response.headers.get("content-type", "").lower():
                return
            try:
                body = response.body()
                if len(body) > 4_000_000:
                    return
                payload = json.loads(body)
                candidates = collect_cards(payload)
                for row in candidates:
                    key = json.dumps(row, ensure_ascii=False, sort_keys=True)
                    if key not in seen:
                        result.append({"payload": row, "requestPath": parsed.path})
                        seen.add(key)
                if candidates:
                    print("OFFICIAL JSON", parsed.path, "+", len(candidates),
                          "records, total", len(result), flush=True)
                elif len(diagnostics) < 30:
                    diagnostics.append({"path": parsed.path,
                                        "type": type(payload).__name__,
                                        "keys": list(payload)[:25] if isinstance(payload, dict) else []})
            except Exception as exc:
                print("SKIP response", parsed.path, type(exc).__name__, flush=True)
        page.on("response", response_handler)
        try:
            page.goto(page_url, wait_until="domcontentloaded", timeout=30000)
        except Exception as exc:
            print("Page load issue:", type(exc).__name__, str(exc)[:120], file=sys.stderr)
        print("Official cardlist is open. Use filters/search/pagination in this browser.")
        print("Return to this terminal and press Enter to save what the site returned.")
        try:
            input()
        except EOFError:
            pass
        # Browser events complete during networkidle/brief read without extra page requests.
        try:
            page.wait_for_load_state("networkidle", timeout=4000)
        except Exception:
            pass
        browser.close()
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "schemaVersion": 1,
        "captureMethod": "official-public-ui-json",
        "capturedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "origin": OFFICIAL_PAGE,
        "cards": result,
        "diagnostics": diagnostics,
    }
    dest.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("CAPTURE", len(result), "card printings saved to", dest, flush=True)
    if not result:
        print("No card records recognized. See diagnostics in saved file; send it for API field mapping.")
    return 0


if __name__ == "__main__":
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--output", default="local_data/official_cn_capture.json")
    args = a.parse_args()
    sys.exit(capture(path=args.output))
