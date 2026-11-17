# vedic skill 变更记录

## v5.3（2026-11-16）新增 prashna 模块（吠陀卜卦）

来源：上游 `CNWU16/vedic-astro-skills` 的 `skills/vedic-prashna`（提交 `9b72c1d`，2026-11-16）。5.1、5.2 的已知限制里写的“上游 vedic-prashna 未收入”，这一版收入并改到本 skill 的目录、引擎与协议。回归用例从 33 项加到 37 项，结果见 `tests/RESULTS.md`。

**本命侧零变化**：引擎版本 `calculator-0.9.2+vedic5.2`、规则版本 `vedic-5.2` 都不变。旧盘不用重排，旧分析不用复核，`check_freshness.py` 不会因为这次升级提示任何东西。

### 新模块做什么
- 用提问时刻（秒级）与提问地点起一张独立的提问盘，回答一件具体的事：成不成、某人会不会动、大致什么时候。不需要出生信息，不读本命盘。
- 技法定死为三层，各答各的：
  1. **标准层**定倾向：*Shatpanchasika*（Ayer 译注）为主文本，经 KN Rao／BVB 实践筛选，有条件收入 *Prasna Marga*。模型拆题写取象单，脚本按逐条有出处的规则计成事账，定偏成／持平／偏不成。这一层是上游的工作，规则与判定脚本原样移植。
  2. **时间副层**：只在偏成、持平时给大致时间。
  3. **Tajika 过程层**：*Tajika Nilakanthi* 十六 Yoga，答“两边现在在靠近还是走远”。
- 路由、例外登记与脚本表写进根 SKILL.md；`shared/capabilities.md`、`shared/permissions.md` 各加一行。

### 与上游不同的地方（以后同步上游时对照这一节）
1. **Tajika 从“默认关闭、明说才跑”改成随判定一起跑**，并在判读单里单列一节。权限没有放宽：不进成事账、不改内部档、不写成“两套方法互相确认”（它在上游仍标研究验证版，这个标签保留）。它与成事账方向不同时按“两个子问题各有答案”分开讲，写法在 `prashna/resources/judgment-writing.md` §3 第 10 条。文件名 `tajika-optional.md` 改为 `tajika-layer.md`。
2. **新增 `prashna/scripts/run_prashna.py`**：取象单写好后一条命令跑判定、时间副层、过程层（只起子进程，三层之间的隔离不变）。起盘时另写 `prashna_meta.json`，后续脚本不用再手抄时刻、经纬度和宫主。改取象单重跑时，不再适用的旧时间／过程产物改名为 `*.superseded.md`。
3. **判读单写法**：先答后证（标题一句话答所问，倾向用白话直说，每节第一句是结论）；默认篇幅 1,500–2,500 字（上游 3,000–5,000）；聊天里先给简版；每个卡点带对应做法，“现在能做什么”按 `shared/grounding_basic.md` 写。绝对断语、`rule_id`、状态码、输入精度仍不进给用户看的部分。
4. **没有移植**：KP 独立栈（1–249 数字起盘、Krishnamurti 岁差、Placidus 宫头；上游自己标未达生产级，岁差与宫制也和本 skill 的固定计算设置不同）；日文层 `ja-prashna.md`。本命交叉照上游保持失败关闭。
5. 文档里的“创始人某日定”是上游维护者的裁决，统一改写成“上游某日定”。

### 给共享引擎加的东西
- `engine.calculate_full_chart`、`to_jd` 与五个 PyJHora 包装多了 `second`（可带小数，默认 0）；`calculate_full_chart` 多了 `fold`；新增 `engine.local_instant`、`engine.instant_to_jd`。整张盘只本地化一次，各子模块的时刻都从同一个瞬间派生。这是照上游 engine v1.0 的“秒级瞬间”一项移植的。
- 只有 prashna 传秒。本命排盘入口照旧只收到分钟。验证：24 张随机本命盘改动前后整盘逐字节相同；同一组参数的 `chart_data.json` 除生成时间外相同、`structured_data.md` 零差异；回归 X19。
- 引擎返回值没有加键；提问盘的计算溯源（引擎版本、UTC 瞬间、岁差）只写在 prashna 这一侧。

