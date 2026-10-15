#!/usr/bin/env python3
"""One-time low-volume public frontend JavaScript API-discovery probe (not a card scraper).

Only touches official website HTML + at most 4 site-hosted script assets.
Never tries guessed endpoints, authentication, or card download. Prints only
candidate API paths and asset names, not script contents or credentials.
"""
import html.parser
import re
import sys
import urllib.request
from urllib.parse import urljoin, urlsplit

BASE = "https://www.digimoncard.cn/cardlist"
HEADERS = {"User-Agent": "AegisChineseCommunityAPIResearch/0.1",
           "Accept": "text/html,application/javascript,*/*"}
HOSTS = {"digimoncard.cn", "www.digimoncard.cn"}


def allowed(link):
    p = urlsplit(link)
    return p.scheme == "https" and p.hostname in HOSTS and not p.username and not p.password


def limited_read(link, byte_limit=2_500_000):
    if not allowed(link):
        raise ValueError("Disallowed host")
    req = urllib.request.Request(link, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=18) as resp:
        if not allowed(resp.url):
            raise ValueError("Redirect to outside host")
        data = resp.read(byte_limit + 1)
        if len(data) > byte_limit:
            raise ValueError("Asset exceeds size cap")
        return data.decode("utf-8", "replace")


class Scripts(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = []
        self.prefetch = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        source = attrs.get("src") if tag.lower() == "script" else (
            attrs.get("href") if tag.lower() == "link" else None)
        if not source:
            return
        link = urljoin(BASE, source)
        if not allowed(link) or not urlsplit(link).path.endswith(".js"):
            return
        if tag.lower() == "script":
            self.paths.append(link)
        elif any(x in str(attrs.get("rel", "")).lower() for x in ("prefetch", "preload")):
            self.prefetch.append(link)


def probe():
    markup = limited_read(BASE)
    src = Scripts()
    src.feed(markup)
    scripts = list(dict.fromkeys(src.paths))
    prefetch = list(dict.fromkeys(src.prefetch))
    print("Official CN website: HTML received", len(markup), "characters", flush=True)
    print("Official JS assets referenced:", len(scripts), flush=True)
    print("Official JS prefetch assets:", len(prefetch), flush=True)
    scripts.sort(key=lambda link: (0 if re.search(r"(?:app|main|index|runtime)", link, re.I)
                                  else 1 if "chunk" in link else 2, link))
    prefetch.sort(key=lambda link: (0 if re.search(r"card|list|search|query", link, re.I) else 1, link))
    selected = list(dict.fromkeys(scripts + prefetch))[:14]
    print("Selected JS asset paths:")
    for link in selected:
        print(" ", urlsplit(link).path)
    candidates = set()
    for link in selected:
        try:
            body = limited_read(link, byte_limit=4_000_000)
        except Exception as exc:
            print("Asset unavailable:", urlsplit(link).path,
                  type(exc).__name__, str(exc)[:100])
            continue
        print("Asset received:", urlsplit(link).path, len(body), "chars")
        # Look for actual JS string literals containing API/card paths. This
        # is a *candidate* list, not a confirmed callable backend endpoint.
        for match in re.finditer(r"""["']([^"'<>\\]{5,200})["']""", body):
            value = match.group(1)
            if re.search(r"(?i)(cardlist|/api/|card/query|card/search|/card/)", value):
                if "?" in value or "token" in value.lower() or "password" in value.lower():
                    continue
                candidates.add(value[:150])
    print("Candidate literal paths", len(candidates))
    for value in sorted(candidates)[:35]:
        print("API_CANDIDATE", value)
    print("Probe complete: no card database downloaded or API calls made.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(probe())
    except Exception as exc:
        print("Probe unavailable:", type(exc).__name__, str(exc)[:140])
        sys.exit(0)
