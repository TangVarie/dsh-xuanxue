# 档案格式 v1：case.json 与 index.json

玄学台前端只读两个位置：`xuanxue-cases\index.json`（列表页）与 `xuanxue-cases\<id>\case.json`（详情页）。
本文件是这两个文件的字段正本；`xuanxue-orchestra/SKILL.md` 第九节规定何时写，本文件规定写成什么样（含 2.9 的 `cross` 跨门拟合块）。
写入方：玄学台「玄学」预设里的 agent；用户可手改，但改完必须仍过第六节校验。其他会话不要写这个库。

## 〇、通用约定

- 编码 UTF-8、无 BOM；严格 JSON：无注释、无尾逗号、无 `NaN`/`Infinity`/`undefined`，键名双引号。
- 时间是字符串：`createdAt`、`updatedAt`、`readings[].at`、`verificationLog[].at` 用带偏移的 ISO 8601（`2026-11-16T10:00:00+08:00`，允许秒后小数）；`nextCheck`、`birth.date` 只用日期（`2027-03-01`）；`birth.time` 只用 24 小时制 `HH:MM`。
- 默认时区 Asia/Shanghai（+08:00）；用户明确在别的时区出生/起卦时，`birth.tz` 与时间戳用对应的 IANA 名与偏移，并在 `params.notes` 说明。
- 不新增、不改名本文件没列的字段。前端按白名单渲染，多一个没约定的字段可能整块不显示；确实需要新字段，先改本文件并同步改前端，再写档。
- 数字字段用数字（`lng`、`sav`、`version` 等），不要写成字符串。

## 一、index.json

列表页唯一数据源；不扫目录。整档增删改都要同步这里，缺席的 case 不会显示。