### 没有照上游改的
- **Lagna 基准**。上游 v1.0 把 D1 Lagna 与 PyJHora 分盘 Lagna 统一到与桌面 JHora 一致的基准，这会移动已有本命盘的 Lagna（上游估计最多约 39″，D9 Lagna 约 0.1% 的盘换座），所以没有动（5.2“没有改的”里那条约 45″ 的口径差保持原样）。对提问盘的影响：Lagna 落在某条分盘分界前后一两秒钟以内时（实测一张盘是 1.0 秒，约占全部时刻的 0.4%），“Lagna 六分盘座主”表会隐藏并写明哪一层不一致，`P-I.4` 这一题不读 varga 一项。隐藏而不是给出一侧的结果，是上游原有的保护；上游测试里“分界两侧 0.2 秒都显示”的断言相应放宽为“5 秒外必须显示，0.2 秒内要么显示要么写明不一致”。
- 根本三角：本 skill 的引擎不单列 `moolatrikona`（记 `own_sign`）；prashna 两者都归“本座”，判定结果相同。

### 验证了什么，没验证什么
- 上游 12 项测试在本 skill 的引擎上通过（P1），其中判定算例复现了上游冻结的成事账（规则、方向、合计、内部档、能力层、行动链、限定语）。
- Tajika 过程层新写 4 项（P2）：出版接触几何（Journal of Astrology article 153）复现；*Hāyanaratna* 3.3 的 Sun–Mars `14° × 12 = 168 日` 正例；“靠近／走远”用 10 分钟后的真实星历位置独立复算，340 个接触（77 个含逆行星）全部一致；跑不跑过程层，标准层判定逐字节相同。
- 12 张带秒的提问盘用 astropy 独立复算位置（一次性核对，未进回归）：七曜与 Rahu 差 ≤1.0′（Saturn 最大，是 ERFA 内置星历自身的误差量级），Lagna 差 ≤0.41′。
- **没有验证**：标准层规则对现实的命中率（上游也没有命中率数据）；Tajika 十六 Yoga 的分类没有完整出版例盘，过程层保持研究验证版；判读单写法只按文档走过流程，没有独立场景试用记录。

### 许可
上游代码是 AGPL-3.0；上游另有 `COMMERCIAL_NOTICE`：指令文件（SKILL.md、resources/ 下的文件）个人使用、学习、修改自由，未经书面授权不得用于向第三方提供商业服务。`prashna/resources/` 沿用这一条。

## v5.2（2026-11-11）自检发现的问题修正

来源：对 5.1 做的一轮自检（自带回归 27/27 通过；另跑 240 张随机盘、逐项独立重算、异常输入）。回归用例从 27 项加到 33 项，结果见 `tests/RESULTS.md`；新增的 6 项在 5.1 上全部失败。引擎版本 `calculator-0.9.2+vedic5.2`，规则版本 `vedic-5.2`。

### 会改变已有结果的两处
1. **Chara Dasha 双主座（Scorpio：Mars/Ketu；Aquarius：Saturn/Rahu）取主规则**。5.1 写成"两主各数一次取年数较大者"，那是从 JHora 的 2 个双主数据点反推的。现在按出处改为五步：两主都在本座 12 年 → 只有一主在本座数到另一主 → 同座行星更多者 → 所落星座变动 > 固定 > 启动 → 年数较大者。出处：BPHS Dasha 章的共主规则（P.V.R. Narasimha Rao 2005 年在 Sri Jagannatha 讨论组逐条列出）、K.N. Rao《Predicting through Jaimini's Chara Dasha》的例盘（"与更多行星同座者较强"）。JHora 的 24 个对照点新旧规则都是 24/24。
   - 范围：240 张随机盘里 171 张（约七成）至少有一段年数变了；变的是 Scorpio / Aquarius 这两段的长度，以及大运顺序里排在它们之后各段的起止。Vimsottari 不受影响。
   - 规则只留一份：`timing/scripts/chara_dasha.py` 直接调用 `calculator/scripts/chara_dasha.py`。阅读版的 Chara 表多了「所数宫主」「双主座依据」两列；旧引擎排的表会在表头提示先重排。
   - PVR 说过 JHora 的「Chara dasa of K.N.Rao」选项判共主强弱并不严格照 K.N. Rao，而且可以手动指定 Sc/Aq 的主：双主座与 JHora 不一致时先看这项设置，按 `timing/resources/chara_dasha_rules.md` 的对照写法标注，不回退规则。
