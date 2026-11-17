#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""六爻复盘记录：模板、校验、导出（字段定义见 references/22_输出协议.md 第十节）

用法
  python scripts/record.py new > 2026-10-12-01.json      出一份空模板
  python scripts/record.py validate log.json             校验（文件可为单条记录或记录列表；装了 PyYAML 也可读 .yaml）
  python scripts/record.py show log.json                 每条导出一行
  python scripts/record.py show log.json --full          导出全表（Markdown）

校验只查结构和纪律（事前登记齐不齐、各镜是否分别记录、可观察结果与窗口是否事前写好、
事后判定是否越出窗口），不评判断对错。只依赖标准库。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

WENFA = ("能否成", "走向好坏", "该不该", "只问时间")
LEVELS = ("高", "中", "低")
VERDICTS = ("应验", "部分应验", "未应", "无法判定")
RULE_VERSION = "r6.1"

TEMPLATE = {
    "记录编号": "2026-10-12-01",
    "起卦时间": {"公历": "2026-10-12 14:30", "时区": "+08:00", "四值": "丙午年 戊戌月 己未日 辛未时",
              "干支来源": "脚本换算"},
    "起卦方式": "铜钱",
    "卦": "天火同人之风雷益",
    "问题": {"来意摘要": "", "问法类型": "能否成", "时限": ""},
    "输入版本": "v1",
    "主用神": {"主": "", "备选": []},
    "规则版本": RULE_VERSION,
    "门派": "默认",
    "各镜独立结论": {"主流镜": "", "张德镜": ""},
    "最终主判": "",
    "备选与触发条件": [],
    "关键反证": [],
    "应期候选": [{"时间": "", "依据": ""}],
    "置信度": {"等级": "中", "理由": ""},
    "可观察结果": {"应验": "", "未应": "", "时间窗口": {"起": "2026-10-12", "止": "2026-12-31"}},
    "修订记录": [],
    "事后结果": None,
}


def load(path: Path):
    text = path.read_text(encoding="utf-8")
    if path.suffix in (".yaml", ".yml"):
        try:
            import yaml  # noqa: PLC0415
        except ImportError as exc:
            raise SystemExit("读 .yaml 需要 PyYAML；或改用 .json") from exc
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    return data if isinstance(data, list) else [data]


def _blank(x) -> bool:
    return x is None or (isinstance(x, str) and not x.strip()) or (isinstance(x, (list, dict)) and not x)


def _date(s, where: str, problems: list[str]):
    try:
        return date.fromisoformat(str(s)[:10])
    except (TypeError, ValueError):
        problems.append(f"{where} 不是 YYYY-MM-DD 日期：{s!r}")
        return None


