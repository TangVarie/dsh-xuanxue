> 本文件是 `vedic` skill 的 **calculator** 模块。文中相对路径（resources/、scripts/）以本模块目录 `calculator/` 为根；跨模块引用写作 `<模块>/...` 或「<模块> 模块」，指本 skill 下的同名目录，调用方式见根目录 SKILL.md。

# calculator 模块: 吠陀占星排盘引擎

一次计算，同时写出 `chart_data.json`（脚本读）与 `structured_data.md`（阅读版）。产物分工、缺失值、精度、版本标识、检查状态的正本是 `shared/data_contract.md`。

## 前置条件

- Python 3.8 ~ 3.13（pysweph 为 C 扩展，**3.14 暂不支持**）
- 依赖: pysweph, PyJHora==4.8.6, pytz

> ⚠️ **不要直接 `pip install -r requirements.txt`！** PyJHora 未声明其运行时依赖，且 pip 包缺少 .se1 星历文件。
> 请使用 `setup_env.py` 自动安装（见下方）。

### 环境自动检测

```
运行前检查依赖是否可用（按优先级）：

  1. 已有 venv（check_env.py 按此顺序找）：
     - <calculator 目录>/venv/
     - <工作目录>/vedic-calc-env/
     - <工作目录>/venv/
     找到 → 用其 Python 运行 → 尝试 import swisseph → 成功 → 直接使用

  2. 尝试当前 Python import swisseph：
     - 成功且 swe.version 不是 '0.0.0' → 直接使用
     - 失败或空壳 → 继续

  3. 创建 venv（skill 目录通常只读，建在工作目录）：
     <合适的Python> calculator/scripts/setup_env.py --target <工作目录>/vedic-calc-env
     脚本会自动：检测 Python 版本 → 创建 venv → 按正确顺序安装 → 验证 SAV=337
```

> ⚠️ 如果系统默认 Python 是 3.14，setup_env.py 会自动查找 3.12/3.13 来创建 venv。

### ⚠️ 首次使用必须先跑环境诊断

```
python calculator/scripts/check_env.py

自动检查：venv 位置和 Python 版本、3 个核心依赖、swisseph 空壳、星历表文件、最小计算测试（SAV=337）
输出 🎉 → 直接使用它报告的 Python 路径
输出 ⚠️ → 按提示运行 setup_env.py 修复
check_env.py 本身可以用任何 Python 版本运行（包括 3.14），它会自动找到正确的 venv Python。
```

下文的 `python` 都指 check_env.py 报告的那个解释器。

## 使用流程

### Step 1: 收集出生信息（只问一次）

缺什么问什么，合成一条消息；用户已经给过的直接复用。由 reader 进入时，reader Step 3 已经问过的不再问。

```
- 出生日期 (YYYY-MM-DD)、出生时间 (HH:MM，24小时制)、出生地点 (城市名)
- 时间来源：出生证 / 医院记录 / 家人明确记忆 / 家人记忆 / 本人记忆 / 模糊记忆 / 未追问 / 未知
- 误差（可选）：用户自己说的范围，如"前后一刻钟"；没说就是未声明
- 性别、感情状态（可选）
```

⚠️ 夏令时确认（出生日期落在当地夏令时期间时必做，如中国大陆 1986-1991 每年4月中~9月中）：
```
向用户输出一句确认（默认=当地钟表时间，绝大多数记录是当时钟表显示的时间）：
"您出生时当地正实行夏令时。您提供的时间是当时钟表显示的时间吗？（通常是，直接回'是'即可）
 若家里记录的是未拨快的'标准时/北京时间'，请说明。"
→ 当地钟表时间（默认）→ 正常排盘，pytz 按夏令时换算 UTC
→ 用户声明标准时 → 加 --clock-type 标准时：时区仍用 IANA 名（如 Asia/Shanghai），
   脚本把报时换成当地钟表时间再算，并在元信息「出生时间」「精度说明」写明换算
   （标准时 23:00 以后换算会跨到次日，元信息的出生日期同时写出计算用日期与用户报的日期）
```

