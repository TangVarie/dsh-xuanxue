#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用金标准例检验 Jev 来意预判（scripts/jev_gold.yaml）

  python scripts/jev_eval.py                       中文题干跑一遍，报告打到标准输出
  python scripts/jev_eval.py --lang both           中英文题干各跑一遍，对比
  python scripts/jev_eval.py --mock                不联网，只检验流程（数字没有意义）
  python scripts/jev_eval.py --out report.md --raw raw.json

看什么
  · 用神·明确例：第一名是否落在可接受集合里；有没有把明确的例子误标成歧义
  · 用神·歧义例：有没有标出歧义（或选"说不清"）——这是 Jev 概率真正有用的地方
  · 类别 / 动机 / 谁的事 / 一念一事 / 来意清楚：各自的命中率
  · 用神答对与答错时，第一名的平均概率（粗看概率可信不可信）
密钥与模型：同 scripts/jev_judge.py。没有密钥时直接退出并说明。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import jev_judge  # noqa: E402

GOLD_PATH = Path(__file__).resolve().parent / "jev_gold.yaml"
CASE_FIELDS = jev_judge.ALLOWED_FIELDS
LABELED_FIELDS = ("matter_category", "wenfa_type", "motive", "asker_role")
BOOL_FIELDS = ("single_matter", "intent_clear", "involves_decision")


def load_gold(path: Path = GOLD_PATH) -> dict:
    import yaml  # noqa: PLC0415
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def run(gold: dict, bank: dict, lang: str, mock: bool, timeout: float) -> list[dict]:
    rows = []
    for case in gold["cases"]:
        payload = {k: case[k] for k in CASE_FIELDS if case.get(k)}
        result = jev_judge.judge(payload, lang=lang, mock=mock, timeout=timeout, bank=bank)
        if result["status"] not in ("ok", "mock"):
            raise SystemExit(f"[{case['id']}] {result['status']}/{result.get('error_code')}：{result.get('reason')}")
        rows.append({"case": case, "result": result})
    return rows


def score(rows: list[dict]) -> dict:
    s = {"clear_n": 0, "clear_hit": 0, "clear_false_alarm": 0, "amb_n": 0, "amb_caught": 0,
         "other_amb_n": 0, "other_amb_caught": 0, "p_hit": [], "p_miss": [], "fields": {}}
    for row in rows:
        exp, ans = row["case"]["expect"], row["result"]["answers"]
        ys = ans.get("yongshen_main", {})
        if "yongshen" in exp:
            s["clear_n"] += 1
            hit = ys.get("answer") in exp["yongshen"]
            s["clear_hit"] += hit
            s["clear_false_alarm"] += bool(ys.get("ambiguous"))
            top_p = ys["top3"][0][1] if ys.get("top3") else None
            if top_p is not None:
                (s["p_hit"] if hit else s["p_miss"]).append(top_p)
            row["yongshen_verdict"] = ("✓" if hit else "✗") + ("（标了歧义）" if ys.get("ambiguous") else "")
        elif exp.get("yongshen_ambiguous"):
            s["amb_n"] += 1
            caught = bool(ys.get("ambiguous"))
            s["amb_caught"] += caught
            row["yongshen_verdict"] = "✓ 标出歧义" if caught else "✗ 没标出"
        for qid in exp.get("ambiguous_items", []):
            s["other_amb_n"] += 1
            s["other_amb_caught"] += bool(ans.get(qid, {}).get("ambiguous"))
        for field in LABELED_FIELDS:
            if field in exp:
                f = s["fields"].setdefault(field, [0, 0])
                f[0] += 1
                f[1] += ans.get(field, {}).get("answer") == exp[field]
        for field in BOOL_FIELDS:
            if field in exp:
                f = s["fields"].setdefault(field, [0, 0])
                item = ans.get(field, {})
                f[0] += 1
                f[1] += (not item.get("ambiguous")) and item.get("answer") == exp[field]
    return s


def pct(a: int, b: int) -> str:
    return f"{a}/{b}（{a / b:.0%}）" if b else "—"


