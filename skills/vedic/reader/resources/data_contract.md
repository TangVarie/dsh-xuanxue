# structured_data.md 格式参考（reader）

> **正本是 `shared/data_contract.md`**：产物分工、读取顺序、缺失值四种写法、出生时间与精度、chart_id/audit_id、检查状态都以它为准；本文件与正本不一致时按正本。
>
> 本文件只列 `structured_data.md` 各节的位置与表格格式，用于两件事：
> 1. 读数时知道每一节在哪、各列什么意思；
> 2. 提取兜底模式下按这个格式写提取稿，交给 `calculator/scripts/import_legacy_md.py` 生成 `chart_data.json`（节标题与列顺序要照抄，脚本按标题找表）。
>
> Calc 路径下 `structured_data.md` 由 `build_chart.py` 与 `chart_data.json` 同一次生成，不手改表格；改动只能重算或用脚本（`merge_shadbala.py`、`build_chart.py --from-json`）。
> 验前事结果、验前事校准率、生时矫正记录、信号修正日志属于验证记录，不在本文件里（见文末）。

## 数据源

计算事实只来自 calculator；PDF、截图、文本只做交叉验证，不覆盖计算值。唯一可合并的是同一出生时刻的 JHora PDF Shadbala，且只能用 `merge_shadbala.py` 逐行合并。规则正本 `shared/data_contract.md` §1、§6；reader 的执行细节见 `reader/MODULE.md`「数据源优先级」。

缺失值只写「未提供 / 未计算 / 计算失败 / 不适用」（可附原因），不用空白、`—`、`[待填]` 或 ✅ 代替（`shared/data_contract.md` §3）。表格里结构上不存在的格子（如 Rahu/Ketu 的尊贵列）沿用 calculator 的 `—`（`shared/data_contract.md` §3 的例外）。

---

## 元信息

```
出生日期: YYYY-MM-DD
出生时间: HH:MM
出生地点: [城市] ([经度], [纬度])［括号内为 经度, 纬度］
出生时区: [IANA 时区]（UTC偏移 H:MM:SS）
钟表时间性质: [当地钟表时间 / 标准时]
时间来源: [出生证 / 医院记录 / 家人明确记忆 / 家人记忆 / 本人记忆 / 模糊记忆 / 未追问 / 未知]
声明精度: [用户原话或 ±N分钟 / 未声明]
有效精度: [±分钟级 / ±5分钟 / ±15分钟 / ±1小时 / 不确定]（±N 分钟，来源修正后）
实际审计范围: ±N 分钟（逐分钟扫描）
精度说明: [脚本给出的说明，如"未声明误差，按来源下限 ±1 分钟"；标准时换算说明]
验证轨道: 轨道1-标准
读盘方式: [vedic-calculator直接计算 / 旧版导入 / JH表格 / 文本度数 / 视觉识别+用户确认]
Ayanamsa: [True Chitrapaksha（Lahiri系,差<1′） (度数) / 检测到的其他岁差]
宫位制: 整宫制（Whole Sign）
数据版本: chart_id=<12位> · audit_id=<12位> · 引擎 … · 规则 vedic-5.2
生成时间: [ISO 时间]
机器可读数据: chart_data.json（与本文件同一次计算生成；脚本优先读它）
夏令时: [否 / 是]（UTC偏移 …）
Node模式: [Mean Node / True Node]
```

