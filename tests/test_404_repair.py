import json
import tempfile
import threading
import time
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from tools import repair_404_links
from tools.fast_bootstrap import StartRateLimiter
from tools.sync_cards import load, save

BT1 = "https://app.digicamoe.cn/Cards/BT-1/BT1-006/R"
ALT = "https://app.digicamoe.cn/Cards/BT-1/BT1-006/R-P"


class Repair404Tests(unittest.TestCase):
    def test_shared_pause_delays_all_workers_without_burst(self):
        limiter = StartRateLimiter(.02)
        event = threading.Event()
        limiter.pause(.06)
        start = time.monotonic()
        self.assertTrue(limiter.wait_slot(event, start + 1))
        self.assertGreaterEqual(time.monotonic() - start, .045)
        start = time.monotonic()
        self.assertTrue(limiter.wait_slot(event, start + 1))
        self.assertGreaterEqual(time.monotonic() - start, .015)

    def test_targets_only_failed_404_once_per_day(self):
        index = {"cards": {"BT1-006": [BT1], "BT1-007": [
            BT1.replace("006", "007")]}}
        status = {
            "BT1-006": {"status": "failed", "reason": "HTTP 404"},
            "BT1-007": {"status": "deferred", "reason": "HTTP 500"}}
        pending = repair_404_links.targets(index, status, {}, max_packs=4)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0][0], "BT-1")
        from tools.sync_cards import timestamp
        pending = repair_404_links.targets(index, status,
                                           {"BT-1": timestamp()}, max_packs=4)
        self.assertFalse(pending)

    def test_refresh_404_uses_only_real_listed_urls(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            idx = root / "index" / "AUTO.json"
            istate = root / "index-state.json"
            sstate = root / "sync-state.json"
            save(idx, {"version": 1, "cards": {"BT1-006": [BT1]}})
            save(sstate, {"version": 1, "cards": {
                "BT1-006": {"status": "failed", "reason": "HTTP 404"}}})
            save(istate, {"version": 1, "scanned": {}, "errors": {}})
            html = '<a href="/Cards/BT-1/BT1-006/R-P">alt</a>'
            with patch.object(repair_404_links, "INDEX_FILE", idx), \
                 patch.object(repair_404_links, "STATE_FILE", istate), \
                 patch.object(repair_404_links, "DATA", root), \
                 patch.object(repair_404_links, "fetch", return_value=html) as network:
                self.assertEqual(repair_404_links.repair(max_packs=2), 0)
                self.assertEqual(repair_404_links.repair(max_packs=2), 0)
            self.assertEqual(network.call_count, 1)
            self.assertEqual(load(idx, {})["cards"]["BT1-006"], [ALT, BT1])
            self.assertEqual(load(sstate, {})["cards"]["BT1-006"]["status"],
                             "pending_recheck")
            self.assertIn("BT-1", load(istate, {})["repairChecks"])

    def test_upstream_429_aborts_without_writing_new_index_links(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            idx = root / "index" / "AUTO.json"
            istate = root / "index-state.json"
            save(idx, {"version": 1, "cards": {"BT1-006": [BT1]}})
            save(root / "sync-state.json", {"cards": {
                "BT1-006": {"status": "failed", "reason": "HTTP 404"}}})
            with patch.object(repair_404_links, "INDEX_FILE", idx), \
                 patch.object(repair_404_links, "STATE_FILE", istate), \
                 patch.object(repair_404_links, "DATA", root), \
                 patch.object(repair_404_links, "fetch",
                              side_effect=urllib.error.HTTPError(BT1, 429, "limit", None, None)):
                self.assertEqual(repair_404_links.repair(), 2)
            self.assertEqual(load(idx, {})["cards"]["BT1-006"], [BT1])


if __name__ == "__main__":
    unittest.main()