夏令时切换当天的两种情况（脚本会直接报出来，按提示处理，不要自己加减一小时）：
- 钟表时刻不存在（夏令时开始，钟表拨快跳过的那一小时）：多半记录的是标准时 → 向用户确认后加 `--clock-type 标准时`。
- 钟表时刻出现两次（夏令时结束，钟表拨回重复的那一小时）：问用户是拨回前还是拨回后，加 `--repeated-hour 夏令时` 或 `--repeated-hour 标准时`。两次相差一小时，是两张不同的盘（chart_id 不同）；用户分不清时两张都排，按 reader 的双 Lagna 对比或 rectifier 处理。

### Step 2: 地理坐标与时区

根据用户提供的城市名填写纬度、经度、IANA 时区名：

```
北京:     39.9042, 116.4074, "Asia/Shanghai"
上海:     31.2304, 121.4737, "Asia/Shanghai"
广州:     23.1291, 113.2644, "Asia/Shanghai"
成都:     30.5728, 104.0668, "Asia/Shanghai"
重庆:     29.5630, 106.5516, "Asia/Shanghai"
深圳:     22.5431, 114.0579, "Asia/Shanghai"
杭州:     30.2741, 120.1551, "Asia/Shanghai"
南京:     32.0603, 118.7969, "Asia/Shanghai"
武汉:     30.5928, 114.3055, "Asia/Shanghai"
西安:     34.3416, 108.9398, "Asia/Shanghai"
天津:     39.3434, 117.3616, "Asia/Shanghai"
台北:     25.0330, 121.5654, "Asia/Taipei"
香港:     22.3193, 114.1694, "Asia/Hong_Kong"
新德里:   28.6139, 77.2090,  "Asia/Kolkata"
孟买:     19.0760, 72.8777,  "Asia/Kolkata"
```

> 表里没有的城市：用该城市市区的经纬度（保留 4 位小数），时区用 IANA 名；地点只到省或县时问一次具体城市，用户不知道就用县/市政府所在地，并在 --place 注明。
> ⚠️ 中国全境使用 "Asia/Shanghai" (UTC+8)
> ⚠️ 印度全境使用 "Asia/Kolkata" (UTC+5:30)

### Step 3: 运行 build_chart.py

#### 完整盘

```bash
python calculator/scripts/build_chart.py --date YYYY-MM-DD --time HH:MM --tz <IANA时区> \
    --lat <纬度> --lon <经度> --place <地名> --source <时间来源> \
    [--declared-min N] [--declared-text "用户原话"] [--clock-type 标准时] [--repeated-hour 夏令时|标准时] \
    [--gender 男|女] [--relationship <感情状态>] --out <工作目录>
```

| 参数 | 说明 |
|---|---|
| `--time` | 用户报的时间，按 `--clock-type` 解释 |
| `--tz` | IANA 时区名 |
| `--source` | 时间来源，取值见 Step 1；不在表内按 ±15 分钟保守处理；不传记为「未追问」 |
| `--declared-min` | 用户声明的误差（分钟）。不传 = 未声明，按来源下限 |
| `--declared-text` | 用户原话，写进元信息「声明精度」；知道记录时刻语义（啼哭/分娩/断脐/事后录入）时一并写上 |
| `--clock-type` | `当地钟表时间`（默认）/ `标准时` |
| `--repeated-hour` | 只在钟表时刻落在夏令时结束当晚的重复时段时用：`夏令时`（拨回前）/ `标准时`（拨回后） |
| `--lat` / `--lon` | 纬度在前、经度在后（西经、南纬为负）。纬度超出 ±90 直接拒绝；经度与时区的中央经线相差 50° 以上会提示核对是否传反 |
| `--gender` / `--relationship` | 写进「用户信息」；不传标「未提供」 |
| `--no-transit` | 不算过运（行运能力标「未计算」） |
| `--transit-date` | 过运快照取指定日期（当地正午）；缺省为现在。复现或查询指定日期时用 |

