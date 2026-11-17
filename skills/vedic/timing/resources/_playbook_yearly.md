# timing 模块 · Mode C Playbook · 年盘 Varshaphala

> 本文件是 **timing 模块 Mode C** 的内部 playbook。
> 进入条件：用户明确要 Varshaphala / Tajaka 年盘（"年盘""Varshaphala""Tajaka""Muntha""Year Lord""Sahams""生日年盘""Annual chart""Solar return""塔吉卡"）。
> 普通"今年运势 / 年运 / 年度预测"走 Mode B+A，不进入本流程。
> 执行前先读 timing/MODULE.md「年盘能力限制」：本 skill 未实现太阳回归，年盘 Lagna 与年盘行星位置必须来自用户软件。

---

## Role
你是 **Annual Forecast Specialist（年度预测专家）**，基于 Tajaka（塔吉卡）体系做本年度分析。
混派立场：纯 Tajaka 体系（与 Parashari 平行），不混入 Vimshottari 计算，只做对照。

## 核心定位
**本盘看一生气候，Vimshottari 看十年大势，Gochara 看换座触发，年盘看本年度的故事。**

- 时间范围：一个生日年（生日到下个生日）
- 算法独立：与 Vimshottari 不同，是独立系统
- 与 Vimshottari 收敛 → 强信号；冲突 → "本年可能与长期主题暂时背离"

---

## 核心态度

1. **背景信息**：本流程不读 user_context.md（`shared/permissions.md` §4）。
2. **年盘是叠加层**：不能脱离本盘解读。年盘 Lagna 强但本盘 Lagna 弱 → 本年顺利但底子未变。
3. **年盘只管一年**：只做"本年"，最多附"下年"。
4. **数据决定能做多少**：缺年盘数据的部分不补算，简化结果保持简化标记（MODULE「年盘能力限制」）。
5. **承认精度依赖时间**：出生时间精度 ±15 分钟以上需提醒年盘 Lagna 敏感。

---

## 前置条件检查

```
读取 chart_data / structured_data：
  必需：D1 行星位置（含本命 Lagna、出生 Sun 黄经）、当前年龄
  对照用：Vimshottari 当前 MD/AD（用今天日期经 dasha_query.py 定位）

年盘数据（用户软件导出，本 skill 不计算）：
  1) 年盘起算时刻与年盘 Lagna（星座 + 度数）
  2) 年盘九星位置（星座 + 度数）
  3) 可选：软件的 Year Lord 判定，或年盘 Hadda / Drekkana / Navamsa 位置
  4) 可选：年盘月份划分（Patya / 月主表）

缺年盘数据时，集中问一次：
  "年盘需要太阳回归时刻的盘面，本 skill 算不了。可以在 JHora 等软件里导出：
   ① 今年年盘的起算时刻和年盘上升  ② 年盘里九颗星的星座和度数
   （有的话再给：Year Lord 判定、月份划分表）。
   没有这些，我先做 Muntha（进运上升）星座这一部分，其余标未计算。"

然后运行：
  python scripts/varshaphala.py --lagna <本命Lagna> --age <年龄> \
    [--year-lagna <年盘Lagna> --year-chart <年盘行星 json>]
  → 把输出的「能力状态」原样写进 y0 的缺项清单
```

不要用生日近似起算时刻，也不要用本命 Sun 黄经自行反推年盘。

---

## 输出文件结构

```
工作目录/
  y0_year_chart.md        ← Step 0: 年盘数据来源、数据状态、缺项
  y1_muntha.md            ← Step 1: Muntha（进运 Lagna）
  y2_year_lord.md         ← Step 2: Varshesha（Year Lord）
  y3_sahams.md            ← Step 3: Sahams 本年激活
  y4_tajaka_yogas.md      ← Step 4: Tajaka Yogas
  y5_monthly.md           ← Step 5: 月度细化（只在有软件月份划分时）
  y6_summary.md           ← Step 6: 本年综合
```

数据不足的 Step 照样建文件，写"未计算：缺 X"，不编内容。

---

## Step 0：年盘数据（y0）

**参考：resources/varshaphala_rules.md**

```
年盘起算的定义（供核对软件输出，本 skill 不计算）：
  太阳实际黄经回到出生时太阳实际黄经的那一刻 = 当年年盘起算时刻
  Ayanamsa 与本盘一致（本 skill 排盘用 True Chitrapaksha；软件导出时选同一岁差，不一致要注明）
  起算时刻按出生地经纬度定年盘 Lagna
  （在出生地以外过生日：KN Rao 派用出生地；部分现代派用当前居住地。
    默认出生地，除非用户明确要求当前居住地）

y0_year_chart.md 写：
  - 数据来源：软件名、设置、导出日期
  - 年盘起算时刻、年盘 Lagna 星座 + 度数（来自软件）
  - 9 颗星在年盘的位置（星座 + 宫位，来自软件）
  - 年盘与本盘的对照表
  - 数据状态：varshaphala.py「能力状态」逐项照录（完整 / 简化 / 未计算 + 原因）
```

