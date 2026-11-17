#!/usr/bin/env python3
"""check_freshness.py — 读旧报告/旧摘要前的失效检查（规则见 shared/versioning.md）。

python check_freshness.py --dir <某人的工作目录> [--today YYYY-MM-DD]

分别检查，不用一个总开关：
  1. 分析记录 / core_summary 绑定的 chart_id ≠ 当前 chart_data.json → 旧分析失效，相关结论待更新
  2. audit_id 不同（误差范围变了）→ 依赖分盘的结论待复核
  3. 规则版本不同 → 列出需复核
  4. 查询日期变了 → 用今天重新定位 MD/AD/PD；运期变了就更新时效段落
  5. 过运快照：快照日之后已有换座（即使不满 3 个月）→ 更新过运判断；超过 90 天 → 重取
  6. 验证记录绑定的 chart_id ≠ 当前盘 → 旧盘验证，不能当新盘验证
  7. user_context.md 在分析之后被修改 → 更新表达与建议，必要时进入差异复核
  8. chart_data.json 由旧版引擎生成 / 分析记录用旧规则写成（与当前 skill 比，不与盘内字段比）→ 重排或复核
  合盘子目录（没有自己的 chart_data.json）：按分析记录里登记的双方盘路径逐一核对 chart_id
退出码: 0 全部有效 / 1 有需更新项 / 2 有无法判断项（且无需更新项）
"""
import argparse
import datetime as dt
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "calculator", "scripts"))
try:
    from chart_io import ENGINE_VERSION as CUR_ENGINE, RULES_VERSION as CUR_RULES  # noqa: E402
    from chart_io import ENGINE_CHANGE_NOTE, RULES_CHANGE_NOTE  # noqa: E402
except ImportError:  # 单独拷出本脚本时
    CUR_ENGINE, CUR_RULES = None, "vedic-5.2"
    ENGINE_CHANGE_NOTE = RULES_CHANGE_NOTE = ""


def _note(text):
    return f"（{text}）" if text else ""

OK, STALE, UNK = "有效", "需更新", "无法判断"


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def current_periods(chart, day):
    """返回 day 当天所在的 (MD, AD, PD) 行星名；找不到返回 None。"""
    dashas = chart.get("dashas")
    if not isinstance(dashas, list):
        return None
    key = day.isoformat()
    for md in dashas:
        for ad in md.get("antardashas") or []:
            a0, a1 = str(ad.get("start_time") or ad["start"])[:10], str(ad.get("end_time") or ad["end"])[:10]
            if a0 <= key < a1:
                pd_name = None
                for pd in ad.get("pratyantardashas") or []:
                    p0, p1 = str(pd.get("start_time") or pd["start"])[:10], str(pd.get("end_time") or pd["end"])[:10]
                    if p0 <= key < p1:
                        pd_name = pd["planet"]
                return (md["planet"], ad["planet"], pd_name)
    return None


def summary_header(path):
    if not os.path.exists(path):
        return None
    text = open(path, encoding="utf-8").read(3000)
    m = re.search(r"chart_id=([0-9a-f]{12})", text)
    if not m:
        return {"chart_id": None}
    a = re.search(r"audit_id=([0-9a-f]{12})", text)
    r = re.search(r"规则 (vedic-[\d.]+)", text)
    d = re.search(r"基准日 (\d{4}-\d{2}-\d{2})", text)
    return {"chart_id": m.group(1), "audit_id": a.group(1) if a else None,
            "rules_version": r.group(1) if r else None, "as_of": d.group(1) if d else None}


