import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from tools import sync_official_cn as s


class OfficialApiSyncTests(unittest.TestCase):
    def test_official_printed_model_is_valid(self):
        self.assertEqual(s.printed_no("BT1-001"), "BT1-001")
        self.assertEqual(s.printed_no("BTC-01"), "")
        self.assertIsNone(s.page_signature({"records": []}))
        self.assertEqual(s.page_signature({"records": [
            {"id": 109, "model": "BT1-001"},
            {"id": 110, "model": "BT1-002"}]}), (2, "109", "BT1-001", "110", "BT1-002"))

    def test_two_pages_write_resumable_staging_and_matching(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            page1 = [{"id": k, "model": "BT1-%03d" % k,
                      "cardGroup": "BTC-01", "name": "测试兽"} for k in range(1,41)]
            page2 = [{"id": k, "model": "BT1-%03d" % k,
                      "cardGroup": "BTC-01", "name": "测试兽"} for k in range(41,81)]
            responses = [
                {"requestedPage": 1, "records": page1, "totalPages": 2, "totalCount": 80},
                {"requestedPage": 2, "records": page2, "totalPages": 2, "totalCount": 80},
            ]
            lookup = {"BT1-%03d" % i: ["https://app.digicamoe.cn/example"]
                      for i in range(1,81)}
            with patch.object(s, "fetch_page", side_effect=responses) as fetching, \
                 patch.object(s, "indexed_ids", return_value=lookup), \
                 patch.object(s, "aegis_ids", return_value=set(lookup)), \
                 patch.object(s.time, "sleep"):
                self.assertEqual(s.sync(max_pages=2, interval=3, directory=base/"pages"), 0)
                self.assertEqual(fetching.call_count, 2)
                self.assertEqual(s.sync(max_pages=2, interval=3, directory=base/"pages"), 0)
                self.assertEqual(fetching.call_count, 2)
            raw = json.loads((base/"official_cn_capture.json").read_text(encoding="utf-8"))
            self.assertEqual(len(raw["records"]), 80)
            alignment = json.loads((base/"official_alignment.json").read_text(encoding="utf-8"))
            self.assertEqual(alignment["summary"]["threeWayMatched"], 80)

    def test_429_stops_and_keeps_prior_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            old = {"requestedPage": 1, "records": [
                {"id": 1, "model": "BT1-001", "name": "测试兽", "cardGroup": "BTC-01"} for _ in range(40)
            ], "totalPages": 2, "totalCount": 80}
            s.save_local(s.checkpoint_path(base/"pages", 1), old)
            error = urllib.error.HTTPError(s.URL, 429, "Too many requests", None, None)
            with patch.object(s, "fetch_page", side_effect=error), \
                 patch.object(s, "indexed_ids", return_value={"BT1-001":["url"]}), \
                 patch.object(s, "aegis_ids", return_value={"BT1-001"}), \
                 patch.object(s.time, "sleep"):
                self.assertEqual(s.sync(max_pages=2, interval=3, directory=base/"pages"), 2)
            self.assertTrue(s.checkpoint_path(base/"pages", 1).exists())
            self.assertEqual(json.loads((base/"official_alignment.json").read_text(encoding="utf-8"))
                             ["summary"]["threeWayMatched"], 1)

    def test_bulk_needs_explicit_opt_in(self):
        with self.assertRaises(ValueError):
            s.sync(max_pages=6, directory=Path("/tmp/does_not_matter"), full=False)


if __name__ == "__main__":
    unittest.main()
