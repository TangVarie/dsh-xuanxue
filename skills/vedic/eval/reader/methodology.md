# eval/reader · 读盘回归测试套装

把 **reader 模块 的 18 条运行时数学校验**，冻成一套**带标准答案、可回归**的评测——
让你每次改动 reader 之后，都能用数字确认"提取准确率有没有掉"，而不是凭感觉。

> 这是把达尔文那套（评估 → 改进 → 实测 → keep/revert）落到 reader 模块 上的执行件。
> **为什么是 reader 而不是解读模块**：读盘的输出（行星落座、度数、D9、AK、Dasha 起止）
> **100% 有确定答案**，比种草的红线层还干净——这是整套占星 skill 里达尔文能干净落地、
> 且杠杆最大的地方（reader 读错一颗逆行/认错南北盘，下游 core/career/love/soul 全建在错数据上）。
> 解读层没有标准答案，不在本套装范围内——别用 LLM-judge 假装能给"解读质量"打分。

---

## 两层评分（对应种草那套红线 / 高分的精神）

| 层 | 脚本 | 要什么 | 标准 | 哲学 |
|---|---|---|---|---|
| **A · 不变量** | `check_invariants.py` | **零标准答案** | 全部通过（红线） | reader 输出自相矛盾就抓出来 |
| **B · 对标真值** | `score_extraction.py` | JHora 参考盘 | 红线 100% + 覆盖层看准确率 | 错一个星座下游全废 |

**A 层**把 reader 18 条校验里【纯内部一致性】的部分变成回归检查，不需要参考盘：
SAV 总和=337、Ra-Ke 差 180°、日月恒不逆行/节点恒逆行、Nakshatra 与度数一致、
D9=D1 度数按公式推出、Chara Karaka 排序与度数一致、Vimshottari 周期/顺序/间隔。
A 层打分是纯算术，不是判断，不存在评分者偏向自己输出的问题。

**B 层**对标你 JHora 导出的真值：
- **红线层（必须 100%）**：每颗行星星座 / 逆行 / Lagna 星座 / AK —— 错一个就 DISCARD
- **覆盖层（看准确率，追高分而非 100%）**：度数(±1°) / Nakshatra+Pada / D9 / Karaka 排序 / Dasha 起点

**状态**按 5.1 统一口径：通过 0 / 失败 1 / 未完成 2（正本 `shared/data_contract.md` §7；两个脚本各自的判定条件见 MODULE.md「状态与退出码」）。
覆盖层不决定状态，只和 baseline 比。真值缺 d1 或 AK 时 B 层红线没有可比项，脚本仍会退出 0——按未完成处理，不算通过。

---

## 🔑 fixture 设计铁律

**测试盘的输入必须是 PDF / 截图（reader 易错的路径），真值来自同一张盘的 JHora 文字导出。**

文字粘贴当输入 → reader 只是复述文本 → trivially 100% → **没有任何测试意义**。
reader 真正会错的地方在视觉提取：南北盘识别、逆行小括号遗漏、D10/D4/D5 小盘图误读
（skill 自己都承认"AI 从 PDF 视觉提取分盘准确率极低"）。回归套装的价值就在守住这些。

---

## 怎么加你自己的盘（每张盘三步）

```
fixtures/
  <chart_id>/
    input.pdf  (或 input.png)   ← reader 的输入：你信任的那张盘的 PDF/截图
    ground_truth.json           ← 真值：从 JHora 文字导出，按 schema.md 编码
    reader_output.json          ← reader 跑完后，把它的提取结果归一化成此文件
```

1. **真值**：在 JHora 里把这张盘的行星表/Dasha/SAV 复制出来，按 `schema.md` 填成
   `ground_truth.json`。（嫌手填麻烦？把 JHora 文字粘给 Claude，让它按 schema 吐 JSON。）
   ⚠️ 真值必须用**你 JHora 的设置**（岁差体系 / 节点 mean 还是 true）——见下方"限制"。
2. **输入**：把同一张盘的 **PDF/截图**放成 `input.pdf`。
3. **跑 reader → 评分**：让 reader 模块 处理 `input.pdf`，把它的提取结果归一化成 `reader_output.json`
   （5.1 起优先从 `import_legacy_md.py` 导入后的 `chart_data.json` 按 `schema.md` 路径表取），然后：
   ```
   python3 check_invariants.py fixtures/<id>/reader_output.json
   python3 score_extraction.py fixtures/<id>/ground_truth.json fixtures/<id>/reader_output.json
   ```

