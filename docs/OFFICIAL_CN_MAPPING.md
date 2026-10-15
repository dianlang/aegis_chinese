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

## 已验证的官网 API（2026-10-15）

从官网前端模块与公开 JSON 响应中实际确认：

- API 基址：https://dtcgweb-api.digimoncard.cn
- 卡表分页：GET /gamecard/gamecardmanager/weblist?page=1&limit=40&state=0
- 单卡详情：GET /gamecard/gamecardmanager/webInfo/{id}
- 列表响应格式：code、msg、page；其中 page.list 包含卡牌对象。
- **关键映射：card.model = 印刷编号，例如 BT1-001；card.id = 官网内部数字 ID；card.cardGroup = 中文商品系列，例如 BTC-01。**
- 中文效果字段：effect（主效果）、envolutionEffect（进化源效果）、safeEffect（安防效果）。
- 按 limit=2 测试时，接口报告 totalCount=7527 条收录记录（含异画/重收录），不等于 7527 张不同卡。
- 按 limit=40 正式验证了前两页，连续获得 80 条不同官网内部 ID，80 条的印刷编号均与日版索引和 Aegis 精确匹配。

### Windows 直接分页同步（推荐）

在项目根目录双击：

    scripts\sync_official_cn_windows.bat

选择 1：先测试 3 页（最多 120 条）；选择 2：全量同步（分页，每 4 秒最多发起一个请求，逐页保存，碰到 429/5xx 会停止，下一次自动跳过已保存页面）。默认最多 60 分钟，通常不需一次跑满。

也可以运行：

~~~bat
py -m pip install -r requirements.txt
py tools\sync_official_cn.py --max-pages 3
py tools\sync_official_cn.py --full --interval 4 --time-budget-minutes 60
~~~

正式全量不会绕过验证码、身份验证、服务器限流或防爬措施，且不下载卡图。已保存的页面重新运行时不重复下载。

本地输出：

- local_data/official_cn_pages/page_*.json：每页官方原始记录，断点续抓。
- local_data/official_cn_capture.json：合并去重后的官方记录。
- local_data/official_alignment.json / .csv：官网 model 与已有日版卡号、Aegis 卡号的严格三方对照；记录中文商品包 cardGroup 与异画，不按同名合并。

这些文件全部保存在 Git 忽略的 local_data/。正式导入仓库前必须确认官方简体中文数据的再分发权利，并审阅同卡号不同印刷版本的效果冲突。现有 DigiCamoe 日版中文翻译不自动被官网卡文覆盖。

---

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

现已从官网实际前端和 API 响应确认端点、请求参数和 model 编号字段。Edge 观察工具仍可用于后续网站改版时重新确认接口。

正式分页同步器已经提供逐页缓存与断点续传；后续可扩展差异更新，但不能根据未经验证的字段盲目请求。

官网数据的展示不意味着允许未经授权公开镜像/再分发。DigiCamoe 对日版中文翻译的非商业使用许可不自动覆盖官方简体中文版数据。在明确数据权利前，不将官方完整效果文本直接提交到仓库。