def mean(xs: list[float]) -> str:
    return f"{sum(xs) / len(xs):.2f}" if xs else "—"


def report(all_runs: dict, gold: dict, bank: dict, mock: bool) -> str:
    lines = [f"# Jev 来意预判 · 金标准例报告",
             "",
             f"金标准 {gold.get('gold_version')} · 题库 {bank.get('bank_version')} · "
             f"模型 {next(iter(all_runs.values()))[0]['result'].get('model')}",
             ""]
    if mock:
        lines += ["> ⚠️ MOCK 运行：答案是随机生成的，下面的数字没有任何意义，只说明流程能跑通。", ""]
    names = {"matter_category": "问事类别", "wenfa_type": "问法类型", "motive": "动机", "asker_role": "谁的事",
             "single_matter": "一念一事", "intent_clear": "来意清楚", "involves_decision": "涉及决定"}
    header = "| 指标 | " + " | ".join(all_runs) + " |"
    lines += [header, "|---|" + "---|" * len(all_runs)]
    scores = {lang: score(rows) for lang, rows in all_runs.items()}
    def row(label, fn):
        lines.append(f"| {label} | " + " | ".join(fn(scores[l]) for l in all_runs) + " |")
    row("用神·明确例 命中", lambda s: pct(s["clear_hit"], s["clear_n"]))
    row("用神·明确例 误标歧义", lambda s: pct(s["clear_false_alarm"], s["clear_n"]))
    row("用神·歧义例 标出", lambda s: pct(s["amb_caught"], s["amb_n"]))
    row("其他题·歧义例 标出", lambda s: pct(s["other_amb_caught"], s["other_amb_n"]))
    for field, label in names.items():
        row(label, lambda s, f=field: pct(*reversed(s["fields"].get(f, [0, 0]))))
    row("用神答对时第一名平均概率", lambda s: mean(s["p_hit"]))
    row("用神答错时第一名平均概率", lambda s: mean(s["p_miss"]))
    for lang, rows in all_runs.items():
        lines += ["", f"## 逐条（{lang}）", "",
                  "| id | 来意 | 期望用神 | Jev 前两名 | 结果 |", "|---|---|---|---|---|"]
        for r in rows:
            exp = r["case"]["expect"]
            want = "／".join(exp["yongshen"]) if "yongshen" in exp else (
                "应标歧义" if exp.get("yongshen_ambiguous") else "—")
            ys = r["result"]["answers"].get("yongshen_main", {})
            top = "，".join(f"{k} {v:.2f}" for k, v in (ys.get("top3") or [])[:2])
            text = r["case"]["来意摘要"]
            text = text if len(text) <= 22 else text[:21] + "…"
            lines.append(f"| {r['case']['id']} | {text} | {want} | {top} | {r.get('yongshen_verdict', '—')} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Jev 来意预判 · 金标准例检验")
    ap.add_argument("--lang", choices=("zh", "en", "both"), default="zh")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--timeout", type=float, default=15.0)
    ap.add_argument("--out", help="报告写到这个文件（默认打到标准输出）")
    ap.add_argument("--raw", help="逐条原始结果写到这个 JSON 文件")
    args = ap.parse_args(argv)

    if not args.mock and not jev_judge.find_api_key():
        print("没有找到 Jev 密钥：先 export TYPESAFE_API_KEY=...（或用 --mock 只测流程）", file=sys.stderr)
        return 1
    bank, gold = jev_judge.load_bank(), load_gold()
    langs = ("zh", "en") if args.lang == "both" else (args.lang,)
    all_runs = {lang: run(gold, bank, lang, args.mock, args.timeout) for lang in langs}
    text = report(all_runs, gold, bank, args.mock)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"报告已写入 {args.out}")
    else:
        print(text)
    if args.raw:
        Path(args.raw).write_text(json.dumps(
            {lang: [{"id": r["case"]["id"], "result": r["result"]} for r in rows]
             for lang, rows in all_runs.items()}, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
