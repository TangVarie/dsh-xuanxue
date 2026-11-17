#!/usr/bin/env python3
"""check_chart.py — 排盘产物总检查（vedic 5.1）。

用法:
  python check_chart.py --dir <工作目录>            # 读 chart_data.json + structured_data.md
  python check_chart.py --file <某人的 structured_data.md>

逐项输出 通过 / 失败 / 未完成，并给出能力范围（缺什么只限制依赖它的能力）。
退出码: 0 全部通过 / 1 有失败项 / 2 无失败但有未完成项
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chart_io as cio  # noqa: E402
import dasha_check as dc  # noqa: E402
import capability as cap  # noqa: E402

PASS, FAIL, INC = "通过", "失败", "未完成"
NAK_SPAN = 360 / 27

FEEDBACK_SECTIONS = ("## 盘面初验结果", "## 验前事校准率", "## 生时矫正记录", "## 信号修正日志")
OLD_TRUST_PHRASES = ("✅ 可信（直接计算）", "全部分盘可信")


class Report:
    def __init__(self):
        self.items = []
        self.caps = []

    def add(self, name, status, detail=""):
        self.items.append((name, status, detail))

    def worst(self):
        sts = [s for _, s, _ in self.items]
        return FAIL if FAIL in sts else (INC if INC in sts else PASS)


def _sign_ok(x):
    return isinstance(x, str) and x in cio.SIGNS


def check_fields_json(doc, rep):
    ch = doc.get("chart", {})
    mode = doc.get("input", {}).get("mode", "full")
    errs = []
    lag = ch.get("lagna")
    lag_idx = None
    if mode == "date_only":
        if not cio.is_missing(lag):
            errs.append("chart.lagna: 仅日期模式不应有上升")
    else:
        if not isinstance(lag, dict) or not _sign_ok(lag.get("sign")):
            errs.append(f"chart.lagna.sign: 非法或缺失（{lag.get('sign') if isinstance(lag, dict) else lag}）")
        else:
            lag_idx = cio.SIGNS.index(lag["sign"])
    planets = ch.get("planets") or {}
    for name in cio.PLANETS9:
        p = planets.get(name)
        if not isinstance(p, dict):
            errs.append(f"chart.planets.{name}: 缺失")
            continue
        sign = p.get("sign")
        if cio.is_missing(sign):
            if mode != "date_only":
                errs.append(f"chart.planets.{name}.sign: {cio.missing_label(sign)}")
            continue
        if not _sign_ok(sign):
            errs.append(f"chart.planets.{name}.sign: 非法星座名「{sign}」")
            continue
        si = cio.SIGNS.index(sign)
        lon = p.get("longitude")
        if isinstance(lon, (int, float)):
            if not 0 <= lon < 360:
                errs.append(f"chart.planets.{name}.longitude: 超出 [0,360)：{lon}")
            elif int(lon // 30) != si:
                errs.append(f"chart.planets.{name}: 经度 {lon:.4f} 与星座 {sign} 不符")
            nk = p.get("nakshatra")
            if isinstance(nk, dict) and "name" in nk:
                nk_name = cio.canon_nakshatra(nk["name"])   # 旧盘里的 Moola 等异写按同一宿处理
                if nk_name not in cio.NAKSHATRAS:
                    errs.append(f"chart.planets.{name}.nakshatra: 非法宿名「{nk['name']}」")
                elif cio.NAKSHATRAS.index(nk_name) != int(lon // NAK_SPAN):
                    errs.append(f"chart.planets.{name}.nakshatra: {nk['name']} 与经度不符")
                if "pada" in nk and nk["pada"] not in (1, 2, 3, 4):
                    errs.append(f"chart.planets.{name}.nakshatra.pada: 非法 {nk['pada']}")
        deg = p.get("degree")
        if isinstance(deg, (int, float)) and not 0 <= deg < 30:
            errs.append(f"chart.planets.{name}.degree: 超出 [0,30)：{deg}")
        if lag_idx is not None:
            h = p.get("house")
            exp = (si - lag_idx) % 12 + 1
            if h != exp:
                errs.append(f"chart.planets.{name}.house: {h} 与星座/上升推出的 {exp} 不符")
    rep.add("字段合法性（chart_data.json）", FAIL if errs else PASS, "；".join(errs[:6]) + ("…" if len(errs) > 6 else ""))
    return lag_idx


_PLANET_ROW = re.compile(r"^\|\s*(Lagna|Sun|Moon|Mars|Mercury|Jupiter|Venus|Saturn|Rahu|Ketu)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|")


def check_fields_md(text, rep):
    sec = text.split("### 行星位置", 1)
    if len(sec) < 2:
        rep.add("字段合法性（structured_data.md）", INC, "找不到「行星位置」表")
        return
    body = sec[1].split("\n### ", 1)[0]
    errs, seen, lag_idx = [], set(), None
    rows = [m.groups() for m in (_PLANET_ROW.match(ln) for ln in body.splitlines()) if m]
    for name, sign, house, deg in rows:
        seen.add(name)
        if sign not in cio.SIGNS:
            errs.append(f"行星位置.{name}.星座: 非法星座名「{sign}」")
            continue
        if name == "Lagna":
            lag_idx = cio.SIGNS.index(sign)
    for name, sign, house, deg in rows:
        if name == "Lagna" or sign not in cio.SIGNS:
            continue
        if not house.isdigit() or not 1 <= int(house) <= 12:
            errs.append(f"行星位置.{name}.宫位: 非法「{house}」")
        elif lag_idx is not None and int(house) != (cio.SIGNS.index(sign) - lag_idx) % 12 + 1:
            errs.append(f"行星位置.{name}.宫位: {house} 与星座/上升不符")
        m = re.match(r"(\d+)°(\d+)'", deg)
        if not m or not (0 <= int(m.group(1)) < 30 and 0 <= int(m.group(2)) < 60):
            errs.append(f"行星位置.{name}.度数: 非法「{deg}」")
    missing = [n for n in ["Lagna"] + cio.PLANETS9 if n not in seen]
    if missing:
        errs.append("行星位置: 缺 " + "/".join(missing))
    rep.add("字段合法性（structured_data.md）", FAIL if errs else PASS, "；".join(errs[:6]))


def check_consistency(doc, text, rep):
    md_id = re.search(r"chart_id=([0-9a-f]{12})", text)
    if not md_id:
        rep.add("两份产物同源", INC, "structured_data.md 没有 chart_id（旧版文件），无法确认与 JSON 同源")
    elif md_id.group(1) != doc.get("chart_id"):
        rep.add("两份产物同源", FAIL, f"chart_id 不一致：md={md_id.group(1)} json={doc.get('chart_id')}，重新生成 md")
    else:
        rep.add("两份产物同源", PASS, f"chart_id={doc.get('chart_id')}")

    inp = doc.get("input", {})
    if inp.get("mode") == "date_only":
        rep.add("精度声明与审计范围", PASS, "仅日期模式：精度=不确定，不做分盘审计")
        return
    eff = inp.get("effective_minutes")
    audit = (doc.get("chart", {}).get("divisional_boundary_audit") or {})
    aud = audit.get("uncertainty_minutes") if audit.get("status") == "ok" else None
    m_eff = re.search(r"有效精度: [^（\n]*（±(\d+) 分钟", text)
    m_aud = re.search(r"实际审计范围: ±(\d+) 分钟", text)
    m_aud2 = re.search(r"边界审计范围: 报时前后±(\d+)分钟", text)
    problems = []
    if eff is None:
        problems.append("JSON 未记录有效精度")
    if aud is None:
        problems.append("JSON 未完成边界审计")
    if eff is not None and aud is not None and int(eff) != int(aud):
        problems.append(f"有效精度 ±{eff} ≠ 审计 ±{aud}")
    for label, m, want in (("md 有效精度", m_eff, eff), ("md 实际审计范围", m_aud, aud), ("md 分盘声明审计范围", m_aud2, aud)):
        if not m:
            problems.append(f"{label} 缺失")
        elif want is not None and int(m.group(1)) != int(want):
            problems.append(f"{label} ±{m.group(1)} 与 JSON ±{want} 不一致")
    if "有效精度: ±分钟级\n" in text or re.search(r"有效精度: ±分钟级\s*$", text, re.M):
        problems.append("有效精度写成缺省「±分钟级」但没有分钟数")
    hard = [p for p in problems if "不一致" in p or "≠" in p or "缺省" in p]
    legacy = doc.get("provenance", {}).get("source") == "legacy_md_import"
    if legacy and problems:
        rep.add("精度声明与审计范围", INC, "旧版导入：精度与审计信息不全，按未声明处理（" + "；".join(problems) + "）")
    else:
        rep.add("精度声明与审计范围", FAIL if hard else (INC if problems else PASS), "；".join(problems))

    # 分盘声明与审计结果一致；不得残留无条件“可信”字样
    mism = []
    if audit.get("status") == "ok":
        for key in ("D1", "D9", "D10", "D4", "D5"):
            stable = audit.get("charts", {}).get(key, {}).get("stable")
            m = re.search(rf"^{key}\s+(✅|⚠️)", text, re.M)
            if not m:
                mism.append(f"{key} 声明缺失")
            elif (m.group(1) == "✅") != bool(stable):
                mism.append(f"{key} 声明为{'稳定' if m.group(1) == '✅' else '边界敏感'}，审计结果相反")
    for ph in OLD_TRUST_PHRASES:
        if ph in text:
            mism.append(f"残留无条件可信字样「{ph}」")
    if mism and doc.get("provenance", {}).get("source") == "legacy_md_import" and audit.get("status") != "ok":
        rep.add("分盘声明与审计结果一致", INC, "旧版导入：没有边界审计；" + "；".join(mism))
        return
    rep.add("分盘声明与审计结果一致", FAIL if mism else (PASS if audit.get("status") == "ok" else INC),
            "；".join(mism) if mism else ("" if audit.get("status") == "ok" else "审计未完成"))


def legacy_doc(doc):
    return bool(doc) and doc.get("provenance", {}).get("source") == "legacy_md_import"


def run(md_path, json_path):
    rep = Report()
    text = open(md_path, encoding="utf-8").read() if md_path and os.path.exists(md_path) else None
    doc = None
    if json_path and os.path.exists(json_path):
        try:
            doc = cio.load_doc(json_path)
        except Exception as exc:
            rep.add("读取 chart_data.json", FAIL, str(exc))
    if doc is None and not any(n == "读取 chart_data.json" for n, _, _ in rep.items):
        rep.add("读取 chart_data.json", INC, "没有机器可读数据（旧版产物）：用 import_legacy_md.py 导入，缺项保持缺失")
    if text is None:
        rep.add("读取 structured_data.md", INC, "文件不存在")

    if doc:
        check_fields_json(doc, rep)
    if text:
        if not (doc and doc.get("input", {}).get("mode") == "date_only"):
            check_fields_md(text, rep)
        leak = [s for s in FEEDBACK_SECTIONS if s in text]
        rep.add("计算数据不含反馈信息", FAIL if leak else PASS,
                ("structured_data.md 含 " + "、".join(leak) + "：用 import_legacy_md.py 导入（会迁到 verification_record.md），或按出生信息重排") if leak else "")
    if doc and text:
        check_consistency(doc, text, rep)

    full = not (doc and doc.get("input", {}).get("mode") == "date_only")
    if full:
        tree = dc.tree_from_json(doc["chart"]) if doc else (dc.tree_from_md(text) if text else None)
        levels = None
        if tree:
            res = dc.check_tree(tree, tol_days=1 if legacy_doc(doc) else 0)
            levels = {k: res[k]["status"] for k in ("md", "ad", "pd")}
            rep.add("Vimsottari MD/AD/PD 层级", {"PASS": PASS, "FAIL": FAIL, "INCOMPLETE": INC}[res["overall"]],
                    "；".join(e for k in ("md", "ad", "pd") for e in (res[k]["errors"] + res[k].get("notes", []))[:2]))
        if doc:
            eff = doc.get("input", {}).get("effective_minutes")
            tr = doc.get("transit")
            rep.caps = cap.table(doc["chart"], eff if isinstance(eff, int) else None,
                                 transit_ok=bool(tr) and not cio.is_missing(tr), dasha_levels=levels,
                                 legacy=legacy_doc(doc))
        if doc:
            k = doc["chart"].get("karakas")
            k7 = k.get("7k") if isinstance(k, dict) else None
            k8 = k.get("8k") if isinstance(k, dict) else None
            if not (isinstance(k7, list) and isinstance(k8, list)):
                rep.add("Karaka 7K/8K 对照", INC, "缺 7K 或 8K 完整排序（旧版导入常见）；love/soul 需要 8K 时重排，不得自行补算")
            else:
                p7, p8 = [r[1] for r in k7], [r[1] for r in k8]
                errs = []
                if len(p7) != 7 or len(set(p7)) != 7 or set(p7) & {"Rahu", "Ketu"}:
                    errs.append(f"7K 应为 Sun~Saturn 七星各一次，实际 {p7}")
                if len(p8) != 8 or len(set(p8)) != 8 or "Rahu" not in p8 or "Ketu" in p8:
                    errs.append(f"8K 应为七星加 Rahu，实际 {p8}")
                if k.get("dk_7k") and p7 and k["dk_7k"] != p7[-1]:
                    errs.append(f"dk_7k={k['dk_7k']} 与 7K 末位 {p7[-1]} 不符")
                if isinstance(k.get("dk_8k"), str) and p8 and k["dk_8k"] != p8[-1]:
                    errs.append(f"dk_8k={k['dk_8k']} 与 8K 末位 {p8[-1]} 不符")
                rep.add("Karaka 7K/8K 对照", FAIL if errs else PASS, "；".join(errs))
        elif text:
            rep.add("Karaka 7K/8K 对照", PASS if "### Chara Karakas 7K/8K 对照" in text else INC,
                    "" if "### Chara Karakas 7K/8K 对照" in text else "旧版文件没有 8K 对照，需要 love/soul 的 8K 时重排")
        if doc:
            tr = doc.get("transit")
            rep.add("过运快照", PASS if (tr and not cio.is_missing(tr)) else INC,
                    f"提取时间点 {tr.get('date')}（使用前跑 check_freshness.py）" if (tr and not cio.is_missing(tr)) else cio.missing_label(tr) if tr else "缺失")
    else:
        unstable = [n for n, p in (doc["chart"].get("planets") or {}).items()
                    if isinstance(p, dict) and cio.is_missing(p.get("sign"))]
        rep.add("能力范围（仅日期）", INC,
                "只能用全天稳定的行星星座与宿；上升、宫位、宫主、分盘、Vimsottari、Karaka、过运宫位为不适用/未计算"
                + (f"；当天换座、星座不定: {', '.join(unstable)}" if unstable else "")
                + "。合盘与时机只执行允许的部分，相关结论标限制")
    return rep


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir")
    ap.add_argument("--file")
    a = ap.parse_args()
    if not (a.dir or a.file):
        ap.error("需要 --dir 或 --file")
    if a.dir:
        md = os.path.join(a.dir, "structured_data.md")
        js = os.path.join(a.dir, "chart_data.json")
    else:
        md = a.file
        js = os.path.join(os.path.dirname(os.path.abspath(a.file)), "chart_data.json")
    rep = run(md, js)
    w = max(len(n) for n, _, _ in rep.items)
    for n, s, d in rep.items:
        print(f"{n.ljust(w)}  {s}" + (f"  — {d}" if d else ""))
    if rep.caps:
        print("\n能力范围（有效精度 × 边界审计 × Dasha 检查；规则见 shared/divisional.md §1、shared/time_window.md §1）")
        wk = max(len(k) for k, _, _ in rep.caps)
        for k, st, d in rep.caps:
            print(f"  {k.ljust(wk)}  {st}" + (f"  — {d}" if d else ""))
    worst = rep.worst()
    print(f"\n总体: {worst}")
    sys.exit({PASS: 0, FAIL: 1, INC: 2}[worst])


if __name__ == "__main__":
    main()