精度与审计范围（正本 `shared/data_contract.md` §4）：
- 有效误差 = max(`--declared-min`, 来源下限)。来源下限：出生证/医院记录 ±1；家人明确记忆/家人记忆 ±5；本人记忆/模糊记忆/未追问/未知 ±15；校时（rectifier 写回）±1，且必须给 `--declared-min` 与 `--original-source`。
- 分盘边界审计范围自动等于有效误差（逐分钟扫描 D1/D9/D10/D4/D5 Lagna），不另传、不手改；`check_chart.py` 核对两者一致。
- 元信息写出：出生时区与 UTC 偏移、钟表时间性质、时间来源、声明精度、有效精度、实际审计范围、精度说明、数据版本（chart_id / audit_id）。没有声明误差写「未声明」，不写成「±分钟级」。
- 验前事命中不收窄误差；收窄只能靠更可靠的来源或 rectifier。

产物：同一次计算写出 `chart_data.json` 与 `structured_data.md`，两者 chart_id 相同。不要自己写 Python 调 engine/formatter，也不要手改 md 表格或用 print 读 chart 数据。

退出码：0 写出且自检通过 / 1 文件已写出但自检有失败项（按 Step 4 处理）/ 2 参数或计算错误（未写出）。
退出码 2 时看第一行：「输入有误」= 日期/时间格式、时区名、经纬度范围、夏令时切换时段、校时缺 `--original-source` 这类输入问题，按提示改参数或问用户；「计算失败」= 环境或引擎问题，先跑 `check_env.py`。

出生日期、时间、地点、时区、钟表时间性质任一变化 → 先 `python shared/scripts/archive_chart.py --dir <工作目录> --reason "<原因>"` 归档旧盘产物，再用完整参数重排，得到新 chart_id（`shared/versioning.md` §3）。只补性别或感情状态时用同样的出生参数重跑，chart_id 不变（之前合并过 PDF Shadbala 的，重跑后再合并一次）。

#### 仅日期模式（`--date-only`）

```bash
python calculator/scripts/build_chart.py --date-only --date YYYY-MM-DD --tz <IANA时区> \
    --lat <纬度> --lon <经度> [--place <地名>] --out <目录>
```

- 用于合盘一方只有出生日期，或本人暂时没有出生时间
- 当地 00:00-23:59 每 30 分钟采样，全天同一星座/宿才给出，否则标「未计算」；Moon 不给度数
- 上升、宫位、宫主、分盘、Dasha、Karaka 标「不适用 / 未计算」，没有过运宫位
- 不得为了通过自检补一个出生时刻（`shared/data_contract.md` §6）；后续能做什么见 `shared/capabilities.md` §1

#### 从 chart_data.json 重新生成 md（`--from-json`）

```bash
python calculator/scripts/build_chart.py --from-json <目录>/chart_data.json
```

只从已有 JSON 重写 `structured_data.md`，不重新计算，chart_id 不变。用于 build_chart 排出的盘需要重出阅读版时。`merge_shadbala.py` 合并后已自动重新生成 md，不必再跑。旧版导入的 JSON 不要用它（导入的 md 由 `import_legacy_md.py` 直接写出）。

#### 旧盘导入（`import_legacy_md.py`）

```bash
python calculator/scripts/import_legacy_md.py --file <旧 structured_data.md 或提取稿> --out <目录> [--tz <IANA时区>]
```

- 把旧版（v4/v5.0）或 reader 提取稿格式的 Markdown 读成 `chart_data.json`；能解析的表照原值导入，旧文件没有的表一律「未计算」，不补成已验证
- 旧版「✅ 可信（直接计算）」不算边界审计，分盘审计标「未计算」；旧的「±分钟级」缺省写法改写为「未声明」
- 旧文件里的「盘面初验结果 / 验前事校准率 / 生时矫正记录 / 信号修正日志」迁到 `verification_record.md`（绑定导入后的 chart_id，未按 5.1 评分重算）；原文件另存为 `structured_data.legacy.md`
- 出生日期、时间、地点齐全且环境可用时，导入后改用完整盘重排更好；导入只是过渡。重排前先 `shared/scripts/archive_chart.py` 把导入的数据、迁出的旧反馈与旧版原文归档（重排多半得到新 chart_id）

#### PDF Shadbala 合并（`merge_shadbala.py`）

```bash
python calculator/scripts/merge_shadbala.py --chart <目录>/chart_data.json --pdf-data shadbala_pdf.json
```

