#!/usr/bin/env python3
"""analysis_record.py — 分析记录（结论、依据、模式、数据版本、变更日志），规则见 shared/permissions.md 与 shared/versioning.md。

每个分析模块一份：<工作目录>/analysis_record_<module>.json（core 也可写 analysis_record.json）。

  init    初始推导开始前：绑定当前 chart_data.json 的 chart_id / audit_id / 规则版本 / 基准日 / 模式
          合盘等多盘分析：--chart A/chart_data.json --chart B/chart_data.json（可写 标签=路径），各方 chart_id 都登记
  add     记一条结论：python analysis_record.py add --file R --id C1 --claim "..." --evidence "..." --resolution AD
  freeze  初始推导结束：锁定初始结论（之后才允许读验证记录 / 用户反馈）
  change  反馈复核或纠错：原结论 → 新证据 → 修改原因 → 新结论（--kind 读数错误/规则应用错误/新输入推翻前提/反馈复核）
  stage   设置阶段 initial / reviewed / expressed；读过反馈后 mode 自动改为 calibrated
  show    打印全部结论与变更日志（变更编号 X1、X2…，与结论编号分开）

模式（mode）：
  strict_blind  初始推导在未接触用户经历与反馈的执行环境中完成（如单独开的子任务，只拿到 chart_data.json）
  chart_derived 结论都有盘面依据，但执行时同一会话接触过用户经历（默认）
  calibrated    初始结论冻结后读过验证记录 / 用户反馈并复核
"""
import argparse
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "calculator", "scripts"))
try:
    from chart_io import RULES_VERSION  # noqa: E402  当前 skill 的规则版本（不取盘内字段）
except ImportError:
    RULES_VERSION = "vedic-5.2"