2. **标准时报时在 23:00 以后、且处于夏令时**：5.1 只把时间加了一小时、日期没有跟着进位，整张盘按前一天算（Moon 差一整天的行度，约 13–15°，Dasha 全错）。现在计算用日期与用户报的日期都记录，元信息同时写出。范围：`--clock-type 标准时` 且报时 23:00–23:59 的盘（中国大陆 1986–1991 夏令时期间）。

### 修掉的阻断
3. **第 19 宿**：引擎写 `Moola`，校验表是 `Mula`。任一行星落在这一宿，`check_chart.py` 就判「总体: 失败」（240 张随机盘里 62 张）；任一方 Moon 在这一宿，合盘直接拒绝生成。引擎统一写 `Mula`；旧盘里的 `Moola` 等异写按同一宿接受，真正的非法宿名仍判失败。
4. **夏令时切换点附近**：审计范围（如 ±15 分钟）跨过切换点时，整张盘算不出来，而且报的是一个用户没给过的时刻。现在审计按绝对时间前后挪。钟表上不存在的时刻报错并指路（多半是标准时 → `--clock-type 标准时`，这条路 5.1 走不通，现在可以）；钟表上出现两次的时刻必须用新参数 `--repeated-hour 夏令时|标准时` 指明，两次是两张盘。仅日期模式在切换当天也能排。

### 其他
5. **输入校验**：纬度超出 ±90、经度超出 ±180 直接拒绝（5.1 会排出一张盘并通过检查）；经纬度看起来传反时点明；经度与时区中央经线相差 50° 以上提示核对。时区名、日期、时间格式、带秒的时间、超出星历范围的年份都给出能照着改的提示，第一行写「输入有误」，与「计算失败」分开。元信息的出生地点一行注明括号内是「经度, 纬度」。
6. **校时**：`--source 校时` 现在同时要求 `--declared-min` 与 `--original-source`（文档一直写的是必填）。
7. **D2**：改用传统 Parasara Hora（行星只落 Cancer / Leo）。5.1 用的是 PyJHora 的 Uma Shambhu 变体，与代码注释和 reader 的「D2 必须 Cn 或 Le」不一致。D2 只在 JSON 里，没有模块读它，已有分析不受影响。
8. **Chara 时间线的日期**按出生地日期写（5.1 按 UT，东八区 08:00 前出生的盘第一段比出生日早一天）。
9. `dasha_query.py` 查到出生日之前的日期时加一行提示；`check_env.py` 给的修复命令带 `--target <工作目录>/vedic-calc-env`；功能身份表里 Moon 的 MT 宫一格不再写它不掌管的宫。
10. 措辞与正本对齐：`bhrigu_bindu.md`「命中率 ≥50% → 盘可信」、`cross_verification.md`「≥60% → 未来预测可信度高」改成适配度的说法（`shared/validation_scoring.md`：命中率不是预测准确率）。
11. 用法示例里的出生信息全部换成虚构测试盘（`build_chart.py`、`time_scan.py`、`merge_shadbala.py`、`calculator/MODULE.md`）。
12. `check_freshness.py` 在引擎或规则版本变了的时候，写明这次升级改了什么、哪些旧结论要复核（只有引用 Chara Dasha 时间线的时机结论），不让整份分析被当成作废。

### 升级后要做的
- 旧盘按原参数重排（chart_id 不变）。之前合并过 PDF Shadbala 的，重排后再合并一次。
- 写过「双系统确认 / 共振」的时机结论，按重排后的 Chara 表复核；Chara 表没变的盘不用动。

### 没有改的
- Chara 规则走到最后一步时，K.N. Rao 原书还要比两主度数；这里按年数较大者定（此时两主其余条件完全对称）。
- 上升用的岁差值与行星用的差最多约 45″（上升与 PyJHora 的分盘上升同一口径，行星用真位置口径），相当于 3 秒钟的出生时间，远小于最窄的 ±1 分钟误差，保持不动。
- HTML 报告仍在线加载 Google Fonts（国内网络下会回落到系统字体）。
- Shadbala、Chara AD、Yogini AD 仍然没有独立基准；与 JHora 的逐项对照没有做。

## v5.1（2026-10-11）稳定兑现 + 可追溯

