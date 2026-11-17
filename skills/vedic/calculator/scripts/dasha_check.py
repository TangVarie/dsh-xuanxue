"""Vimsottari 层级完整性检查（MD / AD / PD 三层）。

不只数行数：逐层检查数量、行星名、Vimsottari 顺序、父子归属、首尾边界与区间合法性。
数据来源优先 chart_data.json（完整时间精度），否则解析 structured_data.md。

状态只有三种：PASS 通过 / FAIL 失败（明确错误或矛盾）/ INCOMPLETE 未完成（缺层、无法比较）。
能力映射：MD 层→背景趋势；AD 层→阶段窗口；PD 层→月级窗口。下层依赖上层：上层未通过时下层最多“未完成”。
"""
import re

ORDER = ['Ketu', 'Venus', 'Sun', 'Moon', 'Mars', 'Rahu', 'Jupiter', 'Saturn', 'Mercury']
PASS, FAIL, INCOMPLETE = "PASS", "FAIL", "INCOMPLETE"
CN = {PASS: "通过", FAIL: "失败", INCOMPLETE: "未完成"}


def _cycle_from(first):
    i = ORDER.index(first)
    return ORDER[i:] + ORDER[:i]


# ---------- 读取 ----------
def tree_from_json(chart):
    dashas = chart.get("dashas")
    if not isinstance(dashas, list):
        return None
    mds = []
    for md in dashas:
        ads = []
        for ad in md.get("antardashas") or []:
            pds = [{"planet": p.get("planet"), "start": p.get("start_time") or p.get("start"),
                    "end": p.get("end_time") or p.get("end")} for p in ad.get("pratyantardashas") or []]
            ads.append({"planet": ad.get("planet"), "start": ad.get("start_time") or ad.get("start"),
                        "end": ad.get("end_time") or ad.get("end"), "pds": pds})
        start = ads[0]["start"] if ads else md.get("start")
        end = ads[-1]["end"] if ads else md.get("end")
        mds.append({"planet": md.get("planet"), "start": start, "end": end, "ads": ads,
                    "start_label": md.get("start"), "end_label": md.get("end")})
    return {"source": "chart_data.json", "mds": mds}


_MD_ROW = re.compile(r"^\|[^|]*\|\s*([A-Za-z]+)\s*\|\s*(\d{4}-\d{2}(?:-\d{2})?)\s*\|\s*(\d{4}-\d{2}(?:-\d{2})?)\s*\|\s*\d+\s*\|")
_AD_ROW = re.compile(r"^\|\s*([A-Za-z]+)-([A-Za-z]+)\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|")
_PD_ROW = re.compile(r"^\|\s*([A-Za-z]+)-([A-Za-z]+)-([A-Za-z]+)\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|")


def tree_from_md(text):
    lines = text.splitlines()
    section = None
    md_rows, ad_rows, pd_rows = [], [], []
    for ln in lines:
        if ln.startswith("### "):
            if "Vimsottari Dasha" in ln:
                section = "md"
            elif "Pratyantardasha" in ln:
                section = "pd"
            elif "Antardasha" in ln:
                section = "ad"
            else:
                section = None
            continue
        if ln.startswith("## "):
            section = None
            continue
        if section == "md":
            m = _MD_ROW.match(ln)
            if m:
                md_rows.append({"planet": m.group(1), "start": m.group(2), "end": m.group(3)})
        elif section == "ad":
            m = _AD_ROW.match(ln)
            if m:
                ad_rows.append({"md": m.group(1), "planet": m.group(2), "start": m.group(3), "end": m.group(4)})
        elif section == "pd":
            m = _PD_ROW.match(ln)
            if m:
                pd_rows.append({"md": m.group(1), "ad": m.group(2), "planet": m.group(3),
                                "start": m.group(4), "end": m.group(5)})
    return {"source": "structured_data.md", "md_rows": md_rows, "ad_rows": ad_rows, "pd_rows": pd_rows}


