> 本文件是 `vedic` skill 的 **eval/reader** 模块。文中相对路径（resources/、scripts/）以本模块目录 `eval/reader/` 为根；跨模块引用写作 `<模块>/...` 或「<模块> 模块」，指 vedic skill 下的同名目录，调用方式见根目录 SKILL.md。

# reader 模块 读盘回归测试套装

把 reader 模块 的 18 条运行时数学校验，冻成**带标准答案、可回归**的评测——
每次改动 reader 后用数字确认"提取准确率有没有掉"，而不是凭感觉。**只测提取，不评解读质量。**

## 何时用 / 不用
- **用**：评测/回归测试 reader 的提取、给盘建测试集、改完 reader 想验证、排查提取错误。仅在用户明确要求时进入（根 SKILL.md 路由表）。
- **不用**：用户只是想读/分析一张盘（那是 `reader 模块`，不是本模块）。

## 为什么 reader 值得这样测
读盘输出（行星落座/度数/Nakshatra/D9/AK/Dasha 起止）**有确定答案**，是整个占星 skill 栈里确定性回归能干净落地、
且杠杆最大的地方（reader 读错一颗逆行/认错南北盘，下游 core/career/love/soul 全建在错数据上）。
**解读层没标准答案，不在本模块范围**——别用 LLM-judge 给"解读质量"打分。

## 两层评分（详见 methodology.md）
- **A 层 `check_invariants.py`**：**零标准答案**。把 18 条里的确定性不变量
  （SAV=337、Ra-Ke 差 180°、日月恒不逆行/节点恒逆行、Nakshatra/D9/Karaka 排序与度数一致、
  Vimshottari 周期）冻成回归检查，跑 reader 输出就能抓内部矛盾。**红线，必须 100%**。纯算术，不是判断。
- **B 层 `score_extraction.py`**：对标 JHora 真值。**红线层**(星座/逆行/Lagna/AK 必须 100%)
  + **覆盖层**(度数±1°/Nakshatra+Pada/D9/Karaka 排序/Dasha 起点，看准确率)。

## 状态与退出码（vedic 5.1 统一口径，正本 `shared/data_contract.md` §7）

| 脚本 | 通过 0 | 失败 1 | 未完成 2 |
|---|---|---|---|
| `check_invariants.py` | 全部不变量通过 | 任一不变量违反（含缺行星、缺 Karaka 排序、SAV 不足 12 宫） | —（输入不完整按失败处理） |
| `score_extraction.py` | 红线层全过，且红线层确实比上了（真值有 d1 与 AK） | 红线层有错 | 真值或提取结果没有可比较的行星字段（比较数为 0） |

- 覆盖层不决定状态，单独记百分比，用于和 baseline 比。
- 参数错误退出 4（不属于检查状态）。`score_extraction.py` 在真值或提取结果没有行星字段时退出 2（未完成）；真值缺 `chara_karaka.ak` 时 AK 一项不比，汇报里写明。
  跑之前确认 `ground_truth.json` 有 9 行星 + Lagna 和 AK；输出里覆盖层各行全是 `0/0` 时说明没比上，按**未完成**处理，不算通过。
- 汇报时写明比了几项：A 层「N/N 不变量」，B 层红线层结论 + 覆盖层各行的 `命中/总数`。

## 🔑 fixture 设计铁律
**测试盘的输入必须是 PDF/截图（reader 易错的路径），真值来自同一张盘的 JHora 文字导出。**
文字粘贴当输入 → reader 只是复述文本 → trivially 100% → **白测**。reader 真正会错的地方在
视觉提取：南北盘识别、逆行小括号遗漏、D10/D4/D5 小盘图误读。
真值也不能用本 skill 的 `build_chart.py` 生成——那是拿被测系统的同类计算当标准答案，不独立。

## 工作流程

### 加一张盘（每张盘三件）
`fixtures/<chart_id>/` 下放：`input.pdf`（或 `.png`）、`ground_truth.json`、`reader_output.json`。
1. **真值**：把用户 JHora 的行星表/Dasha/SAV 文字，按 `schema.md` 蒸馏成 `ground_truth.json`
   （Claude 直接做这步归一化）。⚠️ 必须用**用户 JHora 的设置**（岁差体系 / 节点 mean 还是 true）。
