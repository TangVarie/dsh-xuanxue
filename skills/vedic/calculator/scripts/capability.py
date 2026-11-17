"""capability.py — 一张盘的「能力范围」（formatter 写进 structured_data.md，check_chart.py 打印）。

规则正本：分盘启用见 shared/divisional.md §1（有效精度矩阵 × 边界审计）；
Dasha 窗口的时间敏感度见 shared/time_window.md §1。这里只把两份正本落到具体一张盘上，不另立规则。
纯标准库，不调用星历。
"""

NAK_SPAN = 360.0 / 27.0
LORDS = ['Ketu', 'Venus', 'Sun', 'Moon', 'Mars', 'Rahu', 'Jupiter', 'Saturn', 'Mercury']
YEARS = {'Ketu': 7, 'Venus': 20, 'Sun': 6, 'Moon': 10, 'Mars': 7, 'Rahu': 18, 'Jupiter': 16, 'Saturn': 19, 'Mercury': 17}
SIDEREAL_YEAR = 365.256364

# shared/divisional.md §1 的矩阵（改规则改那份正本，再同步这里）
MATRIX = {
    "±分钟级": {"D9": "启用", "D10": "启用", "D5": "启用", "D4": "启用", "D7": "参考", "D30": "不启用", "D60": "不启用"},
    "±5分钟": {"D9": "启用", "D10": "启用", "D5": "启用", "D4": "启用", "D7": "参考", "D30": "不启用", "D60": "不启用"},
    "±15分钟": {"D9": "启用", "D10": "参考", "D5": "参考", "D4": "参考", "D7": "不启用", "D30": "不启用", "D60": "不启用"},
    "±1小时": {"D9": "参考", "D10": "不启用", "D5": "不启用", "D4": "不启用", "D7": "不启用", "D30": "不启用", "D60": "不启用"},
    "不确定": {"D9": "参考", "D10": "不启用", "D5": "不启用", "D4": "不启用", "D7": "不启用", "D30": "不启用", "D60": "不启用"},
}

# shared/time_window.md §1：出生时间误差带来的 Dasha 日期整体平移（天）
PD_OK, PD_COND = 7, 30        # PD 月级：≤7 天可用；≤30 天条件使用；更大不启用
AD_OK, AD_COND = 30, 120      # AD 阶段：≤30 天可用；≤120 天条件使用；更大只作背景
MD_COND = 365                 # MD 背景：平移超过 1 年时大运交界也标条件使用


def precision_label(minutes):
    if minutes is None:
        return "不确定"
    if minutes <= 2:
        return "±分钟级"
    if minutes <= 5:
        return "±5分钟"
    if minutes <= 15:
        return "±15分钟"
    if minutes <= 60:
        return "±1小时"
    return "不确定"


