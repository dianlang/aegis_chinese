# Aegis DTCG 中文社区数据库与汉化工具

非官方、**仅限非商业用途**。DigiCamoe 已向项目维护者表示在不盈利的条件下可使用；保留来源链接及署名。此授权不等于拥有卡牌本身的著作权，也不意味着官方 Aegis 可以直接采用相同再许可条款。

此项目分为两条独立的数据链：`data/cards/*.json` 供 Tampermonkey 读取中文卡文；`data/ui-overrides.json` 用来生成可供 Aegis 官方合并的简体中文界面文案。绝不把 DigiCamoe 的整库卡文直接塞入 Aegis 的 `zh-CN.ts`。

## 用户使用

安装对应版本的 Aegis DTCG 中文优化 Tampermonkey 脚本（v0.3.3；目前单独提供下载，尚未上传到本仓库根目录）。新版默认指向本仓库：

`https://raw.githubusercontent.com/dianlang/aegis_chinese/main/data`

中文卡文优先从 GitHub 静态 JSON 加载，未收录的卡默认保留英文，**不会访问 DigiCamoe**。已缓存卡可以离线使用，游戏规则由 Aegis 自身执行。

## 一次性两小时初始化（截至 2026-10-14）

仓库已有 **约 4,474 个卡号的真实详情 URL 索引**（先前成功扫描了 97 个卡包），但已发布中文卡文仍需要继续采集。首次运行不再按“每天 600 张”限制，而是对当前已索引的所有卡号执行一次有截止时间的导入。

