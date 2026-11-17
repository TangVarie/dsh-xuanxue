#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""公历 → 年月日时干支（六爻起卦用）

只用标准库。月建按"节"交接（立春寅月、惊蛰卯月……），年按立春换，日按换日约定，
时辰按两小时一辰。起卦时刻落在节气交接前后、或 23～24 点而没指定换日约定时，
相关字段标 unconfirmed 并给出两种候选，不替用户挑。

用法
  python scripts/ganzhi.py "2026-10-12 14:30"
  python scripts/ganzhi.py "2026-10-12 23:20" --zi-rule 23     # 23 点换日（子初换日）
  python scripts/ganzhi.py "2026-10-12" --tz +08:00 --json
  python scripts/ganzhi.py "2026-10-12 14:30" --expect-day 己未  # 核对用户给的日干支

输入
  时间    "YYYY-MM-DD"、"YYYY-MM-DD HH" 或 "YYYY-MM-DD HH:MM"，为起卦地的钟表时间
  --tz    该钟表时间的 UTC 偏移。不给时按 +08:00（北京时间）算，并在节气交接落在
          "换个时区月建就不同"的时段内时给出提示（起卦地不在东八区请写明 --tz）。不做真太阳时校正。
  --zi-rule  23 = 23:00 起算次日；00 = 0:00 换日。不给时，23～24 点的日干支标 unconfirmed。
  --margin-min  节气交接判"未确认"的半宽，默认 60 分钟（见下"精度"）

精度
  太阳视黄经用 Meeus《天文算法》第 25 章低精度公式（约 0.01°，相当于 15 分钟左右），
  ΔT 用 Espenak–Meeus 多项式。tests/test_ganzhi.py 拿 sxtwl 对 1900–2100 年全部节气核过误差，
  默认 60 分钟的未确认带宽大于实测最大误差。只支持 1900–2100 年。
  装了 sxtwl 时会自动交叉核对节气时刻与日干支，结果写在 crosscheck 字段。

输出 status 只有三种：ok / unconfirmed / error。
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
# 十二节（定月建）与对应太阳视黄经；寅月始于立春 315°
JIE = [("立春", 315), ("惊蛰", 345), ("清明", 15), ("立夏", 45), ("芒种", 75), ("小暑", 105),
       ("立秋", 135), ("白露", 165), ("寒露", 195), ("立冬", 225), ("大雪", 255), ("小寒", 285)]
MIN_YEAR, MAX_YEAR = 1900, 2100


class GanzhiError(ValueError):
    """输入不合法或超出支持范围。"""


# ── 基础 ──────────────────────────────────────────────────────────────

def gz_name(index: int) -> str:
    """六十甲子序号（甲子=0）→ 干支名"""
    return STEMS[index % 10] + BRANCHES[index % 12]


def gz_index(name: str) -> int:
    """干支名 → 六十甲子序号；不合法时抛错"""
    if len(name) != 2 or name[0] not in STEMS or name[1] not in BRANCHES:
        raise GanzhiError(f"不是合法干支：{name!r}")
    s, b = STEMS.index(name[0]), BRANCHES.index(name[1])
    if (s - b) % 2:
        raise GanzhiError(f"干支阴阳不配：{name}")
    for i in range(60):
        if i % 10 == s and i % 12 == b:
            return i
    raise GanzhiError(name)  # pragma: no cover


def xunkong(day_gz: str) -> str:
    """按日干支查旬空，返回两支，如 '午未'"""
    i = gz_index(day_gz)
    xun_start = i - i % 10          # 本旬甲日序号
    b = xun_start % 12              # 甲日所在地支
    return BRANCHES[(b + 10) % 12] + BRANCHES[(b + 11) % 12]