PDF 数据文件格式：
```json
{"source": "JHora PDF p.3", "birth": "1990-05-21 14:23",
 "rows": {"Sun": {"total_rupas": 7.80}, "Mars": {"total_rupas": 6.1, "strength_pct": 122.0}}}
```

- `birth` 必须等于 `chart_data.json` 的出生日期与计算用时间（input.date + input.time_used），否则拒绝；校时改了时间后旧 PDF 作废
- 只改 PDF 里出现的行：每行保留 calc 原值、采用值、来源；PDF 没有的行保持 calc，禁止整表覆盖
- `strength_pct` 缺省时按 BPHS 必需值换算；PDF 给了 `ishta_phala` / `kashta_phala` 就一并采用，没给的保持 calc；「calc基准」列保留被替换的原计算值
- 合并后自动重新生成 `structured_data.md`；有差异的行星在聊天里点名
- 退出码：0 合并完成 / 1 拒绝合并 / 2 参数错误

### Step 4: 检查输出

```bash
python calculator/scripts/check_chart.py --dir <工作目录>
python calculator/scripts/dasha_query.py --file <工作目录>/structured_data.md --check
```

结果只有三种状态（正本 `shared/data_contract.md` §7）：

| 状态 | 含义 | 后续 |
|---|---|---|
| 通过 | 必需内容齐全，检查成立 | 执行对应分析 |
| 失败 | 明确错误或内部矛盾 | 修复受影响部分（多为输入、时区、钟表时间性质）后重排再用 |
| 未完成 | 缺数据、未执行或无可比较事实 | 只限制对应能力，其余照常 |

退出码统一：0 通过 / 1 失败 / 2 未完成。

- `check_chart.py` 检查：两份产物的字段合法性、计算数据不含反馈信息、两份产物同源（chart_id）、精度声明与审计范围一致、分盘声明与审计结果一致、Vimsottari MD/AD/PD 层级、Karaka 7K/8K 对照、过运快照，并给出能力范围。
- `dasha_query.py --check` 逐层检查 MD/AD/PD 的数量、行星名、顺序、父子归属与边界；能力映射：MD → 背景趋势，AD → 阶段窗口，PD → 月级窗口，上层未通过时下层最多「未完成」。
- `structured_data.md` 自带「校验结果」（17 项自检）与「能力范围」两节，可直接引用。

分盘消费（正本 `shared/divisional.md` §1）：
- `✅ 审计区间内稳定`：对应分盘可按当前 Lagna 正常使用
- `⚠️ 边界敏感`：保留给定时刻的计算表，分盘宫位、内部宫主和下游形态结论条件化或降级
- 旧数据缺边界审计：「未审计」，不得补写成高可信
- 出生证来源与"直接计算"都不等于分盘在误差内稳定；出生证未写明记录时刻语义时，时刻语义仍未知

时间分辨率（正本 `shared/time_window.md` §1）：只读 MD 只出背景趋势；MD×AD 最多出阶段窗口；月份或窄于 AD 的窗口必须读 PD；PD 未通过检查时停止月级判定，禁止用 AD 或 365.25 天近似。

### Step 4.5: 三级运渐进读取（不改canonical数据）

排盘仍一次性计算、校验并写入完整 `9 MD + 81 AD + 729 PD`。渐进读取只优化下游模型上下文，不删数据、不少算、不改时间线。下游一律按三层消费：MD 定背景 → AD 定领域候选与事件阶段 → PD 只在用户要求月/日、实际输出窄于完整 AD、或相邻 AD/PD 接力会改变结论时读取。

禁止默认把 729 行 PD 整表送入模型上下文。使用确定性工具（同目录有 chart_id 一致的 `chart_data.json` 时脚本优先读它）：

```bash
# 默认读盘：输出全部非PD数据与MD/AD，折叠729行PD
python calculator/scripts/dasha_query.py --file structured_data.md --overview

# 层级检查：只输出结果，不展开PD
python calculator/scripts/dasha_query.py --file structured_data.md --check

# 月级下钻：只返回命中的PD与相邻上下文
python calculator/scripts/dasha_query.py --file structured_data.md --month 2023-06 --context 1

# 日级或自定义[start,end)窗口
python calculator/scripts/dasha_query.py --file structured_data.md --date 2023-06-15 --context 1
python calculator/scripts/dasha_query.py --file structured_data.md --start 2023-05-01 --end 2023-07-01 --context 1
```

