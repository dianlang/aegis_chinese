#!/usr/bin/env python3
"""Fail-closed three-ID crosswalk for official CN printings, JP IDs and Aegis.

No network access unless --fetch-aegis was explicitly requested. It never
writes to the public card database: only files in local_data/. Only exact
normalized original card numbers auto-match. CN reprint series (BTC, EXC,
STC) require a reviewer-confirmed CSV mapping. Never align by suffix alone.
"""
import argparse
import csv
import json
import re
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

from official_cn_capture import CARD_NO, ID_KEYS, candidate_number

AEGIS_URL = (
    "https://raw.githubusercontent.com/vinicius3333/aegis-digimon-tcg/"
    "develop/packages/shared/src/cards/data/cards.json"
)
JP = re.compile(r"^(BT|EX|ST|AD|RB)-?(\d{1,2})-(\d{2,3})$|^(P|LM)-(\d{3})$", re.I)
REPRINT = re.compile(r"^(?:BTC|EXC|STC)-?\d{1,3}-\d{2,3}$", re.I)
MATCH_LABELS = ("cardNo", "cardNO", "cardNum", "cardNumber", "card_number",
                "cardCode", "card_code", "cardId", "card_id", "cardid",
                "number", "code", "卡牌编号", "卡号", "编号")


def normalize_jp(raw):
    if not isinstance(raw, str):
        return ""
    value = raw.strip().upper().replace("—", "-").replace("－", "-")
    m = JP.fullmatch(value)
    if not m:
        return ""
    if m.group(4):
        return m.group(4) + "-" + m.group(5)
    return m.group(1) + str(int(m.group(2))) + "-" + m.group(3)


def get_cn_number(row):
    if not isinstance(row, dict):
        return ""
    return next((n for k in MATCH_LABELS
                 if (n := candidate_number(row.get(k)))), "")


def collect_index(data_dir):
    all_ids = set()
    for path in (Path(data_dir) / "index").glob("*.json"):
        all_ids.update(json.loads(path.read_text(encoding="utf-8")).get("cards", {}))
    return all_ids


def load_aegis(path, fetch=False):
    dest = Path(path)
    if fetch:
        dest.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(AEGIS_URL, headers={
            "User-Agent": "AegisChineseCommunity/1.0"})
        with urllib.request.urlopen(req, timeout=40) as response:
            blob = response.read(5_500_001)
            if len(blob) > 5_500_000:
                raise ValueError("Aegis catalog unexpectedly large")
        doc = json.loads(blob)
        if not isinstance(doc, list):
            raise ValueError("Unexpected Aegis card JSON schema")
        dest.write_bytes(blob)
    if not dest.is_file():
        raise ValueError("Aegis cards.json unavailable. Pass --fetch-aegis once, or --aegis-json PATH")
    data = json.loads(dest.read_text(encoding="utf-8-sig"))
    if not isinstance(data, list):
        raise ValueError("Expected Aegis cards.json array")
    records = {}
    for obj in data:
        if not isinstance(obj, dict) or not isinstance(obj.get("cardId"), str):
            raise ValueError("Malformed Aegis card catalog")
        identifier = obj["cardId"]
        if identifier in records:
            raise ValueError("Duplicate Aegis card ID: " + identifier)
        records[identifier] = obj
    return records


def manual_map(path):
    mapping = {}
    if not path:
        return mapping
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            printed = candidate_number(row.get("chineseCardId", ""))
            jp = normalize_jp(row.get("japaneseCardId", ""))
            aegis = normalize_jp(row.get("aegisCardId", ""))
            approval = str(row.get("reviewed", "")).strip().lower()
            if (not printed or not jp or not aegis or jp != aegis
                    or approval not in ("yes", "true", "1", "verified")):
                raise ValueError("Invalid/unreviewed explicit mapping for " + repr(row))
            if printed in mapping and mapping[printed] != (jp, aegis):
                raise ValueError("Conflicting mappings for " + printed)
            mapping[printed] = (jp, aegis)
    return mapping


def pick(row, keys):
    for key in keys:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def translated_fields(row):
    return {
        "name": pick(row, ("name", "cardName", "card_name", "cardCnName", "cnName", "卡名", "名称")),
        "main": pick(row, ("effect", "mainEffect", "effectText", "main", "能力", "效果", "主效果")),
        "inherited": pick(row, ("inherited", "inheritedEffect", "inheritedEffectText",
                               "进化源能力", "进化源效果")),
        "security": pick(row, ("security", "securityEffect", "securityEffectText",
                              "安防能力", "安防效果")),
    }


def compatible(row, aegis):
    """Hard reject known contradictions; don't translate/guess English names."""
    for k in ("level", "dp", "playCost"):
        value = row.get(k)
        target = aegis.get(k)
        if value is None or target is None or value == "":
            continue
        try:
            if int(value) != int(target):
                return False, k + " differs"
        except (ValueError, TypeError):
            return False, k + " invalid"
    return True, ""