验收重点：现有能力稳定兑现，每个结论都能追溯到当时用的数据与规则。实际测试结果见 `tests/RESULTS.md`。

### 变更清单
1. **规则权威顺序**：全局约束 → 数据与权限协议（`shared/*.md`）→ 模块流程 → 示例。删掉"冲突时以模块正文为准"；模块例外只认根 SKILL.md 的例外表。数据来源、背景权限、时间分辨率、分盘启用、过期数据、纠错各只留一份正本（`shared/`），模块里的副本改为引用；残留的"最高优先级"字样改为服从全局约束。
2. **数据契约**：排盘一次计算同时写 `chart_data.json`（机器读）和 `structured_data.md`（人读），两者同源（chart_id 一致，JSON→md 逐字可复现）。验证记录、user_context、分析记录分开存放。7K/8K 完整对照；时区、钟表时间性质、计算设置全部记录；精度分"声明 / 来源修正后 / 实际审计"三层，不再缺省写"±分钟级"；缺失值只有四种写法；Shadbala PDF 逐行合并（含 Ishta/Kashta，保留 calc 基准）；旧版 Markdown 可导入，缺项保持缺失、旧 ✅ 校验块与反馈节移出。
3. **盘面推导 ≠ 严格盲审**：三种模式（strict_blind / chart_derived / calibrated）、三阶段（初始推导 → 冻结 → 反馈复核 → 表达）。"见过反馈"与"用了反馈"分开。分析记录脚本强制先冻结再读反馈，改结论必须写"原结论 → 新证据 → 修改原因 → 新结论"并编号。用户说"不准"先按 `shared/error_correction.md` 分诊。
4. **校验器三状态**：通过 / 失败 / 未完成（退出码 0/1/2）。Dasha 层级（数量、名称、顺序、父子、衔接）、合盘字段（星座、宫位、度数、宿、UL、DK）、一致性比较条数、报告打包收录、自检标记都按能力限制，不整体停摆。
5. **评分统一**：准 1 / 部分准 0.5 / 不准 0；≥80% 高、≥60% 中、<60% 低；未答、有效已答 <3 或"记不清"超过 1/3 → 暂不定级；恒真、已知事实、校时用过的证据不计入；小样本标注；输出列全部计数。时间精度只由来源与校时决定；"反轴用户防御"与"更深入必然更准"一类保证删除。
6. **能力表与降级**：`check_chart.py` 打印每张盘的能力范围＝有效精度矩阵 × 逐分钟边界审计（含 D1 上升）× Dasha 层级 × 出生时间误差带来的 Dasha 日期平移（`shared/time_window.md` §1）。仅日期合盘路径：只用全天稳定的行星，宫位/UL/DK/Dasha 层标不适用，不补时刻。
7. **年盘**：本 skill 不做太阳回归，年盘 Lagna 与行星必须来自用户软件；缺数据时只给 Muntha 等可算部分并列出缺项（`varshaphala.py` 能力状态、退出码 2）。MD×AD 五档叠加：混合/平淡逐层陈述，不强行合成一个评级（解决 5.0 的未决项）。
8. **版本与失效**：chart_id / audit_id / 规则版本 / 引擎版本 / 基准日。`check_freshness.py` 分项检查：盘变了、误差范围变了、运期变了、过运已换座（不满 3 个月也算）、user_context 更新、规则或引擎升级；合盘子目录按双方盘核对。出生数据要变时先 `archive_chart.py` 归档，旧验证记录绑定旧盘、不迁移。
9. **交互**：必须问的集中问一次；用户已要完整分析或已点名专题时不弹菜单，直接点名专题/合盘/时机时不先插验前事；正反证据按实际数量写；内置 `shared/grounding_basic.md`，外部 oracle-grounding 只作增强。
10. **可复现验收**：`tests/run_tests.py`（计划表 14 项 + 补充项，虚构出生数据、固定过运日期）与 `tests/bench_positions.py`（独立星历对照）。