def parse_tz(text: str) -> timezone:
    m = re.fullmatch(r"(?:UTC|GMT)?\s*([+-])(\d{1,2})(?::?(\d{2}))?", text.strip(), re.I)
    if not m:
        raise GanzhiError(f"时区写法不认识：{text!r}（例：+08:00）")
    sign = 1 if m.group(1) == "+" else -1
    hours, minutes = int(m.group(2)), int(m.group(3) or 0)
    if hours > 14 or minutes >= 60:
        raise GanzhiError(f"时区超出范围：{text!r}")
    return timezone(sign * timedelta(hours=hours, minutes=minutes))


@dataclass
class ParsedTime:
    local: datetime        # 带时区的钟表时间（只有日期时取当日 12:00 作代表）
    precision: str         # "date" / "hour" / "minute"


def parse_time(text: str, tz: timezone) -> ParsedTime:
    text = text.strip().replace("/", "-").replace("T", " ")
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})(?:\s+(\d{1,2})(?::(\d{1,2}))?)?", text)
    if not m:
        raise GanzhiError(f"时间写法不认识：{text!r}（例：2026-10-12 14:30）")
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not MIN_YEAR <= y <= MAX_YEAR:
        raise GanzhiError(f"只支持 {MIN_YEAR}–{MAX_YEAR} 年：{y}")
    hh = m.group(4)
    mm = m.group(5)
    try:
        if hh is None:
            return ParsedTime(datetime(y, mo, d, 12, 0, tzinfo=tz), "date")
        h = int(hh)
        if h == 24 and (mm is None or int(mm) == 0):
            raise GanzhiError("24 点请写成次日 00:00")
        if mm is None:
            return ParsedTime(datetime(y, mo, d, h, 0, tzinfo=tz), "hour")
        return ParsedTime(datetime(y, mo, d, h, int(mm), tzinfo=tz), "minute")
    except ValueError as exc:
        raise GanzhiError(f"日期不存在：{text!r}（{exc}）") from exc


# ── 天文：太阳视黄经与节气时刻 ─────────────────────────────────────────

def julian_day(dt_utc: datetime) -> float:
    """UTC datetime → 儒略日（UT）"""
    y, m = dt_utc.year, dt_utc.month
    d = dt_utc.day + (dt_utc.hour + (dt_utc.minute + dt_utc.second / 60) / 60) / 24
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    return math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1)) + d + b - 1524.5


def jd_to_utc(jd: float) -> datetime:
    return datetime(2000, 1, 1, 12, tzinfo=timezone.utc) + timedelta(days=jd - 2451545.0)


def delta_t_seconds(year: float) -> float:
    """Espenak–Meeus ΔT 多项式（秒），1900–2150"""
    y = year
    if y < 1920:
        t = y - 1900
        return -2.79 + 1.494119 * t - 0.0598939 * t ** 2 + 0.0061966 * t ** 3 - 0.000197 * t ** 4
    if y < 1941:
        t = y - 1920
        return 21.20 + 0.84493 * t - 0.076100 * t ** 2 + 0.0020936 * t ** 3
    if y < 1961:
        t = y - 1950
        return 29.07 + 0.407 * t - t ** 2 / 233 + t ** 3 / 2547
    if y < 1986:
        t = y - 1975
        return 45.45 + 1.067 * t - t ** 2 / 260 - t ** 3 / 718
    if y < 2005:
        t = y - 2000
        return (63.86 + 0.3345 * t - 0.060374 * t ** 2 + 0.0017275 * t ** 3
                + 0.000651814 * t ** 4 + 0.00002373599 * t ** 5)
    if y < 2050:
        t = y - 2000
        return 62.92 + 0.32217 * t + 0.005589 * t ** 2
    u = (y - 1820) / 100
    return -20 + 32 * u ** 2 - 0.5628 * (2150 - y)


