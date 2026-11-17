# schema · canonical_facts.json / skill_claims_*.json

两者字段同构；`canonical_facts` 是完整的源数据真相，`skill_claims` 是各 skill 断言的**子集**。

## canonical_facts.json （5.1 起从 chart_data.json 蒸馏）

| canonical 字段 | chart_data.json 路径 | 换算 |
|---|---|---|
| `chart_id` | `chart_id` | 原样（12 位） |
| `ak` | `chart.karakas.7k[0][1]` | 7k 每项是 `[名称, 行星, 度数]`，第一项即 AK；主表用 7K（`shared/data_contract.md` §6），不用 8K |
| `d9_lagna` | `chart.d9.Lagna[1]` | d9 每项是 `[星座名, 星座序号 0..11]`，+1 得 1..12 |
| `planet_sign.<P>` | `chart.planets.<P>.sign` / `chart.planets.<P>.sign_idx` | `sign` 是英文星座名；`sign_idx` 是 0..11，+1 得 1..12 |
| `house_lords."1".."12"` | `chart.house_lords."<n>".lord` | 同时用 `cutil.house_lords(chart.lagna.sign_idx + 1)` 推一遍，两者必须一致；不一致先查盘数据 |
| `planet_dignity.<P>` | 不取 `chart.dignity` | 一律 `cutil.dignity(P, planet_sign[P])`（盘数据里的 compound 尊贵度是另一套分档，旧盘导入的还带着 reader 的提取结果） |
| `dasha[].lord` / `.start` / `.years` | `chart.dashas[i].planet` / `chart.dashas[i].antardashas[0].start` / `chart.dashas[i].years` | MD 的 `start` 只到月（YYYY-MM），取第一个 AD 的 `start`（完整日期，与 MD 起点相同）；旧盘导入没有 `years` 时按 Vimshottari 常数填（Ke7 Ve20 Su6 Mo10 Ma7 Ra18 Ju16 Sa19 Me17） |

- 值是 `{"_missing": …}`（未提供 / 未计算 / 计算失败 / 不适用，`shared/data_contract.md` §3）的字段不进 canonical，不补值；
  仅日期模式的盘没有上升、宫主、D9、Dasha、Karaka，能比的只剩行星星座。
- 没有 `chart_data.json` 的旧盘：先 `calculator/scripts/import_legacy_md.py` 导入再按上表取，或从 `structured_data.md` 按同样字段手工蒸馏。

```jsonc
{
  "chart_id": "string",
  "ak": "Sun",                          // Atmakaraka（度数最高，无争议）
  "d9_lagna": 9,                        // D9 上升星座 1..12
  "house_lords": {                      // 12 宫主，键 '1'..'12'，值=行星名
    "1": "Moon", "2": "Sun", "3": "Mercury", "4": "Venus",
    "5": "Mars", "6": "Jupiter", "7": "Saturn", "8": "Saturn",
    "9": "Jupiter", "10": "Mars", "11": "Venus", "12": "Mercury"
  },
  "planet_sign": {                      // 7 行星落座 1..12（可含 Rahu/Ketu）
    "Sun": 2, "Moon": 11, "Mars": 12, "Mercury": 2,
    "Jupiter": 3, "Venus": 1, "Saturn": 10
  },
  "planet_dignity": {                   // Exalted / Debilitated / Own / Other
    "Sun": "Other", "Saturn": "Own", "...": "..."
  },
  "dasha": [                            // 大运边界
    { "lord": "Venus", "start": "1989-01-01", "years": 20 },
    { "lord": "Sun",   "start": "2009-01-01", "years": 6 }
  ]
}
```

## skill_claims_<skill>.json （从某 skill 的输出抽取）

只放该 skill **明确陈述为事实**的项；没断言的字段直接省略。

用 `jev_extract_claims.py` 抽出来的文件还会多一个 `_extractor` 字段（下划线开头，比对时忽略，只有 `pending` 会被读）：
`engine`（jev / baseline）、`models`、`bank_version`、`calls`、`pending_review`、`pending`（待复核字段列表，
如 `["house_lords.10"]`；非空时 `check_consistency.py` 判未完成、退出码 2，不给通过）、`source`（报告路径）。

```jsonc
{
  "skill": "career",                    // core | career | love | soul
  "ak": "Sun",                          // 可选
  "d9_lagna": 9,                        // 可选
  "house_lords": { "1": "Moon", "10": "Mars" },   // 可选，部分
  "planet_sign": { "Venus": 1 },        // 可选，部分
  "planet_dignity": { "Saturn": "Own" },// 可选，部分
  "dasha": [ { "lord": "Venus", "start": "1989-01-01", "years": 20 } ]  // 可选
}
```

## 比对规则（check_consistency.py）

| 字段 | 类型 | 保真度 | 跨 skill |
|---|---|---|---|
| `ak` / `d9_lagna` | 单值 | 与 canonical 相等 | 各 skill 之间相等 |
| `house_lords` / `planet_sign` / `planet_dignity` | 字典逐键 | 每键值与 canonical 相等 | 同键被多 skill 断言时彼此相等 |
| `dasha` | 列表(按 lord) | lord+起点(±31天)+周期一致 | — |

## 行星名 / 星座编号

行星：`Sun Moon Mars Mercury Jupiter Venus Saturn Rahu Ketu`。
星座：1=Ar … 12=Pi（`cutil.SIGN_NAMES`）。

> 抽取省事做法：把某 skill 的输出粘给 Claude，说"按 eval/consistency 的 schema
> 抽 skill_claims_<skill>.json，只抽它陈述为事实的确定性项"。
> canonical_facts.json 按上面的路径表从 chart_data.json 取，尊贵度与宫主用 cutil 推，不靠粘贴让模型转写。