SCHEMA = "vedic-analysis/1.0"
MODES = ("strict_blind", "chart_derived", "calibrated")
KINDS = ("读数错误", "规则应用错误", "新输入推翻前提", "反馈复核")


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save(p, d):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("init")
    i.add_argument("--dir", required=True)
    i.add_argument("--module", required=True)
    i.add_argument("--mode", default="chart_derived", choices=MODES)
    i.add_argument("--file", default=None)
    i.add_argument("--as-of", default=None)
    i.add_argument("--chart", action="append", default=[],
                   help="多盘分析（合盘）时逐个登记各方 chart_data.json，可写 标签=路径；不给则用 --dir 下的 chart_data.json")
    for name in ("add", "freeze", "change", "stage", "show"):
        p = sub.add_parser(name)
        p.add_argument("--file", required=True)
        if name == "add":
            p.add_argument("--id", required=True)
            p.add_argument("--claim", required=True)
            p.add_argument("--evidence", required=True)
            p.add_argument("--resolution", default="structural", help="structural/MD/AD/PD/transit")
        if name == "change":
            p.add_argument("--id", required=True)
            p.add_argument("--new-evidence", required=True)
            p.add_argument("--reason", required=True)
            p.add_argument("--new", required=True)
            p.add_argument("--kind", required=True, choices=KINDS)
        if name == "stage":
            p.add_argument("--set", required=True, choices=("initial", "reviewed", "expressed"))
            p.add_argument("--read-feedback", action="store_true", help="本阶段读过验证记录或用户反馈")
    a = ap.parse_args()

    if a.cmd == "init":
        path = a.file or os.path.join(a.dir, f"analysis_record_{a.module}.json")
        charts = []
        for spec in a.chart:
            label, _, cpath = spec.rpartition("=") if "=" in spec else ("", "", spec)
            if not os.path.exists(cpath):
                print(f"找不到 {cpath}")
                sys.exit(1)
            cd = load(cpath)
            charts.append({"label": label or os.path.basename(os.path.dirname(os.path.abspath(cpath))),
                           "path": os.path.relpath(os.path.abspath(cpath), os.path.dirname(os.path.abspath(path))),
                           "chart_id": cd.get("chart_id"), "audit_id": cd.get("audit_id"),
                           "engine_version": cd.get("engine_version")})
        if not charts:
            own = os.path.join(a.dir, "chart_data.json")
            if not os.path.exists(own):
                print(f"{a.dir} 下没有 chart_data.json：先排盘；合盘等多盘分析用 --chart A/chart_data.json --chart B/chart_data.json")
                sys.exit(1)
            cd = load(own)
            charts_main = {"chart_id": cd.get("chart_id"), "audit_id": cd.get("audit_id"),
                           "engine_version": cd.get("engine_version")}
        else:
            charts_main = {"chart_id": charts[0]["chart_id"], "audit_id": charts[0]["audit_id"],
                           "engine_version": charts[0].get("engine_version")}
        if os.path.exists(path):
            old = load(path)
            if charts:
                same = sorted(c.get("chart_id") for c in old.get("charts") or []) == sorted(c["chart_id"] for c in charts)
            else:
                same = old.get("chart_id") == charts_main["chart_id"]
            print(f"{path} 已存在（chart_id={old.get('chart_id')}，结论 {len(old.get('conclusions', []))} 条，"
                  f"变更 {len(old.get('changes', []))} 条），不覆盖。"
                  + ("同一张盘继续用它；确要重做，先把它移到别处保存。" if same else
                     ("登记的盘已变：先对本目录运行 shared/scripts/archive_chart.py（合盘子目录会归档合盘记录与报告）再 init。"
                      if charts else
                      f"盘已变（当前 {charts_main['chart_id']}）：先运行 shared/scripts/archive_chart.py 归档旧盘产物再 init。")))
            sys.exit(1)
        rec = {"schema": SCHEMA, "module": a.module, "mode": a.mode,
               "chart_id": charts_main["chart_id"], "audit_id": charts_main["audit_id"],
               "rules_version": RULES_VERSION, "engine_version": charts_main.get("engine_version"),
               "as_of": a.as_of or dt.date.today().isoformat(),
               "created_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
               "stage": "initial", "frozen": False,
               "inputs_used": {"chart_data": True, "verification_record": False, "user_context": False},
               "conclusions": [], "changes": []}
        if charts:
            rec["charts"] = charts
        save(path, rec)
        print(f"[写出] {path}  chart_id={rec['chart_id']} mode={rec['mode']} 基准日={rec['as_of']}"
              + (f"  登记 {len(charts)} 张盘" if charts else ""))
        return
    rec = load(a.file)
    if a.cmd == "add":
        if rec.get("frozen"):
            print("初始结论已冻结，不再新增结论：复核时对已有结论用 change；确属新问题（如 QA 新问的专题）另建一份记录")
            sys.exit(1)
        if any(c["id"] == a.id for c in rec["conclusions"]):
            print(f"结论编号 {a.id} 已存在")
            sys.exit(1)
        rec["conclusions"].append({"id": a.id, "claim": a.claim, "evidence": a.evidence,
                                   "resolution": a.resolution, "feedback_used": rec["inputs_used"]["verification_record"]})
    elif a.cmd == "freeze":
        rec["frozen"] = True
        rec["frozen_at"] = dt.datetime.now().isoformat(timespec="seconds")
    elif a.cmd == "change":
        old = next((c for c in rec["conclusions"] if c["id"] == a.id), None)
        if old is None:
            print(f"找不到结论 {a.id}")
            sys.exit(1)
        if a.kind == "反馈复核" and not rec.get("frozen"):
            print("初始结论未冻结，不能按反馈修改：先 freeze")
            sys.exit(1)
        rec["changes"].append({"change_id": f"X{len(rec['changes']) + 1}", "conclusion_id": a.id,
                               "old": old["claim"], "new_evidence": a.new_evidence,
                               "reason": a.reason, "new": a.new, "kind": a.kind,
                               "at": dt.datetime.now().isoformat(timespec="seconds")})
        old["claim"] = a.new
        old["feedback_used"] = old.get("feedback_used") or a.kind == "反馈复核"
    elif a.cmd == "stage":
        if a.read_feedback:
            if not rec.get("frozen"):
                print("初始结论未冻结，不能读反馈：先 freeze")
                sys.exit(1)
            rec["inputs_used"]["verification_record"] = True
            rec["mode"] = "calibrated"
        rec["stage"] = a.set
    if a.cmd != "show":
        save(a.file, rec)
    else:
        print(f"模块 {rec['module']} · 模式 {rec['mode']} · 阶段 {rec['stage']} · 冻结 {rec.get('frozen')} · "
              f"chart_id={rec['chart_id']} · 规则 {rec.get('rules_version')} · 基准日 {rec.get('as_of')}")
        for ch in rec.get("charts") or []:
            print(f"  盘 {ch['label']}: {ch['chart_id']}（{ch['path']}）")
        print("结论:")
        for c in rec["conclusions"]:
            print(f"  {c['id']} [{c.get('resolution')}] {c['claim']} ← {c['evidence']}"
                  + ("（用过反馈）" if c.get("feedback_used") else ""))
        print("变更日志:")
        for x in rec["changes"]:
            print(f"  {x.get('change_id', '—')} {x['conclusion_id']}（{x['kind']}）: {x['old']} → 新证据 {x['new_evidence']} "
                  f"→ 原因 {x['reason']} → {x['new']}")
        if not rec["changes"]:
            print("  无")
        return
    print(f"{rec['module']} · mode={rec['mode']} · stage={rec['stage']} · frozen={rec.get('frozen')} · "
          f"chart_id={rec['chart_id']} · 结论 {len(rec['conclusions'])} 条 · 变更 {len(rec['changes'])} 条")


if __name__ == "__main__":
    main()
