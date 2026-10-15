#!/usr/bin/env python3
"""Offline authorized JSON/CSV -> data/cards/*.json importer (Python 3.9+).

Dry-run by default. Never infers a DigiCamoe URL; uses only indexed real links
or an existing valid card link. Card references and translation provenance are
recorded separately. Does not overwrite manually verified card texts.
"""
import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

try:
    from .sync_cards import DATA, load, save, shard, timestamp, indexed_cards
except ImportError:
    from sync_cards import DATA, load, save, shard, timestamp, indexed_cards

CARD_ID = re.compile(r"^(?:P|LM)-\d{3}$|^(?:BT|EX|ST|AD|RB)\d{1,2}-\d{2,3}$")
CHINESE = re.compile(r"[\u3400-\u9fff]")
ALIASES = {
    "cardId": ("model", "cardId", "card_id", "cardNo", "cardNO", "cardNumber", "card_no", "card_num", "cardCode", "id", "卡号", "编号", "卡牌编号", "card_number", "number"),
    "name": ("name", "cardName", "card_name", "卡名", "卡牌名称", "名称", "中文名"),
    "main": ("main", "effect", "text", "mainEffect", "cardEffect", "card_effect", "效果", "能力", "卡牌效果", "主效果"),
    "inherited": ("envolutionEffect", "inherited", "inheritedEffect", "inherited_effect", "evolutionEffect", "进化源效果", "进化源能力"),
    "security": ("safeEffect", "security", "securityEffect", "security_effect", "安防效果", "安防能力"),
    "japaneseName": ("japaneseName", "japanese_name", "日文名", "日文名称"),
    "cardType": ("belongsType", "cardType", "card_type", "卡片类型", "卡种"),
    "rarity": ("rareDegree", "rarity", "罕贵度", "稀有度"),
    "color": ("color", "颜色"),
    "form": ("form", "形态"),
    "attribute": ("attribute", "属性"),
    "types": ("type", "types", "类型", "种族"),
    "level": ("cardLevel", "level", "lv", "LV", "等级"),
    "playCost": ("playCost", "登场费用"),
    "useCost": ("useCost", "使用费用"),
    "dp": ("dp", "DP"),
}
TEXT_FIELDS = {"name", "main", "inherited", "security", "japaneseName",
               "cardType", "rarity", "color", "form", "attribute", "types"}
EFFECT_FIELDS = ("main", "inherited", "security")
NUM_FIELDS = {"level", "playCost", "useCost", "dp"}


def read_input(path, encoding="utf-8-sig"):
    path = Path(path)
    if path.suffix.lower() == ".csv":
        with path.open(encoding=encoding, newline="") as handle:
            return list(csv.DictReader(handle))
    if path.suffix.lower() != ".json":
        raise ValueError("Only .json or .csv is supported")
    source = json.loads(path.read_text(encoding=encoding))
    if isinstance(source, list):
        return source
    if isinstance(source, dict):
        records = source.get("cards", source.get("records", source))
        if isinstance(records, list):
            return records
        if isinstance(records, dict):
            result = []
            for identifier, record in records.items():
                if not isinstance(record, dict):
                    result.append({"cardId": identifier, "_invalid": True})
                else:
                    if record.get("cardId") and record["cardId"] != identifier:
                        result.append({"cardId": identifier, "_invalid": True})
                    else:
                        result.append({"cardId": identifier, **record})
            return result
    raise ValueError("Expect a JSON list, cardId keyed map, or {'cards': list/map}")


def mappings(mapping_file=None):
    names = {name: list(aliases) for name, aliases in ALIASES.items()}
    if mapping_file:
        custom = json.loads(Path(mapping_file).read_text(encoding="utf-8-sig"))
        if not isinstance(custom, dict):
            raise ValueError("Mapping JSON must be an object")
        for name, aliases in custom.items():
            if name not in names or not isinstance(aliases, (str, list)):
                raise ValueError("Unknown field or invalid mapping: " + str(name))
            values = [aliases] if isinstance(aliases, str) else aliases
            if not values or not all(isinstance(v, str) and v for v in values):
                raise ValueError("Invalid aliases for " + name)
            names[name] = values + names[name]
    return names


def normalize(raw, aliases):
    if not isinstance(raw, dict) or raw.get("_invalid"):
        raise ValueError("Invalid record object")
    row = {str(key).strip(): value for key, value in raw.items()}
    obj = {}
    for name, candidates in aliases.items():
        value = next((row[key] for key in candidates
                      if key in row and row[key] is not None and str(row[key]).strip()), None)
        if value is None:
            continue
        if name in NUM_FIELDS:
            number = str(value).strip()
            if not number.isdecimal():
                raise ValueError("Invalid integer for " + name)
            obj[name] = int(number)
            if not 0 <= obj[name] <= 100000:
                raise ValueError("Out of range " + name)
        elif isinstance(value, (str, int, float)):
            text = str(value).strip()
            if len(text) > (9000 if name in EFFECT_FIELDS else 150):
                raise ValueError("Value too long for " + name)
            if text:
                obj[name] = text.replace("\r\n", "\n")
        else:
            raise ValueError("Invalid value type for " + name)
    identifier = obj.get("cardId", "").upper()
    if not CARD_ID.fullmatch(identifier):
        raise ValueError("Missing or invalid card ID: " + repr(identifier))
    obj["cardId"] = identifier
    if not obj.get("name"):
        raise ValueError("Missing Chinese card name")
    if not CHINESE.search(obj["name"]):
        raise ValueError("Card name is not Chinese")
    effects = [obj.get(key, "") for key in EFFECT_FIELDS if obj.get(key)]
    if effects:
        if not CHINESE.search("".join(effects)):
            raise ValueError("Card effects do not contain Chinese")
    elif not (obj.get("cardType") and any(field in obj for field in NUM_FIELDS)):
        raise ValueError("No Chinese effect or sufficient printed vanilla-card metadata")
    shard(identifier)
    return obj