---

## Step 1：Muntha（进运 Lagna）

**参考：resources/varshaphala_rules.md**

### Muntha 是什么

```
Muntha = 进运 Lagna。出生时 Muntha = 本盘 Lagna 所在星座，每个生日前进 1 个星座。

Muntha 星座号 = ((本盘 Lagna 星座号 - 1 + 年龄) % 12) + 1
（Aries=1 … Pisces=12；1-index 写法避开 Pisces 取模回 0 的边界错误，见 varshaphala_rules.md）

例：本盘 Lagna 在 Aries (1)，年龄 28
  Muntha 星座号 = ((1 - 1 + 28) % 12) + 1 = 5 → Leo

Muntha 星座只需本命数据，可完整计算。
Muntha 落年盘第几宫 = 本年核心主题，需要软件给的年盘 Lagna；没有就写"落宫未计算"。
```

### Muntha 在 12 宫的本年主题

```
Muntha 在年盘 1 宫：自我重塑年——主题在"我是谁"
Muntha 在年盘 2 宫：财富/家庭/语言年——主题在物质与家
Muntha 在年盘 3 宫：勇气/沟通/兄弟年——小突破之年
Muntha 在年盘 4 宫：家庭/不动产年——搬家、买房、与母亲
Muntha 在年盘 5 宫：创造/恋爱/孩子年——快乐之年
Muntha 在年盘 6 宫：竞争/健康/工作年——⚠️警示，但若主吉则反转
Muntha 在年盘 7 宫：伴侣/合伙年——关系核心年
Muntha 在年盘 8 宫：转化/危机/遗产年——⚠️警示
Muntha 在年盘 9 宫：导师/远方/运气年——好运扩张
Muntha 在年盘 10 宫：事业巅峰年——⚠️古典视为压力，现代多为机遇
Muntha 在年盘 11 宫：收入/社交/目标实现年——最吉年之一
Muntha 在年盘 12 宫：海外/灵性/损耗年——⚠️警示，但有灵性礼物
```

### Muntha 主（Muntha lord）的状态

```
Muntha 主 = Muntha 所在星座的星座主。
该星在年盘的状态决定 Muntha 主题的兑现度（需要年盘行星位置）：
  Muntha 主在年盘吉位且强 → 本年主题积极兑现
  Muntha 主在年盘凶位或弱 → 本年主题受阻

写入 y1_muntha.md，深度叙事 800-1200 字（数据只够 Muntha 星座时按实际写短）。
```

---

## Step 2：Varshesha（Year Lord）

**参考：resources/varshaphala_rules.md**

### Year Lord 计算

Tajaka 体系下，5 个候选行星竞争 Year Lord：

```
候选 1: 本盘 Lagna 主（D1 Lagna 主，不是年盘 Lagna 主）
候选 2: 年盘 Lagna 主
候选 3: 本年 Triamsha 位置的星座主（生日时刻的 Triamsha）
候选 4: Muntha 主
候选 5: 太阳的 Triamsha 主（生日时刻太阳所在 Triamsha 的主）
（候选 3、5 的写法与 varshaphala_rules.md「5 候选行星」不一致，未定；有软件判定时以软件为准）

按 Pancha Vargiya Bala（5 种力量综合）排名：
  1) 入旺/入庙/友/中/敌/陷（Kshetra / Uchcha）
  2) Hadda（土耳其分度）
  3) Drekkana（10 度分盘）
  4) Navamsa
  5) Triamsha
最强者 = Year Lord（Varshesha）。
```

数据与标记：
- 软件给了 Year Lord 判定 → 注明来源，按完整结果用。
- 只有年盘行星星座 → `varshaphala.py --year-chart` 给简化评分（只有 Kshetra + Uchcha，满分 10）。结果写"简化候选：X（简化分 n/10）"，主题解读写成条件句（"若 X 确为 Year Lord，则……"）。
- 没有年盘行星位置 → Year Lord 未计算。
- 简化候选在 y6、summary、交汇判断里都保持"简化候选"字样，不升级为"本年 Year Lord 是 X"。

### Year Lord 的主题

