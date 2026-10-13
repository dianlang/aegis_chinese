import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from sync_cards import parse, indexed_cards, shard

HTML = """<html><body>
<nav>site links</nav><h1>烂泥兽</h1>
<div>编号</div><div>P-101</div><span>形态：成熟期</span>
<h3>能力</h3><p>【登场时】【进化时】丢弃1张手牌后，抽2张卡。</p>
<h3>进化源能力</h3><p>【攻击时】消灭对手1只Lv.3数码兽。</p>
<h3>安防能力</h3><p>无</p>
<h3>收录信息</h3><p>这里不属于效果</p>
</body></html>"""

class CardSyncTests(unittest.TestCase):
    def test_valid_card(self):
        data = parse(HTML, "P-101", "https://app.digicamoe.cn/Cards/PR-LCS2023/P-101/P")
        self.assertEqual(data["name"], "烂泥兽")
        self.assertIn("丢弃1张", data["main"])
        self.assertIn("攻击时", data["inherited"])
        self.assertNotIn("这里不属于效果", data["security"])
    def test_reject_other_id(self):
        with self.assertRaises(ValueError):
            parse(HTML, "P-102", "https://app.digicamoe.cn/Cards/PR-LCS2023/P-102/P")
    def test_index(self):
        self.assertIn("P-248", indexed_cards())
        self.assertIn("PR-TB33", indexed_cards()["P-248"][0])
    def test_shards(self):
        self.assertEqual(shard("P-248"), "P")
        self.assertEqual(shard("BT08-108"), "BT8")

if __name__ == "__main__":
    unittest.main()
