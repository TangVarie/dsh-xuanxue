#!/usr/bin/env python3
"""merge_shadbala.py — 把 JHora PDF 的 Shadbala 逐行合并进 chart_data.json，再重新生成 structured_data.md。

规则（shared/data_contract.md「Shadbala 来源」）：
  - PDF 必须对应同一出生时刻：数据文件里的 "birth": "YYYY-MM-DD HH:MM" 与 chart_data.json 的出生日期/计算用时间不一致 → 拒绝
  - 只改 PDF 里出现的行；PDF 没有的行保持 calc 原值，不整表覆盖
  - 每行保留三样：calc 原计算值、采用值、来源
  - 校准改了出生时间后，旧 PDF 的 Shadbala 一律作废（chart_id 变了，本脚本会拒绝）

PDF 数据文件（JSON）格式：
  {"source": "JHora PDF p.3", "birth": "1990-05-21 14:23",
   "rows": {"Sun": {"total_rupas": 7.80, "ishta_phala": 24.1, "kashta_phala": 31.0},
            "Mars": {"total_rupas": 6.1, "strength_pct": 122.0}}}
  ishta_phala / kashta_phala 可选；给了就一并采用，没给保持 calc。
  strength_pct 缺省时按 BPHS 必需值换算（Sun 5 / Moon 6 / Mars 5 / Mercury 7 / Jupiter 6.5 / Venus 5.5 / Saturn 5）。

用法: python merge_shadbala.py --chart <目录>/chart_data.json --pdf-data shadbala_pdf.json
退出码: 0 合并完成 / 1 拒绝合并 / 2 参数错误
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chart_io as cio  # noqa: E402

REQUIRED = {"Sun": 5.0, "Moon": 6.0, "Mars": 5.0, "Mercury": 7.0, "Jupiter": 6.5, "Venus": 5.5, "Saturn": 5.0}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--chart", required=True)
    ap.add_argument("--pdf-data", required=True)
    a = ap.parse_args()
    doc = cio.load_doc(a.chart)
    pdf = json.load(open(a.pdf_data, encoding="utf-8"))
    inp = doc["input"]
    want = f"{inp['date']} {inp.get('time_used')}"
    if (pdf.get("birth") or "").strip() != want:
        print(f"拒绝合并：PDF 出生时刻「{pdf.get('birth')}」与当前盘「{want}」不一致（校准后旧 PDF 作废）")
        sys.exit(1)
    sb = doc["chart"].get("shadbala")
    if not isinstance(sb, dict) or "error" in sb:
        print("拒绝合并：当前盘没有 calc Shadbala 基准（计算失败），先修复计算环境")
        sys.exit(1)
    rows = pdf.get("rows") or {}
    bad = [p for p in rows if p not in REQUIRED]
    if bad:
        print(f"拒绝合并：非法行星名 {bad}（只收 {list(REQUIRED)}）")
        sys.exit(1)
    ov = doc.setdefault("overrides", {}).setdefault("shadbala", {})
    for planet, vals in rows.items():
        rupas = vals.get("total_rupas")
        if not isinstance(rupas, (int, float)) or rupas <= 0:
            print(f"拒绝合并：{planet}.total_rupas 非法（{rupas}）")
            sys.exit(1)
        pct = vals.get("strength_pct")
        if pct is None:
            pct = round(rupas / REQUIRED[planet] * 100, 2)
        calc = sb.get(planet, {})
        adopted = {"total_rupas": rupas, "strength_pct": pct}
        for k in ("ishta_phala", "kashta_phala"):
            if isinstance(vals.get(k), (int, float)):
                adopted[k] = vals[k]
        ov[planet] = {
            "calc": {k: calc.get(k) for k in ("total_rupas", "strength_pct", "ishta_phala", "kashta_phala")},
            "adopted": adopted,
            "source": pdf.get("source", "JHora PDF"),
        }
    cio.save_doc(doc, a.chart)
    from build_chart import render_md
    md_path = os.path.join(os.path.dirname(os.path.abspath(a.chart)), "structured_data.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(render_md(doc))
    kept = [p for p in REQUIRED if p not in rows]
    print(f"合并完成：PDF 行 {sorted(rows)}；保持 calc 的行 {kept}；已重新生成 {md_path}")


if __name__ == "__main__":
    main()
