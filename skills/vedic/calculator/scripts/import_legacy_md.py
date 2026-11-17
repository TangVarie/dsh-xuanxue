#!/usr/bin/env python3
"""import_legacy_md.py — 旧版 structured_data.md 兼容导入（vedic 5.1）。

把旧格式（v4/v5.0 calculator 或 reader 提取）的 Markdown 读成 chart_data.json：
  - 能解析的表照原值导入；旧文件没有的表（Graha Drishti、功能身份、格局预扫、互视/互溶、
    分盘内部宫主、Chara Dasha、PD、8K 对照等）一律标「未计算」，不自动补成已验证
  - 旧版「✅ 可信（直接计算）」不算边界审计：分盘审计标「未计算」
  - 「盘面初验结果 / 验前事校准率 / 生时矫正记录 / 信号修正日志」是反馈信息，迁到 verification_record.md，
    不留在计算数据里（--keep-feedback 可关闭迁出，仅用于对照）
  - 原文件另存为 structured_data.legacy.md；新的 structured_data.md = 原文去掉反馈节 + 元信息加 chart_id

出生日期/时间/地点齐全且计算环境可用时，优先用 build_chart.py 重排，导入只是过渡。

用法: python import_legacy_md.py --file <旧 structured_data.md> --out <目录> [--tz Asia/Shanghai]
"""
import argparse
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chart_io as cio  # noqa: E402
import dasha_check as dc  # noqa: E402

FEEDBACK = ["## 盘面初验结果", "## 验前事校准率", "## 生时矫正记录", "## 信号修正日志"]
NOT_IN_LEGACY = ["graha_drishti", "functional", "yoga_prescan", "mutual_drishti", "parivartana",
                 "varga_internal", "chara_dasha", "pushkara", "d9_dignity"]


def section(text, title, level="### "):
    i = text.find(level + title)
    if i < 0:
        return None
    rest = text[i + len(level + title):]
    j = re.search(r"\n#{2,3} ", rest)
    return rest[: j.start()] if j else rest


def table_rows(body):
    rows = []
    for ln in (body or "").splitlines():
        if ln.startswith("|") and not re.match(r"^\|\s*-", ln):
            rows.append([c.strip() for c in ln.strip().strip("|").split("|")])
    return rows[1:] if rows else []


def meta_value(text, key):
    m = re.search(rf"^{key}:\s*(.+)$", text, re.M)
    return m.group(1).strip() if m else None


def deg_to_float(s):
    m = re.match(r"(\d+)°(\d+)'", s or "")
    return int(m.group(1)) + int(m.group(2)) / 60 if m else None


