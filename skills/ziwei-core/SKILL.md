---
name: ziwei-core
description: 紫微斗数解读引擎：用户给生辰，要排紫微盘、看命宫十二宫主星四化、批事业财运感情婚姻六亲健康、看大限流年流月流日和小限、问某年某月某日某事或挑日子、两人合盘，或问倪海厦《天纪》怎么说时使用。排盘交给脚本（开源 ziwei-doushu 引擎：iztro 加斗数全书口径修正，已用独立安星规则核过 3000 盘），三合派与四化派分开推、各自挂依据，结论带置信标签和验证状态，每条斗数说法标明是倪师原话还是通行教法。不处理八字、六爻、梅花、吠陀。
compatibility: Windows 本机已配置 Node.js 排盘环境；运行不依赖 oo CLI。
metadata:
  icon: ':lucide:wrench:'
  title: Ziwei Core
---

# ziwei-core —— 紫微斗数解读引擎

## 运行环境

排盘是一个独立的 node 运行时目录（ziwei-doushu：iztro + 斗数全书口径修正），不在插件包里。解析顺序：`$env:XUANXUE_ZIWEI_PAN` → 玄学运行时 `%USERPROFILE%\.dsh\xuanxue\ziwei` → 本机已有 `%USERPROFILE%\.cache\ziwei-core`；体检写出的 `xuanxue-skills/health.json` 会给最终路径。官方入口是 `node node_modules\tsx\dist\cli.mjs run\pan.ts <参数>`；沙箱里 tsx 起 esbuild 会 spawn EPERM，这时改跑预编译入口 `node prebuilt\run\pan.cjs <参数>`，参数完全一致（含 `--selftest`、`--ni`、`--json`）。真要用 tsx，注意 PowerShell 用 `$env:USERPROFILE` 而不是 `$env:HOME`。缺运行时按 `xuanxue-orchestra/scripts/setup-runtime.ps1` 与插件 `docs/SETUP.zh.md` 第 3 节准备。


本版 2026-11-13（第五版：加「时间层级」一节，脚本能排流月、流日；第四版加了财富专题）。引擎固定在 Renhuai123/ziwei-doushu 提交 `495b79e`（2026-10-31）。

**定位**：排盘全部交给脚本，模型只读盘。默认口径与主流排盘软件一致（亮度依《斗数全书》、闰月月中分界、晚子时换次日），倪师口径可以一键切换。读盘分两套视角：三合派（看星曜组合、三方四正、格局，生年四化固定不动，大限只看宫位移动）和四化派（宫干四化、自化、化忌冲、大限与流年四化叠盘、来因宫）。通常把倪海厦《天纪》归入三合派【通】；倪师自己没用这个名称，他明确反对的是四化飞来飞去【倪】（`--ni 飞来飞去`）。两派都不自动胜出：同向就加强，相反就两读并带，并说明各自在什么条件下成立。

---

## 来源标注

协议里每条斗数说法都标了来源，解读时照此引用：

- **【倪】** 倪海厦《天纪》有原话可查，括号里给 `--ni` 检索词。引用时用检索出的原话和时间码，不凭协议里的转述引用。
- **【通】** 通行教法，没有逐条对过文献。可以作为默认做法，写进解读时不说成倪师的观点，也不说成古籍原文。
- **【赵】** 赵财猫（公众号「赵财猫说紫微」）两篇付费长文里的看法（一篇讲财富层次，一篇讲大限、流年、流月、流日），四化派口径，用户指定为高权重信源。只用在「财富专题」和「时间层级」两节；写进解读时说成赵财猫的看法，不说成倪师或古籍的话。标【赵·案例】的是从文中三张案例盘的点评里读出来的用法，作者没有明文写成规则。
- 没有标签的是本 skill 自己的操作规则（怎么排、怎么标、怎么写），不是斗数说法。

---

## 入口

| 入口 | 什么时候 | 做什么 |
|---|---|---|
| 全盘 | 给了生辰，要完整看，或没说看哪方面 | Z0–Z9 全跑，标准档 |
| 专题 | 带具体问题来（事业、感情、财、健康、某个决定） | 内部做完 Z0–Z5，再做对应宫位专题、当前大限（Z7）和 Z9；问到具体年份才跑 Z8；先答所问。问财运、赚钱、存钱、财富层次、家里或配偶的财，按「财富专题」一节做 |
| 流年、流月、流日 | 问某一年、某个月、某一天，或要挑日子 | Z0–Z2 加 Z7–Z8，按「时间层级」一节读；`--year` 给目标年，`--months` 列一年十二个月，`--day` 给公历日期 |
| 合盘 | 两人关系 | 两盘各自做 Z0–Z4，再按「合盘」一节对照 |
| 同盘追问 | 本会话已排过同一盘 | 复用参数卡和已有判断，只补受影响的部分；口径或时辰变了就重排 |
| 查原话 | 问倪师怎么说、要出处 | 只跑 `--ni`，不做人生分析 |

---

## 安装（每个环境第一次用时做一次）

需要能访问 GitHub 和 npm。装不上就如实告诉用户，**不要手排或心算安星**。已装过本版（`cat "$ZW/.ok"` 输出 `2026-11-13-v5`）就跳过；`.ok` 不存在或日期不同，三步都重做。

第一步，取引擎、装依赖：

```bash
ZW="${ZIWEI_HOME:-$HOME/.cache/ziwei-core}"
mkdir -p "$ZW/run" && cd "$ZW"
[ -f src/lib/ziwei/algorithm.ts ] || { git init -q src && git -C src fetch -q --depth 1 https://github.com/Renhuai123/ziwei-doushu 495b79ecb3524b20b2edc026067d7d0b0f407319 && git -C src checkout -q FETCH_HEAD; }
printf '{"name":"ziwei-runtime","private":true}\n' > package.json
npm i --silent --no-audit --no-fund iztro@2.6.1 lunar-javascript@1.7.7 tsx@4.23.15
mkdir -p node_modules/server-only && printf '{"name":"server-only","main":"index.js"}\n' > node_modules/server-only/package.json && : > node_modules/server-only/index.js
```

第二步，把文末「附录」那一整段命令原样执行一次，写出 `run/pan.ts`。已经装过旧版的环境也要重新执行这一步，再做第三步。

第三步，自检，通过才算装好：

```bash
cd "${ZIWEI_HOME:-$HOME/.cache/ziwei-core}" && npx tsx run/pan.ts --selftest && echo 2026-11-13-v5 > .ok
```

`src/` 是上游仓库原样代码，只通过 `run/pan.ts` 调用，不在 `src/` 里面装依赖或运行别的脚本。`server-only` 用空包代替，因为引擎原本跑在 Next.js 服务端，这个包在普通 Node 里会直接报错。

---

## 脚本速查

```bash
cd "${ZIWEI_HOME:-$HOME/.cache/ziwei-core}"
npx tsx run/pan.ts --date 1990-01-01 --time 12:00 --city 上海 --gender male --year 2026,2027
#  出生地：--city 城市名（国内地级市与部分区县）或 --lng 经度；海外出生必须 --lng 和 --tz 一起给（--tz 是出生地标准时区，如纽约 -5）
#  --lunar 1995-08-25 [--leap yes]  农历输入
#  --shichen 午  直接给时辰（不做任何校正）；23 点后出生写 --shichen 晚子，换不换日跟 --zi 口径走
#  --dst yes|no  所报是夏令时钟表时间就 yes（减 60 分钟）：大陆只有 1986–1991，台湾、港澳、海外按当地实情；--uncertainty 15  时辰边界容差，分钟；--solar no  不做真太阳时校正
#  口径：--leapmode split|next-month|prev-month   --zi next-day|current-day
#        --bright QS|XD1|XD2|ZZ   --kuiyue rhyme|engine
#  倪师口径：--leapmode next-month --zi current-day
#  --months 2027  列农历 2027 年十二个月：月干支、流月命宫、月干四化、流年四化和生年禄忌落在流月的哪一宫
#  --day 2026-11-13,2026-11-20  给公历日期：流年、流月、流日的命宫和三层四化，流月与流日十二宫对照
#  --json  整盘结构化数据
npx tsx run/pan.ts --ni 化忌,夫妻 --limit 20   # 检索倪师《天纪》原话；逗号分隔表示同时命中
npx tsx run/pan.ts --selftest                  # 依赖或环境变了就跑
```

输出依次是：参数卡；十二宫（主星亮度、生年四化、六吉六煞禄马、杂曜、空宫借星）；命宫三方四正；生年四化；宫干四化（◎ 为离心自化，⇄ 为化入对宫）与来因宫；财富专题数据（生年禄、禄存所在宫和兄弟、田宅、父母、命、福德各宫的生年四化、离心与向心自化、空劫煞星，生年忌在六内还是六外，全盘自化统计）；格局检测（成格、加分、破格）；大限（每个大限的三方四正、大限宫干四化、生年禄与禄存和生年忌落在大限的哪一宫、大限命宫与大限福德宫的主星）；流年（流年命宫即太岁宫及其三方四正、小限及对宫、流年干四化和它落在流年的哪一宫、流年斗君）。给了 `--months` 另出流月一览；给了 `--day` 另出流月流日（三层的命宫，三层天干四化各落在本命和各层的哪一宫，流月与流日十二宫对照）。宫位关系都由脚本列出，不要自己数宫。脚本只出计算结果，不做解读。脚本报错或自检失败就停下，不拿不完整的盘去解读。参数名写错、日期不存在、时间格式不对，脚本都会直接报错，不会按默认值出盘。

---

## 八条铁律

