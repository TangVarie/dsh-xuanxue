#!/usr/bin/env python3
"""archive_chart.py — 出生数据要变（用户更正时间/地点、校时写回）之前，把旧盘产物归档。

python archive_chart.py --dir <工作目录> --reason "用户更正出生时间 06:40→06:52" [--dry-run]

规则见 shared/versioning.md §3：旧盘产物全部保留、绑定旧 chart_id，不迁移成新盘的结果。
  复制：chart_data.json、structured_data.md（随后 build_chart.py 会在原位置写新盘）
  移动：分析记录、core_summary、各模块报告与分节文件、QA 文件、验证记录、读盘提取、旧版导入原文、HTML 报告、parts/
  不动：user_context.md（用户的现实背景不随盘变）、intake*.md、rectification_*（校时过程本身）、archive/、其他文件
合盘子目录（没有 chart_data.json、分析记录用 --chart 登记了双方盘）：把 analysis_record*.json、synastry_data.md、
  reports/ 移到 archive/<A的chart_id>_<B的chart_id>/；intake.md 与 B/ 不动（B 的出生数据要变时对 B/ 单独运行本脚本）
退出码: 0 已归档（或 --dry-run 列出）/ 2 没有可归档的盘或参数错误
"""
import argparse
import datetime as dt
import fnmatch
import json
import os
import re
import shutil
import sys

COPY = ["chart_data.json", "structured_data.md"]
MOVE_PATTERNS = [
    "analysis_record*.json", "core_summary.md", "verification_record.json", "verification_record.md",
    "calibration_quiz.md", "extracted_chart.md", "structured_data.legacy.md", "report*.html",
    "qa_*.md", "p[0-9]*_*.md", "appendix.md", "career_*.md", "love_*.md", "s[1-6]_*.md",
    "timing_*.md", "y[0-9]*_*.md", "t[0-9]*_*.md", "dc[0-9]*_*.md", "verification_dual.json",
]
MOVE_DIRS = ["parts", "alt_lagna"]
# 合盘子目录（没有自己的 chart_data.json）：归档合盘计算与报告，intake.md 与各方盘目录（如 B/）不动
MULTI_MOVE = ["analysis_record*.json", "synastry_data.md"]
MULTI_DIRS = ["reports"]
KEEP_PATTERNS = ["user_context.md", "intake*.md", "rectification_*"]


