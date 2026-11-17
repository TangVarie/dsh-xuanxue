---
name: "vedic"
description: "吠陀占星（Vedic/Jyotish，KN Rao 派 Parashari）一体化入口：排盘、读盘、完整星盘分析、事业、感情婚姻、灵魂层、行运流年大运、出生时间校准、双人合盘、吠陀卜卦（Prashna：用提问时刻起提问盘，回答一件具体的事成不成、某人会不会动、大致何时，不需要出生信息），以及对已有报告追问。凡涉及吠陀占星或印度占星都用本 skill，由它按需加载内部模块。触发词：吠陀、印度占星、Jyotish、Vedic astrology、排盘、算一下、读盘、看盘、星盘分析、帮我分析、完整分析、生成报告、P1-P12、D9、D10、事业方向、职业、恋爱、桃花、婚姻、配偶、DK、Upapada、灵魂、Atmakaraka、Karakamsa、本命神、行运、Sade Sati、流年、今年运势、大运、Dasha、Chara Dasha、Yogini、年盘、Varshaphala、校准时间、出生时间不准、rectification、合盘、配对、两个人合不合、合作搭档、synastry、Prashna、吠陀卜卦、提问盘、即时盘、时盘、horary、用吠陀卜一卦。也用于 vedic 模块的一致性检查和读盘回归测试（仅在用户明确要求时）。"
metadata:
  icon: ':lucide:wrench:'
  title: Vedic
---

# vedic：吠陀占星一体化 skill

## 运行环境

执行前设 `$env:PYTHONUTF8="1"`、`$env:PYTHONIOENCODING="utf-8"`。解释器：先读 `xuanxue-skills/health.json`（`xuanxue-orchestra` 体检写），或 `$env:XUANXUE_VEDIC_PY`；默认位置是玄学运行时的 `%USERPROFILE%\.dsh\xuanxue\venv\Scripts\python.exe`（不是 `bin/python`），缺环境跑 `xuanxue-orchestra/scripts/setup-runtime.ps1`。不要用系统 Python 3.14（pysweph 不支持）。验证用 `calculator/scripts/check_env.py`：依赖齐时打印 SAV=337 与「环境就绪」，它自己也会给出修复命令（`calculator/scripts/setup_env.py`）。星历用本技能自带的 `calculator/scripts/ephe` 三个 .se1（引擎显式使用这一份）；pip 卡在缓存临时文件时设 `$env:PIP_NO_CACHE_DIR="1"`。已验证 PyJHora==4.8.6、pysweph==2.10.3.6、numpy==2.3.5、timezonefinder==6.0.1。


一个入口，内部按模块分工。模块正文在 `<模块>/MODULE.md`，共用协议在 `shared/`。用户不需要知道模块名，说想看什么即可。

## 一、规则的权威顺序

同一件事在多处有写法时，按以下顺序执行，上层优先：

1. **全局约束**：本文件
2. **数据与权限协议**：`shared/` 下的正本
3. **模块流程**：`<模块>/MODULE.md` 与其 `resources/`
4. **示例**：模块里的示例、模板、示范话术

示例与上层规则不一致时，按上层规则写，示例只看格式。模块只能在下表明确列出的范围内设例外；数据质量、分盘稳定性、来源标注、时间分辨率、背景信息权限这些规则，模块不能自行绕过。

| 允许的模块例外 | 范围 |
|---|---|
| timing Mode C 年盘 | 按 Tajaka 体系使用容度相位与年盘自己的判定；年盘给出的月份不受 PD 限制，但要写明依据，简化部分保持简化标记 |
| timing Mode A 行运 | Ashtakavarga 行运以 BAV/SAV 为方法本身；行运日期来自真实星历 |
| synastry 跨盘接触 | 跨盘度数分级用 `synastry/resources/aspect-policy.md`，不套本命盘的合相三档 |
| prashna 提问盘 | 独立产物目录 `prashna_*`：不读写 `chart_data.json`、`user_context.md` 与分析记录，不做验前事，不跑 `check_chart.py`／`check_freshness.py`；时间只来自它自己的时间副层，不用 Dasha、行运、分盘；Tajika 接触只在它的过程层里用，不改它标准层的结论。细则见 `prashna/MODULE.md`「与本 skill 其他部分的关系」 |