def parse(text, tz):
    na = lambda r: cio.missing("not_computed", r)  # noqa: E731
    chart, problems = {}, []
    # 行星
    lagna, planets = None, {}
    for r in table_rows(section(text, "行星位置")):
        if len(r) < 5:
            continue
        name, sign, house, deg, retro = r[:5]
        if sign not in cio.SIGNS:
            problems.append(f"行星位置.{name}.星座 非法「{sign}」")
            continue
        d = deg_to_float(deg)
        si = cio.SIGNS.index(sign)
        entry = {"sign": sign, "sign_idx": si, "degree": d, "deg_str": deg,
                 "longitude": si * 30 + d if d is not None else None}
        if name == "Lagna":
            lagna = dict(entry, house=1)
        else:
            entry.update({"house": int(house) if house.isdigit() else None, "retrograde": retro == "R"})
            planets[name] = entry
    for r in table_rows(section(text, "Nakshatra")):
        if len(r) >= 4 and (r[0] in planets or r[0] == "Lagna"):
            nk = {"name": cio.canon_nakshatra(r[1]), "pada": int(r[2]) if r[2].isdigit() else None, "lord": r[3]}
            (lagna if r[0] == "Lagna" else planets[r[0]])["nakshatra"] = nk
    chart["lagna"] = lagna or cio.missing("not_provided", "旧文件无上升行")
    chart["planets"] = planets
    # Karakas
    k7 = []
    for r in table_rows(section(text, "Chara Karakas")):
        if len(r) >= 4 and r[0].isdigit():
            k7.append([r[1], r[2], float(re.sub(r"[^\d.]", "", r[3]) or 0)])
    dk8 = re.search(r"8K参考 DK = (\w+)", text)
    chart["karakas"] = {"7k": k7, "8k": na("旧文件没有 8K 完整排序"), "dk_7k": k7[6][1] if len(k7) >= 7 else None,
                        "dk_8k": dk8.group(1) if dk8 else na("旧文件没有 8K DK")} if k7 else na("旧文件无 Karaka 表")
    # 特殊点位
    sp = {}
    for r in table_rows(section(text, "特殊点位")):
        if len(r) >= 3 and r[1] in cio.SIGNS:
            key = "UL" if r[0].startswith("UL") else ("AL" if r[0].startswith("AL") else None)
            if key:
                sp[key] = {"sign": r[1], "house": int(r[2]) if r[2].isdigit() else None}
    chart["special_points"] = sp or na("旧文件无特殊点位")
    # SAV
    sav_raw = section(text, "原始值（按星座，用于校验）", "#### ")
    rows = table_rows(sav_raw)
    if rows and len(rows[0]) >= 12:
        chart["sav"] = {cio.SIGNS[i]: int(rows[0][i]) for i in range(12)}
        hv = table_rows(section(text, "宫位映射（按宫位，供core/career/love直接使用）", "#### "))
        if hv and lagna and not cio.is_missing(lagna):
            chart["sav_by_house"] = {h + 1: {"sign": cio.SIGNS[(lagna["sign_idx"] + h) % 12], "value": int(hv[0][h])}
                                     for h in range(12)}
    else:
        chart["sav"] = na("旧文件无 SAV")
    # 尊贵度、宫主
    dig = {r[0]: {"compound": r[3]} for r in table_rows(section(text, "行星尊贵度（Compound Dignity / Panchadha Maitri）"))
           if len(r) >= 4}
    chart["dignity"] = dig or na("旧文件无尊贵度表")
    hl = {}
    for r in table_rows(section(text, "宫主表")):
        if len(r) >= 4 and r[0].isdigit():
            hl[int(r[0])] = {"domain": r[1], "lord": r[2], "lord_house": int(r[3]) if r[3].isdigit() else None}
    chart["house_lords"] = hl or na("旧文件无宫主表")
    # 分盘
    for key, title in (("d9", "D9 Navamsha"), ("d10", "D10 Dasamsha"), ("d4", "D4 Chaturthamsha"), ("d5", "D5 Panchamsha")):
        rows = table_rows(section(text, title))
        if rows:
            chart[key] = {r[0]: [r[1], cio.SIGNS.index(r[1])] for r in rows if len(r) >= 2 and r[1] in cio.SIGNS}
        else:
            chart[key] = na(f"旧文件无 {title}")
    # 分盘审计
    m = re.search(r"边界审计范围: 报时前后±(\d+)分钟", text)
    if m:
        charts = {}
        for key in ("D1", "D9", "D10", "D4", "D5"):
            lm = re.search(rf"^{key}\s+(✅|⚠️)[^\n]*Lagna=([A-Za-z→]+)", text, re.M)
            if lm:
                obs = lm.group(2).split("→")
                charts[key] = {"base_sign": obs[0], "stable": lm.group(1) == "✅", "observed_signs": obs}
        chart["divisional_boundary_audit"] = {"status": "ok", "uncertainty_minutes": int(m.group(1)),
                                              "charts": charts, "source": "legacy_md"}
    else:
        chart["divisional_boundary_audit"] = na("旧版没有逐分钟边界审计；“直接计算/可信”不等于稳定")
    # Dasha
    tree = dc.tree_from_md(text)
    mds, _, _ = dc._md_tree(tree)
    if mds:
        chart["dashas"] = [{"planet": md["planet"], "start": md["start"], "end": md["end"],
                            "antardashas": [{"planet": ad["planet"], "start": ad["start"], "end": ad["end"],
                                             "start_time": ad["start"], "end_time": ad["end"],
                                             "pratyantardashas": [{"planet": p["planet"], "start": p["start"],
                                                                   "end": p["end"], "start_time": p["start"],
                                                                   "end_time": p["end"]} for p in ad["pds"]]}
                                            for ad in md["ads"]]} for md in mds]
    else:
        chart["dashas"] = na("旧文件无 Vimsottari 表")
    for k in NOT_IN_LEGACY:
        chart[k] = na("旧版 Markdown 没有此表")
    if "### 主要相位关系" in text:
        problems.append("旧文件含西占 orb「主要相位关系」表：已废弃，未导入")
    # 过运
    tm = re.search(r"提取时间点：(\d{4}-\d{2}-\d{2})", text)
    if tm:
        tr = {"date": tm.group(1), "planets": {}}
        for r in table_rows(section(text, "慢行星过运")):
            if len(r) >= 3 and r[1] in cio.SIGNS:
                tr["planets"][r[0]] = {"sign": r[1], "house": int(r[2]) if r[2].isdigit() else None}
        fi = []
        for r in table_rows(section(text, "未来过运换座时间表（真实天文计算，未来5年）")):
            mm = re.match(r"(\w+) → (\w+)", r[2]) if len(r) >= 3 else None
            if mm:
                fi.append({"date": r[0], "planet": r[1], "from_sign": mm.group(1), "to_sign": mm.group(2)})
        tr["future_ingress"] = fi or cio.missing("not_computed", "旧文件无未来换座表")
        transit = tr
    else:
        transit = cio.missing("not_computed", "旧文件无过运快照")
    return chart, transit, problems


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tz", default=None, help="旧文件不记录时区；知道时传入，否则记为未提供")
    ap.add_argument("--keep-feedback", action="store_true")
    a = ap.parse_args()
    text = open(a.file, encoding="utf-8").read()
    chart, transit, problems = parse(text, a.tz)
    loc = re.search(r"出生地点:\s*(.*?)\s*\(([-\d.]+),\s*([-\d.]+)\)", text)
    inp = {
        "mode": "legacy", "date": meta_value(text, "出生日期"), "time_reported": meta_value(text, "出生时间"),
        "time_used": meta_value(text, "出生时间"), "clock_type": cio.missing("not_provided", "旧文件未记录"),
        "tz": a.tz or cio.missing("not_provided", "旧文件未记录时区"),
        "lat": float(loc.group(3)) if loc else None, "lon": float(loc.group(2)) if loc else None,
        "place": loc.group(1) if loc else "未提供", "time_source": meta_value(text, "时间来源") or "未提供",
        "declared_precision_text": meta_value(text, "时间精度") or "未声明",
        "declared_minutes": None, "effective_minutes": None,
        "effective_label": ("未声明" if (meta_value(text, "有效精度") or "").strip() in ("", "±分钟级")
                            else meta_value(text, "有效精度")),
        "audit_minutes": (chart["divisional_boundary_audit"] or {}).get("uncertainty_minutes")
        if not cio.is_missing(chart["divisional_boundary_audit"]) else None,
    }
    settings = {"ayanamsa": meta_value(text, "Ayanamsa") or cio.missing("not_provided"), "node": meta_value(text, "Node模式")}
    chart_id, audit_id = cio.compute_ids(inp, settings)
    doc = {"schema": cio.SCHEMA_VERSION, "chart_id": chart_id, "audit_id": audit_id, "generated_at": cio.now_iso(),
           "engine_version": "legacy-markdown", "rules_version": cio.RULES_VERSION, "input": inp,
           "settings": settings, "user": {}, "chart": chart, "transit": transit, "overrides": {},
           "provenance": {"source": "legacy_md_import", "imported_from": os.path.abspath(a.file),
                          "verified": False, "problems": problems}}
    os.makedirs(a.out, exist_ok=True)
    cio.save_doc(cio.to_jsonable(doc), os.path.join(a.out, "chart_data.json"))
    shutil.copyfile(a.file, os.path.join(a.out, "structured_data.legacy.md"))
    # 反馈节迁出
    fb_parts, kept = [], text
    if not a.keep_feedback:
        for title in FEEDBACK:
            i = kept.find(title)
            if i >= 0:
                rest = kept[i:]
                j = re.search(r"\n## ", rest[3:])
                block = rest[: j.start() + 3] if j else rest
                fb_parts.append(block.strip())
                kept = kept.replace(block, "")
    kept = kept.replace("读盘方式:", f"数据版本: chart_id={chart_id} · 旧版 Markdown 导入（未重新验证）\n读盘方式:", 1)
    kept = re.sub(r"^读盘方式: (.*)$", r"读盘方式: 旧版 Markdown 导入（原文写「\1」）", kept, count=1, flags=re.M)
    kept = re.sub(r"^时间精度: (.*)$", r"时间精度: 旧文件原话「\1」（未核实，不作有效精度）", kept, count=1, flags=re.M)

    def _replace_section(txt, heading, note):
        i = txt.find(heading)
        if i < 0:
            return txt
        level = heading.split(" ")[0]
        rest = txt[i + len(heading):]
        m = re.search(r"\n#{2,%d} " % len(level), rest)
        end = i + len(heading) + (m.start() + 1 if m else len(rest))
        return txt[:i] + heading + "\n\n" + note + "\n\n" + txt[end:]

    # 旧引擎的 ✅ 校验块不代表 5.1 的检查；西占 orb 相位表已废弃
    kept = _replace_section(kept, "## 校验结果",
                            "> 旧版校验块已移除：旧引擎的 ✅ 不等于本版检查（例如旧引擎 Dasha 交界有 ±1 天出入）。"
                            "以 `calculator/scripts/check_chart.py --dir <目录>` 的结果与能力范围为准；原文见 structured_data.legacy.md。")
    kept = _replace_section(kept, "### 主要相位关系",
                            "> 旧版西占 orb 相位表已废弃、未导入；吠陀相位读「Graha Drishti」（旧文件没有，需重排）。")
    # 旧版缺省写法如实改写：不保留“±分钟级/可信（直接计算）”这类未经审计的声明
    kept = re.sub(r"^有效精度: ±分钟级\s*$", "有效精度: 未声明（旧文件缺省写成±分钟级，实际精度未知）", kept, flags=re.M)
    kept = re.sub(r"^(D\d+)\s+✅ 可信（直接计算）\s*$", r"\1  ⚠️ 未审计（旧版只做直接计算，未做报时误差边界审计）", kept, flags=re.M)
    with open(os.path.join(a.out, "structured_data.md"), "w", encoding="utf-8") as f:
        f.write(kept)
    if fb_parts:
        with open(os.path.join(a.out, "verification_record.md"), "w", encoding="utf-8") as f:
            f.write(f"# 验证记录（从旧版 structured_data.md 迁出）\n\n> 绑定盘：chart_id={chart_id}（旧盘）。"
                    "以下是旧流程的反馈与修正日志原文，未按 5.1 评分规则重算；需要等级时用 shared/scripts/score_probes.py 重新登记。\n\n"
                    + "\n\n".join(fb_parts) + "\n")
    missing_keys = [k for k, v in chart.items() if cio.is_missing(v)]
    print(f"[写出] {a.out}/chart_data.json（chart_id={chart_id}，provenance=legacy_md_import）")
    print(f"导入缺项（保持缺失）：{', '.join(missing_keys) or '无'}")
    if fb_parts:
        print(f"反馈节已迁出到 verification_record.md：{len(fb_parts)} 节")
    for p in problems:
        print(f"注意：{p}")


if __name__ == "__main__":
    main()