2. **输入**：同一张盘的 PDF/截图放成 `input.pdf`。
3. **跑 reader → 归一化**：让 reader 模块处理 `input.pdf`，把它的输出按 `schema.md` 归一化成 `reader_output.json`。
   5.1 起 reader 的提取经 `calculator/scripts/import_legacy_md.py` 导入成 `chart_data.json`（`provenance.source = legacy_md_import`），
   可按 `schema.md`「从 chart_data.json 归一化」的路径表取，比让模型转写 `structured_data.md` 稳定。
   ⚠️ 只用 reader 路径产出的 `chart_data.json`；`build_chart.py` 直接排出来的盘不是 reader 的提取结果，不能当 reader_output。

### 跑评测
```bash
python3 check_invariants.py fixtures/<id>/reader_output.json
python3 score_extraction.py fixtures/<id>/ground_truth.json fixtures/<id>/reader_output.json
```
A 层应通过；B 层红线应 100%、覆盖层记录百分比。状态按上面的表读。

### 改 reader 时的 keep/revert 循环
0. **baseline**：全部 fixture 跑 reader→两检查器，记 A 层通过数 + B 覆盖层综合%，写 `iteration-log.md`。
1. 单变量改 `reader/MODULE.md` 一处，git commit。
2. 对**同一批冻结的 input** 重跑 reader→两检查器。
3. A 层任一失败 → **revert**；A 全部通过且 B 覆盖 ≥ baseline → **keep**；A 全部通过但 B 覆盖↓ → **revert**。
   有盘判未完成 → 先补齐真值或归一化，再比，不计入 keep/revert。

提取评分是确定性的，没有噪声带 δ 的烦恼；视觉识别本身的随机性可对同一盘跑 2-3 次取一致结果压掉。

### 跨盘聚合
跑完 N 张，把失败项按"检查×盘类型"汇总，找**系统性失败** → 指向 reader 某处该改
（如 D10 落座在多张盘 miss = 该改 reader 的 D10 提取话术），而不是逐张盘打补丁。详见 `methodology.md`。

## 示例（解压即可跑）
`fixtures/example_chart/` 是用 swisseph 算出的**合成模板盘** + 完美/注入错误两份提取：
```bash
python3 check_invariants.py fixtures/example_chart/reader_output.with_errors.json   # 应判失败（退出码 1），抓出多条不变量违反
python3 score_extraction.py fixtures/example_chart/ground_truth.json fixtures/example_chart/reader_output.clean.json  # 应通过（退出码 0），覆盖层 100%
```
把它换成你 JHora 验证过的 **10-20 张真盘**即可（南/北印、有/无逆行、Lagna 边界、含/不含分盘）。

## 文件
- `check_invariants.py` / `score_extraction.py` — 两个检查器（A / B 层）
- `vutil.py` — 确定性公式**单一来源**（D9/Nakshatra/Karaka），三个脚本共用
- `gen_example.py` — 可选，造示例盘（需 `pip install pyswisseph`；你自己用时**不需要**跑）
- `schema.md` — `ground_truth.json` / `reader_output.json` 字段定义，及从 `chart_data.json` 归一化的路径
- `methodology.md` — 两层评分、回归循环、跨盘聚合、限制（深入说明）
- `iteration-log.md` — 迭代日志模板
- `fixtures/example_chart/` — 可跑通示例

## 限制（详见 methodology.md）
- **示例 fixture 是合成盘**：真值由 `gen_example.py` 用 swisseph 算出（Lahiri + mean node），SAV 是凑满 337 的示意值，
  Dasha 是周期长度正确的示意时间线；两份提取是构造的。它只能演示检查器能抓提取错误，**不能当作数值准确性的外部验证**。
  涉及数值准确性的声明（如"reader / 排盘与 JHora 一致"）需要独立基准：用户 JHora 导出、按相同设置核对过的真盘。
- 真值须匹配你 JHora 的岁差/节点设置；SAV/Shadbala/Dasha 日期请直接从 JHora 填、**不要脚本重算**
  （独立重算极易与 JHora 出现细微偏差，反而污染真值）。
- 本模块只管**提取**；解读层的事实一致性用 `eval/consistency`；解读质量本身靠验前事反馈 + 人的判断
  （验前事反馈不是预测准确率，`shared/validation_scoring.md`）。
