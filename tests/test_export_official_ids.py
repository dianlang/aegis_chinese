import unittest
from tools.export_official_ids import export_ids


class ExportOfficialIDsTests(unittest.TestCase):
    def test_separates_internal_id_printed_number_and_chinese_pack(self):
        data = [
            {"id": 109, "model": "BT1-001", "cardGroup": "BTC-01", "name": "比高兽",
             "effect": "中文内容不应该进入编号映射"},
            {"id": 210, "model": "BT1-001", "cardGroup": "BTC-02", "name": "比高兽",
             "effect": "可能不同的中文文字"},
            {"id": 110, "model": "BT1-002", "cardGroup": "BTC-01", "name": "幼龙兽"},
            {"id": 888, "model": "BT27-084", "cardGroup": "BT-27", "name": "测试兽"},
            {"id": 999, "model": "BTC-01", "cardGroup": "BTC-01", "name": "商品不是卡牌"}
        ]
        result = export_ids(data, {"BT1-001": [], "BT1-002": []},
                            {"BT1-001", "BT1-002", "BT27-084"})
        self.assertEqual(result["summary"]["uniqueOfficialPrintedCards"], 3)
        self.assertEqual(result["summary"]["invalidRows"], 1)
        self.assertEqual(result["summary"]["matchingCounts"]["three_way_matched"], 2)
        card = result["cards"]["BT1-001"]
        self.assertEqual(card["officialRecordIds"], [109, 210])
        self.assertEqual(card["cnProductCodes"], ["BTC-01", "BTC-02"])
        self.assertEqual(card["aegisCardId"], "BT1-001")
        self.assertEqual(card["cnCardNo"], "BT1-001")
        self.assertEqual(result["cards"]["BT27-084"]["matchStatus"], "cn_aegis_no_jp_index")
        as_text = str(result)
        self.assertNotIn("中文内容", as_text)
        self.assertNotIn("比高兽", as_text)


if __name__ == "__main__":
    unittest.main()