def _md_tree(raw):
    """把 Markdown 三张表按父子关系挂成树；挂不上的行记为 orphan。"""
    mds = [{"planet": r["planet"], "start": r["start"], "end": r["end"], "ads": []} for r in raw["md_rows"]]
    orphans = []
    by_md = {}
    for md in mds:
        by_md.setdefault(md["planet"], []).append(md)
    for r in raw["ad_rows"]:
        cands = by_md.get(r["md"], [])
        if not cands:
            orphans.append(f"AD {r['md']}-{r['planet']} 找不到父 MD")
            continue
        cands[0]["ads"].append({"planet": r["planet"], "start": r["start"], "end": r["end"], "pds": []})
    for r in raw["pd_rows"]:
        md = (by_md.get(r["md"]) or [None])[0]
        ad = next((a for a in (md["ads"] if md else []) if a["planet"] == r["ad"]), None)
        if ad is None:
            orphans.append(f"PD {r['md']}-{r['ad']}-{r['planet']} 找不到父 AD")
            continue
        ad["pds"].append({"planet": r["planet"], "start": r["start"], "end": r["end"]})
    return mds, orphans, raw


# ---------- 检查 ----------
def _days_apart(a, b):
    """两个日期字符串相差的天数（只比到日）；格式不足到日时返回 None。"""
    import datetime as _dt
    try:
        return abs((_dt.date.fromisoformat(str(a)[:10]) - _dt.date.fromisoformat(str(b)[:10])).days)
    except ValueError:
        return None


def _check_level(items, expected_first, label, parent_start, parent_end, errors, date_cmp, tol_days=0, notes=None):
    """检查一组同级区间：9 段、首段=父主星、顺序循环、连续、首尾贴合父区间、start<end。
    tol_days>0（旧版导入数据）：交界相差不超过 tol_days 天记为说明而不是错误。"""
    if len(items) != 9:
        errors.append(f"{label}: 应有 9 段，实际 {len(items)} 段")
    names = [x["planet"] for x in items]
    bad = [n for n in names if n not in ORDER]
    if bad:
        errors.append(f"{label}: 非法行星名 {bad}")
        return
    if items and expected_first and names[0] != expected_first:
        errors.append(f"{label}: 首段应为 {expected_first}，实际 {names[0]}")
    if items:
        exp = _cycle_from(names[0])[:len(items)]
        if names != exp:
            errors.append(f"{label}: 顺序不符 Vimsottari 循环（{'-'.join(names)}）")
    for x in items:
        if not (x["start"] and x["end"]) or not date_cmp(x["start"], x["end"]):
            errors.append(f"{label}: {x['planet']} 区间不合法 [{x['start']}, {x['end']})")
    for p, c in zip(items, items[1:]):
        if p["end"] != c["start"]:
            gap = _days_apart(p["end"], c["start"])
            if tol_days and gap is not None and gap <= tol_days and notes is not None:
                notes.append(f"{label}: {p['planet']}→{c['planet']} 交界差 {gap} 天（{p['end']} / {c['start']}，旧数据精度）：交界日前后 {tol_days} 天内不下结论")
            else:
                errors.append(f"{label}: {p['planet']}→{c['planet']} 不衔接（{p['end']} ≠ {c['start']}）")
    def _fits(child, parent):
        c, p = str(child), str(parent)
        return c.startswith(p[:len(c)]) or p.startswith(c[:len(p)])

    for which, child, parent in (("首段起点", items[0]["start"] if items else None, parent_start),
                                 ("末段终点", items[-1]["end"] if items else None, parent_end)):
        if child is None or parent is None or _fits(child, parent):
            continue
        gap = _days_apart(child, parent)
        if tol_days and gap is not None and gap <= tol_days and notes is not None:
            notes.append(f"{label}: {which} {child} 与父区间 {parent} 差 {gap} 天（旧数据精度）：该日前后 {tol_days} 天内不下结论")
        else:
            errors.append(f"{label}: {which} {child} 与父区间{'起点' if which == '首段起点' else '终点'} {parent} 不贴合")


