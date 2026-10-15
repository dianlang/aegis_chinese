# 官方简体中文卡表 × 日版索引 × Aegis 对齐

## 已确认的编号关系

官方中文卡表：https://www.digimoncard.cn/cardlist

**重要：卡包的商品编号 ≠ 卡片上的印刷编号。** 例如中文商品系列 BTC-01 收录 BT1-010 等卡片。不能按字符串把 BTC-01 换成 BT1，也不能用中文名称猜测卡号。

- JP：仓库 data/index/*.json 中的日版**卡牌编号**（去重）。
- CN：官方卡表实际返回的**卡牌编号**。只有拿到真实官方响应才可填写；商品所属包号单独保存到 cnPackCodes。
- Aegis：从 vinicius3333/aegis-digimon-tcg 的 develop 分支 apps/api/src/cards/*/*.ts 读取的真实卡牌实现文件编号。
- 异画和复刻：同一张卡牌编号可有多个版本，保留多个 CN 商品包与卡面变体，不重复计入卡牌数量。
- 同名不同编号：绝不自动合并。对不合法编号、缺少 ID、Aegis 尚无实现、日版索引缺少的编号，统一输出为待核对。

截至本次检查：Aegis 源码 4481 个不同卡牌编号；现有日版索引 4474 个；交集为 4474 个。Aegis 独有的 7 个编号是 BT27-084、LM-063～LM-068。这个数字是对 Aegis 源码文件名和日版索引的核对，**不表示已经从官方网站验证这些卡的中文印刷编号**。

- 基线表：[reports/card_id_alignment_baseline.csv](../reports/card_id_alignment_baseline.csv)
- Aegis 卡号快照：[data/mapping/aegis_cards.json](../data/mapping/aegis_cards.json)

## Windows 官方网站接口观察（小范围试运行）

因为官方卡表使用 JavaScript，网页上显示的内容并不直接证明后台 API 的 URL 或字段结构。我们不能猜一个接口地址然后全量下载。

先在项目根目录双击：

    scripts\official_cn_probe_windows.bat

程序首次运行时安装 Playwright，直接启动电脑上现有的 Microsoft Edge（不需要下载另一套浏览器）。打开官网卡表后，在两分钟内通过网页搜索一两张卡，或点击下一页。脚本仅观察官方站点实际返回的 JSON 卡牌响应，保存到本地：

- local_data/official_cn_capture.json：本地浏览器实际接收到的卡牌记录。
- local_data/official_cn_capture_endpoints.json：请求的主机/路径、JSON 顶层字段和检测到的卡牌数量；不保存 Cookie、Authorization 请求头或完整查询参数。
- local_data/official_alignment.json：三方卡号匹配表与验证状态。
- local_data/official_alignment.csv：Excel 可查看的三方对照表。

上述文件位于已被 .gitignore 忽略的 local_data/，**不会自动提交到 GitHub**。请先审阅是否有非卡牌字段和数据再分发限制。

命令行手动使用：

~~~bat
py -m pip install playwright
py tools\capture_official_browser.py --seconds 120
py tools\align_official_cards.py --official-json local_data\official_cn_capture.json
~~~

也可以完全离线对现有日版索引和 Aegis 编号生成待匹配表：

~~~bat
py tools\align_official_cards.py
~~~

状态含义：

| 状态 | 含义 |
|---|---|
| three_way_matched | 实际官方卡号已确认与日版索引和 Aegis 编号一致 |
| awaiting_cn_record | 日版和 Aegis 已对齐，但尚无官方中文卡牌记录 |
| cn_not_in_aegis | 官方有卡号，但 Aegis 暂无对应卡牌实现 |
| aegis_not_in_jp_index | Aegis 有卡号，日版索引暂缺 |
| cn_aegis_no_jp_index | 官方与 Aegis 同编号，但日版索引暂缺 |
| needs_manual_review | 其他未能安全证明的匹配情况 |

### 关于批量导入

官网没有在本次开发环境中提供可直接读取的浏览器网络请求，**尚未证实其真实 API 端点、查询参数、分页方式或响应字段**。上述工具属于实际浏览器数据采样和严格对齐框架；此刻还不是已经完成的整库采集器。

拿到一份小规模有效响应后，才能针对实际接口编写支持分页、合理速率限制、缓存、断点续传与差异更新的自动化导入器。

官网数据的展示不意味着允许未经授权公开镜像/再分发。DigiCamoe 对日版中文翻译的非商业使用许可不自动覆盖官方简体中文版数据。在明确数据权利前，不将官方完整效果文本直接提交到仓库。
