#!/usr/bin/env python3
"""Merge a completed GitHub Actions data checkpoint with the newest main branch.

This tool only works on card/metadata JSON within data/. It never touches
translation source code, workflows, or authentication.
"""
import argparse
import json
from pathlib import Path
from datetime import datetime, timezone


def load(path, fallback):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return fallback


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if not path.exists() or path.read_text(encoding="utf-8") != serialized:
        path.write_text(serialized, encoding="utf-8")


def merge_card_records(remote, harvested, remote_status, harvested_status):
    merged = dict(remote)
    for card_id, card in harvested.items():
        current = merged.get(card_id)
        if current is None:
            merged[card_id] = card
            continue
        if current.get("reviewStatus") == "verified":
            continue
        if card.get("reviewStatus") == "verified":
            merged[card_id] = card
            continue
        old_when = remote_status.get(card_id, {}).get("checkedAt", "")
        new_when = harvested_status.get(card_id, {}).get("checkedAt", "")
        if new_when >= old_when:
            # Prefer an equal/newer harvested version, retaining existing
            # metadata fields not extracted by an older parser.
            merged[card_id] = {**current, **card}
    return merged


def merge_index(remote, harvested):
    out = dict(remote)
    out["version"] = remote.get("version", harvested.get("version", 1))
    cards = {k: list(v) for k, v in remote.get("cards", {}).items()}
    for card_id, urls in harvested.get("cards", {}).items():
        entries = cards.setdefault(card_id, [])
        for url in urls:
            if url not in entries:
                entries.append(url)
    out["cards"] = dict(sorted(cards.items()))
    out["finished"] = bool(remote.get("finished") and harvested.get("finished"))
    return out


def merge_state(remote, harvested):
    out = dict(remote)
    for key in ("scanned", "cards"):
        if key in harvested or key in remote:
            new = dict(remote.get(key, {}))
            for name, record in harvested.get(key, {}).items():
                existing = new.get(name, {})
                if record.get("checkedAt", "") >= existing.get("checkedAt", ""):
                    new[name] = record
            out[key] = new
    out["errors"] = {**harvested.get("errors", {}), **remote.get("errors", {})}
    for name in out.get("scanned", {}):
        out.get("errors", {}).pop(name, None)
    out["catalogPackages"] = max(remote.get("catalogPackages", 0), harvested.get("catalogPackages", 0))
    out["lastCatalogueAt"] = max(remote.get("lastCatalogueAt", ""), harvested.get("lastCatalogueAt", ""))
    return out


def merge(captured_dir, data_dir):
    captured_dir, data_dir = Path(captured_dir), Path(data_dir)
    remote_status = load(data_dir / "sync-state.json", {"version": 1, "cards": {}})
    harvested_status = load(captured_dir / "sync-state.json", {"version": 1, "cards": {}})
    for captured in sorted((captured_dir / "cards").glob("*.json")):
        remote = data_dir / "cards" / captured.name
        merged = merge_card_records(load(remote, {}), load(captured, {}),
                                    remote_status.get("cards", {}),
                                    harvested_status.get("cards", {}))
        save(remote, merged)

    for captured in sorted((captured_dir / "index").glob("*.json")):
        remote = data_dir / "index" / captured.name
        save(remote, merge_index(load(remote, {}), load(captured, {})))

    save(data_dir / "sync-state.json", merge_state(remote_status, harvested_status))
    save(data_dir / "index-state.json",
         merge_state(load(data_dir / "index-state.json", {"version": 1}),
                     load(captured_dir / "index-state.json", {"version": 1})))

    current_config = load(data_dir / "bootstrap.json", {})
    harvested_config = load(captured_dir / "bootstrap.json", {})
    if current_config.get("enabled") and harvested_config.get("enabled") is False:
        current_config["enabled"] = False
        save(data_dir / "bootstrap.json", current_config)

    manifest_path = data_dir / "manifest.json"
    manifest = load(manifest_path, {"schemaVersion": 1})
    manifest["updatedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest["cardShards"] = sorted(p.stem for p in (data_dir / "cards").glob("*.json"))
    manifest["publishedCardCount"] = sum(len(load(p, {})) for p in (data_dir / "cards").glob("*.json"))
    manifest["note"] = "Incremental Chinese card database; checkpoint merged with latest remote data"
    save(manifest_path, manifest)
    print("Merged checkpoint:", manifest["publishedCardCount"], "published cards", flush=True)
    return manifest["publishedCardCount"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("captured_directory", help="Path to a saved copy of data/")
    parser.add_argument("--destination", default="data")
    args = parser.parse_args()
    merge(args.captured_directory, args.destination)
