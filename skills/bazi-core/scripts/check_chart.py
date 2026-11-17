#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_chart.py —— 四柱的历法一致性核验、扫描错字修复、批量核验。不做解读，不判真假人。

只回答确定性问题：这组干支合不合遁法；在给定年份范围和口径下，哪些时间区间能排出它；
所称的大运、起运岁数、出生年是否由【同一个】候选同时满足。

用法
  1) 核一个盘
     python3 check_chart.py --pillars "乙未 己卯 丁丑 庚戌" --gender male --qiyun 4 --born 1955
     python3 check_chart.py --pillars "甲辰 丙寅 戊戌"              # 三柱：时柱未知，按全天找
     python3 check_chart.py --pillars "甲辰 丙寅 戊戌 壬戌" --at "2024-02-04 20:00"   # 另核"这个时刻排出来是不是这四柱"
  2) 修扫描错字
     python3 check_chart.py --repair "乙已丁庚未卯丑戌"        （先四干后四支）
     python3 check_chart.py --repair "王辰 王子 甲辰 丁卯"      （逐柱）
  3) 批量
     python3 check_chart.py --batch charts.txt
     每行：四柱[,性别][,起运岁][,出生年]   例：辛巳 丁酉 乙亥 己卯,乾,7,1971   （# 开头为注释）

口径
  反查按北京时间、不做经度修正；换日默认 23 点（--ziday 0 改为晚子时口径）。
  年柱按立春、月柱按十二节，交节时刻精确到分钟，不再用"每天中午"代表全天。
  找不到候选只说明"在所查年份范围和口径下没有"，不等于历法上绝对不存在。
  通过也只说明历法与所给信息一致，不说明这是不是真人命例。

退出码（单盘）：0 通过；1 发现不一致（结构非法/遁法不符/范围内未找到/与所称信息不符）；
             2 无法完成（输入缺失或格式错）；3 运行错误。