1. **盘以脚本为准，参数可见。** 参数卡原样给用户看。不默认性别，不默认时辰；只知道大概时段，就把候选时辰分别排盘。参数卡里的 ⚠ 都要处理：时辰跨界列候选盘；真太阳时校正改变了时辰时，两盘都要交代，并说明按哪张读；夏令时照提示先分清出生地，再问报的是不是当年钟表时间（大陆只在 1986–1991 实行过）；闰月说明用了哪种口径；落在历表争议区间先问家里过的农历生日；闰月三十日提示紫微存疑的，排对照盘。
2. **口径先说清。** 默认主流口径。用户要按倪师、或问题本身在倪师体系里，就用倪师口径重排。两种口径排出的盘不同、且影响到结论时，两盘并列，只在受影响的判断上分叉。
3. **两派分开推，各自挂依据。** 每条判断标明出自【三合派】【四化派】【两派同向】或【两派相反】；两派相反时两读并列，各写成立条件，标签最高【存疑】。倪师立场是四化排定后固定不动，流年动、星不动【倪】（`--ni 四化是否会动`）：按倪师批时不用宫干四化、自化、大限和流年四化；这些只在四化派视角下用。
4. **每条重要结论挂盘面依据**：哪个宫、哪颗星、亮度、会照或对冲、四化、格局的成格与破格。说不出依据的不写。格局名只是标签，要讲清成格条件、破格项，以及大限有没有走到：命好不如限好【倪】（`--ni 命好不如限好`）。
5. **标签和验证状态分开标**，与 bazi-core 用同一套。【铁断】要同时满足：本宫与三方四正多处同向、两派同向、没有未解决的反证、不依赖未定的口径或候选时辰。【推断】是单线或单派支持。【存疑】是依赖分叉口径、候选时辰，或两派相反。验证状态另列：未验证／已知事实拟合／盲测核验／前瞻检验。
6. **六亲降一档。** 斗数批六亲比较弱【倪】（`--ni 批六亲`）。父母、兄弟、子女的结论最高到【推断】，除非和已知事实对上。
7. **重断设门槛。** 寿夭、重病、离婚、官非、横祸，不凭一颗星或一个化忌下断语。要本命、大限、流年三层同时指向，才写成需要防范的年份；只说防范，不断死期。健康只给留意方向，不当诊断。
8. **只引可核的原文。** 倪师原话只从 `--ni` 检索结果引，带讲次和时间码；原话照录，明显的转写错字在后面用〔〕注正字（如「妙旺〔庙旺〕」），不暗改。【通】条目不说成倪师或古书的话。以下都是二手材料，可以当线索，不当原文引用：`heming-knowledge.ts` 的断语（其中 9 条标为倪师原话的句子，整句在倪师语料里都查不到，有 4 句夹着原话片段，属改写拼接）、`lib/classics/` 的古籍节选、格局检测里的「出处」、引擎代码注释里关于倪师的说法（如把追溯化星来源说成「倪师体系常用」，与倪师不飞星的立场不合）。

---

## 读盘流程 Z0–Z9

| 相位 | 做什么 | 要点 |
|---|---|---|
| Z0 排盘与定盘 | 跑脚本，处理参数卡的 ⚠ | 有已知事实（学业、职业类型、婚否、大的变动年份）先对照；时辰存疑时拿各候选盘分别对事实。倪师另有看发旋定时辰的办法【倪】（`--ni 发旋`），只作参考 |
| Z1 骨架 | 命宫干支、五行局、阴阳顺逆、命主身主、身宫落宫、紫微落宫 | 五行局本身没什么意义，不按局论行业【倪】（`--ni 五行局`）；身宫看后天重心落在哪【通】；《天纪》按紫微落十二宫分章讲盘【倪】（5上–8上，如 `--ni 紫微在午`） |
| Z2 命宫与三方四正 | 命宫主星组合与亮度，对宫迁移，再看财帛、官禄 | 先看对面，再看三方【倪】（`--ni 先看对面`）。空宫借对宫星，力量打折【通】。夹宫：辅弼、昌曲、魁钺为吉夹，羊陀、火铃、空劫为凶夹【通】。吉煞多寡和庙陷一起看【通】 |
| Z3 格局 | 逐个核脚本检测出的格局：成格条件、破格项 | 脚本的格局库只有四十个左右，不全：盘上明显成形却没检出的（如泛水桃花、日月反背），可以自己补认，写出成格条件，标【推断】，倪师讲过的用 `--ni` 查。层次要落到现实定位：结合三方四正的质量和中年大限，说清大致对应的职业层级、财富量级和社会位置，不只给「上格」「中格」 |
| Z4 生年四化 | 禄权科忌各落哪宫、会照哪宫 | 化忌坐本宫和冲对宫不同【倪】（`--ni 化忌在本宫`）。化禄是资源所在，化忌是执着与亏欠所在【通】。科权禄三会，倪师批盘时专门点出【倪】（`--ni 科权禄三会`） |
| Z5 四化派视角 | 宫干四化、离心自化 ◎（本宫宫干化本宫的星）、向心自化（对宫宫干化本宫的星，宫干四化表里对宫那一行带 ⇄）、化忌冲、来因宫【通】 | 只在四化派视角下用，结论标【四化派】。命宫、财帛、官禄、夫妻四宫宫干的化忌飞向最关键【通】。来因宫按四化派通行定义：宫干与生年天干相同的那一宫，壬年寅、子两宫同干取寅，辛年卯、丑两宫同干取卯；脚本就按这个算。另一种用法是追溯某一化从哪宫宫干飞出，看宫干四化表里哪几宫的同一化指向那颗星。两种不要混用，写明用的是哪一种 |
| Z6 专题宫位 | 按问题取宫（下表），每宫都看本宫、对宫、三方四正 | 看任何一宫都要看三方四正和对面【倪】（`--ni 看一个宫`） |
| Z7 大限 | 当前大限和问题涉及的大限：把大限宫当命宫，看脚本列出的它的三方四正 | 十年为主，流年为辅【倪】（`--ni 十年为主`）。三合派只看宫位移动【倪】（`--ni 四化是否会动`）；四化派叠大限宫干四化，看禄入哪宫、忌冲哪宫【通】。好运来得太早用不上，要落在能用的年纪才有用【倪】（`--ni 太早`）；倪师说的「限在中年」是指中年有凶限，不要拿来讲好运。【赵】的大限读法（大限命宫看外在、大限福德看内在，大限四化只代表主观意愿）见「时间层级」一节 |
| Z8 流年 | 三合派：小限只看本宫与对宫【倪】（`--ni 小流年`）。四化派：流年命宫（太岁宫）和流年干四化，叠在大限与本命上【通】 | 倪师讲的「流年」从戌宫起子、男顺女逆（`--ni 男顺女逆`），和通行小限起法一致，脚本按小限算；这个对应是本 skill 的判断。先定大限基调，再看流年。流月、流日按「时间层级」一节读，落宫用 `--months`、`--day` 读脚本，不心算 |
| Z9 核验定稿 | 对照事实，定标签，写建议 | 每提一个问题都配对应的办法：算命是为了事先知道、事先预防【倪】（`--ni 算命的目的`）。oracle-grounding 在场时，现实翻译可交给它，并注明 |

**专题取宫**（除标【倪】的两项，取宫法都属【通】）

| 问题 | 主看 | 兼看 |
|---|---|---|
| 性格、整体 | 命宫、身宫、迁移 | 福德（精神底色） |
| 事业 | 官禄 | 命宫、财帛、迁移；当前大限的官禄 |
| 财 | 按「财富专题」一节：生年禄、禄存、兄弟、田宅、生年忌的内外【赵】 | 三合派对照：财帛（求财模式）、福德（财源与花钱心态）、田宅（财库）、命宫。按倪师口径批时只用这一栏 |
| 感情婚姻 | 夫妻 | 福德（女命福德非常重要【倪】，`--ni 福德,女人`）、官禄（夫妻对宫）、迁移；红鸾天喜 |
| 健康 | 全盘 | 先找全盘杀星、化忌最集中的那一宫，按地支对应脏腑（寅肺 卯大肠 辰胃 巳脾 午心 未小肠 申膀胱 酉肾 戌心包 亥三焦 子胆 丑肝）；疾厄宫只作参考【倪】（`--ni 肺寅`、`--ni 疾厄`） |
| 子女、父母、兄弟 | 对应宫 | 六亲降一档 |
| 置产、家宅 | 田宅 | 子女（田宅对宫）、财帛 |
| 人际、合伙、下属 | 仆役（交友） | 兄弟、命宫 |
| 外出、异地发展 | 迁移 | 命宫、官禄 |

---

## 财富专题

问财运、赚钱能力、存不存得住、财富层次、能不能靠家里或配偶时用。主线是赵财猫的四化派看法【赵】，三合派的财帛宫读法只作对照。盘面事实一律从脚本的【财富专题数据】读，不自己数宫、不心算自化。按倪师口径批盘时不用本节。

**能答到哪一步**【赵】

- 命盘给的是层次，不是数额：财富上限、财富底线、获取财富的吃力程度。不报具体金额；同一张盘放在不同地域和年代，数额差得很远。
- 「求财顺利」的刻度是在本人生活的当地跨过中产门槛：有房有车，日常开销不用算计，收入在当地中上，手里有应对风险的余钱。
- 不铁口断贫富。好盘也有人赚不到，坎坷的盘也有人突破，结论里留出主观能动性的位置。
- 财帛宫不决定有钱没钱，只说明求正财的模式和趋向，如天府在财帛是稳定缓慢的累积而非暴富。

**四项分开看**

| 项 | 看哪里 | 读法 |
|---|---|---|
| 赚：能力与上限 | 生年禄、禄存 | 这两颗是全盘唯二代表赚钱的星，比武曲、太阴等财星有用；生年禄是全盘最大的财源【赵】。看落在哪宫、有没有破相（见下两表） |
| 存：留不留得住 | 兄弟宫（手头资金：钱到手能放多久、拿去投资是赚是亏、花钱松紧）、田宅宫（储蓄置业：能不能变成固定资产、资产涨跌稳不稳） | 看化忌和煞星，煞星里地空、地劫破财最重。两宫有损就是蓄水池漏水，流水再高也是过手财神【赵】。有主星又得自化禄权的，一颗空劫不算大破相；空宫再见空劫才是守不住【赵·案例】，这条是两案对比推出的，标【推断】 |
| 保：容错率与底线 | 生年忌在六内宫还是六外宫 | 依据是禄随忌走【赵】。六内（命、财帛、官禄、田宅、疾厄、福德）：钱最终落回自己掌控的范围，保值性强；忌在财帛尤其如此，过程焦虑劳累、把钱看得重，结局往往比一般人有钱。六外（迁移、仆役、夫妻、子女、父母、兄弟）：钱容易流向他人；不是发不了财，是重大决策要三思、少待在高风险环境、不为感情、子女、朋友面子无限投入 |
| 得：他人之财 | 父母宫（父亲、长辈）、兄弟宫（母亲、兄弟姐妹）、田宅宫（家族资产） | 三宫有生年禄、禄存，或底子厚，多半出身条件好、旺家运【赵】。「线」当一体看：禄权在疾厄，也算在父疾线上【赵·案例】。禄在这些位置却逢自化忌：出生时家境好，之后走低。婚姻得财同理，本质都是禄在不同宫发力，禄有损则转到哪里效率都打折【赵】 |

**生年禄的位置**【赵】

| 档 | 落宫 |
|---|---|
| 最好 | 命宫＞财帛＞官禄。只要上班做事就有效益 |
| 中等 | 迁移、田宅 |
| 当下时代有利 | 仆役（文章叫交友宫，指粉丝和客户） |
| 较难利用 | 福德、疾厄、夫妻、子女。不懂盘的人基本用不上；知道了就能追着禄点跑 |

**禄的破相与加分**

| 情形 | 在【财富专题数据】里怎么认 | 读法【赵】 |
|---|---|---|
| 禄忌 | 禄所在宫有生年忌或自化忌，或对宫有生年忌（原文「对宫也算」） | 不是赚不到，是模式不能持续：好一阵坏一阵、工作频繁变动、赚到后中断甚至亏损，难成复利 |
| 逢空劫 | 禄所在宫有地空或地劫 | 财来财去，赚 100 到手 30；防被骗 |
| 其他煞星、禄出 | 同宫羊陀火铃；同宫离心自化禄 | 有影响，比前两种轻得多 |
| 禄权、禄科 | 禄所在宫有自化权或自化科，不必是同一颗星【赵·案例】 | 渠道持续向上、有扩张效果 |