| 字段 | 含义 |
|---|---|
| 出生时间 | 计算用时间（当地钟表时间）。报的是标准时且出生时处于夏令时，脚本已换算，换算说明见「精度说明」 |
| 出生时区 | IANA 时区名与出生时刻的 UTC 偏移 |
| 钟表时间性质 | 用户报时的性质（`--clock-type`） |
| 时间来源 | 来源决定误差下限：出生证/医院记录 ±1；家人明确记忆/家人记忆 ±5；其余 ±15（`shared/data_contract.md` §4） |
| 声明精度 | 用户自己说的误差或原话（`--declared-min` / `--declared-text`）；没说写「未声明」 |
| 有效精度 | max(声明误差, 来源下限)，括号里是具体分钟数；分盘启用按它取行（`shared/divisional.md` §1） |
| 实际审计范围 | 分盘边界审计实际扫过的范围，必须等于有效精度（`check_chart.py` 核对） |
| 验证轨道 | 排盘时的缺省值；reader 实际分配的轨道写在 `verification_record.json` |
| 数据版本 | chart_id 随出生数据与计算设置变化；audit_id 另含审计范围（`shared/data_contract.md` §5） |

- 不得把没声明的误差写成「±分钟级」。验前事命中不收窄有效精度；收窄只能靠更可靠的来源或 rectifier。
- 时间可信度不单列字段：按 `reader/MODULE.md` Step 5「时间可信度标注规则」由「时间来源」「有效精度」得出（经过 rectifier 时看 `verification_record.json` 的 `rectification` 段）。信号解释置信度在 `verification_record.json`。
- 提取兜底的提取稿：至少写出生日期、出生时间、出生地点（经纬度）、时间来源、Ayanamsa、Node模式；拿不到的字段写「未提供」。

## 用户信息

```
性别: [男 / 女 / 未提供]
感情状态: [单身 / 恋爱中 / 已婚 / 分居 / 离异 / 丧偶 / 未提供]
```

由 `build_chart.py --gender / --relationship` 写入。以下内容不进本文件，写入 `user_context.md`（建档与增量回写见 `reader/MODULE.md` Step 8）：职业状态、核心关切/具体问题、用户补充的人生事件、特质类证据。

## D1基础数据

### 行星位置
| 行星 | 星座 | 宫位 | 度数 | 逆行 |
|------|------|------|------|------|
| Lagna | [sign] | 1 | [deg]°[min]' | — |
| Sun | [sign] | [house] | [deg]°[min]' | [D/R] |
| Moon | [sign] | [house] | [deg]°[min]' | [D/R] |
| Mars | [sign] | [house] | [deg]°[min]' | [D/R] |
| Mercury | [sign] | [house] | [deg]°[min]' | [D/R] |
| Jupiter | [sign] | [house] | [deg]°[min]' | [D/R] |
| Venus | [sign] | [house] | [deg]°[min]' | [D/R] |
| Saturn | [sign] | [house] | [deg]°[min]' | [D/R] |
| Rahu | [sign] | [house] | [deg]°[min]' | R |
| Ketu | [sign] | [house] | [deg]°[min]' | R |

### Chara Karakas
| 排名 | Karaka | 行星 | 有效度数 | 说明 |
|------|--------|------|---------|------|
| 1 | AK | [planet] | [deg] | 灵魂指示星（core板块1/9, career Phase3引用） |
| 2 | AmK | [planet] | [deg] | 事业指示星（career Phase2引用） |
| 3 | BK | [planet] | [deg] | 兄弟指示星 |
| 4 | MK | [planet] | [deg] | 母亲指示星 |
| 5 | PK | [planet] | [deg] | 子女/恋爱指示星（love引用） |
| 6 | GK | [planet] | [deg] | 障碍指示星 |
| 7 | DK | [planet] | [deg] | 配偶指示星（love引用） |

> KN Rao 7K体系：Sun~Saturn 共 7 颗，按宫内度数降序。主表与 DK 用 7K。

### Chara Karakas 7K/8K 对照
| 排名 | 7K Karaka | 7K 行星 | 7K 有效度数 | 8K Karaka | 8K 行星 | 8K 有效度数 |
|------|-----------|---------|------------|-----------|---------|------------|
| 1 | AK | [planet] | [deg] | AK | [planet] | [deg] |
| … | … | … | … | … | … | … |
| 8 | — | — | 不适用 | DK | [planet] | [deg] |