def align(document, indexed, aegis, overrides=None):
    overrides = overrides or {}
    raw_records = document.get("cards", []) if isinstance(document, dict) else document
    if not isinstance(raw_records, list):
        raise ValueError("Captured data has no cards array")
    crosswalk = {}
    rows = []
    export_by_jp = defaultdict(list)
    for item in raw_records:
        raw = item.get("payload", item) if isinstance(item, dict) else None
        printed = get_cn_number(raw)
        if not printed:
            rows.append({"chineseCardId": "", "japaneseCardId": "",
                         "aegisCardId": "", "status": "no_cn_number", "note": "No printed number"})
            continue
        verified_manual = printed in overrides
        if verified_manual:
            jp, aegis_id = overrides[printed]
            basis = "reviewed_mapping"
        else:
            jp = normalize_jp(printed)
            aegis_id = jp
            basis = "exact_original_id" if jp else "no_original_id"
        status, note = "aligned", basis
        if not jp:
            status, note = "manual_mapping_required", "Chinese reprint number cannot be inferred"
        elif jp != aegis_id:
            status, note = "conflict", "Aegis and JP IDs disagree"
        elif jp not in indexed:
            status, note = "not_in_existing_index", "No matching DigiCamoe original ID"
        elif aegis_id not in aegis:
            status, note = "not_in_aegis", "No Aegis catalog card"
        elif not compatible(raw, aegis[aegis_id])[0]:
            status, note = "conflict", compatible(raw, aegis[aegis_id])[1]
        elif (printed in crosswalk and crosswalk[printed] != aegis_id):
            status, note = "conflict", "same Chinese print maps to another Aegis card"
        else:
            crosswalk[printed] = aegis_id
        output = {"chineseCardId": printed, "japaneseCardId": jp, "aegisCardId": aegis_id,
                  "status": status, "note": note}
        rows.append(output)
        if status == "aligned":
            translation = translated_fields(raw)
            if translation["name"] and any(translation.values()):
                export_by_jp[jp].append(translation)

    imports = []
    multi = []
    for jp, translations in sorted(export_by_jp.items()):
        # Multiple CN printings may be the same original card; only export
        # if all have precisely the same Chinese name and effect fields.
        signatures = {tuple(x.get(k, "") for k in ("name", "main", "inherited", "security"))
                      for x in translations}
        if len(signatures) != 1:
            multi.append(jp)
            for row in rows:
                if row["aegisCardId"] == jp and row["status"] == "aligned":
                    row["status"] = "conflicting_printings"
                    row["note"] = "Multiple official printings disagree; manual review"
            continue
        record = {"cardId": jp, **translations[0]}
        imports.append(record)
    return rows, imports, multi


def run(capture, output, review_csv, import_preview, index_dir,
        aegis_json, fetch_aegis=False, manual_csv=None):
    doc = json.loads(Path(capture).read_text(encoding="utf-8-sig"))
    indexed = collect_index(index_dir)
    if not indexed:
        raise ValueError("No existing card indexes in " + str(index_dir))
    aegis = load_aegis(aegis_json, fetch=fetch_aegis)
    overrides = manual_map(manual_csv)
    rows, converted, multi = align(doc, indexed, aegis, overrides)
    for target in (output, review_csv, import_preview):
        Path(target).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(json.dumps({"schemaVersion": 1, "crosswalk": rows},
                                       ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with Path(review_csv).open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=[
            "chineseCardId", "japaneseCardId", "aegisCardId", "status", "note"])
        writer.writeheader()
        writer.writerows(rows)
    Path(import_preview).write_text(json.dumps({"cards": converted}, ensure_ascii=False,
                                                indent=2) + "\n", encoding="utf-8")
    statuses = {}
    for item in rows:
        statuses[item["status"]] = statuses.get(item["status"], 0) + 1
    print("OFFICIAL CN CROSSWALK:", json.dumps(statuses, ensure_ascii=False))
    print("Aegis known card IDs", len(aegis), "DigiCamoe indexed", len(indexed),
          "import-ready unique original cards", len(converted),
          "conflicting printings", len(multi))
    print("Results:", output, review_csv, import_preview)
    print("Staging only: nothing added to public data/cards and NO redistribution rights assumed")
    return 0


def main():
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--capture", default="local_data/official_cn_capture.json")
    a.add_argument("--aegis-json", default="local_data/aegis_cards.json")
    a.add_argument("--fetch-aegis", action="store_true")
    a.add_argument("--mapping", help="CSV with verified chineseCardId, japaneseCardId, aegisCardId, reviewed")
    a.add_argument("--index-dir", default="data")
    a.add_argument("--output", default="local_data/official_cn_alignment.json")
    a.add_argument("--review-csv", default="local_data/official_cn_review.csv")
    a.add_argument("--import-preview", default="local_data/official_cn_import_preview.json")
    opts = a.parse_args()
    try:
        return run(opts.capture, opts.output, opts.review_csv,
                   opts.import_preview, opts.index_dir,
                   opts.aegis_json, opts.fetch_aegis, opts.mapping)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print("ALIGN ERROR:", exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
