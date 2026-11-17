> 本文件是 `vedic` skill 的 **prashna** 模块。文中相对路径（resources/、scripts/、tests/）以本模块目录 `prashna/` 为根；跨模块引用写作 `<模块>/...` 或「<模块> 模块」，指本 skill 下的同名目录，调用方式见根目录 SKILL.md。

# 吠陀卜卦（Prashna）：一事一问的提问盘

## 执行主线

1. **先记下提问时刻**。用户直接发问或说“现在”，这条消息一到就取时刻，精确到秒，写下来；之后读资源、澄清、算盘都不再另取。有时间工具就用时间工具；没有就在终端取 UTC（`date -u +"%Y-%m-%d %H:%M:%S"`）再换成提问地时区。用户给了明确时刻（“昨晚 21:40 想到这件事”）就用它。
2. **门控与输入**（Phase 0）：一个具体问题，加提问地点。必须问的集中问一次；已经给过的直接复用。
3. **完整读六个默认资源**（见“读什么”）。
4. **起盘**（Phase 1）：`scripts/build_prashna_data.py`，用 calculator 计算环境的解释器（`calculator/scripts/check_env.py` 报告的那个 `python`；需要 Python 3.9 及以上）。
5. **拆题、写取象单**（Phase 2）：`prashna_plan.json`。
6. **一条命令跑三层**（Phase 3–5）：`python scripts/run_prashna.py --dir <当前 prashna_* 目录>`，依次出判定（成事账、内部档）、时间副层、Tajika 过程层。
7. **写判读单**（Phase 6）：完整版写文件，聊天里给简版（`resources/judgment-writing.md` §7.1）。
8. **追问沿用原盘**（Phase 7），不换时间挑答案。

## 定位

用一个具体问题产生时的时间和地点建立独立提问盘，回答这一件事。不看本命盘，不需要出生信息。

**技法定死，一卦只用这一套**，不临场换法，也不因为结果不合意换一种口径重判：

| 层 | 回答什么 | 依据 | 权限 |
|---|---|---|---|
| 标准层 | 事情成不成（行动型另答“某人会不会动”） | *Shatpanchasika*（Ayer 译注）为主文本，经 KN Rao／Bharatiya Vidya Bhavan 实践兼容性筛选，有条件收入同一系的 *Prasna Marga*；规则逐条有出处（`resources/standard-layer.md`） | 唯一定倾向的一层：脚本计成事账，定内部三档（偏成／持平／偏不成） |
| 时间副层 | 大致什么时候 | *Prasna Marga* XIV.81–85、*Shatpanchasika* V.5（`resources/timing-layer.md`） | 只在偏成、持平时给；不改档 |
| Tajika 过程层 | 问者与所问之事现在在靠近、已接上，还是走远；有没有传递、援助、阻断 | *Tajika Nilakanthi* 十六 Yoga（`resources/tajika-layer.md`） | 随判定一起跑；不进成事账、不改档、不当作第二套方法的确认（仍是研究验证版） |

不要把标准层写成“KN Rao 自创的完整 Prashna 体系”，也不把他的本命 Jaimini、Dasha、分盘或 SAV 工具迁入提问盘。本模块没有 KP（1–249 数字起盘、sub-lord）、Kerala 问卜征兆、数字起卦；用户要这些时如实说明未收入。

**分工**：模型取象，脚本计数。模型拆题、抓关键词、定事项宫与行动者，写成取象单；判定脚本按古法规则计成事账、能力否决、行动链与限定语，定出内部档；模型照着判定结果和盘面写判读单，讲事情怎么走。规则必须有本土典籍出处；拆题是主流程，古法给出处，不单独否决；数法、问法分流、输出形态属执行口径，在资源文件里明写。

本模块移植自上游 `CNWU16/vedic-astro-skills` 的 `vedic-prashna`（规则账本、判定脚本与出处核证都是上游的工作），改到本 skill 的目录、计算引擎与协议；与上游的差异记在根目录 `CHANGELOG.md` 的 5.3 一节。

---

## 与本 skill 其他部分的关系

提问盘是独立的一类产物，根 SKILL.md 的例外表有登记。下面这些共用协议在本模块**不适用**，不要套：

