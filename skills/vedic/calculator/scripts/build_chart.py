#!/usr/bin/env python3
"""build_chart.py — 排盘一次计算，同时写出 chart_data.json 与 structured_data.md。

完整出生信息:
  python build_chart.py --date 1990-05-21 --time 14:23 --tz Asia/Shanghai \\
      --lat 39.9042 --lon 116.4074 --place 北京 --source 出生证 --out <工作目录>
  （--lat 纬度在前，--lon 经度在后；上面是虚构示例）
  可选: --declared-min 15 --declared-text "大概±15分钟" --clock-type 标准时 --gender 男 --relationship 单身

只有出生日期（合盘一方缺时间等）:
  python build_chart.py --date-only --date 1995-03-14 --tz Asia/Shanghai --lat 31.23 --lon 121.47 --out <目录>
  只输出全天稳定的行星星座/宿；上升、宫位、分盘、Dasha 一律标「不适用/未计算」，不补时刻。

从已有 chart_data.json 重新生成 structured_data.md（合并 Shadbala、导入旧盘之后用）:
  python build_chart.py --from-json <目录>/chart_data.json

时间来源（--source）取值：出生证 / 医院记录 / 家人明确记忆 / 家人记忆 / 本人记忆 / 模糊记忆 / 未追问 / 未知 / 校时
  校时：rectifier 校准后重排时使用，--declared-min 传校准达成的窗口半宽，--original-source 记原来源（两项都必填）

夏令时切换当天:
  报时是未拨快的标准时 → --clock-type 标准时（脚本换成当地钟表时间）
  钟表时刻落在夏令时结束当晚的重复时段（同一时刻出现两次）→ 加 --repeated-hour 夏令时|标准时 指明是哪一次
有效误差 = max(用户声明, 来源下限)；审计范围 = 有效误差（见 shared/data_contract.md）。
退出码: 0 写出且自检通过 / 1 自检有失败项 / 2 参数或计算错误
"""
import argparse
import copy
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import chart_io as cio  # noqa: E402


def _settings(ayanamsa_value):
    return {
        "ayanamsa": "True Chitrapaksha (SIDM_TRUE_CITRA)",
        "ayanamsa_value_deg": ayanamsa_value,
        "node": "Mean Node",
        "house_system": "Whole Sign",
        "ephemeris": "Swiss Ephemeris, PyJHora PLANET_FLAGS",
    }


class InputError(ValueError):
    """输入有问题（不是计算出错）：消息直接给用户看。"""


def _check_inputs(a):
    """排盘前把输入查一遍：格式、范围、经纬度是否像是传反了。返回要提示的话（不拦截）。"""
    import re
    import pytz
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", a.date or ""):
        raise InputError(f"出生日期要写成 YYYY-MM-DD，收到的是「{a.date}」")
    try:
        d0 = datetime.strptime(a.date, "%Y-%m-%d")
    except ValueError:
        raise InputError(f"出生日期「{a.date}」不是一个存在的日期")
    if not 1800 <= d0.year <= 2399:
        raise InputError(f"出生年份 {d0.year} 超出星历文件范围（1800–2399）")
    if not a.date_only:
        if re.fullmatch(r"\d{1,2}:\d{2}:\d{2}", a.time or ""):
            raise InputError(f"出生时间只到分钟（HH:MM）。「{a.time}」带了秒，请四舍五入到分钟再传")
        if not re.fullmatch(r"\d{1,2}:\d{2}", a.time or ""):
            raise InputError(f"出生时间要写成 24 小时制 HH:MM，收到的是「{a.time}」")
        hh, mm = map(int, a.time.split(":"))
        if hh > 23 or mm > 59:
            raise InputError(f"出生时间「{a.time}」超出范围（00:00–23:59；午夜 24:00 请写成次日 00:00）")
    try:
        tz = pytz.timezone(a.tz)
    except pytz.exceptions.UnknownTimeZoneError:
        raise InputError(f"不认识的时区「{a.tz}」：要用 IANA 时区名，例如中国大陆 Asia/Shanghai、印度 Asia/Kolkata、"
                         "美东 America/New_York（不接受 +08:00、Beijing 这类写法）")
    if not -90 <= a.lat <= 90:
        hint = "；--lat 是纬度、--lon 是经度，看起来两个值传反了" if -90 <= a.lon <= 90 and -180 <= a.lat <= 180 else ""
        raise InputError(f"纬度 --lat {a.lat} 超出范围（-90 到 90）{hint}")
    if not -180 <= a.lon <= 180:
        raise InputError(f"经度 --lon {a.lon} 超出范围（-180 到 180，西经为负）")
    warns = []
    try:   # 经度与时区对不上：多半是经纬度传反或时区选错。只提示，不拦截（一国一时区的地方本来就会差很多）
        probe = tz.localize(datetime(d0.year, d0.month, d0.day, 12, 0), is_dst=False)
        std_h = (probe.utcoffset() - (probe.dst() or timedelta(0))).total_seconds() / 3600.0
        gap = abs(((a.lon - std_h * 15.0) + 180) % 360 - 180)
        if gap > 50:
            warns.append(f"经度 {a.lon} 与时区 {a.tz}（标准时 UTC{std_h:+g}，中央经线约 {std_h * 15:g}°）相差 {gap:.0f}°："
                         "请确认 --lat / --lon 没有传反、时区没有选错")
    except Exception:
        pass
    return warns