## 二、共用协议（正本只有一份，模块引用它）

| 主题 | 正本 |
|---|---|
| 数据来源、产物分工、缺失值、精度与时区、版本标识、检查状态 | `shared/data_contract.md` |
| 背景信息权限、盲审模式、三个推导阶段、结论修改 | `shared/permissions.md` |
| 时间分辨率、MD×AD 叠加 | `shared/time_window.md` |
| 分盘启用、边界审计、线A/线B | `shared/divisional.md` |
| 验前事评分、时间精度职责 | `shared/validation_scoring.md` |
| 用户说"不准"的分诊、错误纠正 | `shared/error_correction.md` |
| 过期数据、旧报告失效 | `shared/versioning.md` |
| 按材料与任务决定能力、降级路径 | `shared/capabilities.md` |
| 建议与行动指引的基础落地 | `shared/grounding_basic.md` |

## 三、模块地图与路由

| 模块 | 做什么 | 进入条件 |
|---|---|---|
| calculator | 由出生信息排盘，同时写出 `chart_data.json` 与 `structured_data.md`；仅日期模式；旧盘导入 | 给了出生日期、时间、地点；或只有日期（合盘一方） |
| reader | 导入 PDF/截图/文本星盘并校验；验前事；建档 `user_context.md` | 给了星盘文件；排盘后做验前事 |
| core | 完整分析、十大板块、技术附录、core_summary、追问 | 要完整分析或报告；对已有报告追问 |
| career | 事业深挖 | 事业、职业方向、换工作 |
| love | 感情深挖 | 感情、桃花、婚姻、配偶画像 |
| soul | 灵魂层（Jaimini + SJC） | 此生功课、AK、Karakamsa、本命神 |
| timing | Mode A 行运 / Mode B 多 Dasha / Mode C 年盘 | 何时会发生 → B；最近、当下 → A；明确要年盘 → C。普通"今年运势"默认走大运与行运（B+A），不默认起年盘 |
| rectifier | 出生时间校准 | 时间来源不可靠且需要分盘精度；用户要求校准 |
| synastry | 双人合盘 | 两个人的关系、合作、配对 |
| prashna | 吠陀卜卦：用提问时刻与地点起提问盘，回答一件具体的事成不成、某人会不会动、大致什么时候；不需要出生信息 | 一件具体的事要个答案（能不能成、会不会来、找不找得回）；用户说 Prashna、吠陀卜卦、提问盘、即时盘、时盘、horary |
| eval/consistency、eval/reader | 开发质检 | 仅在用户明确要求 |

使用方式：
1. 按路由表判断模块，**完整读取**该模块的 `MODULE.md` 后执行。模块里的相对路径以模块目录为根；`X/...` 指本 skill 下的 X 模块。
2. 模块里说"触发 / 调用 / 进 X 模块"，就是读取 `X/MODULE.md` 继续。一次只加载当下要用的模块。
3. 模块之间通过工作目录的文件交接，不靠对话记忆。
4. 标准顺序：calculator 或 reader → core → 按需 career / love / soul / timing。校时改了时间后回到 calculator 重排（新 chart_id），旧分析按 `shared/versioning.md` 处理。八字×吠陀交叉由单独的 `dual-lens-oracle` skill 编排。
5. 卜卦与本命分开：问一件具体的事 → prashna；问人生趋势、某一年的运势、性格 → 本命模块。prashna 不读本命盘和 `user_context.md`，本命模块也不引用提问盘的结论。进 prashna 的第一步是先记下提问时刻（见它的执行主线），再读别的。

## 四、每次都要做的检查

- 拿到或生成盘后：`python calculator/scripts/check_chart.py --dir <工作目录>`，按输出的能力范围工作；失败项先修，未完成项只限制对应能力。
- 引用旧报告、旧摘要、回答时机问题前：`python shared/scripts/check_freshness.py --dir <工作目录>`。
- 读取一律以 `chart_data.json` 为准（`shared/data_contract.md` §2）；没有就先导入或重排。
- prashna 模块不做上面三项：它不读 `chart_data.json`，产物在独立的 `prashna_*` 目录，按 `prashna/MODULE.md` 的自检执行。

