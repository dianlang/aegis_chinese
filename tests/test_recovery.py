import tempfile
import threading
import time
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from tools.fast_bootstrap import StartRateLimiter, build_pending, fetch_card
from tools.merge_collected import merge_card_records, merge_index, merge

EXAMPLE = ('<h1>亚古兽</h1><div>编号</div><div>P-001</div>'
           '<div>能力</div><p>【登场时】抽1张卡。</p><div>收录信息</div>')
U = "https://app.digicamoe.cn/Cards/PR/P-001/P"


class RecoveryTests(unittest.TestCase):
    def test_all_indexed_urls_can_be_used(self):
        urls = [U.replace("/PR/", f"/PKG{n}/") for n in range(4)]
        def mock_get(url, timeout):
            if url != urls[-1]:
                raise urllib.error.HTTPError(url, 404, "Not Found", None, None)
            return EXAMPLE
        with patch("tools.fast_bootstrap.fetch", side_effect=mock_get):
            result = fetch_card("P-001", urls, StartRateLimiter(.001),
                                threading.Event(), time.monotonic()+10, 3)
        self.assertEqual(result[0], "ok")
        self.assertEqual(result[2]["url"], urls[-1])

    def test_temporary_transport_fault_recovers(self):
        event = threading.Event()
        issue = urllib.error.URLError(OSError("temporary DNS failure"))
        with patch("tools.fast_bootstrap.fetch", side_effect=[issue, issue, EXAMPLE]), \
             patch("tools.fast_bootstrap.StartRateLimiter.pause"), \
             patch.object(event, "wait", return_value=False):
            result = fetch_card("P-001", [U], StartRateLimiter(.001),
                                event, time.monotonic()+10, 3)
        self.assertEqual(result[0], "ok")
        self.assertFalse(event.is_set())

    def test_transport_failure_is_deferred_without_global_halt(self):
        event = threading.Event()
        with patch("tools.fast_bootstrap.fetch",
                   side_effect=urllib.error.URLError(OSError("timeout"))), \
             patch("tools.fast_bootstrap.StartRateLimiter.pause"), \
             patch.object(event, "wait", return_value=False):
            result = fetch_card("P-001", [U], StartRateLimiter(.001),
                                event, time.monotonic()+10, 3)
        self.assertEqual(result[0], "deferred")
        self.assertIn("timeout", result[3])
        self.assertFalse(event.is_set())

    def test_existing_404_rechecks_when_more_variants_added(self):
        from tools.sync_cards import timestamp
        record = {"cards": {"P-001": {"status": "failed",
                                    "checkedAt": timestamp(),
                                    "reason": "HTTP 404"}}}
        urls = [U.replace("/PR/", f"/PKG{n}/") for n in range(3)]
        pending = build_pending({"P-001": urls}, {"P": {}}, record, "all")
        self.assertEqual(len(pending), 1)

    def test_merge_retains_reviewed_remote(self):
        remote = {"P-001": {"cardId": "P-001", "name": "人工校对", "reviewStatus": "verified"}}
        harvested = {"P-001": {"cardId": "P-001", "name": "机器抓取"}}
        self.assertEqual(merge_card_records(remote, harvested, {}, {})["P-001"]["name"],
                         "人工校对")

    def test_merge_preserves_new_remote_cards_and_index_urls(self):
        with tempfile.TemporaryDirectory() as home:
            root = Path(home)
            base, captured = root/"main", root/"checkpoint"
            from tools.merge_collected import save, load
            save(base/"cards"/"P.json", {"P-001":{"cardId":"P-001","name":"remote",
                            "main":"效果","url":U}})
            save(captured/"cards"/"P.json", {"P-002":{"cardId":"P-002","name":"capture",
                            "main":"效果","url":U.replace("P-001","P-002")}})
            save(base/"index"/"P.json", {"version":1,"cards":{"P-001":[U]}})
            save(captured/"index"/"P.json", {"version":1,"cards":{"P-001":[U+"?alt"]}})
            save(base/"manifest.json", {"schemaVersion":1,"publishedCardCount":1})
            merge(captured,base)
            cards = load(base/"cards"/"P.json",{})
            self.assertEqual(set(cards), {"P-001","P-002"})
            self.assertEqual(load(base/"manifest.json",{})["publishedCardCount"],2)
            self.assertEqual(len(load(base/"index"/"P.json",{})["cards"]["P-001"]),2)


if __name__ == "__main__":
    unittest.main()