自化的范围【赵·案例】：离心自化和向心自化都算。作者说案例一「自化禄权很多」，那张盘离心加向心的禄权合计 8 处；原文没有给门槛，不硬设数字。自化禄权多的作用【赵】：禄和禄存长得不好时能弥补很多，长得好时锦上添花；也能抵掉命福有忌这类瑕疵【赵·案例】。对宫空劫不算破相（案例一禄存对宫有地劫，作者仍说没问题）【赵·案例】。

**三档**【赵】（三组典型配置，不是穷尽分类）

| 档 | 配置 | 现实定位与做法 |
|---|---|---|
| 第一档 | 生年禄无破相且遇自化权科；全盘自化禄权多；兄弟、田宅无严重破相；生年忌在六内；命宫福德较好；最好有成格 | 现实里极少。找到禄所在宫对应的领域持续深耕，不频繁换赛道，适度投资，做好资产配置；持续下来到中产以上、身边同龄人前 30% |
| 第二档 | 生年禄无破相或只有非空劫的小破相；兄弟、田宅有一个稳；生年忌在六内；命福中上 | 比第一档常见，有干扰但整体稳。稳扎稳打，少做忌所在宫的事，重点用赚和存里较强的一环；存不住就强制储蓄、配置资产 |
| 第三档 | 生年禄有禄忌；兄弟、田宅都有不同程度破相；生年忌位置不定；命福中等 | 求财有起伏，不是赚不到。多做禄权科所在宫的事，少碰忌所在宫的事；守住赚钱模式的持续性；强制储蓄，避免冲动消费 |

赚、存、保三项大体同向才给档位。不同向时照实分项写，不硬归档：案例二禄无破且成禄权，但生年忌在兄弟宫又自化忌、田宅空宫见地空，哪一档都放不进，作者的结论就是赚了一千万、存下零。

**格局**【赵】：成格条件苛刻，缺一项就不算，实战以上面四项为主。双禄拱：命、财、官、迁四宫有生年禄加禄存，不见自化忌、禄出、空劫煞星；用得好，配额千万。火贪格：火星或铃星与贪狼在命、财、官，贪狼落辰戌丑未，见化禄或禄存，不碰忌；属快钱，几百万到上千万，看具体盘。按 Z3 落现实定位时，用这些和三档的定位作刻度。

**大运**【赵】：同一套也用于看大运。把大限宫当命宫，看生年禄、禄存、生年忌落在大限的哪一宫（脚本大限一栏已列出）：这步运生年禄在大限官禄是工作得财，下步在大限夫妻是婚姻得财。原文只有这一句和这一例，展开部分标【推断】。逐项列，不合成一句「转好」或「转差」：一步运留不留得住，分别看大限宫自己有没有空劫、生年禄和禄存落在大限的哪一档位置、生年忌落在大限的六内还是六外；只变了一两项，就照实说哪项变了、哪项没变。把六内六外用到大限宫上是本 skill 的延伸，原文没有。落宫一律读脚本，不心算：大限三合的两宫一个是财帛、一个是官禄，容易数反。

**原文没讲到的地方**（本 skill 的处理）

- 禄存的破相标准：原文把禄存与生年禄并列为「唯二」，之后只讲生年禄。照生年禄的标准用，结论标【推断】。禄存必被羊陀相夹，夹不算破相。
- 禄在父母宫、兄弟宫：位置排序不含这两宫；「禄在父母宫，是不是有可能父亲给你钱」原文是设问，不是规则；案例一禄正在父母宫，盘主却白手起家、反过来养亲戚。处理：禄的落宫说的是财经由哪条线来，不规定谁给谁；父母宫兼指长辈、上司、机构与文书【通】。先问事实（家里给过多少、起步资金哪来、现在谁养谁）再定读法，没有事实时两读并列，标【存疑】。盘例一禄权在父母宫，读博由国家留学基金委出资、硕士家里供、创业家里基本没给，对上的是公家机构与文书线这一读法。
- 生年忌在田宅宫：「存」一项看到化忌算有损，「保」一项说忌在六内是保值，两条在这里相遇。两读都写，不二选一：三合派读法（居所多变动、置业吃力、家宅文书多事）【通】说的是过程，【赵】的保值读法说的是终局。后者要等当事人有了资产才检验得了，之前标【存疑】。
- 兄弟宫或田宅宫是空宫、又无煞无忌：不算破相，但没有守财的力量，读作钱不会自己结余、要靠强制储蓄【推断】。
- 福德或财帛一线有火贪、武贪而不成格（见忌、见空劫，或不在命财官）：读作进账是单笔、项目型，来了不沉淀；不直接读成投机冲动，投不投机问事实【推断】。
- 命福「较好」的标准：原文没给。按案例，主要看这两宫有没有生年忌、自化忌，星曜质量参考 Z2。案例一「命福双忌」里命宫那一个，读作命宫宫干化忌入迁移（表里带 ⇄），这个读法标【存疑】。
- 各宫对应什么赚钱领域：原文只点了财帛与官禄（上班工作）、仆役（粉丝客户）、父母（长辈）、夫妻（婚姻），其余按宫位本义推，标【推断】。

**与三合派对照、标签、验证**

- 先写【赵】的读法。三合派读法相反时（如化忌坐财帛，三合派读作求财辛苦，【赵】读作保值）两读并列，各写成立条件，按铁律 3、5 定标签；只有本节支持的结论最高【推断】。
- 这套断语的依据是作者自选的三个案例，加我方一个盘例（见「核验记录」盘例一）。盘例一对上的三条都在本命和大限层面：禄权在父母宫读作机构与文书线，兄弟宫空宫加当前大限读作留存少，生年忌在田宅读作居所不定；福德一条读偏。只有一张盘，验证状态仍从「未验证」起，对上已知事实再改。
- 取样问题：近十年收入有没有中断或大起大落的年份（禄忌）；赚到的钱实际到手多少、有没有被骗被拖款（空劫）；手头存款相当于几个月收入、有没有房产（兄弟、田宅）；大额支出最后花在谁身上（忌的内外）；家里给过多少（得）。
- 每指出一处问题都配上表里对应的做法，目的是修补变现通道上的化忌、空劫和留不住的消耗【赵】。

---

## 时间层级：大限、流年、流月、流日

问某段时间的状态、某年某月某日、挑日子，或「本命明明如此，这几年为什么不像」时用。出自赵财猫【赵】，四化派口径。落宫和四化一律读脚本（大限一栏、流年一栏、`--months`、`--day`）。按倪师口径批盘时不用本节。

**五层**【赵】

- 本命＞大限＞流年＞流月＞流日，一层套一层。看具体问题先定位当下走在哪一层的哪一宫，不只盯本命盘。
- 本命是一生的总结：底色、格局高低、性格基调。大限是这十年的总结，是这十年的特质。流年是这一年的总结。流年的波动在大限的范围里波动，最后回落到大限的水平。
- 流日只管当天，流月只管当月（农历月），流年只管当年。原文把它比作统计和天气预报。

**大限**【赵】

- 把大限宫当命宫：大限命宫的星看这十年的外在表现，大限福德宫的星看内在精神，连同落在这两宫的四化一起读。本命像破军而这十年不像，多半是大限走到了别的星上。
- 大限宫干四化是从大限命宫发出去的，代表这十年主观上想做和不想做的事，不代表客观上成不成。客观看生年四化落在大限的哪一宫：大限禄权进了大限夫妻宫，而生年忌也在大限夫妻宫，是很想谈、却谈不顺。这和 Z7 里叠大限宫干四化看吉凶的通行读法【通】不同，两者相反时两读并列。
- 其他：五行局对性格只有一点加强（火局冲动，水局深沉敏感，木局头脑清晰，金局刚毅，土局沉稳而不变通），不作单独依据；八字的起运时间在紫微里不参考。「起运男生越晚越好、女生越早越好」原文只有一句、没有给理由，记录在此，不用来下判断。

**流年**【赵】

- 流年命宫在当年地支所在的宫，其余十一宫顺着排。
- 流年干四化是今年有没有事发生的关键：它引动本命盘或流年盘里已有的象。大限显示这十年容易有某事，哪一年发生看流年，例如结婚看流年夫妻宫、子女宫走得好不好。

**流月、流日**【赵】

- 流月：正月所在宫因人而异，跟生月、生时有关（斗君）；从正月宫顺时针一月一宫。流日：初一起于流月命宫，顺时针一天一宫。找到命宫后以它立太极，排出那一层的十二宫。
- 流年、流月、流日各取当年、当月、当日天干的四化（乙年机梁紫阴，己月武贪梁曲，辛日巨阳曲昌）。这三层四化对当时的运势有切实的催动作用，重要程度与生年四化相当，是判断的基点；大限四化反而不重要。
- 叠看：流月的禄权和流年的禄权都落在当月的官禄宫，这个月容易升职加薪。

**各宫在流月、流日的读法**【赵】

| 宫 | 流月看什么 | 流日看什么 | 化禄 | 化忌 |
|---|---|---|---|---|
| 命宫 | 这个月的性格特质，偏向流月命宫的星 | 当天的心情和状态 | 心情好、顺心（化权：比较努力，做事积极） | 心情差、莫名不爽，诸事不顺 |
| 疾厄 | 身体哪里不舒服，办公环境变动 | 身体感受，工作地点 | 身体舒服，或容易长胖 | 小病小痛，或办公环境让人不舒服 |
| 福德 | 精神压力，舍不舍得花钱享受，想法积不积极 | 念头、嗜好、想法 | 想开了，享受生活 | 钻牛角尖、失眠、焦虑，或花冤枉钱 |
| 财帛 | 求财状态 | 具体的开销或财运 | 进账，或花钱花得痛快 | 破财、罚款、丢东西，或因钱起冲突 |
| 官禄 | 工作情况，有没有升职、离职的机会 | 当天的工作、学习任务 | 工作轻松、灵感多、办事顺 | 加班、出错、压力大，或不想上班 |
| 田宅 | 搬家、装修、买房，家庭成员关系 | 出不出门，家庭琐事 | 家里舒服，家人相聚开心 | 家里东西坏、和家人吵架，或出门不顺 |
| 夫妻 | 感情甜蜜度，有没有桃花机会 | 和对象的相处；当天的副业 | 约会、亲密互动 | 吵架、冷战；单身的觉得孤独 |
| 子女 | 性生活、怀孕、带孩子，合伙情况 | 娱乐，孩子、下属 | 出去玩得开心 | 孩子惹事、下属不听话，玩得不尽兴 |
| 父母 | 和领导、父母的关系，考试运、合同运 | 见领导，办证、签字 | 领导夸、父母给钱、考试顺利 | 挨批、文书填错、被长辈施压 |
| 兄弟 | 投资状态，睡眠，手头资金的开销，出门娱乐 | 当天花销、投资涨跌、睡眠 | 和朋友聚会开心，花了笔开心钱，投资小涨 | 朋友借钱，突然一笔大额支出，睡眠不好 |
| 仆役（交友） | 社交圈扩大，客户来源，粉丝增长 | 社交场合、陌生人、涨粉 | 饭局多、受欢迎、涨粉 | 遇小人、被放鸽子，人际关系心累 |
| 迁移 | 出差、去外地的机会，旅游 | 路上的状态，给人的第一印象 | 出门顺利，遇贵人 | 堵车、剐蹭、迷路，出门办事碰壁（天机化忌尤其） |