```json
{"version":1,"cases":[]}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `version` | number | 是 | 固定 `1` |
| `cases` | array | 是 | 可为空数组；每项一行摘要，结构见下 |
| `cases[].id` | string | 是 | 与 case 目录名、case.json 的 `id` 完全一致 |
| `cases[].title` | string | 是 | 与 case.json 一致；建议 `主语 · 体系 · 焦点` |
| `cases[].subject` | string | 是 | 命主/问事人的显示名，与 `case.subject.label` 一致 |
| `cases[].systems` | string[] | 是 | 非空；只允许 `bazi` `liuyao` `ziwei` `vedic`；与 case.json 一致，且等于实际跑过的门 |
| `cases[].focus` | string[] | 是 | 可为空数组；与 case.json 一致 |
| `cases[].createdAt` | string | 是 | 带偏移 ISO 8601；与 case.json 一致 |
| `cases[].updatedAt` | string | 是 | 带偏移 ISO 8601；等于 case.json 的 `updatedAt`；≥ `createdAt` |
| `cases[].status` | string | 是 | 只允许 `draft` `read` `verified` `invalidated` |
| `cases[].verification` | string | 是 | 只允许 `untested` `fitted` `blind-checked` `forward-checked` |
| `cases[].confidence` | string | 是 | 只允许 `high` `medium` `low` `none` |
| `cases[].summary` | string | 是 | 一句话核心结论，≤80 字，与 case 的结论一致；多门 case 要概括 `cross` 的交叉结论：有 agree 写共同结论，未决冲突写分歧主题 |
| `cases[].nextCheck` | string | 否 | `YYYY-MM-DD`；没有待复核窗口就省略该键 |
| `cases[].sessionId` | string | 否 | 最近一次解读的会话 id；拿不到就省略 |

维护规则：

1. 一个 case 恰好一行；`id` 全局唯一；写完重读检查没有重复行、没有指向不存在目录的行。
2. 排序按 `updatedAt` 降序（最新在前），前端再自行排序也不会出错。
3. 更新 case 时先读现网 index，只改对应的那一行再整体写回，避免覆盖别处新增的行。
4. index 的值都是派生的：以 case.json 与验证记录为准。两处不一致时改 index 去对齐 case.json。
5. index 不为 `cross` 新增字段；多门 case 的交叉结论由 `summary` 承担，`systems` 只能列实际跑过的门。

## 二、case.json

### 2.1 顶层

| 字段 | 类型 | 必填 | 规则 |
|---|---|---|---|
| `version` | number | 是 | 固定 `1` |
| `id` | string | 是 | 见第四节；等于目录名 |
| `title` | string | 是 | 非空；与 index 一致 |
| `subject` | object | 是 | 见 2.2 |
| `systems` | string[] | 是 | 非空；只允许四门；与实际跑过的门一致 |
| `focus` | string[] | 是 | 可为空；建议词表见第三节 |
| `params` | object | 是 | 见 2.3 |
| `charts` | object | 否 | 见 2.4；没有关键值可省略 |
| `cross` | object | 否 | 跨门拟合汇总；见 2.9；`systems` ≥2 门时必填，单门 case 省略整个键 |
| `conclusions` | array | 是 | 可为空；见 2.5 |
| `timing` | array | 是 | 可为空；见 2.6 |
| `readings` | array | 是 | 可为空；见 2.7 |
| `verificationLog` | array | 是 | 可为空；见 2.8 |
| `createdAt` | string | 是 | 建档时刻，带偏移 |
| `updatedAt` | string | 是 | 最后一次写入时刻，带偏移，≥ `createdAt` |

`status`、`verification`、`confidence`、`summary`、`nextCheck`、`sessionId` **只存在 index 行**，不写进 case.json。

### 2.2 subject

由参数卡映射：卡片 `label`→`label`、`sex`→`sex`、其余出生字段→`birth`（SKILL 第二节）；自动模式从「已知信息」映射，缺的字段省略并在 `params.notes` 写缺什么；各门口径差异写进 `params.notes`。

| 字段 | 类型 | 必填 | 规则 |
|---|---|---|---|
| `label` | string | 是 | 显示名，如「陈某」；不写全名也允许，但要能区分命主 |
| `sex` | string | 是 | 只允许 `male` `female` `unknown`；紫微必须 `male`/`female`，不知道就先问，不得用 `unknown` 排紫微 |
| `birth` | object | 是 | 出生/起卦参数，见下表 |

`birth` 字段：

| 字段 | 类型 | 必填 | 规则 |
|---|---|---|---|
| `calendar` | string | 是 | 只允许 `gregorian` `lunar`；吠陀只收 `gregorian` |
| `leapMonth` | boolean | 是 | 农历是否闰月；`gregorian` 时固定 `false` |
| `date` | string | 是 | `YYYY-MM-DD` |
| `time` | string | 否 | `HH:MM`（24 小时制）；确实没有时间（八字只有日期、吠陀 `--date-only`）时省略，并在 `params.notes` 写「无出生时间」 |
| `uncertaintyMinutes` | number | 否 | ≥0 的整数；时间不确定时给容差，省略按 0 处理；时辰跨界时在 `params.notes` 记录候选盘处理结果 |
| `place` | string | 否 | 出生地或起卦地原文，如「上海」「杭州」；海外写「城市, 国家」 |
| `lng` | number | 否 | 经度，-180～180；与 `place` 至少给一个，缺经度时按出生地城市换算 |
| `tz` | string | 否 | IANA 时区名（`Asia/Shanghai`）或固定偏移（`+08:00`）；海外出生必填 |
| `timeSource` | string | 否 | 时间来源：`birth-certificate` `hospital` `family` `vague` `unknown`（与起课台同值）；校时后写原来源，校时本身写进 `params.notes` |
| `clockType` | string | 否 | 用户报的是什么时间：`clock`（当地钟表时间）`standard`（标准时）`mean-solar`（平太阳时）`true-solar`（真太阳时）；省略按 `clock` |

**卜卦 case 的 `birth` 不是出生**：六爻记**起卦时刻与起卦地**，prashna 记**提问时刻与提问地**（提问时刻秒级、`date`/`time` 保留到分，秒写 `params.notes`；经纬度与时区必须能确定）。两者 `subject.sex` 可 `unknown`（prashna 不需要性别），`params.notes` 必须写明「起卦盘」或「prashna 提问盘，不读本命、不做验前事」；`systems` 仍是 `liuyao` / `vedic`。

### 2.3 params

| 字段 | 类型 | 必填 | 规则 |
|---|---|---|---|
| `card` | string | 是 | 起课台平面参数卡原文（SKILL 第二节：出生字段与 `birth` 块同名，另有 `system`/`systems`/`focus`；自动模式可为 `system:"auto"` 加 `question`/`expect`，可补 `label`/`notes`）；原样保存，不改写成 subject 嵌套；换行写成 `\n` |
| `notes` | string[] | 否 | 口径、候选盘、缺失值、无法判定原因、下一步说明等；一条一句 |

### 2.4 charts

只放各门关键值，完整盘面留在读数文件或 `chart/` 里，本对象不放大段文本。

| 键 | 结构 | 说明 |
|---|---|---|
| `bazi` | `{"pillars":"庚午 壬午 辛亥 壬辰","extra":{}}` | `pillars` 四柱原文；`extra` 自由对象（大运、起运等） |
| `ziwei` | `{"mingGong":"辛未","ju":"土五局"}` | 命宫干支、五行局；可加 `shenGong` 等短字段 |
| `liuyao` | `{"benHexagram":"水火既济","bianHexagram":"山火贲"}` | 本卦、变卦；无变卦省略 `bianHexagram` |
| `vedic` | `{"lagna":"Virgo","sav":337}` | 上升星座、SAV 等关键值；数字用数字 |

规则：键只能是 `systems` 里出现过的门；没跑的门省略整个键；`charts` 与 `systems` 不一致时以前者为准回改（写档前统一）。契约示例里的四个键只是字段形状示意，实际写档只写实际跑过的门。

### 2.5 conclusions

| 字段 | 类型 | 必填 | 规则 |
|---|---|---|---|
| `text` | string | 是 | 判词本体，一句话到三句话 |
| `evidence` | string | 是 | 依据：做功点/宫星/四化/信号，写不出来由的结论不许进档 |
| `system` | string | 是 | 四门之一，且在该 case 的 `systems` 里 |
| `tag` | string | 是 | 该门自己的标签原话：八字/紫微用 `铁断` `推断` `存疑` `不作判断`；六爻用 `高` `中` `低`；吠陀用 `低` `中` `高`。不跨门混用 |
| `verification` | string | 是 | 中文验证状态：`未验证` `已知事实拟合` `盲测核验` `前瞻检验` |
| `window` | string | 否 | 涉及时间才写：`2027 春`、`2027-02..2027-04`、`2027`；不涉及就省略 |

多门结论分开写，一条 `system` 只归一门；不得把两门说法合成一条 `evidence`（见 SKILL 第六节）。

### 2.6 timing

应期表，事前写死，事后只改 `status`。

| 字段 | 类型 | 必填 | 规则 |
|---|---|---|---|
| `window` | string | 是 | 时间窗：区间 `YYYY-MM..YYYY-MM`、单日 `YYYY-MM-DD` 或 `2027 春`；写窗口不写模糊词 |
| `event` | string | 是 | 可观察事件，写「什么算应验」，不写「运势好」这类不可判定的说法 |
| `status` | string | 是 | 只允许 `pending` `hit` `miss` `partial` |

### 2.7 readings

| 字段 | 类型 | 必填 | 规则 |
|---|---|---|---|
| `file` | string | 是 | 相对 case 目录的 POSIX 路径，`readings/YYYY-MM-DD-<system>.md`；文件必须存在 |
| `at` | string | 是 | 写入时刻，带偏移；不晚于对应结论的对外交付时刻 |
| `sessionId` | string | 否 | 产生该次解读的 DSH 会话 id |

读写数文件本身用 Markdown，首行写 `# <日期> <门> <焦点>`，正文保留判词、依据、给用户的原文。

