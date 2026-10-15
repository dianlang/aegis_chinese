#!/usr/bin/env python3
"""Bounded one-time static inspection of already-observed official cardlist JS module.

No card requests or bulk fetch. Prints short JS contexts around cardlist query
execution so an adapter can be written against actual observed names.
"""
import re
import urllib.request

LINK = "https://www.digimoncard.cn/static/js/chunk-39d13e45.80a95c7f.js"
req = urllib.request.Request(LINK, headers={"User-Agent": "AegisChineseCommunityAPIResearch/0.1"})
with urllib.request.urlopen(req, timeout=15) as resp:
    data = resp.read(300_000).decode("utf-8", "replace")
print("Cardlist JS bytes", len(data))
for needle in ("this.queryParams=e.page", "methods:{", "queryParams:{", "E.", "P.", "queryCard", "getCard", "this.get"):
    offset = 0
    printed = 0
    while printed < 3:
        pos = data.find(needle, offset)
        if pos < 0:
            break
        start, end = max(0, pos - 230), min(len(data), pos + 400)
        excerpt = data[start:end].replace("\n", " ")
        excerpt = re.sub(r"(?i)(token|password|authorization).{0,30}", "[redacted]", excerpt)
        print("NEAR", needle, pos, excerpt)
        offset = pos + len(needle)
        printed += 1
print("Done, no API endpoint called.")
