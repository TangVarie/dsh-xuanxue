#!/usr/bin/env python3
"""Progressive reader for calculator-generated ``structured_data.md`` / ``chart_data.json``.

vedic 5.1: ``--check`` runs the full MD/AD/PD hierarchy check (counts, names, order,
parent-child ownership, boundaries) and exits 0 通过 / 1 失败 / 2 未完成.
When ``chart_data.json`` sits next to the Markdown file with the same chart_id, it is
preferred as the data source (full time precision).

The canonical file keeps all 9 MD, 81 AD, and 729 PD rows.  This helper keeps
the model-facing context small: ``--overview`` collapses the full PD tables,
while date queries return only the PD rows that overlap the requested window
plus a small amount of adjacent context.
"""

import argparse
import calendar
import json
import os
import re
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dasha_check as dc  # noqa: E402
import capability as cap  # noqa: E402


PD_HEADING_RE = re.compile(r"^### .*Pratyantardasha（三级运）\s*$")
PD_ROW_RE = re.compile(
    r"^\|\s*([A-Za-z]+-[A-Za-z]+-[A-Za-z]+)\s*\|\s*"
    r"(\d{4}-\d{2}-\d{2})\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|"
)


def parse_date(value):
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("date must use YYYY-MM-DD: %s" % value) from exc