### 2.8 verificationLog

| 字段 | 类型 | 必填 | 规则 |
|---|---|---|---|
| `at` | string | 是 | 复盘时刻（不是事发时刻），带偏移；必须晚于被核对的 `readings[].at` |
| `item` | string | 是 | 被核对的条目，引用 `timing[].event` 或 `conclusions[].text` 的原话 |
| `result` | string | 是 | 只允许 `hit` `miss` `partial`；无法判定不写这里（见 SKILL 第十节） |
| `note` | string | 否 | 实际发生了什么、为什么算命中/未中/部分；建议写，便于复核 |

只追加，不改旧条目；同一件事复核多次就多条按时间排。

### 2.9 cross（跨门拟合汇总）

多门 case 的调度说明与交叉拟合结论，前端详情页按「调度说明 / 共同支持 / 冲突与分辨 / 缺口」四段渲染。**单门 case 省略整个 `cross` 键**（不写空对象）；`systems` 有两门及以上时必须写。字段名与大小写固定，不得改写。

| 字段 | 类型 | 必填 | 规则 |
|---|---|---|---|
| `plan` | string | 是 | 一句话说清为什么选这几门、为什么不需要其他门；不写「综合多门」这类空话 |
| `agree` | array | 否 | 多门共同支持项；没有就省略该键 |
| `agree[].statement` | string | 是 | 共同支持的结论，一句话；必须能由对应门的 `conclusions` 支撑 |
| `agree[].systems` | string[] | 是 | 至少 2 项，每项 ∈ case 的 `systems`；只写实际给出独立依据的门 |
| `agree[].strength` | string | 是 | 只允许 `strong` `medium`（见 3.1）；没有 high/low |
| `conflicts` | array | 否 | 真冲突；「一门支持、一门未覆盖」不是冲突，不写这里 |
| `conflicts[].topic` | string | 是 | 分歧主题，一句话 |
| `conflicts[].readings` | array | 是 | 至少 2 项，一项一门读法 |
| `conflicts[].readings[].system` | string | 是 | ∈ case 的 `systems` |
| `conflicts[].readings[].text` | string | 是 | 该门读法原话，不合并成折中话 |
| `conflicts[].condition` | string | 是 | 非空；写可观察预测或可问的事实说明怎样分辨两读；不写「看后续发展」 |
| `gaps` | array | 否 | 缺口清单；建议 ≤3，超过 3 条先问最关键 3 条 |
| `gaps[].missing` | string | 是 | 缺什么：生日、时辰、摇卦、某段经历、某时间点事件 |
| `gaps[].why` | string | 是 | 能区分什么 |

