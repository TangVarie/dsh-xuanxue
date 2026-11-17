#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
paipan.py —— 排盘地基（bazi-core 的 P0）。只做确定性计算，不做任何解读。

用法
  A) 给出生时间排盘：
     python3 paipan.py --date "1997-09-05 20:00" --gender male [--lon 121.47] [--tz +8] [--name 张三]
       --gender   male/female、男/女、乾/坤。不给就不定大运顺逆，两种都列。
       --lon      出生地经度。给了就做经度时差修正（只按经度，不含均时差）。
       --eot      在经度时差上再加均时差，得真太阳时。
       --tz       时区：+8、-5、+05:30，或 Asia/Shanghai 这类时区名。不给按 UTC+8，并在参数卡标"默认"。
       --dst      钟表时间是不是夏令时：yes/no/unknown（默认 unknown）。给时区名时由时区库判断。
       --basis    输入时间本身是什么：clock（钟表时间，默认）/ mean-solar / true-solar（已校正过，不再修正）。
       --lunar    输入是农历日期；闰月加 --leap yes。
       --ziday    换日口径：23（默认，子初换日）或 0（晚子时）。
       --uncertainty  出生时间可能误差的分钟数，用来列出边界候选。
     只给日期不给时刻（--date "1997-09-05"）也可以：时柱留空，起运给区间。

  B) 已有四柱，只要藏干、十神、神煞查表和地支关系扫描（无大运）：
     python3 paipan.py --pillars "丁丑 戊申 壬子 庚戌"

  加 --json 输出结构化结果。

