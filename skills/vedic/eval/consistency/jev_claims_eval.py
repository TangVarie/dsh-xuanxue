#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
jev_claims_eval.py —— 用金标准例检验闭集抽取（fixtures/jev_gold/cases.yaml）

  用法:
    python3 jev_claims_eval.py                      有密钥时 Jev 和字符串基线都跑；没密钥只跑基线
    python3 jev_claims_eval.py --engine jev         只跑 Jev
    python3 jev_claims_eval.py --out report.md      报告写文件

  先看哪几个数（这是回归门的抽取器，按危害排）:
    错值   抽到了，但值不对 —— 会凭空造出矛盾，或者把真矛盾盖掉，最要命
    误抽   报告没这么说却抽了（多半是踩了陷阱：假设句、D9、AmK、"落在某宫"……）
    漏抽   报告说了没抽到 —— 只是少查一项，不会造假矛盾
    待复核 没把握、没写进 claims 的项 —— 要人看，但不会出错
  Jev 要用，至少得在"错值 + 误抽"上明显少于字符串基线；否则不如用 Claude 抽、人扫一眼。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import jev_extract_claims as jx  # noqa: E402

GOLD_PATH = HERE / "fixtures" / "jev_gold" / "cases.yaml"
SKIP = {"skill", "_extractor", "dasha"}


def flatten(claims: dict) -> dict:
    out = {}
    for field, val in (claims or {}).items():
        if field in SKIP:
            continue
        if isinstance(val, dict):
            for k, v in val.items():
                out[f"{field}.{k}"] = v
        else:
            out[field] = val
    return out


def score_case(case: dict, claims: dict, records: list[dict]) -> dict:
    gold, got = flatten(case.get("gold") or {}), flatten(claims)
    review = {f"{r['field']}.{r['key']}" if r["key"] else r["field"]
              for r in records if r["status"] == "needs_review"}
    traps = set(case.get("traps") or [])
    res = {"tp": [], "wrong": [], "fn": [], "fp": [], "trap_hits": [], "review": sorted(review),
           "review_ok": [], "review_missed": []}
    for k, v in gold.items():
        if k not in got:
            res["fn"].append(k + ("（标了待复核）" if k in review else ""))
        elif got[k] == v:
            res["tp"].append(k)
        else:
            res["wrong"].append(f"{k}: 抽了 {got[k]}，应为 {v}")
            if f"{k}={got[k]}" in traps:
                res["trap_hits"].append(f"{k}={got[k]}")
    for k, v in got.items():
        if k not in gold:
            res["fp"].append(f"{k}={v}")
            if f"{k}={v}" in traps:
                res["trap_hits"].append(f"{k}={v}")
    for k in case.get("expect_review") or []:
        (res["review_ok"] if (k in review and k not in got) else res["review_missed"]).append(k)
    return res


def summarize(rows: list[dict]) -> dict:
    tot = {k: sum(len(r["score"][k]) for r in rows)
           for k in ("tp", "wrong", "fn", "fp", "trap_hits", "review", "review_ok", "review_missed")}
    denom_p = tot["tp"] + tot["wrong"] + tot["fp"]
    denom_r = tot["tp"] + tot["wrong"] + tot["fn"]
    tot["precision"] = tot["tp"] / denom_p if denom_p else None
    tot["recall"] = tot["tp"] / denom_r if denom_r else None
    tot["n_traps"] = sum(len(r["case"].get("traps") or []) for r in rows)
    tot["n_expect_review"] = sum(len(r["case"].get("expect_review") or []) for r in rows)
    tot["calls"] = sum(r["meta"]["calls"] for r in rows)
    return tot


def pct(x) -> str:
    return "—" if x is None else f"{x:.0%}"


def report(runs: dict, gold: dict, bank: dict) -> str:
    lines = ["# 闭集抽取 · 金标准例报告", "",
             f"金标准 {gold.get('gold_version')}（{len(gold['cases'])} 段报告）· 题库 {bank.get('bank_version')} · "
             f"判定门槛 {bank['decision']['min_top']} / {bank['decision']['min_margin']}", ""]
    sums = {name: summarize(rows) for name, rows in runs.items()}
    names = list(runs)
    lines += ["| 指标 | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]

    def row(label, fn):
        lines.append(f"| {label} | " + " | ".join(fn(sums[n]) for n in names) + " |")
    row("**错值**（抽到但值不对）", lambda s: str(s["wrong"]))
    row("**误抽**（报告没这么说）", lambda s: str(s["fp"]))
    row("其中踩陷阱", lambda s: f"{s['trap_hits']} / {s['n_traps']}")
    row("正确写入", lambda s: str(s["tp"]))
    row("漏抽", lambda s: str(s["fn"]))
    row("待复核（未写入）", lambda s: str(s["review"]))
    row("前后不一被标出", lambda s: f"{s['review_ok']} / {s['n_expect_review']}")
    row("精确率", lambda s: pct(s["precision"]))
    row("召回率", lambda s: pct(s["recall"]))
    row("调用次数", lambda s: str(s["calls"]))
    for name, rows in runs.items():
        lines += ["", f"## 逐段问题（{name}）", ""]
        bad = False
        for r in rows:
            s = r["score"]
            issues = ([f"错值 {x}" for x in s["wrong"]] + [f"误抽 {x}" for x in s["fp"]]
                      + [f"漏抽 {x}" for x in s["fn"]] + [f"该标待复核没标 {x}" for x in s["review_missed"]])
            if issues:
                bad = True
                lines.append(f"- **{r['case']['id']}**（{r['case'].get('note', '')}）：" + "；".join(issues))
        if not bad:
            lines.append("- 全部正确。")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="闭集抽取 · 金标准例检验")
    ap.add_argument("--engine", choices=("baseline", "jev", "both"))
    ap.add_argument("--out")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args(argv)

    import yaml  # noqa: PLC0415
    bank = jx.load_bank()
    gold = yaml.safe_load(GOLD_PATH.read_text(encoding="utf-8"))
    key = jx.find_api_key()
    choice = args.engine or ("both" if key else "baseline")
    if choice in ("jev", "both") and not key:
        print("没有找到 Jev 密钥：先 export TYPESAFE_API_KEY=...（或 --engine baseline）", file=sys.stderr)
        return 1
    engines = []
    if choice in ("baseline", "both"):
        engines.append(("字符串基线", jx.BaselineEngine(bank)))
    if choice in ("jev", "both"):
        model = __import__("os").environ.get("JEV_MODEL") or bank["model"]
        engines.append((f"Jev {model}", jx.JevEngine(key, model)))

    runs = {}
    for name, engine in engines:
        rows = []
        for case in gold["cases"]:
            try:
                claims, records, meta = jx.extract(case["report"], case["skill"], engine, bank, workers=args.workers)
            except jx.JevError as exc:
                print(f"[{case['id']}] 抽取失败：{exc}", file=sys.stderr)
                return 1
            rows.append({"case": case, "meta": meta, "score": score_case(case, claims, records)})
        runs[name] = rows
    text = report(runs, gold, bank)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"报告已写入 {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