规则：

1. `cross` 不替代 `conclusions`/`timing`：判词与应期仍各写各的，`cross` 只是汇总视图；`agree.statement` 要有对应门的 `conclusions` 支撑。
2. `cross` 里出现的门必须都在 `systems` 里（实际跑过的门）；没跑或不可用的门不得出现在 `agree`/`conflicts` 里。
3. 未决冲突（`conflicts` 非空且 `condition` 未判）时，index 的 `confidence` 最高 `medium`，`summary` 写「A 与 B 分歧在 X」，不写成单门结论。
4. `cross` 可随新证据修订：刷新 `updatedAt`，并在 `params.notes` 记一句为什么改；历史判定照旧进 `verificationLog`。
5. 没有内容的数组省略键，不写 `null`，也不写空字符串占位。

## 三、枚举与派生

### 3.1 枚举总表

| 字段 | 允许值 | 含义 |
|---|---|---|
| `systems[]` | `bazi` `liuyao` `ziwei` `vedic` | 八字 / 六爻 / 紫微 / 吠陀；中文只出现在 title 里 |
| `status` | `draft` `read` `verified` `invalidated` | 草稿（建卡/已排盘未交付）/ 已交付解读 / 验证闭环已走一轮 / 作废（参数或盘错、结论被明确证伪） |
| `verification` | `untested` `fitted` `blind-checked` `forward-checked` | 未验证 / 已知事实拟合 / 盲测核验 / 前瞻检验（与四门用语一一对应） |
| `confidence` | `high` `medium` `low` `none` | 与【铁断】【推断】【存疑】/不作判断对应 |
| `timing[].status` | `pending` `hit` `miss` `partial` | 待验 / 命中 / 未中 / 部分 |
| `verificationLog[].result` | `hit` `miss` `partial` | 同上，不允许 `pending` |
| `cross.agree[].strength` | `strong` `medium` | 共同支持强度：两门证据都实、无未解决反证为 `strong`；一门较弱或间接为 `medium` |
| `sex` | `male` `female` `unknown` | 男 / 女 / 未知 |
| `birth.calendar` | `gregorian` `lunar` | 公历 / 农历 |
| `birth.timeSource` | 见 2.2 | 时间来源五值 |
| `birth.clockType` | `clock` `standard` `mean-solar` `true-solar` | 所报时间的性质 |

