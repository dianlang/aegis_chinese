import csv
import json
import tempfile
import unittest
from pathlib import Path

from tools.import_dataset import normalize, read_input, mappings, preview_or_import
from tools.coverage_report import report, generate
from tools.sync_cards import load

URL = "https://app.digicamoe.cn/Cards/BT-25/BT25-058/R"


class ImportAndCoverageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.root.joinpath("cards").mkdir()
        self.root.joinpath("index").mkdir()
        self.row = {"卡号": "BT25-058", "卡名": "卡莉斯兽",
                    "效果": "【登场时】可以选择1只对手的数码兽。"}
        self.index = {"BT25-058": [URL]}

    def test_csv_and_json_equivalent(self):
        path = self.root / "source.csv"
        with path.open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=list(self.row))
            writer.writeheader()
            writer.writerow(self.row)
        self.assertEqual(normalize(read_input(path)[0], mappings())["name"], "卡莉斯兽")
        document = self.root / "source.json"
        document.write_text(json.dumps({"cards": {"BT25-058": {
            "name": "卡莉斯兽", "main": "【登场时】抽1张。"
        }}}, ensure_ascii=False), encoding="utf-8")
        self.assertEqual(read_input(document)[0]["cardId"], "BT25-058")

    def test_official_capture_records_support_cardNo_and_cardEffect(self):
        path = self.root / "capture.json"
        path.write_text(json.dumps({"schemaVersion": 1, "records": [
            {"cardNo": "BT25-058", "cardName": "测试兽",
             "cardEffect": "【登场时】抽1张卡。"}
        ]}, ensure_ascii=False), encoding="utf-8")
        records = read_input(path)
        self.assertEqual(len(records), 1)
        self.assertEqual(normalize(records[0], mappings())["cardId"], "BT25-058")
        stats, errors = preview_or_import(records, self.index, self.root,
                                          "Official CN sample", apply=False)
        self.assertFalse(errors)
        self.assertEqual(stats["new"], 1)

    def test_preview_does_not_write(self):
        stats, errors = preview_or_import([self.row], self.index, self.root,
                                          "authorized source", apply=False)
        self.assertFalse(errors)
        self.assertEqual(stats["new"], 1)
        self.assertFalse((self.root / "cards" / "BT25.json").exists())

    def test_apply_imports_real_index_url_and_updates_manifest(self):
        stats, errors = preview_or_import([self.row], self.index, self.root,
                                          "licensed dataset", apply=True)
        self.assertFalse(errors)
        item = load(self.root / "cards" / "BT25.json", {})["BT25-058"]
        self.assertEqual(item["url"], URL)
        self.assertEqual(item["translationSource"], "licensed dataset")
        self.assertEqual(load(self.root / "manifest.json", {})["publishedCardCount"], 1)

    def test_no_fabricated_source_and_no_partial_commit(self):
        rows = [self.row, {"卡号": "BT25-059", "卡名": "测试兽", "效果": "【登场时】抽1张。"}]
        stats, errors = preview_or_import(rows, self.index, self.root,
                                          "license", apply=True)
        self.assertTrue(errors)
        self.assertFalse((self.root / "cards" / "BT25.json").exists())

    def test_verified_remote_card_is_protected(self):
        prior = {"BT25-058": {"cardId": "BT25-058", "name": "校对名称",
                              "main": "【攻击时】校对效果", "reviewStatus": "verified",
                              "url": URL}}
        (self.root / "cards" / "BT25.json").write_text(
            json.dumps(prior, ensure_ascii=False), encoding="utf-8")
        stats, errors = preview_or_import([self.row], self.index, self.root,
                                          "license", apply=True, overwrite=True)
        self.assertEqual(stats["verified_protected"], 1)
        self.assertFalse(errors)
        self.assertEqual(load(self.root / "cards" / "BT25.json", {})["BT25-058"]["name"],
                         "校对名称")

    def test_distinct_card_numbers_not_variant_links(self):
        cards = {"BT25-058": {"main": "【登场时】抽1张"},
                 "BT25-059": {"cardType": "数码兽卡", "dp": 3000}}
        index = {"BT25-058": [URL, URL.replace("/R", "/R-P")],
                 "BT25-059": [URL.replace("058", "059")],
                 "BT25-060": [URL.replace("058", "060")]}
        summary, missing = report(index, cards, {})
        self.assertEqual(summary["totals"]["indexed"], 3)
        self.assertEqual(summary["totals"]["stored"], 2)
        self.assertEqual(summary["totals"]["chineseEffect"], 1)
        self.assertEqual(summary["totals"]["metadataOnly"], 1)
        self.assertEqual([m["cardId"] for m in missing], ["BT25-060"])

    def test_generate_files_and_detect_missing_status(self):
        (self.root / "index" / "AUTO.json").write_text(json.dumps(
            {"version": 1, "cards": {"BT25-058": [URL]}}), encoding="utf-8")
        (self.root / "sync-state.json").write_text(json.dumps(
            {"cards": {"BT25-058": {"status": "failed", "reason": "HTTP 500"}}}),
            encoding="utf-8")
        output = self.root / "coverage.json"
        md = self.root / "coverage.md"
        csvfile = self.root / "missing.csv"
        summary, miss = generate(self.root, output, md, csvfile)
        self.assertEqual(summary["totals"]["missing"], 1)
        self.assertEqual(miss[0]["reason"], "HTTP 500")
        self.assertIn("BT25", md.read_text(encoding="utf-8"))
        self.assertEqual(load(output, {})["totals"]["indexed"], 1)


if __name__ == "__main__":
    unittest.main()