def sun_apparent_longitude(jd_ut: float) -> float:
    """太阳视黄经（度，0–360），Meeus 第 25 章低精度算法"""
    year = 2000 + (jd_ut - 2451545.0) / 365.25
    jde = jd_ut + delta_t_seconds(year) / 86400
    t = (jde - 2451545.0) / 36525
    l0 = 280.46646 + 36000.76983 * t + 0.0003032 * t * t
    m = math.radians(357.52911 + 35999.05029 * t - 0.0001537 * t * t)
    c = ((1.914602 - 0.004817 * t - 0.000014 * t * t) * math.sin(m)
         + (0.019993 - 0.000101 * t) * math.sin(2 * m) + 0.000289 * math.sin(3 * m))
    omega = math.radians(125.04 - 1934.136 * t)
    lam = l0 + c - 0.00569 - 0.00478 * math.sin(omega)
    return lam % 360


def _angle_diff(target: float, current: float) -> float:
    return (target - current + 180) % 360 - 180


def solar_term_jd(longitude: float, jd_guess: float) -> float:
    """太阳视黄经到达 longitude 的时刻（儒略日 UT），从 jd_guess 附近找"""
    jd = jd_guess
    for _ in range(50):
        diff = _angle_diff(longitude, sun_apparent_longitude(jd))
        jd += diff / 0.98564736
        if abs(diff) < 1e-7:
            break
    return jd


def jie_list(year: int) -> list[tuple[str, int, float]]:
    """该公历年及前后的十二节时刻：[(名, 黄经, JD_UT)]，按时间排序"""
    out = []
    for y in (year - 1, year, year + 1):
        for name, lon in JIE:
            # 立春约在 2 月 4 日；按黄经推算大致日期作初值
            days = ((lon - 315) % 360) / 0.98564736
            guess = julian_day(datetime(y, 2, 4, tzinfo=timezone.utc)) + days
            out.append((name, lon, solar_term_jd(lon, guess)))
    out.sort(key=lambda x: x[2])
    return out


