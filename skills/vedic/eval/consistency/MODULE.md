> 本文件是 `vedic` skill 的 **eval/consistency** 模块。文中相对路径（resources/、scripts/）以本模块目录 `eval/consistency/` 为根；跨模块引用写作 `<模块>/...` 或「<模块> 模块」，指 vedic skill 下的同名目录，调用方式见根目录 SKILL.md。

# 跨模块 一致性 harness

检查 **core / career / love / soul** 在**确定性事实**上 ①忠于源数据（`chart_data.json`）、②彼此不打架。
**不评解读质量。**

## 何时用 / 不用
- **用**：确认四个解读模块事实不矛盾、改完某模块验证事实没塌、排查 skill 间说法冲突。仅在用户明确要求时进入（根 SKILL.md 路由表）。
- **不用**：评"解读写得好不好"——那没标准答案，靠验前事反馈 + 人的判断。验前事反馈只说明一组探针与用户反馈对得上多少，
  不是预测准确率（`shared/validation_scoring.md`）。

## 为什么是这个、而不是"解读质量评分"
解读层没有标准答案——"土星落 7 宫对婚姻意味着什么"无法 A/B 打分，更不能用 LLM-judge 假装能打。
但这四个模块都读同一份盘数据，所以它们引用的**确定性事实**（AK、各宫主、行星星座/尊贵度、D9 上升、Dasha）
**必须一致且忠于源数据**。这是解读层里唯一能被确定性检验的东西，而且逐个看单模块根本看不出来。

## 查两件事（都通过 `check_consistency.py`，比对是纯算术）
- **保真度 fidelity**：某模块自己把 10 宫主读错 / 把尊贵度说反 / AK 选错（偏离源数据）。
- **跨模块一致性**：core 说 10 宫主火星、career 说土星（四个模块互相矛盾）。

## 状态与退出码（vedic 5.1 统一口径，正本 `shared/data_contract.md` §7）

| 状态 | 退出码 | 含义 |
|---|---|---|
| 通过 | 0 | 实际比较了 ≥1 条事实，无矛盾，无待复核 |
| 失败 | 1 | 有保真度或跨模块矛盾 |
| 未完成 | 2 | 实际比较的事实数为 0（空提取、字段与源数据对不上、目录里没有 claims），或有抽取待复核未清空 |

- 每次汇报都写实际比较了多少条事实（脚本末尾「实际比较：对源数据 N 条 · 跨模块共同事实 M 条」），不能只报"通过"。
- **空提取 = 未完成**，不算通过；待复核没清空 = 未完成。
- 用法错误（没给参数）脚本退出 4：检查没有执行，不属于上面三种状态，修好参数重跑。

## 数据流
```
chart_data.json ──蒸馏──▶ canonical_facts.json   (源数据真相，单一真相；字段路径见 schema.md)
各模块 输出 ──抽取确定性主张（Claude，或 jev_extract_claims.py）──▶ skill_claims_<skill>.json
        │
        ▼  check_consistency.py
   ① 各 claims vs canonical（保真度）   ② 多 claims 互比（跨模块）
```
抽取那步（prose → JSON）可以让 Claude 做，也可以用 Jev 做闭集抽取（见下「用 Jev 抽取」）；**比对那步始终是确定性脚本**。

## 工作流程（一张盘）
1. **蒸馏 canonical_facts.json**：5.1 起直接从 `chart_data.json` 蒸馏，字段路径见 `schema.md`
   （`chart.planets.*.sign`、`chart.house_lords`、`chart.karakas.7k`、`chart.d9.Lagna`、`chart.dashas` 等）。
   先跑 `calculator/scripts/check_chart.py --dir <目录>`，失败项先修。只有旧版 `structured_data.md`、没有 JSON 时，
   先用 `calculator/scripts/import_legacy_md.py` 导入，或按 `schema.md` 从 Markdown 手工蒸馏。
   ⚠️ **尊贵度一律用 `cutil` 从行星星座推，宫主用 `cutil` 从 Lagna 推出来再与 `chart.house_lords` 对一遍**，
   别照抄盘数据里写好的尊贵度——旧盘导入的数据带着 reader 当时的提取结果，标错了照抄就会连"源数据"一起错，检查器永远抓不到。
   （实测：一份真实 reader 输出把 Virgo 的 Jupiter 标成了落陷，core、career、校时报告都沿用了；用 cutil 推出来的 canonical 一比就露出来。）
   宫主推出来与 `chart.house_lords` 不一致 → 先查盘数据，不往下跑。
