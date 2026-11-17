# 数据契约（正本）

本文件是「数据来源」的唯一正本。模块里涉及数据从哪来、存在哪、怎么改，以本文件为准。

## 1. 五类产物，分开保存

| 产物 | 内容 | 谁写 | 怎么改 |
|---|---|---|---|
| `chart_data.json` | 计算事实：输入、计算设置、行星、分盘、Dasha、Karaka、审计、过运快照 | `calculator/scripts/build_chart.py`；旧盘用 `import_legacy_md.py` 导入 | 只能重算或用脚本改（`merge_shadbala.py`），不手改 |
| `structured_data.md` | 同一份计算事实的阅读版 | 与 JSON 同一次生成；`build_chart.py --from-json` 重新生成 | 不手改表格；改了 JSON 就重新生成 |
| `verification_record.json` / `.md` | 验前事题目、用户反馈、评分、校时证据 | reader、rectifier | 按 `shared/validation_scoring.md` 登记，评分用 `shared/scripts/score_probes.py` |
| `user_context.md` | 用户提供的现实背景（关切、职业、经历、事件） | reader、rectifier；core QA 阶段增量追加 | 按 `shared/permissions.md` 的权限 |
| `analysis_record_<模块>.json` | 结论、依据、所用时间分辨率、模式、数据版本、变更日志 | 各分析模块（`shared/scripts/analysis_record.py init --module <模块>`，默认文件名 analysis_record_<模块>.json；report_builder 读 analysis_record_core.json 或 analysis_record.json） | 只追加；改结论必须走变更日志。同一模块对同一张盘另做一份独立分析（例如另一个时机问题）时用 `--file analysis_record_<模块>_<主题>.json`，`check_freshness.py` 会一并核对 |

计算事实、验证反馈、分析结论三者不混放。`structured_data.md` 里不得出现「盘面初验结果 / 验前事校准率 / 信号修正日志」，这些属于验证记录。`check_chart.py` 会把混入判为失败。

## 2. 读取顺序

1. 同目录有 `chart_data.json` 且 chart_id 与 `structured_data.md` 一致：脚本读 JSON，模型读 Markdown 引用和核对。
2. 只有旧版 `structured_data.md`：先跑 `calculator/scripts/import_legacy_md.py` 生成 JSON；缺的表保持缺失，不补成已验证。导入的 JSON 不能用 `build_chart.py --from-json` 重新生成完整 Markdown（字段不全），保留导入时生成的 structured_data.md。出生信息齐全、环境可用时，直接用 `build_chart.py` 重排更好（已导入的先用 `shared/scripts/archive_chart.py` 归档）。
3. 使用前先跑 `calculator/scripts/check_chart.py --dir <目录>`，按它给出的能力范围工作。

## 3. 缺失值只有四种写法

| 状态 | 含义 |
|---|---|
| 未提供 | 用户或来源没有给（如性别、时区） |
| 未计算 | 本流程没有算（如旧盘没有 PD、仅日期模式没有 Dasha） |
| 计算失败 | 算了但出错（附原因） |
| 不适用 | 这种输入下不存在（如无出生时间时的上升） |

JSON 里写成 `{"_missing": "not_provided|not_computed|failed|not_applicable", "reason": "…"}`。不得用空白、`—`、`[待填]` 或 ✅ 代替。
唯一例外：表格里结构上本来就没有的格子（Lagna 行的逆行/度数列、7K 表的第 8 行、Rahu/Ketu 的尊贵列）可以写 `—`，它表示"这一格不存在"，不是缺失值。

## 4. 出生时间与精度

`chart_data.json` 的 `input` 必须记录：出生日期、用户报的时间、计算用时间、钟表时间性质（当地钟表时间 / 标准时）、IANA 时区、UTC 偏移、是否夏令时、经纬度、时间来源、用户声明的误差、来源修正后的有效误差、实际审计范围。