def month_index_at(jd_ut: float) -> int:
    """寅月=0 … 丑月=11"""
    lam = sun_apparent_longitude(jd_ut)
    return int(((lam - 315) % 360) // 30)


# ── 干支计算 ──────────────────────────────────────────────────────────

def day_gz_of(d: date) -> str:
    """公历日期 → 日干支（与时区无关，指该日 0 点到 24 点）"""
    jdn = d.toordinal() + 1721425  # 0001-01-01 的儒略日数为 1721426
    return gz_name((jdn + 49) % 60)


def year_gz_index(lichun_year: int) -> int:
    return (lichun_year - 4) % 60


def month_gz(year_stem: int, month_idx: int) -> str:
    """五虎遁：甲己之年丙作首"""
    stem = (year_stem * 2 + 2 + month_idx) % 10
    branch = (2 + month_idx) % 12
    return STEMS[stem] + BRANCHES[branch]


def hour_gz(day_stem: int, hour: int) -> str:
    """五鼠遁：甲己还加甲"""
    branch = ((hour + 1) // 2) % 12
    stem = (day_stem * 2 + branch) % 10
    return STEMS[stem] + BRANCHES[branch]


def _fmt_local(jd_ut: float, tz: timezone) -> str:
    return jd_to_utc(jd_ut).astimezone(tz).strftime("%Y-%m-%d %H:%M")


def _year_month_at(jd_ut: float, jie_all: list, local_year: int) -> tuple[str, str]:
    """给定时刻 → (年干支, 月干支)。年以立春为界，月以节为界。"""
    feb4 = julian_day(datetime(local_year, 2, 4, tzinfo=timezone.utc))
    lichun_this = min((j for j in jie_all if j[0] == "立春"), key=lambda j: abs(j[2] - feb4))
    yi = year_gz_index(local_year if jd_ut >= lichun_this[2] else local_year - 1)
    return gz_name(yi), month_gz(yi % 10, month_index_at(jd_ut))


# 没写时区、按 +08:00 算时：真实时区可在 UTC-12～+14 之间，真实时刻相对假定时刻落在 [-6h, +20h]。
# 这个区间里有节气交接，月建（立春时还有年）就取决于时区。
TZ_ASSUMED = "+08:00"
TZ_WINDOW_BEFORE_H, TZ_WINDOW_AFTER_H = 6.0, 20.0


def convert(text: str, tz_text: str | None = TZ_ASSUMED, zi_rule: str | None = None,
            margin_min: float = 60.0, expect: dict | None = None, tz_assumed: bool = False) -> dict:
    """主入口。永远返回 dict；出错时 status=error。

    tz_text 为 None 或 tz_assumed=True 表示时区是默认假定的（没有人确认过），
    此时若节气交接落在时区能影响月建的时段内，warnings 里会加一条提示，status 不变。
    """
    if tz_text is None:
        tz_text, tz_assumed = TZ_ASSUMED, True
    try:
        tz = parse_tz(tz_text)
        pt = parse_time(text, tz)
        if zi_rule not in (None, "23", "00"):
            raise GanzhiError("--zi-rule 只能是 23 或 00")
    except GanzhiError as exc:
        return {"status": "error", "reason": str(exc), "input": text}

    local = pt.local
    warnings: list[str] = []
    result: dict = {"input": text, "tz": tz_text, "tz_assumed": bool(tz_assumed), "precision": pt.precision,
                    "zi_rule": zi_rule, "method": "Meeus 低精度太阳黄经 + ΔT 多项式"}

    # 判断用的时间范围：只有日期时，代表一整天；有小时没分钟时，代表那一小时
    if pt.precision == "date":
        start = local.replace(hour=0, minute=0)
        end = start + timedelta(days=1) - timedelta(minutes=1)
    elif pt.precision == "hour":
        start = local
        end = local + timedelta(minutes=59)
    else:
        start = end = local
    jd_start = julian_day(start.astimezone(timezone.utc))
    jd_end = julian_day(end.astimezone(timezone.utc))
    jd_mid = julian_day(local.astimezone(timezone.utc))

    # ── 年、月：看时间范围（±margin）内有没有节交接 ──
    margin = margin_min / 1440
    jie_all = jie_list(local.year)
    near = [j for j in jie_all if jd_start - margin <= j[2] <= jd_end + margin]
    # 范围内有节交接：取交接前、后各一刻作两个候选；没有就只取起卦时刻
    probes = [near[0][2] - 1e-5, near[0][2] + 1e-5] if near else [jd_mid]
    ym_candidates = []
    for jd in probes:
        ym = _year_month_at(jd, jie_all, local.year)
        if ym not in ym_candidates:
            ym_candidates.append(ym)
    prev_jie = max((j for j in jie_all if j[2] <= jd_mid), key=lambda j: j[2])
    next_jie = min((j for j in jie_all if j[2] > jd_mid), key=lambda j: j[2])
    jieqi_info = {"prev": {"name": prev_jie[0], "time": _fmt_local(prev_jie[2], tz)},
                  "next": {"name": next_jie[0], "time": _fmt_local(next_jie[2], tz)}}
    if len(ym_candidates) == 1:
        result["year"] = {"ganzhi": ym_candidates[0][0], "status": "ok"}
        result["month"] = {"ganzhi": ym_candidates[0][1], "branch": ym_candidates[0][1][1],
                           "status": "ok", "jieqi": jieqi_info}
    else:
        jn = "、".join(f"{j[0]} {_fmt_local(j[2], tz)}" for j in near)
        years = sorted({c[0] for c in ym_candidates})
        months = [c[1] for c in ym_candidates]
        result["year"] = ({"ganzhi": years[0], "status": "ok"} if len(years) == 1 else
                          {"ganzhi": None, "status": "unconfirmed", "candidates": [c[0] for c in ym_candidates]})
        result["month"] = {"ganzhi": None, "branch": None, "status": "unconfirmed",
                           "candidates": months, "jieqi": jieqi_info,
                           "why": f"起卦时间与节气交接（{jn}）相距不到 {margin_min:.0f} 分钟"
                                  + ("，且只给了日期" if pt.precision == "date" else "")}
        warnings.append(f"月建未确认：{result['month']['why']}；请确认起卦时刻（候选 {'/'.join(months)}）")

    # ── 时区是假定的：节气交接落在时区可影响的时段内就提示 ──
    if tz_assumed:
        lo = jd_start - TZ_WINDOW_BEFORE_H / 24
        hi = jd_end + TZ_WINDOW_AFTER_H / 24
        hits = [j for j in jie_all if lo <= j[2] <= hi and j not in near]
        if hits:
            jn = "、".join(f"{j[0]} {_fmt_local(j[2], tz)}" for j in hits)
            result["tz_note"] = {"jieqi": [{"name": j[0], "time": _fmt_local(j[2], tz)} for j in hits],
                                 "why": "时区按默认 +08:00（北京时间）算，没有确认过"}
            warnings.append(f"时区未指明，按北京时间（+08:00）换算；{jn}（北京时间）交接离起卦时刻很近，"
                            "起卦地不在东八区时月建可能不同，请用 --tz 写明当地 UTC 偏移后重算")

    # ── 日 ──
    d0 = local.date()
    in_zi = pt.precision != "date" and local.hour == 23
    if in_zi and zi_rule is None:
        cands = [day_gz_of(d0), day_gz_of(d0 + timedelta(days=1))]
        result["day"] = {"ganzhi": None, "status": "unconfirmed", "candidates": cands,
                         "why": "起卦在 23～24 点，未指定换日约定（--zi-rule 23 或 00）"}
        warnings.append(f"日干支未确认：23 点后起卦，按 0 点换日为 {cands[0]}，按 23 点换日为 {cands[1]}")
    else:
        dd = d0 + timedelta(days=1) if (in_zi and zi_rule == "23") else d0
        result["day"] = {"ganzhi": day_gz_of(dd), "status": "ok"}
        if pt.precision == "date":
            warnings.append("只给了日期：如果起卦在 23 点以后，日干支可能按次日算（看换日约定）")

    # ── 时 ──
    if pt.precision == "date":
        result["hour"] = {"ganzhi": None, "branch": None, "status": "unconfirmed", "why": "没有给时刻"}
    elif in_zi and zi_rule != "23":
        # 23～24 点不按 23 点换日时属"晚子时"：时支是子没有争议，时干各家算法不一
        both = [hour_gz(STEMS.index(day_gz_of(x)[0]), 23) for x in (d0, d0 + timedelta(days=1))]
        result["hour"] = {"ganzhi": None, "branch": "子", "status": "unconfirmed", "candidates": both,
                          "why": "23～24 点的时干有早子时、晚子时两种算法；六爻一般只用时支"}
    else:
        hgz = hour_gz(STEMS.index(result["day"]["ganzhi"][0]), local.hour)
        result["hour"] = {"ganzhi": hgz, "branch": hgz[1], "status": "ok"}

    # ── 旬空 ──
    if result["day"]["status"] == "ok":
        result["xunkong"] = xunkong(result["day"]["ganzhi"])
    else:
        result["xunkong"] = {c: xunkong(c) for c in result["day"]["candidates"]}

    # ── 核对用户给的干支 ──
    if expect:
        mism = []
        for key in ("year", "month", "day", "hour"):
            want = expect.get(key)
            if not want:
                continue
            got = result[key]
            pool = [got["ganzhi"]] if got.get("ganzhi") else list(got.get("candidates") or [])
            if key == "month" and len(want) == 1:      # 只给了月支
                pool = [p[1] for p in pool if p]
            if want not in pool:
                mism.append(f"{key}：用户给 {want}，换算为 {'/'.join(p for p in pool if p) or '未确认'}")
        result["expect_check"] = {"mismatches": mism, "ok": not mism}
        if mism:
            warnings.append("用户给的干支与换算不一致：" + "；".join(mism))

    result["crosscheck"] = _crosscheck(result, local, tz)
    result["warnings"] = warnings
    statuses = [result[k]["status"] for k in ("year", "month", "day")]
    result["status"] = "ok" if all(s == "ok" for s in statuses) else "unconfirmed"
    return result


def _crosscheck(result: dict, local: datetime, tz: timezone) -> dict:
    """装了 sxtwl 时交叉核对（只核年、月、日；sxtwl 节气 JD 按北京时间）"""
    try:
        import sxtwl  # noqa: PLC0415
    except ImportError:
        return {"sxtwl": "unavailable"}
    try:
        bj = local.astimezone(timezone(timedelta(hours=8)))
        day = sxtwl.fromSolar(local.year, local.month, local.day)
        dgz = STEMS[day.getDayGZ().tg] + BRANCHES[day.getDayGZ().dz]
        notes = {}
        if result["day"]["status"] == "ok" and not (local.hour == 23 and result.get("zi_rule") == "23"):
            notes["day"] = "agree" if dgz == result["day"]["ganzhi"] else f"disagree（sxtwl {dgz}）"
        if result["month"]["status"] == "ok":
            bday = sxtwl.fromSolar(bj.year, bj.month, bj.day)
            mgz = STEMS[bday.getMonthGZ().tg] + BRANCHES[bday.getMonthGZ().dz]
            # sxtwl 的月柱按日取，节当天以交节时刻为界；只在非节日比较
            if not bday.hasJieQi():
                notes["month"] = "agree" if mgz == result["month"]["ganzhi"] else f"disagree（sxtwl {mgz}）"
        return {"sxtwl": notes or "skipped"}
    except Exception as exc:  # noqa: BLE001
        return {"sxtwl": f"error: {exc}"}


# ── 命令行 ────────────────────────────────────────────────────────────

def summary(r: dict) -> str:
    if r["status"] == "error":
        return f"换算失败：{r['reason']}"
    def show(k):
        x = r[k]
        if x.get("ganzhi"):
            return x["ganzhi"]
        if x.get("candidates"):
            return "未确认(" + "/".join(c for c in x["candidates"] if c) + ")"
        return "未确认"
    xk = r["xunkong"] if isinstance(r["xunkong"], str) else "、".join(f"{k}日{v}" for k, v in r["xunkong"].items())
    tzs = r["tz"] + ("，默认" if r.get("tz_assumed") else "")
    lines = [f"{r['input']}（{tzs}）→ {show('year')}年 {show('month')}月 {show('day')}日 {show('hour')}时",
             f"月建 {r['month'].get('branch') or '未确认'}｜日辰 {r['day'].get('ganzhi') or '未确认'}｜旬空 {xk}",
             f"前一节 {r['month']['jieqi']['prev']['name']} {r['month']['jieqi']['prev']['time']}；"
             f"后一节 {r['month']['jieqi']['next']['name']} {r['month']['jieqi']['next']['time']}",
             f"状态 {r['status']}｜交叉核对 {r['crosscheck']}"]
    lines += [f"⚠ {w}" for w in r["warnings"]]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="公历换算六爻起卦干支")
    ap.add_argument("time", help='起卦钟表时间，如 "2026-10-12 14:30"')
    ap.add_argument("--tz", default=None, help="起卦地钟表时间的 UTC 偏移，如 +08:00、+00:00；不给按 +08:00")
    ap.add_argument("--zi-rule", choices=("23", "00"))
    ap.add_argument("--margin-min", type=float, default=60.0)
    ap.add_argument("--expect-year"); ap.add_argument("--expect-month")
    ap.add_argument("--expect-day"); ap.add_argument("--expect-hour")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    expect = {k: v for k, v in (("year", a.expect_year), ("month", a.expect_month),
                                ("day", a.expect_day), ("hour", a.expect_hour)) if v}
    r = convert(a.time, a.tz or TZ_ASSUMED, a.zi_rule, a.margin_min, expect or None, tz_assumed=a.tz is None)
    print(json.dumps(r, ensure_ascii=False, indent=2) if a.json else summary(r))
    return 0 if r["status"] != "error" else 2


if __name__ == "__main__":
    sys.exit(main())