### 3.2 status 状态机

`draft` → `read` → `verified`；任一状态可 → `invalidated`（保留目录与文件，不删除）。

- `draft`：已有参数卡/盘/读数，但还没交付完整解读，或解读仍在进行。
- `read`：已把解读交付给用户（`readings` 非空），结论可含未验证项。
- `verified`：至少一条 `timing` 已判定 `hit`/`miss`/`partial` 且 `verificationLog` 有对应条目。
- `invalidated`：出生参数或盘面错误、结论被明确证伪、技能重排后整盘作废；`summary` 写一句作废原因。
- 只进不退；`verified` 之后发现作废才转 `invalidated`。

### 3.3 verification 与 confidence 的派生

- `verification` 取本 case 已完成的最高档：无证据 `untested`；只有事后对照 `fitted`；事前落档、事后由外部结果核对过去事件 `blind-checked`；落档时尚未发生的预测到点完成判定 `forward-checked`（命中、未中、部分都算完成）。技能版本变了不套用旧成绩。
- `confidence`：`high` 需至少一条【铁断】级且无未解决【存疑】；`medium` 主体【推断】（六爻/吠陀的中）；`low` 主体【存疑】或依赖候选盘/未定口径；`none` 只有排盘或资料解释。`cross.conflicts` 未决（`condition` 尚未判定）时最高 `medium`。
- `summary` ≤80 字，一句话结论，不写套话。
- `nextCheck` 取最早一个 `pending` 窗口的结束日（季节窗按保守末日手写并在 `params.notes` 说明）；没有 `pending` 就省略。
- `sessionId` 取最近一条 `readings[].sessionId`；没有就省略。

### 3.4 focus 词表

`career` `wealth` `marriage` `family` `health` `timing` `study`——与起课台一致，只用这 7 个 id；没有合适的焦点就留空数组，不自造词（前端按 `focus.<id>` 取中文）。

## 四、id 规则

```
YYYY-MM-DD-<subject>-<system>-<focus>      例：2026-11-16-chen-bazi-career
YYYY-MM-DD-<subject>-multi-<focus>         多门同看时第二段写 multi
```

- 日期用建档日（不是出生日），`YYYY-MM-DD`。
- `<subject>` 用姓氏拼音或匿名代号，小写；`<system>` 用第一个主门或 `multi`；`<focus>` 用 3.4 的词。
- 只允许小写字母、数字、连字符：`^[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9]+(?:-[a-z0-9]+)*$`。
- 同一天、同一命主、同一门、同一焦点的第二条加 `-2`（再往后 `-3`）。
- `id` 一经写入不得修改；改名等于新建一档，旧档 `status` 改 `invalidated` 保留。
- 目录名必须等于 `id`；`readings/`、`chart/` 是保留子目录名。

## 五、完整示例（假数据，可直接过校验）

### 5.1 index.json（一个多门 case + 一个单门 case，按 updatedAt 降序）

```json
{"version":1,"cases":[{"id":"2026-11-20-zhou-liuyao-timing","title":"周某 · 六爻 · 应期","subject":"周某","systems":["liuyao"],"focus":["timing"],"createdAt":"2026-11-20T21:10:00+08:00","updatedAt":"2026-11-20T21:10:00+08:00","status":"read","verification":"untested","confidence":"medium","summary":"问下月面试结果：用神得生、动爻化退，窗口在 12 月上旬，主动确认有助。","nextCheck":"2026-12-15","sessionId":"session-demo-0002"},{"id":"2026-07-28-lin-bazi-career","title":"林某 · 八字与紫微 · 事业","subject":"林某","systems":["bazi","ziwei"],"focus":["career"],"createdAt":"2026-07-28T21:30:00+08:00","updatedAt":"2026-11-16T10:20:00+08:00","status":"verified","verification":"forward-checked","confidence":"medium","summary":"组织内执行型底色，2026 秋职责扩张已部分应验；管理幅度时点八字看 2027 春、紫微看 2026 年内，待辨。","nextCheck":"2027-04-30","sessionId":"session-demo-0001"}]}
```