> 8K 体系含 Rahu（度数按 30° 减座内度数计），产生 PiK。8K 只在模块明确要求时参考；下游不得自行补算（`shared/data_contract.md` §6）。旧版导入的盘没有这张表，标「未计算」。

### DK (配偶指示星)
```
DK = [planet]（7K主用）
8K参考 DK = [planet]
```

### Nakshatra
| 行星 | Nakshatra | Pada | Nakshatra主 |
|------|-----------|------|-------------|
| Lagna | [name] | [1-4] | [planet] |
| Sun | [name] | [1-4] | [planet] |
| ... | ... | ... | ... |

### 特殊点位
| 点位 | 星座 | 宫位 | 说明 |
|------|------|------|------|
| AL (Arudha Lagna) | [sign] | [house] | 社会人设/外界形象（core板块8引用） |
| UL (Upapada Lagna) | [sign] | [house] | 婚姻/配偶来源（love引用） |

> 计算规则 (BPHS标准)：
> AL = 1宫主从1宫数X宫，再从1宫主数X宫（X=1宫主距Lagna的距离）
> UL = 12宫主从12宫数X宫，再从12宫主数X宫
> 例外：Arudha不可落在本宫(→取第10宫) 或对宫(→取第4宫)
> 数据来源：calculator；提取兜底时取 JHora 图中 AL/UL 标记或按公式计算并标"公式计算"

## 量化数据

### Shadbala
| 行星 | Rupas | 百分比 | 排名 | 强弱 | IshtaPhala | KashtaPhala | calc基准 | 数据来源/校验 |
|------|-------|--------|------|------|-----------|-------------|----------|---------------|
| [planet] | [展示值] | [展示值]% | [rank] | [强/中/弱] | [val] | [val] | [calc rupas / pct] | [calc / PDF 来源] |

> 强: ≥150% | 中: 100-149% | 弱: <100%
> 默认是 calc 值。同一出生时刻的 JHora PDF 用 `merge_shadbala.py` 逐行合并：PDF 有的行展示采用值，「calc基准」列保留原计算值，「数据来源」列写 PDF 来源；PDF 没有的行保持 calc，不整表覆盖。Ishta/Kashta 目前保持 calc。
> PyJHora 底层 Shadbala 与 JHora 存在系统性偏差（分盘蝴蝶效应、aspect 插值公式、日出折射等），平均每颗行星 1-2 rupas，个别可达 4 rupas：**排序基本正确，数值不精确**。下游引用以排序和强弱分级为准，避免引用具体数值。

### SAV (Sarvashtakavarga)

#### 原始值（按星座，用于校验）
| Ar | Ta | Ge | Cn | Le | Vi | Li | Sc | Sg | Cp | Aq | Pi | 总计 |
|----|----|----|----|----|----|----|----|----|----|----|----|------|
| [n] | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... | [n] | 337 |

#### 宫位映射（按宫位，供core/career/love直接使用）
> Lagna星座: [sign]（第N宫 = 从 Lagna 星座起数第 N 个星座的 SAV 值）

| 1宫 | 2宫 | 3宫 | 4宫 | 5宫 | 6宫 | 7宫 | 8宫 | 9宫 | 10宫 | 11宫 | 12宫 |
|-----|-----|-----|-----|-----|-----|-----|-----|-----|------|------|------|
| [n] | ... | ... | ... | ... | ... | ... | ... | ... | ...  | ...  | [n]  |

### BAV (Bhinnashtakavarga)
| 行星 | Ar | Ta | Ge | Cn | Le | Vi | Li | Sc | Sg | Cp | Aq | Pi | 行和 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|------|
| Sun | | | | | | | | | | | | | 48 |
| Moon | | | | | | | | | | | | | 49 |
| Mars | | | | | | | | | | | | | 39 |
| Mercury | | | | | | | | | | | | | 54 |
| Jupiter | | | | | | | | | | | | | 56 |
| Venus | | | | | | | | | | | | | 52 |
| Saturn | | | | | | | | | | | | | 39 |

