import json
import tempfile
import threading
import time
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from tools import local_bootstrap
from tools.fast_bootstrap import StartRateLimiter, fetch_card

URL = "https://app.digicamoe.cn/Cards/PR/P-001/P"
HTML = '<h1>亚古兽</h1><div>编号</div><div>P-001</div><div>能力</div><p>【登场时】抽1张卡。</p><div>收录信息</div>'


class LocalBootstrapTests(unittest.TestCase):
    def test_reads_existing_index_and_published_count(self):
        with tempfile.TemporaryDirectory() as home:
            data = Path(home)
            (data / "index").mkdir()
            (data / "index" / "AUTO.json").write_text(json.dumps({
                "cards": {"P-001": [URL], "P-002": [URL]}
            }), encoding="utf-8")
            (data / "index" / "P.json").write_text(json.dumps({
                "cards": {"P-002": [URL], "P-003": [URL]}
            }), encoding="utf-8")
            (data / "manifest.json").write_text(json.dumps({
                "publishedCardCount": 3
            }), encoding="utf-8")
            with patch.object(local_bootstrap, "DATA", data):
                self.assertEqual(local_bootstrap.count_indexed(), 3)
                self.assertEqual(local_bootstrap.published(), 3)

    def test_server_500_retries_then_recovers(self):
        error = urllib.error.HTTPError(URL, 500, "Server error", None, None)
        stop = threading.Event()
        with patch("tools.fast_bootstrap.fetch", side_effect=[error, error, HTML]), \
             patch("tools.fast_bootstrap.StartRateLimiter.pause") as cooldown, \
             patch.object(stop, "wait", return_value=False):
            status, _, card, reason = fetch_card(
                "P-001", [URL], StartRateLimiter(.001), stop,
                time.monotonic() + 120, 5
            )
        self.assertEqual(status, "ok")
        self.assertEqual(card["cardId"], "P-001")
        self.assertFalse(stop.is_set())
        self.assertEqual([call.args[0] for call in cooldown.call_args_list], [15, 45])

    def test_persistent_server_500_is_deferred(self):
        error = urllib.error.HTTPError(URL, 500, "Server error", None, None)
        stop = threading.Event()
        with patch("tools.fast_bootstrap.fetch", side_effect=error), \
             patch("tools.fast_bootstrap.StartRateLimiter.pause"), \
             patch.object(stop, "wait", return_value=False):
            status, _, card, reason = fetch_card(
                "P-001", [URL], StartRateLimiter(.001), stop,
                time.monotonic() + 120, 5
            )
        self.assertEqual(status, "deferred")
        self.assertIn("HTTP 500", reason)
        self.assertIsNone(card)
        self.assertFalse(stop.is_set())

    def test_429_still_stops(self):
        error = urllib.error.HTTPError(URL, 429, "Rate limit", None, None)
        stop = threading.Event()
        with patch("tools.fast_bootstrap.fetch", side_effect=error):
            status, *_ = fetch_card(
                "P-001", [URL], StartRateLimiter(.001), stop,
                time.monotonic() + 10, 5
            )
        self.assertEqual(status, "blocked")
        self.assertTrue(stop.is_set())


if __name__ == "__main__":
    unittest.main()