def _resolve_clock(date_s, time_s, tz_s, clock_type, repeated_hour=None):
    """把报时换成计算用的当地钟表时间。返回 (time_used, utc_offset, is_dst, note, date_used, is_dst_pref)。

    - 标准时：先按该地标准时偏移换成 UTC，再换回当地钟表时间（夏令时期间 = 报时 + 1 小时；
      夏令时切换那几个小时也照此处理，不会落进"钟表上不存在"的时刻）。
    - 当地钟表时间：钟表上不存在的时刻（夏令时开始时拨快跳过）报错；
      重复的时刻（夏令时结束时拨回）必须用 --repeated-hour 指明是哪一次。
    is_dst_pref 只在钟表时刻重复时不是 None，交给 engine 用。
    """
    import pytz
    tz = pytz.timezone(tz_s)
    dt = datetime.strptime(f"{date_s} {time_s}", "%Y-%m-%d %H:%M")
    note = ""
    if clock_type == "标准时":
        probe = tz.localize(dt, is_dst=False)
        std_off = probe.utcoffset() - (probe.dst() or timedelta(0))
        loc = tz.normalize(pytz.utc.localize(dt - std_off).astimezone(tz))
        wall = loc.replace(tzinfo=None)
        if wall != dt:
            day = "" if wall.date() == dt.date() else f"{wall:%Y-%m-%d} "
            note = (f"报时为标准时，出生时刻处于夏令时，按 +{loc.dst()} 换成当地钟表时间 {day}{wall:%H:%M}")
        dt = wall
    else:
        try:
            loc = tz.localize(dt, is_dst=None)
        except pytz.exceptions.NonExistentTimeError:
            raise InputError(
                f"{dt:%Y-%m-%d %H:%M} 这个钟表时刻在 {tz_s} 不存在：当天夏令时开始，钟表被拨快跳过了这一段。"
                "如果出生记录写的是未拨快的标准时，加 --clock-type 标准时 重排；否则请核对时间。")
        except pytz.exceptions.AmbiguousTimeError:
            if repeated_hour not in ("夏令时", "标准时"):
                raise InputError(
                    f"{dt:%Y-%m-%d %H:%M} 这个钟表时刻在 {tz_s} 出现过两次：当晚夏令时结束，钟表被拨回。"
                    "是拨回之前的那一次（还在夏令时）→ 加 --repeated-hour 夏令时；"
                    "是拨回之后的那一次（已回到标准时）→ 加 --repeated-hour 标准时。两次相差一小时，分不清时先问用户。")
            loc = tz.localize(dt, is_dst=(repeated_hour == "夏令时"))
            note = f"钟表时刻在夏令时结束当晚出现两次，按用户确认取{'拨回前（夏令时）' if repeated_hour == '夏令时' else '拨回后（标准时）'}的那一次"
    # 钟表时刻是否重复（标准时换算后也可能落在重复时段：此时它就是拨回后的那一次）
    pref = None
    try:
        tz.localize(dt, is_dst=None)
    except pytz.exceptions.AmbiguousTimeError:
        pref = bool(loc.dst())
    except pytz.exceptions.NonExistentTimeError:
        pass
    return dt.strftime("%H:%M"), str(loc.utcoffset()), bool(loc.dst()), note, dt.strftime("%Y-%m-%d"), pref