### Vimsottari Dasha

> 区间一律按 `[起始, 结束)`：边界日归后一段，相邻区间无缝、无重叠。calc 路径 9 段 MD + 81 段 AD + 729 段 PD；层级检查用 `dasha_query.py --check`（通过 / 失败 / 未完成）。缺哪层就禁用该层分辨率，禁止按比例或 365.25 天补算（`shared/time_window.md` §1）。

| 大运 | 行星 | 起始 | 结束 | 年数 |
|------|------|------|------|------|
| [→当前] | [planet] | YYYY-MM | YYYY-MM | [n] |
| ... | ... | ... | ... | ... |

### 各大运Antardasha表（全部MD）

```
### [MD planet]大运 Antardasha（当前/下一/空）
| 小运 | 起始 | 结束 |
|------|------|------|
| [MD]-[AD planet] | YYYY-MM-DD | YYYY-MM-DD |
```

> 提取兜底提取不到 AD 时，本节写「未提供」；下游只到大运级（背景趋势），不出年月级窗口。

### 各大运Pratyantardasha表（全部MD×AD×PD，calc路径）

```
### [MD planet]大运 Pratyantardasha（三级运）
| 三级运 | 起始 | 结束 |
|----------|------|------|
| [MD]-[AD]-[PD] | YYYY-MM-DD | YYYY-MM-DD |
```

> PD 只支持月级候选与窄于完整 AD 的窗口；默认用 `dasha_query.py --overview` 折叠，按月/日下钻时再读。

当前状态:
```
Mahadasha: [planet] (YYYY-MM ~ YYYY-MM)
Antardasha: [MD]-[AD] (YYYY-MM-DD ~ YYYY-MM-DD)
Pratyantardasha: [MD]-[AD]-[PD] (YYYY-MM-DD ~ YYYY-MM-DD)
```

> "→当前"是生成日的快照；回答时机问题前用今天重新定位（`shared/time_window.md` §7）。

### Chara Dasha 时间线（K.N. Rao，[顺行/逆行]）
> 第二时间系统（Jaimini 星座大运，KN Rao 变体），由 calculator chara_dasha.py 生成；单主座年数上游作者报告与 JHora 双盘 24/24 对照一致，双主座（Scorpio / Aquarius）取主规则与出处见 `timing/resources/chara_dasha_rules.md`。用途见 `shared/time_window.md` §3。起止按出生地日期写。5.1 及更早的引擎排出的表没有后两列，表头会提示重排。

| 大运座 | 起始 | 结束 | 年数 | 所数宫主 | 双主座依据 |
|--------|------|------|------|----------|------------|
| [sign] | YYYY-MM-DD | YYYY-MM-DD | [N] |

> 没有此表（旧版导入、提取兜底）时，下游禁止写"双系统确认 / 共振"，也禁止心算 Chara Dasha。

## 预分析（calculator计算，core直接引用）

### 行星尊贵度（Compound Dignity / Panchadha Maitri）
| 行星 | 落座 | 座主 | 复合尊贵度 | 说明 |
|------|------|------|-----------|------|
| [planet] | [sign] | [lord] | [exalted/own_sign/great_friend/friend/neutral/enemy/great_enemy/debilitated] | [一句话] |

> 旺/入庙/陷直接确定；其余由自然关系 + 临时关系查 Panchadha 合成表。死敌（great_enemy）≠ 落陷（debilitated）。Rahu/Ketu 不参与临时关系。

### Graha Drishti（吠陀行星相位·宫位照射）
| 行星 | 落宫 | 照射宫位 | 照到的行星 |
|------|------|---------|-----------|
| [planet] | [house] | [houses] | [planets] |

> 口径：所有星→第7；Mars +4/8；Jupiter +5/9；Saturn +3/10；Rahu/Ketu 仅第7（对齐底层 jhora）。Rahu 行带「（放大）」标记 = 相位放大/膨胀迷惑。西占度数 orb 相位不属本体系。缺这一节时下游降级，禁止手推。

