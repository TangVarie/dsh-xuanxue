#!/usr/bin/env python3
"""score_probes.py — 验前事（盘面初验）评分，口径见 shared/validation_scoring.md。

验证记录 verification_record.json:
{
  "schema": "vedic-verification/1.0",
  "chart_id": "<排盘的 chart_id>",          # 绑定盘版本；校时后新盘另建记录
  "round": "R1",
  "probes": [
    {"id": "P1", "statement": "...", "window": "2019-07~2020-06",
     "flags": {"tautology": false, "known_fact": false, "used_in_rectification": false},
     "feedback": "hit"}                       # hit 准 / partial 部分准 / miss 不准 / unknown 不知道·记不清 / pending 未答
  ]
}

计分：准=1，部分准=0.5，不准=0。
不计入独立验证：恒真陈述（tautology）、已知事实核对（known_fact）、校时用过的证据（used_in_rectification）。
「不知道/记不清」单列待核，不算准也不删掉；「未答」视为反馈未完成。
等级：有效已答题 <3、仍有未答、或待核题超过有效题的 1/3 → 暂不定级；≥80% 高；≥60% 中；<60% 低；已答 <5 标「小样本」。
等级只描述这组探针的反馈匹配，不是预测准确率。

用法:
  python score_probes.py <verification_record.json> [--chart chart_data.json] [--json]
退出码: 0 已定级 / 2 暂不定级 / 1 记录非法或与当前盘不匹配
"""
import argparse
import json
import sys

POINTS = {"hit": 1.0, "partial": 0.5, "miss": 0.0}
VALID_FEEDBACK = set(POINTS) | {"unknown", "pending"}
MIN_ANSWERED = 3
SMALL_SAMPLE = 5


def score(record):
    probes = record.get("probes") or []
    errors = []
    excluded, valid = [], []
    for p in probes:
        fb = p.get("feedback")
        if fb not in VALID_FEEDBACK:
            errors.append(f"{p.get('id', '?')}.feedback 非法「{fb}」（只收 {sorted(VALID_FEEDBACK)}）")
            continue
        fl = p.get("flags") or {}
        why = [lab for k, lab in (("tautology", "恒真"), ("known_fact", "已知事实核对"),
                                ("used_in_rectification", "校时已用")) if fl.get(k)]
        (excluded if why else valid).append((p, why))
    answered = [p for p, _ in valid if p["feedback"] in POINTS]
    unknown = [p for p, _ in valid if p["feedback"] == "unknown"]
    pending = [p for p, _ in valid if p["feedback"] == "pending"]
    pts = sum(POINTS[p["feedback"]] for p in answered)
    ratio = (pts / len(answered)) if answered else None
    if errors:
        level, reason = "无效", "记录有非法反馈，修正后再评分"
    elif pending:
        level, reason = "暂不定级", f"仍有 {len(pending)} 题未答（反馈未完成）"
    elif len(unknown) * 3 > len(valid):
        level, reason = "暂不定级", (f"待核（不知道/记不清）{len(unknown)} 题，超过有效题 {len(valid)} 的 1/3："
                                    "先补答或换题，避免只按答得上的题定级")
    elif len(answered) < MIN_ANSWERED:
        level, reason = "暂不定级", f"有效已答题 {len(answered)} 题，少于 {MIN_ANSWERED} 题"
    elif ratio >= 0.8:
        level, reason = "高", ""
    elif ratio >= 0.6:
        level, reason = "中", ""
    else:
        level, reason = "低", ""
    return {
        "chart_id": record.get("chart_id"),
        "total_probes": len(probes),
        "excluded": [{"id": p.get("id"), "why": why} for p, why in excluded],
        "valid": len(valid),
        "answered": len(answered),
        "unknown_pending_review": [p.get("id") for p in unknown],
        "not_answered": [p.get("id") for p in pending],
        "points": pts,
        "match_rate": None if ratio is None else round(ratio, 4),
        "answered_share": round(len(answered) / len(valid), 4) if valid else None,
        "level": level,
        "level_reason": reason,
        "small_sample": bool(answered) and len(answered) < SMALL_SAMPLE,
        "errors": errors,
        "note": "反馈等级只描述这组探针与用户反馈的匹配，不是预测准确率；不单独决定出生时间精度。",
    }


def render(r):
    rate = "—" if r["match_rate"] is None else f"{r['points']:g}/{r['answered']} = {r['match_rate']*100:.1f}%"
    out = [f"盘版本 chart_id: {r['chart_id']}",
           f"探针 {r['total_probes']} 题 · 不计入独立验证 {len(r['excluded'])} 题 · 有效 {r['valid']} 题 · 已答 {r['answered']} 题",
           f"待核（不知道/记不清）: {', '.join(r['unknown_pending_review']) or '无'} · 未答: {', '.join(r['not_answered']) or '无'}",
           f"匹配率: {rate}" + ("（小样本）" if r["small_sample"] else "")
           + (f" · 有效题中已答占 {r['answered_share']*100:.0f}%" if r.get("answered_share") is not None else ""),
           f"反馈等级: {r['level']}" + (f"（{r['level_reason']}）" if r["level_reason"] else "")]
    for e in r["excluded"]:
        out.append(f"  不计入：{e['id']}（{'、'.join(e['why'])}）")
    for e in r["errors"]:
        out.append(f"  错误：{e}")
    out.append(r["note"])
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("record")
    ap.add_argument("--chart", help="当前 chart_data.json，用于核对记录绑定的盘版本")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    rec = json.load(open(a.record, encoding="utf-8"))
    if rec.get("schema") != "vedic-verification/1.0":
        print("记录非法：schema 应为 vedic-verification/1.0")
        sys.exit(1)
    r = score(rec)
    if a.chart:
        cur = json.load(open(a.chart, encoding="utf-8")).get("chart_id")
        if cur != rec.get("chart_id"):
            r["errors"].append(f"记录绑定 chart_id={rec.get('chart_id')}，当前盘 {cur}：这份验证属于另一张盘（旧盘或候选盘），"
                               "不能当作当前盘的验证")
            r["level"], r["level_reason"] = "无效", "记录与当前盘不匹配"
    print(json.dumps(r, ensure_ascii=False, indent=1) if a.json else render(r))
    if r["errors"]:
        sys.exit(1)
    sys.exit(2 if r["level"] == "暂不定级" else 0)


if __name__ == "__main__":
    main()
