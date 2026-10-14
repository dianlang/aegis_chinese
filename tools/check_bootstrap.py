#!/usr/bin/env python3
"""Disable bulk bootstrap only after a broad index and mostly completed card collection."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
config_file = DATA / "bootstrap.json"
config = json.loads(config_file.read_text(encoding="utf-8"))
if not config.get("enabled"):
    print("Bootstrap already completed / disabled")
    raise SystemExit(0)
indexed = set()
for f in (DATA / "index").glob("*.json"):
    obj = json.loads(f.read_text(encoding="utf-8"))
    indexed.update(obj.get("cards", {}))
published = set()
for f in (DATA / "cards").glob("*.json"):
    published.update(json.loads(f.read_text(encoding="utf-8")))
minimum = config.get("minimumIndexedCards", 4000)
target_fraction = config.get("completionFraction", 0.95)
coverage = len(published & indexed) / max(len(indexed), 1)
print(f"Bootstrap progress: indexed={len(indexed)}, published={len(published & indexed)}, coverage={coverage:.1%}")
index_state_path = DATA / "index-state.json"
index_state = json.loads(index_state_path.read_text(encoding="utf-8")) if index_state_path.exists() else {}
all_packages_scanned = (
    index_state.get("catalogPackages", 0) > 0
    and len(index_state.get("scanned", {})) >= index_state.get("catalogPackages")
    and not index_state.get("errors", {})
)
print("Indexed package coverage:", len(index_state.get("scanned", {})),
      "/", index_state.get("catalogPackages", "?"), "complete:", all_packages_scanned)
if all_packages_scanned and len(indexed) >= minimum and coverage >= target_fraction:
    config["enabled"] = False
    config_file.write_text(json.dumps(config,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Bootstrap completed. Switching to 20-card daily maintenance.")
else:
    print("Bulk bootstrap stays active.")