### calculator 专有的预分析节
「功能身份」「结构格局预扫」「格局关系类 · 互视 / 互溶」「分盘内部宫主表 + 尊贵度（线A）」由 calculator 核验生成，下游照读、禁止自推。提取稿不写这些节；旧版导入与提取兜底的盘里它们是「未计算」。

### 宫主表
| 宫位 | 领域 | 宫主 | 宫主落宫 |
|------|------|------|---------|
| 1 | 自我 | [planet] | [house] |
| 2 | 财富 | [planet] | [house] |
| ... | ... | ... | ... |
| 12 | 损耗 | [planet] | [house] |

## 分盘数据

### 分盘可信度声明
```
边界审计范围: 报时前后±N分钟，逐分钟扫描
D1  ✅ 审计区间内稳定（Lagna=[sign]）
D9  ✅ 审计区间内稳定（Lagna=[sign]）
D10 ⚠️ 边界敏感（Lagna=[sign]→[sign]）；宫位/宫主结论只可条件使用
D4  …
D5  …
```

> 审计范围 = 有效精度。"直接计算成功"与"分盘输入稳定"是两项不同状态；出生证/医院记录也只说明来源可靠度。规则正本 `shared/divisional.md` §1。
> 提取稿没有审计时写 `边界审计范围: 未审计`，不写 D 行；导入后分盘审计为「未计算」，受影响分盘的结论留在条件级。

### D9 Navamsha
| 行星 | D9星座 | D9宫位 | Vargottama | D9尊贵 | D9房东 |
|------|--------|--------|-----------|--------|--------|
| Lagna | [sign] | 1 | — | — | — |
| [planet] | [sign] | [house] | [是/否] | [旺/自庙/陷/友/敌/中性] | [座主] |

> D9尊贵与D9房东由 calculator 查表确定，D9 审计直接读这两列，禁止自行判读。Rahu/Ketu 不出这两列。

Pushkara Navamsa（滋养保护区）: [星名列表 / 无]
Pushkara Bhaga（精确滋养度）: [星名列表 / 无]

### D10 Dasamsha
| 行星 | D10星座 | D10宫位 |
|------|---------|---------|
| Lagna | [sign] | 1 |
| [planet] | [sign] | [house] |

### D4 Chaturthamsha
| 行星 | D4星座 | D4宫位 |
|------|--------|--------|
| Lagna | [sign] | 1 |
| [planet] | [sign] | [house] |

### D5 Panchamsha
| 行星 | D5星座 | D5宫位 |
|------|--------|--------|
| Lagna | [sign] | 1 |
| [planet] | [sign] | [house] |

### 分盘内部宫主表 + 尊贵度（线A · calc 查表，禁自推）
**D[9/10/4/5]** Lagna=[sign]（D*-Lagna主=[行星]）
  宫主(线A): D*-L1=[行星]@H* D*-L2=[行星]@H* …（12宫，以分盘自身 Lagna 起宫）
  分盘尊贵: [星]=[旺/自庙/陷/友/敌/中]/座主[行星] …（7曜）
> 线A / 线B 的定义与禁止项见 `shared/divisional.md` §2。

## 校验结果

> 状态只有三种：通过 / 失败（有明确错误，修复后再用）/ 未完成（缺数据或未执行，只限制对应能力）。

```
 1. SAV=337          通过
 2. BAV行常量        通过
 3. 行星完整性(10)   通过 10/10
 4. 度数唯一性        通过
 5. Ra-Ke差180°      通过
 6. 逆行标记完整      通过
 6b. 燃烧检测        通过 [燃烧行星列表]
 7. Ayanamsa一致     通过 [岁差与度数]
 7c. 盈月/亏月       [盈月/亏月] (距Sun X°)
 8. Nakshatra↔度数   通过
 9. Chara Karaka排序 通过
10. Vimsottari层级   通过 MD=9/AD=81/PD=729（父子归属与命名的完整检查见 check_chart.py）
11. D9公式交叉       通过
12. Ra-Ke分盘校验    通过
13. 精度声明一致     通过（有效精度 ±N = 审计范围 ±N）
14. 分盘边界审计     通过 / 未完成
15. Karaka 7K/8K对照 通过
16. Shadbala         通过
17. 过运快照         通过（提取时间点 YYYY-MM-DD）
```