### 5.2 多门 case.json（带 `cross`）

```json
{
  "version": 1,
  "id": "2026-07-28-lin-bazi-career",
  "title": "林某 · 八字与紫微 · 事业",
  "subject": {
    "label": "林某",
    "sex": "female",
    "birth": {
      "calendar": "gregorian",
      "leapMonth": false,
      "date": "1988-03-12",
      "time": "07:20",
      "uncertaintyMinutes": 5,
      "place": "杭州",
      "lng": 120.16,
      "tz": "Asia/Shanghai",
      "timeSource": "family",
      "clockType": "clock"
    }
  },
  "systems": ["bazi", "ziwei"],
  "focus": ["career"],
  "params": {
    "card": "{\"system\":\"multi\",\"systems\":[\"bazi\",\"ziwei\"],\"calendar\":\"gregorian\",\"leapMonth\":false,\"date\":\"1988-03-12\",\"time\":\"07:20\",\"uncertaintyMinutes\":5,\"sex\":\"female\",\"place\":\"杭州\",\"lng\":120.16,\"tz\":\"Asia/Shanghai\",\"timeSource\":\"family\",\"focus\":[\"career\"],\"label\":\"林某\",\"notes\":[\"时柱落在辰时末，±5 分钟内不跨界\"]}",
    "notes": ["出生时间来自母亲回忆，误差按 ±5 分钟处理。", "紫微真太阳时校正未改变时辰，只按一张盘读。"]
  },
  "charts": {
    "bazi": {"pillars": "戊辰 乙卯 丙寅 壬辰", "extra": {"dayun": "丙辰 2021–2030"}},
    "ziwei": {"mingGong": "辛卯", "ju": "木三局"}
  },
  "conclusions": [
    {
      "text": "职业底色偏组织内执行与流程管理，不是纯技术单干型。",
      "evidence": "八字：月令官星得地、印星护身，做功集中在月日两支。",
      "system": "bazi",
      "tag": "推断",
      "verification": "已知事实拟合"
    },
    {
      "text": "工作性质偏组织内流程与资源协调，不是自由职业形态。",
      "evidence": "紫微：官禄宫紫微天相、三方会禄；命宫与迁移对照成组织内格局。",
      "system": "ziwei",
      "tag": "推断",
      "verification": "已知事实拟合"
    },
    {
      "text": "2026 年秋有岗位职责扩张或换岗的迹象。",
      "evidence": "紫微：流年官禄宫见化禄，官禄三方会吉，2026 流年引动官禄。",
      "system": "ziwei",
      "tag": "推断",
      "verification": "前瞻检验",
      "window": "2026-08..2026-10"
    },
    {
      "text": "管理幅度真正扩大更可能在 2027 年春夏。",
      "evidence": "八字：大运与流年叠加，官星应期落在卯、辰月。",
      "system": "bazi",
      "tag": "存疑",
      "verification": "未验证",
      "window": "2027 春"
    }
  ],
  "cross": {
    "plan": "有生辰与时辰、问事业：八字定层级与应期，紫微看宫位细节，两门都能独立覆盖 2026–2027 窗口，故并用；六爻无卦、吠陀未跑。",
    "agree": [
      {"statement": "职业底色偏组织内执行与流程管理。", "systems": ["bazi", "ziwei"], "strength": "strong"},
      {"statement": "2026 秋到 2027 春是职责扩张窗口。", "systems": ["bazi", "ziwei"], "strength": "medium"}
    ],
    "conflicts": [
      {
        "topic": "管理幅度扩大的时点",
        "readings": [
          {"system": "bazi", "text": "2027 年春卯、辰月应期更实。"},
          {"system": "ziwei", "text": "流年官禄化禄落在 2026 年内，扩张更早。"}
        ],
        "condition": "2027-02..2027-04 是否出现团队或人头调整；若 2026 年内已换岗带人，则紫微读法更贴。"
      }
    ],
    "gaps": [
      {"missing": "2026 年秋是否已实际换岗或带人", "why": "能区分两门对管理幅度时点的分歧"}
    ]
  },
  "timing": [
    {"window": "2026-08..2026-10", "event": "岗位职责扩张或换岗，需能指出具体变化", "status": "partial"},
    {"window": "2027-02..2027-04", "event": "管理岗位或团队调整落地", "status": "pending"}
  ],
  "readings": [
    {"file": "readings/2026-07-28-bazi.md", "at": "2026-07-28T21:30:00+08:00", "sessionId": "session-demo-0001"},
    {"file": "readings/2026-07-28-ziwei.md", "at": "2026-07-28T21:45:00+08:00", "sessionId": "session-demo-0001"}
  ],
  "verificationLog": [
    {"at": "2026-11-16T10:20:00+08:00", "item": "2026 秋岗位职责扩张或换岗", "result": "partial", "note": "部门内职责扩大、未换岗；按落档时写定的可观察结果算部分应验。"}
  ],
  "createdAt": "2026-07-28T21:30:00+08:00",
  "updatedAt": "2026-11-16T10:20:00+08:00"
}
```

