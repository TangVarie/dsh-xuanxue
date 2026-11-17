#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""chart_core.py —— paipan.py 与 check_chart.py 共用的输入校验与历法计算。

只做确定性计算，不做解读。两个入口都从这里取同一套口径，避免一边一个算法。

默认口径（都会写进参数卡；可用参数改，改了也写进参数卡）
- 节气：交节是天文时刻。出生时刻先换算成北京时间（UTC+8），再与 lunar_python 的节气表比较。
  年柱按立春换，月柱按十二节换。
- 日柱、时柱：按"所用地方时"取。
    不给经度  → 当地标准时（钟表时间扣掉夏令时）；
    给经度    → 经度时差修正（只按经度差，每度 4 分钟，不含均时差）；
    再加 --eot → 真太阳时（经度时差 + 均时差，均时差用 NOAA 近似式，误差约 1 分钟内）。
  输入本身已是校正过的太阳时（--basis mean-solar / true-solar），不再做任何经度修正。
- 换日：默认 23 点换日（子初换日：23:00 起算次日日柱，时干按次日五鼠遁）。
  可选 0 点换日（晚子时：23 点后日柱仍算当天，时干按次日）。
- 起运：lunar_python sect=1（三天折一年、一天折四个月、一个时辰折十天）。

依赖：lunar_python==1.4.4（见 requirements.txt）。
"""
import datetime as _dt
import re

try:
    from lunar_python import Solar, Lunar, LunarYear
except ImportError:  # pragma: no cover
    Solar = Lunar = LunarYear = None

G = "甲乙丙丁戊己庚辛壬癸"
Z = "子丑寅卯辰巳午未申酉戌亥"
JZ = [G[i % 10] + Z[i % 12] for i in range(60)]
WX_GAN = dict(zip(G, "木木火火土土金金水水"))
YY_GAN = dict(zip(G, "阳阴阳阴阳阴阳阴阳阴"))
ZANGGAN = {
    "子": ["癸"], "丑": ["己", "癸", "辛"], "寅": ["甲", "丙", "戊"], "卯": ["乙"],
    "辰": ["戊", "乙", "癸"], "巳": ["丙", "戊", "庚"], "午": ["丁", "己"], "未": ["己", "丁", "乙"],
    "申": ["庚", "壬", "戊"], "酉": ["辛"], "戌": ["戊", "辛", "丁"], "亥": ["壬", "甲"],
}
BEIJING = _dt.timedelta(hours=8)


class InputError(ValueError):
    """用户输入不合法或缺项。入口脚本捕获后给短说明，不打堆栈。"""


class NeedsChoice(ValueError):
    """输入本身合法，但有两种以上读法，必须由用户补一个参数。附带候选。"""

    def __init__(self, msg, options):
        super().__init__(msg)
        self.options = options


def require_lunar():
    if Solar is None:
        raise RuntimeError("缺少依赖 lunar_python。安装：pip install -r requirements.txt"
                           "（或 pip install lunar_python==1.4.4 --break-system-packages）")


# ---------------------------------------------------------------- 干支基础
def shishen(day_gan, other_gan):
    if other_gan not in WX_GAN:
        return ""
    me_wx, o_wx = WX_GAN[day_gan], WX_GAN[other_gan]
    same = YY_GAN[day_gan] == YY_GAN[other_gan]
    sheng = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
    ke = {"木": "土", "火": "金", "土": "水", "金": "木", "水": "火"}
    if o_wx == me_wx:
        return "比肩" if same else "劫财"
    if sheng[me_wx] == o_wx:
        return "食神" if same else "伤官"
    if ke[me_wx] == o_wx:
        return "偏财" if same else "正财"
    if ke[o_wx] == me_wx:
        return "七杀" if same else "正官"
    return "偏印" if same else "正印"


def valid_pillar(p):
    return len(p) == 2 and p[0] in G and p[1] in Z and G.index(p[0]) % 2 == Z.index(p[1]) % 2


def parse_pillars(s, allow_three=False):
    """'甲辰 丙寅 戊戌 壬戌' → list。允许三柱（时柱未知）时传 allow_three。"""
    if not s or not s.strip():
        raise InputError("没有给四柱")
    parts = [p for p in re.split(r"[\s,，、]+", s.strip()) if p]
    if len(parts) == 1 and len(parts[0]) in (6, 8):  # 连写：甲辰丙寅戊戌壬戌
        t = parts[0]
        parts = [t[i:i + 2] for i in range(0, len(t), 2)]
    want = (3, 4) if allow_three else (4,)
    if len(parts) not in want:
        raise InputError("四柱应为 %s 柱，收到 %d 柱：%s" % ("3 或 4" if allow_three else "4", len(parts), " ".join(parts)))
    bad = [p for p in parts if not valid_pillar(p)]
    if bad:
        raise InputError("不是合法干支柱：%s（干支须阴阳同性，如 甲子 可、甲丑 不可）" % " ".join(bad))
    return parts


GENDER_MAP = {"male": "male", "m": "male", "男": "male", "乾": "male", "乾造": "male",
              "female": "female", "f": "female", "女": "female", "坤": "female", "坤造": "female"}


def norm_gender(s):
    if s is None or str(s).strip() == "":
        return None
    g = GENDER_MAP.get(str(s).strip().lower())
    if g is None:
        raise InputError("性别只能是 male/female、男/女、乾/坤，收到：%s" % s)
    return g


def gender_cn(g):
    return {"male": "男", "female": "女"}.get(g, "未提供")


# ---------------------------------------------------------------- 遁法
_TIGER = {"甲": "丙", "己": "丙", "乙": "戊", "庚": "戊", "丙": "庚", "辛": "庚",
          "丁": "壬", "壬": "壬", "戊": "甲", "癸": "甲"}
_RAT = {"甲": "甲", "己": "甲", "乙": "丙", "庚": "丙", "丙": "戊", "辛": "戊",
        "丁": "庚", "壬": "庚", "戊": "壬", "癸": "壬"}


def month_stem_ok(yp, mp):
    """五虎遁：年干定寅月之干。"""
    first = _TIGER[yp[0]]
    return G[(G.index(first) + (Z.index(mp[1]) - 2) % 12) % 10] == mp[0]


def rat_stem(day_gan, hour_branch):
    return G[(G.index(_RAT[day_gan]) + Z.index(hour_branch)) % 10]


def hour_stem_ok(dp, hp, ziday="23"):
    """五鼠遁：日干定子时之干。0 点换日口径下，子时还可能是"晚子时"（时干按次日）。"""
    if rat_stem(dp[0], hp[1]) == hp[0]:
        return True
    if ziday == "0" and hp[1] == "子":
        nxt = JZ[(JZ.index(dp) + 1) % 60]
        return rat_stem(nxt[0], "子") == hp[0]
    return False


def xunkong(pillar):
    """旬空：该柱所在旬缺的两个地支。"""
    i = JZ.index(pillar)
    start = i - i % 10
    return Z[(start + 10) % 12] + Z[(start + 11) % 12]


def is_forward(year_gan, gender):
    return (G.index(year_gan) % 2 == 0) == (gender == "male")


def expected_dayun(yp, mp, gender, n=8):
    step = 1 if is_forward(yp[0], gender) else -1
    i = JZ.index(mp)
    return [JZ[(i + step * (k + 1)) % 60] for k in range(n)]


def years_of(yp, lo, hi):
    return [y for y in range(lo, hi + 1) if JZ[(y - 4) % 60] == yp]


def day_pillar_of(d):
    """公历日（0 点起算）的日柱。1900-01-31 是甲辰日。"""
    return JZ[((d - _dt.date(1900, 1, 1)).days + 10) % 60]


# ---------------------------------------------------------------- 历法计算
_ec_cache = {}


def _ec(dt):
    key = (dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)
    if key not in _ec_cache:
        require_lunar()
        _ec_cache[key] = Solar.fromYmdHms(*key).getLunar()
    return _ec_cache[key].getEightChar()


def pillars_at(local_dt, beijing_dt=None, ziday="23"):
    """年月柱按北京时间比节气；日时柱按所用地方时。返回 (年, 月, 日, 时)。"""
    eb = _ec(beijing_dt or local_dt)
    el = _ec(local_dt)
    el.setSect(1 if ziday == "23" else 2)
    return (eb.getYear(), eb.getMonth(), el.getDay(), el.getTime())


def jie_around(beijing_dt):
    """前后两个"节"（定月柱的十二节）及距离（分钟）。"""
    require_lunar()
    l = Solar.fromYmdHms(beijing_dt.year, beijing_dt.month, beijing_dt.day,
                         beijing_dt.hour, beijing_dt.minute, beijing_dt.second).getLunar()
    out = {}
    for tag, j in (("prev", l.getPrevJie()), ("next", l.getNextJie())):
        s = j.getSolar()
        t = _dt.datetime(s.getYear(), s.getMonth(), s.getDay(), s.getHour(), s.getMinute(), s.getSecond())
        out[tag] = {"name": j.getName(), "time_beijing": t.strftime("%Y-%m-%d %H:%M"),
                    "minutes": round(abs((beijing_dt - t).total_seconds()) / 60)}
    return out


def minutes_to_hour_boundary(local_dt):
    """距最近的时辰交界（奇数整点）多少分钟。"""
    m = local_dt.hour * 60 + local_dt.minute + local_dt.second / 60.0
    best = min(abs(m - b) for b in [h * 60 for h in range(-1, 26, 2)])
    return round(best)


def eot_minutes(dt_utc):
    """均时差（分钟，真太阳时 − 平太阳时），NOAA 近似式。"""
    doy = dt_utc.timetuple().tm_yday
    import math
    gam = 2 * math.pi / 365.0 * (doy - 1 + (dt_utc.hour - 12) / 24.0)
    return 229.18 * (0.000075 + 0.001868 * math.cos(gam) - 0.032077 * math.sin(gam)
                     - 0.014615 * math.cos(2 * gam) - 0.040849 * math.sin(2 * gam))


def yun_info(beijing_dt, gender):
    """大运方向、起运时间、十步大运。gender 必须是 male/female。"""
    require_lunar()
    ec = _ec(beijing_dt)
    yun = ec.getYun(1 if gender == "male" else 0, 1)
    s = yun.getStartSolar()
    dy = [{"ganzhi": d.getGanZhi(), "start_year": d.getStartYear(), "start_age_xu": d.getStartAge()}
          for d in yun.getDaYun(11)[1:] if d.getGanZhi()]
    return {"gender": gender, "forward": yun.isForward(),
            "start": {"years": yun.getStartYear(), "months": yun.getStartMonth(), "days": yun.getStartDay(),
                      "hours": yun.getStartHour()},
            "start_decimal": round(yun.getStartYear() + yun.getStartMonth() / 12.0 + yun.getStartDay() / 365.0, 2),
            "start_solar": s.toYmd(), "dayun": dy}


# ---------------------------------------------------------------- 时间输入
_DT_FORMATS = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"]


def parse_dt(s):
    """返回 (datetime, has_time)。只认 YYYY-MM-DD[ HH:MM[:SS]]，斜杠和点也可。"""
    if not s or not s.strip():
        raise InputError("没有给出生日期")
    t = s.strip().replace("/", "-").replace(".", "-").replace("T", " ")
    t = re.sub(r"\s+", " ", t)
    for f in _DT_FORMATS:
        try:
            d = _dt.datetime.strptime(t, f)
            return d, f != "%Y-%m-%d"
        except ValueError:
            continue
    raise InputError("日期格式应为 YYYY-MM-DD 或 YYYY-MM-DD HH:MM，收到：%s" % s)


def _zoneinfo(name):
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(name)
    except Exception:
        return None


def parse_tz(s):
    """返回 dict(kind=fixed|iana, offset_min, zone, label, source)。"""
    if s is None or str(s).strip() == "":
        return {"kind": "fixed", "offset_min": 480, "zone": None, "label": "UTC+8", "source": "默认（未提供时区）"}
    t = str(s).strip().upper().replace("UTC", "").replace("GMT", "")
    m = re.fullmatch(r"([+-])?(\d{1,2})(?::?(\d{2}))?", t)
    if m:
        sign = -1 if m.group(1) == "-" else 1
        mins = sign * (int(m.group(2)) * 60 + int(m.group(3) or 0))
        if not -720 <= mins <= 840:
            raise InputError("时区偏移超出范围：%s" % s)
        return {"kind": "fixed", "offset_min": mins, "zone": None,
                "label": "UTC%+d" % (mins // 60) + (":%02d" % (abs(mins) % 60) if mins % 60 else ""), "source": "用户"}
    z = _zoneinfo(str(s).strip())
    if z is None:
        raise InputError("认不出时区：%s。请给 +8、-5、+05:30 这样的偏移，或 Asia/Shanghai 这样的时区名"
                         "（时区名需要系统时区库）" % s)
    return {"kind": "iana", "offset_min": None, "zone": z, "label": str(s).strip(), "source": "用户"}


def in_china_dst(naive_dt):
    """中国 1986–1991 年夏令时。靠系统时区库判断；没有时区库时返回 None（未知）。"""
    z = _zoneinfo("Asia/Shanghai")
    if z is None:
        return None
    try:
        return bool(naive_dt.replace(tzinfo=z).dst())
    except Exception:
        return None


def resolve_time(date_str, *, calendar="solar", leap=None, tz=None, dst="unknown", basis="clock",
                 lon=None, eot=False, ziday="23", uncertainty=0):
    """把原始出生时间解析成计算用时间，并记下每个口径。

    返回 dict：
      record   参数卡（原始输入、历法、时区、夏令时、经度、时间口径、换日等，每项带来源）
      has_time 是否给了时刻
      main     {"local": 日时柱用时间, "beijing": 节气比较用北京时间}
      variants 其他合理读法 [{"label","local","beijing","ziday"}]，用于发现边界候选
      notes    提示
    """
    if ziday not in ("23", "0"):
        raise InputError("换日口径只能是 23 或 0")
    if basis not in ("clock", "mean-solar", "true-solar"):
        raise InputError("时间口径只能是 clock / mean-solar / true-solar")
    if lon is not None and not -180 <= lon <= 180:
        raise InputError("经度应在 -180 到 180 之间，收到：%s" % lon)
    if dst not in ("yes", "no", "unknown"):
        raise InputError("夏令时只能是 yes / no / unknown")
    if uncertainty < 0 or uncertainty > 240:
        raise InputError("时间误差应在 0–240 分钟")

    raw = date_str
    dt_in, has_time = parse_dt(date_str)
    rec = {"原始输入": {"value": raw, "source": "用户"}}
    notes = []

    # 1) 历法
    if calendar == "lunar":
        require_lunar()
        y, mo, d = dt_in.year, dt_in.month, dt_in.day
        leap_m = LunarYear.fromYear(y).getLeapMonth()
        if leap_m == mo and leap is None:
            opts = []
            for lp in (False, True):
                s = Lunar.fromYmdHms(y, -mo if lp else mo, d, dt_in.hour, dt_in.minute, 0).getSolar()
                opts.append({"leap": lp, "solar": s.toYmd()})
            raise NeedsChoice("农历 %d 年有闰%d月，请说明是不是闰月（--leap yes/no）" % (y, mo), opts)
        if leap and leap_m != mo:
            raise InputError("农历 %d 年没有闰%d月" % (y, mo))
        try:
            s = Lunar.fromYmdHms(y, -mo if leap else mo, d, dt_in.hour, dt_in.minute, dt_in.second).getSolar()
        except Exception:
            raise InputError("农历日期不存在：%s" % raw)
        dt_in = _dt.datetime(s.getYear(), s.getMonth(), s.getDay(), dt_in.hour, dt_in.minute, dt_in.second)
        rec["历法"] = {"value": "农历%s → 公历 %s" % ("（闰月）" if leap else "", dt_in.strftime("%Y-%m-%d")), "source": "用户"}
    else:
        rec["历法"] = {"value": "公历", "source": "用户" if calendar == "solar" else "默认"}

    if not has_time:
        rec["出生时刻"] = {"value": "未提供", "source": "—"}

    # 2) 时区与夏令时
    tzi = parse_tz(tz)
    rec["时区"] = {"value": tzi["label"], "source": tzi["source"]}
    noon = dt_in if has_time else dt_in.replace(hour=12)
    if tzi["kind"] == "iana":
        aware = noon.replace(tzinfo=tzi["zone"])
        total = aware.utcoffset()
        dst_td = aware.dst() or _dt.timedelta(0)
        if dst != "unknown":
            dst_td = _dt.timedelta(minutes=60) if dst == "yes" else _dt.timedelta(0)
            rec["夏令时"] = {"value": "是" if dst == "yes" else "否", "source": "用户（覆盖时区库）"}
        else:
            rec["夏令时"] = {"value": "是（%d 分钟）" % (dst_td.total_seconds() // 60) if dst_td else "否",
                          "source": "时区库"}
        std_off = total - (aware.dst() or _dt.timedelta(0))
    else:
        std_off = _dt.timedelta(minutes=tzi["offset_min"])
        dst_td = _dt.timedelta(minutes=60) if dst == "yes" else _dt.timedelta(0)
        rec["夏令时"] = {"value": {"yes": "是（60 分钟）", "no": "否", "unknown": "未说明，按否计算"}[dst],
                      "source": "用户" if dst != "unknown" else "默认"}
    total_off = std_off + dst_td

    # 3) 时间口径
    lon_used = lon
    rec["出生地经度"] = {"value": ("%.2f°" % lon) if lon is not None else "未提供", "source": "用户" if lon is not None else "—"}
    if basis == "clock":
        utc = noon - total_off if has_time else None
        if not has_time:
            correction = "none"
        elif lon is None:
            correction = "none"
        else:
            correction = "true" if eot else "mean"
        rec["时间口径"] = {"value": {"none": "当地标准时（钟表时间扣夏令时），未做经度修正",
                                  "mean": "经度时差修正（每度 4 分钟，不含均时差）",
                                  "true": "真太阳时（经度时差 + 均时差，NOAA 近似式）"}[correction],
                       "source": "默认" if correction == "none" else "用户（给了经度%s）" % ("和 --eot" if eot else "")}
    else:
        correction = "given"
        rec["时间口径"] = {"value": "输入已是%s，不再做经度修正" % ("平太阳时" if basis == "mean-solar" else "真太阳时"),
                       "source": "用户"}
        if eot and basis == "mean-solar":
            notes.append("输入已标为平太阳时，--eot 被忽略。")

    def compute(clock_dt, corr, dst_delta=None):
        """由钟表时间（或已校正太阳时）得 (local, beijing)。"""
        dd = dst_td if dst_delta is None else dst_delta
        if basis == "clock":
            u = clock_dt - (std_off + dd)
            if corr == "none":
                loc = clock_dt - dd
            elif corr == "mean":
                loc = u + _dt.timedelta(minutes=4 * lon_used)
            else:
                loc = u + _dt.timedelta(minutes=4 * lon_used + eot_minutes(u))
            return loc, u + BEIJING
        # 已校正太阳时
        if lon_used is not None:
            u = clock_dt - _dt.timedelta(minutes=4 * lon_used)
            if basis == "true-solar":
                u = u - _dt.timedelta(minutes=eot_minutes(u))
        else:
            u = clock_dt - BEIJING
        return clock_dt, u + BEIJING

    if basis != "clock" and lon_used is None:
        notes.append("输入是太阳时但没给经度，节气比较按“输入时间≈北京时间”近似；临近交节时要补经度。")

    rec["换日"] = {"value": "23 点换日（子初换日）" if ziday == "23" else "0 点换日（晚子时：23 点后日柱算当天，时干按次日）",
                 "source": "默认" if ziday == "23" else "用户"}
    rec["起运算法"] = {"value": "lunar_python sect=1（三天折一年，一个时辰折十天）", "source": "默认"}

    out = {"record": rec, "has_time": has_time, "notes": notes, "variants": []}
    if not has_time:
        day0 = dt_in.replace(hour=0, minute=0, second=0)
        out["main"] = None
        out["day_window"] = []
        for h, m in ((0, 0), (23, 59)):
            loc = day0.replace(hour=h, minute=m)
            out["day_window"].append({"local": loc, "beijing": loc - std_off + BEIJING})
        return out

    loc, bj = compute(dt_in, correction)
    out["main"] = {"local": loc, "beijing": bj, "ziday": ziday, "label": "采用口径"}
    rec["日时柱所用时间"] = {"value": loc.strftime("%Y-%m-%d %H:%M"), "source": "计算"}
    rec["节气比较所用北京时间"] = {"value": bj.strftime("%Y-%m-%d %H:%M"), "source": "计算"}

    # 4) 其他合理读法（只用来发现候选，不改主口径）
    V = []
    if basis == "clock" and lon is not None:
        for c, lab in (("none", "不做经度修正"), ("mean", "只做经度时差"), ("true", "经度时差＋均时差")):
            if c != correction:
                l2, b2 = compute(dt_in, c)
                V.append({"label": lab, "local": l2, "beijing": b2, "ziday": ziday})
    if basis == "clock" and dst == "unknown" and tzi["kind"] == "fixed" and tzi["offset_min"] == 480:
        cd = in_china_dst(dt_in)
        if cd:
            l2, b2 = compute(dt_in, correction, dst_delta=_dt.timedelta(minutes=60))
            V.append({"label": "若钟表时间是夏令时（减 60 分钟）", "local": l2, "beijing": b2, "ziday": ziday})
            notes.append("该日期在中国 1986–1991 年夏令时期内，钟表时间可能是夏令时；未说明，已列候选。")
    if basis == "clock" and dst == "unknown" and tzi["kind"] == "iana" and dst_td:
        l2, b2 = compute(dt_in, correction, dst_delta=_dt.timedelta(0))
        V.append({"label": "若钟表时间是标准时（不按夏令时扣）", "local": l2, "beijing": b2, "ziday": ziday})
        notes.append("时区库显示该时刻在夏令时内，已按夏令时扣除；用户没说明钟表是否用了夏令时，另一读法已列候选。")
    if uncertainty:
        for sgn in (-1, 1):
            l2, b2 = compute(dt_in + _dt.timedelta(minutes=sgn * uncertainty), correction)
            V.append({"label": "出生时间%+d 分钟" % (sgn * uncertainty), "local": l2, "beijing": b2, "ziday": ziday})
        rec["时间误差"] = {"value": "±%d 分钟" % uncertainty, "source": "用户"}
    if loc.hour == 23:
        V.append({"label": "换另一种换日口径", "local": loc, "beijing": bj, "ziday": "0" if ziday == "23" else "23"})
    out["variants"] = V
    return out


def chart_candidates(tr):
    """主口径与各候选读法排出的四柱，相同的合并。返回 [{"pillars":[..], "labels":[..]}]，主口径在前。"""
    rows = []
    for v in [tr["main"]] + tr["variants"]:
        ps = list(pillars_at(v["local"], v["beijing"], v["ziday"]))
        for r in rows:
            if r["pillars"] == ps:
                r["labels"].append(v["label"])
                break
        else:
            rows.append({"pillars": ps, "labels": [v["label"]], "beijing": v["beijing"]})
    return rows
