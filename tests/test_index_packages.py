import unittest
from tools.index_packages import list_packs, list_cards
from tools.sync_cards import parse

class PackageIndexTests(unittest.TestCase):
    def test_catalogue_collects_package_slugs_and_ignores_other_hosts(self):
        html = ('<a href="/Package/BT-26">BT26</a>'
                '<a href="https://app.digicamoe.cn/Package/EX-13">EX13</a>'
                '<a href="https://evil.example/Package/BT-99">bad</a>'
                '<a href="/Cards/BT-26/BT26-001/C">card</a>')
        self.assertEqual(list_packs(html), ["BT-26", "EX-13"])

    def test_package_collects_real_link_and_deduplicates_art(self):
        html = ('<a href="/Cards/BT-26/BT26-001/C">Card</a>'
                '<a href="/Cards/BT-26/BT26-001/C">Same card</a>'
                '<a href="/Cards/BT-26/BT26-002/R">Next</a>'
                '<a href="/Cards/EX-13/EX13-001/R">Wrong pack</a>'
                '<a href="javascript:alert(1)">invalid</a>')
        cards = list_cards(html, "BT-26")
        self.assertEqual(set(cards), {"BT26-001", "BT26-002"})
        self.assertEqual(len(cards["BT26-001"]), 1)

class PrintedCardParserTests(unittest.TestCase):
    def test_digimon_with_separated_attributes(self):
        html = """<body><h1>狼人加鲁鲁兽</h1><h2>ワーガルルモン</h2>
        <div>卡片类型</div><div>数码兽卡</div><div>编 号</div><div>P-008</div>
        <div>罕贵度</div><div>P</div><div>颜 色</div><div>蓝</div><div>LV</div><div>5</div>
        <div>登场费用</div><div>7</div><div>DP</div><div>6000</div>
        <div>形 态</div><div>完全体</div><div>属 性</div><div>疫苗</div>
        <div>类 型</div><div>兽人型</div><div>进化条件：</div>
        <div>蓝 / Lv.4 / 费用 3</div>
        <div>能力</div><div>〖攻击时〗这只数码兽激活。</div>
        <div>进化源能力</div><div>〖自己的回合〗DP+1000。</div><div>收录信息</div></body>"""
        value = parse(html, "P-008", "https://app.digicamoe.cn/Cards/PR/P-008/P")
        self.assertEqual(value["name"], "狼人加鲁鲁兽")
        self.assertEqual(value["cardType"], "数码兽卡")
        self.assertEqual(value["rarity"], "P")
        self.assertEqual(value["playCost"], 7)
        self.assertEqual(value["dp"], 6000)
        self.assertEqual(value["level"], 5)
        self.assertEqual(value["form"], "完全体")
        self.assertEqual(value["digivolutionConditions"], ["蓝 / Lv.4 / 费用 3"])
        self.assertIn("攻击时", value["main"])
        self.assertIn("自己的回合", value["inherited"])

    def test_no_effect_vanilla_valid(self):
        html = """<h1>普通数码兽</h1><div>卡片类型 数码兽卡</div>
        <div>编号 P-777</div><div>LV 3</div><div>登场费用 2</div>
        <div>DP 2000</div><h3>收录信息</h3>"""
        value = parse(html, "P-777", "https://app.digicamoe.cn/Cards/PR/P-777/P")
        self.assertEqual(value["dp"], 2000)
        self.assertNotIn("main", value)

    def test_wrong_number_rejected(self):
        html = '<h1>卡牌</h1><div>编号 P-999</div><div>能力</div><p>效果</p>'
        with self.assertRaises(ValueError):
            parse(html, "P-998", "https://app.digicamoe.cn/Cards/PR/P-998/P")

if __name__ == "__main__":
    unittest.main()