def url_is_valid(url, identifier):
    parts = urlsplit(url)
    return (parts.scheme == "https" and parts.netloc == "app.digicamoe.cn"
            and f"/{identifier}/" in parts.path and not parts.query and not parts.fragment)


def preview_or_import(records, index, data_dir, source_label, apply=False,
                      overwrite=False, mapping=None):
    """Two phases: validate all rows, then apply writes only if every row is valid."""
    aliases = mappings(mapping)
    accepted, errors = {}, []
    duplicates = 0
    for line, row in enumerate(records, start=1):
        try:
            item = normalize(row, aliases)
            identifier = item["cardId"]
            if identifier in accepted:
                if item != accepted[identifier]:
                    raise ValueError("Conflicting duplicate card number: " + identifier)
                duplicates += 1
                continue
            accepted[identifier] = item
        except (ValueError, TypeError) as exc:
            errors.append(f"row {line}: {exc}")
    data_dir = Path(data_dir)
    existing = {}
    for path in (data_dir / "cards").glob("*.json"):
        existing[path.stem] = load(path, {})
    stats = Counter()
    changed = {}
    for identifier, item in sorted(accepted.items()):
        group = shard(identifier)
        previous = existing.get(group, {}).get(identifier, {})
        if previous.get("reviewStatus") == "verified":
            stats["verified_protected"] += 1
            continue
        urls = index.get(identifier, [])
        candidate = previous.get("url", "")
        if not url_is_valid(candidate, identifier):
            candidate = next((u for u in urls if url_is_valid(u, identifier)), "")
        if not candidate:
            errors.append(f"{identifier}: no existing indexed DigiCamoe reference URL")
            continue
        # The URL is a card reference, not an assertion that DigiCamoe
        # authored the input translation. Provenance is the explicit label.
        merged = dict(previous)
        merged["cardId"] = identifier
        merged["url"] = candidate
        merged["translationSource"] = source_label
        for key, value in item.items():
            if key != "cardId" and (overwrite or not merged.get(key)):
                merged[key] = value
        if merged == previous:
            stats["unchanged"] += 1
            continue
        if previous and not overwrite:
            # Do not overwrite previously recorded translation provenance if
            # existing effect/name fields were kept as-is.
            if all(previous.get(k) == merged.get(k) for k in ("name",) + EFFECT_FIELDS):
                if previous.get("translationSource"):
                    merged["translationSource"] = previous["translationSource"]
                elif any(previous.get(k) for k in EFFECT_FIELDS):
                    merged.pop("translationSource", None)
        if merged == previous:
            stats["unchanged"] += 1
            continue
        changed.setdefault(group, {})[identifier] = merged
        stats["updated"] += bool(previous)
        stats["new"] += not bool(previous)
    stats["duplicate_identical"] = duplicates
    stats["records"] = len(records)
    stats["valid_unique"] = len(accepted)
    stats["errors"] = len(errors)
    if apply and not errors:
        for group, rows in changed.items():
            path = data_dir / "cards" / (group + ".json")
            old = load(path, {})
            old.update(rows)
            save(path, dict(sorted(old.items())))
        manifest_file = data_dir / "manifest.json"
        manifest = load(manifest_file, {"schemaVersion": 1})
        manifest["updatedAt"] = timestamp()
        manifest["cardShards"] = sorted(path.stem for path in (data_dir / "cards").glob("*.json"))
        manifest["publishedCardCount"] = sum(len(load(path, {}))
                                             for path in (data_dir / "cards").glob("*.json"))
        save(manifest_file, manifest)
    return dict(stats), errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_file")
    parser.add_argument("--source-label", required=True,
                        help="The authorized dataset's actual provenance, e.g. DigiCamoe-licensed-2026")
    parser.add_argument("--mapping", help="Optional JSON object of output field -> input column name(s)")
    parser.add_argument("--encoding", default="utf-8-sig", help="e.g. gb18030 for legacy CSV")
    parser.add_argument("--apply", action="store_true", help="Actually write data; default is dry-run")
    parser.add_argument("--permission-confirmed", action="store_true",
                        help="Confirm authorization for GitHub redistributing these texts")
    parser.add_argument("--overwrite-unverified", action="store_true",
                        help="Replace existing non-verified translations instead of filling blanks")
    args = parser.parse_args(argv)
    if args.apply and not args.permission_confirmed:
        parser.error("--apply requires --permission-confirmed; obtain data-use permission first")
    try:
        records = read_input(args.input_file, args.encoding)
        if not records:
            raise ValueError("Input is empty")
        stats, errors = preview_or_import(records, indexed_cards(), DATA,
                                          args.source_label, args.apply,
                                          args.overwrite_unverified, args.mapping)
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        print("IMPORT ERROR:", exc, file=sys.stderr)
        return 2
    print("IMPORT", "applied" if args.apply and not errors else "preview",
          json.dumps(stats, ensure_ascii=False))
    for error in errors[:30]:
        print("REJECT", error, file=sys.stderr)
    if errors:
        print("No database files written; fix errors then rerun.", file=sys.stderr)
        return 2
    if not args.apply:
        print("Dry run only. Add --apply --permission-confirmed once licensed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