**怎么用**【赵】

- 日子是过出来的，不是算出来的；用在关键决策上避坑。
- 流月忌、流日忌所在的宫，当月当日尽量不碰。流日田宅忌可以出门化解；流日官禄忌，工作不要偷懒；流日父母宫有忌，剪发、美容、签字办证要谨慎。
- 挑日子：要做的事对应哪一宫，就挑那一宫好的日子（有生年禄或流日禄）。做投放挑流日交友宫好的日子；签合同看父母宫，昌曲化忌那天多核对；流日夫妻宫和福德宫同时不好，处理感情要小心。

**本 skill 的处理**

- 标签与验证：只有本节支持的结论最高【推断】；流月、流日的好坏判断，验证状态写「未验证」。盘例一里流年应期没有过对照（见「已知口径分叉与限制」），所以流年、流月、流日用来说哪一宫的事占精力、哪些事当天宜缓，不用来断具体事件一定发生；要断，就按「验证纪律」事先约定。
- 原文说流年会回落到大限的水平，和盘例一的结果同向（流年业务量涨，留存仍按大限走）：先定大限，再看流年，流年改不了大限的基调。
- 流日的忌只提示多留意，不替代该做的事：合同该审照审；重断仍按铁律 7。
- 三合派的小限【倪】照旧另列，原文不用小限。
- 闰月里的流月、流日标【存疑】。

---

## 合盘

两盘各跑一次。看甲的夫妻宫星曜与乙的命宫是否相应；双方生年四化有没有落进对方的要害宫，尤其化忌入对方命宫或夫妻宫；两人当前大限是否同步【通】。倪师的合盘观：先看各自先天是一世夫妻还是二婚的命，再谈合不合；先天二婚的命，反而要找八字不合的人【倪】（`--ni 合八字`）。`src/lib/ziwei/heming-knowledge.ts` 有十四主星在夫妻宫的整理断语，可作线索，属二手材料。

---

## 输出

- **档位**：简明（追问、小问题）／标准（默认）／详细（要推导细节或逐年）。档位只改篇幅，内部步骤照做。
- **结构**：先答所问。先把盘立起来（命宫、三方四正、四化落点），再展开。每节开头一句结论，方便对方跳着看。术语第一次出现当场解释，并落到能核对的具体表现上。
- **来源**：写进解读的斗数说法，凡出自【倪】的给讲次和时间码；出自【通】的不挂倪师或古籍的名字。
- **写给当事人本人看**：重心放在本人的特质和可用之处，时间节点只点关键几处；凶处给出路，吉处留余地。不写心理咨询式的安慰话。
- **对照事实**：对方说「想不出来」不算否证，那是还没取到样。给出取样办法（比如回想某几年前后有没有换工作、搬家、感情变化），并单独说明什么情况才算真的读偏了。放在谁身上、换哪段时间都成立的说法不计分，不当作验证；看到结果之后才想到的解释也不算。对还没发生的事下判断，事先写清什么算中、什么算不中。
- **验证纪律**（2026-11 盘例一得来）：
  - 验证应期（某年应某事）时，不该应的年份也要问。当事人处在求学、跨国、创业初期这类高频变动的阶段时，搬家、换工作每年都可能发生，只问该应的年份会把基率算成命中。
  - 几件事并列的断语（「搬迁、破财或分手」）中了一项不计分；要验证就拆成单项。
  - 事先约定检验标准时只押一边，用绝对量不用百分比（基数接近零时百分比没有意义），不预先写好不中时怎么解释。
  - 事先知道当事人的职业和经历时，验证状态最高写「已知事实拟合」，行业只写到盘面能推出的颗粒度；声明剥离背景不等于盲测。
  - 别的解读（人或 AI）被反驳后改口，或读过本解读后与本解读一致，都不算印证。对方的落宫、飞化、格局先用脚本核一遍，再谈结论。
- **说某宫是某段时间的主线**：意思是这类事占精力，不等于吉凶。落在疾厄宫或身体上时，明说不是「会生病」；断病按铁律 7。
- 全程中文。

---

## 已知口径分叉与限制

| 项 | 情况 | 处理 |
|---|---|---|
| 辛年魁钺 | 口诀「六辛逢马虎」魁午钺寅（脚本默认 `rhyme`）；主流排盘软件默认魁寅钺午（`engine`，见引擎 `algorithm.ts` 注释）。`engine` 口径下这两颗不显示亮度，亮度表在寅魁、午钺两位留空 | 辛年生人涉及魁钺的判断标【存疑】或两读 |
| 闰月 | `split` 月中分界（默认，主流软件）／`next-month` 归下月（倪师【倪】，`--ni 闰月生人`）／`prev-month` 视为本月。闰月三十日：归下月时仍按 30 日起紫微；`prev-month` 遇到本月只有 29 天，引擎按 29 日起，脚本会提示 | 闰月生人说明口径；影响判断时两盘并列；闰月三十日的 `prev-month` 盘，紫微落宫标【存疑】 |
| 晚子时 | `next-day` 换次日（默认）／`current-day` 仍算当日（倪师【倪】，`--ni 晚子`） | 23 点后出生的说明用了哪种 |
| 夏令时 | `--dst yes` 把钟表时间减 60 分钟。大陆只在 1986–1991 实行过，脚本只对这几年主动提示。引擎的夏令时表还含 1935–1961、1974–1975、1979，日期与台湾历年夏令时大体吻合，遇到这些年份脚本提示「大陆出生加 `--dst no`」。港澳台用 `--city` 给出时，1980 年以前出生的脚本另行提示；各地具体哪几年实行、海外的夏令时，脚本都不查 | 台湾、港澳、海外出生的，先问清当时当地是否实行夏令时、所报是不是钟表时间，再定 `--dst` |
| 海外出生 | `--lng` 和 `--tz` 必须一起给；只给国内范围（73–135）以外的经度，脚本直接报错。韩国、东南亚这类经度落在国内范围里的地方脚本分辨不出，漏了 `--tz` 会按东八区算 | 海外一律带 `--tz`；参数卡里经度修正超过 ±60 分钟就回头核对经度和时区 |
| 真太阳时 | 给了出生地就按经度和均时差校正（默认）；`--solar no` 直接用钟表时间。排盘软件做法不统一 | 校正前后跨时辰时脚本会提示；两盘都交代，说明按哪张读 |
| 农历历表 | 1933-07-22~08-20、1954-11-25~12-24、1978-09-02~10-01、2057-09-28~10-27 这四段，两套历表相差一天 | 脚本自动提示；以家里过的农历生日为准，用 `--lunar` 重排。这样排出的盘，参数卡上的公历日和节气四柱可能差一天，转 bazi-core 时用真实公历生日 |
| 亮度 | 默认《斗数全书》（QS），另有现代修订两版（XD1、XD2）和中州派（ZZ） | 亮度左右判断时说明用的哪套 |
| 庚年四化 | 脚本取阳武阴同；引擎配置里另列阳武同阴、阳武府同、阳武府相、阳武同相四种，分歧在化科、化忌两位 | 只有判断依赖有分歧的那一位化星时才标【存疑】 |
| 流年应期 | 2026-11 盘例一做过对照：「流年命宫或流年化忌入田宅，应在住处变动」，该应的两年都应了，不该应的五年里三年也有迁动（当事人连续五年跨国往返），分辨不出。同一张盘本命和大限层面的三条判断对上了 | 流年判断先问清这类事在当事人身上的基率；高频变动阶段不断具体事件，只说哪一宫的事占精力。流年结论的验证状态单独标，不借用本命、大限层面已经对上的事实 |
| 流月、流日 | 脚本按通行起法排：流年斗君定正月所在宫，逐月顺数；初一起于流月命宫，逐日顺数；月干按五虎遁配农历月，日干取当日干支。闰月算哪个流月，各软件处理不一，脚本按本月算并提示。读法出自【赵】，我方没有验证过：此前在一张盘上临时推过两个月，落宫都对，好坏两次都没中，样本很小 | 按「时间层级」一节读；好坏判断的验证状态写「未验证」，事先写清什么算中、什么算不中；闰月里的日子标【存疑】 |
| 未覆盖 | 流时；长生、博士、岁前、将前十二神（劫煞、龙德除外） | 需要时说明做不到 |

**核验记录**：2026-11-02，用另外独立写的安星规则（农历换算改用 lunardate）对 1930–2030 年随机 3000 盘逐项比对：命宫、身宫、五行局、宫干、十四主星、左右昌曲魁钺、禄存羊陀、空劫、火铃、天马、生年四化、大限、小限全部一致；差异只有上表中的辛年魁钺和历表争议区间两类。引擎自带的 9 项排盘回归测试全部通过。2026-11-11 复核：另写一套规则重跑 3000 盘，结论相同，另查出第三类差异——闰月三十日（1900–2099 共 20 天，引擎 `next-month` 路径在其中 17 天把日数压成 29，紫微差一宫），脚本已改为归下月时按 30 日起；脚本算的小限、大限落宫与 iztro 自带运限 3000 例一致；文中 21 个 `--ni` 检索词逐个核过，原话支持文中说法。杂曜落宫和亮度没有独立核过，依赖引擎自己对金标准盘的对齐。2026-11-13：财富专题数据用赵财猫文中三张案例盘核过，做法是按盘面特征反推出同盘的生日时辰重排，脚本列出的生年四化、离心自化、向心自化与原图的星曜和自化箭头逐宫一致。盘例一（2026-11-13，丁丑年阴男，金四局，天府坐命）：财富专题四条事先判断，对上两条（留存少；禄在父母宫读作机构与文书线），半对一条（当前大限钱流向合伙与客户线：有垫资，无损失），读偏一条（福德火贪自化忌读作投机冲动，实际投机很少，是单笔项目型进账）；流年层的对照见上表「流年应期」。【赵】「忌在六内保值」和 34 岁以后大限的判断属前瞻检验，未到期。流月、流日落宫（第五版）：脚本算的流月命宫、流日命宫、月干、日干，与 iztro 自带运限随机 400 例逐项一致（非闰月出生，目标日不在闰月）；赵财猫文中两张流年盘截图上的正月所在宫和各月天干也对得上。闰月未核。

