# eval/consistency · 跨模块 一致性 harness

检查 **core / career / love / soul** 这四个解读模块，在**确定性事实**上是否
①忠于源数据（`chart_data.json`）、②彼此不打架。

> **为什么是这个、而不是"解读质量评分"**：解读层没有标准答案——
> "土星落 7 宫对婚姻意味着什么"无法 A/B 打分，更不能用 LLM-judge 假装能打。
> 但这四个模块都读同一份盘数据，所以它们引用的**确定性事实**
> （AK、各宫主、行星星座/尊贵度、D9 上升、Dasha 起止）**必须一致且忠于源数据**。
> 这是解读层里唯一能被确定性检验的东西——而且眼睛逐个看单模块根本看不出来。
> 解读本身的好坏只能靠验前事反馈和人的判断；验前事反馈说明的是一组探针与用户反馈对得上多少，
> 不是预测准确率（`shared/validation_scoring.md`）。

---

## 查两件事

| 检查 | 抓什么 |
|---|---|
| **保真度 fidelity** | 某个 skill 自己把 10 宫主读错、把尊贵度说反、AK 选错——即偏离源数据 |
| **跨模块 一致性** | core 说 10 宫主是火星、career 说是土星——四个独立长出来的模块互相矛盾 |

两者都通过 `check_consistency.py`，比对是**纯算术**，不是判断，不存在评分者偏向自己输出的问题。
**本 harness 不评解读质量**，只查确定性事实是否自洽。

状态与退出码按 5.1 统一口径：通过 0 / 失败 1 / 未完成 2（正本 `shared/data_contract.md` §7，本模块的判定条件见 MODULE.md「状态与退出码」）。
每次汇报写明实际比较了多少条事实；空提取 = 未完成，不算通过。

---

## 数据流

```
chart_data.json ──蒸馏──▶ canonical_facts.json   (源数据真相，单一来源；字段路径见 schema.md)
                                      │
   ┌──────────┬──────────┬───────────┤  各模块跑完后，从其输出里
 core 输出   career 输出  love 输出  soul 输出   抽取"确定性主张"
   │          │          │          │
   ▼          ▼          ▼          ▼
 skill_claims_core/career/love/soul.json
                                      │
                                      ▼
                         check_consistency.py
                  ① 每份 claims vs canonical (保真度)
                  ② 多份 claims 互相比 (跨模块)
```

抽取那步（prose → JSON）是 Claude 辅助的（或用 Jev 闭集抽取）；**比对那步是确定性脚本**。
canonical_facts 是源数据，是唯一真相——任何 skill 引用事实时都必须忠于它。
5.1 起 canonical 直接从 `chart_data.json` 按 `schema.md` 的路径表取，尊贵度与宫主用 `cutil` 推，不再让模型转写 `structured_data.md`。

---

## 怎么用（一张盘）

1. 盘数据过了 `calculator/scripts/check_chart.py` 后，按 `schema.md` 从 `chart_data.json` 蒸馏 `canonical_facts.json`
   （没有 JSON 的旧盘先用 `import_legacy_md.py` 导入）。
2. 把这张盘依次跑 core / career / love / soul。
3. 从每个 skill 的输出里抽取它**断言过的确定性事实**，写成
   `skill_claims_<skill>.json`（按 `schema.md`）。
   ——只抽它明确陈述为事实的项（"你的 10 宫主是火星""土星入庙"），不抽解读。
4. 跑检查：
   ```
   python3 check_consistency.py fixtures/<chart>/canonical_facts.json fixtures/<chart>/
   # 目录模式会自动扫该目录下所有 skill_claims_*.json
   ```
   读状态（通过 / 失败 / 未完成）和「实际比较」那一行。

---

## 与 ① 的关系（两套合起来才完整）

```
①  eval/reader        ②  eval/consistency
   读盘提取是否正确             解读模块 是否忠于盘数据 + 彼此一致
   (对标 JHora 真值)            (对标 chart_data.json + 跨模块)
        │                              │
        └──────────────┬───────────────┘
                       ▼
        提取正确  →  四个模块 都忠于盘数据  →  解读才站在可靠地基上
        (①管)          (②管)                  (验前事反馈 + 人的判断)
```

①管"数据对不对"，②管"四个模块用数据用得一不一致"。
解读本身好不好——那是验前事反馈 + 你这个行家的判断，工具测不了，也不该假装能测。

---

## 改解读模块 时怎么用（回归门）

编辑 core/career/love/soul 任一处后，把这套当**回归门**：
```
0. baseline：选 5-10 张盘，每张跑四个模块 → 抽 claims → check_consistency 应全部「通过」，
   并记下每张盘实际比较的事实数。未完成不算通过。
1. 改某个 skill 一处话术/规则。
2. 对同一批盘重抽 claims → 重跑 check_consistency。
3. 保真度/一致性出现任何新矛盾（失败）→ revert（事实退步零容忍）。
   比较事实数明显少于 baseline → 先查抽取或 canonical，再下结论。
   全部通过 → 解读层的"事实地基"没塌，再凭你的判断看解读有没有变好。
```
跨多张盘反复出现的同类矛盾（如 career 总把某宫主读错）→ 提名成对那个 skill 的明确改动。

---

## 文件

文件清单与用途见 MODULE.md「文件」。

---

## 限制（诚实摆出来）

- **fixture 是合成示例盘**：`fixtures/example_chart/`（`example_template_1990`）的 canonical 与四份 claims 都是构造的，
  career 的两处错误是手工注入的。它只能演示抽取 → 比对这套流程有牙齿，**不能当作数值准确性的外部验证**。
- **canonical 来自被检查的同一份盘数据**：本 harness 只回答"模块是否忠于 `chart_data.json`"。
  `chart_data.json` 本身算错（岁差、节点、Dasha 起点、分盘公式），这里一条也查不出。
  涉及数值准确性的声明（如"排盘与 JHora 一致""Dasha 起点准确"）需要独立基准：用 JHora 等外部软件按相同设置导出的真盘做对照
  （`eval/reader` 的 B 层或单独的对照测试），不能拿本套件的通过当证据。
- **只查确定性事实**：AK / 宫主 / 行星星座 / 尊贵度 / D9 上升 / Dasha。解读不查。
- **尊贵度**只到 `Exalted / Debilitated / Own / Other` 四档（friend/enemy/neutral 归 Other），
  避免自然友谊表的体系分歧。要更细可在 `cutil.dignity` 扩。
- **canonical_facts 的字段**应按你四个模块实际会引用的事实扩充
  （如要查 D10 上升、AL/UL、特定 Karaka，加进 schema + canonical + 各 claims 即可）。
- **claims 抽取是 LLM 辅助步骤**——抽完最好扫一眼，确认抽的是 skill"陈述为事实"的项，
  而不是把解读里的修辞误当事实。比对本身是确定性的，不受影响。
- **也可以用 Jev 做闭集抽取**（`jev_extract_claims.py`，见 MODULE.md「用 Jev 抽取」）：答案限定在行星 / 星座 / 尊贵度里，
  没把握的标待复核、不写进 claims，待复核没清空检查器判未完成。代价是 dasha 不覆盖、中文效果要自己用
  `jev_claims_eval.py` 验。回归门里前后两轮必须用同一个抽取器，否则抽取差异会被误当成 skill 退步。
