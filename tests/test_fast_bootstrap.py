import threading
import time
import unittest
import urllib.error
from unittest.mock import patch

from tools.fast_bootstrap import StartRateLimiter, build_pending, fetch_card


class FastBootstrapTests(unittest.TestCase):
    def test_global_rate_limiter_never_bursts(self):
        limiter = StartRateLimiter(0.025)
        stop = threading.Event()
        end = time.monotonic() + 1
        first = time.monotonic()
        self.assertTrue(limiter.wait_slot(stop, end))
        self.assertTrue(limiter.wait_slot(stop, end))
        self.assertGreaterEqual(time.monotonic() - first, 0.021)

    def test_prioritizes_old_schema_then_missing_cards(self):
        idx = {"P-003": ["https://app.digicamoe.cn/Cards/PR/P-003/P"],
               "P-002": ["https://app.digicamoe.cn/Cards/PR/P-002/P"],
               "P-001": ["https://app.digicamoe.cn/Cards/PR/P-001/P"]}
        shards = {"P": {"P-003": {"cardId": "P-003", "parserVersion": 2},
                        "P-002": {"cardId": "P-002", "main": "效果"}}}
        pending = build_pending(idx, shards, {"cards": {}}, "all")
        self.assertEqual([x[1] for x in pending], ["P-002", "P-001", "P-003"])
        self.assertEqual([x[1] for x in build_pending(idx, shards, {}, "new")], ["P-001"])

    def test_block_immediately_on_429(self):
        limiter = StartRateLimiter(0.001)
        stop = threading.Event()
        url = "https://app.digicamoe.cn/Cards/PR/P-001/P"
        error = urllib.error.HTTPError(url, 429, "rate limited", None, None)
        with patch("tools.fast_bootstrap.fetch", side_effect=error):
            status, card_id, card, message = fetch_card(
                "P-001", [url], limiter, stop, time.monotonic() + 10, 3
            )
        self.assertEqual((status, card_id, card, message), ("blocked", "P-001", None, "HTTP 429"))
        self.assertTrue(stop.is_set())

    def test_valid_card_fetch(self):
        limiter = StartRateLimiter(0.001)
        stop = threading.Event()
        url = "https://app.digicamoe.cn/Cards/PR/P-001/P"
        html = '<h1>亚古兽</h1><div>编号</div><div>P-001</div><div>能力</div><p>【登场时】抽1张卡。</p><div>收录信息</div>'
        with patch("tools.fast_bootstrap.fetch", return_value=html):
            status, card_id, card, message = fetch_card(
                "P-001", [url], limiter, stop, time.monotonic() + 10, 3
            )
        self.assertEqual(status, "ok")
        self.assertEqual(card_id, "P-001")
        self.assertEqual(card["name"], "亚古兽")
        self.assertEqual(card["parserVersion"], 2)
        self.assertFalse(stop.is_set())

    def test_expired_budget_skips_network(self):
        limiter = StartRateLimiter(1)
        stop = threading.Event()
        with patch("tools.fast_bootstrap.fetch") as network:
            status, _, _, _ = fetch_card(
                "P-001", ["https://app.digicamoe.cn/Cards/PR/P-001/P"],
                limiter, stop, time.monotonic() - 0.1, 3
            )
        self.assertEqual(status, "paused")
        network.assert_not_called()


if __name__ == "__main__":
    unittest.main()