### 5.3 单门 case.json（省略 `cross`）

```json
{
  "version": 1,
  "id": "2026-11-20-zhou-liuyao-timing",
  "title": "周某 · 六爻 · 应期",
  "subject": {
    "label": "周某",
    "sex": "unknown",
    "birth": {
      "calendar": "gregorian",
      "leapMonth": false,
      "date": "2026-11-20",
      "time": "21:10",
      "place": "上海",
      "lng": 121.47,
      "tz": "Asia/Shanghai"
    }
  },
  "systems": ["liuyao"],
  "focus": ["timing"],
  "params": {
    "card": "{\"system\":\"liuyao\",\"question\":\"下月面试能否通过\",\"castTime\":\"2026-11-20 21:10\",\"castMethod\":\"铜钱\",\"lines\":[7,8,9,7,8,6],\"label\":\"周某\",\"focus\":[\"timing\"]}",
    "notes": ["birth 记的是起卦时刻，不是命主出生；六爻不批本命。"]
  },
  "charts": {
    "liuyao": {"benHexagram": "火风鼎", "bianHexagram": "雷风恒"}
  },
  "conclusions": [
    {
      "text": "面试结果偏成，但决定权在对方流程，窗口在 12 月上旬。",
      "evidence": "用神得月建生扶、动爻化进，世应相生。",
      "system": "liuyao",
      "tag": "中",
      "verification": "未验证",
      "window": "2026-12-01..2026-12-15"
    }
  ],
  "timing": [
    {"window": "2026-12-01..2026-12-15", "event": "收到面试结果通知（过或不过都算应期）", "status": "pending"}
  ],
  "readings": [
    {"file": "readings/2026-11-20-liuyao.md", "at": "2026-11-20T21:10:00+08:00", "sessionId": "session-demo-0002"}
  ],
  "verificationLog": [],
  "createdAt": "2026-11-20T21:10:00+08:00",
  "updatedAt": "2026-11-20T21:10:00+08:00"
}
```

## 六、校验规则

写入后必须逐条过；任何一条不过就先修再交付。

**必过（可脚本化）**