批量与修复：0 跑完；2 文件或输入错误；3 运行错误。
"""
import argparse
import collections
import datetime as _dt
import itertools
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chart_core as C  # noqa: E402

try:  # 输出接到 head 之类时安静退出
    import signal
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
except (AttributeError, ValueError):
    pass

G, Z, JZ = C.G, C.Z, C.JZ
DEFAULT_RANGE = (1840, 2030)
WIDE_RANGE = (1600, 2200)
VERDICTS = ["通过", "结构非法", "遁法不符", "范围内未找到", "与所称信息不符", "输入缺失或无法检查"]

OCR_G = {
    "王": "壬", "工": "壬", "士": "壬", "玉": "壬", "任": "壬",
    "已": "己", "巳": "己", "巴": "己", "乙": "乙己", "己": "己乙",
    "戌": "戊", "成": "戊", "戍": "戊", "茂": "戊",
    "内": "丙", "两": "丙", "葵": "癸", "奏": "癸", "发": "癸",
    "申": "甲", "田": "甲", "由": "甲", "幸": "辛", "康": "庚", "了": "丁", "十": "丁",
}
OCR_Z = {
    "已": "巳", "己": "巳", "巴": "巳", "成": "戌", "戊": "戌", "戍": "戌",
    "西": "酉", "末": "未", "中": "申", "甲": "申", "串": "申",
    "于": "子", "孑": "子", "干": "午", "千": "午", "牛": "午",
    "卵": "卯", "展": "辰", "长": "辰", "反": "辰", "玄": "亥", "友": "亥", "亏": "亥",
    "演": "寅", "宙": "寅", "宾": "寅", "五": "丑", "卯": "卯",
}

MIN = _dt.timedelta(minutes=1)


def _windows(c, hour_branch):
    """公历日 c 上可能落在该时支的时间窗（含前一日 23 点那一段）。hour_branch=None 时给全天。"""
    day0 = _dt.datetime(c.year, c.month, c.day)
    wins = [(day0 - _dt.timedelta(hours=1), day0, "子"), (day0, day0 + _dt.timedelta(hours=1), "子")]
    for k in range(1, 12):
        wins.append((day0 + _dt.timedelta(hours=2 * k - 1), day0 + _dt.timedelta(hours=2 * k + 1), Z[k]))
    wins.append((day0 + _dt.timedelta(hours=23), day0 + _dt.timedelta(hours=24), "子"))
    return [(a, b) for a, b, zb in wins if hour_branch is None or zb == hour_branch]


def _refine(a, b, ok):
    """窗 [a,b) 内满足 ok 的子区间。窗内最多一个交节点（日界在窗边上）。"""
    last = b - MIN
    oa, ob = ok(a), ok(last)
    if oa and ob:
        return (a, b)
    if not oa and not ob:
        return None
    lo, hi = a, last  # 二分到分钟
    while (hi - lo) > MIN:
        mid = lo + _dt.timedelta(minutes=((hi - lo).total_seconds() // 60) // 2)
        if ok(mid) == oa:
            lo = mid
        else:
            hi = mid
    return (a, hi) if oa else (hi, b)


def find_candidates(ps, lo, hi, ziday="23"):
    """在 lo–hi 年（按年柱起始年）里找所有能排出 ps 的时间区间。ps 为 3 柱或 4 柱。"""
    yp, mp, dp = ps[:3]
    hb = ps[3][1] if len(ps) == 4 else None
    k = len(ps)
    target = tuple(ps)

    def ok(t):
        return C.pillars_at(t, t, ziday)[:k] == target

    out = []
    for y in C.years_of(yp, lo, hi):
        d, end = _dt.date(y, 1, 20), _dt.date(y + 1, 2, 25)
        while C.day_pillar_of(d) != dp:
            d += _dt.timedelta(days=1)
        while d <= end:
            for a, b in _windows(d, hb):
                r = _refine(a, b, ok)
                if r:
                    out.append({"pillar_year": y, "start": r[0], "end": r[1]})
            d += _dt.timedelta(days=60)
    out.sort(key=lambda x: x["start"])
    merged = []
    for c in out:  # 相邻时间窗连成一段
        if merged and merged[-1]["end"] == c["start"] and merged[-1]["pillar_year"] == c["pillar_year"]:
            merged[-1]["end"] = c["end"]
        else:
            merged.append(dict(c))
    return merged


def _dist(q, lo, hi):
    return 0.0 if lo <= q <= hi else min(abs(q - lo), abs(q - hi))


def check(pillars, gender=None, dayun=None, qiyun=None, born=None, lo=None, hi=None, ziday="23", at=None):
    """单盘核验。pillars 可为字符串或列表。返回结构化结果（不打印）。"""
    r = {"input": {"pillars": pillars if isinstance(pillars, str) else " ".join(pillars), "gender": gender,
                   "dayun": dayun, "qiyun": qiyun, "born": born},
         "convention": {"time": "北京时间，不做经度修正", "ziday": "23 点换日" if ziday == "23" else "0 点换日（晚子时）",
                        "jie": "年柱按立春、月柱按十二节，精确到分钟"},
         "problems": [], "checks_done": [], "checks_not_done": [], "candidates": []}

    def done(verdict, status):
        r["verdict"], r["status"] = verdict, status
        return r

    # 输入
    try:
        if isinstance(pillars, str):
            raw_parts = [p for p in re.split(r"[\s,，、]+", pillars.strip()) if p]
        else:
            raw_parts = list(pillars)
        if len(raw_parts) not in (3, 4):
            raise C.InputError("四柱应为 3 或 4 柱，收到 %d 柱" % len(raw_parts))
        bad = [p for p in raw_parts if not C.valid_pillar(p)]
        if bad:
            r["problems"].append("不是合法干支柱：" + " ".join(bad))
            r["checks_not_done"] = ["遁法", "日期反查", "大运", "起运", "出生年"]
            return done("结构非法", "发现不一致")
        ps = raw_parts
        gender = C.norm_gender(gender)
        if lo is None:
            lo, hi, range_given = DEFAULT_RANGE[0], DEFAULT_RANGE[1], False
        else:
            range_given = True
        if not (1000 <= lo <= hi <= 3000):
            raise C.InputError("年份范围不合法：%s–%s" % (lo, hi))
        if dayun is not None:
            dayun = dayun.split() if isinstance(dayun, str) else list(dayun)
            badd = [p for p in dayun if not C.valid_pillar(p)]
            if badd:
                raise C.InputError("大运里有不合法干支：" + " ".join(badd))
        if at is not None:
            at_dt, has_t = C.parse_dt(at)
            if not has_t:
                raise C.InputError("--at 需要到分钟")
    except C.InputError as e:
        r["problems"].append(str(e))
        return done("输入缺失或无法检查", "无法完成")
    r["input"]["gender"] = gender
    r["pillars"] = " ".join(ps)
    yp, mp, dp = ps[:3]
    hp = ps[3] if len(ps) == 4 else None

    # 遁法
    r["month_stem_ok"] = C.month_stem_ok(yp, mp)
    if not r["month_stem_ok"]:
        r["problems"].append("月干违反五虎遁（%s年不会有%s月）" % (yp[0], mp))
    if hp:
        r["hour_stem_ok"] = C.hour_stem_ok(dp, hp, ziday)
        if not r["hour_stem_ok"]:
            msg = "时干违反五鼠遁（%s日不会有%s时）" % (dp[0], hp)
            other = "0" if ziday == "23" else "23"
            if C.hour_stem_ok(dp, hp, other):
                msg += "；按%s口径则合，可加 --ziday %s 再核" % ("0 点换日（晚子时）" if other == "0" else "23 点换日", other)
                r["ziday_hint"] = other
            r["problems"].append(msg)
    else:
        r["checks_not_done"].append("时干遁法（未给时柱）")
    r["checks_done"].append("遁法")

    # 大运（只依赖年干、月柱、性别）
    if gender:
        r["dayun_expected"] = C.expected_dayun(yp, mp, gender)
        if dayun:
            exp = r["dayun_expected"][:len(dayun)]
            r["dayun_ok"] = exp == dayun
            r["checks_done"].append("大运")
            if not r["dayun_ok"]:
                r["problems"].append("大运应为 " + " ".join(exp))
    elif dayun or qiyun is not None:
        r["checks_not_done"].append("大运与起运（未给性别）")

    if not r["month_stem_ok"] or r.get("hour_stem_ok") is False:
        r["checks_not_done"].append("日期反查（遁法不合，先修抄写）")
        return done("遁法不符", "发现不一致")

    # 日期反查
    cands = find_candidates(ps, lo, hi, ziday)
    r["range"] = [lo, hi]
    if not cands and not range_given:
        lo2, hi2 = WIDE_RANGE
        cands = find_candidates(ps, lo2, hi2, ziday)
        r["range"] = [lo2, hi2]
        r["range_note"] = "默认 %d–%d 年没有，已自动扩到 %d–%d 年" % (DEFAULT_RANGE + WIDE_RANGE)
    r["checks_done"].append("日期反查")

    for c in cands:
        item = {"pillar_year": c["pillar_year"], "start": c["start"].strftime("%Y-%m-%d %H:%M"),
                "end": c["end"].strftime("%Y-%m-%d %H:%M"), "hour_known": hp is not None}
        if gender:
            q = [C.yun_info(t, gender)["start_decimal"] for t in (c["start"], c["end"] - MIN)]
            item["qiyun_range"] = [min(q), max(q)]
            if qiyun is not None:
                item["qiyun_ok"] = (_dist(qiyun, min(q), max(q)) <= 1.6 or _dist(qiyun, min(q) + 1, max(q) + 1) <= 1.0)
        if born is not None:
            item["born_ok"] = born in (c["start"].year, c["pillar_year"])
        item["all_ok"] = all(item.get(k, True) for k in ("qiyun_ok", "born_ok"))
        r["candidates"].append(item)
    if gender and qiyun is not None and cands:
        r["checks_done"].append("起运（%s）" % ("按时柱所在时段给区间" if hp else "时柱未知，按全天给区间"))
    if born is not None:
        r["checks_done"].append("出生年")
        if JZ[(born - 4) % 60] != yp and JZ[(born - 5) % 60] != yp:
            r["problems"].append("所称生年 %d 是%s年，不是%s年" % (born, JZ[(born - 4) % 60], yp))

    if at is not None:
        got = list(C.pillars_at(at_dt, at_dt, ziday))[:len(ps)]
        r["at_check"] = {"at": at, "pillars_at": " ".join(got), "ok": got == ps}
        r["checks_done"].append("指定时刻正排")
        if got != ps:
            r["problems"].append("%s 排出来是 %s，不是 %s" % (at, " ".join(got), " ".join(ps)))

    if not cands:
        r["problems"].append("在 %d–%d 年、上述口径下没有找到能排出 %s 的时间（不等于历法上绝对不存在）"
                             % (r["range"][0], r["range"][1], " ".join(ps)))
        return done("范围内未找到", "发现不一致")

    joint = [c for c in r["candidates"] if c["all_ok"]]
    needs_joint = born is not None or (gender is not None and qiyun is not None)
    if needs_joint and not joint:
        parts = []
        if born is not None:
            parts.append("出生年 %d" % born)
        if gender and qiyun is not None:
            parts.append("起运 %s 岁" % qiyun)
        r["problems"].append("没有一个候选同时满足%s" % "、".join(parts))
    if r.get("dayun_ok") is False or (needs_joint and not joint) or (r.get("at_check") and not r["at_check"]["ok"]):
        return done("与所称信息不符", "发现不一致")
    if needs_joint:
        r["matched"] = joint
    return done("通过", "通过")


# ---------------------------------------------------------------- 错字修复
def split_raw(raw):
    s = re.sub(r"[\s\.．·‧、,，:：'‘’\"“”]", "", raw)
    if len(s) != 8:
        return None
    parts = re.split(r"[\s,，]+", raw.strip())
    if len(parts) == 4 and all(len(re.sub(r"[\.．·‧'‘’]", "", p)) == 2 for p in parts):
        ps = [re.sub(r"[\.．·‧'‘’]", "", p) for p in parts]
        return [p[0] for p in ps], [p[1] for p in ps]
    return list(s[:4]), list(s[4:])


def repair(raw, gender=None, lo=None, hi=None, limit=8, ziday="23"):
    sp = split_raw(raw)
    if not sp:
        return {"raw": raw, "status": "无法完成", "error": "去掉标点后不是 8 个字，无法自动修复"}
    gs, zs = sp
    g_opts = [(c if c in G else "") + "".join(x for x in OCR_G.get(c, "") if x != c) for c in gs]
    z_opts = [(c if c in Z else "") + "".join(x for x in OCR_Z.get(c, "") if x != c) for c in zs]
    if any(not o for o in g_opts + z_opts):
        unk = [c for c, o in zip(gs + zs, g_opts + z_opts) if not o]
        return {"raw": raw, "status": "无法完成", "error": "有认不出的字：" + "".join(unk)}
    cands = []
    for g in itertools.product(*g_opts):
        for z in itertools.product(*z_opts):
            ps = [g[i] + z[i] for i in range(4)]
            if not all(C.valid_pillar(p) for p in ps):
                continue
            edits = sum(1 for a, b in zip(list(g) + list(z), gs + zs) if a != b)
            r = check(ps, gender, lo=lo or DEFAULT_RANGE[0], hi=hi or DEFAULT_RANGE[1], ziday=ziday)
            score = (r["verdict"] == "通过", r.get("month_stem_ok", False) and r.get("hour_stem_ok", False), -edits)
            cands.append((score, ps, r, edits))
    cands.sort(key=lambda x: x[0], reverse=True)
    out = [{"pillars": " ".join(ps), "changed_chars": e, "verdict": r["verdict"],
            "dates": sorted({c["start"][:10] for c in r["candidates"]}), "problems": r["problems"]}
           for _, ps, r, e in cands[:limit]]
    passing = [c for c in out if c["verdict"] == "通过"]
    return {"raw": raw, "status": "完成", "unique": len(passing) == 1, "passing": len(passing), "candidates": out}


# ---------------------------------------------------------------- 批量
def run_batch(path, lo, hi, ziday="23"):
    try:
        lines = open(path, encoding="utf8").read().splitlines()
    except OSError as e:
        raise C.InputError("读不了批量文件：%s" % e)
    rows = []
    for no, line in enumerate(lines, 1):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        f = [x.strip() for x in re.split(r"[,，]", s)]
        row = {"line": no, "text": s}
        try:
            gender = C.norm_gender(f[1]) if len(f) > 1 and f[1] else None
            try:
                qiyun = float(f[2]) if len(f) > 2 and f[2] else None
                born = int(f[3]) if len(f) > 3 and f[3] else None
            except ValueError:
                raise C.InputError("起运岁或出生年不是数字")
            if len(f) > 4:
                raise C.InputError("字段多于 4 个")
            r = check(f[0], gender, None, qiyun, born, lo, hi, ziday)
        except C.InputError as e:
            r = {"verdict": "输入缺失或无法检查", "status": "无法完成", "problems": [str(e)], "candidates": []}
        row.update({"verdict": r["verdict"], "status": r["status"], "problems": r["problems"],
                    "dates": sorted({c["start"][:10] for c in r.get("candidates", [])})})
        if r.get("ziday_hint"):
            row["ziday_hint"] = r["ziday_hint"]
        cq = [c["qiyun_range"] for c in r.get("candidates", []) if "qiyun_range" in c]
        if r.get("input", {}).get("qiyun") is not None and cq:
            q = r["input"]["qiyun"]
            near = min(cq, key=lambda x: _dist(q, x[0], x[1]))
            row["qiyun_claim"], row["qiyun_calc"] = q, round((near[0] + near[1]) / 2, 1)
        rows.append(row)
    stat = {v: 0 for v in VERDICTS}
    for row in rows:
        stat[row["verdict"]] += 1
    hint = collections.Counter(r["ziday_hint"] for r in rows if r.get("ziday_hint"))
    qa = [(r["qiyun_claim"], r["qiyun_calc"]) for r in rows if "qiyun_claim" in r]
    extra = {}
    if hint:
        extra["ziday_hint"] = dict(hint)
    if len(qa) >= 10:
        extra["qiyun_hist"] = {"claimed": dict(sorted(collections.Counter(int(round(a)) for a, _ in qa).items())),
                               "calculated": dict(sorted(collections.Counter(int(round(b)) for _, b in qa).items()))}
    return {"file": path, "total": len(rows), "stat": stat, "rows": rows, "extra": extra,
            "range": [lo, hi] if lo is not None else list(DEFAULT_RANGE),
            "note": "只报历法与所给信息的一致性。通过不说明是真人命例，未通过先查输入、转录与口径。"}


def print_batch(b):
    n = b["total"]
    print("共 %d 盘（所有非空、非注释行都计入）" % n)
    for k in VERDICTS:
        v = b["stat"][k]
        print("  %-10s %4d  (%.0f%%)" % (k, v, 100.0 * v / n if n else 0))
    if n == 0:
        print("文件里没有可检查的行（空行和 # 注释不计）。")
    ex = b.get("extra", {})
    for zd, k in ex.get("ziday_hint", {}).items():
        print("遁法不符的盘里，%d 盘换用%s口径即合（加 --ziday %s 重核）。" % (k, "0 点换日（晚子时）" if zd == "0" else "23 点换日", zd))
    if ex.get("qiyun_hist"):
        h = ex["qiyun_hist"]
        print("所称起运岁数分布（取整）：" + "，".join("%s岁 %d" % kv for kv in h["claimed"].items()))
        print("按历法算得的起运分布（取最接近所称的候选）：" + "，".join("%s岁 %d" % kv for kv in h["calculated"].items()))
    print(b["note"])
    for row in b["rows"]:
        if row["verdict"] != "通过":
            print("  第%d行  %s  [%s] %s" % (row["line"], row["text"], row["verdict"], "；".join(row["problems"])))


def print_single(r):
    print("%s  →  %s" % (r.get("pillars", r["input"]["pillars"]), r["verdict"]))
    if r.get("range_note"):
        print("  " + r["range_note"])
    if r.get("candidates"):
        print("  候选时间（%s；%s）：" % (r["convention"]["time"], r["convention"]["ziday"]))
        for c in r["candidates"][:12]:
            extra = []
            if "qiyun_range" in c:
                lo_, hi_ = c["qiyun_range"]
                extra.append("起运 %.1f 岁" % lo_ if abs(hi_ - lo_) < 0.05 else "起运 %.1f–%.1f 岁" % (lo_, hi_))
            for k, lab in (("qiyun_ok", "起运"), ("born_ok", "生年")):
                if k in c:
                    extra.append("%s%s" % (lab, "合" if c[k] else "不合"))
            print("    %s ～ %s  %s" % (c["start"], c["end"], "，".join(extra)))
        if len(r["candidates"]) > 12:
            print("    …共 %d 个" % len(r["candidates"]))
    if r.get("dayun_expected"):
        print("  大运应为：" + " ".join(r["dayun_expected"]))
    if r.get("at_check"):
        print("  指定时刻 %s 排出：%s" % (r["at_check"]["at"], r["at_check"]["pillars_at"]))
    for p in r["problems"]:
        print("  ✗ " + p)
    if r["checks_not_done"]:
        print("  未做：" + "；".join(r["checks_not_done"]))


def main(argv=None):
    ap = argparse.ArgumentParser(description="四柱历法一致性核验 / 扫描错字修复 / 批量核验")
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--pillars", help='四柱，如 "乙未 己卯 丁丑 庚戌"；三柱表示时柱未知')
    src.add_argument("--repair", help="带扫描错字的八个字")
    src.add_argument("--batch", help="批量文件")
    ap.add_argument("--gender", help="male/female、男/女、乾/坤")
    ap.add_argument("--dayun", help='书上所列大运，如 "戊寅 丁丑 丙子"')
    ap.add_argument("--qiyun", type=float, help="书上所称起运岁数")
    ap.add_argument("--born", type=int, help="书上所称出生公历年")
    ap.add_argument("--at", help='另核：这个时刻（北京时间）排出来是不是这组四柱，"YYYY-MM-DD HH:MM"')
    ap.add_argument("--range", help="搜索年份范围，默认 1840-2030；默认范围找不到会自动扩到 1600-2200")
    ap.add_argument("--ziday", default="23", choices=["23", "0"])
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        lo = hi = None
        if a.range:
            m = re.fullmatch(r"\s*(\d{3,4})\s*[-–~]\s*(\d{3,4})\s*", a.range)
            if not m:
                raise C.InputError("--range 格式应为 1840-2030")
            lo, hi = int(m.group(1)), int(m.group(2))
        if a.batch:
            b = run_batch(a.batch, lo, hi, a.ziday)
            print(json.dumps(b, ensure_ascii=False, indent=1) if a.json else "", end="")
            if not a.json:
                print_batch(b)
            return 0
        if a.repair:
            r = repair(a.repair, C.norm_gender(a.gender), lo, hi, ziday=a.ziday)
            if a.json:
                print(json.dumps(r, ensure_ascii=False, indent=1))
            elif "error" in r:
                print("无法修复：", r["error"])
            else:
                print("原串：%s   通过的读法 %d 个%s" % (r["raw"], r["passing"], "（唯一）" if r["unique"] else ""))
                for c in r["candidates"]:
                    print("  %s  改%d字  [%s] %s %s" % (c["pillars"], c["changed_chars"], c["verdict"],
                                                     ",".join(c["dates"][:4]), "；".join(c["problems"])))
            return 2 if "error" in r else 0
        if not a.pillars:
            ap.print_usage()
            print("需要 --pillars / --repair / --batch 之一", file=sys.stderr)
            return 2
        r = check(a.pillars, a.gender, a.dayun, a.qiyun, a.born, lo, hi, a.ziday, a.at)
    except C.InputError as e:
        print(json.dumps({"status": "无法完成", "verdict": "输入缺失或无法检查", "problems": [str(e)]},
                         ensure_ascii=False) if a.json else "输入错误：%s" % e)
        return 2
    except RuntimeError as e:
        print("运行错误：%s" % e, file=sys.stderr)
        return 3
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        print_single(r)
    return {"通过": 0, "发现不一致": 1, "无法完成": 2}[r["status"]]


if __name__ == "__main__":
    sys.exit(main())