def render_md(doc):
    """由 chart_data.json 的内容生成 structured_data.md（完整盘）。"""
    from formatter import format_structured_data
    chart = copy.deepcopy(doc["chart"])
    cio.restore_int_keys(chart)
    for planet, ov in (doc.get("overrides", {}).get("shadbala") or {}).items():
        sb = chart.get("shadbala")
        if isinstance(sb, dict) and planet in sb and isinstance(sb[planet], dict):
            sb[planet]["_override"] = {**ov.get("adopted", {}), "source": ov.get("source", "PDF")}
    inp = doc["input"]
    meta = {
        "dob": inp["date"], "dob_reported": inp.get("date_reported"),
        "time": inp["time_used"], "time_reported": inp.get("time_reported"),
        "clock_type": inp.get("clock_type"), "place": inp.get("place", "未提供"),
        "lat": inp["lat"], "lon": inp["lon"], "tz": inp.get("tz"), "utc_offset": inp.get("utc_offset"),
        "time_source": inp.get("time_source"), "original_source": inp.get("original_source"),
        "declared_precision_text": inp.get("declared_precision_text"),
        "effective_minutes": inp.get("effective_minutes"), "precision_note": inp.get("precision_note"),
        "chart_id": doc.get("chart_id"), "audit_id": doc.get("audit_id"),
        "engine_version": doc.get("engine_version"), "rules_version": doc.get("rules_version"),
        "generated_at": doc.get("generated_at"),
    }
    if doc.get("provenance", {}).get("source") == "legacy_md_import":
        meta["precision_note"] = (meta.get("precision_note") or "") + "（旧版 Markdown 导入；缺项按缺失处理，未重新验证）"
    user = {k: v for k, v in (doc.get("user") or {}).items()}
    return format_structured_data(chart, doc.get("transit"), meta, user)


# ---------------- 完整盘 ----------------
def build_full(a):
    from engine import calculate_full_chart
    from transit import calc_transit
    time_used, utc_off, is_dst, clock_note, date_used, dst_pref = _resolve_clock(
        a.date, a.time, a.tz, a.clock_type, a.repeated_hour)
    if a.source == "校时" and not a.original_source:
        raise InputError("来源为「校时」时还要用 --original-source 写明校时前的原始时间来源（如 家人记忆）")
    eff, prec_note = cio.resolve_precision(a.source, a.declared_min)
    y, mo, d = map(int, date_used.split("-"))
    hh, mm = map(int, time_used.split(":"))
    chart = calculate_full_chart(y, mo, d, hh, mm, a.lat, a.lon, a.tz, uncertainty_minutes=eff, is_dst=dst_pref)
    if a.no_transit:
        transit = cio.missing("not_computed", "调用时关闭了过运计算")
    else:
        try:
            transit = calc_transit(chart["lagna"]["sign_idx"], chart["planets"]["Moon"]["sign_idx"], a.tz,
                                   on_date=a.transit_date)
        except Exception as exc:  # 过运失败只限制行运能力
            transit = cio.missing("failed", str(exc)[:200])
    inp = {
        "mode": "full", "date": date_used, "time_reported": a.time, "time_used": time_used,
        "clock_type": a.clock_type, "tz": a.tz, "utc_offset": utc_off, "is_dst": is_dst,
        "lat": a.lat, "lon": a.lon, "place": a.place or "未提供",
        "time_source": a.source, "original_source": a.original_source, "declared_minutes": a.declared_min,
        "declared_precision_text": a.declared_text or (f"±{a.declared_min}分钟" if a.declared_min else "未声明"),
        "effective_minutes": eff, "effective_label": cio.precision_label(eff),
        "audit_minutes": (chart.get("divisional_boundary_audit") or {}).get("uncertainty_minutes"),
        "precision_note": "；".join(x for x in (prec_note, clock_note) if x),
    }
    if date_used != a.date:          # 标准时在午夜前后换算跨了日：计算用日期与报的日期不同，两者都留
        inp["date_reported"] = a.date
    if dst_pref is not None:         # 只有钟表时刻重复时才写，避免改变其他盘的 chart_id
        inp["repeated_hour"] = "夏令时" if dst_pref else "标准时"
    settings = _settings(chart.get("ayanamsa"))
    chart_id, audit_id = cio.compute_ids(inp, settings)
    user = {
        "gender": a.gender or cio.missing("not_provided"),
        "relationship": a.relationship or cio.missing("not_provided"),
    }
    doc = {
        "schema": cio.SCHEMA_VERSION, "chart_id": chart_id, "audit_id": audit_id,
        "generated_at": cio.now_iso(), "engine_version": cio.ENGINE_VERSION,
        "rules_version": cio.RULES_VERSION, "input": inp, "settings": settings, "user": user,
        "chart": chart, "transit": transit, "overrides": {},
        "provenance": {"source": "vedic-calculator"},
    }
    return cio.to_jsonable(doc)