候选比较的规则（全部候选先在 MD/AD 层锁定，再统一下钻 PD）见 `shared/time_window.md` §1。

### Step 5: 排盘完成后

在聊天里简短报告：chart_id、检查结果（通过 / 未完成 / 失败各几项，未完成的是什么）、有效精度与审计范围、能力范围里受限的部分。Shadbala 默认是 calc 值；用户若有同一出生时刻的 JHora PDF，可以发来按 Step 3 合并。

然后按用户已经说明的目的直接继续，不弹选择菜单：
- 用户要完整分析 → 进 reader 做验前事（reader 在 Calc 模式下跳过提取，直接读数据），之后进 core
- 用户直接点名某个专题、合盘或时机 → 不先插入验前事，按根 SKILL.md 的路由直接进对应模块；结尾可用一句话提示"可以做一轮验前事核对盘面"
- 用户只要排盘 → 停在这里，补一句"接下来可以做验前事和完整分析，或直接问某个方面"
- 用户发来 PDF → 核对出生信息一致 → 从 PDF 文本层提取 Shadbala → `merge_shadbala.py`；其余 PDF 数据只做交叉验证（由 reader 记录差异）

排盘完成时不主动提示任何导出选项。用户明确提出"小火人资料""可复制资料""关系资料"或类似请求时，才进入导出分支：
- 保留已生成的 `structured_data.md` 不变，运行 `python calculator/scripts/make_xiaohuo_person_card.py structured_data.md`，把 stdout 返回的一段 `xiaohuo-person-v1` 纯文字直接发给用户；不生成图片，不要求用户打开或理解文件，也不把资料卡当作新的排盘结果。
- 双人使用时，两个人分别排盘、分别生成一段个人资料，再在双人对话中标为 A/B 粘贴。
- 导出包含明确的 `Lagna`、当前 MD/AD/PD 和带日期的慢行星过运快照；导出器不调用星历，也不把旧快照改成今天。用户要求真实当日过运且源文件日期已过期时，先 `python calculator/scripts/transit.py --chart chart_data.json --write` 刷新过运快照（会重新生成 structured_data.md），再导出；不得只重跑导出器或手改日期。


## engine 返回数据结构（脚本开发参考）

> 日常排盘只用 `build_chart.py`，不要直接调 engine。本节供修改脚本时查 key 名；`chart_data.json` 的 `chart` 字段就是这份结构（JSON 化后整数键变成字符串，缺失项用 `{"_missing": 状态, "reason": …}`）。