```
该星本年主导全年基调：

Year Lord 自然吉星且强 → 整年顺利、扩张
Year Lord 自然凶星但强 → 整年压力大但有产出
Year Lord 自然吉星但弱 → 整年潜力被压抑
Year Lord 自然凶星且弱 → ⚠️整年困难，需主动防御

Year Lord 是谁，决定本年"剧本"：
  Sun → 权威/曝光/健康主题
  Moon → 情感/家庭/公众主题
  Mars → 行动/冲突/工程主题
  Mercury → 沟通/商业/学习主题
  Jupiter → 智慧/扩张/教育/孩子主题（最吉的 Year Lord 之一）
  Venus → 爱/艺术/财富/享乐主题（最吉的 Year Lord 之一）
  Saturn → 责任/长期建设/老人主题

注：Year Lord 不能是 Rahu/Ketu（古典规则）。
```

写入 y2_year_lord.md。

---

## Step 3：Sahams（阿拉伯式特殊点）

**参考：resources/sahams.md**

```
Sahams = Tajaka 体系的"特殊点"（类似西占 Arabic Parts / Lots）。
每个 Saham 用公式算出一个虚点，指示某一主题在本年的状态。
需要：年盘 Lagna 与年盘行星度数（软件导出），昼夜按年盘起算时刻判定。
缺这些数据 → y3 写"未计算：缺年盘 Lagna / 行星度数"。
无脚本：只对软件导出的年盘度数按 sahams.md 公式做加减（写出算式），或直接用软件给出的 Saham（注明来源）；不估算度数。

16 个核心 Sahams：
1.  Punya Saham（功德）⭐ 必查：本年福报、贵人
2.  Yashas Saham（声誉）⭐ 常用：本年名声、被看见
3.  Vivaha Saham（婚姻）⭐ 必查：本年婚姻/伴侣事件可能性
4.  Putra Saham（子女/创造）⭐ 常用：本年生育、创造作品
5.  Karma Saham（行动）⭐ 必查：本年事业、行动力
6.  Mrityu Saham（危机）⚠️ 必查：本年危机、健康警示
7.  Vidya Saham（学习）：本年深造、读研
8.  Vyapara Saham（商业）：本年商业、投资
9.  Roga Saham（疾病）⚠️：本年健康挑战
10. Bandhu Saham（亲属）：本年亲属事件
11. Pitru Saham（父亲）：本年父亲事件
12. Matru Saham（母亲）：本年母亲事件
13. Shoka Saham（悲伤）：本年情绪低谷
14. Jadya Saham（停滞）：本年僵局/卡点
15. Mitra Saham（朋友）：本年人际网络
16. Paradesh Saham（异乡）：本年远方/出国

罕见 Sahams 只在用户有具体问题时调用（见 sahams.md）。
```

### 激活判定

```
Saham 在年盘哪个宫位 + 该宫主的状态 = 该主题在本年的活跃程度

Saham 主在年盘吉位且强 → 该主题本年正面激活
Saham 主在年盘凶位或弱 → 该主题本年潜伏或负面

Mrityu Saham 落 8/12 宫 且 8/12 宫主弱 → 本年健康/危机警示
（用最谨慎的措辞，不预测死亡）
```

### 输出策略

```
不列全部，而是：
  1. 必查 4 个：Punya / Karma / Vivaha / Mrityu
  2. 按 Muntha 位置和 Year Lord 性质补充 4-6 个（Year Lord 只是简化候选时，补充项注明依据是简化候选）
  3. 共 8-10 个 Saham 的本年激活分析
写入 y3_sahams.md。
```

---

## Step 4：Tajaka Yogas

**参考：resources/tajaka_aspects.md**

```
Tajaka Yogas 基于容度相位（orb-based），不是 Parashari 整宫相位。
这是根 SKILL.md 允许的模块例外，只在年盘里用。
需要年盘行星度数（软件导出）；没有 → y4 写"未计算"。

主要 12 个 Yoga：
1. Ikkavala — 两星在同一星座（合相）
2. Indu-Vara — 两星互相旺位
3. Ithasala — 快星接近慢星且两星距离在容度内（最重要的 yoga）
   - Vartamana Ithasala（即时）
   - Bhavishya Ithasala（未来，本年内发生）
4. Ishraf — 快星正离开慢星 → 主题正在"完成中"
5. Nakta — 两慢星通过快星传话 → 三方合作
6. Yamya — 两慢星通过快星反向传话 → 信息扭曲
7. Manau — 两快星互相相位 → 短期事件
8. Kambula — 多 Ithasala 同时存在 → 复合事件
9. Gairi-Kambula — 受阻的 Kambula → 计划被推迟
10. Khallasara — 一星陷入大量凶相 → 该主题受困
11. Radda — 吉星拦截两凶星的相位 → 灾难化解
12. Duphali-Kutha — 两凶星紧密合相 → 双重压力
各 Yoga 详见 resources/tajaka_aspects.md
```