def validate_record(r: dict) -> list[str]:
    p: list[str] = []
    if not isinstance(r, dict):
        return ["记录不是对象"]
    rid = r.get("记录编号") or "?"
    def need(path: str, value):
        if _blank(value):
            p.append(f"[{rid}] 缺 {path}")
    need("记录编号", r.get("记录编号"))
    t = r.get("起卦时间") or {}
    if _blank(t.get("四值")) and _blank(t.get("公历")):
        p.append(f"[{rid}] 起卦时间至少要有 四值 或 公历")
    need("起卦方式", r.get("起卦方式"))
    need("卦", r.get("卦"))
    q = r.get("问题") or {}
    need("问题.来意摘要", q.get("来意摘要"))
    if q.get("问法类型") not in WENFA:
        p.append(f"[{rid}] 问题.问法类型 只能是 {'/'.join(WENFA)}：{q.get('问法类型')!r}")
    need("输入版本", r.get("输入版本"))
    need("主用神.主", (r.get("主用神") or {}).get("主"))
    need("规则版本", r.get("规则版本"))
    mirrors = r.get("各镜独立结论") or {}
    if not isinstance(mirrors, dict) or not mirrors:
        p.append(f"[{rid}] 各镜独立结论 要分别记录，不能只存综合主判")
    else:
        if (r.get("门派") or "默认") == "默认":
            for m in ("主流镜", "张德镜"):
                need(f"各镜独立结论.{m}", mirrors.get(m))
        for k, v in mirrors.items():
            need(f"各镜独立结论.{k}", v)
    need("最终主判", r.get("最终主判"))
    cands = r.get("应期候选") or []
    if len(cands) > 3:
        p.append(f"[{rid}] 应期候选最多三个（现 {len(cands)} 个）")
    for i, c in enumerate(cands, 1):
        if _blank((c or {}).get("时间")) or _blank((c or {}).get("依据")):
            p.append(f"[{rid}] 应期候选{i} 要有 时间 与 依据")
    conf = r.get("置信度") or {}
    if conf.get("等级") not in LEVELS:
        p.append(f"[{rid}] 置信度.等级 只能是 高/中/低：{conf.get('等级')!r}")
    need("置信度.理由", conf.get("理由"))
    obs = r.get("可观察结果") or {}
    win = obs.get("时间窗口") or {}
    has_obs = not _blank(obs.get("应验")) and not _blank(obs.get("未应"))
    if not has_obs:
        p.append(f"[{rid}] 可观察结果 要事前写清'应验'与'未应'各是什么（相近结果分开写）")
    start = _date(win.get("起"), f"[{rid}] 时间窗口.起", p) if win.get("起") else None
    end = _date(win.get("止"), f"[{rid}] 时间窗口.止", p) if win.get("止") else None
    if not (win.get("起") and win.get("止")):
        p.append(f"[{rid}] 可观察结果.时间窗口 要事前写好 起、止")
    elif start and end and start > end:
        p.append(f"[{rid}] 时间窗口 起 晚于 止")
    for i, rev in enumerate(r.get("修订记录") or [], 1):
        for k in ("时间", "改动", "原因", "受影响结论"):
            if _blank((rev or {}).get(k)):
                p.append(f"[{rid}] 修订记录{i} 缺 {k}")
    post = r.get("事后结果")
    if post:
        v = post.get("判定")
        if v not in VERDICTS:
            p.append(f"[{rid}] 事后结果.判定 只能是 {'/'.join(VERDICTS)}：{v!r}")
        if not has_obs and v not in (None, "无法判定"):
            p.append(f"[{rid}] 没有事前定义可观察结果，事后只能判'无法判定'")
        when = _date(post.get("日期"), f"[{rid}] 事后结果.日期", p) if post.get("日期") else None
        if v in ("应验", "部分应验") and when and start and end and not (start <= when <= end):
            p.append(f"[{rid}] 结果日期 {when} 在事前窗口 {start}～{end} 之外，不能判{v}（窗口不放宽）")
        each = post.get("各镜判定")
        if isinstance(mirrors, dict) and mirrors and isinstance(each, dict):
            miss = [m for m in mirrors if m not in each]
            if miss:
                p.append(f"[{rid}] 事后结果.各镜判定 缺 {'、'.join(miss)}")
        elif isinstance(mirrors, dict) and mirrors:
            p.append(f"[{rid}] 事后结果 要对各镜分别判定")
        if "事后解释" in post and not isinstance(post["事后解释"], (list, str, type(None))):
            p.append(f"[{rid}] 事后解释 单列为文字或列表")
    return p


def one_line(r: dict) -> str:
    q = r.get("问题") or {}
    cands = "；".join(f"{c.get('时间')}（{c.get('依据')}）" for c in r.get("应期候选") or [])
    win = (r.get("可观察结果") or {}).get("时间窗口") or {}
    post = r.get("事后结果") or {}
    t = r.get("起卦时间") or {}
    return "｜".join([str(r.get("记录编号")), str(t.get("公历") or t.get("四值")), str(r.get("卦")),
                     str(q.get("问法类型")), str(r.get("最终主判")), cands or "—",
                     str((r.get("置信度") or {}).get("等级")),
                     f"窗口 {win.get('起')}～{win.get('止')}", str(post.get("判定") or "未复盘")])


def full_table(r: dict) -> str:
    rows = []
    def row(k, v):
        if isinstance(v, (dict, list)):
            v = json.dumps(v, ensure_ascii=False)
        rows.append(f"| {k} | {v if v not in (None, '') else '—'} |")
    for k in TEMPLATE:
        row(k, r.get(k))
    return "| 字段 | 内容 |\n|---|---|\n" + "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="六爻复盘记录")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("new")
    v = sub.add_parser("validate"); v.add_argument("file")
    s = sub.add_parser("show"); s.add_argument("file"); s.add_argument("--full", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "new":
        print(json.dumps(TEMPLATE, ensure_ascii=False, indent=2))
        return 0
    try:
        recs = load(Path(a.file))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"读不了记录：{exc}", file=sys.stderr)
        return 2
    if a.cmd == "validate":
        probs = [x for r in recs for x in validate_record(r)]
        if probs:
            print("记录有问题：\n  " + "\n  ".join(probs))
            return 1
        print(f"{len(recs)} 条记录通过校验")
        return 0
    for r in recs:
        print(full_table(r) + "\n" if a.full else one_line(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