---

## 资料与来源

| 内容 | 来源 | 核过没有 |
|---|---|---|
| 排盘计算 | 引擎 `src/lib/ziwei/`，底层是 iztro；亮度、换年、魁钺、截空、大耗等修正是仓库作者依主流排盘软件对照所做 | 主要安星项独立核过 3000 盘；杂曜、亮度未核 |
| 独立核对用的安星规则 | 按通行安星诀另写（安命身宫、五虎遁、纳音定局、起紫微、两系主星、辅煞、四化、大限小限） | 与引擎互相印证，不等于对上某个特定古本 |
| 倪师原话（1848 条） | `src/docs/tianji-ziwei/`，取自 nihai-tianji-corpus，是《天纪》B 站视频的字幕整理，每条带时间码 | 字幕转写，偶有错字 |
| 口径选项 | 引擎 `school-config.ts`、`school-data.ts`；辛年魁钺分歧见 `algorithm.ts` 注释 | — |
| 历表争议日期 | lunar-javascript 与 lunardate 在 1900–2100 年逐日比对 | 哪本历表对，未判定 |
| 协议骨架与标签 | 与 bazi-core 保持一致 | — |
| 【通】条目 | 通行教法 | 未逐条对文献 |
| 格局规则 | `src/lib/ziwei/patterns.ts`，作者自写，「出处」为作者所标 | 未核 |
| 财富专题【赵】 | 赵财猫讲财富层次的付费长文（公众号「赵财猫说紫微」），用户提供的截图转录稿，约七千字加三张案例盘 | 转录稿对过 15 张原始截图。文末断在总结段、章节号有重复和缺号，都是原文如此。三张案例盘的四化已用脚本复现；断语本身未用我方盘例验证 |
| 时间层级【赵】 | 赵财猫讲大限、流年、流月、流日的付费长文，用户提供的 13 张截图，直接读图，没有另做转录稿 | 文中的起运、斗君、流月流日起法与脚本和 iztro 一致；各宫禄忌的读法未用我方盘例验证 |
| 合盘整理 | `src/lib/ziwei/heming-knowledge.ts` | 二手；标为倪师原话的 9 句，整句在语料里都查不到 |
| 古籍节选 | `src/lib/classics/data/`（骨髓赋、全集、全书） | 节选，未对底本 |

倪师原话按讲分文件：2上 十二宫；3上 四化与北斗；4上 南斗、六杀与批命顺序；5上–8上 紫微在十二宫；9上 化忌冲命、再婚；10上 杀破狼个性与案例；11上–12上 六亲与多婚；13上 杀破狼、科权禄三会；14上–15上 太阳太阴与女命；19上、24下各有一份补充（共 40 条）。

授权：引擎代码 MIT；倪师原话 CC BY-NC-SA 4.0（限非商用，自用不受影响）。

---

## 与其他 skill

- 参数卡里有节气四柱，同一人可以直接交给 bazi-core 复核。
- 要多套系统一起看时，照 dual-lens-oracle 的做法：各自盲跑，再对照，紫微作为其中一镜。

---

## 附录：写出 run/pan.ts

```bash
cat > "${ZIWEI_HOME:-$HOME/.cache/ziwei-core}/run/pan.ts" <<'ZWEOF'
// ziwei-core 排盘封装：调用 ziwei-doushu 引擎（iztro + 全书口径修正），只出计算结果，不做解读。
import { generateChart, setBrightnessSchool } from '../src/lib/ziwei/algorithm';
import { detectPatterns } from '../src/lib/ziwei/patterns';
import { calculateTrueSolarTime, resolveZiweiDayOffset, shiftGregorianDate } from '../src/lib/ziwei/true-solar-time';
import { isChinaDST } from '../src/lib/ziwei/dst-cn';
import { PROVINCES } from '../src/lib/ziwei/cities';
import { SI_HUA_TABLE, STEMS, BRANCHES } from '../src/lib/ziwei/constants';
import { schoolStarBrightness } from '../src/lib/ziwei/school-data';
import { Lunar, Solar, LunarYear } from 'lunar-javascript';

const A: Record<string, string> = {};
const av = process.argv.slice(2);
for (let i = 0; i < av.length; i++) if (av[i].startsWith('--')) { const k = av[i].slice(2); const v = av[i + 1] && !av[i + 1].startsWith('--') ? av[++i] : 'yes'; A[k] = v; }
const die = (m: string): never => { console.error('错误：' + m); process.exit(2); };
process.on('uncaughtException', err => die(`脚本异常，这次没有排出盘：${(err as Error).message}`));
const KNOWN = ['date', 'lunar', 'leap', 'time', 'shichen', 'city', 'lng', 'tz', 'dst', 'solar', 'uncertainty', 'gender', 'year', 'months', 'day', 'leapmode', 'zi', 'bright', 'kuiyue', 'json', 'ni', 'limit', 'selftest'];
const unk = Object.keys(A).filter(k => !KNOWN.includes(k));
if (unk.length) die(`不认识的参数 ${unk.map(k => '--' + k).join(' ')}。可用：${KNOWN.map(k => '--' + k).join(' ')}`);
const stray = av.filter((x, i) => !x.startsWith('--') && !(i > 0 && av[i - 1].startsWith('--')));
if (stray.length) die(`多出来的参数值：${stray.join(' ')}（多个年份用逗号连写，不加空格）`);
if (A.ni) {  // 倪师《天纪》原话检索：多个关键词用逗号分隔，须同时命中（原话、册目、小标题里任一处）
  const fs = require('node:fs'), path = require('node:path');
  const f = path.join(__dirname, '../src/docs/tianji-ziwei/entries.jsonl');
  const kws = A.ni.split(/[,，]/).filter(Boolean), lim = Number(A.limit ?? 30);
  const hits = fs.readFileSync(f, 'utf8').trim().split('\n').map((l: string) => JSON.parse(l))
    .filter((e: any) => kws.every((k: string) => `${e.quote}${e.h2}${e.h3}`.includes(k)));
  for (const e of hits.slice(0, lim)) {
    const sec = e.t_hms.split(':').map(Number).reduce((a: number, b: number) => a * 60 + b, 0);
    const jiang = e.part % 2 ? `${(e.part + 1) / 2}上` : `${e.part / 2}下`;
    console.log(`[${jiang} ${e.t_hms}] 「${e.quote}」〔${e.h2}${e.h3 ? ' › ' + e.h3 : ''}〕 https://www.bilibili.com/video/${e.bvid}?p=${e.part}&t=${sec}`);
  }
  console.log(`共 ${hits.length} 条${hits.length > lim ? `，只列前 ${lim} 条（--limit 调整）` : ''}`); process.exit(0);
}
if (A.selftest) {  // 期望值来自独立安星规则核对通过的盘（命宫支、局数、紫微支、生年化忌）
  const T: [string, number, 'male' | 'female', number, number, number, string][] = [['1966-12-15', 7, 'female', 5, 2, 3, '廉贞'], ['1983-10-15', 3, 'male', 7, 6, 5, '贪狼'], ['2004-7-7', 5, 'female', 1, 2, 11, '太阳'], ['1949-1-14', 8, 'male', 5, 5, 9, '天机'], ['1990-1-1', 6, 'male', 7, 5, 2, '文曲'], ['1944-6-20', 0, 'male', 6, 5, 7, '太阳']];  // 末一盘是闰四月三十日，引擎 split 路径按 30 日起紫微；归下月的处理依赖这一点
  let bad = 0;
  for (const [dt, h, g, mg, ju, zw, ji] of T) {
    const [yy, mo, dd] = dt.split('-').map(Number), c = generateChart({ year: yy, month: mo, day: dd, hour: h, gender: g });
    const got = [c.mingGongBranch, c.wuxingJu, c.ziweiPos, c.palaces.flatMap(p => p.stars).find(s => s.siHua === '忌')?.name];
    const ok = JSON.stringify(got) === JSON.stringify([mg, ju, zw, ji]); bad += ok ? 0 : 1;
    console.log(`${ok ? '✓' : '✗'} ${dt} ${'子丑寅卯辰巳午未申酉戌亥'[h]}时 ${g}  得 ${JSON.stringify(got)}  应 ${JSON.stringify([mg, ju, zw, ji])}`);
  }
  console.log(bad ? `自检失败 ${bad} 项：引擎或依赖版本有变，先别用这次的盘` : '自检通过'); process.exit(bad ? 1 : 0);
}
if (!A.gender || !/^(male|female|男|女)$/.test(A.gender)) die('必须给 --gender male|female，不默认');
const gender: 'male' | 'female' = /^(male|男)$/.test(A.gender) ? 'male' : 'female';
const ZI = A.zi ?? 'next-day', LEAP = (A.leapmode === 'origin-month' ? 'prev-month' : A.leapmode) ?? 'split', BR = A.bright ?? 'QS', KY = A.kuiyue ?? 'rhyme';
if (!['rhyme', 'engine'].includes(KY)) die('--kuiyue 只能是 rhyme|engine');
if (!['next-day', 'current-day'].includes(ZI)) die('--zi 只能是 next-day|current-day');
if (!['split', 'next-month', 'prev-month'].includes(LEAP)) die('--leapmode 只能是 split|next-month|prev-month');  // origin-month 排出的盘与 prev-month 相同，按 prev-month 处理
const num = (k: string, lo: number, hi: number) => { if (A[k] === undefined) return undefined; const v = Number(A[k]); if (!Number.isFinite(v) || v < lo || v > hi) die(`--${k} 要是 ${lo} 到 ${hi} 之间的数，收到「${A[k]}」`); return v; };
const LNG = num('lng', -180, 180), TZ = num('tz', -12, 14), U = num('uncertainty', 0, 120) ?? 15;
for (const k of ['dst', 'solar', 'leap']) if (A[k] !== undefined && !['yes', 'no'].includes(A[k])) die(`--${k} 只能是 yes|no`);
const norm = (s: string) => s.replace(/(特别行政区|自治州|自治县|新区|地区|市|县|区|盟)$/, '');
const ymd = (s: string, what: string) => { const t = /^(\d{4})-(\d{1,2})-(\d{1,2})$/.exec(s); if (!t) die(`${what} 要写成 YYYY-MM-DD，收到「${s}」`); return t!.slice(1).map(Number); };
if (!['QS', 'XD1', 'XD2', 'ZZ'].includes(BR)) die('--bright 只能是 QS|XD1|XD2|ZZ');
setBrightnessSchool(BR as any);
const notes: string[] = [], warns: string[] = [];