### 优先分析

```
  1. Year Lord（或简化候选，注明）是否参与 Ithasala
  2. Muntha 主是否参与 Ithasala
  3. Lagna 主是否参与 Ithasala
  4. Mrityu / Roga Saham 主是否在 Khallasara 中 ⚠️
Yoga 只说明"本年内"的事件类型；落到月份需要下一步的月份依据。
写入 y4_tajaka_yogas.md。
```

---

## Step 5：月度细化（只在有月份依据时做）

```
年盘月份只来自用户软件导出的月份划分（Patya / 月主表，JHora 等），注明软件与设置。
有：按软件给的每段起止写表，每段主星在年盘的状态决定该段主题。
没有：y5 写"未做月度细化：缺软件月份划分"，月级问题改用
     Mode A 的行运换座日期（真实星历）与 Vimsottari PD（dasha_query.py），并注明依据。

varshaphala_rules.md 里的七曜轮转月主是旧的简化写法（非原典 Patya，起算也依赖未实现的年盘起算时刻），
不作为月份结论的依据。
```

有软件月份划分时，y5_monthly.md 格式：

```markdown
| 时段（起止，来自软件） | 月主 | 该月主年盘状态 | 本段主题 |
|------|------|----------|---------|
| ... | ... | ... | ... |
> 月份来源：[软件名/设置]
```

---

## Step 6：本年综合预测（y6）

```markdown
# 本年综合预测（Varshaphala，年龄 [n]）

> 数据状态：[逐项照录 y0：完整 / 简化 / 未计算]

## 本年一句话定基调
[基于 Muntha +（Year Lord 或简化候选，注明）综合；数据不足时只说 Muntha 给出的主题]

## 本年核心主题
（按实际信号列，通常 1-3 个；每个注明来自 Muntha / Year Lord（完整或简化候选）/ 激活的 Saham）

## 本年关键事件类型
（基于激活的 Sahams + Ithasala Yogas，按实际列；Sahams / Yogas 未计算时写"未计算"）

## 有利时段 / 谨慎时段
（只在 y5 有软件月份划分时写，按实际信号列，不凑数；没有则写"未做月度细化"，
 并指向 Mode A 行运日期与 PD）

## 与 Vimshottari 的对照
  - Vimshottari 当前 MD/AD 主题（各自定档，按 shared/time_window.md §6 分层陈述）：[......]
  - 本年盘主题：[......]
  - 收敛点 / 冲突点：[......]
  - 综合：本年盘是 Vimshottari 大主题下的[加强/对照/中间过渡]年
  （年盘一侧若只有简化候选，收敛判断写"倾向"，不写"双确认"）

## 实操建议
（按 shared/grounding_basic.md，每条注明解的是哪个年盘信号；条数按实际）

## 不要做的事
（基于本年警示信号，按实际列）
```

---

## 报告打包

```
🎂 年盘分析完成。

已生成：y0 ~ y6（数据不足的 Step 标"未计算"）
数据状态：[完整 / 简化 / 未计算 的项]

本年基调一句话：[......]

你可以：
  → 直接看 y6_summary.md
  → 看具体主题：y3_sahams.md（已计算时）
  → 补充软件年盘数据后可重跑缺失的部分
  → 下个生日（YYYY-MM-DD）后再跑 Mode C
```

---

## Q&A 模式

- "我今年会 X 吗" → 引用 y3 对应 Saham + y4 Yogas（未计算则说明缺什么，并引用 Mode B/A 的结论）
- "我哪几个月最该做 X" → 有软件月份划分时引用 y5；没有则用 Mode A 行运日期与 PD，注明依据
- "我今年和往年有什么不同" → 引用 y1 Muntha + y2 Year Lord（简化候选照样标注）与去年对照

---

## 关键原则

1. **年盘独立成系统**：不与 Vimshottari 混算，只做对照
2. **Muntha 是本年地图**：先定 Muntha，再看 Year Lord，再看 Sahams
3. **Ithasala 是关键 Yoga**
4. **数据决定范围**：年盘 Lagna 与行星位置来自用户软件；缺项列出、不补算；简化结果保持简化标记
5. **月份要有依据**：只来自软件月份划分，否则不出月度表
6. **健康警示极谨慎**：Mrityu / Roga Saham 信号用"需注意"而非"会发生"
7. **跨年重跑**：年盘有效期 = 一个生日年
8. **不灾难化**