def check_tree(tree, tol_days=0):
    """返回 {'source','md','ad','pd' 各层状态与错误, 'overall'}。
    tol_days：旧版导入数据（旧引擎日期有 ±1 天出入）传 1，交界差 ≤1 天记为说明（notes），不判失败。"""
    def lt(a, b):
        return str(a) < str(b)

    orphans = []
    if tree.get("source") == "structured_data.md":
        mds, orphans, raw = _md_tree(tree)
        counts = (len(raw["md_rows"]), len(raw["ad_rows"]), len(raw["pd_rows"]))
    else:
        mds = tree["mds"]
        counts = (len(mds), sum(len(m["ads"]) for m in mds), sum(len(a["pds"]) for m in mds for a in m["ads"]))
    res = {"source": tree.get("source"), "counts": {"MD": counts[0], "AD": counts[1], "PD": counts[2]}}

    # MD
    md_err = []
    if counts[0] == 0:
        res["md"] = {"status": INCOMPLETE, "errors": ["缺 MD 层（Vimsottari 大运表不存在或解析为空）"]}
    else:
        md_notes = []
        _check_level(mds, None, "MD", None, None, md_err, lt, tol_days, md_notes)
        res["md"] = {"status": FAIL if md_err else PASS, "errors": md_err, "notes": md_notes}

    # AD
    ad_err = list(o for o in orphans if o.startswith("AD"))
    if counts[1] == 0:
        res["ad"] = {"status": INCOMPLETE, "errors": ["缺 AD 层"]}
    elif res["md"]["status"] == INCOMPLETE:
        res["ad"] = {"status": INCOMPLETE, "errors": ["MD 层缺失，AD 的父子归属无法核对"] + ad_err}
    else:
        ad_notes = []
        for md in mds:
            _check_level(md["ads"], md["planet"], f"AD@{md['planet']}", md.get("start"), md.get("end"), ad_err, lt,
                         tol_days, ad_notes)
        res["ad"] = {"status": FAIL if ad_err else PASS, "errors": ad_err, "notes": ad_notes}

    # PD
    pd_err = list(o for o in orphans if o.startswith("PD"))
    if counts[2] == 0:
        res["pd"] = {"status": INCOMPLETE, "errors": ["缺 PD 层（只能给到 AD 阶段窗口）"]}
    elif res["ad"]["status"] == INCOMPLETE:
        res["pd"] = {"status": INCOMPLETE, "errors": ["AD/MD 层缺失，PD 的父子归属无法核对"] + pd_err}
    else:
        pd_notes = []
        for md in mds:
            for ad in md["ads"]:
                _check_level(ad["pds"], ad["planet"], f"PD@{md['planet']}-{ad['planet']}",
                             ad["start"], ad["end"], pd_err, lt, tol_days, pd_notes)
        res["pd"] = {"status": FAIL if pd_err else PASS, "errors": pd_err, "notes": pd_notes}

    sts = [res[k]["status"] for k in ("md", "ad", "pd")]
    res["overall"] = FAIL if FAIL in sts else (INCOMPLETE if INCOMPLETE in sts else PASS)
    res["capabilities"] = {
        "背景趋势（MD）": res["md"]["status"],
        "阶段窗口（MD×AD）": res["ad"]["status"] if res["md"]["status"] == PASS else
        (FAIL if res["md"]["status"] == FAIL else INCOMPLETE),
        "月级窗口（PD）": res["pd"]["status"] if res["ad"]["status"] == PASS else
        (FAIL if FAIL in (res["md"]["status"], res["ad"]["status"]) else INCOMPLETE),
    }
    return res


def format_result(res):
    out = [f"数据源: {res['source']}  行数 MD={res['counts']['MD']} AD={res['counts']['AD']} PD={res['counts']['PD']}"]
    for k, name in (("md", "MD 层"), ("ad", "AD 层"), ("pd", "PD 层")):
        r = res[k]
        out.append(f"  {name}: {CN[r['status']]}")
        for e in r["errors"][:8]:
            out.append(f"    - {e}")
        for e in r.get("notes", [])[:4]:
            out.append(f"    · {e}")
        if len(r["errors"]) > 8:
            out.append(f"    - …另有 {len(r['errors']) - 8} 条")
    out.append("能力:")
    for cap, st in res["capabilities"].items():
        out.append(f"  {cap}: {CN[st]}")
    out.append(f"总体: {CN[res['overall']]}")
    return "\n".join(out)


def exit_code(status):
    return {PASS: 0, FAIL: 1, INCOMPLETE: 2}[status]
