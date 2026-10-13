#!/usr/bin/env python3
"""Merge a Tampermonkey exported local cache into static GitHub JSON shards."""
import argparse
import datetime as dt
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
FIELDS = ("name", "form", "attribute", "types", "main", "inherited", "security", "variant")

def shard(card_id):
    if re.fullmatch(r"(?:P|LM)-\d{3}", card_id):
        return card_id.split("-")[0]
    match = re.fullmatch(r"((?:BT|EX|ST|AD|RB))(\d{1,2})-\d{2,3}", card_id)
    if not match: raise ValueError("Invalid card ID " + card_id)
    return match.group(1) + str(int(match.group(2)))

def run(args):
    source = json.loads(Path(args.export_file).read_text(encoding="utf-8-sig"))
    if source.get("schemaVersion") != 1 or not isinstance(source.get("cards"), dict):
        raise ValueError('Expected {"schemaVersion": 1, "cards": { ... }}')
    shards = {}
    skipped = []
    for card_id, value in source["cards"].items():
        try:
            name = shard(card_id)
            if not isinstance(value, dict) or value.get("cardId", card_id) != card_id:
                raise ValueError("card identity mismatch")
            record = {"cardId": card_id}
            for field in FIELDS:
                field_value = value.get(field, "")
                if not isinstance(field_value, str) or len(field_value) > (9000 if field in ("main", "inherited", "security") else 150):
                    raise ValueError("invalid " + field)
                if field_value: record[field] = field_value
            if not any(record.get(k) for k in ("main", "inherited", "security")):
                raise ValueError("missing card effects")
            url = value.get("url") or value.get("sourceUrl", "")
            u = urlsplit(url)
            if u.scheme != "https" or u.hostname != "app.digicamoe.cn" or f"/{card_id}/" not in u.path:
                raise ValueError("invalid DigiCamoe link")
            record["url"] = url
            shards.setdefault(name, {})[card_id] = record
        except (ValueError, TypeError) as e:
            skipped.append(f"{card_id}: {e}")
    for name, records in shards.items():
        path = DATA / "cards" / (name + ".json")
        previous = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        if args.keep_existing:
            previous = {**records, **previous}
        else:
            previous.update(records)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(dict(sorted(previous.items())), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest_path = DATA / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["updatedAt"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest["cardShards"] = sorted(path.stem for path in (DATA / "cards").glob("*.json"))
    manifest["publishedCardCount"] = sum(len(json.loads(p.read_text(encoding="utf-8"))) for p in (DATA / "cards").glob("*.json"))
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Imported", sum(map(len, shards.values())), "records; skipped", len(skipped))
    for item in skipped[:15]: print("SKIP", item)

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("export_file")
    p.add_argument("--keep-existing", action="store_true")
    run(p.parse_args())
