#!/usr/bin/env python3
"""Offline Chinese card coverage by set, with deduplicated IDs and CSV missing list."""
import argparse
import csv
import datetime as dt
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

try:
    from .sync_cards import DATA, load, save, shard
except ImportError:
    from sync_cards import DATA, load, save, shard


def snapshot(data):
    data = Path(data)
    indexed = {}
    for path in sorted((data / "index").glob("*.json")):
        for cid, urls in load(path, {}).get("cards", {}).items():
            if urls:
                current = indexed.setdefault(cid, [])
                for url in urls:
                    if url not in current:
                        current.append(url)
    cards = {}
    for path in sorted((data / "cards").glob("*.json")):
        cards.update(load(path, {}))
    state = load(data / "sync-state.json", {"cards": {}}).get("cards", {})
    return indexed, cards, state


def has_chinese_effect(card):
    return any(re.search(r"[\u3400-\u9fff]", card.get(field, ""))
               for field in ("main", "inherited", "security"))


def package_order(name):
    match = re.fullmatch(r"([A-Z]+)(\d+)?", name)
    return (match.group(1), int(match.group(2) or 0)) if match else (name, 0)


def report(indexed, cards, state):
    groups = defaultdict(list)
    for cid in indexed:
        groups[shard(cid)].append(cid)
    per_pack = []
    missing = []
    for pack, ids in sorted(groups.items(), key=lambda item: package_order(item[0])):
        ids = sorted(set(ids))
        stored = [cid for cid in ids if cid in cards]
        effects = [cid for cid in stored if has_chinese_effect(cards[cid])]
        verified = [cid for cid in stored if cards[cid].get("reviewStatus") == "verified"]
        for cid in ids:
            if cid not in cards:
                info = state.get(cid, {})
                missing.append({"cardId": cid, "pack": pack, "status": info.get("status", "not_attempted"),
                                "reason": info.get("reason", "")})
        per_pack.append({
            "pack": pack, "indexed": len(ids), "stored": len(stored),
            "chineseEffect": len(effects), "metadataOnly": len(stored)-len(effects),
            "verified": len(verified), "missing": len(ids)-len(stored),
            "storedPercent": round(100*len(stored)/len(ids), 2),
            "effectPercent": round(100*len(effects)/len(ids), 2)
        })
    indexed_count = len(indexed)
    stored_count = len(set(cards) & set(indexed))
    effect_count = sum(1 for cid in indexed if cid in cards and has_chinese_effect(cards[cid]))
    totals = {
        "indexed": indexed_count, "stored": stored_count, "chineseEffect": effect_count,
        "metadataOnly": stored_count-effect_count, "missing": indexed_count-stored_count,
        "unindexedStored": len(set(cards) - set(indexed)),
        "storedPercent": round(100*stored_count/indexed_count, 2) if indexed_count else 0,
        "effectPercent": round(100*effect_count/indexed_count, 2) if indexed_count else 0
    }
    return {"schemaVersion": 1, "totals": totals, "packs": per_pack}, missing


def to_markdown(data, missing):
    t = data["totals"]
    lines = [
        "# Aegis 中文卡牌数据库覆盖率",
        "",
        "> 按卡号去重。建立索引不代表卡文入库；有中文卡文也不代表游戏弹窗一定匹配成功。",
        "",
        "索引：**%d** 张；已存储：**%d** 张（%.2f%%）；含中文效果：**%d** 张（%.2f%%）；"
        "仅元数据：**%d** 张；缺失：**%d** 张。" % (
            t["indexed"], t["stored"], t["storedPercent"], t["chineseEffect"],
            t["effectPercent"], t["metadataOnly"], t["missing"]),
        "",
        "| 卡包 | 索引 | 已存储 | 有中文效果 | 仅元数据 | 缺失 | 效果覆盖率 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in data["packs"]:
        lines.append("| %(pack)s | %(indexed)d | %(stored)d | %(chineseEffect)d | "
                     "%(metadataOnly)d | %(missing)d | %(effectPercent)s%% |" % r)
    lines.extend(["", "## 缺失状态", ""])
    for status, count in sorted(Counter(item["status"] for item in missing).items()):
        lines.append("- %s：%d 张" % (status, count))
    lines += ["", "缺失卡号及抓取原因见 reports/coverage_missing.csv。",
              "此报告纯本地计算，不向 DigiCamoe 发送请求。", ""]
    return "\n".join(lines)


def generate(data=DATA, output="data/coverage.json", markdown="reports/COVERAGE.md",
             missing_csv="reports/coverage_missing.csv"):
    index, cards, states = snapshot(data)
    summary, missing = report(index, cards, states)
    summary["updatedAt"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if output:
        save(Path(output), summary)
    if markdown:
        target = Path(markdown)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(to_markdown(summary, missing), encoding="utf-8")
    if missing_csv:
        target = Path(missing_csv)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=["cardId", "pack", "status", "reason"])
            writer.writeheader()
            writer.writerows(missing)
    print("COVERAGE", json.dumps(summary["totals"], ensure_ascii=False), flush=True)
    return summary, missing


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-dir", default=str(DATA))
    p.add_argument("--output", default="data/coverage.json")
    p.add_argument("--markdown", default="reports/COVERAGE.md")
    p.add_argument("--missing-csv", default="reports/coverage_missing.csv")
    a = p.parse_args()
    generate(a.data_dir, a.output, a.markdown, a.missing_csv)


if __name__ == "__main__":
    main()
