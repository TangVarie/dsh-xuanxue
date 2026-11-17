# 产物版本与失效（正本）

本文件是「过期数据处理」的唯一正本。

## 1. 每份分析记录写明

chart_id、audit_id、规则版本、基准日（`as_of`）、模式（`shared/permissions.md`）。core_summary.md 首行之后写一行：

`> 数据版本: chart_id=<12位> · audit_id=<12位> · 规则 vedic-5.2 · 基准日 YYYY-MM-DD · 模式 <mode>`

各模块的 analysis_record 由 `shared/scripts/analysis_record.py init` 自动填这些字段。

## 2. 读旧报告、旧摘要之前

先跑：`python shared/scripts/check_freshness.py --dir <工作目录>`，按结果处理。不能无提示地继续引用旧摘要。

| 发生的变化 | 检出方式 | 应更新什么 |
|---|---|---|
| 出生时间、地点或计算设置改变 | chart_id 不同 | 重算相关数据；旧分析标「待更新」，不得直接引用 |
| 时间误差范围改变 | audit_id 不同 | 重做稳定性审计；复核依赖分盘宫位/宫主的结论 |
| 查询日期改变 | 基准日与今天的 MD/AD/PD 不同 | 用今天重新定位运期，更新时效相关段落 |
| 行星已经换座 | 快照日之后换座表有事件（即使不满 3 个月）；或快照超过 90 天 | 更新过运及相关判断 |
| 新增用户背景 | user_context.md 修改时间晚于基准日 | 更新表达与建议；必要时进入反馈复核 |
| 解读规则版本改变 | rules_version 不同 | 标明哪些旧结论需要复核 |

结构数据、过运快照、分析结论分别管理，不用一个总开关把所有内容重做。运期没变、盘没变时，旧结论照常可用。

## 3. 出生数据改变之后（用户更正时间/地点，或校时写回）

- 重排**之前**先归档：`python shared/scripts/archive_chart.py --dir <工作目录> --reason "<原因>"`。它把 chart_data.json、structured_data.md 复制到 `archive/<旧 chart_id>/`，把分析记录、core_summary、各模块报告与分节文件、QA 文件、验证记录、旧版导入原文移过去；user_context.md 与校时过程文件留在原处。然后用 `build_chart.py` 按新数据写回同一工作目录。
- 新盘新 chart_id；旧盘产物全部保留在 archive，绑定旧盘。`check_freshness.py` 会报告"当前盘还没有分析，旧盘分析在 archive/…"。没有先归档就重排的，`check_freshness.py` 按 chart_id 判旧记录失效，`analysis_record.py init` 拒绝覆盖旧记录，此时补跑归档即可（chart_data.json 已是新盘，旧盘文件只剩记录类）。
- 只改了误差范围（时间不变）：chart_id 不变、audit_id 变，不归档，复核依赖分盘的结论。
- 旧验证记录不迁移成新盘的验证结果；新盘需要验证时另建记录（`shared/validation_scoring.md` §4）。
- 新盘的分析从初始推导重新开始；可以对照旧结论，但对照属于反馈复核，要记变更日志。