退出码：0 完成；2 输入错误或需要补参数；3 运行错误（如缺依赖）。
口径说明见 chart_core.py 开头。
"""
import argparse
import datetime as _dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chart_core as C  # noqa: E402

try:  # 输出接到 head 之类时安静退出
    import signal
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
except (AttributeError, ValueError):
    pass

G, Z = C.G, C.Z

# ---------------------------------------------------------------- 神煞表（查表，不解读）
LU = {"甲": "寅", "乙": "卯", "丙": "巳", "丁": "午", "戊": "巳", "己": "午", "庚": "申", "辛": "酉", "壬": "亥", "癸": "子"}
YANGREN = {"甲": "卯", "丙": "午", "戊": "午", "庚": "酉", "壬": "子"}
WENCHANG = {"甲": "巳", "乙": "午", "丙": "申", "丁": "酉", "戊": "申", "己": "酉", "庚": "亥", "辛": "子", "壬": "寅", "癸": "卯"}
# 天乙：甲戊庚牛羊、乙己鼠猴、丙丁猪鸡、壬癸兔蛇、六辛逢马虎。庚另有"庚辛逢马虎"一版，两版合并列出。
TIANYI = {"甲": ["丑", "未"], "戊": ["丑", "未"], "庚": ["丑", "未", "午", "寅"],
          "乙": ["子", "申"], "己": ["子", "申"], "丙": ["亥", "酉"], "丁": ["亥", "酉"],
          "辛": ["午", "寅"], "壬": ["卯", "巳"], "癸": ["卯", "巳"]}
KUIGANG = {"庚辰", "庚戌", "壬辰", "戊戌"}
MA = {"申": "寅", "子": "寅", "辰": "寅", "寅": "申", "午": "申", "戌": "申", "巳": "亥", "酉": "亥", "丑": "亥", "亥": "巳", "卯": "巳", "未": "巳"}
TAOHUA = {"申": "酉", "子": "酉", "辰": "酉", "寅": "卯", "午": "卯", "戌": "卯", "巳": "午", "酉": "午", "丑": "午", "亥": "子", "卯": "子", "未": "子"}
JIANGXING = {"申": "子", "子": "子", "辰": "子", "寅": "午", "午": "午", "戌": "午", "巳": "酉", "酉": "酉", "丑": "酉", "亥": "卯", "卯": "卯", "未": "卯"}
HUAGAI = {"申": "辰", "子": "辰", "辰": "辰", "寅": "戌", "午": "戌", "戌": "戌", "巳": "丑", "酉": "丑", "丑": "丑", "亥": "未", "卯": "未", "未": "未"}
YUEDE = {"寅": "丙", "午": "丙", "戌": "丙", "申": "壬", "子": "壬", "辰": "壬", "亥": "甲", "卯": "甲", "未": "甲", "巳": "庚", "酉": "庚", "丑": "庚"}

# ---------------------------------------------------------------- 地支关系表
# adopted：本库主分析是否采用这一口径（依据 references/02）。False 的只列出，供他派口径参照。
LIUHE = [("子", "丑"), ("寅", "亥"), ("卯", "戌"), ("辰", "酉"), ("巳", "申"), ("午", "未")]
LIUCHONG = [("子", "午"), ("丑", "未"), ("寅", "申"), ("卯", "酉"), ("辰", "戌"), ("巳", "亥")]
CHUAN = [("子", "未"), ("丑", "午"), ("寅", "巳"), ("卯", "辰"), ("申", "亥"), ("酉", "戌")]
PO_MAIN = [("子", "卯"), ("卯", "午"), ("午", "酉")]                       # 02 第十节
PO_TRAD = [("子", "酉"), ("辰", "丑"), ("戌", "未"), ("寅", "亥"), ("巳", "申")]  # 传统六破里主库不用的五对（卯午两边都有）
ANHE = [("卯", "申"), ("午", "亥"), ("寅", "丑")]                          # 02 第六节：暗合只取三组
BANHE = {("申", "子"): "水", ("子", "辰"): "水", ("亥", "卯"): "木", ("卯", "未"): "木",
         ("寅", "午"): "火", ("午", "戌"): "火", ("巳", "酉"): "金", ("酉", "丑"): "金"}
GONG = {("申", "辰"): "子", ("亥", "未"): "卯", ("寅", "戌"): "午", ("巳", "丑"): "酉"}
SANHE = [(("申", "子", "辰"), "水"), (("亥", "卯", "未"), "木"), (("寅", "午", "戌"), "火"), (("巳", "酉", "丑"), "金")]


def _has(pairs, a, b):
    return (a, b) in pairs or (b, a) in pairs


def _get(d, a, b):
    return d.get((a, b)) or d.get((b, a))


def scan_relations(branches, labels=None):
    """逐对扫地支关系。返回 [{type, where, adopted, basis}]。不做解读。"""
    labels = labels or ["年", "月", "日", "时"][:len(branches)]
    rel = []

    def add(t, where, adopted, basis):
        rel.append({"type": t, "where": where, "adopted": adopted, "basis": basis})

    n = len(branches)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = branches[i], branches[j]
            if a == b:
                continue
            w = "%s%s-%s%s" % (labels[i], a, labels[j], b)
            if _has(LIUHE, a, b):
                add("六合", w, True, "02 五")
            if _has(LIUCHONG, a, b):
                add("六冲", w, True, "02 七")
            if _has(CHUAN, a, b):
                add("相穿（害）", w, True, "02 八")
            if _get(BANHE, a, b):
                add("半合%s" % _get(BANHE, a, b), w, True, "02 六")
            if _get(GONG, a, b):
                add("拱%s" % _get(GONG, a, b), w, True, "02 六")
            if _has(ANHE, a, b):
                add("暗合", w, True, "02 六：只取寅丑、午亥、卯申")
            if _has(PO_MAIN, a, b):
                add("破", w, True, "02 十：只论子卯、卯午、午酉")
            elif _has(PO_TRAD, a, b):
                add("破（传统六破）", w, False, "主库不论此破，02 十")
            if {a, b} in ({"丑", "戌"}, {"未", "戌"}):
                add("刑（丑戌未两字）", w, True, "02 九：丑戌、未戌两两相见论刑")
            if {a, b} in ({"寅", "巳"}, {"巳", "申"}, {"寅", "申"}):
                add("刑（寅巳申两字）", w, False, "02 九：两字各从本论（寅巳穿、巳申合、寅申冲），三字见全才论刑")
            if {a, b} == {"子", "卯"}:
                add("子卯刑", w, False, "02 九：主库子卯论破")
    s = set(branches)
    for trio, wx in SANHE:
        if all(t in s for t in trio):
            add("三合%s局" % wx, "".join(trio), True, "02 六")
    if {"寅", "巳", "申"} <= s:
        add("寅巳申三刑", "寅巳申", True, "02 九")
    if {"丑", "戌", "未"} <= s:
        add("丑戌未三刑", "丑戌未", True, "02 九")
    for zz in "辰午酉亥":
        if branches.count(zz) >= 2:
            add("%s%s自刑" % (zz, zz), zz * 2, False, "02 九：段氏不用自刑，江湖派用")
    return rel


MA_WIDE = {"申": "寅午戌", "子": "寅午戌", "辰": "寅午戌", "寅": "申子辰", "午": "申子辰", "戌": "申子辰",
           "巳": "亥卯未", "酉": "亥卯未", "丑": "亥卯未", "亥": "巳酉丑", "卯": "巳酉丑", "未": "巳酉丑"}


def shensha(day_gan, zhis, gans, day_pillar):
    """查表结果，分两组：段氏五神煞（主库）与江湖煞（校验、直断时调用）。只列名称和所在，不附含义。
    墓库属地支关系，见关系扫描与 references/02。"""
    duan, jh = [], []
    if LU[day_gan] in zhis:
        duan.append("禄（%s禄在%s）" % (day_gan, LU[day_gan]))
    if day_gan in YANGREN and YANGREN[day_gan] in zhis:
        duan.append("羊刃（%s刃在%s）" % (day_gan, YANGREN[day_gan]))
    for base_name, idx in (("年", 0), ("日", 2)):
        base = zhis[idx]
        hits = ["%s%s" % (["年", "月", "日", "时"][k], z) for k, z in enumerate(zhis) if k != idx and z in MA_WIDE[base]]
        if hits:
            duan.append("驿马（%s支%s起，%s任一皆马；见于%s）" % (base_name, base, MA_WIDE[base], "、".join(hits)))
    duan.append("空亡（日柱%s旬空%s）" % (day_pillar, C.xunkong(day_pillar)))
    if day_pillar in KUIGANG:
        jh.append("魁罡（日柱%s）" % day_pillar)
    if WENCHANG[day_gan] in zhis:
        jh.append("文昌（在%s）" % WENCHANG[day_gan])
    ty = [z for z in TIANYI[day_gan] if z in zhis]
    if ty:
        jh.append("天乙贵人（在%s%s）" % ("/".join(ty), "；庚日两版口诀合并" if day_gan == "庚" else ""))
    for base_name, base in (("年", zhis[0]), ("日", zhis[2])):
        for nm, tb in (("桃花", TAOHUA), ("将星", JIANGXING), ("华盖", HUAGAI)):
            if tb[base] in zhis:
                jh.append("%s（%s支起，在%s）" % (nm, base_name, tb[base]))
        if MA[base] in zhis:
            jh.append("驿马·传统单马（%s支起，在%s）" % (base_name, MA[base]))
    yd = YUEDE.get(zhis[1])
    if yd and yd in gans:
        jh.append("月德贵人（%s月，%s透）" % (zhis[1], yd))
    return {"duan": duan, "jianghu": jh}


def chart_table(pillars):
    gans = [p[0] for p in pillars]
    zhis = [p[1] for p in pillars]
    dg = gans[2]
    cols = ["年柱", "月柱", "日柱", "时柱"][:len(pillars)]
    return {
        "columns": cols,
        "gan": gans, "gan_shishen": [("日主" if i == 2 else C.shishen(dg, g)) for i, g in enumerate(gans)],
        "zhi": zhis, "zanggan": [[(g, C.shishen(dg, g)) for g in C.ZANGGAN[z]] for z in zhis],
        "day_master": "%s（%s，%s）" % (dg, C.WX_GAN[dg], C.YY_GAN[dg]),
    }


def static_facts(pillars):
    """四柱确定后，与时间无关的查表结果。三柱（时柱未知）时只扫三柱。"""
    t = chart_table(pillars)
    zhis, gans = t["zhi"], t["gan"]
    facts = {"table": t, "relations": scan_relations(zhis),
             "dun": {"month_stem_ok": C.month_stem_ok(pillars[0], pillars[1])}}
    if len(pillars) == 4:
        facts["shensha"] = shensha(gans[2], zhis, gans, pillars[2])
        facts["dun"]["hour_stem_ok"] = C.hour_stem_ok(pillars[2], pillars[3])
    else:
        facts["shensha"] = shensha(gans[2], zhis, gans, pillars[2])
    return facts


# ---------------------------------------------------------------- 主流程
def run_date(a):
    gender = C.norm_gender(a.gender)
    tr = C.resolve_time(a.date, calendar="lunar" if a.lunar else "solar",
                        leap={"yes": True, "no": False}.get(a.leap), tz=a.tz, dst=a.dst, basis=a.basis,
                        lon=a.lon, eot=a.eot, ziday=a.ziday, uncertainty=a.uncertainty)
    rec = tr["record"]
    rec["性别"] = {"value": C.gender_cn(gender), "source": "用户" if gender else "未提供（大运顺逆未定）"}
    rec["四柱来源"] = {"value": "由出生时间计算", "source": "计算"}
    if a.name:
        rec["造主"] = {"value": a.name, "source": "用户"}
    res = {"status": "已完成", "params": rec, "notes": list(tr["notes"]), "missing": []}

    if tr["has_time"]:
        cands = C.chart_candidates(tr)
        main = cands[0]["pillars"]
        bj, loc = tr["main"]["beijing"], tr["main"]["local"]
        res["boundary"] = {"minutes_to_hour_boundary": C.minutes_to_hour_boundary(loc), "jie": C.jie_around(bj)}
        if len(cands) > 1:
            res["status"] = "候选并行"
            diff = [["年", "月", "日", "时"][i] for i in range(4) if any(c["pillars"][i] != main[i] for c in cands[1:])]
            res["notes"].append("不同口径排出的盘不同（差在%s柱），受影响的判断要分支保留。" % "、".join(diff))
        res["candidates"] = cands
        res["pillars"] = main
        if any(c["pillars"][:2] != main[:2] for c in cands[1:]):  # 年月柱不同，大运也不同
            yun_sets = [("候选 " + " ".join(c["pillars"]), [c["beijing"]]) for c in cands]
        else:
            yun_sets = [("", [bj])]
    else:
        w = tr["day_window"]
        noon = w[0]["local"].replace(hour=12)
        day_p = C.pillars_at(noon, noon - (w[0]["local"] - w[0]["beijing"]), a.ziday)[2]
        ym = [list(C.pillars_at(x["local"], x["beijing"], a.ziday))[:2] for x in w]
        ps = [ym[0] + [day_p], ym[1] + [day_p]]
        res["status"] = "部分完成"
        res["missing"].append("出生时刻：时柱未排；起运只给全天区间")
        yun_sets = [("", [x["beijing"] for x in w])]
        if ps[0] != ps[1]:
            res["status"] = "候选并行"
            b0, b1 = w[0]["beijing"], w[1]["beijing"]
            lo_, hi_ = b0, b1  # 二分找交节分钟
            while (hi_ - lo_).total_seconds() > 60:
                mid = lo_ + (hi_ - lo_) / 2
                mid = mid.replace(second=0, microsecond=0)
                if mid <= lo_:
                    break
                if list(C.pillars_at(mid, mid, a.ziday))[:2] == ym[0]:
                    lo_ = mid
                else:
                    hi_ = mid
            res["notes"].append("当天交节（北京时间约 %s），年柱或月柱随出生时刻不同：%s / %s" %
                                (hi_.strftime("%H:%M"), " ".join(ps[0]), " ".join(ps[1])))
            res["candidates"] = [{"pillars": ps[0], "labels": ["交节前"]}, {"pillars": ps[1], "labels": ["交节后"]}]
            yun_sets = [("交节前", [b0, lo_]), ("交节后", [hi_, b1])]
        res["pillars"] = ps[0]
        if a.ziday == "23":
            res["notes"].append("按 23 点换日：若生于 23 点后，日柱为次日 %s。" % C.JZ[(C.JZ.index(day_p) + 1) % 60])

    res["facts"] = static_facts(res["pillars"])
    if tr["has_time"]:
        bj = tr["main"]["beijing"]
        l = C._ec(bj)
        res["facts"]["xunkong"] = {"day": l.getDayXunKong(), "year": l.getYearXunKong()}
        res["facts"]["taiyuan_minggong_shengong"] = [l.getTaiYuan(), l.getMingGong(), l.getShenGong()]
        res["facts"]["nayin"] = [l.getYearNaYin(), l.getMonthNaYin(), l.getDayNaYin(), l.getTimeNaYin()]

    genders = [gender] if gender else ["male", "female"]
    res["yun"] = []
    for g in genders:
        for label, times in yun_sets:
            infos = [C.yun_info(t, g) for t in times]
            y = dict(infos[0])
            y["candidate"] = label
            if len(infos) > 1:
                y["start_range"] = [min(i["start_decimal"] for i in infos), max(i["start_decimal"] for i in infos)]
            res["yun"].append(y)
    if not gender:
        res["missing"].append("性别：大运顺逆未定，两种排法都列出")
    return res


def run_pillars(a):
    ps = C.parse_pillars(a.pillars, allow_three=True)
    res = {"status": "已完成", "params": {"四柱来源": {"value": "用户直接给出", "source": "用户"},
                                        "出生时间": {"value": "未提供", "source": "—"}},
           "notes": [], "missing": ["出生时间：无节气定位、无起运日期、无大运（需要可用 --date 或 check_chart.py 反查）"]}
    if len(ps) == 3:
        res["status"] = "部分完成"
        res["missing"].append("时柱")
    res["pillars"] = ps
    res["facts"] = static_facts(ps)
    d = res["facts"]["dun"]
    if not d["month_stem_ok"] or d.get("hour_stem_ok") is False:
        res["notes"].append("遁法不合：%s。先用 check_chart.py 核对抄写，再分析。" %
                            "、".join(x for x, ok in (("月干（五虎遁）", d["month_stem_ok"]),
                                                      ("时干（五鼠遁）", d.get("hour_stem_ok", True))) if not ok))
        res["status"] = "部分完成"
    return res


def print_text(r):
    print("# 排盘地基（确定性计算，不含解读）\n")
    print("状态：%s" % r["status"])
    for m in r.get("missing", []):
        print("- 缺：%s" % m)
    for n in r.get("notes", []):
        print("- 注：%s" % n)
    print("\n## 参数卡\n")
    print("| 项 | 值 | 来源 |\n|---|---|---|")
    for k, v in r["params"].items():
        print("| %s | %s | %s |" % (k, v["value"], v["source"]))
    if r.get("boundary"):
        b = r["boundary"]
        print("\n## 边界\n")
        print("- 距最近时辰交界：%d 分钟" % b["minutes_to_hour_boundary"])
        print("- 上一节：%s %s（北京时间，距 %s）" % (b["jie"]["prev"]["name"], b["jie"]["prev"]["time_beijing"], _hm(b["jie"]["prev"]["minutes"])))
        print("- 下一节：%s %s（北京时间，距 %s）" % (b["jie"]["next"]["name"], b["jie"]["next"]["time_beijing"], _hm(b["jie"]["next"]["minutes"])))
    if r.get("candidates") and len(r["candidates"]) > 1:
        print("\n## 候选盘\n")
        for c in r["candidates"]:
            print("- %s　← %s" % (" ".join(c["pillars"]), "、".join(c["labels"])))
    t = r["facts"]["table"]
    print("\n## 四柱（主口径）\n")
    print("| | " + " | ".join(t["columns"]) + " |")
    print("|---|" + "---|" * len(t["columns"]))
    print("| 天干 | " + " | ".join(t["gan"]) + " |")
    print("| 干十神 | " + " | ".join(t["gan_shishen"]) + " |")
    print("| 地支 | " + " | ".join(t["zhi"]) + " |")
    print("| 藏干（十神） | " + " | ".join("·".join(g + s for g, s in zg) for zg in t["zanggan"]) + " |")
    f = r["facts"]
    if f.get("nayin"):
        print("| 纳音 | " + " | ".join(f["nayin"]) + " |")
    print("\n- 日主：%s，生%s月" % (t["day_master"], t["zhi"][1]))
    d = f["dun"]
    print("- 遁法：月干%s%s" % ("合" if d["month_stem_ok"] else "不合",
                             ("，时干" + ("合" if d["hour_stem_ok"] else "不合")) if "hour_stem_ok" in d else ""))
    if f.get("xunkong"):
        print("- 空亡：日柱 %s｜年柱 %s" % (f["xunkong"]["day"], f["xunkong"]["year"]))
        print("- 胎元 %s｜命宫 %s｜身宫 %s" % tuple(f["taiyuan_minggong_shengong"]))
    print("\n## 神煞（查表结果，未解读）\n")
    print("段氏五神煞（主库；墓库见关系扫描）：" + ("　".join(f["shensha"]["duan"]) or "无"))
    print("江湖煞（骨架不用，校时辰、直断时调用）：" + ("　".join(f["shensha"]["jianghu"]) or "无"))
    print("\n## 地支关系扫描\n")
    used = [x for x in f["relations"] if x["adopted"]]
    other = [x for x in f["relations"] if not x["adopted"]]
    if not f["relations"]:
        print("- 四支之间无合冲穿刑破拱")
    for x in used:
        print("- %s：%s（%s）" % (x["type"], x["where"], x["basis"]))
    if other:
        print("\n列出但主库不采用（他派口径）：")
        for x in other:
            print("- %s：%s（%s）" % (x["type"], x["where"], x["basis"]))
    print("\n夹拱、扩展暗合等位置依赖的关系脚本不扫，按 references/02 手动补。")
    for y in r.get("yun", []):
        print("\n## 大运（%s命%s）\n" % (C.gender_cn(y["gender"]), "·" + y["candidate"] if y.get("candidate") else ""))
        st = y["start"]
        rng = ("；全天区间 %.1f–%.1f 岁" % tuple(y["start_range"])) if y.get("start_range") else ""
        print("方向：%s　起运：出生后 %d 年 %d 个月 %d 天（约 %s 起运）%s" %
              ("顺行" if y["forward"] else "逆行", st["years"], st["months"], st["days"], y["start_solar"], rng))
        print("\n| 大运 | 起始公历年 | 起始虚岁 |\n|---|---|---|")
        for dd in y["dayun"]:
            print("| %s | %d | %d |" % (dd["ganzhi"], dd["start_year"], dd["start_age_xu"]))
    print("\n> 以上只是计算结果。解读按 SKILL.md 与 references/execution-protocol.md 进行。")


def _hm(m):
    return "%d 小时 %d 分" % (m // 60, m % 60) if m >= 60 else "%d 分" % m


def _jsonable(o):
    if isinstance(o, (_dt.datetime, _dt.date)):
        return o.strftime("%Y-%m-%d %H:%M")
    raise TypeError(type(o))


def main(argv=None):
    ap = argparse.ArgumentParser(description="八字排盘地基（确定性计算，不做解读）")
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--date", help='出生时间 "YYYY-MM-DD HH:MM"，或只给日期 "YYYY-MM-DD"')
    src.add_argument("--pillars", help='已知四柱 "丁丑 戊申 壬子 庚戌"（三柱也可，时柱未知）')
    ap.add_argument("--gender", help="male/female、男/女、乾/坤；不给则大运两种方向都列")
    ap.add_argument("--lon", type=float, help="出生地经度，东经为正")
    ap.add_argument("--eot", action="store_true", help="加均时差，得真太阳时（需 --lon）")
    ap.add_argument("--tz", help="时区，默认 UTC+8")
    ap.add_argument("--dst", default="unknown", choices=["yes", "no", "unknown"])
    ap.add_argument("--basis", default="clock", choices=["clock", "mean-solar", "true-solar"])
    ap.add_argument("--lunar", action="store_true", help="--date 是农历")
    ap.add_argument("--leap", choices=["yes", "no"], help="农历闰月")
    ap.add_argument("--ziday", default="23", choices=["23", "0"])
    ap.add_argument("--uncertainty", type=int, default=0, help="出生时间可能误差（分钟）")
    ap.add_argument("--name", default="")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        if a.eot and a.lon is None:
            raise C.InputError("--eot 需要同时给 --lon")
        if a.pillars:
            r = run_pillars(a)
        elif a.date:
            r = run_date(a)
        else:
            ap.print_help()
            return 2
    except C.NeedsChoice as e:
        out = {"status": "需补参数", "error": str(e), "options": e.options}
        print(json.dumps(out, ensure_ascii=False, indent=1) if a.json else
              "需补参数：%s\n" % e + "\n".join("  闰月=%s → 公历 %s" % ("是" if o["leap"] else "否", o["solar"]) for o in e.options))
        return 2
    except C.InputError as e:
        print(json.dumps({"status": "输入错误", "error": str(e)}, ensure_ascii=False) if a.json else "输入错误：%s" % e,
              file=sys.stdout if a.json else sys.stderr)
        return 2
    except RuntimeError as e:
        print("运行错误：%s" % e, file=sys.stderr)
        return 3
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1, default=_jsonable))
    else:
        print_text(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