- 在 [Bulk initial Chinese card database bootstrap](https://github.com/dianlang/aegis_chinese/actions/workflows/bootstrap.yml) 点击 **Run workflow**，分支选 `main`。工作流总超时 119 分钟；其中剩余卡包索引最多约 3 分钟，正文读取最多 110 分钟，之后自动校验并推送 GitHub。
- 执行 `tools/fast_bootstrap.py`：全局每秒最多开始 **1 个 HTTP 请求**、最多 **4 个同时等待响应**，每批 40 条增量写入文件；不会下载卡图；HTTP 429 立即停止；HTTP 5xx 与网络故障有限退避重试后暂停或递延。若两小时内无法取得所有有效卡文，会提交已完成数据，余下部分以后续运行继续。
- Windows 用户建议使用下面的本地启动器，抓取数据先存在本地、经过校验后再提交 GitHub。
- 只有公开卡包目录已经扫描完毕、索引至少 4,000 张且 **索引里的每张卡均已成功入库**时，才自动把 `data/bootstrap.json` 的 `enabled` 设为 `false`。达不到 100% 就会显示剩余数量，不会宣称全量完成。
- 批量期 `Daily 20-card maintenance (after bootstrap)` 自动跳过。批量完成后，每天北京时间 12:20 自动检查最多 20 张，并检查新增卡包。

数据字段包括卡种、罕贵度、颜色、等级、登场与使用费用、DP、形态、属性、类型、进化条件、主效果、进化源效果及安防效果。真实卡牌页面中不存在的字段不会伪造；网站若限制自动抓取，请及时停止并向维护者取得批量数据授权。**两小时是执行上限，不是承诺一定完整采集 4400 张**。

---
## 抓取失败与自动恢复

- HTTP 404：先从真实卡包索引中尝试最多 8 个候选印刷版本，不猜测 URL。Windows 一键程序启动前会从过去失败的卡中选最多 4 个卡包，按每 4 秒最多 1 个请求重新检查卡包页面，并刷新真实卡牌链接；每个卡包 24 小时最多检查一次。若最近 16 张的结果中有至少 8 次 404，程序暂时停止，避免将源站异常误认作大量卡牌下架。个别 404 最快隔 24 小时才再次进入抓取队列。
- 临时 `URLError`、超时、连接中断：最多重试两次，记录具体异常类型；某张卡暂时无法读取时标为 `deferred`，连续 3 张发生网络异常才暂停整个批次。
- HTTP 429：立即中止并保存数据。单张卡的临时 5xx：共享限流器为全部线程施加 15 秒、45 秒的冷却，最多重试两次；持续 5xx 标记为暂缓，一小时后再考虑重试。最近 20 张若有至少 3 次持续 5xx 或连续 3 张连接失败，则暂停整批，保留断点。所有请求仍经过全局频率限制。
- GitHub `main` 在抓取时发生变化：现在会先保存完整 JSON 检查点，重新拉取最新 `main`，按卡号合并后提交；最多重试四次。已人工校对（`reviewStatus: verified`）的卡文优先保留。
- 每次 Actions 工作流会上传可保留七天的 `digicamoe-harvested-data` 备份；即使最终提交失败，也可以从本次运行记录的 **Artifacts** 下载。此前失败的批次没有启用这一备份，不能声称那批数据已入库。

## Windows 一键本地建库（当前推荐）

1. 用 [GitHub Desktop](https://desktop.github.com/) 克隆 `https://github.com/dianlang/aegis_chinese`（推荐，完成后更容易提交），或者在 GitHub 仓库主页选择 **Code → Download ZIP** 并解压完整项目。
2. 安装 Python **3.9 或以上**，确保运行 `py -3 --version` 能显示版本。首次运行会自动安装 `beautifulsoup4`。
3. 在项目文件夹内双击 **`scripts/bootstrap_local_windows.bat`**。它直接使用 `data/index/*.json` 中已扫描的卡号，不会为了已有的约 4,474 张卡重复扫描卡包。
4. **稳定优先**：默认全局每 2 秒最多发起 1 次请求、同时最多 2 个网络请求，单次最多运行约 110 分钟；程序自动尝试小范围 404 索引修复，再抓取卡文。过程显示 `PROGRESS` / `RETRY` / `MISS` / `DEFER`，日志保存在 `logs/local_bootstrap_*.log`。
5. 关机、断网或 DigiCamoe 出现持续 5xx、429 时不要反复猛试。已完成的卡文存放在 `data/cards/*.json`；之后重新双击即可依据 `data/sync-state.json` 继续。
6. 在终端运行 `py tools/validate_database.py`（一键程序结束时也会自动运行）。检查 `data/manifest.json` 的 `publishedCardCount` 后，用 GitHub Desktop 提交变更并推送到 `main`；如果使用普通 ZIP 下载，请通过 GitHub Desktop 先克隆再复制修改后的 `data/`，不要仅上传日志。

**排查方法**：如果某张卡连续出现 404，可以在项目根目录运行 `py tools\\repair_404_links.py --dry-run` 先查看待修复的卡包（不联网），也可以在浏览器手动打开 `data/index/AUTO.json` 中该卡的实际 URL。只对照页面确认，不要自行批量猜测新 URL。遇到持续 HTTP 500 或 429 时，等待源站恢复或维护者提供数据接口比提高频率更合理。

**注意**：本地运行不会直接把文件上传 GitHub，油猴插件必须在你推送 `data/cards/*.json` 后才能使用新卡文。初始化期间已暂停 GitHub 的自动批量抓取以避免冲突；如需重新启用云端批量抓取，可以手动在 Actions 启动。每天 20 张的维护任务在首次建库完成前仍跳过。

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

**日常维护限制**：日常任务单线程、请求间隔至少 6 秒；HTTP 429/5xx 或网络错误停止。完整初始建库使用独立的受限并发程序。索引只来自真实公开目录。

## GitHub Actions 自动更新

初次建库目前**优先使用 Windows 本地启动器**。云端 [Bulk initial Chinese card database bootstrap](https://github.com/dianlang/aegis_chinese/actions/workflows/bootstrap.yml) 已暂停自动定时运行，仍可人工启动；请不要与本地任务同时运行。

完成后启用 [Daily 20-card maintenance](https://github.com/dianlang/aegis_chinese/actions/workflows/sync.yml)：每天北京时间 12:20 最多检查 20 张。首次 P-001～P-020 在线抓取已验证，新增索引器与完整字段尚待真实任务验证。

## 授权数据导入器与中文覆盖率报告

不依赖爬虫，无需访问 DigiCamoe。等待维护者明确授权并提供数据文件后再执行正式导入；在此之前可以用模拟数据测试预览。

在仓库根目录运行：

~~~bat
REM 生成按卡包统计的中文覆盖率报告（只读取本地 JSON，不联网）
py tools\coverage_report.py

REM 预览 CSV / JSON 导入，不会改动数据库
py tools\import_dataset.py "授权数据.csv" --source-label "获授权的数据提供方"

REM 明确取得公开再分发许可、预览无报错后，才正式导入
py tools\import_dataset.py "授权数据.csv" --source-label "获授权的数据提供方" --apply --permission-confirmed

REM 校验并重新生成覆盖率
py tools\validate_database.py
py tools\coverage_report.py
~~~

导入器支持 UTF-8 / UTF-8 BOM 的 CSV 和 JSON，兼容按卡号索引的 JSON 对象或数组。常见字段别名包括编号/cardId、名称/name、能力/main、进化源能力/inherited、安防能力/security。可以使用 --mapping mapping.json 自定义字段名，或用 --encoding gb18030 处理旧 CSV。默认只填充缺失字段；如需替换未经人工校对的旧文本，额外加 --overwrite-unverified。

- 人工校对保护：reviewStatus 为 verified 的数据绝不自动覆盖。重复卡号冲突、错误卡号、非中文卡文、不存在真实索引链接的记录会报错；出现错误时整个批次不会写入。
- 来源区分：记录中的 url 是现有真实卡牌详情页的引用，新增 translationSource 字段单独记录中文译文实际的授权来源，不会伪造 DigiCamoe 链接。
- 覆盖率输出：data/coverage.json（机器可读）、reports/COVERAGE.md（GitHub 阅读）、reports/coverage_missing.csv（缺失卡号及失败原因）。
- 统计口径：相同卡号的异画只算一张，分别报告索引数量、已存储、含中文效果、仅元数据、缺失数量。卡文已入库不代表游戏内触发提示都完成翻译。

完成导入后检查数据库并通过 GitHub Desktop 提交 data/ 与 reports/ 的变化。报告不含其他网站授权，也不会替你申请数据使用权。

---

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

GitHub 仓库主页选择 `Code` → `Download ZIP`，解压后 Windows 用户可双击 `scripts/bootstrap_local_windows.bat` 本地批量采集中文卡文；也可双击 `scripts/update_windows.bat` 进行少量更新，或双击 `scripts/export_upstream_windows.bat` 生成官方 UI 汉化副本。首次运行需要 Python 3.9+ 和 pip。

**发布数量以 `data/manifest.json` 的 `publishedCardCount` 为准。首次全量导入采用最多两小时的任务时间预算；尚未验证能否在真实上游响应条件下完成所有卡牌。**