# ---------------- 只有日期 ----------------
def build_date_only(a):
    import engine as eng
    eng._ensure_swe_state()
    y, mo, d = map(int, a.date.split("-"))
    import pytz
    _tz = pytz.timezone(a.tz)
    _jds, _noon_i = [], 0
    for minute in list(range(0, 24 * 60, 30)) + [23 * 60 + 59]:
        naive = datetime(y, mo, d) + timedelta(minutes=minute)
        try:
            awares = [_tz.localize(naive, is_dst=None)]
        except pytz.exceptions.AmbiguousTimeError:      # 夏令时结束当晚：两次都采样
            awares = [_tz.localize(naive, is_dst=True), _tz.localize(naive, is_dst=False)]
        except pytz.exceptions.NonExistentTimeError:    # 夏令时开始：钟表上没有这一刻，跳过
            continue
        for aw in awares:
            u = aw.astimezone(pytz.utc)
            if minute == 720:
                _noon_i = len(_jds)
            _jds.append(eng.swe.julday(u.year, u.month, u.day, u.hour + u.minute / 60.0))
    samples = []
    for jd in _jds:
        pos = {}
        for name, pid in eng.PLANETS_SWE.items():
            p = eng.calc_planet(jd, pid)
            pos[name] = (p["longitude"], p["retrograde"])
        r = eng.swe.calc_ut(jd, eng.swe.MEAN_NODE, eng.PLANET_FLAGS)[0][0]
        pos["Rahu"] = (r, True)
        pos["Ketu"] = ((r + 180) % 360, True)
        samples.append(pos)
    noon = samples[_noon_i]
    planets = {}
    unstable = []
    for name in cio.PLANETS9:
        lons = [s[name][0] for s in samples]
        signs = {int(l // 30) for l in lons}
        naks = {int(l // (360 / 27)) for l in lons}
        retro = {s[name][1] for s in samples}
        lon_noon = noon[name][0]
        entry = {"house": cio.missing("not_applicable", "无出生时间，无上升")}
        if len(signs) == 1:
            si = signs.pop()
            entry.update({"sign": cio.SIGNS[si], "sign_idx": si})
        else:
            entry["sign"] = cio.missing("not_computed", "当日内换座：" + "→".join(cio.SIGNS[x] for x in sorted(signs)))
            unstable.append(f"{name} 星座")
        if len(naks) == 1:
            ni = naks.pop()
            entry["nakshatra"] = {"name": cio.NAKSHATRAS[ni]}
        else:
            entry["nakshatra"] = cio.missing("not_computed", "当日内换宿")
            unstable.append(f"{name} 宿")
        if name == "Moon":
            entry["longitude"] = cio.missing("not_applicable", "Moon 当日移动约 12-15°，无出生时间不给度数")
        else:
            entry["longitude"] = lon_noon
            entry["degree_note"] = "当地正午位置；当日移动量见 day_span_deg"
            span = max(lons) - min(lons)
            entry["day_span_deg"] = round(span if span < 180 else 360 - span, 3)
        entry["retrograde"] = retro.pop() if len(retro) == 1 else cio.missing("not_computed", "当日内转向")
        planets[name] = entry
    na = cio.missing("not_applicable", "只有出生日期")
    chart = {
        "lagna": na, "planets": planets,
        "divisional_boundary_audit": na, "dashas": cio.missing("not_computed", "Vimsottari 起点取决于 Moon 精确经度"),
        "karakas": cio.missing("not_computed", "Karaka 排序取决于精确度数"),
        "house_lords": na, "special_points": na, "sav": na, "shadbala": na,
        "stability": {"sampled": "当地 00:00-23:59 每 30 分钟", "unstable": unstable},
    }
    inp = {
        "mode": "date_only", "date": a.date, "time_reported": None, "time_used": None,
        "clock_type": cio.missing("not_applicable"), "tz": a.tz, "lat": a.lat, "lon": a.lon,
        "place": a.place or "未提供", "time_source": "无出生时间", "declared_minutes": None,
        "effective_minutes": None, "effective_label": "不确定", "audit_minutes": None,
    }
    settings = _settings(None)
    chart_id, audit_id = cio.compute_ids(inp, settings)
    doc = {
        "schema": cio.SCHEMA_VERSION, "chart_id": chart_id, "audit_id": audit_id,
        "generated_at": cio.now_iso(), "engine_version": cio.ENGINE_VERSION,
        "rules_version": cio.RULES_VERSION, "input": inp, "settings": settings,
        "user": {"gender": a.gender or cio.missing("not_provided")},
        "chart": chart, "transit": cio.missing("not_applicable", "无上升，行运宫位不可算"),
        "overrides": {}, "provenance": {"source": "vedic-calculator(date-only)"},
    }
    return cio.to_jsonable(doc)


def render_date_only_md(doc):
    inp, ch = doc["input"], doc["chart"]
    L = ["## 元信息\n", "```",
         f"出生日期: {inp['date']}", "出生时间: 未提供（只有日期）",
         f"出生地点: {inp.get('place')} ({inp['lon']}, {inp['lat']})［括号内为 经度, 纬度］", f"出生时区: {inp.get('tz')}",
         "有效精度: 不确定（无出生时间）", "读盘方式: vedic-calculator直接计算（仅日期模式）",
         f"数据版本: chart_id={doc['chart_id']} · 引擎 {doc['engine_version']} · 规则 {doc['rules_version']}",
         "机器可读数据: chart_data.json", "```\n",
         "## 行星（当日稳定性检查）\n",
         f"> 采样：{ch['stability']['sampled']}。全天同一星座/宿才给出，否则标「未计算」；不补出生时刻。\n",
         "| 行星 | 星座 | Nakshatra | 逆行 | 宫位 |", "|------|------|-----------|------|------|"]
    for name in cio.PLANETS9:
        p = ch["planets"][name]
        sign = cio.missing_label(p["sign"]) if cio.is_missing(p["sign"]) else p["sign"]
        nak = cio.missing_label(p["nakshatra"]) if cio.is_missing(p["nakshatra"]) else p["nakshatra"]["name"]
        rt = p["retrograde"]
        rt = cio.missing_label(rt) if cio.is_missing(rt) else ("R" if rt else "D")
        L.append(f"| {name} | {sign} | {nak} | {rt} | 不适用 |")
    L += ["", "## 能力范围\n", "| 能力 | 状态 |", "|------|------|",
          "| 上升、宫位、宫主、分盘 | 不适用（无出生时间） |",
          "| Vimsottari Dasha | 未计算（起点取决于 Moon 精确经度） |",
          "| Chara Karaka / DK | 未计算（排序取决于精确度数） |",
          f"| 行星星座 | {'全部稳定' if not ch['stability']['unstable'] else '部分不稳定：' + '、'.join(ch['stability']['unstable'])} |",
          "| 合盘可用层 | 稳定行星的星座/宿与对方盘的接触；Moon 宿稳定时可做月宿筛查 |", ""]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date")
    ap.add_argument("--time", help="HH:MM，报时（按 --clock-type 解释）")
    ap.add_argument("--tz", help="IANA 时区名，如 Asia/Shanghai")
    ap.add_argument("--lat", type=float, help="纬度（-90 到 90，北纬为正）")
    ap.add_argument("--lon", type=float, help="经度（-180 到 180，东经为正）")
    ap.add_argument("--place", default=None)
    ap.add_argument("--source", default="未追问", help="时间来源；校准后写「校时」并配 --declared-min 与 --original-source")
    ap.add_argument("--original-source", default=None, help="校时前的原始时间来源（来源为「校时」时填写）")
    ap.add_argument("--declared-min", type=int, default=None, help="用户声明的误差（分钟）")
    ap.add_argument("--declared-text", default=None, help="用户原话，如 '大概晚上八点半'")
    ap.add_argument("--clock-type", default="当地钟表时间", choices=["当地钟表时间", "标准时"])
    ap.add_argument("--repeated-hour", default=None, choices=["夏令时", "标准时"],
                    help="钟表时刻落在夏令时结束当晚的重复时段时，指明是拨回前（夏令时）还是拨回后（标准时）的那一次")
    ap.add_argument("--gender", default=None)
    ap.add_argument("--relationship", default=None)
    ap.add_argument("--out", default=".", help="输出目录")
    ap.add_argument("--date-only", action="store_true")
    ap.add_argument("--no-transit", action="store_true")
    ap.add_argument("--transit-date", default=None,
                    help="过运快照日期 YYYY-MM-DD（取当地正午）；缺省为当前时刻。用于复现或查询指定日期")
    ap.add_argument("--from-json", default=None, help="已有 chart_data.json，只重新生成 structured_data.md")
    a = ap.parse_args()

    try:
        if a.from_json:
            doc = cio.load_doc(a.from_json)
            out_dir = os.path.dirname(os.path.abspath(a.from_json))
            if doc.get("provenance", {}).get("source") == "legacy_md_import":
                print("这是旧版 Markdown 导入的数据，缺少完整计算字段，不能重新生成完整的 structured_data.md；"
                      "保留导入时生成的 structured_data.md。出生信息齐全时请用 build_chart.py 重排。", file=sys.stderr)
                sys.exit(2)
        else:
            need = ["date", "tz", "lat", "lon"] + ([] if a.date_only else ["time"])
            miss = [k for k in need if getattr(a, k) in (None, "")]
            if miss:
                ap.error("缺少参数: " + ", ".join("--" + m for m in miss))
            for w in _check_inputs(a):
                print("⚠️ " + w, file=sys.stderr)
            doc = build_date_only(a) if a.date_only else build_full(a)
            out_dir = a.out
            os.makedirs(out_dir, exist_ok=True)
            cio.save_doc(doc, os.path.join(out_dir, "chart_data.json"))
        md = render_date_only_md(doc) if doc["input"].get("mode") == "date_only" else render_md(doc)
    except InputError as exc:
        print(f"输入有误（未写出任何文件）: {exc}", file=sys.stderr)
        sys.exit(2)
    except Exception as exc:
        print(f"计算失败: {exc}", file=sys.stderr)
        sys.exit(2)
    md_path = os.path.join(out_dir, "structured_data.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"[写出] {os.path.join(out_dir, 'chart_data.json')}")
    print(f"[写出] {md_path}")
    print(f"chart_id={doc['chart_id']} audit_id={doc['audit_id']} 模式={doc['input'].get('mode')}")
    import re
    fails = [ln for ln in md.splitlines() if re.match(r"^\s*\d+[a-z]?\.\s", ln) and "失败" in ln]
    if fails:
        print("自检失败项:")
        for ln in fails:
            print("  " + ln.strip())
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