### 第四阶段发现并修好的数值问题
- **Dasha 年长错误**（影响 PyJHora 4.8.6 自身）：PyJHora 的"真恒星年"在部分年份多算一整天（实测 1962、2001 年 4 月至次年 4 月出生的盘，也包括东八区；还有个别日期返回 0），整张 Vimsottari 表因此拉伸约 0.27%，25 岁时偏约 3 周、表尾偏约 4 个月。现在改为在 UTC 上直接求太阳入白羊的前后时刻，并加年长合理性检查；引擎版本升到 `calculator-0.9.1+vedic5.1`，旧引擎排的盘会被 `check_freshness.py` 标为需重排。**之前用旧版排过、出生在上述区间的盘，Dasha 日期需要重排。**
- 能力判断补上"出生时间误差 → Dasha 日期平移"：±15 分钟的盘月级（PD）窗口通常不启用，`dasha_query.py` 此时只给 MD/AD 行。

### 新增 / 改写的脚本
`build_chart.py`、`chart_io.py`、`capability.py`、`check_chart.py`、`dasha_check.py`、`merge_shadbala.py`、`import_legacy_md.py`、`transit.py`（快照刷新、任意区间换座、过点日期）、`shared/scripts/` 下的 `score_probes.py`、`analysis_record.py`、`check_freshness.py`、`archive_chart.py`；`dasha_query.py`、`build_synastry_data.py`、`validate_synastry_data.py`、`report_builder.py`、`check_consistency.py`、`yogini_dasha.py`（`--chart`）、`varshaphala.py` 改为三状态与能力输出。

### 需要你确认的口径（改变了解读判断）
1. 校时写回用来源「校时」：有效精度 = 校准窗口半宽，可以窄于原来源下限（原来是窄于下限也按下限）。
2. Dasha 日期平移门槛：≤7 天 PD 可用；7–30 天 PD 条件使用；30–120 天 PD 不启用、AD 条件使用；>120 天只到 MD；>1 年 MD 交界也标条件。
3. "记不清"超过有效题 1/3 → 暂不定级。
4. reader 的轨道 3 / 条件 A / 时间风险改看 D1 边界审计（原来看 Lagna 0-3°/27-30°；未审计的旧数据仍用度数）；D1 边界敏感且来源不是出生证 → 时间可信度降一档（取代"跳过 Step 6 才降档"）。
5. 时间可信度映射：出生证/医院 = 高；±5、±15 = 中；±1 小时及更宽 = 低。
6. 直接点名专题、合盘、时机时不先做验前事。
7. Gana dosha 含 Manushya×Rakshasa；Nadi/Bhakoot/Gana 的减免由脚本判定。
8. 只因反馈而改的结论只落在 p5a/p5b 与分析记录；core Step 4.5 放在反馈复核之后。
9. rectifier：反馈分档改为 80/60；模式 B 弱匹配不计分。
10. timing：年盘岁差统一 True Chitra；删除"七曜月主"作为月份依据；历史回测阈值 60/40；Year Lord 候选 3、5 两条规则未定。
11. 沿用 5.0：love/dk_patterns 的 UL-AL 按 Rashi Drishti 读。

### 已知限制
- 数值准确性只做了位置与 Vimsottari 日期的独立对照（7 张虚构盘，与 astropy/ERFA 差 ≤1.5′，Dasha 结束日差 ≤0.7 天）；Shadbala、SAV/BAV、分盘、Chara Dasha 没有独立基准，仍以 PyJHora/JHora 一致为前提。
- 年盘（太阳回归）未实现；Sahams 只对用户软件导出的度数做公式加减。
- Chara AD、Yogini AD 为简化版，未经 JHora 核对；Yogini 只按 Moon 宿位置起算。
- 第 11、14 项（缺外部落地 skill、完整分析不弹菜单）只能做文档静态检查，行为靠场景试用验证。
- core、reader、rectifier 正文仍长（1000+ 行），已有主线摘要表，未拆分。
- calc 的 Dhana 预扫只核 2↔11；上游 vedic-prashna 未收入。
- 单独安装的旧 `vedic-consistency-eval` 与本 skill 的 `eval/consistency` 重复，建议卸载旧的。

## v5.0（2026-10-10）合并为单一 skill + 移植上游修复

### 结构
- 原 11 个 skill（vedic-calculator / reader / core / career / love / soul / timing / rectifier / synastry / consistency-eval / reader-eval）合并为一个 `vedic` skill。根目录 `SKILL.md` 负责路由，各模块正文在 `<模块>/MODULE.md`，资源与脚本路径不变（相对模块目录）。
- 模块正文里原来的 `vedic-xxx` skill 名统一改成「xxx 模块」或 `xxx/...` 路径；各模块重复的语言契约与日语资源去掉，语言规则只在根 SKILL.md 写一次。
- `dual-lens-oracle` 同步改为调用本 skill 的模块（单独打包）。