def check_multi(d, today=None):
    """合盘子目录：没有自己的 chart_data.json，按分析记录登记的各方盘路径核对。"""
    today = today or dt.date.today()
    recs = sorted(glob.glob(os.path.join(d, "analysis_record*.json")))
    regs, metas = [], []
    for p in recs:
        try:
            r = load(p)
        except ValueError:
            continue
        metas.append((os.path.basename(p), r))
        for ch in r.get("charts") or []:
            regs.append((os.path.basename(p), ch, r))
    if not regs:
        print(f"{UNK}  没有 chart_data.json，也没有登记各方盘的分析记录：旧版产物先导入或重排；"
              "合盘目录用 analysis_record.py init --chart A/chart_data.json --chart B/chart_data.json 建记录")
        return 2
    worst = OK
    for name, r in metas:
        if r.get("rules_version") and r["rules_version"] != CUR_RULES:
            print(f"{STALE}  {name} 用规则 {r['rules_version']} 写成，当前 {CUR_RULES}：标明需复核的结论{_note(RULES_CHANGE_NOTE)}")
            worst = STALE
    for name, ch, r in regs:
        path = ch.get("path") or ""
        full = path if os.path.isabs(path) else os.path.normpath(os.path.join(d, path))
        if not os.path.exists(full):
            print(f"{UNK}  {name}：登记的盘 {path} 不存在")
            worst = STALE if worst == STALE else UNK
            continue
        cdoc = load(full)
        cur = cdoc.get("chart_id")
        if cur == ch.get("chart_id") and r.get("as_of"):
            p0 = current_periods(cdoc.get("chart", {}), dt.date.fromisoformat(r["as_of"]))
            p1 = current_periods(cdoc.get("chart", {}), today)
            if p0 and p1 and p0[:2] != p1[:2]:
                print(f"{STALE}  {name}：{ch.get('label') or path} 的运期自基准日 {r['as_of']} 起已变（MD/AD {'-'.join(p0[:2])} → "
                      f"{'-'.join(p1[:2])}）：重新生成 synastry_data（--today）并更新时机层")
                worst = STALE
        if cur != ch.get("chart_id"):
            print(f"{STALE}  {name}：{ch.get('label') or path} 的盘已变（记录 {ch.get('chart_id')}，现在 {cur}）："
                  "合盘数据重新生成（build_synastry_data.py），相关结论待更新")
            worst = STALE
        else:
            print(f"{OK}  {name}：{ch.get('label') or path} 仍为 {cur}")
    print(f"\n总体: {worst}")
    return {OK: 0, STALE: 1, UNK: 2}[worst]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", required=True)
    ap.add_argument("--today", default=None)
    a = ap.parse_args()
    today = dt.date.fromisoformat(a.today) if a.today else dt.date.today()
    items = []
    cpath = os.path.join(a.dir, "chart_data.json")
    if not os.path.exists(cpath):
        sys.exit(check_multi(a.dir, today))
    doc = load(cpath)
    chart = doc.get("chart", {})
    cur_id, cur_audit, cur_rules = doc.get("chart_id"), doc.get("audit_id"), CUR_RULES
    legacy = doc.get("provenance", {}).get("source") == "legacy_md_import"
    if CUR_ENGINE and not legacy and doc.get("engine_version") != CUR_ENGINE:
        items.append((STALE, f"chart_data.json 由引擎 {doc.get('engine_version')} 生成，当前 {CUR_ENGINE}："
                             "用 build_chart.py 按原参数重排（chart_id 不变时旧分析可对照复核，Dasha 日期以新盘为准）"
                             + _note(ENGINE_CHANGE_NOTE)))

    records = []
    for p in sorted(glob.glob(os.path.join(a.dir, "analysis_record*.json")) +
                    glob.glob(os.path.join(a.dir, "parts", "analysis_record*.json"))):
        try:
            r = load(p)
            r["_path"] = os.path.relpath(p, a.dir)
            records.append(r)
        except ValueError:
            items.append((UNK, f"{os.path.basename(p)} 不是合法 JSON"))
    sh = summary_header(os.path.join(a.dir, "core_summary.md"))
    if sh is not None:
        sh["_path"] = "core_summary.md"
        sh["module"] = "core_summary"
        records.append(sh)
    if not records:
        archived = [d for d in sorted(glob.glob(os.path.join(a.dir, "archive", "*")))
                    if glob.glob(os.path.join(d, "analysis_record*.json")) or os.path.exists(os.path.join(d, "core_summary.md"))]
        if archived:
            items.append((STALE, "当前盘还没有分析；旧盘的分析已归档在 " +
                          "、".join(os.path.relpath(d, a.dir) + "/" for d in archived) +
                          "（绑定旧 chart_id，不适用当前盘）：需要的专题从初始推导重新做"))
        else:
            items.append((UNK, "没有分析记录或 core_summary：无法判断旧结论是否适用（新分析用 analysis_record.py init 建记录）"))

    for r in records:
        name = r["_path"]
        if not r.get("chart_id"):
            items.append((UNK, f"{name} 没有记录 chart_id（5.1 之前的产物）：引用前当作待复核"))
            continue
        if r["chart_id"] != cur_id:
            items.append((STALE, f"{name} 绑定 chart_id={r['chart_id']}，当前盘 {cur_id}：出生数据或计算设置变了，"
                                 "旧分析失效，相关结论标待更新，不得直接引用"))
            continue
        if r.get("audit_id") and r["audit_id"] != cur_audit:
            items.append((STALE, f"{name} 的误差审计范围与当前不同：依赖分盘宫位/宫主的结论待复核"))
        if r.get("engine_version") and doc.get("engine_version") and r["engine_version"] != doc["engine_version"]:
            items.append((STALE, f"{name} 写于引擎 {r['engine_version']} 生成的盘，现盘由 {doc['engine_version']} 重排："
                                 "chart_id 未变，但 Dasha 日期等数值可能变了，复核时机相关结论" + _note(ENGINE_CHANGE_NOTE)))
        if r.get("rules_version") and r["rules_version"] != cur_rules:
            items.append((STALE, f"{name} 用规则 {r['rules_version']} 写成，当前 {cur_rules}：标明需复核的结论{_note(RULES_CHANGE_NOTE)}"))
        as_of = r.get("as_of")
        if as_of:
            p0 = current_periods(chart, dt.date.fromisoformat(as_of))
            p1 = current_periods(chart, today)
            if p0 is None or p1 is None:
                items.append((UNK, f"{name}：基准日或今天不在 Dasha 表范围内"))
            elif p0 != p1:
                lv = ["MD", "AD", "PD"]
                diff = [f"{lv[i]} {p0[i]}→{p1[i]}" for i in range(3) if p0[i] != p1[i]]
                items.append((STALE, f"{name} 基准日 {as_of} 后运期已变（{'，'.join(diff)}）：更新时效相关段落"))
            else:
                items.append((OK, f"{name} 运期仍为 {'-'.join(x for x in p1 if x)}（基准日 {as_of}）"))
        else:
            items.append((UNK, f"{name} 没有基准日：时效段落按今天重新定位"))

    tr = doc.get("transit")
    if isinstance(tr, dict) and tr.get("date") and dt.date.fromisoformat(str(tr["date"])[:10]) > today:
        items.append((UNK, f"过运快照日期 {str(tr['date'])[:10]} 晚于今天 {today}（时区差或日期设置）：按今天用 transit.py --chart chart_data.json --write 重取"))
    elif isinstance(tr, dict) and tr.get("date"):
        snap = dt.date.fromisoformat(str(tr["date"])[:10])
        fi = tr.get("future_ingress") if isinstance(tr.get("future_ingress"), list) else []
        moved = [e for e in fi if snap.isoformat() < str(e["date"]) <= today.isoformat()]
        horizon = max((str(e["date"]) for e in fi), default=None)
        if moved:
            items.append((STALE, "过运快照 " + snap.isoformat() + " 之后已换座：" +
                          "；".join(f"{e['date']} {e['planet']} {e['from_sign']}→{e['to_sign']}" for e in moved) +
                          "——更新过运及相关判断（不论是否满 3 个月）"))
        elif (today - snap).days > 90:
            items.append((STALE, f"过运快照 {snap} 已超过 90 天：用 calculator/scripts/transit.py --chart chart_data.json --write 重取"))
        elif horizon and today.isoformat() > horizon:
            items.append((UNK, "今天超出换座表覆盖范围：用 transit.py --chart chart_data.json --write 重取过运"))
        else:
            items.append((OK, f"过运快照 {snap} 之后到今天没有慢行星换座"))
    else:
        items.append((UNK, "没有过运快照"))

    vmd = os.path.join(a.dir, "verification_record.md")
    if os.path.exists(vmd):
        m = re.search(r"chart_id=([0-9a-f]{12})", open(vmd, encoding="utf-8").read(4000))
        if m and m.group(1) != cur_id:
            items.append((STALE, f"verification_record.md 绑定旧盘 {m.group(1)}：属于旧盘的反馈，用 archive_chart.py 归档或移走，"
                                 "不能当作当前盘的验证"))
    vpath = os.path.join(a.dir, "verification_record.json")
    if os.path.exists(vpath):
        v = load(vpath)
        if v.get("chart_id") != cur_id:
            items.append((STALE, f"verification_record.json 绑定旧盘 {v.get('chart_id')}：保留作历史，"
                                 "不能当作当前盘的验证；需要时对新盘另建记录"))
        else:
            items.append((OK, "验证记录绑定当前盘"))

    uc = os.path.join(a.dir, "user_context.md")
    if os.path.exists(uc):
        uc_t = dt.datetime.fromtimestamp(os.path.getmtime(uc)).astimezone()
        for r in records:
            if r.get("chart_id") != cur_id:
                continue
            ref = None
            if r.get("created_at"):
                try:
                    ref = dt.datetime.fromisoformat(r["created_at"])
                    ref = ref if ref.tzinfo else ref.astimezone()
                except ValueError:
                    ref = None
            later = (uc_t > ref) if ref else (r.get("as_of") and uc_t.date() > dt.date.fromisoformat(r["as_of"]))
            if later:
                items.append((STALE, f"user_context.md 在 {r['_path']} 建立之后更新过：更新表达与建议，必要时进入反馈复核"))

    arch = os.path.join(a.dir, "archive")
    if os.path.isdir(arch):
        olds = sorted(d for d in os.listdir(arch) if os.path.isdir(os.path.join(arch, d)))
        if olds:
            items.append((OK, f"旧盘产物已归档：archive/{', archive/'.join(olds)}（绑定旧 chart_id，不适用当前盘，只作对照）"))

    for st, msg in items:
        print(f"{st}  {msg}")
    sts = {s for s, _ in items}
    worst = STALE if STALE in sts else (UNK if UNK in sts else OK)
    print(f"\n总体: {worst}（今天 {today}）")
    sys.exit({OK: 0, STALE: 1, UNK: 2}[worst])


if __name__ == "__main__":
    main()
