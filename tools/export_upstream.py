#!/usr/bin/env python3
"""Generate a reviewable, upstream-compatible Aegis zh-CN.ts and unified diff."""
import argparse
import difflib
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = "apps/web/src/i18n/zh-CN.ts"
SOURCE = "https://raw.githubusercontent.com/vinicius3333/aegis-digimon-tcg/develop/" + TARGET
LINE = re.compile(r'^(\s*)"([^"\\]+)":\s*("(?:\\.|[^"\\])*")(,?)(\s*)$', re.M)
PLACEHOLDER = re.compile(r"\{[A-Za-z_][A-Za-z0-9_]*\}")

def generate(source_file):
    overrides = json.loads((ROOT / "data" / "ui-overrides.json").read_text(encoding="utf-8"))
    if source_file:
        original = Path(source_file).read_text(encoding="utf-8")
    else:
        request = urllib.request.Request(SOURCE, headers={"User-Agent": "AegisChineseCommunity/0.3"})
        with urllib.request.urlopen(request, timeout=20) as response:
            original = response.read().decode("utf-8")
    missing = set(overrides)
    modified = set()

    def replace(m):
        indent, key, quoted, comma, end = m.groups()
        if key not in overrides: return m.group(0)
        old, new = json.loads(quoted), overrides[key]
        if not isinstance(new, str): raise ValueError(key + ": expected string")
        if set(PLACEHOLDER.findall(old)) != set(PLACEHOLDER.findall(new)):
            raise ValueError(key + ": dynamic placeholder mismatch")
        missing.discard(key)
        if old != new:
            modified.add(key)
            return indent + json.dumps(key, ensure_ascii=False) + ": " + json.dumps(new, ensure_ascii=False) + comma + end
        return m.group(0)

    patched = LINE.sub(replace, original)
    if missing:
        raise ValueError("Missing or nonliteral upstream translation keys: " + ", ".join(sorted(missing)))
    output_dir = ROOT / "dist" / "upstream"
    file = output_dir / TARGET
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(patched, encoding="utf-8")
    diff = "".join(difflib.unified_diff(original.splitlines(keepends=True), patched.splitlines(keepends=True),
        fromfile="a/" + TARGET, tofile="b/" + TARGET))
    (output_dir / "zh-CN.patch").write_text(diff, encoding="utf-8")
    (output_dir / "README_PR.md").write_text(
        "# UI localization pull request\n\n"
        "Target: vinicius3333/aegis-digimon-tcg, branch develop.\n\n"
        "Review the modified file and submit it through your fork after upstream tests.\n"
        "This patch changes ONLY Chinese interface strings; it does not copy "
        "DigiCamoe card effects into the Aegis source tree.\n", encoding="utf-8")
    print(f"Updated {len(modified)} keys. Output: {file}")

if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--source", help="Offline path to official zh-CN.ts")
    args = cli.parse_args()
    generate(args.source)
