#!/usr/bin/env python3
"""Capture card records from the official CN card-list web app in local Edge.

Discover the real browser XHR / fetch responses rather than guessing endpoints.
User navigates the visible website; no rate-limit bypass, auth interception,
pagination guessing or automatic bulk downloading. Only card-like JSON objects
are retained in a LOCAL file (never upload without reviewing official terms).
"""
import argparse
import asyncio
import datetime
import json
from pathlib import Path
from urllib.parse import urlsplit

try:
    from .align_official_cards import rows_in, field, SOURCE_FIELDS, NAME_FIELDS
except ImportError:
    from align_official_cards import rows_in, field, SOURCE_FIELDS, NAME_FIELDS

DEFAULT_URL = "https://www.digimoncard.cn/cardlist"
ALLOWED_HOSTS = {"digimoncard.cn", "www.digimoncard.cn", "api.digimoncard.cn"}


def is_official_host(url):
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    return parts.scheme == "https" and (host in ALLOWED_HOSTS or host.endswith(".digimoncard.cn"))


def discover_records(payload):
    """Only capture objects with actual printed-card ID fields and card info.

    Keep raw *card objects* (not unrelated API response wrappers, user info,
    request headers or cookies), so the parser can adapt to actual API fields.
    """
    return list(rows_in(payload))


async def capture(url, destination, seconds=120, browser_channel="msedge"):
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise RuntimeError("Install Playwright first: py -m pip install playwright") from exc

    if not is_official_host(url):
        raise ValueError("Only the official HTTPS digimoncard.cn domain is allowed")
    found = []
    endpoints = {}
    pending = set()
    limiter = asyncio.Semaphore(3)

    async with async_playwright() as p:
        browser = await p.chromium.launch(channel=browser_channel, headless=False)
        context = await browser.new_context(locale="zh-CN")
        page = await context.new_page()

        async def inspect(response):
            link = response.url
            if not is_official_host(link):
                return
            if response.request.resource_type not in ("xhr", "fetch"):
                return
            parsed = urlsplit(link)
            safe_endpoint = parsed.scheme + "://" + parsed.netloc + parsed.path
            type_header = response.headers.get("content-type", "")
            if "json" not in type_header or response.status != 200:
                return
            async with limiter:
                try:
                    raw = await response.body()
                    if len(raw) > 8_000_000:
                        return
                    content = json.loads(raw)
                except (ValueError, OSError):
                    return
                items = discover_records(content)
                keyinfo = {"endpoint": safe_endpoint, "status": response.status,
                           "sampleKeys": list(content.keys())[:20] if isinstance(content, dict) else ["array"],
                           "cardCountDetected": len(items)}
                endpoints[safe_endpoint] = keyinfo
                if items:
                    for item in items:
                        found.append(item)
                    print("CARDS", safe_endpoint, "records", len(items),
                          "total collected", len(found), flush=True)
                else:
                    # Do not save arbitrary JSON response bodies.
                    print("JSON", safe_endpoint,
                          "top-level keys", ",".join(keyinfo["sampleKeys"])[:200],
                          "(no verified card records)", flush=True)

        def on_response(response):
            task = asyncio.create_task(inspect(response))
            pending.add(task)
            task.add_done_callback(pending.discard)

        page.on("response", on_response)
        print("Opening official card list in your own Edge browser.", flush=True)
        print("Use the visible page's search or pagination to load cards.", flush=True)
        print("The tool observes public JSON card data only; it does not capture credentials.", flush=True)
        print("Auto-stop after", seconds, "seconds. Close the browser to stop early.", flush=True)
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=35000)
            await page.wait_for_timeout(seconds * 1000)
        except Exception as exc:
            print("Browser page stopped:", type(exc).__name__, str(exc)[:140], flush=True)
        if pending:
            await asyncio.wait(pending, timeout=10)
        await browser.close()

    # Exact response duplications can arise from filters/pagination. Deduplicate
    # on serialized value; retain distinct artwork or region printings.
    deduped = {}
    for item in found:
        key = json.dumps(item, ensure_ascii=False, sort_keys=True)
        deduped[key] = item
    result = {
        "schemaVersion": 1,
        "capturedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source": DEFAULT_URL,
        "records": list(deduped.values())
    }
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    diagnostic = path.with_name(path.stem + "_endpoints.json")
    diagnostic.write_text(json.dumps(list(endpoints.values()), ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
    print("Finished. Card records:", len(deduped))
    print("Local capture:", path)
    print("Endpoint diagnostics:", diagnostic)
    if not deduped:
        print("No card records detected. Share the endpoint diagnostic JSON"
              " or a redacted F12 Network Response sample to adapt the parser.")
    return len(deduped)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--seconds", type=int, default=120)
    parser.add_argument("--channel", default="msedge", choices=("msedge", "chrome", "chromium"))
    parser.add_argument("--output", default="local/official_cn_capture.json")
    args = parser.parse_args()
    if not 15 <= args.seconds <= 600:
        parser.error("--seconds must be between 15 and 600")
    try:
        asyncio.run(capture(args.url, args.output, args.seconds, args.channel))
    except Exception as exc:
        parser.exit(2, "Official browser capture failed: " + str(exc) + "\n")


if __name__ == "__main__":
    main()
