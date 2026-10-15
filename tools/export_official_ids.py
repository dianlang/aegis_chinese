#!/usr/bin/env python3
"""Publish only non-textual official CN card-number metadata (no card effects).

Requires local_data/official_cn_capture.json produced from the genuine official
API. Outputs verified model -> Aegis/JP map with official internal IDs and CN
pack SKUs, while raw names/effects stay in gitignored local_data/.
"""
import argparse
import datetime as dt
import json
from collections import defaultdict
from pathlib import Path

try:
    from .align_official_cards import printed_no, aegis_ids, indexed_ids
    from .sync_cards import save
except ImportError:
    from align_official_cards import printed_no, aegis_ids, indexed_ids
    from sync_cards import save

SOURCE = Path(__file__).resolve().parents[1] / "local_data" / "official_cn_capture.json"
OUTPUT = Path(__file__).resolve().parents[1] / "data" / "mapping" / "official_cn_ids.json"


def export_ids(raw, indexed, aegis):
    groups = defaultdict(lambda: {"recordIds": set(), "cnPacks": set(), "count": 0})
    invalid = 0
    for entry in raw:
        if not isinstance(entry, dict):
            invalid += 1
            continue
        cid = printed_no(entry.get("model", ""))
        if not cid:
            invalid += 1
            continue
        item = groups[cid]
        official_id = entry.get("id")
        if isinstance(official_id, int) and official_id >= 0:
            item["recordIds"].add(official_id)
        cn_pack = entry.get("cardGroup")
        if isinstance(cn_pack, str) and len(cn_pack) <= 64:
            item["cnPacks"].add(cn_pack)
        item["count"] += 1
    rows = {}
    statuses = {}
    for cid, x in sorted(groups.items()):
        in_aegis = cid in aegis
        in_index = cid in indexed
        status = ("three_way_matched" if in_aegis and in_index else
                  "cn_aegis_no_jp_index" if in_aegis else "cn_not_in_aegis")
        statuses[status] = statuses.get(status, 0) + 1
        rows[cid] = {
            "cnCardNo": cid,
            "japaneseCardNo": cid if in_index else None,
            "aegisCardId": cid if in_aegis else None,
            "officialRecordIds": sorted(x["recordIds"]),
            "cnProductCodes": sorted(x["cnPacks"]),
            "printingCount": x["count"],
            "matchStatus": status
        }
    return {
        "schemaVersion": 1,
        "source": "https://dtcgweb-api.digimoncard.cn/gamecard/gamecardmanager/weblist",
        "updatedAt": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "summary": {
            "totalOfficialRows": len(raw),
            "uniqueOfficialPrintedCards": len(rows),
            "validPrintedRows": len(raw) - invalid,
            "invalidRows": invalid,
            "existingJapaneseIndexCards": len(indexed),
            "aegisCards": len(aegis),
            "matchingCounts": statuses
        },
        "cards": rows
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=str(SOURCE))
    parser.add_argument("--output", default=str(OUTPUT))
    options = parser.parse_args()
    raw = json.loads(Path(options.input).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("records"), list):
        raise ValueError("Expected official capture JSON with records list")
    result = export_ids(raw["records"], indexed_ids(), aegis_ids())
    save(Path(options.output), result)
    print("OFFICIAL ID MAP", json.dumps(result["summary"], ensure_ascii=False), flush=True)
    print("Only IDs, pack codes and statuses were exported; no card names, text, image URLs or cookies.")


if __name__ == "__main__":
    main()