建议冻 **10-20 张**，覆盖南印/北印、有逆行/无逆行、Lagna 边界/非边界、含分盘/不含分盘。

---

## 达尔文回归循环（改 reader 时怎么用）

reader 是被 Claude 执行的 skill（不是纯函数），所以"跑一遍"那步是 Claude 任务，评分那步是脚本：

```
0. baseline：对全部 N 张 fixture 跑 reader → 两个检查器 → 记下
   A 层通过数（应 = N/N 全部通过）+ B 层覆盖层综合 %。写进 iteration-log.md。

1. 单变量 mutation：只改 reader/MODULE.md 一处
   （例：强化南北盘判别、补一条逆行小括号识别规则、改 D10 提取话术）。git commit。

2. 重跑：对【同一批冻结的 input.pdf】重跑 reader → 两个检查器。

3. keep / revert：
   - A 层任一盘从通过变成失败            → DISCARD，git revert（红线退步零容忍）
   - A 层仍全部通过 且 B 覆盖层综合 ≥ baseline → KEEP，更新 baseline
   - A 层仍全部通过 但 B 覆盖层综合 ↓        → DISCARD，git revert
   - 有盘判未完成（真值或归一化缺项）    → 先补齐，这张盘不参与本轮 keep/revert

4. 每轮写 changelog（见 iteration-log.md），不论 keep/discard。
```

这里没有 δ 噪声带的烦恼——提取评分是确定性的，同一张 input.pdf 跑出来分数稳定
（唯一的随机性在视觉识别本身，可对同一盘跑 2-3 次取一致结果来压掉）。

---

## 跨盘聚合（reader 自我进化的机制）

跑完 N 张后，**别只看单盘**，把所有盘的失败项汇总，看**哪类检查/哪个字段系统性地错**：

- 某条 A 层不变量在多张盘上 fail → reader 在那个环节有结构性 bug
- B 层某字段（如 D10 落座）在 8/10 张盘上 miss → 这就是 skill 自己承认的
  "D10 视觉提取不可靠"，**该去改 reader 的 D10 处理话术**，而不是逐张盘打补丁
- 逆行字段在北印盘上 miss 多、南印盘上少 → 北印盘的逆行小括号识别要加强

跨多张盘都稳定的失败 → 提名成对 reader/MODULE.md 的一次明确改动。
（这跟种草那套"跨 3 个项目都涨分的 mutation 提名进主 skill"是同一个机制，
只是这里的"项目"是一张张盘。）

---

## 文件

文件清单与用途见 MODULE.md「文件」。示例 fixture：`reader_output.clean.json` 是完美提取（演示全部通过），
`reader_output.with_errors.json` 注入了 7 个错误（演示检查器有牙齿）。跑一眼 A 层（无需参考盘）：
```
python3 check_invariants.py fixtures/example_chart/reader_output.with_errors.json
```

---

## 限制（诚实摆出来）

- **示例 fixture 是合成盘，不是外部基准**：`fixtures/example_chart/` 由 `gen_example.py` 用 swisseph 算出，
  提取文件是构造的。它只能证明两个检查器能抓提取错误，**不能当作数值准确性的外部验证**；
  而且它与 calculator 用的是同类天文库，就算对得上也不独立。涉及数值准确性的声明（排盘或 reader 与 JHora 一致、度数准确等）
  需要独立基准：用户 JHora 导出、按相同设置核对过的真盘。
- **真值必须匹配你 JHora 的设置**。示例盘用的是 **Lahiri 岁差 + mean node**；
  你的 JHora 若用 true node 或别的岁差，真值要照你的来，否则比对无效。
- **SAV / BAV / Shadbala / Dasha 起止日期**这类，真值请直接从 JHora 填，
  **不要让脚本重算**——这些计算复杂，独立重算极易和 JHora 出现细微偏差，反而污染真值。
  `gen_example.py` 只重算了它能 100% 算对的部分（D1/Nakshatra/D9/Karaka 排序），
  SAV 用的是一组"总和=337"的示意值、Dasha 用的是"周期长度正确"的示意时间线。
- 本套装只管 **reader 模块（数据提取）**。`timing 模块` 已脚本化的计算器
  （Yogini / Chara Dasha）可用同样的"确定性回归"思路；解读层（core/career/love/soul）
  没有标准答案，要做的是**跨模块 一致性 harness**（同一张盘四个模块 别打架），那是另一件事。
```