// ── 1. 公历日期 ──
let y: number, m: number, d: number;
if (A.lunar) {
  const [ly, lm, ld] = ymd(A.lunar, '--lunar');
  let s: any;
  try { s = Lunar.fromYmd(ly, A.leap === 'yes' ? -lm : lm, ld).getSolar(); }
  catch { die(`农历 ${A.lunar}${A.leap === 'yes' ? '（闰月）' : ''} 在脚本所用的历表里不存在：那一年没有这个闰月，或那个月只有 29 天。1933、1954、1978、2057 年的争议月份两套历表大小月不同，遇到这种情况改用公历生日 --date 排，再按 ⚠ 处理`); }
  [y, m, d] = [s.getYear(), s.getMonth(), s.getDay()];
  notes.push(`农历输入 ${A.lunar}${A.leap === 'yes' ? '（闰月）' : ''} → 公历 ${y}-${m}-${d}`);
} else if (A.date) {
  [y, m, d] = ymd(A.date, '--date');
  const pd = new Date(Date.UTC(y, m - 1, d));
  if (pd.getUTCMonth() !== m - 1 || pd.getUTCDate() !== d) die(`公历 ${A.date} 这一天不存在`);
}
else die('需要 --date YYYY-MM-DD（公历）或 --lunar YYYY-MM-DD [--leap yes]');

// ── 2. 时辰：直接给时辰，或钟表时间 + 校正 ──
if (y! < 1900 || y! > 2100) die(`只支持 1900–2100 年，收到 ${y!} 年`);
let hour: number, day = { year: y!, month: m!, day: d! };
const SC = '子丑寅卯辰巳午未申酉戌亥';
if (A.shichen) {
  const late = /^晚子/.test(A.shichen), sc0 = A.shichen.replace(/^[早晚](?=子)/, '');
  hour = SC.includes(sc0[0]) ? SC.indexOf(sc0[0]) : /^\d+$/.test(sc0) ? Number(sc0) : -1;
  if (!(hour >= 0 && hour <= 11)) die('--shichen 用 子..亥（23 点后写 晚子）或 0..11');
  if (late && ZI === 'next-day') day = shiftGregorianDate(day, 1);
  notes.push(`直接按${late ? '晚' : ''}${SC[hour]}时排盘，未做真太阳时校正${late ? `；晚子时按${ZI === 'next-day' ? '次日' : '当日'}排盘` : hour === 0 ? '；按所给日期排，23 点后出生的要写 --shichen 晚子' : ''}`);
} else {
  if (!A.time) die('需要 --time HH:MM（钟表时间）或 --shichen 子..亥；时辰未知时分别排候选盘，不要猜');
  const tm = /^(\d{1,2}):(\d{2})$/.exec(A.time);
  if (!tm || +tm[1] > 23 || +tm[2] > 59) die(`--time 要写成 HH:MM（00:00 到 23:59），收到「${A.time}」`);
  let hh = +tm![1], mm = +tm![2];
  // 夏令时：引擎的表除大陆 1986–1991 外，还含 1935–1961、1974–1975、1979（与台湾历年夏令时大体吻合），大陆出生不能照减
  const prov = A.city ? PROVINCES.find(p => p.cities.some(c => norm(c.name) === norm(A.city)))?.name ?? '' : '';
  const hmt = /香港|澳门|台湾/.test(prov), overseas = TZ !== undefined && TZ !== 8, tblDST = isChinaDST(day.year, day.month, day.day), cnDST = !overseas && !hmt && tblDST && day.year >= 1986;
  if (A.dst === 'yes') {
    if (!cnDST && !overseas && !hmt && !tblDST && TZ === undefined) die(`${day.year} 年这一天大陆没有夏令时，--dst yes 用不上。港澳台出生用 --city 给出生地，海外出生给 --lng 和 --tz，再加 --dst yes`);
    let t = hh * 60 + mm - 60; if (t < 0) { t += 1440; day = shiftGregorianDate(day, -1); }
    [hh, mm] = [Math.floor(t / 60), t % 60]; notes.push('夏令时：按当年钟表读数减 60 分钟');
    if (!cnDST && !overseas && !hmt) warns.push(`按 --dst yes 减了 60 分钟，但 ${day.year} 年这一天不在大陆夏令时（1986–1991）之内。只有台湾、港澳等地出生且确知当时实行夏令时才这样用，大陆出生去掉 --dst yes`);
  } else if (A.dst !== 'no') {
    if (cnDST) warns.push('出生日在大陆夏令时期间（1986–1991）。若所报是当年钟表时间，加 --dst yes 重排；确认已是标准时间就加 --dst no');
    else if (overseas) warns.push('海外出生：脚本不查当地夏令时。出生时当地若在实行夏令时、所报又是钟表时间，加 --dst yes（减 60 分钟）；否则加 --dst no');
    else if (hmt) { if (day.year <= 1980) warns.push('港澳台出生：三地在 1980 年以前都实行过夏令时，年份各不相同，脚本不逐日查。先查清出生那年当地是否实行：实行且所报是钟表时间，加 --dst yes；否则加 --dst no'); }
    else if (tblDST) warns.push(`引擎的夏令时表把 ${day.year} 年这一天也算作夏令时，但 1986 年以前的条目对应的是台湾等地：大陆 1950–1985 没有实行过，1949 年以前各地不一。大陆出生加 --dst no；台湾出生、或确知当地当时实行夏令时且所报是钟表时间，才加 --dst yes`);
  }
  let lng = LNG;
  if (A.solar === 'no') { lng = undefined; notes.push('按 --solar no 不做真太阳时校正，直接用钟表时间'); }
  else if (lng !== undefined) {
    if (TZ === undefined && (lng < 73 || lng > 135.1)) die(`经度 ${lng} 不在国内范围（73–135）。海外出生要同时给 --tz（出生地标准时区，如纽约 -5），否则会按东八区算错几个小时`);
    if (TZ !== undefined && Math.abs(lng - TZ * 15) > 35) warns.push(`经度 ${lng} 与时区 UTC${TZ >= 0 ? '+' : ''}${TZ} 的中央经线相差超过 35°，核对经度的东西正负和时区`);
  } else if (A.city) {
    const key = norm(A.city), all = PROVINCES.flatMap(p => p.cities.map(c => ({ ...c, prov: p.name })));
    const exact = all.filter(c => norm(c.name) === key);
    const hits = exact.length ? exact : all.filter(c => norm(c.name).startsWith(key) || key.startsWith(norm(c.name)));
    const list = hits.map(h => `${h.prov}${h.name}(${h.longitude})`).join('、');
    if (exact.length || hits.length === 1) {
      lng = hits[0].longitude; notes.push(`出生地 ${hits[0].prov}${hits[0].name}，经度 ${lng}`);
      if (hits.length > 1) warns.push(`城市重名：${list}。当前取第一个，要另一个就改用 --lng`);
    } else warns.push(hits.length ? `「${A.city}」对上了多个城市：${list}，没有采用。写全名或改用 --lng` : `城市表里没找到「${A.city}」，请改用 --lng 经度`);
  }
  if (TZ !== undefined && lng === undefined && A.solar !== 'no') notes.push('给了 --tz 但没有经度，时区没有用上');
  const off = TZ !== undefined ? Math.round(TZ * 60) : undefined;
  const calc = (dm: number) => {
    const t = hh * 60 + mm + dm, sh = Math.floor(t / 1440), tt = ((t % 1440) + 1440) % 1440;
    const dd = shiftGregorianDate(day, sh);
    return { r: calculateTrueSolarTime({ ...dd, clockHour: Math.floor(tt / 60), clockMinute: tt % 60, longitude: lng, utcOffsetMinutes: off }), dd };
  };
  const { r } = calc(0);
  hour = r.branch;
  if (r.corrected) {
    const raw = calculateTrueSolarTime({ ...day, clockHour: hh, clockMinute: mm });
    if (raw.branch !== r.branch) warns.push(`真太阳时校正改变了时辰：钟表时间是${SC[raw.branch]}时，校正后是${SC[r.branch]}时，两张盘完全不同。排盘软件做不做校正不统一，用户若在别处看到的是${SC[raw.branch]}时盘，加 --solar no 排出来对照`);
  }
  day = shiftGregorianDate(day, resolveZiweiDayOffset(r, ZI as any));
  const hm = `${String(r.hour).padStart(2, '0')}:${String(r.minute).padStart(2, '0')}`;
  notes.push(r.corrected ? `真太阳时 ${hm}（经度修正 ${r.longitudeCorrectionMinutes.toFixed(1)} 分，均时差 ${r.equationOfTimeMinutes.toFixed(1)} 分）→ ${SC[hour]}时` : `${A.solar === 'no' ? '' : '未给出生地，'}按钟表时间 ${hm} 定为${SC[hour]}时（未做真太阳时校正）`);
  if (r.branch === 0 && r.normalizedMinutes >= 1380) notes.push(`晚子时（23:00 后）：按 ${ZI === 'next-day' ? '次日' : '当日'}排盘`);
  const cand = new Set([-U, U].map(x => calc(x).r.branch));
  cand.add(hour);
  if (cand.size > 1) warns.push(`出生时间 ±${U} 分钟跨时辰：候选 ${[...cand].map(b => SC[b] + '时').join('、')}。依赖时辰的判断要分候选盘看，或先做定盘`);
}

// ── 3. 排盘 ──
const rawL = Solar.fromYmd(day.year, day.month, day.day).getLunar(), rawLeap = rawL.getMonth() < 0, rawDay = rawL.getDay();
// 闰月后半归下月：引擎 next-month 路径在下月只有 29 天时把闰月三十日压成 29 日，紫微差一宫；split 路径不压。闰月十六日以后两条路径排出的盘本来相同（1900–2099 逐日核过），所以改走 split
const engLeap = LEAP === 'next-month' && rawLeap && rawDay > 15 ? 'split' : LEAP;
const chart = generateChart({ year: day.year, month: day.month, day: day.day, hour, gender }, { leapMonth: engLeap as any });
const L = chart.lunarInfo, P = chart.palaces, byB = (b: number) => P.find(p => p.branch === b)!;
const nm = (b: number) => byB(b).name;
const sfsz = (b: number) => `对宫${nm((b + 6) % 12)}、三合${nm((b + 4) % 12)}·${nm((b + 8) % 12)}`;
const pillar = (s: number, b: number) => STEMS[s] + BRANCHES[b];
// 两套农历表（寿星天文历系 lunar-javascript / lunardate）在下列日期差一天：初一落在哪天有分歧
const DISPUTE: [string, string, string][] = [['1933-07-22', '1933-08-20', '多'], ['1954-11-25', '1954-12-24', '少'], ['1978-09-02', '1978-10-01', '多'], ['2057-09-28', '2057-10-27', '多']];
const iso = `${day.year}-${String(day.month).padStart(2, '0')}-${String(day.day).padStart(2, '0')}`;
const dsp = DISPUTE.find(([a, b]) => iso >= a && iso <= b);
if (dsp) warns.push(A.lunar
  ? '农历输入落在两套农历表相差一天的区间：紫微盘按所给的农历日排，不受影响；但参数卡上的公历日和节气四柱是按脚本的历表反推的，可能与真实公历生日差一天，转给 bazi-core 时用真实公历生日'
  : `排盘日 ${iso} 落在两套农历表相差一天的区间（另一套表的农历日比参数卡上的${dsp[2]}一天），紫微落宫可能整盘改变。先问家里过的农历生日，用 --lunar 按那个日期重排`);
