#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_consistency.py —— 跨 skill 一致性 / 源数据保真度校验

  用法:
    python3 check_consistency.py <canonical_facts.json> <skill_claims_*.json> [更多 skill_claims ...]
    # 或目录模式：自动扫描目录里所有 skill_claims_*.json
    python3 check_consistency.py <dir>

  状态与退出码（vedic 5.1 统一口径）:
    通过 0：实际比较了 ≥1 条事实且无矛盾、无待复核
    失败 1：有 fidelity 或 cross-skill 矛盾
    未完成 2：实际比较的事实数为 0（空提取 / 字段对不上），或有抽取待复核未清空
    参数错误 4
  每次都报告「实际比较了多少条事实」，空提取不会被当成通过。

检查两件事：
  1. 保真度 (fidelity)：每个 skill 断言的确定性事实，必须与 canonical_facts(源数据)一致。
     —— 抓"某 skill 自己把 10 宫主读错/把尊贵度说反"。
  2. 跨 skill 一致性 (cross-skill)：被 ≥2 个 skill 同时断言的同一事实，必须彼此相同。
     —— 抓"core 说 10 宫主是火星、career 说是土星"这类互相打架。

⚠️ 本检查【不评解读质量】，只查确定性事实是否自洽。解读层没有标准答案，不在此列。
⚠️ 这一步免疫 5b-0：比对是纯算术，不是判断。
"""
import sys, json, os, glob
from datetime import date

# 可比对的确定性字段
SCALAR = ["ak", "d9_lagna"]          # 单值
MAP = ["house_lords", "planet_sign", "planet_dignity"]  # 字典(键 → 值)


def load_claims(args):
    files = []
    if len(args) == 1 and os.path.isdir(args[0]):
        files = sorted(glob.glob(os.path.join(args[0], "skill_claims_*.json")))
    else:
        files = list(args)
    return [json.load(open(f, encoding="utf-8")) for f in files]


def dasha_equal(a, b, tol_days=31):
    try:
        return (a.get("lord") == b.get("lord")
                and abs((date.fromisoformat(a["start"]) - date.fromisoformat(b["start"])).days) <= tol_days
                and abs(a.get("years", -1) - b.get("years", -2)) < 0.01)
    except Exception:
        return False


def check_fidelity(canon, claims, counter=None):
    """返回 {skill: [错误描述,...]}；counter['fidelity'] 累计实际比较条数。"""
    out = {}
    counter = counter if counter is not None else {}
    counter.setdefault("fidelity", 0)
    for c in claims:
        sk = c.get("skill", "?")
        errs = []
        for f in SCALAR:
            if f in c and c[f] is not None and canon.get(f) is not None:
                counter["fidelity"] += 1
                if c[f] != canon[f]:
                    errs.append(f"{f}: 断言 {c[f]} ≠ 源数据 {canon[f]}")
        for f in MAP:
            for k, v in (c.get(f) or {}).items():
                cv = (canon.get(f) or {}).get(k)
                if cv is not None:
                    counter["fidelity"] += 1
                    if v != cv:
                        errs.append(f"{f}[{k}]: 断言 {v} ≠ 源数据 {cv}")
        # dasha 列表
        cmap = {e["lord"]: e for e in (canon.get("dasha") or [])}
        for e in (c.get("dasha") or []):
            ce = cmap.get(e.get("lord"))
            if ce:
                counter["fidelity"] += 1
            if ce and not dasha_equal(e, ce):
                errs.append(f"dasha[{e.get('lord')}]: 起止/周期与源数据不符")
        if errs:
            out[sk] = errs
    return out


def check_cross_skill(claims, counter=None):
    """被 ≥2 skill 同时断言的事实必须一致。返回 [矛盾描述,...]；counter['cross'] 累计比较的共同事实数。"""
    issues = []
    counter = counter if counter is not None else {}
    counter.setdefault("cross", 0)
    # 标量
    for f in SCALAR:
        votes = {}
        for c in claims:
            if f in c and c[f] is not None:
                votes.setdefault(c[f], []).append(c.get("skill", "?"))
        if sum(len(v) for v in votes.values()) >= 2:
            counter["cross"] += 1
        if len(votes) > 1:
            desc = "; ".join(f"{val}←{'/'.join(sks)}" for val, sks in votes.items())
            issues.append(f"{f} 出现分歧: {desc}")
    # 字典字段，逐键
    for f in MAP:
        keyvotes = {}  # key -> {value: [skills]}
        for c in claims:
            for k, v in (c.get(f) or {}).items():
                keyvotes.setdefault(k, {}).setdefault(v, []).append(c.get("skill", "?"))
        for k, votes in keyvotes.items():
            if sum(len(v) for v in votes.values()) >= 2:
                counter["cross"] += 1
            if len(votes) > 1:
                desc = "; ".join(f"{val}←{'/'.join(sks)}" for val, sks in votes.items())
                issues.append(f"{f}[{k}] 出现分歧: {desc}")
    return issues


def main():
    if len(sys.argv) < 2:
        print("用法: python3 check_consistency.py <canonical_facts.json> <skill_claims...> | <dir>")
        sys.exit(4)
    canon = json.load(open(sys.argv[1], encoding="utf-8"))
    claims = load_claims(sys.argv[2:])
    if not claims:
        print("未完成：未找到任何 skill_claims_*.json，比较事实数 = 0"); sys.exit(2)

    counter = {}
    fid = check_fidelity(canon, claims, counter)
    cross = check_cross_skill(claims, counter)
    # jev_extract_claims.py 抽出的 claims 会带 _extractor.pending（没把握、没写进去的字段）。
    # 这些字段可能正好藏着矛盾，所以没清空之前不能给 PASS。Claude 手抽的 claims 没有这个字段，行为不变。
    pending = {c.get("skill", "?"): (c.get("_extractor") or {}).get("pending") or [] for c in claims}
    pending = {k: v for k, v in pending.items() if v}

    print(f"\n{'='*64}\n跨 skill 一致性校验   chart = {canon.get('chart_id','?')}"
          f"   skills = {[c.get('skill') for c in claims]}\n{'='*64}")

    print("【保真度】各 skill 的确定性主张 vs 源数据(structured_data.md)")
    if not fid:
        print("  ✅ 全部 skill 忠于源数据")
    else:
        for sk, errs in fid.items():
            print(f"  ❌ {sk}:")
            for e in errs:
                print(f"       - {e}")

    print("\n【跨 skill 一致性】多个 skill 共同断言的事实是否彼此一致")
    if not cross:
        print("  ✅ 无分歧")
    else:
        for i in cross:
            print(f"  ❌ {i}")

    if pending:
        print("\n【抽取待复核】没把握、没写进 claims 的字段（可能藏着矛盾）")
        for sk, items in pending.items():
            print(f"  ⚠️ {sk}: {', '.join(items)}")

    print(f"{'-'*64}")
    print(f"  实际比较：对源数据 {counter['fidelity']} 条 · 跨模块共同事实 {counter['cross']} 条")
    nbad = sum(len(v) for v in fid.values()) + len(cross)
    npend = sum(len(v) for v in pending.values())
    if nbad == 0 and counter["fidelity"] == 0 and counter["cross"] == 0:
        print("  未完成：比较事实数为 0（提取结果为空或字段与源数据对不上），不能算通过")
        sys.exit(2)
    if nbad == 0 and not pending:
        print("  通过：确定性事实全部自洽")
        sys.exit(0)
    elif nbad == 0:
        print(f"  未完成：没发现矛盾，但有 {npend} 项抽取待复核（复核清空前不算通过）")
        sys.exit(2)
    else:
        extra = f"；另有 {npend} 项抽取待复核" if npend else ""
        print(f"  失败：{nbad} 处确定性矛盾（解读可以各有侧重，但事实不能打架）{extra}")
        sys.exit(1)


if __name__ == "__main__":
    main()