## 五、交互

- 深度由用户请求决定：简短追问直接在聊天里回答；专题与完整报告生成文件。
- 必须问的信息集中问一次；已经给过的直接复用。用户已说明要完整分析、或已交代关系类型、目标和深度时，不再弹选择菜单中断，直接做。
- 正反证据按实际数量呈现，某一侧没有就写"未发现"，不凑条数。
- 聊天里展示可核验的数据、依据摘要和检查结果，不铺内部工序。
- 建议、时机、行动指引按 `shared/grounding_basic.md` 写；装了外部 `oracle-grounding` skill 时作为增强层叠加，没装也能完整执行。
- 语言跟随用户，默认中文。术语保留原名，首次出现时解释成能核对的具体表现。文件名、表头、CLI 参数保持原样。

## 六、运行环境与工具

- 排盘与时间扫描用 calculator 的 Python 环境（pysweph + PyJHora 4.8.6 + 星历文件）。首次使用：`python calculator/scripts/check_env.py`；缺依赖时 `python calculator/scripts/setup_env.py --target <工作目录>/vedic-calc-env`（本 skill 目录通常只读）。synastry、timing、shared 的脚本只用标准库；`core/scripts/report_builder.py` 另需 `pip install markdown`。prashna 的脚本用同一个计算环境（Python 3.9 及以上）。
- 主要脚本：

| 脚本 | 用途 |
|---|---|
| `calculator/scripts/build_chart.py` | 排盘（含 `--date-only`、`--from-json`）；输入有误时第一行写「输入有误」并说明怎么改 |
| `calculator/scripts/check_chart.py` | 产物总检查与能力范围 |
| `calculator/scripts/dasha_query.py` | Dasha 层级检查（`--check`）、折叠阅读、按月/日读 PD |
| `calculator/scripts/merge_shadbala.py` | PDF Shadbala 逐行合并 |
| `calculator/scripts/import_legacy_md.py` | 旧版 structured_data.md 导入 |
| `calculator/scripts/transit.py` | 刷新过运快照（`--chart … --write`）、任意区间换座表（`--ingress-from`）、过某度数日期（`--hit`） |
| `shared/scripts/score_probes.py` | 验前事评分 |
| `shared/scripts/analysis_record.py` | 分析记录、冻结、变更日志 |
| `shared/scripts/check_freshness.py` | 旧报告失效检查（含合盘子目录、引擎/规则升级） |
| `shared/scripts/archive_chart.py` | 出生数据要变（更正、校时、导入后重排）之前归档旧盘产物 |
| `rectifier/scripts/time_scan.py` | 逐分钟扫描，带每个候选时刻自己的 Dasha |
| `synastry/scripts/validate_synastry_data.py`、`build_synastry_data.py` | 合盘自检与跨盘计算 |
| `core/scripts/report_builder.py` | HTML 报告打包（列出应收录与实际收录） |
| `prashna/scripts/build_prashna_data.py` | 提问盘起盘（秒级时刻），写 `structured_prashna.md` 与 `prashna_meta.json` |
| `prashna/scripts/run_prashna.py` | 取象单写好后一条命令跑判定、时间副层、Tajika 过程层（`--dir <prashna_* 目录>`） |
| `tests/run_tests.py` | 回归用例（`--python <计算环境解释器>`；P1、P2 调用 `prashna/tests/` 下的两份测试） |
| `tests/bench_positions.py` | 用独立星历（astropy/ERFA，需 `pip install astropy`）复算位置与 Dasha 日期 |

## 七、版本

v5.3（2026-11）：新增 prashna 模块（吠陀卜卦）。本命侧的计算与规则没有变：引擎版本 `calculator-0.9.2+vedic5.2`、规则版本 `vedic-5.2` 不变，旧盘不用重排，旧分析不用复核。变更清单、测试结果与已知限制见 `CHANGELOG.md` 与 `tests/RESULTS.md`。5.1 及更早排出的盘：`check_freshness.py` 会提示重排，并说明只有引用 Chara Dasha 的时机结论需要复核。