if (L.yearStem === 7) {  // 辛年魁钺两说
  const kui = P.find(p => p.stars.some(s => s.name === '天魁'))!, yue = P.find(p => p.stars.some(s => s.name === '天钺'))!;
  const want = KY === 'rhyme' ? { 天魁: 6, 天钺: 2 } : { 天魁: 2, 天钺: 6 };
  if (kui.branch !== want.天魁) {
    const ks = kui.stars.splice(kui.stars.findIndex(s => s.name === '天魁'), 1)[0], ys2 = yue.stars.splice(yue.stars.findIndex(s => s.name === '天钺'), 1)[0];
    for (const [st, b] of [[ks, want.天魁], [ys2, want.天钺]] as [any, number][]) { st.brightnessRaw = schoolStarBrightness(st.name, b, BR as any)?.[0]; byB(b).stars.push(st); }
  }
  notes.push(`辛年魁钺有两说：口诀「六辛逢马虎」魁午钺寅（--kuiyue rhyme，默认）；主流排盘软件默认魁寅钺午（--kuiyue engine）。当前用 ${KY}`);
}
const dispDay = rawLeap && engLeap === 'split' ? rawDay : L.lunarDay;  // 引擎 split 路径的 lunarInfo 会把三十日显示成 29，盘本身是按 30 日排的
if (rawLeap && rawDay === 30 && L.lunarDay !== 30) {
  if (engLeap === 'split') notes.push('闰月三十日归下月，下月只有 29 天：仍按 30 日起紫微');
  else warns.push('闰月三十日，而本月只有 29 天：prev-month 口径下引擎按 29 日起紫微，与按 30 日起差一宫。这张盘的紫微落宫标【存疑】，另排一张 --leapmode split 对照');
}
if (rawLeap) warns.push(`闰月生人（农历闰${-rawL.getMonth()}月${rawL.getDay()}日），当前口径 --leapmode ${LEAP}（split=月中分界，next-month=倪师派归下月，prev-month=视为本月）；口径不同则命盘不同`);
const huaOf = (stem: number) => { const t = SI_HUA_TABLE[stem]; return { 禄: t[0], 权: t[1], 科: t[2], 忌: t[3] } as Record<string, string>; };
const starPal = (name: string) => P.find(p => p.stars.some(s => s.name === name));
const fly = (stem: number) => Object.entries(huaOf(stem)).map(([h, s]) => `${s}化${h}→${starPal(s)?.name ?? '?'}`).join('　');
const fmt = (s: any) => `${s.name}${s.brightnessRaw ? `(${s.brightnessRaw})` : ''}${s.siHua ? `[化${s.siHua}]` : ''}`;
const SIX = ['左辅', '右弼', '文昌', '文曲', '天魁', '天钺', '禄存', '天马', '擎羊', '陀罗', '火星', '铃星', '地空', '地劫'];

const out: string[] = [];
const ming = byB(chart.mingGongBranch);
out.push('【参数卡】');
out.push(`公历排盘日 ${day.year}-${day.month}-${day.day} ${SC[hour]}时　${gender === 'male' ? '男' : '女'}（${chart.yinYangGender}）`);
out.push(`农历 ${L.lunarYear}年${L.isLeapMonth ? '闰' : ''}${Math.abs(L.lunarMonth)}月${dispDay}日　生年干支 ${pillar(L.yearStem, L.yearBranch)}（正月初一换年）　节气四柱 ${L.fourPillars?.join(' ') ?? ''}`);
out.push(`${chart.wuxingJuName}　命宫 ${pillar(ming.stem, ming.branch)}　身宫在${nm(chart.shenGongBranch)}（${BRANCHES[chart.shenGongBranch]}）　命主 ${chart.mingZhu}　身主 ${chart.shenZhu}`);
out.push(`口径：亮度 ${BR}${BR === 'QS' ? '（斗数全书）' : ''}　闰月 ${LEAP}　晚子时 ${ZI}　辛年魁钺 ${KY}　四化表 庚=阳武阴同`);
notes.forEach(n => out.push('· ' + n)); warns.forEach(w => out.push('⚠ ' + w));

out.push('\n【十二宫】（从命宫逆排；主星括号为亮度，[化X] 为生年四化）');
for (let i = 0; i < 12; i++) {
  const p = byB((chart.mingGongBranch - i + 12) % 12);
  const major = p.stars.filter(s => s.type === 'major').map(fmt).join(' ');
  const aux = p.stars.filter(s => SIX.includes(s.name)).map(fmt).join(' ');
  const misc = p.stars.filter(s => s.type !== 'major' && !SIX.includes(s.name)).map(s => s.name + (s.siHua ? `[化${s.siHua}]` : '')).join(' ');
  const tag = (p.isShenGong ? '·身' : '') + (p.isCurrentDaXian ? '·当前大限' : '');
  out.push(`${p.name}${tag}　${pillar(p.stem, p.branch)}　大限${p.daXianAge?.join('-') ?? '—'}`);
  out.push(`　主星：${major || `空宫，借对宫（${p.borrowedFromName}）${p.borrowedStars?.join(' ')}`}`);
  out.push(`　六吉六煞禄马：${aux || '—'}`);
  out.push(`　杂曜：${misc || '—'}`);
}

const sq = [0, 8, 4, 6].map(o => byB((chart.mingGongBranch + o) % 12)); // 命、财帛、官禄、迁移
out.push('\n【命宫三方四正】' + sq.map(p => { const st = p.stars.filter(s => s.type === 'major' || SIX.includes(s.name)).map(fmt).join(' '); return `${p.name}：${p.stars.some(s => s.type === 'major') ? st : `无主星（借${p.borrowedStars?.join(' ') ?? '对宫'}）${st ? ' ' + st : ''}`}`; }).join('｜'));
out.push('\n【生年四化】' + `${STEMS[L.yearStem]}干　` + fly(L.yearStem));

out.push('\n【宫干四化】（飞星派参考；◎=离心自化，本宫宫干化本宫的星；⇄=化入对宫，对宫那颗星得向心自化）');
for (let i = 0; i < 12; i++) {
  const p = byB((chart.mingGongBranch - i + 12) % 12);
  const parts = Object.entries(huaOf(p.stem)).map(([h, s]) => { const t = starPal(s); return `${h}→${t?.name ?? '?'}${t?.branch === p.branch ? '◎' : t?.branch === (p.branch + 6) % 12 ? '⇄' : ''}`; });
  out.push(`${p.name}(${STEMS[p.stem]})　${parts.join('　')}`);
}
const laiyin = P.filter(p => p.stem === L.yearStem && p.branch >= 2).map(p => p.name);
out.push(`来因宫（四化派通行定义：宫干同生年天干；壬年寅子同干取寅，辛年卯丑同干取卯）：${laiyin.join('、') || '—'}`);

// ── 财富专题数据（四化派口径，供「财富专题」一节用；只列盘面事实，不下判断） ──
const opp = (p: any) => byB((p.branch + 6) % 12);
const liXin = (p: any) => Object.entries(huaOf(p.stem)).filter(([, s]) => starPal(s)?.branch === p.branch).map(([h, s]) => `${s}自化${h}`);
const xiangXin = (p: any) => Object.entries(huaOf(opp(p).stem)).filter(([, s]) => starPal(s)?.branch === p.branch).map(([h, s]) => `${s}化${h}`);
const natal = (p: any) => p.stars.filter((s: any) => s.siHua).map((s: any) => `${s.name}化${s.siHua}`);
const has = (p: any, ns: string[]) => p.stars.filter((s: any) => ns.includes(s.name)).map((s: any) => s.name);
const KJ = ['地空', '地劫'], SHA4 = ['擎羊', '陀罗', '火星', '铃星'], or0 = (a: string[]) => a.join('、') || '无';
const luP = P.find(p => p.stars.some(s => s.siHua === '禄'))!, jiP = P.find(p => p.stars.some(s => s.siHua === '忌'))!, cunP = starPal('禄存')!;
const INNER = ['命宫', '财帛', '官禄', '田宅', '疾厄', '福德'], nei = (n: string) => INNER.includes(n) ? '六内宫' : '六外宫';
const NAMES12 = Array.from({ length: 12 }, (_, i) => nm((chart.mingGongBranch - i + 12) % 12)), dxn = (d: number, b: number) => NAMES12[(d - b + 12) % 12];
const roles = new Map<number, string[]>();
const add = (p: any, r: string) => roles.set(p.branch, [...(roles.get(p.branch) ?? []), r]);
add(luP, '生年禄所在'); add(cunP, '禄存所在');
for (const [n, r] of [['兄弟', '手头资金位'], ['田宅', '储蓄置业位'], ['父母', '长辈位'], ['命宫', ''], ['福德', '']]) add(P.find(p => p.name === n)!, r);
out.push('\n【财富专题数据】（四化派口径；离心自化=本宫宫干化本宫星，向心自化=对宫宫干化本宫星；只列事实）');
out.push(`生年禄：${luP.stars.find(s => s.siHua === '禄')!.name}化禄在${luP.name}（${nei(luP.name)}）　禄存在${cunP.name}　生年忌：${jiP.stars.find(s => s.siHua === '忌')!.name}化忌在${jiP.name}（${nei(jiP.name)}）${opp(luP).branch === jiP.branch ? '，正在生年禄对宫' : luP.branch === jiP.branch ? '，与生年禄同宫' : ''}`);
for (const [b, rs] of roles) {
  const p = byB(b), o = opp(p), mj = p.stars.filter(s => s.type === 'major').map(fmt).join(' ');
  out.push(`${p.name} ${pillar(p.stem, p.branch)}〔${rs.filter(Boolean).join('·') || '—'}〕`);
  out.push(`　主星 ${mj || '无（空宫）'}｜生年四化 ${or0(natal(p))}｜离心自化 ${or0(liXin(p))}｜向心自化 ${or0(xiangXin(p))}｜空劫 ${or0(has(p, KJ))}｜羊陀火铃 ${or0(has(p, SHA4))}`);
  out.push(`　对宫${o.name}：生年四化 ${or0(natal(o))}｜离心自化 ${or0(liXin(o))}｜空劫 ${or0(has(o, KJ))}`);
}
const tally = (f: (p: any) => string[]) => ['禄', '权', '科', '忌'].map(h => { const ps = P.filter(p => f(p).some(x => x.endsWith('化' + h))).map(p => p.name); return `${h}${ps.length}${ps.length ? '（' + ps.join('、') + '）' : ''}`; }).join('　');
out.push(`全盘离心自化（按宫计）：${tally(liXin)}`);
out.push(`全盘向心自化（按得化的宫计）：${tally(xiangXin)}`);