```python
chart = {
    # 基础天文
    'ayanamsa': 23.8982,           # float, True Chitra ayanamsa 度数（约23.9°，与Lahiri差<1′）
    'lagna': {
        'sign': 'Cancer',          # str, 英文星座名
        'sign_idx': 3,             # int, 0-indexed (Aries=0)
        'degree': 13.61,           # float, 绝对度数 (星座内)
        'deg_str': "13°36'",       # str, 格式化度分
        'longitude': 103.61,       # float, 黄道经度
        'nakshatra': {'name': 'Pushya', 'pada': 4, 'lord': 'Saturn'}
    },
    'planets': {
        'Sun': {
            'sign': 'Scorpio', 'sign_idx': 7,
            'degree': 25.41, 'deg_str': "25°24'",
            'longitude': 235.41,
            'house': 5,            # int, 1-indexed 从 Lagna 数
            'retrograde': False,
            'nakshatra': {'name': 'Jyeshtha', 'pada': 3, 'lord': 'Mercury'}
        },
        # ... Moon, Mars, Mercury, Jupiter, Venus, Saturn, Rahu, Ketu 同结构
    },

    # SAV — ⚠️ key 是英文星座名，不是 'by_sign'!
    'sav': {
        'Aries': 36, 'Taurus': 34, 'Gemini': 22, 'Cancer': 28,
        'Leo': 34, 'Virgo': 29, 'Libra': 29, 'Scorpio': 25,
        'Sagittarius': 32, 'Capricorn': 20, 'Aquarius': 26, 'Pisces': 22
    },
    'sav_by_house': {
        1: {'sign': 'Cancer', 'value': 28},  # 按宫位编号
        # ... 2-12 同结构
    },

    # BAV
    'bav': {
        'Sun': {'Aries': 6, 'Taurus': 5, ...},  # 12星座
        # ... Moon, Mars, Mercury, Jupiter, Venus, Saturn
    },

    # Shadbala — ⚠️ 用 strength_pct (不是 strength_ratio)!
    'shadbala': {
        'Sun': {
            'total_60ths': 288.6,  'total_rupas': 4.81,
            'sthana': 82.0, 'kaala': 55.0, 'dig': 6.7,
            'cheshta': 44.9, 'naisargika': 60.0, 'drik': 40.0,
            'strength_pct': 96.2,  # ⚠️ 百分比，直接用！
            'classification': '弱',
            'ishta_phala': 7.64,   # Ishta Phala
            'kashta_phala': 50.18  # Kashta Phala
        },
        # ... Moon, Mars, Mercury, Jupiter, Venus, Saturn 同结构
    },

    # Dasha
    'dashas': [
        {
            'planet': 'Jupiter', 'start': '1998-02', 'end': '2014-02',
            'years': 16, 'is_current': False,
            'antardashas': [
                {
                    'planet': 'Jupiter',
                    'start': '1998-02-11', 'end': '2000-04-01',
                    'start_time': '1998-02-11 12:34', 'end_time': '2000-04-01 08:20',
                    'is_current': False,
                    'pratyantardashas': [
                        {
                            'planet': 'Jupiter',
                            'start': '1998-02-11', 'end': '1998-05-26',
                            'start_time': '1998-02-11 12:34', 'end_time': '1998-05-26 04:15',
                            'is_current': False
                        },
                        # ... 每个AD共9个PD
                    ]
                },
                # ... 9个小运
            ]
        },
        # ... 共9段大运
    ],

    # 分盘 — (sign_name, sign_idx) tuple
    'd9':  {'Lagna': ('Scorpio', 7), 'Sun': ('Aquarius', 10), ...},
    'd10': {'Lagna': ('Cancer', 3),  'Sun': ('Pisces', 11), ...},
    'd4':  {'Lagna': ('Libra', 6),   'Sun': ('Leo', 4), ...},
    'd5':  {'Lagna': ('Pisces', 11), 'Sun': ('Scorpio', 7), ...},
    'vargottama': {'Sun': False, 'Moon': False, 'Rahu': True, ...},
    'divisional_charts': {'D2': ..., 'D3': ..., ...},  # 额外分盘
    'divisional_boundary_audit': {...},  # 逐分钟边界审计，uncertainty_minutes = 有效误差

    # 预分析
    'karakas': {'7k': [...], '8k': [...], 'dk_7k': 'Saturn', 'dk_8k': 'Rahu', 'dk_note': '7K(主)=Saturn, 8K(参考)=Rahu'},
    'dignity': {'Sun': {'compound': 'great_friend', ...}, ...},
    'house_lords': {1: {'lord':'Moon','domain':'自我','lord_house':8}, ...},
    'special_points': {'AL': {'sign':'Virgo','house':3}, 'UL': {'sign':'Pisces','house':9}},
    'combustion': {},
    'moon_phase': {'waxing': True, 'sun_moon_diff': 88.6},
}
```


## 输出规格

`chart_data.json`：schema、chart_id、audit_id、规则版本、输入（报时与计算用时间、钟表时间性质、IANA 时区、UTC 偏移、是否夏令时、经纬度、时间来源、声明与有效误差、审计范围）、计算设置、用户信息、上面的 `chart` 结构、过运快照、Shadbala 合并记录、来源说明。

`structured_data.md` 包含以下板块（格式参考 `reader/resources/data_contract.md`）：

