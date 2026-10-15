#!/usr/bin/env python3
"""One-time bounded static lookup of webpack module cb4b used by official card list.

Searches the official page's explicitly referenced JS assets only. Does not
call any backend card API. Prints limited excerpts of identified module.
"""
from html.parser import HTMLParser
import re
import sys
import time
import urllib.request
from urllib.parse import urljoin, urlsplit

BASE = "https://www.digimoncard.cn/cardlist"
HOST = {"digimoncard.cn", "www.digimoncard.cn"}
MODULE_ID = "cb4b"

def fetch(url, cap=4_000_000):
    p = urlsplit(url)
    if p.scheme != "https" or p.hostname not in HOST:
        raise ValueError("Not official host")
    req = urllib.request.Request(url, headers={"User-Agent":"AegisChineseCommunityAPIResearch/0.1"})
    with urllib.request.urlopen(req, timeout=16) as response:
        if urlsplit(response.url).hostname not in HOST:
            raise ValueError("External redirect")
        data = response.read(cap + 1)
        if len(data) > cap:
            raise ValueError("Asset exceeds cap")
        return data.decode("utf-8", "replace")

class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.js = []
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        v = a.get("src") if tag == "script" else a.get("href") if tag == "link" else None
        if v:
            u = urljoin(BASE, v)
            if urlsplit(u).hostname in HOST and urlsplit(u).path.endswith(".js"):
                self.js.append(u)

def main():
    markup = fetch(BASE, 300_000)
    parser = Assets()
    parser.feed(markup)
    paths = list(dict.fromkeys(parser.js))
    print("Searching webpack module", MODULE_ID, "in", len(paths), "official JS assets", flush=True)
    for n, link in enumerate(paths[:45], 1):
        try:
            data = fetch(link)
        except Exception as e:
            print("SKIP", n, type(e).__name__, str(e)[:90], flush=True)
            continue
        token = re.search(r"""(?:["']cb4b["']|(?<![a-zA-Z0-9])cb4b)\s*:\s*function\s*\(""", data)
        print("ASSET", n, urlsplit(link).path, "bytes", len(data),
              "module_match", bool(token), flush=True)
        if token:
            start = token.start()
            segment = data[start:start+3500]
            for needle in ("gamecard", "Gamecard", "/gamecard", "/card", "axios", "request", "getGamecard", "/api"):
                where = segment.find(needle)
                if where >= 0:
                    print("API_MODULE_NEAR", needle,
                          segment[max(0,where-150):where+230].replace("\n"," ")[:400],
                          flush=True)
            print("MODULE_START", segment[:1800].replace("\n"," "),flush=True)
            print("Found actual JS module; inspect it before forming any endpoint call.")
            return 0
        time.sleep(.5)
    print("Not found in static prefetched assets; use observed browser requests instead.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