有效误差 = max(用户声明误差, 来源下限)。来源下限：

| 时间来源 | 下限 |
|---|---|
| 出生证、医院记录（记到分钟） | ±1 分钟 |
| 家人明确记忆、家人记忆 | ±5 分钟 |
| 本人记忆、模糊记忆、未追问、未知 | ±15 分钟 |
| 校时（rectifier 校准后重排） | 按校准达成的窗口半宽（`--source 校时 --declared-min N --original-source 原来源`） |

- 有效精度档（分盘启用矩阵、reader 轨道、报告用的标签）：≤±2 分钟 → ±分钟级；≤±5 → ±5分钟；≤±15 → ±15分钟；≤±60 → ±1小时；更宽或未知 → 不确定。例：±10 分钟属于「±15分钟」档。脚本写在 `input.effective_label`。
- 实际审计范围必须等于有效误差（`build_chart.py` 自动对齐，`check_chart.py` 核对）。
- 禁止缺省写成「±分钟级」。没有声明就写「未声明」，并说明按哪个来源下限处理。
- 验前事命中只能作为辅助证据，不能把家人记忆升级为分钟级。收窄误差只能靠更可靠的来源或校时证据（见 `shared/validation_scoring.md`）。
- 报时是标准时、出生时又处于夏令时：`--clock-type 标准时`，脚本换成当地钟表时间再算，并在元信息写明。
- 夏令时切换当天：钟表上不存在的时刻脚本拒绝并提示核对是否标准时；钟表上出现两次的时刻必须用 `--repeated-hour 夏令时|标准时` 指明，写进 `input.repeated_hour`（两次是两张盘，chart_id 不同）。不自行加减一小时。

## 5. 版本标识

- `chart_id`：只随出生数据与计算设置变化。出生时间、地点、时区、计算设置任一变化 → 新 chart_id。
- `audit_id`：chart_id + 审计范围。误差范围变了 → 新 audit_id。
- `rules_version`：本 skill 的规则版本（当前 `vedic-5.2`）。
- 过运快照另有提取日期。

分析记录、core_summary、验证记录都要写明它们绑定的 chart_id（及 audit_id、规则版本、基准日）。失效判定见 `shared/versioning.md`。

## 6. 专项字段

- **Karaka**：JSON 同时有 7K 与 8K 完整排序；Markdown 有「Chara Karakas 7K/8K 对照」。主表与 DK 用 7K；8K 只在模块明确要求时参考。下游不得自行补算。
- **Shadbala 的 PDF 补充**：只能用 `merge_shadbala.py` 逐行合并。PDF 有的行写采用值，`calc基准` 列保留原计算值，「数据来源」列写来源；PDF 没有的行保持 calc。PDF 必须对应同一出生时刻；校时后旧 PDF 作废。
- **Vimsottari**：MD/AD/PD 三层完整写入；模型默认用 `dasha_query.py --overview` 折叠 PD，按月/日下钻时再读。层级检查见 `calculator/scripts/dasha_check.py`。
- **仅日期模式**（`build_chart.py --date-only`）：只给全天稳定的行星星座与宿；上升、宫位、分盘、Dasha、Karaka 标「不适用 / 未计算」。不得为了通过自检补一个出生时刻。

- **用户信息节**（性别、感情状态）是排盘时随输入记录的元数据。性别用于需要性别的读法；感情状态只用于选择读法与措辞，不移动时间窗，也不当盘面证据。

## 7. 检查状态

所有检查脚本只返回三种状态：

| 状态 | 含义 | 后续 |
|---|---|---|
| 通过 | 必需内容齐全，检查成立 | 执行对应分析 |
| 失败 | 明确错误或内部矛盾 | 修复受影响部分后再用 |
| 未完成 | 缺数据、未执行或无可比较事实 | 只限制对应能力，其余照常 |

退出码统一：0 通过 / 1 失败 / 2 未完成。