### calculator（换成上游 v0.9，2026-09-04 版）
- 岁差统一为 True Chitrapaksha；D1 星历基准与 PyJHora 一致；修复同一进程连续排盘时后一张盘岁差漂移（旧版实测漂 1.2′）、Vimsottari 年长跨盘漂移、极圈盘无法分宫。
- 新增输出：Graha Drishti 表、功能身份、结构格局预扫、互视/互溶（Parivartana 三分类，Dainya 单侧口径）、分盘内部宫主表 + 尊贵度（线A）、逐分钟分盘边界审计、Chara Dasha（K.N. Rao，JHora 对齐）、729 行 PD 三级运、未来 5 年过运换座表、Pushkara、DST 标注。校验区改为真判定。
- 删除西占 orb「主要相位关系」表。
- 新脚本：`dasha_query.py`（PD 按月/日下钻、默认折叠；必须带 `--file`）、`check_env.py`、`chara_dasha.py`、`make_xiaohuo_person_card.py`（上游作者的第三方文本卡片导出，只在用户明确要求时用；上游排盘结束时附带的导出提示已删掉）。
- 本地化调整（与上游不同）：8/12 宫主标签用本地叫法 Trika-Lord；Lagna 主恒为 Core-Driver（上游按 MT 宫定，会把 Pisces 盘 Jupiter 标成 Trader、Taurus/Scorpio 盘 Lagna 主标成 Growth-Hacker，与 core P1.5 规则 4 冲突）；Kemadruma 按古典口径不计 Sun/Rahu/Ketu（与月护三格局一致）；Adhi 输出标明宫号是本命宫号，并注明三宫齐=完整、1-2 宫=部分。

### reader（换成上游 2026-10-10 版 + 回贴本地改动）
- 上游新增：验前事反恒真（基础率过滤）与诚实计分、替补机制、分盘边界审计、rectifier 达成级别定级、双 Lagna 对比流程补齐、节点结果链、DST 确认、岁差基准反转、user_context 权限分级与增量回写。
- 保留本地：命中率 ≤2/5 时不归因于时间的话术、「信号解释置信度」第二维度、Step 9 两维分开写、data_contract 两维字段。
- 对齐修正：验前事 SOP 改为单一正本（rectifier 直接引用）；分盘启用矩阵「经过rectifier」不再一刀切，按有效精度取行；校准后不低于校准前「高」（无反证时）；data_contract「生时矫正记录」加校准达成级别/时间可信度/未定项三行；user_context 权限表补上 soul/timing；Calc 模式识别标记与 formatter 实际写入的字符串对齐；"高(临界待核)"改为字段值只写"高"、另加附注；Step 6 跳过校准时，条件 A（上升贴边界）降一档、条件 B（命中率低）维持原级。

### core（本地版 + 移植）
会改变解读结论口径的：
- 相位一律读 Graha Drishti 与互视/互溶表，禁用西占 orb；格局"互视"按双向判。
- VRY 只保留 P5 一处定义（落自宫不算）；Parivartana 新节（Maha 28 / Khala 8 / Dainya 30，优先级 Dainya > Khala > Maha）并入 Raja/Dhana/Dharma-Karma 判定。
- 大运判定改为五档顺序判定（互斥、全覆盖）；节点改用 P7.4 唯一口径；死敌 ≠ 落陷；NBRY 补全 6 条、分档、完全补救后大运不计落陷。
- SAV 降为辅助（只看极端值，不计入大运正负面）；SAV 读取铁规唯一定义在 house_framework §4；conflict_arbitration 冲突 7 同步。
- 分盘：新增「分盘输入稳定性先决条件」「分盘视角分离铁律」（线A/线B 禁混用），边界敏感分盘结论条件化。
- 新增「时间窗纪律」：月级窗口必须读 PD；QA 加日期失效检查（"→当前"标记会过期）。
- 补上格局识别步骤（读结构格局预扫，强度由模型评），修好 Step 4 引用"Step 1 识别的格局"的断链；Adhi 保留本地三宫齐口径。
- 新增 P2.5 Moon 盈亏、Karaka 使用铁律、凶凶合相口径与合相三档、婚姻三轴护栏（保留本地 UL 婚姻阶段）。
- VRY 孤立性补上 5-10° 一档（原规则只有 >10°、<5°、<1°）；验前事双维度复盘表补齐缺失组合。
- 新增 Step 4.5 措辞落点校订：Step 4 写完后读 user_context，只改 p5a/p5b 措辞落点，结论与数据不动，含敏感经历伦理检查；Step 1-4、Step 5、core_summary 仍全盲。下游盲审模块只读 p2a~p4 与 core_summary。
不改口径的：report_builder 表格前自动补空行；报告导读板块编号纠正；板块4 婚姻阶段改为与 UL 模型一致。