| 板块 | 内容 |
|------|------|
| 元信息 | 出生时间与地点、出生时区、钟表时间性质、时间来源、声明精度、有效精度、实际审计范围、Ayanamsa、宫位制、数据版本（chart_id/audit_id） |
| 用户信息 | 性别、感情状态 |
| 行星位置 | 10颗行星+Lagna，星座/宫位/度数/逆行 |
| Chara Karakas | 7K主表（KN Rao）+「7K/8K 对照」表 + DK |
| Nakshatra | 全部行星的Nakshatra+Pada |
| 特殊点位 | AL(Arudha Lagna) + UL(Upapada Lagna) |
| Shadbala | 7颗行星的Rupas/百分比/排名/强弱/Ishta/Kashta + calc基准 + 数据来源 |
| SAV / BAV | 原始值(按星座) + 宫位映射(按宫位)；7颗行星×12星座矩阵 |
| Vimsottari Dasha | 9段大运 + 81段Antardasha + 729段Pratyantardasha；当前MD/AD/PD |
| Chara Dasha 时间线 | K.N. Rao 星座大运 |
| 预分析 | Compound Dignity、Graha Drishti、功能身份、结构格局预扫、互视/互溶、宫主表 |
| 分盘 | 分盘可信度声明（边界审计）+ D9/D10/D4/D5 + Vargottama + Pushkara + 分盘内部宫主表（线A） |
| 校验结果 | 17项自检（通过/失败/未完成）+ 能力范围表 |
| 过运 | 慢行星过运 + Sade Sati + 双过运 + 未来5年换座时间表（带提取日期） |

过运快照过期（快照日之后已换座，或超过 90 天）时只刷新过运，不必重排：
`python calculator/scripts/transit.py --chart <目录>/chart_data.json --write`（可加 `--date YYYY-MM-DD`）。chart_id 不变，structured_data.md 随之重新生成。其他日期：`--ingress-from <日期> --years N` 给任意区间的换座表；`--hit <恒星黄经度数> --planets Saturn,Jupiter --from … --to …` 给行星经过某一度数（如 Bhrigu Bindu）的日期。

验前事结果、校准率、生时矫正记录、信号修正日志不属于计算数据，不写进这两个文件（见 `shared/data_contract.md` §1）。

## 技术规格

- Ayanamsa: **True Chitrapaksha (TRUE_CITRA)**（固定，不可更改；属Lahiri系，差<1′）
- Node模式: **Mean Node**
- 天文核心: pysweph (Swiss Ephemeris C binding)
- SAV/BAV: **PyJHora 原生** (ashtakavarga_pyjhora.py)
- Dasha: **PyJHora 原生 MD/AD/PD** (dasha_pyjhora.py)；区间统一按`[start,end)`，禁止自行近似补三级运
- Shadbala: **PyJHora + 9项修正** (shadbala_pyjhora.py)
- 分盘: **PyJHora 原生** (divisional_pyjhora.py) — 15张 D1~D60；D2 用传统 Parasara Hora（行星只落 Cancer / Leo）。D2/D3/D7/D12 等只在 `chart_data.json` 的 `chart.divisional_charts` 里，阅读版只列 D9/D10/D4/D5
- 分盘稳定性: 在有效误差范围内逐分钟重算 D1/D9/D10/D4/D5 Lagna（build_chart.py 自动传入）；数学正确性与输入稳定性分别报告
- Dignity: 自建（旺/入庙/陷前置判断）；燃烧 orb / 方位强宫两表内联于 engine.py
- Chara Karakas: 7K（KN Rao）+ 8K参考
- 容错策略: **fail-fast**（缺依赖直接报错，不给错误结果）；过运计算失败只把行运能力标「计算失败」

## 与其他模块的关系

```
路径1（排盘，推荐）：
  出生信息 → build_chart.py → chart_data.json + structured_data.md → check_chart.py
  → reader 模块(验前事) → core 模块

路径2（PDF + 排盘）：
  PDF → reader 提取出生信息 → build_chart.py → PDF 交叉验证（仅同一出生时刻的 Shadbala 用 merge_shadbala.py 合并）
  → reader(验前事) → core

路径3（旧盘 / 兜底）：
  旧版 structured_data.md 或 reader 提取稿 → import_legacy_md.py → check_chart.py（缺项按能力范围降级）
  → reader(验前事) → core

路径4（仅日期）：
  只有出生日期 → build_chart.py --date-only → synastry 等按 shared/capabilities.md 降级使用
```

下游一律读 `chart_data.json` / `structured_data.md`，按 `check_chart.py` 的能力范围工作；来源不同的盘在能力范围里区分，不靠下游猜。
