import csv
import json
import tempfile
import unittest
from pathlib import Path

from tools.official_cn_capture import collect_cards, candidate_number
from tools.official_cn_align import (
    normalize_jp, get_cn_number, align, manual_map, run
)


class OfficialCnCrosswalkTests(unittest.TestCase):
    def setUp(self):
        self.index = {"BT25-058", "BT1-005"}
        self.aegis = {
            "BT25-058": {"cardId": "BT25-058", "level": 6, "dp": 12000},
            "BT1-005": {"cardId": "BT1-005", "level": 3, "dp": 2000},
        }
        self.card = {"cardNo": "BT-25-058", "cardName": "测试数码兽",
                     "mainEffect": "【攻击时】发动1个效果。", "level": 6,
                     "dp": 12000}

    def test_original_id_normalization_but_not_cn_series_guess(self):
        self.assertEqual(normalize_jp("BT-25-058"), "BT25-058")
        self.assertEqual(normalize_jp("BT25-058"), "BT25-058")
        self.assertEqual(normalize_jp("P-001"), "P-001")
        self.assertEqual(normalize_jp("ST24-11"), "ST24-11")
        self.assertEqual(normalize_jp("BTC-01-058"), "")
        self.assertEqual(candidate_number("BTC-01-058"), "BTC-01-058")

    def test_capture_extracts_rows_from_nested_official_json(self):
        records = collect_cards({"data": {"records": [self.card]}})
        self.assertEqual(len(records), 1)
        self.assertEqual(get_cn_number(records[0]), "BT-25-058")

    def test_exact_three_way_crosswalk_requires_both_references(self):
        result, preview, multi = align({"cards": [{"payload": self.card}]},
                                       self.index, self.aegis)
        self.assertEqual(result[0]["status"], "aligned")
        self.assertEqual(result[0]["japaneseCardId"], "BT25-058")
        self.assertEqual(result[0]["aegisCardId"], "BT25-058")
        self.assertEqual(preview[0]["cardId"], "BT25-058")
        self.assertEqual(preview[0]["main"], self.card["mainEffect"])

    def test_differing_cn_number_without_manual_mapping_stays_pending(self):
        record = {**self.card, "cardNo": "BTC-01-058"}
        rows, preview, multi = align({"cards": [{"payload": record}]},
                                     self.index, self.aegis)
        self.assertEqual(rows[0]["status"], "manual_mapping_required")
        self.assertFalse(preview)

    def test_reviewed_mapping_accepts_explicit_cn_reprint(self):
        record = {**self.card, "cardNo": "BTC-01-058"}
        rows, preview, multi = align({"cards": [{"payload": record}]},
                                     self.index, self.aegis,
                                     {"BTC-01-058": ("BT25-058", "BT25-058")})
        self.assertEqual(rows[0]["status"], "aligned")
        self.assertEqual(preview[0]["cardId"], "BT25-058")

    def test_no_matching_digicamoe_index_or_aegis_card(self):
        rows, preview, _ = align([self.card], set(), self.aegis)
        self.assertEqual(rows[0]["status"], "not_in_existing_index")
        self.assertFalse(preview)
        rows, preview, _ = align([self.card], self.index, {})
        self.assertEqual(rows[0]["status"], "not_in_aegis")

    def test_stat_conflict_fails_closed(self):
        bad = {**self.card, "dp": 14000}
        rows, preview, _ = align([bad], self.index, self.aegis)
        self.assertEqual(rows[0]["status"], "conflict")
        self.assertFalse(preview)

    def test_multiple_original_printings_with_conflicting_text_not_exported(self):
        a = {**self.card, "cardNo": "BT25-058"}
        b = {**self.card, "cardNo": "BTC-01-058", "mainEffect": "【登场时】发动另一效果。"}
        rows, preview, multi = align([a,b], self.index, self.aegis,
                                     {"BTC-01-058": ("BT25-058", "BT25-058")})
        self.assertFalse(preview)
        self.assertEqual(multi, ["BT25-058"])
        self.assertTrue(all(x["status"] == "conflicting_printings" for x in rows))

    def test_manual_csv_must_be_reviewed(self):
        with tempfile.TemporaryDirectory() as work:
            path = Path(work) / "mapping.csv"
            path.write_text("chineseCardId,japaneseCardId,aegisCardId,reviewed\n"
                            "BTC-01-058,BT25-058,BT25-058,yes\n",
                            encoding="utf-8")
            self.assertEqual(manual_map(path)["BTC-01-058"][0], "BT25-058")
            path.write_text("chineseCardId,japaneseCardId,aegisCardId,reviewed\n"
                            "BTC-01-058,BT25-058,BT25-058,no\n",
                            encoding="utf-8")
            with self.assertRaises(ValueError):
                manual_map(path)

    def test_staging_does_not_modify_existing_public_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            public = root / "data"
            (public / "index").mkdir(parents=True)
            (public / "index" / "AUTO.json").write_text(json.dumps(
                {"cards": {"BT25-058": ["https://app.digicamoe.cn/Cards/BT-25/BT25-058/R"]}}))
            capture = root / "official_capture.json"
            capture.write_text(json.dumps({"cards": [{"payload": self.card}]}))
            catalog = root / "aegis_cards.json"
            catalog.write_text(json.dumps([self.aegis["BT25-058"]]))
            output = root / "local" / "mapping.json"
            review = root / "local" / "review.csv"
            preview = root / "local" / "preview.json"
            result = run(capture, output, review, preview, public, catalog)
            self.assertEqual(result, 0)
            self.assertFalse((public / "cards").exists())
            self.assertEqual(json.loads(preview.read_text())["cards"][0]["cardId"], "BT25-058")


if __name__ == "__main__":
    unittest.main()