### career / love（本地版 + 移植）
- 相位改读 Graha Drishti；线A/线B 分写并先过分盘可信度声明（career_archetypes 删除 ±12 分钟阈值）；时间窗纪律副本（月级读 PD）；Chara 只读时间线表、缺表降为单系统信号（消除 love 两处矛盾）；SAV 铁规与降权；死敌 ≠ 落陷；过运日期只引换座表；Gaja/Adhi 改读格局预扫；行业名标"形态族举例"；配偶画像注明"符号推演，非实人档案"；落地层行动卡精度不细于实际读到的 Dasha 层级。
- 修复 dk_patterns 一个未闭合代码块。

### soul
- D60 启用条件改按 reader 有效精度矩阵（默认不用 D60 Lagna/宫位）。

### timing
- **Chara Dasha 修正**：方向改看 Lagna 起第 9 宫足性（旧版看 Lagna 奇偶），年数按各星座自身足性方向数（旧版按整体方向），双主取年数较大者（旧版取较近），年长改恒星年。与 calculator 随机 20000 张盘逐段一致。规则文档、Mode B 流程同步；Chara AD 标注为未经核对、只作阶段参考。
- 行运实位与未来换座改读 calculator 输出；新增时间窗纪律条目（Dasha 月级读 PD，年盘月份与行运日期注明依据）和日期失效检查。
- cross_verification 的 Vimsottari 吉凶判定副本（旧四档 + SAV 计票）删除，改为指向 core house_framework 五档。
- user_context 例外的位置对齐到 _playbook_dasha.md Step 4「历史回顾」。

### rectifier（本地版 + 移植上游至 2026-10-10）
- time_scan.py 换成 swisseph + True Chitra 版（与 calculator 同口径），保留 IANA 时区/当地钟表时间写法；新增 `--event-date` / `--pd`：每个候选时刻用它自己的出生时刻算 MD/AD/PD，并标出 Moon 跨宿。逐分钟对照 calculator 0 不一致；跨零点日期不借位。不再依赖 ephem。
- 规则：分钟级只认 D9/D10 换座点；换 Lagna 改为"冠军 vs 次高"比较；四层强制（含 drishti）；先填矩阵再写叙事、硬反证强制重检；Step 0 来源核实与 DST；边界事件权重减半、旧盘对照组；证据三分类与两腿等权；新增 `rectifier/resources/calibration_quiz.md` 出题规范；event_house_map 加静态事实映射；输出必带「校准达成级别」声明。
- 改变判断口径、需要确认的三处：user_context 读取范围放宽到客观事实项；家人记忆 + 5/5 且未做 D9 精调时可信度定为中（原中-高；但校准前 reader 已定为高、本次未推翻原 Lagna 且无反证时保持高）；Lagna 层欠定时可信度定为低（原中）。

### synastry（换成上游版 + 回贴本地落地层原则第 8 条）
- 新增 SAV 铁规、线A/线B、Layer 3 正负面判定 + 时间窗纪律、QA 偏差分诊、Rashi Drishti 判定表；脚本未变。完整模式只引用 A 的 p2a~p4 与 core_summary。

### 已知未决
- love/dk_patterns 的 UL-AL「三合/相位」按 Rashi Drishti 解读，待确认是否原意。
- MD×AD 叠加规则只覆盖正/负两档，混合/困难/危机/平淡的叠加未定义。
- calc 的 Dhana 预扫只核 2↔11，2/11×1/5/9 变体由模型读表补判。
- Chara AD、Yogini AD 为简化版，未经 JHora 核对。
- 上游 vedic-prashna（卜卦盘）未收入。