| 共用协议 | 本模块的做法 |
|---|---|
| `shared/data_contract.md`：`chart_data.json`、`structured_data.md`、chart_id | 不读不写。产物只在 `prashna_<yyyymmdd_HHMMSS>_<label>/`；溯源写在 `structured_prashna.md` 元信息“计算溯源”一行与 `prashna_meta.json` |
| `calculator/scripts/check_chart.py`、`shared/scripts/check_freshness.py`、分析记录 | 不跑。提问盘没有“过期”：同一问题沿用第一次清晰提问的盘（`resources/qa_rules.md` §1） |
| `shared/permissions.md`、验前事、`user_context.md` | 不读不写 `user_context.md`；不做验前事；不读本命产物。本命交叉当前失败关闭（`resources/cross-natal-policy.md`） |
| `shared/time_window.md`、`shared/divisional.md` | 不用 Dasha、行运、完整分盘。时间只来自时间副层 |
| 时间精度 | 时间地点由提问人负责：按所给的起盘，不因精度追问用户，也不在判读里谈输入精度（`resources/judgment-rubric.md` §13） |

适用的只有 `shared/grounding_basic.md`（§2–§4、§6，用在判读单的“现在能做什么”；不另写行动卡）和根 SKILL.md 的交互约定。

用户已有本命工作目录时，`prashna_*` 目录可以放在它下面，两边互不读取。

---

## 读什么

每次执行按顺序完整读取：

1. `resources/question-decomposition.md`：拆题、三型、子问题出口、转宫、抓关键词、取象单格式、澄清与门控；
2. `resources/house-meanings.md`：宫义、星义、星座性质、行动者与关键词库、按问题读、连接口径、限定语检验；
3. `resources/matter-rules.md`：事项登记（事项宫与本事古法）、查表题、不判；
4. `resources/judgment-rubric.md`：判定脚本怎么定档，怎样读判定结果；
5. `resources/judgment-writing.md`：判读单怎么写；
6. `resources/moon-policy.md`：Moon 的使用边界。

按情况再读：写“两边现在在靠近还是走远”一节前读 `resources/tajika-layer.md`；时间副层运行时读 `resources/timing-layer.md`；只给城市名、需要查经纬度或时区时读 `resources/locations.md`；追问读 `resources/qa_rules.md`；问出处、维护规则时读 `resources/standard-layer.md`；用户要结合本命时读 `resources/cross-natal-policy.md`。

---

## 隔离硬约束

1. 只读调用共享 `calculator/scripts/engine.py`；不向共享 engine 增加 Prashna、Tajika 或 Void 字段。（5.3 给 engine 加的 `second`／`fold` 是通用的计算瞬间参数，整分调用结果逐字节不变。）
2. 默认输出必须由 `scripts/format_prashna_standard.py` 生成；禁止调用共享本命 `formatter.py` 后再删段。
3. 不修改 core、love、career、soul、timing、synastry、rectifier、reader 等其他模块。
4. 产物只写入 `prashna_<yyyymmdd_HHMMSS>_<label>/`（同名目录已有盘时 builder 另开 `_2`、`_3`……，不覆盖旧盘；后续产物写进 builder 实际打印的那个目录）：`structured_prashna.md`、`prashna_meta.json`、`prashna_plan.json`、`prashna_verdict.json`、`prashna_verdict.md`、`prashna_judgment_<label>.md`；时间副层只增加 `timing_overlay.md`；过程层只增加 `tajika_overlay.md`。
5. 不读取或写入 `user_context.md`。
6. Tajika 计算只存在本模块；标准 builder 与判定脚本不导入它，也不接受 optional flag。时间副层由独立 `scripts/build_timing_overlay.py` 生成：标准 builder 不导入它，它也不导入 Tajika。`scripts/run_prashna.py` 只起子进程调度，不导入任何一层。
7. 不读取其他 `prashna_*` 目录；追问只沿用当前盘。

---

## 标准层禁入项

不得消费或输出：

- Chara Karaka、DK、UL、AL；
- SAV／BAV、Shadbala、Bhava Bala；
- 完整 D9、D10、D4、D5 等本命分盘；
- engine 的 functional P1 身份、natal yoga prescan（宫表的吉凶标签是 `P-I.3` 注的 Ayer 功能吉凶，从被占据／照射的星座起算，不是 P1）；
- 120 年 Vimshottari、Chara Dasha；
- transit、Sade Sati、double transit；
- Tajika orb／applying／separating（只在过程层）；
- KP cusp／sub-lord。

本命专用的尊贵度结算不进提问盘：落陷解除（Neecha Bhanga 档位）、落陷 Vargottama 三分类、Pushkara 补丁。提问盘的落陷、逆行只按能力层的折损与救应读（`M-XIV.39–40` Raman 注，`resources/judgment-rubric.md` §5），根本三角归本座。

