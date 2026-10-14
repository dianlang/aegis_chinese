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
        assert any(value.get(field) for field in ("main", "inherited", "security")) or (
            value.get("cardType") and any(field in value for field in ("level", "dp", "playCost", "useCost"))
        )
        for field in ("name", "japaneseName", "cardType", "rarity", "color", "form", "attribute", "types", "main", "inherited", "security"):
            if field in value:
                assert isinstance(value[field], str) and len(value[field]) <= 9000
        for field in ("level", "dp", "playCost", "useCost"):
            if field in value:
                assert type(value[field]) is int and 0 <= value[field] <= 100000
        if "parserVersion" in value:
            assert type(value["parserVersion"]) is int and value["parserVersion"] >= 1
        if "colors" in value:
            assert isinstance(value["colors"], list) and len(value["colors"]) <= 4
            assert all(isinstance(c, str) and 0 < len(c) <= 20 for c in value["colors"])
        if "digivolutionConditions" in value:
            assert isinstance(value["digivolutionConditions"], list) and len(value["digivolutionConditions"]) <= 12
            assert all(isinstance(v, str) and 0 < len(v) <= 300 for v in value["digivolutionConditions"])
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