2. 这张盘依次跑 `core 模块` / `career 模块` / `love 模块` / `soul 模块`。
3. 从每个 skill 的输出里抽它**明确陈述为事实**的确定性项 → `skill_claims_<skill>.json`
   （按 `schema.md`，Claude 做）。**只抽事实**（"10 宫主是火星""土星入庙"），**不抽解读**。
   - 或用 Jev：`python3 jev_extract_claims.py <该模块 的输出.md> --skill <skill> --out fixtures/<chart>/skill_claims_<skill>.json`。
     抽取器退出码 3 = 有待复核项（claims 里 `_extractor.pending` 列出是哪几项）：看 `jev_review_<skill>.json` 里的依据句子，
     确认后把值手动补进 claims，再从 pending 里删掉那一项。dasha 仍由 Claude 抽（`--keep-dasha` 保留已抽好的）。
     抽取器其它退出码：0 无待复核、2 输入错误、4 没找到密钥（未抽取）、1 调用失败。它是抽取工具，不是检查脚本，状态以 `check_consistency.py` 为准。
4. 跑检查：
   ```bash
   python3 check_consistency.py fixtures/<chart>/canonical_facts.json fixtures/<chart>/
   ```
   目录模式会自动扫该目录下所有 `skill_claims_*.json`。按上面的状态表读结果，并写明实际比较的事实数。

## 用 Jev 抽取（可选）
**为什么**：Claude 自由抽取会把修辞当事实，而且每次抽的结果会抖——在"出现任何新矛盾就 revert"的回归门里，抽取本身的抖动会造成误报。
Jev 做闭集抽取：每个字段一道选择题，答案只能是行星 / 星座 / 尊贵度，外加「未陈述」「前后不一」「其他说法」，编不出别的值；
没把握的一律**待复核、不写进 claims**。

**怎么做**：代码先把报告里相关的句子捞出来（带所在小节标题，表格行带表头，"它落在……"这种代词句会连上一句一起带），
再逐字段问：L10 说成了哪颗星？Saturn 的本命落座说成了哪个星座？尊贵度是哪一档？第一名 ≥ 0.70 且领先 ≥ 0.30 才写进 claims。

**纪律**
- 抽取器**看不到** canonical_facts 和别的 skill 的 claims，只抽"这份报告说了什么"——说错了照错的抽，错不错交给检查器。
- 只抽本命盘（D1）事实；分盘里的落座 / 尊贵度 / 宫主不算（D9 上升除外）；假设、否定、一般规律不算；不许把"落 10 宫"换算成星座。
- **待复核没清空，`check_consistency.py` 不给通过**（未完成，退出码 2）——待复核的字段可能正好藏着矛盾。
- **检查器报了矛盾，revert 之前先看 `jev_review_<skill>.json` 里那个字段的依据句子**，确认是 skill 说错了、不是抽错了。
- 不覆盖 dasha（日期对 Jev 只是文字）。

**先跑金标准再用**：`python3 jev_claims_eval.py`（有密钥时和字符串基线并排跑；`fixtures/jev_gold/` 有 19 段带陷阱的报告片段：
AK 与 AmK 同句、D9 落座、"落在宫里"≠宫主、假设句、一般规律、前后说法不一、表格写法、Neecha Bhanga 句、并列候选上升……）。
先看**错值 + 误抽**（会造假矛盾或盖掉真矛盾），再看待复核数（只是要人看）。
这套例子上（2026-09 实测，jc-v0.2）：字符串基线 错值 0、误抽 1（踩了 D9 入旺的陷阱）、待复核 11、召回 69%；
Jev 错值 0、误抽 0、待复核 3、召回 94%，连跑两次结果相同。
拿两份真实的历史输出试过：一段 core 审计原文，连跑 3 次都是 9 项对 8 项、0 错值 0 误抽（漏的那项是句子里没点名行星）；
一份校时报告（表格里并列两个候选上升），0 错值，但 3 次里有 2 次把**弃用那一栏**的宫主抽了进来——
**别拿并列候选盘的报告（校时报告之类）来抽**，这套只管 core / career / love / soul。
**Jev 值得用的标准：错值 + 误抽不多于基线，同时待复核明显更少。** 达不到就继续用 Claude 抽、人扫一眼。

**演示**（不需要密钥，用字符串基线测流程）：
```bash
mkdir -p /tmp/demo && cp fixtures/example_chart/canonical_facts.json fixtures/example_chart/skill_claims_core.json \
  fixtures/example_chart/skill_claims_love.json fixtures/example_chart/skill_claims_soul.json /tmp/demo/
python3 jev_extract_claims.py fixtures/jev_demo/career_report.md --skill career --out /tmp/demo/skill_claims_career.json --baseline
python3 check_consistency.py /tmp/demo/canonical_facts.json /tmp/demo/
```
`career_report.md` 是示例 career claims 的散文版，同样把 L10 写成 Saturn、把 Saturn 写成落陷；抽出来后检查器照样判失败在这两处。
有密钥时去掉 `--baseline` 即走 Jev。