def archive_multi(a):
    recs = [x for x in sorted(os.listdir(a.dir)) if fnmatch.fnmatch(x, "analysis_record*.json")]
    ids = []
    for x in recs:
        try:
            with open(os.path.join(a.dir, x), encoding="utf-8") as f:
                ids = [c.get("chart_id") for c in json.load(f).get("charts") or []] or ids
        except (OSError, ValueError):
            pass
    if not ids:
        print("没有 chart_data.json，也没有登记各方盘的分析记录：没有可归档的盘（旧版产物先用 import_legacy_md.py 导入）")
        return 2
    dest = os.path.join(a.dir, "archive", "_".join(str(i) for i in ids))
    n = 2
    while os.path.exists(dest):
        dest = os.path.join(a.dir, "archive", "_".join(str(i) for i in ids) + f"-{n}")
        n += 1
    names = sorted(os.listdir(a.dir))
    to_move = [x for x in names if os.path.isfile(os.path.join(a.dir, x)) and any(fnmatch.fnmatch(x, p) for p in MULTI_MOVE)]
    to_move += [x for x in MULTI_DIRS if os.path.isdir(os.path.join(a.dir, x))]
    print(f"合盘记录（{' / '.join(map(str, ids))}）→ {os.path.relpath(dest, a.dir)}/")
    print("移动: " + (", ".join(to_move) or "无"))
    print("不动: " + (", ".join(x for x in names if x not in to_move and x != "archive") or "无"))
    if a.dry_run:
        print("（--dry-run：未改动任何文件）")
        return 0
    os.makedirs(dest)
    for x in to_move:
        shutil.move(os.path.join(a.dir, x), os.path.join(dest, x))
    with open(os.path.join(dest, "ARCHIVED.txt"), "w", encoding="utf-8") as f:
        f.write(f"归档时间: {dt.datetime.now().isoformat(timespec='seconds')}\n原因: {a.reason}\n登记的各方盘: {ids}\n")
    print("下一步：重新运行 build_synastry_data.py，再用 analysis_record.py init --chart … 建新记录。")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", required=True)
    ap.add_argument("--reason", default="出生数据变更")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    cpath = os.path.join(a.dir, "chart_data.json")
    if not os.path.exists(cpath):
        return archive_multi(a)
    with open(cpath, encoding="utf-8") as f:
        doc = json.load(f)
    cid = doc.get("chart_id") or "unknown"
    dest = os.path.join(a.dir, "archive", cid)
    n = 2
    while os.path.exists(dest):
        dest = os.path.join(a.dir, "archive", f"{cid}-{n}")
        n += 1

    names = sorted(os.listdir(a.dir))
    # 记录类文件绑定的 chart_id：已经先重排、chart_data.json 已是新盘时，按记录绑定的旧盘归档（补归档）
    bound = set()
    for x in names:
        fp = os.path.join(a.dir, x)
        if fnmatch.fnmatch(x, "analysis_record*.json") or x == "verification_record.json":
            try:
                with open(fp, encoding="utf-8") as f:
                    bound.add(json.load(f).get("chart_id"))
            except (OSError, ValueError):
                pass
        elif x in ("core_summary.md", "verification_record.md"):
            m = re.search(r"chart_id=([0-9a-f]{12})", open(fp, encoding="utf-8").read(4000))
            if m:
                bound.add(m.group(1))
    bound.discard(None)
    late = len(bound) == 1 and cid not in bound
    if late:
        cid = bound.pop()
        dest = os.path.join(a.dir, "archive", cid)
        n = 2
        while os.path.exists(dest):
            dest = os.path.join(a.dir, "archive", f"{cid}-{n}")
            n += 1
    elif len(bound) > 1:
        print(f"工作目录里的记录绑定了多张盘 {sorted(bound)}：先手动分开，再归档")
        return 2
    to_copy = [] if late else [x for x in COPY if x in names]
    to_move = [x for x in names if os.path.isfile(os.path.join(a.dir, x))
               and any(fnmatch.fnmatch(x, p) for p in MOVE_PATTERNS)]
    to_move += [x for x in MOVE_DIRS if os.path.isdir(os.path.join(a.dir, x))]
    kept = [x for x in names if x not in to_copy and x not in to_move and x != "archive"]

    print(f"旧盘 chart_id={cid} → {os.path.relpath(dest, a.dir)}/"
          + ("（补归档：chart_data.json 已是新盘，旧盘的计算文件不可得，只归档记录类文件）" if late else ""))
    print("复制: " + (", ".join(to_copy) or "无"))
    print("移动: " + (", ".join(to_move) or "无"))
    print("不动: " + (", ".join(kept) or "无"))
    if a.dry_run:
        print("（--dry-run：未改动任何文件）")
        return 0
    os.makedirs(dest)
    for x in to_copy:
        shutil.copy2(os.path.join(a.dir, x), os.path.join(dest, x))
    for x in to_move:
        shutil.move(os.path.join(a.dir, x), os.path.join(dest, x))
    with open(os.path.join(dest, "ARCHIVED.txt"), "w", encoding="utf-8") as f:
        if late:
            f.write(f"归档时间: {dt.datetime.now().isoformat(timespec='seconds')}\n原因: {a.reason}（补归档）\n"
                    f"chart_id: {cid}\n重排先于归档，旧盘的 chart_data.json / structured_data.md 已被新盘覆盖。\n"
                    "这些记录绑定上面的旧盘，不适用新盘，只作对照。\n")
        else:
            f.write(f"归档时间: {dt.datetime.now().isoformat(timespec='seconds')}\n原因: {a.reason}\n"
                    f"chart_id: {cid}\naudit_id: {doc.get('audit_id')}\n"
                    f"出生: {doc.get('input', {}).get('date')} {doc.get('input', {}).get('time_used')}\n"
                    "这些文件绑定上面的旧盘，不适用新盘，只作对照。\n")
    print("新盘从初始推导重新开始。" if late else
          "下一步：用 build_chart.py 按新的出生数据重排（--out 同一工作目录），新盘从初始推导重新开始。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
