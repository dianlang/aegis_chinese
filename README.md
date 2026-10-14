# Aegis DTCG 中文社区数据库与汉化工具

非官方、**仅限非商业用途**。DigiCamoe 已向项目维护者表示在不盈利的条件下可使用；保留来源链接及署名。此授权不等于拥有卡牌本身的著作权，也不意味着官方 Aegis 可以直接采用相同再许可条款。

此项目分为两条独立的数据链：`data/cards/*.json` 供 Tampermonkey 读取中文卡文；`data/ui-overrides.json` 用来生成可供 Aegis 官方合并的简体中文界面文案。绝不把 DigiCamoe 的整库卡文直接塞入 Aegis 的 `zh-CN.ts`。

## 用户使用

安装对应版本的 Aegis DTCG 中文优化 Tampermonkey 脚本（v0.3.1；目前单独提供下载，尚未上传到本仓库根目录）。新版默认指向本仓库：

`https://raw.githubusercontent.com/dianlang/aegis_chinese/main/data`

中文卡文优先从 GitHub 静态 JSON 加载，未收录的卡默认保留英文，**不会访问 DigiCamoe**。已缓存卡可以离线使用，游戏规则由 Aegis 自身执行。

## 一次性两小时初始化（截至 2026-10-14）

仓库已有 **4,364 个卡号的真实详情 URL 索引**（先前成功扫描了 97 个卡包），但已发布中文卡文仍需要继续采集。首次运行不再按“每天 600 张”限制，而是对当前已索引的所有卡号执行一次有截止时间的导入。

- 在 [Bulk initial Chinese card database bootstrap](https://github.com/dianlang/aegis_chinese/actions/workflows/bootstrap.yml) 点击 **Run workflow**，分支选 `main`。工作流总超时 119 分钟；其中剩余卡包索引最多约 3 分钟，正文读取最多 110 分钟，之后自动校验并推送 GitHub。
- 执行 `tools/fast_bootstrap.py`：全局每秒最多开始 **1 个 HTTP 请求**、最多 **4 个同时等待响应**，每批 40 条增量写入文件；不会下载卡图；HTTP 429、服务器 5xx 或网络故障即停止。若两小时内无法取得所有有效卡文，会提交已完成数据，余下部分以后续运行继续。
- Windows 用户可以双击 `scripts/bootstrap_windows.bat`，本地同样采用两小时预算，完成后需自行检查并推送 GitHub。
- 只有公开卡包目录已经扫描完毕、索引至少 4,000 张且 **索引里的每张卡均已成功入库**时，才自动把 `data/bootstrap.json` 的 `enabled` 设为 `false`。达不到 100% 就会显示剩余数量，不会宣称全量完成。
- 批量期 `Daily 20-card maintenance (after bootstrap)` 自动跳过。批量完成后，每天北京时间 12:20 自动检查最多 20 张，并检查新增卡包。

数据字段包括卡种、罕贵度、颜色、等级、登场与使用费用、DP、形态、属性、类型、进化条件、主效果、进化源效果及安防效果。真实卡牌页面中不存在的字段不会伪造；网站若限制自动抓取，请及时停止并向维护者取得批量数据授权。**两小时是执行上限，不是承诺一定完整采集 4400 张**。

---
## 本地更新（Windows）

安装 Python 3.9 以上（推荐 3.11）后，在仓库根目录运行：

```bat
py -m pip install -r requirements.txt
py tools\sync_cards.py --dry-run --limit 20
py tools\sync_cards.py --limit 20 --delay 6 --time-budget-minutes 25
py tools\validate_database.py
```

也可以指定单张卡：`py tools\sync_cards.py --card P-248 --limit 1 --force`。

**抓取安全限制**：所有采集模式单线程、间隔至少 6 秒；HTTP 429、5xx、网络错误停止。失败卡至少 7 天不自动重试，已采集卡按需补全元数据。采集数据基于索引中已知的 URL，不会遍历不存在的卡号。

## GitHub Actions 自动更新

初次建库请使用 [Bulk initial Chinese card database bootstrap](https://github.com/dianlang/aegis_chinese/actions/workflows/bootstrap.yml)：先发现卡包真实链接，再每日最多处理 600 张卡，支持断点续跑，完成后自动关闭。

完成后启用 [Daily 20-card maintenance](https://github.com/dianlang/aegis_chinese/actions/workflows/sync.yml)：每天北京时间 12:20 最多检查 20 张。首次 P-001～P-020 在线抓取已验证，新增索引器与完整字段尚待真实任务验证。

## 导出 Aegis 官方汉化副本

```bat
py tools\export_upstream.py
```

仓库中的 `Build upstream Aegis zh-CN patch` 工作流也会自动构建，并在 [Actions](https://github.com/dianlang/aegis_chinese/actions) 运行详情中提供 `Aegis-zh-CN-upstream-PR` 下载包。其运行已验证成功，但补丁合并前仍需人工审阅。

本地工具拉取 Aegis `develop` 分支原始 `apps/web/src/i18n/zh-CN.ts`，仅合并 `data/ui-overrides.json` 中的人工校对内容，校验占位符，输出：

- `dist/upstream/apps/web/src/i18n/zh-CN.ts`
- `dist/upstream/zh-CN.patch`
- `dist/upstream/README_PR.md`

如本地有原站文件，使用 `--source path/to/zh-CN.ts` 离线生成。人工审阅后 Fork Aegis 官方仓库，以 `develop` 为目标发起 PR；不应自动向官方推送未经审核的卡文或界面修订。

## 导入已有用户缓存

插件的「导出本机已有中文卡文」功能可导出个人浏览器中已抓取的数据；导入命令：

```bat
py tools\import_cached_cards.py aegis-cn-cached-cards-2026-10-13.json
```

运行 `py tools\validate_database.py` 再提交；请先审阅文本，保留 DigiCamoe 的来源 URL。不要提交用户隐私、玩家数据、Cookie 或登录信息。

## 数据源声明

- [DigiCamoe](https://app.digicamoe.cn/)：卡牌简中与日版中文译文，非商业使用。
- [Aegis 开源项目](https://github.com/vinicius3333/aegis-digimon-tcg)：游戏代码与界面语言文件。
- `data/index/P.json`：2026-10-13 扫描快照，249 个卡号，部分失败，因此不是全量覆盖。

## 下载整套本地程序

GitHub 仓库主页选择 `Code` → `Download ZIP`，解压后 Windows 用户可双击 `scripts/update_windows.bat` 更新中文卡文，或双击 `scripts/export_upstream_windows.bat` 生成官方 UI 汉化副本。首次运行需要 Python 3.9+ 和 pip。

**发布数量以 `data/manifest.json` 的 `publishedCardCount` 为准。首次全量导入采用最多两小时的任务时间预算；尚未验证能否在真实上游响应条件下完成所有卡牌。**