只允许 rising Navamsa（星座与序号）、Lagna 所在 drekkana、Lagna 六分盘座主表三项有限数据，因为 `P-I.4`（注：Lagna、Hora、Drekkana、Navamsa、Dwadasamsa、Trimsamsa 六分盘）、`P-I.7`、`P-VI.1~2`、`P-VI.4`、`P-VII.13` 明确使用它们；禁止由此展开完整 D2、D3、D9、D12、D30 解读。

---

## Phase 0：输入与门控

| 输入 | 规则 |
|---|---|
| 具体问题 | 一个可观察结果，或一个描述对象（相处、局面）；一句多问先拆、先选一个（`resources/question-decomposition.md` 第 8 节） |
| 提问时刻 | 按“执行主线”第 1 步：取这条消息到达的时刻（提问地时区，保留秒），不在处理数分钟后另取整分钟。用户给了显式时刻就用它 |
| 提问地点 | 提问人此刻所在的城市或经纬度；必须能确定 IANA 时区。只给城市名时查 `resources/locations.md`；地点未知时问一次（有定位工具时可以取近似城市，向用户确认一句再用），不用机器时区代替 |

门控：模糊、假设、已发生、A／B 二选一按 `resources/question-decomposition.md` 第 8 节澄清；不判与操控、打听类按 `resources/matter-rules.md` 第 6 节一句话说明并给替代问法；同一问题和现实状态未变化时沿用第一次清晰提问盘（`resources/qa_rules.md` §1），不使用 24 小时、3 个月阈值；出现自伤或极端语句时先回应安全，不起盘。

用户问的其实是长期人生趋势、性格、某一年运势时，不是卜卦的题：按根 SKILL.md 路由到本命模块。

进入下一阶段条件：问题可拆出一个可观察结果或描述对象，时间地点完整。

---

## Phase 1：起盘

```bash
python scripts/build_prashna_data.py \
  --datetime "<YYYY-MM-DD HH:MM[:SS[.ffffff]][+HH:MM]|now>" \
  --lat <lat> --lon <lon> --tz "<IANA>" \
  --question "<single observable question>" \
  --label "<kebab-case>" --out-parent "<工作目录>"
```

`--datetime` 写第 1 步记下的时刻（提问地的钟表时间）；`now` 只在这条命令就是收到问题后的第一个动作时才用。产物：`structured_prashna.md`（白名单事实）与 `prashna_meta.json`（时刻、地点、十二宫宫主，后续脚本照抄）。计算环境没装时先按 `calculator/MODULE.md` 的环境检查处理。

Lagna 落在某条分盘分界前后一两秒钟以内时，“Lagna 六分盘座主”表会隐藏并写明哪一层不一致；这时 `P-I.4` 不读 varga 一项，照表里的说明处理，不手推补造。

进入下一阶段条件：产物存在，默认白名单无越权字段。

---

## Phase 2：拆题与取象

按 `resources/question-decomposition.md`：

1. 拆出行动者、动作、对象、结果、限定语；判型（事件型、行动型、描述型），定每个子问题的出口；
2. 别人的动作以那个人的宫为命宫转宫（对方主动＝本盘 9 宫，不是本盘 3 宫）；
3. 逐句抓关键词，查 `resources/house-meanings.md` 关键词库，记下宫与星、相合还是相反、出处；
4. “事情成不成”查 `resources/matter-rules.md` 登记表取 `matter`；表外取 `通用`，按宫义选事项宫并写明出处；描述型取 `描述`（只出事实、不定档）；查表题跳到 Phase 6 按 `resources/matter-rules.md` 第 5 节输出；
5. 定时间范围 `time_scope`（在看盘结果之前，`resources/question-decomposition.md` 第 5 节）；写取象单 `prashna_plan.json` 到当前 `prashna_*` 目录。

进入下一阶段条件：取象单每个关键词有出处，每个子问题有唯一出口。

---

## Phase 3–5：判定、时间副层、过程层

```bash
python scripts/run_prashna.py --dir "<当前 prashna_* 目录>"
```

它读 `prashna_meta.json` 与取象单，依次以子进程运行三个脚本，打印每一层跑没跑、为什么：

| 层 | 脚本 | 产物 | 何时不运行 |
|---|---|---|---|
| 判定 | `judge_prashna_standard.py` | `prashna_verdict.json`／`.md` | — |
| 时间副层 | `build_timing_overlay.py` | `timing_overlay.md` | 偏不成（含能力不足）；持平·盘面未给方向；必要条件不成立；描述型；路上顺不顺 |
| Tajika 过程层 | `build_tajika_overlay.py` | `tajika_overlay.md` | 描述型；问者星与事项星是同一颗（不拿别的星顶替） |

