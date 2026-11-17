#!/usr/bin/env python3
"""validate_synastry_data.py — 合盘跨盘计算前的自检（vedic 5.1）

校验两份排盘数据（chart_data.json 优先，或 structured_data.md）：
  - 所有参与计算的字段：星座名必须是规范全名或两字母缩写，宫位 1-12，度数 [0,30)，宿名合法
  - 盘内一致性：行星齐全、Ra-Ke 对宫、宫位与星座/上升一致
  - 一方只有出生日期（build_chart.py --date-only）时：不要求上升/宫位/Moon 宿，列出被限制的层

用法: python validate_synastry_data.py <A数据> <B数据>
状态: 通过 / 失败 / 未完成；退出码 0 通过 / 1 失败 / 2 无失败但有未完成（降级运行）/ 3 参数错误
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_synastry_data import Chart, PLANETS, house_from  # noqa: E402

PASS, FAIL, INC = "通过", "失败", "未完成"


def check_one(c):
    """返回 [(状态, 说明)]。"""
    out = [(FAIL, e) for e in c.errors]
    present = [p for p in PLANETS if p in c.planets]
    if c.date_only:
        out.append((PASS if len(present) == 9 else INC,
                    f"行星（全天稳定才使用）{len(present)}/9" + ("" if len(present) == 9 else "；不稳定的行星不参与接触计算")))
        out.append((INC, "无出生时间：上升、宫位叠盘、UL、DK、Dasha 时机层不适用"))
    else:
        out.append((PASS if len(present) == 9 else FAIL, f"行星完整性 {len(present)}/9"))
        out.append((PASS if c.lagna_idx is not None else FAIL, f"Lagna（{c.lagna_sign}）"))
        bad_house = [p for p in present
                     if c.planets[p]['house'] != house_from(c.planets[p]['sidx'], c.lagna_idx)]
        if c.lagna_idx is not None:
            out.append((FAIL if bad_house else PASS,
                        "宫位与星座/上升一致" + (f"：不一致 {bad_house}" if bad_house else "")))
    ra, ke = c.planets.get('Rahu'), c.planets.get('Ketu')
    if ra and ke:
        diff = (ra['sidx'] - ke['sidx']) % 12
        out.append((PASS if diff == 6 else FAIL, f"Ra-Ke 对宫（相差 {diff} 星座）"))
    if c.moon_nak:
        out.append((PASS, f"Moon Nakshatra {c.moon_nak} pada{c.moon_pada}"))
    else:
        out.append((INC if c.date_only else FAIL, "Moon Nakshatra 缺失" + ("（当日不稳定，月宿层只做按星座的项）" if c.date_only else "")))
    if not c.date_only:
        if not c.ul:
            out.append((INC, "UL 缺失 → UL/D9 承载层降级"))
        if not c.dk:
            out.append((INC, "DK 缺失 → 配偶指示层降级"))
        if not c.dasha_md:
            out.append((INC, "当前 Dasha 缺失 → 时机层降级"))
    return out


def main():
    if len(sys.argv) < 3:
        print("用法: python validate_synastry_data.py <A数据> <B数据>")
        sys.exit(3)
    worst = PASS
    for label, path in (('A', sys.argv[1]), ('B', sys.argv[2])):
        print(f"=== {label}: {path} ===")
        if not os.path.exists(path):
            print(f"  {FAIL} 文件不存在")
            worst = FAIL
            continue
        c = Chart(path, label)
        print(f"  数据源: {c.source}{'（仅日期）' if c.date_only else ''}")
        for st, msg in check_one(c):
            print(f"  {st}  {msg}")
            if st == FAIL:
                worst = FAIL
            elif st == INC and worst == PASS:
                worst = INC
    print("\n结果:", {PASS: "通过，可运行 build_synastry_data.py",
                      INC: "未完成项只限制对应层，可运行 build_synastry_data.py（降级）",
                      FAIL: "失败：先修复上面的字段再合盘"}[worst])
    sys.exit({PASS: 0, FAIL: 1, INC: 2}[worst])


if __name__ == '__main__':
    main()