1. 每个 JSON 文件 `JSON.parse` 成功；文件 UTF-8 无 BOM；无注释、尾逗号。
2. 必填字段齐全、类型正确（字符串/数字/布尔/数组/对象），数字字段不是字符串。
3. 枚举精确匹配：只接受第三、四节列出的值；大小写、连字符、下划线都算错（`blind_checked`、`Blind-Checked` 均无效）。
4. 时间格式：`createdAt`/`updatedAt`/`readings[].at`/`verificationLog[].at` 匹配 `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?[+-]\d{2}:\d{2}$`；`nextCheck`、`birth.date` 匹配 `^\d{4}-\d{2}-\d{2}$`；`birth.time` 匹配 `^\d{2}:\d{2}$`。
5. `id` 匹配第四节正则，且等于目录名；`index.cases[].id` 唯一。
6. `systems` 非空且只含四门；`charts` 的键 ⊆ `systems`；`conclusions[].system` ∈ `systems`。
7. `timing[].status`、`verificationLog[].result`、`status`、`verification`、`confidence` 全部在枚举内。
8. `updatedAt` ≥ `createdAt`；`verificationLog[].at` > 对应 `readings[].at`。
9. `readings[].file` 以 `readings/` 开头、文件真实存在；`chart/` 产物不写进 JSON。
10. index 与 case 互证：同一 `id` 的 `title`/`systems`/`focus`/`createdAt` 相同，`updatedAt` 相同；每个 case 目录在 index 中恰好一行；没有指向不存在目录的行。
11. `status=verified` ⇒ `verification` ∈ {`blind-checked`,`forward-checked`}；`status=read` ⇒ `readings` 非空。
12. `summary` ≤80 字且非空；`title` 非空；`conclusions` 每条 `evidence` 非空。
13. `cross` 只出现在 `systems` ≥2 门的 case；单门 case 出现 `cross`（含空对象）判错，多门 case 缺 `cross` 判错。
14. `cross.plan` 非空；`cross` 里所有 `system`（`agree[].systems`、`conflicts[].readings[].system`）⊆ `systems`；`agree[].systems` ≥2 项。
15. `agree[].strength` ∈ {`strong`,`medium`}；`conflicts[].readings` ≥2 项、每项 `text` 非空；`conflicts[].topic`、`conflicts[].condition` 非空。
16. `cross.gaps` ≤3，每项 `missing`、`why` 非空；`agree`/`conflicts`/`gaps` 没有内容时省略键，不写 `[]`、`null` 或占位字符串。
17. `systems` 等于实际跑过的门：多门 case 每门至少一条 `conclusions` 或在 `params.notes` 说明该门为什么没出结论；不可用/没跑的门不得出现在 `systems`、`charts`、`cross`。
18. 多门 case 的 index `summary` 与 `cross` 一致：有 `agree` 写共同结论，有未决 `conflict` 写分歧主题，不写成单门结论。

**人工判定（不能脚本化，写在交付说明里）**

- `verification` 档是否真达到：看落档时间是否早于结果告知（`readings[].at` 与 `verificationLog[].at` 的先后只是下限，还要确认推导时没看过答案）。
- `event` 是否事前写死、可观察；`window` 是否事后被放宽。
- `summary` 是否真是一句话结论，不是把判词堆在一起。
- `confidence` 是否按标签综合，而非拍脑袋。
- `cross.plan` 是否真解释了「为什么不需要其他门」，而非套话；`agree` 是否真是两门独立依据，而不是同一门的两条线索；`condition` 是否可观察或可问，不是「看以后」；`gaps` 是否值得问、是否超过 3 条。

**常见错误对照**

| 错写 | 正确 |
|---|---|
| `next_check` / `nextCheckAt` | `nextCheck` |
| `created_at` / `createdAt` 无时区 `2026-11-16 10:00` | `createdAt`：`2026-11-16T10:00:00+08:00` |
| `verification: "blind_checked"` | `"blind-checked"` |
| `verificationLog[].result: "pending"` | `pending` 只能出现在 `timing[].status` |
| `systems: ["八字"]` | `["bazi"]` |
| `timeSource: "family-memory"` | `family`（起课台五值之一） |
| `focus: ["升职"]` | 7 个 id 之一或空数组 |
| `charts` 里放了整段报告文本 | 只放关键值，正文写进 `readings/` |
| 把 `verification`/`status` 写进 case.json | 只写进 index 行 |
| 用 `null` 代替省略 | 可选字段没有就整个省略键 |
| `cross.agree[].strength: "high"` / `"low"` | 只用 `strong` / `medium` |
| `agree[].systems: ["bazi"]` | 共同支持至少 2 门，单门写进 `conclusions` 即可 |
| 把「一门支持、一门未覆盖」写进 `conflicts` | 记单门支持或省略；未覆盖不是反对 |
| `conflicts[].condition: "看后续发展"` | 写可观察预测或可问的事实 |
| 单门 case 也写 `cross` | `cross` 只在 `systems` ≥2 时出现 |
| 多门 case 省略 `cross` | 多门必须写 `cross` |
| `cross` 里出现 `systems` 没跑的门 | 只写实际跑过的门 |
| 多门 case 的 `summary` 写成单门结论 | 概括交叉结论：共同支持或未决分歧 |
