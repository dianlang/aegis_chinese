import json
import tempfile
import unittest
from pathlib import Path

from tools.align_official_cards import (
    printed_no, rows_in, read_official, align, write_alignment,
)
from tools.capture_official_browser import discover_records, is_official_host


class OfficialAlignmentTests(unittest.TestCase):
    def test_accepts_real_printed_card_ids_not_pack_skus(self):
        self.assertEqual(printed_no("BT1-010"), "BT1-010")
        self.assertEqual(printed_no("ＢＴ１－０１０"), "")
        self.assertEqual(printed_no("BT25－058"), "BT25-058")
        self.assertEqual(printed_no("NO.BT1-010"), "BT1-010")
        self.assertEqual(printed_no("BTC-01"), "")
        self.assertEqual(printed_no("EXC-04"), "")
        self.assertEqual(printed_no("BT1"), "")

    def test_capture_extracts_actual_card_data_from_wrapped_json(self):
        result = {"code": 0, "data": {"records": [
            {"cardNo": "BT1-010", "cardName": "亚古兽", "packCode": "BTC-01"},
            {"cardNo": "BT1-011", "cardName": "亚古兽博士", "packCode": "BTC-01"}
        ], "current": 1}}
        rows = discover_records(result)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["cardNo"], "BT1-010")

    def test_duplicate_prints_do_not_make_ambiguous_card_identity(self):
        records = [{"cardNo": "BT1-010", "cardName": "亚古兽", "packCode": "BTC-01"},
                   {"cardNo": "BT1-010", "cardName": "亚古兽", "packCode": "BTC-02"}]
        indexed = {"BT1-010": ["https://app.digicamoe.cn/Cards/BT-1/BT1-010/R"],
                   "BT1-011": ["https://app.digicamoe.cn/Cards/BT-1/BT1-011/C"]}
        aegis = {"BT1-010", "BT1-011", "BT27-084"}
        result = align(records, indexed, aegis)
        self.assertEqual(result["summary"]["threeWayMatched"], 1)
        self.assertEqual(result["summary"]["awaitingOfficialCN"], 1)
        lookup = {item["cardId"]: item for item in result["cards"]}
        self.assertEqual(lookup["BT1-010"]["cnPrintCount"], 2)
        self.assertEqual(lookup["BT1-010"]["aegisCardId"], "BT1-010")
        self.assertEqual(lookup["BT1-010"]["jpCardNo"], "BT1-010")
        self.assertEqual(lookup["BT1-010"]["cnCardNo"], "BT1-010")
        self.assertEqual(lookup["BT1-010"]["cnPackCodes"], ["BTC-01", "BTC-02"])
        self.assertEqual(lookup["BT27-084"]["status"], "aegis_not_in_jp_index")

    def test_do_not_fuzzy_match_same_name_different_numbers(self):
        result = align([{"cardNo": "BT2-999", "cardName": "亚古兽"}],
                       {"BT1-010": ["https://app.digicamoe.cn/Cards/BT-1/BT1-010/R"]},
                       {"BT1-010"})
        rows = {r["cardId"]:r for r in result["cards"]}
        self.assertEqual(rows["BT2-999"]["status"], "cn_not_in_aegis")
        self.assertEqual(rows["BT1-010"]["status"], "awaiting_cn_record")

    def test_invalid_official_row_kept_for_review(self):
        result = align([{"cardNo": "BTC-01", "cardName": "某商品"},
                        {"id": "12345", "cardName": "某卡"}], {}, set())
        self.assertEqual(result["summary"]["invalidOfficialRows"], 2)

    def test_capture_file_and_csv_emitted(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / "official.json"
            source.write_text(json.dumps({"records": [{
                "cardNo": "BT1-010", "cardName": "亚古兽"
            }]}), encoding="utf-8")
            parsed = read_official(source)
            self.assertEqual(len(parsed), 1)
            result = align(parsed, {"BT1-010":["valid URL"]}, {"BT1-010"})
            write_alignment(result, folder/"mapping.json", folder/"mapping.csv")
            self.assertEqual(json.loads((folder/"mapping.json").read_text(encoding="utf-8"))
                             ["summary"]["threeWayMatched"], 1)
            self.assertIn("three_way_matched", (folder/"mapping.csv").read_text(encoding="utf-8-sig"))

    def test_only_official_https_domains_captured(self):
        self.assertTrue(is_official_host("https://www.digimoncard.cn/cardlist"))
        self.assertTrue(is_official_host("https://api.digimoncard.cn/v1/query"))
        self.assertFalse(is_official_host("http://www.digimoncard.cn/cardlist"))
        self.assertFalse(is_official_host("https://digimoncard.cn.attacker.net/cardlist"))


if __name__ == "__main__":
    unittest.main()
