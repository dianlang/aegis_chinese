#!/usr/bin/env python3
"""Conservative 3-way Japanese / official-CN / Aegis card-number reconciliation.

Only the actual printed card number (not Chinese pack code BTC-01) may connect
records. Different artworks/printings for the same printed number stay grouped.
Does not download, publish or infer card texts or manufacture mappings.
"""
import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

try:
    from .sync_cards import DATA, load, shard
except ImportError:
    from sync_cards import DATA, load, shard

ROOT = Path(__file__).resolve().parents[1]
PRINTED = re.compile(r"^(?:(?:BT|EX|ST|AD|RB)\d{1,2}-\d{2,3}|(?:P|LM)-\d{3})$")
SOURCE_FIELDS = ("cardNo", "cardNO", "cardno", "cardNumber", "card_number",
                 "cardNoStr", "cardCode", "card_code", "card_num", "cardNum",
                 "number", "编号", "卡号", "卡牌编号", "cardId", "card_id", "id")
PACK_FIELDS = ("pack", "packCode", "packName", "package", "packageName",
               "pack_code", "productCode", "productName", "卡包", "收录商品", "商品")
NAME_FIELDS = ("name", "cardName", "card_name", "cardNameCn", "cnName", "中文名",
               "卡名", "名称")
NESTED_KEYS = ("cards", "cardList", "cardlist", "cardData", "list",
               "records", "rows", "items", "data", "result", "content", "page")

def printed_no(value):
    """Accept only printed identifiers; pack SKU names and Aegis DB keys differ."""
    if not isinstance(value, (str, int)):
        return ""
    text = str(value).strip().upper()
    text = text.replace("－", "-").replace("–", "-").replace("—", "-").replace(" ", "")
    if text.startswith("NO."):
        text = text[3:]
    return text if PRINTED.fullmatch(text) else ""


def field(row, names):
    if not isinstance(row, dict):
        return ""
    for name in names:
        value = row.get(name)
        if value is not None and isinstance(value, (str, int, float)) and str(value).strip():
            return str(value).strip()
    return ""


def rows_in(payload, depth=0):
    """Extract only card-like objects from known result/list wrappers."""
    if depth > 7:
        return
    if isinstance(payload, list):
        for item in payload:
            yield from rows_in(item, depth + 1)
    elif isinstance(payload, dict):
        if any(name in payload for name in SOURCE_FIELDS) and (
            any(name in payload for name in NAME_FIELDS)
            or any(k in payload for k in ("effect", "mainEffect", "cardType", "type", "image", "imageUrl"))
        ):
            yield payload
            return
        for name in NESTED_KEYS:
            if name in payload:
                yield from rows_in(payload[name], depth + 1)


def read_official(path):
    if not path:
        return []
    path = Path(path)
    if path.suffix.lower() == ".csv":
        with path.open(newline="", encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    return list(rows_in(payload))


def indexed_ids(data_dir=DATA):
    idx = {}
    for path in sorted((Path(data_dir) / "index").glob("*.json")):
        for cid, urls in load(path, {}).get("cards", {}).items():
            if urls and printed_no(cid):
                idx.setdefault(cid, [])
                for url in urls:
                    if url not in idx[cid]:
                        idx[cid].append(url)
    return idx


def aegis_ids(aegis_file=None, data_dir=DATA):
    path = Path(aegis_file) if aegis_file else Path(data_dir) / "mapping" / "aegis_cards.json"
    obj = load(path, {})
    return set(obj.get("aegisCardIds", []))


def align(official, indexed, aegis):
    grouped = defaultdict(list)
    invalid = []
    for pos, raw in enumerate(official, 1):
        card = printed_no(field(raw, SOURCE_FIELDS))
        if not card:
            invalid.append({"row": pos,
                            "candidate": field(raw, SOURCE_FIELDS)[:80],
                            "reason": "missing_or_non_card_printed_number"})
            continue
        grouped[card].append({
            "cnCardNo": card,
            "cnPack": field(raw, PACK_FIELDS),
            "cnName": field(raw, NAME_FIELDS)
        })
    all_ids = sorted(set(aegis) | set(indexed) | set(grouped))
    matched, missing, mismatched = [], [], []
    records = []
    for cid in all_ids:
        jp = cid if cid in indexed else None
        aegis_id = cid if cid in aegis else None
        cn = grouped.get(cid, [])
        if jp and aegis_id and cn:
            status = "three_way_matched"
        elif jp and aegis_id:
            status = "awaiting_cn_record"
        elif cn and not aegis_id:
            status = "cn_not_in_aegis"
        elif aegis_id and not jp:
            status = "aegis_not_in_jp_index" if not cn else "cn_aegis_no_jp_index"
        else:
            status = "needs_manual_review"
        variants = sorted(set((entry["cnPack"], entry["cnName"]) for entry in cn))
        row = {
            "cardId": cid,
            "jpCardNo": jp,
            "cnCardNo": cid if cn else None,
            "aegisCardId": aegis_id,
            "status": status,
            "cnPrintCount": len(cn),
            "cnPackCodes": sorted({item["cnPack"] for item in cn if item["cnPack"]}),
            "cnNames": sorted({item["cnName"] for item in cn if item["cnName"]}),
            "jpIndexedUrlCount": len(indexed.get(cid, []))
        }
        records.append(row)
        if status == "three_way_matched":
            matched.append(cid)
        elif status == "awaiting_cn_record":
            missing.append(cid)
        else:
            mismatched.append(cid)
    return {"summary": {
        "indexedJapaneseCards": len(indexed),
        "aegisCards": len(aegis),
        "officialRowsAccepted": sum(len(v) for v in grouped.values()),
        "officialUniquePrintedNumbers": len(grouped),
        "threeWayMatched": len(matched),
        "awaitingOfficialCN": len(missing),
        "needsReview": len(mismatched),
        "invalidOfficialRows": len(invalid)
    }, "cards": records, "invalidOfficialRows": invalid}


def write_alignment(result, json_path, csv_path):
    path = Path(json_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    path = Path(csv_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        fields = ["cardId", "jpCardNo", "cnCardNo", "aegisCardId", "status",
                  "cnPrintCount", "cnPackCodes", "cnNames", "jpIndexedUrlCount"]
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for row in result["cards"]:
            writer.writerow({**row,
                             "cnPackCodes": " | ".join(row["cnPackCodes"]),
                             "cnNames": " | ".join(row["cnNames"])})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--official-json", help="Captured official card JSON/CSV; optional")
    parser.add_argument("--aegis-index", default=str(DATA / "mapping" / "aegis_cards.json"))
    parser.add_argument("--output", default="reports/official_alignment.json")
    parser.add_argument("--csv", default="reports/official_alignment.csv")
    args = parser.parse_args()
    source = read_official(args.official_json)
    result = align(source, indexed_ids(), aegis_ids(args.aegis_index))
    write_alignment(result, args.output, args.csv)
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