**配置**：密钥放 `TYPESAFE_API_KEY`（或 `TYPESAFE_KEY_FILE` 指向的文件、`~/.config/typesafe/key`）；模型版本固定在
`jev_claims_questions.yaml`（`JEV_MODEL` 可覆盖）；需要 PyYAML。

## 改解读模块 时当回归门
0. **baseline**：5-10 张盘，每张跑四个模块→抽 claims→`check_consistency` 应全部「通过」（退出码 0），写 `iteration-log.md`，
   记下每张盘实际比较的事实数。**未完成不算全绿**；比较事实数明显少于 baseline，说明抽取或 canonical 漏了，先查再比。
   **抽取器要固定**：baseline 和之后每一轮用同一个抽取器（都用 Claude，或都用同一 Jev 模型 + 同一题库版本），
   否则抽取的差异会被当成 skill 退步。
1. 改某个 skill 一处话术/规则。
2. 对同一批盘重抽 claims→重跑。
3. 出现**任何新的事实矛盾**（失败）→ **revert**（事实退步零容忍）；全部通过 → 事实地基没塌，再凭判断看解读。

跨多张盘反复出现的同类矛盾（如 career 总把某宫主读错）→ 提名成对那个 skill 的明确改动。

## 与 eval/reader 的关系
**提取正确（`eval/reader` 管）→ 四个模块都忠于提取（本模块管）→ 解读才站在可靠地基上。**
解读本身好不好——验前事反馈 + 人的判断，工具测不了，也不该假装能测。

## 示例（解压即可跑）
`fixtures/example_chart/` 含 `canonical_facts` + 四份 `skill_claims`（career 故意注入 2 个矛盾）：
```bash
python3 check_consistency.py fixtures/example_chart/canonical_facts.json fixtures/example_chart/
```
应判**失败**（退出码 1）并指出 career 的两处矛盾（10 宫主、土星尊贵度）——既是保真度也是跨模块命中，演示检查器有牙齿。

## 文件
- `check_consistency.py` — 保真度 + 跨模块 检查（通过 0 / 失败 1 / 未完成 2，报告实际比较的事实数）
- `jev_extract_claims.py` — Jev 闭集抽取（`--baseline` 字符串基线、`--dry-run` 看要问的题、`--check` 校验题库）
- `jev_claims_questions.yaml` — 抽取题库：行星 / 星座 / 尊贵度的选项与别名、检索线索、判定门槛
- `jev_claims_eval.py` + `fixtures/jev_gold/cases.yaml` — 19 段带陷阱的金标准例；Jev 与字符串基线并排比
- `fixtures/jev_demo/career_report.md` — 演示用散文报告（与示例 career claims 同样的两处注入错误）
- `cutil.py` — 宫主/尊贵度规则**单一来源**
- `gen_consistency_example.py` — 可选，复用 `eval/reader` 示例盘造一份可跑通示例
- `schema.md` — `canonical_facts.json` / `skill_claims_*.json` 字段定义，及从 `chart_data.json` 蒸馏的字段路径
- `methodology.md` — 深入说明 + 限制
- `iteration-log.md` — 迭代日志模板
- `fixtures/example_chart/` — 可跑通示例

## 限制（详见 methodology.md）
- **fixture 是合成示例盘**（`example_template_1990`，career 的错误是手工注入的），只能测抽取与事实一致性这套流程本身，
  **不能当作数值准确性的外部验证**。
- **canonical 来自被检查的同一份盘数据**：本模块只看模块是否忠于 `chart_data.json`，`chart_data.json` 本身算错（岁差、节点、Dasha 起点等），这里查不出。
  涉及数值准确性的声明（如"排盘与 JHora 一致"）需要独立基准：用 JHora 等外部软件导出、按相同设置核对过的真盘，走 `eval/reader` 的 B 层或另做对照。
- 只查确定性事实（AK/宫主/星座/尊贵度/D9 上升/Dasha）；尊贵度只到 `Exalted/Debilitated/Own/Other` 四档；
  `canonical_facts` 字段应按四个模块实际引用的事实扩（要查 D10 上升、AL/UL、特定 Karaka，加进 schema + canonical + 各 claims 即可）。
- claims 抽取是 LLM 辅助步骤，抽完最好扫一眼确认抽的是"陈述为事实"的项、而非把解读修辞误当事实。
  用 Jev 抽取时：中文报告上的准确度要以你自己跑 `jev_claims_eval.py` 的结果为准；判定门槛是暂定的；不覆盖 dasha；
  报告里若夹着说明性文字（比如"这里故意写错了 L10"），也会被当成报告内容抽——抽之前别往报告里加批注。
