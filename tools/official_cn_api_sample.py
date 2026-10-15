#!/usr/bin/env python3
"""One-time request for 2 public CN card records to inspect official API schema.

Backend and path were observed in official frontend JS. Logs keys and printed
card numbers only (not bulk text / artwork). Do not turn into a large crawler.
"""
import json
import urllib.parse
import urllib.request

BASE = "https://dtcgweb-api.digimoncard.cn/gamecard/gamecardmanager/weblist"
PARAMS = {"page": 1, "limit": 2, "state": 0}
URL = BASE + "?" + urllib.parse.urlencode(PARAMS)
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AegisChineseCommunity/0.1)",
           "Accept": "application/json, text/plain, */*",
           "Origin": "https://www.digimoncard.cn",
           "Referer": "https://www.digimoncard.cn/cardlist"}


def run():
    with urllib.request.urlopen(urllib.request.Request(URL, headers=HEADERS), timeout=18) as resp:
        raw = resp.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError("Small sample response over size cap")
        obj = json.loads(raw)
        print("HTTP", resp.status, "content-type", resp.headers.get("content-type", ""))
    print("TOP", sorted(obj) if isinstance(obj, dict) else type(obj).__name__)
    print("API code", obj.get("code"), "message available", bool(obj.get("msg")))
    pg = obj.get("page", {}) if isinstance(obj, dict) else {}
    print("PAGE", {k:v for k,v in pg.items() if k not in ("list", "records", "items", "data")})
    cards = pg.get("list", []) if isinstance(pg, dict) else []
    print("RECORDS", len(cards))
    for item in cards[:2]:
        if not isinstance(item, dict):
            print("ROW NOT A DICT", type(item).__name__)
            continue
        print("ROW KEYS", sorted(item))
        only_ids = ("cardNo","cardNumber","cardNum","cardCode","number","id",
                    "cardGroup","gamecardNumber","cardId","cardNoStr")
        print("ID FIELDS", {k:str(item[k])[:70] for k in only_ids if k in item})
    return 0


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print("API SAMPLE FAILED", type(exc).__name__, str(exc)[:200])
