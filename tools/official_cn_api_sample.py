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
        print("CARD KEYS FOR MATCHING", {
            k: str(item[k])[:85] for k in ("model","name","belongsType","getWayStr",
                                           "rareDegree","cardGroup","imageCover")
            if k in item})
    if cards and isinstance(cards[0], dict) and isinstance(cards[0].get("id"), int):
        detail_url = "https://dtcgweb-api.digimoncard.cn/gamecard/gamecardmanager/webInfo/" + str(cards[0]["id"])
        with urllib.request.urlopen(urllib.request.Request(detail_url,headers=HEADERS),timeout=18) as resp:
            raw=resp.read(1_000_001)
            if len(raw)>1_000_000:
                raise ValueError("Detail response over 1 MB cap")
            detail=json.loads(raw)
            info=detail.get("gamecardManager", {})
            print("DETAIL", resp.status, "top keys", sorted(detail),
                  "card keys", sorted(info) if isinstance(info,dict) else type(info).__name__)
            if isinstance(info,dict):
                print("DETAIL CARD NUMBER FIELDS", {
                    k:str(info[k])[:85] for k in ("id","model","cardNo","cardNumber","name","cardGroup")
                    if k in info})
    return 0


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print("API SAMPLE FAILED", type(exc).__name__, str(exc)[:200])