def read_text(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def _md_chart_id(text):
    m = re.search(r"chart_id=([0-9a-f]{12})", text)
    return m.group(1) if m else None


def load_source(path):
    """返回 (tree, text_or_None, note, doc_or_None)。优先同目录、同 chart_id 的 chart_data.json。"""
    if path.endswith(".json"):
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        return (dc.tree_from_json(doc.get("chart", {})) or {"source": "chart_data.json", "mds": []}, None,
                "chart_data.json", doc)
    text = read_text(path)
    sib = os.path.join(os.path.dirname(os.path.abspath(path)), "chart_data.json")
    if os.path.exists(sib):
        with open(sib, encoding="utf-8") as f:
            doc = json.load(f)
        if doc.get("chart_id") and doc.get("chart_id") == _md_chart_id(text):
            tree = dc.tree_from_json(doc.get("chart", {}))
            if tree:
                return tree, text, "chart_data.json（与 structured_data.md 同一 chart_id）", doc
            return dc.tree_from_md(text), text, "structured_data.md", doc
        else:
            sys.stderr.write("⚠️ 同目录 chart_data.json 的 chart_id 与本文件不一致，改用 Markdown 表；"
                             "两份数据不是同一次计算，先用 check_chart.py 核对。\n")
    return dc.tree_from_md(text), text, "structured_data.md", None


def _birth_date(doc, text):
    """出生日期（查询早于出生日时提示用）；拿不到就返回 None。"""
    raw = None
    if doc and isinstance(doc.get("input"), dict):
        raw = doc["input"].get("date")
    if not raw and text:
        m = re.search(r"^出生日期:\s*(\d{4}-\d{2}-\d{2})", text, re.M)
        raw = m.group(1) if m else None
    try:
        return parse_date(raw) if raw else None
    except Exception:
        return None


def rows_from_tree(tree, text=None):
    rows = []
    if tree.get("source") == "structured_data.md":
        lines = {(r["path"], r["start"]): r["line"] for r in parse_pd_rows(text)} if text else {}
        for r in tree["pd_rows"]:
            path, st = f"{r['md']}-{r['ad']}-{r['planet']}", parse_date(r["start"])
            ln = lines.get((path, st))
            rows.append({"path": path, "start": st, "end": parse_date(r["end"]),
                         "line": f"structured_data.md 第 {ln} 行" if ln else None})
    else:
        for i, md in enumerate(tree["mds"]):
            for j, ad in enumerate(md["ads"]):
                for k, pd in enumerate(ad["pds"]):
                    rows.append({"path": f"{md['planet']}-{ad['planet']}-{pd['planet']}",
                                 "start": parse_date(str(pd["start"])[:10]),
                                 "end": parse_date(str(pd["end"])[:10]),
                                 "line": f"chart_data.json dashas[{i}].antardashas[{j}].pratyantardashas[{k}]"})
    rows.sort(key=lambda row: (row["start"], row["end"], row["path"]))
    return rows


def render_ad_window(tree, start, end, reason):
    """月级窗口不可用时，只给 MD/AD 层：与查询区间重叠的 AD 行（加前后各一行）。"""
    mds = tree["mds"] if tree.get("source") != "structured_data.md" else dc._md_tree(tree)[0]
    rows = []
    for md in mds:
        for ad in md["ads"]:
            rows.append((f"{md['planet']}-{ad['planet']}", str(ad["start"])[:10], str(ad["end"])[:10]))
    rows.sort(key=lambda r: r[1])
    s, e = start.isoformat(), end.isoformat()
    hits = [i for i, r in enumerate(rows) if r[1] < e and r[2] > s]
    out = ["# MD/AD 阶段窗口（月级窗口不可用）", "", f"> {reason}", f"> 查询区间：`[{s}, {e})`", "",
           "| 关系 | MD-AD | 起始 | 结束 |", "|------|-------|------|------|"]
    if not hits:
        out.append("| — | 查询区间不在 Dasha 表范围内 | | |")
        return "\n".join(out) + "\n"
    for i in range(max(0, hits[0] - 1), min(len(rows), hits[-1] + 2)):
        out.append(f"| {'命中' if i in hits else '相邻'} | {rows[i][0]} | {rows[i][1]} | {rows[i][2]} |")
    return "\n".join(out) + "\n"


def collapsed_overview(text):
    output = []
    skipping_pd = False
    for line in text.splitlines():
        if PD_HEADING_RE.match(line):
            skipping_pd = True
            output.append(line)
            output.append(
                "> 已折叠完整PD表；月/日级审计用 "
                "`dasha_query.py --month/--date/--start --end` 按需读取。"
            )
            continue
        if skipping_pd:
            if not line.strip():
                output.append("")
                skipping_pd = False
            continue
        output.append(line)
    return "\n".join(output) + "\n"


def parse_pd_rows(text):
    rows = []
    for line_no, line in enumerate(text.splitlines(), 1):
        match = PD_ROW_RE.match(line)
        if not match:
            continue
        rows.append(
            {
                "path": match.group(1),
                "start": parse_date(match.group(2)),
                "end": parse_date(match.group(3)),
                "line": line_no,
            }
        )
    rows.sort(key=lambda row: (row["start"], row["end"], row["path"]))
    return rows


def validate_pd_rows(rows):
    if len(rows) != 729:
        raise ValueError(
            "PD completeness failed: found %d rows, expected 729. "
            "Regenerate structured_data.md with vedic-calculator before "
            "making a month/day-level judgment." % len(rows)
        )
    invalid = [row for row in rows if row["end"] <= row["start"]]
    if invalid:
        raise ValueError("PD interval is not positive at source line %d" % invalid[0]["line"])
    for previous, current in zip(rows, rows[1:]):
        if previous["end"] != current["start"]:
            raise ValueError(
                "PD continuity failed between source lines %d and %d: %s != %s"
                % (
                    previous["line"],
                    current["line"],
                    previous["end"].isoformat(),
                    current["start"].isoformat(),
                )
            )


def month_window(value):
    try:
        year, month = [int(part) for part in value.split("-")]
        start = date(year, month, 1)
    except (TypeError, ValueError) as exc:
        raise ValueError("month must use YYYY-MM: %s" % value) from exc
    last_day = calendar.monthrange(year, month)[1]
    return start, date(year, month, last_day) + timedelta(days=1)


def query_window(args):
    modes = sum(
        [
            bool(args.month),
            bool(args.date),
            bool(args.start or args.end),
        ]
    )
    if modes != 1:
        raise ValueError(
            "choose exactly one query: --month, --date, or the --start/--end pair"
        )
    if args.month:
        return month_window(args.month)
    if args.date:
        start = parse_date(args.date)
        return start, start + timedelta(days=1)
    if not args.start or not args.end:
        raise ValueError("--start and --end must be supplied together")
    start = parse_date(args.start)
    end = parse_date(args.end)
    if end <= start:
        raise ValueError("--end must be later than --start; intervals use [start,end)")
    return start, end


def render_query(rows, start, end, context):
    hits = [index for index, row in enumerate(rows) if row["start"] < end and row["end"] > start]
    if not hits:
        raise ValueError(
            "query window %s to %s is outside the available PD timeline"
            % (start.isoformat(), end.isoformat())
        )
    first = max(0, hits[0] - context)
    last = min(len(rows), hits[-1] + context + 1)
    hit_set = set(hits)
    output = [
        "# 局部三级运窗口",
        "",
        "> 查询区间：`[%s, %s)`" % (start.isoformat(), end.isoformat()),
        "> 完整性：MD/AD/PD 三层层级检查已通过（数量、名称、父子归属、边界）。",
        "",
        "| 关系 | MD-AD-PD | 起始 | 结束 | 源行 |",
        "|------|----------|------|------|------|",
    ]
    for index in range(first, last):
        row = rows[index]
        relation = "命中窗口" if index in hit_set else "相邻上下文"
        output.append(
            "| %s | %s | %s | %s | %s |"
            % (
                relation,
                row["path"],
                row["start"].isoformat(),
                row["end"].isoformat(),
                row["line"] or "未定位",
            )
        )
    return "\n".join(output) + "\n"


def build_parser():
    parser = argparse.ArgumentParser(
        description="Read structured_data progressively without loading all 729 PD rows into model context"
    )
    parser.add_argument("--file", required=True, help="path to structured_data.md or chart_data.json")
    parser.add_argument("--check", action="store_true", help="full MD/AD/PD hierarchy check; exit 0 通过 / 1 失败 / 2 未完成")
    parser.add_argument("--overview", action="store_true", help="print all non-PD content and collapse PD tables")
    parser.add_argument("--month", help="query a calendar month, YYYY-MM")
    parser.add_argument("--date", help="query one date, YYYY-MM-DD")
    parser.add_argument("--start", help="query start date, inclusive, YYYY-MM-DD")
    parser.add_argument("--end", help="query end date, exclusive, YYYY-MM-DD")
    parser.add_argument("--context", type=int, default=1, help="adjacent PD rows to include on each side (default: 1)")
    parser.add_argument("--candidate", action="store_true",
                        help="出生时间误差使月级窗口「不启用」时仍列出 PD 表，只作候选，不得写成月级结论")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    if args.context < 0:
        parser.error("--context must be non-negative")
    try:
        tree, text, note, doc = load_source(args.file)
        legacy = bool(doc) and doc.get("provenance", {}).get("source") == "legacy_md_import"
        tol = 1 if legacy else 0
        if args.check:
            if args.overview or args.month or args.date or args.start or args.end:
                raise ValueError("--check cannot be combined with overview or a date query")
            res = dc.check_tree(tree, tol_days=tol)
            sys.stdout.write(dc.format_result(res) + "\n")
            sys.exit(dc.exit_code(res["overall"]))
        if args.overview:
            if args.month or args.date or args.start or args.end:
                raise ValueError("--overview cannot be combined with a PD date query")
            if text is None:
                raise ValueError("--overview 需要 structured_data.md")
            sys.stdout.write(collapsed_overview(text))
            return
        start, end = query_window(args)
        res = dc.check_tree(tree, tol_days=tol)
        if res["capabilities"]["月级窗口（PD）"] != dc.PASS:
            sys.stdout.write(dc.format_result(res) + "\n")
            sys.stdout.write("月级窗口不可用：PD 层级检查未通过，只能给到能通过检查的上一层（AD 阶段或 MD 背景）。\n\n")
            if res["capabilities"]["阶段窗口（MD×AD）"] == dc.PASS:
                sys.stdout.write(render_ad_window(tree, start, end, "PD 缺失或未通过检查：下面只到 AD 阶段窗口"))
            sys.exit(dc.exit_code(res["capabilities"]["月级窗口（PD）"]))
        banner = ""
        if doc and isinstance(doc.get("chart"), dict):
            eff = doc.get("input", {}).get("effective_minutes")
            levels = {k: res[k]["status"] for k in ("md", "ad", "pd")}
            pd_row = next((r for r in cap.table(doc["chart"], eff if isinstance(eff, int) else None,
                                                dasha_levels=levels, legacy=legacy)
                           if r[0].startswith("Vimsottari 月级")), None)
            if pd_row and pd_row[1] == "不启用" and not args.candidate:
                sys.stdout.write(f"月级窗口不启用：{pd_row[2]}。\n只给 AD 阶段窗口（shared/time_window.md §1）；"
                                 "需要看 PD 候选表时加 --candidate，结论只能写候选。\n\n")
                sys.stdout.write(render_ad_window(tree, start, end, f"出生时间误差：{pd_row[2]}"))
                sys.exit(2)
            if pd_row and pd_row[1] != "可用":
                banner = f"> ⚠️ 月级窗口{pd_row[1]}：{pd_row[2]}\n"
            if legacy:
                banner += "> ⚠️ 旧版导入数据：日期有 ±1 天出入，交界日前后 1 天内不下结论\n"
        birth = _birth_date(doc, text)
        if birth and start < birth:
            banner += (f"> ⚠️ 查询区间{'在' if end <= birth else '有一部分在'}出生日 {birth} 之前："
                       "Vimsottari 表从出生时所在大运的起点列起，出生日之前的行不是当事人经历过的运期，先核对事件年份\n")
        rows = rows_from_tree(tree, text)
        sys.stdout.write("> 数据源：%s\n" % note)
        sys.stdout.write(banner + "\n")
        sys.stdout.write(render_query(rows, start, end, args.context))
    except (ValueError, OSError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