def dasha_shift_days(chart, minutes):
    """有效误差 ±minutes 分钟 → Vimsottari 全部日期的最大平移（天）。返回 (天数, 起运主星说明) 或 (None, None)。

    时间轴在宿界两侧是连续的：Moon 每走 1°，日期平移 = 1°/13°20′ × 所在宿主星年数。
    误差范围跨宿时，两侧主星的年数取较大者（只有出生时正在走的那段大运主星不同，那段已经过去）。"""
    moon = (chart.get("planets") or {}).get("Moon")
    if minutes is None or not isinstance(moon, dict) or not isinstance(moon.get("longitude"), (int, float)):
        return None, None
    speed = abs(moon.get("speed") or 13.176)  # 度/日
    move = minutes / 1440.0 * speed
    lon = moon["longitude"]
    lords = {LORDS[int(((lon + d) % 360) // NAK_SPAN) % 9] for d in (-move, 0.0, move)}
    years = max(YEARS[x] for x in lords)
    lord = LORDS[int(lon // NAK_SPAN) % 9]
    label = lord if len(lords) == 1 else f"{lord}（误差范围跨宿：{'/'.join(sorted(lords))}，按较大年数算）"
    return move / NAK_SPAN * years * SIDEREAL_YEAR, label


def _audit_chart(chart, key):
    audit = chart.get("divisional_boundary_audit")
    if not isinstance(audit, dict) or audit.get("status") != "ok":
        return None
    return audit.get("charts", {}).get(key)


def table(chart, minutes, transit_ok=None, dasha_levels=None, legacy=False):
    """返回 [(能力, 状态, 说明)]。状态取值：可用 / 条件使用 / 参考 / 不启用 / 未完成。

    minutes: 有效误差（分钟）；None = 未声明（旧数据）
    dasha_levels: {"md": "PASS|FAIL|INCOMPLETE", "ad": …, "pd": …}（dasha_check 结果），None 表示未检查
    """
    rows = []
    label = precision_label(minutes) if minutes is not None else None
    unknown = "有效精度未知（旧数据未声明），按未验证处理"

    # D1 上升 / 宫位
    d1 = _audit_chart(chart, "D1")
    if d1 is None:
        rows.append(("D1 行星星座与度数", "可用", ""))
        rows.append(("D1 上升/宫位/宫主", "条件使用", "没有边界审计，上升稳定性未验证"))
    else:
        rows.append(("D1 行星星座与度数", "可用", ""))
        if d1.get("stable"):
            rows.append(("D1 上升/宫位/宫主", "可用", ""))
        else:
            alt = "→".join(d1.get("observed_signs") or [])
            rows.append(("D1 上升/宫位/宫主", "条件使用",
                         f"审计范围内上升换座（{alt}）：宫位、宫主、行运落宫按两种上升分别写，或先校时"))

    # Vimsottari
    shift, lord = dasha_shift_days(chart, minutes)
    lv = dasha_levels or {}

    def base(level):
        st = lv.get(level)
        return {"PASS": "可用", "FAIL": "不启用", "INCOMPLETE": "未完成", None: "可用"}.get(st, "未完成")

    md_st = base("md")
    md_note = "" if md_st == "可用" else "层级检查未通过"
    if md_st == "可用" and shift is not None and shift > MD_COND:
        md_st, md_note = "条件使用", f"出生时间 ±{minutes} 分钟 → 大运交界可平移约 ±{shift:.0f} 天，交界前后这段时间内不定"
    rows.append(("Vimsottari 大运背景（MD）", md_st, md_note))
    ad_st, pd_st = base("ad"), base("pd")
    if shift is None:
        ad_note = pd_note = unknown if minutes is None else ""
        if minutes is None:
            ad_st = "条件使用" if ad_st == "可用" else ad_st
            pd_st = "条件使用" if pd_st == "可用" else pd_st
    else:
        s = f"出生时间 ±{minutes} 分钟 → Dasha 日期整体可平移约 ±{shift:.0f} 天（起运主星 {lord}）"
        ad_note = pd_note = s
        if ad_st == "可用":
            ad_st = "可用" if shift <= AD_OK else ("条件使用" if shift <= AD_COND else "不启用")
        if pd_st == "可用":
            pd_st = "可用" if shift <= PD_OK else ("条件使用" if shift <= PD_COND else "不启用")
        if ad_st == "条件使用":
            ad_note += "；AD 交界前后这段时间内不定"
        if pd_st == "条件使用":
            pd_note += "；PD 交界前后这段时间内不下月级结论"
        elif pd_st == "不启用" and base("pd") == "可用":
            pd_note += "；只给 AD 阶段窗口"
    if base("ad") != "可用":
        ad_note = "层级检查未通过"
    if base("pd") != "可用":
        pd_note = "PD 缺失或层级未通过，最多给 AD 阶段窗口"
    rows.append(("Vimsottari 阶段窗口（AD）", ad_st, ad_note))
    rows.append(("Vimsottari 月级窗口（PD）", pd_st, pd_note))

    # 分盘：精度矩阵 × 边界审计
    for key in ("D9", "D10", "D4", "D5"):
        allow = MATRIX[label][key] if label else None
        it = _audit_chart(chart, key)
        if allow == "不启用":
            rows.append((f"{key} 宫位/宫主/形态", "不启用", f"有效精度 {label}（divisional §1）"))
            continue
        if it is None:
            rows.append((f"{key} 宫位/宫主/形态", "条件使用", "边界审计未完成，输入稳定性未验证"
                         + ("" if label else "；" + unknown)))
            continue
        if not it.get("stable"):
            alt = "→".join(it.get("observed_signs") or [])
            rows.append((f"{key} 宫位/宫主/形态", "条件使用", f"审计范围内 Lagna 换座（{alt}），分候选写"
                         + ("；且精度档只到「参考」" if allow == "参考" else "")))
        elif allow == "参考":
            rows.append((f"{key} 宫位/宫主/形态", "参考", f"有效精度 {label}：可用，须标「时间精度有限，仅供参考」"))
        else:
            rows.append((f"{key} 宫位/宫主/形态", "可用" if label else "条件使用", "" if label else unknown))
    if label:
        for key in ("D7", "D30", "D60"):
            allow = MATRIX[label][key]
            rows.append((key, {"启用": "可用"}.get(allow, allow),
                         "D60 只作行星星座线索，不启用 Lagna 与宫位" if key == "D60" else ""))

    if transit_ok is not None:
        rows.append(("当前行运", "可用" if transit_ok else "未完成",
                     "使用前跑 check_freshness.py 做时效检查" if transit_ok else "没有过运快照：transit.py --chart … --write"))
    return rows


def render_md(rows):
    out = ["| 能力 | 状态 | 说明 |", "|------|------|------|"]
    for k, s, d in rows:
        out.append(f"| {k} | {s} | {d} |")
    return out