### 能力范围（由上方检查自动得出）
| 能力 | 状态 | 说明 |
|------|------|------|
| D1 行星星座与度数 | 可用 | |
| D1 上升/宫位/宫主 | 可用 / 条件使用 | 上升在审计范围内换座时分两种上升写 |
| Vimsottari 大运背景（MD）/ 阶段窗口（AD）/ 月级窗口（PD） | 可用 / 条件使用 / 不启用 / 未完成 | 层级检查 × 出生时间误差带来的日期平移（`shared/time_window.md` §1） |
| D9 / D10 / D4 / D5 宫位/宫主/形态 | 可用 / 参考 / 条件使用 / 不启用 | 有效精度矩阵 × 边界审计（`shared/divisional.md` §1） |
| D7 / D30 / D60 | 参考 / 不启用 | |
| 当前行运 | 可用 / 未完成 | 使用前按今天日期做时效检查 |
| 精度声明 | 可用 / 未完成 | |
（读盘导入的数据没有边界审计、精度未声明时，相应各行为「条件使用 / 未验证」。）

> 完整检查以 `check_chart.py --dir <目录>` 的输出为准（退出码 0 通过 / 1 失败 / 2 未完成）。提取兜底的提取类校验定义见 `reader/resources/validation_rules.md`。

## 当前过运位置（Transit Data）

> 数据来源：calculator 自动计算
> 提取时间点：YYYY-MM-DD（快照；超过 90 天或之后已有换座即需更新，见 `shared/versioning.md`）

### 慢行星过运
| 行星 | 过运星座 | 过运宫位(从Lagna数) | 说明 |
|------|---------|-------------------|------|
| Saturn | [sign] | [house] | ~2.5年/星座 |
| Jupiter | [sign] | [house] | ~1年/星座 |
| Rahu | [sign] | [house] | ~1.5年/星座 |
| Ketu | [sign] | [house] | 自动取Rahu对冲 |

### Sade Sati初判
```
Moon本命星座: [sign]
Saturn过运星座: [sign]
相对位置: [Moon前1宫 / Moon本宫 / Moon后1宫 / 非Sade Sati]
Sade Sati状态: [第一阶段(升起) / 第二阶段(顶峰) / 第三阶段(消退) / 未激活]
```

### 双过运触发检查（Saturn-Jupiter Double Transit）
```
Saturn过运相位覆盖宫位: [宫位列表]
Jupiter过运相位覆盖宫位: [宫位列表]
双过运激活宫位: [两者交集]
```

### 未来过运换座时间表（真实天文计算，未来5年）
| 日期 | 行星 | 换座 |
|------|------|------|
| [YYYY-MM-DD] | [Saturn/Jupiter/Rahu] | [from_sign] → [to_sign] |

> 报告/QA 中一切未来过运窗口必须引用本表日期，禁止凭记忆推算换座时间；逆行回跨如实列出。没有此表（提取兜底）时，下游不给带年月的未来过运表述，只写"需实算确认"。

---

## 不在本文件里的内容

「盘面初验结果」「验前事校准率」「生时矫正记录」「信号修正日志」以及信号解释置信度，都属于验证记录，写在 `verification_record.json` / `.md`（格式见 `reader/MODULE.md` Step 8，评分口径见 `shared/validation_scoring.md`）。`structured_data.md` 里出现这些节，`check_chart.py` 判为失败；旧文件用 `import_legacy_md.py` 迁出。
