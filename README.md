# Aegis DTCG 中文社区数据库与汉化工具

非官方、**仅限非商业用途**。DigiCamoe 已向项目维护者表示在不盈利的条件下可使用；保留来源链接及署名。此授权不等于拥有卡牌本身的著作权，也不意味着官方 Aegis 可以直接采用相同再许可条款。

此项目分为两条独立的数据链：`data/cards/*.json` 供 Tampermonkey 读取中文卡文；`data/ui-overrides.json` 用来生成可供 Aegis 官方合并的简体中文界面文案。绝不把 DigiCamoe 的整库卡文直接塞入 Aegis 的 `zh-CN.ts`。

## 用户使用

安装对应版本的 Aegis DTCG 中文优化 Tampermonkey 脚本（v0.3.1；目前单独提供下载，尚未上传到本仓库根目录）。新版默认指向本仓库：

`https://raw.githubusercontent.com/dianlang/aegis_chinese/main/data`

中文卡文优先从 GitHub 静态 JSON 加载，未收录的卡默认保留英文，**不会访问 DigiCamoe**。已缓存卡可以离线使用，游戏规则由 Aegis 自身执行。

## 本地更新（Windows）

安装 Python 3.9 以上（推荐 3.11）后，在仓库根目录运行：

```bat
py -m pip install -r requirements.txt
py tools\sync_cards.py --dry-run --limit 20
py tools\sync_cards.py --limit 20 --delay 6
py tools\validate_database.py
```

也可以指定单张卡：`py tools\sync_cards.py --card P-248 --limit 1 --force`。

**抓取安全限制**：只读取 `data/index/*.json` 已收录的卡详情 URL；一次默认检查 20 张、每张最多两个 URL、单线程、每次请求间隔至少 6 秒，HTTP 429/5xx 或网络故障立即停止，不自动重试。`data/sync-state.json` 记录成功、失败和更新时间。7 天内不会反复请求失败卡；已有卡文默认 45 天内不重复抓取。可以增量导入其他卡包索引，格式和 `data/index/P.json` 相同。

**重要**：目前已提供 P 卡索引 249 张，但在本仓库上线前并未实际批量抓取中文卡文；`data/cards/P.json` 初始是 `{}`。索引中部分候选 URL 可能失效。更新工具会严格核对卡号、效果段落和中文字符，失败不会写入卡文。

## GitHub Actions 自动更新

仓库 [Actions](https://github.com/dianlang/aegis_chinese/actions) 中的 `Weekly Chinese card text sync` 工作流预定每周一 UTC 04:20（上海时间周一 12:20）自动处理最多 20 张；也可 `Run workflow` 手动执行。工作流写入 `data/cards/`、`data/manifest.json` 和 `data/sync-state.json`，不会下载卡图。

自动运行的单次上限是 20 张卡，手动执行也默认使用相同安全限制。可双击 `scripts/update_windows.bat` 在 Windows 上本地更新，再自行提交 git。若站方要求暂停同步，直接禁用 `Weekly Chinese card text sync` workflow。首次线上执行要检查 Actions 日志是否成功解析真实页面；目前仅以离线 HTML 样本测试，**未宣称已验证真实站点抓取**。

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

**当前发布状态：P 卡链接索引 249 张；已发布卡文数量以 `data/manifest.json` 的 `publishedCardCount` 为准。自动采集流程尚未完成真实 DigiCamoe 页面端到端验证。**
