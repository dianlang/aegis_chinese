#!/usr/bin/env python3
"""Validate card data and P link index; no network access."""
import json
import re
from pathlib import Path
from urllib.parse import urlsplit
DATA = Path(__file__).resolve().parents[1] / "data"
manifest = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
assert manifest["schemaVersion"] == 1
total = 0
for f in (DATA / "cards").glob("*.json"):
    records = json.loads(f.read_text(encoding="utf-8"))
    assert isinstance(records, dict) and len(records) <= 600
    for card_id, value in records.items():
        assert isinstance(value, dict) and value.get("cardId") == card_id
        assert bool(re.fullmatch(r"(?:P|LM)-\d{3}|(?:BT|EX|ST|AD|RB)\d{1,2}-\d{2,3}", card_id))
        assert any(value.get(field) for field in ("main", "inherited", "security"))
        for field in ("name", "form", "attribute", "types", "main", "inherited", "security"):
            if field in value:
                assert isinstance(value[field], str) and len(value[field]) <= 9000
        u = urlsplit(value.get("url", ""))
        assert u.scheme == "https" and u.hostname == "app.digicamoe.cn"
        assert f"/{card_id}/" in u.path
        total += 1
for f in (DATA / "index").glob("*.json"):
    indexes = json.loads(f.read_text(encoding="utf-8"))
    assert indexes.get("version") == 1
    for card_id, urls in indexes["cards"].items():
        assert urls and isinstance(urls, list)
        for url in urls:
            u = urlsplit(url)
            assert u.scheme == "https" and u.hostname == "app.digicamoe.cn"
            assert f"/{card_id}/" in u.path
assert set(manifest.get("cardShards", [])) == {p.stem for p in (DATA / "cards").glob("*.json")}
assert manifest.get("publishedCardCount") == total
print("Validated", total, "Chinese cards")