改了取象单重跑时，这一次不再适用的 `timing_overlay.md`／`tajika_overlay.md` 会改名为 `*.superseded.md`，判读单不引用它们。需要单独重跑某一层时，各脚本的参数见 `resources/timing-layer.md` §5、`resources/tajika-layer.md`“计算契约”，时刻照抄 `prashna_meta.json` 的 `instant`。

**读判定**：`prashna_verdict.md` 给成事账（每条规则、方向、计分、合计）、内部档与强度、能力层、限定语、行动链、输入提示。判读按它写，**不手算、不改档**。描述型只有事实表，没有档。写的时候发现取象错了（关键词、事项宫、行动者），改取象单重跑；发现规则本身读错，按 `resources/qa_rules.md` §4 纠错。

**读时间副层**：偏成写“约……”，持平写成条件式（“如果推进顺利，大约……”）；偏不成不给时间，判读单写明不给时间、什么变化之后可以再问。几个候选并列，不平均、不折中；婚恋题另看 `M-XVII.31` 偏早提示；问题自带日期时只说盘面节奏与最近触发日，判断不了是否恰好落在那天。正文只写取象单 `time_scope` 范围内的时间，范围外的留核对区（`resources/timing-layer.md` §3 第 7 条）。

**读过程层**：先读 `tajika_overlay.md` 的“先说人话”，再看主星对与检出的 Yoga。它答的是“两边在靠近还是走远”，和“成不成”是两个子问题：方向不同不算冲突，按 `resources/judgment-writing.md` §3 第 10 条分开讲；不写“两套方法都确认”，不因它提高或降低把握。过程层的“度差 × 12 日”只列核对区，主时间以时间副层为准。

进入下一阶段条件：`prashna_verdict.md` 存在，与取象单一致。

---

## Phase 6：判读单

写入 `prashna_judgment_<label>.md`，按 `resources/judgment-writing.md`（先答后证、内容契约、过程一节、安抚、高频题型要点）。标题一句话直接回答所问，倾向用白话直说；每个小节第一句是这一节的结论；每个卡点带对应的做法。给用户看的部分不出现 `rule_id`、英文状态码、照搬的强度标签和输入精度；行动型问题标题与简述各用一句分别答“会不会动”和“事情成不成”。

聊天里给简版（约 500–900 字），完整判读单与核对区在文件里；用户要详细版或要看依据时给全文（`resources/judgment-writing.md` §7.1）。

查表题的判读单：标题、简述、正文用白话写查表结果，两说都写；核对区只留“这张盘的范围”和一张查表；不写三档、过程和时间。
描述型的判读单：讲局面与相处的样子，约 1,000–1,500 字，不写成败、过程与时间；核对区引用事实表（`resources/judgment-writing.md` 第 7 节）。

---

## Phase 7：追问

已有盘追问不重起，读取 `resources/qa_rules.md`，只访问当前 `prashna_*` 目录。追问不改档；补限定语、换问法按 `resources/qa_rules.md` §1、§4（改取象单后重跑 `run_prashna.py`）；标准层与过程层的对照只并列、不拼票。

---

## 本命交叉

默认关闭。用户明确要求时读取 `resources/cross-natal-policy.md`；当前因裁决规则未完成来源重审而失败关闭：不能调用不存在的参数，也不能用 SAV、本命 Dasha 或分盘升降提问盘的结论。用户想看本命趋势时另走本命模块，结果不回写提问盘。

---

## 最终自检

- [ ] 提问时刻是消息到达时记下的，保留到秒，没有用处理时刻替代？
- [ ] 已完整读取六个默认资源？
- [ ] 取象单的关键词都有出处，每个子问题只有一个出口，别人的动作从那个人的宫起算？
- [ ] 判定由脚本生成，判读的倾向与内部档一致，没有手算或改档？
- [ ] 默认产物由专用 formatter 生成，未使用 Chara Karaka、SAV、完整分盘、本命 Dasha 或过运？没有读 `user_context.md` 和本命产物？
- [ ] 标题一句话答了所问，倾向用白话直说；只读每节第一句能拿到完整答案？
- [ ] 给用户看的部分没有 `rule_id`、状态码、绝对断语和输入精度，行动型问题两问分答？
- [ ] “两边现在在靠近还是走远”与“成不成”分开讲，没有写成两套方法互相确认，没有因它改口？
- [ ] 偏成／持平才给时间，偏不成与盘面未给方向没给？过程层的时间候选只在核对区？
- [ ] 查表题只给查表结果、两说并列，没有出三档、过程和时间？
- [ ] 每个卡点都有对应的做法；情感类安抚只出现一次、有盘面依据、没有改结论？
- [ ] 产物只写入当前 `prashna_*`；追问沿用当前盘，没有换时间重起？