// ── 时间层级（流年、流月、流日）用的换算；只算落宫和四化，不下判断 ──
const bMonth = ((starPal('左辅')!.branch - 4 + 12) % 12) + 1;  // 安星所用的生月：左辅从辰宫起正月顺数
const douJun = (yb: number) => (((yb - (bMonth - 1) + hour) % 12) + 12) % 12;  // 流年斗君：流年支上起正月逆数到生月，再起子时顺数到生时
const yrOf = (Y: number) => ({ yb: (((Y - 4) % 12) + 12) % 12, ys: (((Y - 4) % 10) + 10) % 10 });
const mOf = (ys: number, yb: number, M: number) => ({ mB: (douJun(yb) + M - 1) % 12, mS: ((ys % 5) * 2 + 2 + M - 1) % 10, mZ: (M + 1) % 12 });  // 流月命宫从斗君顺数；月干按五虎遁配农历月
const flyRel = (stem: number, lv: [string, number][]) => Object.entries(huaOf(stem)).map(([h, s]) => { const t = starPal(s); return `${s}化${h}→${t ? `${t.name}（${lv.map(([n, mb]) => n + dxn(mb, t.branch)).join('·')}）` : '?'}`; }).join('　');
const mjOf = (p: any) => p.stars.some((s: any) => s.type === 'major') ? p.stars.filter((s: any) => s.type === 'major').map(fmt).join(' ') : `空宫（借${p.borrowedStars?.join(' ') ?? '对宫'}）`;
const CN = ['正', '二', '三', '四', '五', '六', '七', '八', '九', '十', '冬', '腊'];
const dxOf = (age: number) => { const dx = chart.daXians.find(x => age >= x.startAge && age <= x.endAge); return dx ? `${dx.startAge}-${dx.endAge} ${nm(dx.palaceBranch)}` : '童限或超出'; };

const pats = detectPatterns(chart);
out.push('\n【格局检测】（引擎规则库，三合派口径；只列命中，非定论）');
const LV: Record<string, string> = { excellent: '上', good: '中', neutral: '平', caution: '忌' };
if (!pats.length) out.push('无命中');
pats.forEach(pt => {
  out.push(`· ${pt.name}［${LV[pt.level] ?? pt.level}］ 涉及：${pt.palaces.join('、')}${pt.source ? '　出处：' + pt.source : ''}`);
  const c = pt.conditions; if (c) { if (c.required?.length) out.push('　成格：' + c.required.join('；')); if (c.bonus?.length) out.push('　加分：' + c.bonus.join('；')); if (c.breaking?.length) out.push('　破格：' + c.breaking.join('；')); }
});

out.push('\n【大限】（虚岁；起止年为农历年；大限四化按大限宫干，飞星/四化派用，倪师派不用）');
chart.daXians.forEach(dx => {
  const p = byB(dx.palaceBranch), y0 = L.lunarYear + dx.startAge - 1;
  out.push(`${dx.startAge}-${dx.endAge}岁（${y0}-${y0 + dx.endAge - dx.startAge}）${p.name} ${pillar(p.stem, p.branch)}${p.isCurrentDaXian ? ' ◀当前' : ''}\n　三方四正（本命宫名）：${sfsz(p.branch)}\n　大限四化：${fly(p.stem)}\n　禄忌落大限宫：生年禄在大限${dxn(p.branch, luP.branch)}　禄存在大限${dxn(p.branch, cunP.branch)}　生年忌在大限${dxn(p.branch, jiP.branch)}（${nei(dxn(p.branch, jiP.branch))}）\n　大限命宫主星：${mjOf(p)}　大限福德在本命${nm((p.branch + 2) % 12)}：${mjOf(byB((p.branch + 2) % 12))}`);
});
if (chart.daXians[0]?.startAge > 1) out.push(`童限：1-${chart.daXians[0].startAge - 1}岁`);

const years = (A.year ?? String(new Date().getFullYear())).split(',').map(Number);
const xxStart: Record<number, number> = { 2: 4, 6: 4, 10: 4, 8: 10, 0: 10, 4: 10, 5: 7, 9: 7, 1: 7, 11: 1, 3: 1, 7: 1 };
out.push('\n【流年】（流年命宫=太岁宫，即流年地支所在宫；小限=倪师所称「流年」，按生年支起、男顺女逆）');
for (const Y of years) {
  const age = Y - L.lunarYear + 1, yb = ((Y - 4) % 12 + 12) % 12, ys = ((Y - 4) % 10 + 10) % 10;
  const dx = chart.daXians.find(x => age >= x.startAge && age <= x.endAge);
  const xx = (xxStart[L.yearBranch] + (gender === 'male' ? 1 : -1) * (age - 1) + 1200) % 12;
  out.push(`${Y} ${pillar(ys, yb)}年　虚岁${age}　所属大限：${dx ? `${dx.startAge}-${dx.endAge} ${nm(dx.palaceBranch)}` : '童限或超出'}`);
  out.push(`　流年命宫（太岁宫）在本命${nm(yb)}（${BRANCHES[yb]}），${sfsz(yb)}`);
  out.push(`　小限在本命${nm(xx)}（${BRANCHES[xx]}），对宫${nm((xx + 6) % 12)}`);
  out.push(`　流年干四化（飞星/四化派用；倪师派四化不动；括号里是落在流年的哪一宫）：${flyRel(ys, [['流年', yb]])}`);
  out.push(`　流年斗君（正月所在宫）在本命${nm(douJun(yb))}（${BRANCHES[douJun(yb)]}）；逐月用 --months ${Y}，某一天用 --day YYYY-MM-DD`);
}
for (const Y of (A.months ? A.months.split(',').map(Number) : [])) {
  if (!Number.isInteger(Y) || Y < 1900 || Y > 2100) die(`--months 要给 1900–2100 的年份（农历年），收到「${A.months}」`);
  const { yb, ys } = yrOf(Y), leapM = LunarYear.fromYear(Y).getLeapMonth();
  out.push(`\n【流月一览】${Y} ${pillar(ys, yb)}年（农历年）　虚岁${Y - L.lunarYear + 1}　所属大限：${dxOf(Y - L.lunarYear + 1)}`);
  out.push(`　流年命宫在本命${nm(yb)}（${BRANCHES[yb]}）　流年斗君在本命${nm(douJun(yb))}（${BRANCHES[douJun(yb)]}）　流年干四化：${flyRel(ys, [['流年', yb]])}`);
  for (let M = 1; M <= 12; M++) {
    const { mB, mS, mZ } = mOf(ys, yb, M);
    out.push(`${CN[M - 1]}月 ${pillar(mS, mZ)}（公历 ${Lunar.fromYmd(Y, M, 1).getSolar().toYmd()} 起）　流月命宫在本命${nm(mB)}（${BRANCHES[mB]}）`);
    out.push(`　月干四化：${flyRel(mS, [['流月', mB]])}`);
    out.push(`　流年四化落在流月：${Object.entries(huaOf(ys)).map(([h, s]) => `${h}→流月${dxn(mB, starPal(s)!.branch)}`).join('　')}　生年禄在流月${dxn(mB, luP.branch)}　生年忌在流月${dxn(mB, jiP.branch)}`);
    if (leapM === M) out.push(`　⚠ 本年有闰${CN[M - 1]}月（公历 ${Lunar.fromYmd(Y, -M, 1).getSolar().toYmd()} 起）：闰月算哪个流月，各软件处理不一，脚本按${CN[M - 1]}月算，未核`);
  }
}
for (const ds of (A.day ? A.day.split(',') : [])) {
  const [ty, tm, td] = ymd(ds, '--day'), pd2 = new Date(Date.UTC(ty, tm - 1, td));
  if (pd2.getUTCMonth() !== tm - 1 || pd2.getUTCDate() !== td) die(`公历 ${ds} 这一天不存在`);
  const tl = Solar.fromYmd(ty, tm, td).getLunar(), Y = tl.getYear(), leap = tl.getMonth() < 0, M = Math.abs(tl.getMonth()), D = tl.getDay();
  if (Y < 1900 || Y > 2100) die(`--day 只支持 1900–2100 年，收到 ${ds}`);
  const { yb, ys } = yrOf(Y), { mB, mS, mZ } = mOf(ys, yb, M), dB = (mB + D - 1) % 12, dgz = tl.getDayInGanZhi(), dS = STEMS.indexOf(dgz[0]);
  out.push(`\n【流月流日】公历 ${ty}-${tm}-${td}　农历 ${pillar(ys, yb)}年${leap ? '闰' : ''}${CN[M - 1]}月${D}日　${dgz}日　虚岁${Y - L.lunarYear + 1}　所属大限：${dxOf(Y - L.lunarYear + 1)}`);
  if (leap) out.push(`⚠ 这一天在闰${CN[M - 1]}月：闰月算哪个流月，各软件处理不一，脚本按${CN[M - 1]}月算，未核`);
  const tiso = `${ty}-${String(tm).padStart(2, '0')}-${String(td).padStart(2, '0')}`;
  if (DISPUTE.some(([a, b]) => tiso >= a && tiso <= b)) out.push('⚠ 这一天落在两套农历表相差一天的区间，流日可能差一宫');
  out.push(`　流年命宫在本命${nm(yb)}（${BRANCHES[yb]}）　流月（${pillar(mS, mZ)}月）命宫在本命${nm(mB)}（${BRANCHES[mB]}）　流日命宫在本命${nm(dB)}（${BRANCHES[dB]}）`);
  out.push(`　流年干${STEMS[ys]}：${flyRel(ys, [['流年', yb], ['流月', mB], ['流日', dB]])}`);
  out.push(`　流月干${STEMS[mS]}：${flyRel(mS, [['流月', mB], ['流日', dB]])}`);
  out.push(`　流日干${STEMS[dS]}：${flyRel(dS, [['流日', dB]])}`);
  const marks = (b: number, withDay: boolean) => { const hs = (stem: number, tag: string) => Object.entries(huaOf(stem)).filter(([, s]) => starPal(s)?.branch === b).map(([h, s]) => `${tag}${s}化${h}`); return [...natal(byB(b)).map(x => '生年' + x), ...hs(ys, '流年'), ...hs(mS, '流月'), ...(withDay ? hs(dS, '流日') : [])]; };
  for (const [lab, mb, wd] of [['流月', mB, false], ['流日', dB, true]] as [string, number, boolean][]) {
    out.push(`　${lab}十二宫（${lab}宫名＝本命宫｜主星｜落在这一宫的四化；空劫羊陀火铃）`);
    for (let i = 0; i < 12; i++) { const p = byB((mb - i + 12) % 12); out.push(`　　${NAMES12[i]}＝本命${p.name}｜${mjOf(p)}｜${or0(marks(p.branch, wd))}；${or0([...has(p, KJ), ...has(p, SHA4)])}`); }
  }
}
if (A.json) console.log(JSON.stringify({ chart, patterns: pats, notes, warns }, null, 1)); else console.log(out.join('\n'));
ZWEOF
```
