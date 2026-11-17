#!/usr/bin/env python3
"""vedic 5.3 可复现回归测试。

用法:
  python tests/run_tests.py [--python <装了 pysweph+PyJHora 的解释器>] [--work <工作目录>] [--report tests/RESULTS.md]

- 出生数据全部是虚构测试盘；过运快照固定在 2026-10-11（--transit-date），结果不随运行日期变化。
- 计算环境不可用时，依赖排盘的用例记为「未完成」，不记为通过。
- 01–14 与 X 系列只证明脚本按规则执行、错误输入会被拦住；不证明数值的外部准确性。
  B1 调用 tests/bench_positions.py，用独立星历（astropy，需 pip install astropy）对照位置与 Vimsottari 日期；
  其余数值（Shadbala、SAV、分盘、Chara）需要 JHora 导出逐项比对，不能用内部自洽代替。
- P 系列（5.3）跑 prashna 模块自带的两份测试：上游的隔离断言与算例、Tajika 过程层的出版几何与独立复算。
  X19、X20 验证给引擎加的秒级参数不改变本命盘，提问盘目录不干扰本命检查。
退出码: 0 全部通过 / 1 有失败 / 2 无失败但有未完成
"""
import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CALC = os.path.join(SKILL, "calculator", "scripts")
SHARED = os.path.join(SKILL, "shared", "scripts")
SNAP = "2026-10-11"
PASS, FAIL, INC = "通过", "失败", "未完成"

A = dict(date="1990-05-21", time="14:23", tz="Asia/Shanghai", lat="39.9042", lon="116.4074",
         place="北京（虚构测试盘）", source="出生证", gender="女")
B = dict(date="1992-11-03", time="08:10", tz="Asia/Shanghai", lat="31.2304", lon="121.4737",
         place="上海（虚构测试盘）", source="家人记忆", gender="男")


# ---------------------------------------------------------------- 基础设施
class Ctx:
    def __init__(self, py, work):
        self.py, self.work = py, work
        self.calc_ok = None
        self.log = []

    def run(self, args, py=None, timeout=900):
        cmd = [py or self.py] + [str(x) for x in args]
        t0 = time.time()
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                               env=dict(os.environ, PYTHONIOENCODING="utf-8"))
            out, code = (p.stdout or "") + (p.stderr or ""), p.returncode
        except subprocess.TimeoutExpired:
            out, code = "超时", -9
        shown = " ".join(os.path.relpath(c, SKILL) if c.startswith(SKILL) else
                         (c.replace(self.work, "$WORK") if isinstance(c, str) else c) for c in cmd[1:])
        self.log.append((shown, code, round(time.time() - t0, 1)))
        return code, out

    def std(self, args):
        """只用标准库的脚本：用当前解释器运行。"""
        return self.run(args, py=sys.executable)

    def path(self, *p):
        return os.path.join(self.work, *p)


class Case:
    def __init__(self, cid, title, expected):
        self.cid, self.title, self.expected = cid, title, expected
        self.checks = []          # (说明, 是否成立)
        self.status, self.note = None, ""
        self.cmds = []

    def check(self, desc, cond):
        self.checks.append((desc, bool(cond)))
        return bool(cond)

    def incomplete(self, why):
        self.status, self.note = INC, why

    def finish(self):
        if self.status is None:
            self.status = PASS if self.checks and all(ok for _, ok in self.checks) else FAIL
        return self


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def dump(obj, p):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def write(p, s):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(s)


def line_of(out, key):
    for ln in out.splitlines():
        if key in ln:
            return ln
    return ""


def build(ctx, out_dir, person, extra=()):
    args = [os.path.join(CALC, "build_chart.py"), "--date", person["date"], "--tz", person["tz"],
            "--lat", person["lat"], "--lon", person["lon"], "--out", out_dir, "--transit-date", SNAP]
    if person.get("time"):
        args += ["--time", person["time"]]
    for k in ("place", "source", "gender"):
        if person.get(k):
            args += ["--" + k, person[k]]
    return ctx.run(args + list(extra))


def need_calc(ctx, case):
    if not ctx.calc_ok:
        case.incomplete("计算环境不可用（pysweph / PyJHora / 星历文件），依赖排盘的用例未执行")
        return False
    return True


# ---------------------------------------------------------------- 用例
def t01_two_full(ctx):
    c = Case("01", "两组完整出生信息", "排盘、读取、合盘和时间扫描正常完成")
    if not need_calc(ctx, c):
        return c
    for tag in ("A", "B"):
        c.check(f"{tag} 排盘退出码 0", ctx.results[f"build_{tag}"][0] == 0)
        code, out = ctx.run([os.path.join(CALC, "check_chart.py"), "--dir", ctx.path(tag)])
        c.check(f"{tag} check_chart 总体通过", code == 0 and "总体: 通过" in out)
    code, out = ctx.run([os.path.join(CALC, "dasha_query.py"), "--file", ctx.path("A", "chart_data.json"), "--check"])
    c.check("dasha_query --check MD/AD/PD 通过", code == 0)
    code, out = ctx.run([os.path.join(CALC, "dasha_query.py"), "--file", ctx.path("A", "structured_data.md"),
                         "--month", "2026-10"])
    c.check("dasha_query --month 2026-10 读到 PD", code == 0 and "2026-" in out)
    code, out = ctx.run([os.path.join(CALC, "dasha_query.py"), "--file", ctx.path("A", "structured_data.md"), "--overview"])
    c.check("dasha_query --overview 折叠 PD", code == 0 and "Antardasha" in out)
    code, out = ctx.run([os.path.join(CALC, "transit.py"), "--chart", ctx.path("A", "chart_data.json"), "--date", SNAP])
    c.check("transit.py 快照可算", code == 0 and "Sade Sati" in out)
    md = read(ctx.path("A", "structured_data.md"))
    c.check("Chara Dasha 时间线在表内", "### Chara Dasha 时间线" in md)
    # 时间扫描（rectifier/time_scan.py）：原时刻(+0)的事件 PD 必须与排盘数据一致
    code, scan = ctx.run([os.path.join(SKILL, "rectifier", "scripts", "time_scan.py"), "--date", A["date"],
                          "--time", A["time"], "--tz", A["tz"], "--lat", A["lat"], "--lon", A["lon"],
                          "--range", "5", "--event-date", "2015-09-01=测试事件", "--pd"])
    c.check("time_scan 逐分钟扫描完成", code == 0 and "| +0min |" in scan)
    code, q = ctx.run([os.path.join(CALC, "dasha_query.py"), "--file", ctx.path("A", "chart_data.json"), "--date", "2015-09-01"])
    hit = re.search(r"命中窗口 \| (\w+)-(\w+)-(\w+) \|", q)
    row = re.search(r"\| -5~\+5 \| [^|]+ \| [^|]+ \| ([^|]+) \|", scan)
    at0 = None
    if row:
        cell = row.group(1).strip()
        segs = re.findall(r"(\w+/\w+/\w+)（([+-]\d+)~([+-]\d+)）", cell)
        at0 = next((s for s, lo, hi in segs if int(lo) <= 0 <= int(hi)), None) if segs else cell.split()[0]
    c.check("time_scan 原时刻的 2015-09-01 PD = 排盘数据的 PD",
            bool(hit) and at0 == "/".join(hit.groups()))
    syn = ctx.path("syn_AB")
    code, out = ctx.std([os.path.join(SKILL, "synastry", "scripts", "build_synastry_data.py"),
                         ctx.path("A", "chart_data.json"), ctx.path("B", "chart_data.json"), syn, "--today", SNAP])
    c.check("合盘数据生成退出码 0", code == 0 and os.path.exists(os.path.join(syn, "synastry_data.md")))
    code, out = ctx.std([os.path.join(SKILL, "synastry", "scripts", "validate_synastry_data.py"),
                         ctx.path("A", "chart_data.json"), ctx.path("B", "chart_data.json")])
    c.check("合盘自检通过（退出码 0）", code == 0)
    return c


def t02_precision15(ctx):
    c = Case("02", "声明 ±15 分钟", "元信息与实际审计范围一致；篡改后被检出")
    if not need_calc(ctx, c):
        return c
    d = ctx.path("A15")
    code, _ = build(ctx, d, dict(A, source="本人记忆"), ["--declared-min", "15", "--declared-text", "大概±15分钟"])
    c.check("排盘退出码 0", code == 0)
    doc = load(os.path.join(d, "chart_data.json"))
    inp = doc["input"]
    c.check("JSON 有效误差 15 = 审计范围 15", inp.get("effective_minutes") == 15 and inp.get("audit_minutes") == 15)
    md = read(os.path.join(d, "structured_data.md"))
    c.check("md 实际审计范围 ±15", "实际审计范围: ±15 分钟" in md)
    c.check("md 分盘声明审计范围 ±15", "边界审计范围: 报时前后±15分钟" in md)
    code, out = ctx.run([os.path.join(CALC, "check_chart.py"), "--dir", d])
    c.check("check_chart 精度项通过", "通过" in line_of(out, "精度声明与审计范围"))
    # 能力范围：±15 分钟 → Dasha 日期可平移数十天，月级窗口不启用（shared/time_window.md §1）
    c.check("check_chart 能力范围：PD 月级窗口不启用并给出平移天数",
            "不启用" in line_of(out, "月级窗口（PD）") and "可平移约" in line_of(out, "月级窗口（PD）"))
    code, q = ctx.run([os.path.join(CALC, "dasha_query.py"), "--file", os.path.join(d, "chart_data.json"), "--month", "2026-10"])
    c.check("dasha_query --month 不给 PD、只给 MD/AD 阶段窗口（退出码 2）",
            code == 2 and "月级窗口不启用" in q and "MD/AD 阶段窗口" in q and "| 命中 |" in q)
    code, q = ctx.run([os.path.join(CALC, "dasha_query.py"), "--file", os.path.join(d, "chart_data.json"), "--month", "2026-10",
                       "--candidate"])
    c.check("--candidate 列出候选表并标警示", code == 0 and "⚠️ 月级窗口不启用" in q)
    code, out1 = ctx.run([os.path.join(CALC, "check_chart.py"), "--dir", ctx.path("A")])
    c.check("对照：出生证 ±1 分钟的盘 PD 月级窗口可用",
            line_of(out1, "月级窗口（PD）").split("—")[0].strip().endswith("可用"))
    # 来源下限：本人记忆声明 ±3 → 仍按 ±15
    d3 = ctx.path("A3")
    build(ctx, d3, dict(A, source="本人记忆"), ["--declared-min", "3", "--no-transit"])
    c.check("本人记忆声明 ±3 → 有效 ±15（来源下限）", load(os.path.join(d3, "chart_data.json"))["input"]["effective_minutes"] == 15)
    # 篡改审计范围
    bad = ctx.path("A15_tamper")
    shutil.copytree(d, bad)
    write(os.path.join(bad, "structured_data.md"), md.replace("实际审计范围: ±15 分钟", "实际审计范围: ±5 分钟"))
    code, out = ctx.run([os.path.join(CALC, "check_chart.py"), "--dir", bad])
    c.check("篡改审计范围 → 失败（退出码 1）", code == 1 and "失败" in line_of(out, "精度声明与审计范围"))
    # 缺省「±分钟级」
    bad2 = ctx.path("A15_default")
    shutil.copytree(d, bad2)
    write(os.path.join(bad2, "structured_data.md"),
          re.sub(r"有效精度: .*", "有效精度: ±分钟级", md, count=1))
    code, out = ctx.run([os.path.join(CALC, "check_chart.py"), "--dir", bad2])
    c.check("缺省写「±分钟级」→ 失败", code == 1)
    return c


def t03_karaka(ctx):
    c = Case("03", "下游需要完整 7K/8K 对照", "可以直接读取，无需自行补算；不合规的排序被拦住")
    if not need_calc(ctx, c):
        return c
    doc = load(ctx.path("A", "chart_data.json"))
    k = doc["chart"]["karakas"]
    c.check("JSON 7K 七项、不含 Rahu/Ketu", len(k["7k"]) == 7 and not {r[1] for r in k["7k"]} & {"Rahu", "Ketu"})
    c.check("JSON 8K 八项、含 Rahu", len(k["8k"]) == 8 and "Rahu" in {r[1] for r in k["8k"]})
    md = read(ctx.path("A", "structured_data.md"))
    sec = md.split("### Chara Karakas 7K/8K 对照", 1)[1].split("###", 1)[0] if "### Chara Karakas 7K/8K 对照" in md else ""
    c.check("md 有 7K/8K 对照表（8 行）", len(re.findall(r"^\| [1-8] \|", sec, re.M)) == 8)
    bad = ctx.path("A_k8")
    shutil.copytree(ctx.path("A"), bad)
    d2 = load(os.path.join(bad, "chart_data.json"))
    d2["chart"]["karakas"]["8k"] = [r for r in d2["chart"]["karakas"]["8k"] if r[1] != "Rahu"]
    dump(d2, os.path.join(bad, "chart_data.json"))
    code, out = ctx.run([os.path.join(CALC, "check_chart.py"), "--dir", bad])
    c.check("8K 缺 Rahu → 失败", code == 1 and "失败" in line_of(out, "Karaka 7K/8K"))
    return c


def t04_pd_only(ctx):
    c = Case("04", "只保留 PD，删除 MD/AD", "返回缺失或未完成；月级查询被拒绝")
    if not need_calc(ctx, c):
        return c
    md = read(ctx.path("A", "structured_data.md"))
    parts = re.split(r"(?m)^(?=### )", md)
    keep = [p for p in parts if not (p.startswith("### Vimsottari Dasha") or re.match(r"### \w+大运 Antardasha", p))]
    d = ctx.path("pd_only")
    write(os.path.join(d, "structured_data.md"), "".join(keep))
    code, out = ctx.run([os.path.join(CALC, "dasha_query.py"), "--file", os.path.join(d, "structured_data.md"), "--check"])
    c.check("--check 退出码 2（未完成）", code == 2)
    c.check("输出写明未完成", "未完成" in out)
    code, out = ctx.run([os.path.join(CALC, "dasha_query.py"), "--file", os.path.join(d, "structured_data.md"),
                         "--month", "2026-10"])
    c.check("--month 拒绝给月级窗口（退出码非 0）", code != 0)
    return c


def t05_bad_sign(ctx):
    c = Case("05", "输入无效星座名", "明确报错，指出字段")
    if not need_calc(ctx, c):
        return c
    bad = ctx.path("B_badsign")
    shutil.copytree(ctx.path("B"), bad)
    d = load(os.path.join(bad, "chart_data.json"))
    d["chart"]["planets"]["Mars"]["sign"] = "Aires"
    dump(d, os.path.join(bad, "chart_data.json"))
    code, out = ctx.std([os.path.join(SKILL, "synastry", "scripts", "build_synastry_data.py"),
                         ctx.path("A", "chart_data.json"), os.path.join(bad, "chart_data.json"), ctx.path("syn_bad"), "--today", SNAP])
    c.check("合盘生成拒绝（退出码 1）", code == 1)
    c.check("报错指出 Mars 与非法值 Aires", "Mars" in out and "Aires" in out)
    c.check("没有写出合盘数据", not os.path.exists(ctx.path("syn_bad", "synastry_data.md")))
    code, out = ctx.std([os.path.join(SKILL, "synastry", "scripts", "validate_synastry_data.py"),
                         ctx.path("A", "chart_data.json"), os.path.join(bad, "chart_data.json")])
    c.check("合盘自检失败（退出码 1）", code == 1)
    code, out = ctx.run([os.path.join(CALC, "check_chart.py"), "--dir", bad])
    c.check("check_chart 字段合法性失败并指出 Mars", code == 1 and "Mars" in out)
    bad2 = ctx.path("B_badul")
    shutil.copytree(ctx.path("B"), bad2)
    d = load(os.path.join(bad2, "chart_data.json"))
    d["chart"]["special_points"]["UL"]["sign"] = "Leoo"
    d["chart"]["karakas"]["dk_7k"] = "Pluto"
    dump(d, os.path.join(bad2, "chart_data.json"))
    code, out = ctx.std([os.path.join(SKILL, "synastry", "scripts", "build_synastry_data.py"),
                         ctx.path("A", "chart_data.json"), os.path.join(bad2, "chart_data.json"), ctx.path("syn_bad2"), "--today", SNAP])
    c.check("UL 星座非法、DK 行星名非法 → 拒绝并分别指出字段", code == 1 and "special_points.UL.sign" in out
            and "karakas.dk_7k" in out)
    return c


def t06_empty_claims(ctx):
    c = Case("06", "空的事实提取结果", "返回未完成，比较数量为零")
    d = ctx.path("empty_claims")
    write(os.path.join(d, "skill_claims_core.json"), json.dumps({"skill": "core", "claims": []}))
    facts = os.path.join(SKILL, "eval", "consistency", "fixtures", "example_chart", "canonical_facts.json")
    code, out = ctx.std([os.path.join(SKILL, "eval", "consistency", "check_consistency.py"), facts,
                         os.path.join(d, "skill_claims_core.json")])
    c.check("退出码 2（未完成）", code == 2)
    c.check("写明比较数为 0", "对源数据 0 条" in out and "跨模块共同事实 0 条" in out)
    code, out = ctx.std([os.path.join(SKILL, "eval", "consistency", "check_consistency.py"),
                         os.path.join(SKILL, "eval", "consistency", "fixtures", "example_chart")])
    c.check("对照：带注入冲突的样例 → 失败（退出码 1）", code == 1)
    return c


def _probes(fbs, flags=None):
    flags = flags or {}
    return [{"id": f"P{i+1}", "statement": "测试陈述", "feedback": fb, "flags": flags.get(i, {})}
            for i, fb in enumerate(fbs)]


def t07_scoring(ctx):
    c = Case("07", "2.5/5、3.5/5 及待核反馈", "评分与状态符合统一规则（准1/部分0.5/不准0；≥80高 ≥60中 <60低）")
    d = ctx.path("score")
    os.makedirs(d, exist_ok=True)
    sets = {
        "r25": (_probes(["hit", "hit", "partial", "miss", "miss"]), 0, "低", 2.5),
        "r35": (_probes(["hit", "hit", "hit", "partial", "miss"]), 0, "中", 3.5),
        "pending": (_probes(["hit", "hit", "hit", "hit", "pending"]), 2, "暂不定级", None),
        "unknown": (_probes(["hit", "hit", "hit", "hit", "unknown"]), 0, "高", 4.0),
        "taut": (_probes(["hit", "hit", "hit", "miss", "hit"], {0: {"tautology": True}, 1: {"known_fact": True}}),
                 0, "中", 2.0),
        "few": (_probes(["hit", "hit", "unknown"]), 2, "暂不定级", None),
        "unk2": (_probes(["hit", "hit", "hit", "unknown", "unknown"]), 2, "暂不定级", None),
        "rect": (_probes(["hit", "hit", "hit", "miss", "miss", "hit"], {0: {"used_in_rectification": True},
                                                                       1: {"used_in_rectification": True}}), 0, "低", 2.0),
        "bad": (_probes(["hit", "hit", "maybe", "hit"]), 1, "无效", None),
    }
    for name, (probes, want_code, want_level, want_pts) in sets.items():
        p = os.path.join(d, name + ".json")
        dump({"schema": "vedic-verification/1.0", "chart_id": "testchart000", "round": "R1", "probes": probes}, p)
        code, out = ctx.std([os.path.join(SHARED, "score_probes.py"), p, "--json"])
        try:
            r = json.loads(out[out.index("{"):])
        except ValueError:
            r = {}
        ok = code == want_code and r.get("level") == want_level and (want_pts is None or r.get("points") == want_pts)
        c.check(f"{name}: 退出码 {want_code}、等级 {want_level}" + (f"、得分 {want_pts}" if want_pts is not None else ""), ok)
        if name == "unknown":
            c.check("unknown: 待核题单列、不计分、标小样本", r.get("unknown_pending_review") == ["P5"]
                    and r.get("answered") == 4 and r.get("small_sample") is True)
        if name == "unk2":
            c.check("unk2: 3 准 + 2 不知道 → 待核超过 1/3，暂不定级（不按 3/3=100% 定为高）", "待核" in r.get("level_reason", ""))
        if name == "rect":
            c.check("rect: 校时用过的 2 题不计入（有效 4 题：2 准 2 不准 = 50% → 低）", r.get("valid") == 4)
        if name == "taut":
            c.check("taut: 恒真题与已知事实不计入（有效 3 题）", r.get("valid") == 3 and len(r.get("excluded", [])) == 2)
    code, out = ctx.std([os.path.join(SHARED, "score_probes.py"), os.path.join(d, "r35.json")])
    c.check("文本输出同时显示题数、有效题、匹配率、等级", all(k in out for k in ("探针 5 题", "有效 5 题", "匹配率", "反馈等级: 中")))
    return c


def t08_date_only_synastry(ctx):
    c = Case("08", "合盘一方缺出生时间", "执行允许的部分，限制对应结论")
    if not need_calc(ctx, c):
        return c
    d = ctx.path("B_date")
    code, out = ctx.run([os.path.join(CALC, "build_chart.py"), "--date-only", "--date", B["date"], "--tz", B["tz"],
                         "--lat", B["lat"], "--lon", B["lon"], "--out", d])
    c.check("仅日期排盘退出码 0", code == 0)
    doc = load(os.path.join(d, "chart_data.json"))
    ch = doc["chart"]
    c.check("上升=不适用、Dasha=未计算，不补时刻",
            ch.get("lagna", {}).get("_missing") == "not_applicable" and ch.get("dashas", {}).get("_missing") in ("not_computed", "not_applicable"))
    syn = ctx.path("syn_A_Bdate")
    code, out = ctx.std([os.path.join(SKILL, "synastry", "scripts", "build_synastry_data.py"),
                         ctx.path("A", "chart_data.json"), os.path.join(d, "chart_data.json"), syn, "--today", SNAP])
    c.check("合盘数据照常生成（退出码 0）", code == 0)
    smd = read(os.path.join(syn, "synastry_data.md")) if os.path.exists(os.path.join(syn, "synastry_data.md")) else ""
    c.check("缺时一方宫位标「不适用」", "不适用" in smd)
    c.check("写明受限层（仅日期）", "仅日期" in smd)
    code, out = ctx.std([os.path.join(SKILL, "synastry", "scripts", "validate_synastry_data.py"),
                         ctx.path("A", "chart_data.json"), os.path.join(d, "chart_data.json")])
    c.check("合盘自检 = 未完成（降级运行，退出码 2）", code == 2)
    return c


def _seed_records(ctx, d, as_of):
    code, out = ctx.std([os.path.join(SHARED, "analysis_record.py"), "init", "--dir", d, "--module", "core",
                         "--file", os.path.join(d, "analysis_record.json"), "--mode", "chart_derived", "--as-of", as_of])
    doc = load(os.path.join(d, "chart_data.json"))
    write(os.path.join(d, "core_summary.md"),
          f"# 核心摘要\n> 数据版本: chart_id={doc['chart_id']} · audit_id={doc['audit_id']} · 规则 {doc['rules_version']} · "
          f"基准日 {as_of} · 模式 chart_derived\n\n测试摘要。\n")
    dump({"schema": "vedic-verification/1.0", "chart_id": doc["chart_id"], "round": "R1",
          "probes": _probes(["hit", "hit", "partial", "miss", "hit"])}, os.path.join(d, "verification_record.json"))
    return code


def t09_rectified(ctx):
    c = Case("09", "出生时间校准后继续追问", "检出旧报告版本失效；旧验证记录不当新盘验证")
    if not need_calc(ctx, c):
        return c
    d = ctx.path("rect")
    shutil.copytree(ctx.path("A"), d)
    c.check("建分析记录", _seed_records(ctx, d, SNAP) == 0)
    code, out = ctx.std([os.path.join(SHARED, "check_freshness.py"), "--dir", d, "--today", SNAP])
    c.check("校时前：全部有效（退出码 0）", code == 0)
    old_id = load(os.path.join(d, "chart_data.json"))["chart_id"]
    code, out = build(ctx, d, dict(A, time="14:25", source="校时"), ["--declared-min", "2", "--original-source", "出生证"])
    new_id = load(os.path.join(d, "chart_data.json"))["chart_id"]
    c.check("校时重排得到新 chart_id", code in (0, 1) and new_id != old_id)
    code, out = ctx.std([os.path.join(SHARED, "check_freshness.py"), "--dir", d, "--today", SNAP])
    c.check("校时后：退出码 1（需更新）", code == 1)
    c.check("analysis_record.json 判为失效", "需更新  analysis_record.json 绑定 chart_id" in out)
    c.check("core_summary.md 判为失效", "需更新  core_summary.md 绑定 chart_id" in out)
    c.check("旧验证记录判为旧盘", "verification_record.json 绑定旧盘" in out)
    code, out = ctx.std([os.path.join(SHARED, "score_probes.py"), os.path.join(d, "verification_record.json"),
                         "--chart", os.path.join(d, "chart_data.json")])
    c.check("旧验证记录对新盘评分被拒（退出码 1）", code == 1)
    code, out = ctx.std([os.path.join(SHARED, "analysis_record.py"), "init", "--dir", d, "--module", "core",
                         "--file", os.path.join(d, "analysis_record.json"), "--mode", "chart_derived", "--as-of", SNAP])
    c.check("不能在旧记录上直接 init 覆盖（先归档）", code != 0)
    code, out = ctx.std([os.path.join(SHARED, "archive_chart.py"), "--dir", d, "--reason", "测试：先重排后归档"])
    arch = os.path.join(d, "archive", old_id)
    c.check("补归档：记录按其绑定的旧 chart_id 归档，不复制新盘文件",
            code == 0 and os.path.exists(os.path.join(arch, "analysis_record.json"))
            and not os.path.exists(os.path.join(arch, "chart_data.json")))
    code, out = ctx.std([os.path.join(SHARED, "check_freshness.py"), "--dir", d, "--today", SNAP])
    c.check("归档后：提示当前盘还没有分析、旧分析在 archive（需更新）", code == 1 and f"archive/{old_id}/" in out)
    return c


def x09_archive_first(ctx):
    c = Case("X9", "用户更正出生时间（先归档再重排）", "旧盘计算文件与全部记录进 archive/<旧 chart_id>/；user_context 留下；新盘提示重新分析")
    if not need_calc(ctx, c):
        return c
    d = ctx.path("correct")
    shutil.copytree(ctx.path("A"), d)
    _seed_records(ctx, d, SNAP)
    write(os.path.join(d, "user_context.md"), "# 用户背景\n- 测试\n")
    write(os.path.join(d, "parts", "p2a_planets.md"), "# P1\n")
    write(os.path.join(d, "qa_career.md"), "# QA\n")
    old_id = load(os.path.join(d, "chart_data.json"))["chart_id"]
    code, out = ctx.std([os.path.join(SHARED, "archive_chart.py"), "--dir", d, "--reason", "用户更正 14:23→14:40"])
    arch = os.path.join(d, "archive", old_id)
    c.check("归档退出码 0", code == 0)
    c.check("旧盘 chart_data.json / structured_data.md 复制进 archive", all(os.path.exists(os.path.join(arch, f))
            for f in ("chart_data.json", "structured_data.md", "ARCHIVED.txt")))
    c.check("分析记录、摘要、验证记录、parts/、QA 移走", all(os.path.exists(os.path.join(arch, f)) for f in
            ("analysis_record.json", "core_summary.md", "verification_record.json", "parts", "qa_career.md"))
            and not os.path.exists(os.path.join(d, "analysis_record.json")))
    c.check("user_context.md 留在原处", os.path.exists(os.path.join(d, "user_context.md")))
    code, _ = build(ctx, d, dict(A, time="14:40"))
    code, out = ctx.std([os.path.join(SHARED, "check_freshness.py"), "--dir", d, "--today", SNAP])
    c.check("重排后 check_freshness：当前盘还没有分析，旧分析在 archive（退出码 1）",
            code == 1 and f"archive/{old_id}/" in out)
    code, _ = ctx.std([os.path.join(SHARED, "analysis_record.py"), "init", "--dir", d, "--module", "core",
                       "--file", os.path.join(d, "analysis_record.json"), "--as-of", SNAP])
    c.check("新盘可以 init 新记录", code == 0)
    return c


def t10_ingress(ctx):
    c = Case("10", "快照未满三个月但已换座", "更新相关过运判断；刷新快照后恢复有效")
    if not need_calc(ctx, c):
        return c
    d = ctx.path("ingress")
    shutil.copytree(ctx.path("A"), d)
    tr = load(os.path.join(d, "chart_data.json"))["transit"]
    first = min((e for e in tr["future_ingress"] if e["date"] > SNAP), key=lambda e: e["date"])
    f_day = dt.date.fromisoformat(first["date"])
    c.check(f"快照 {SNAP} 后第一个换座 {first['date']} {first['planet']}（< 90 天）", (f_day - dt.date.fromisoformat(SNAP)).days < 90)
    before = (f_day - dt.timedelta(days=2)).isoformat()
    after = (f_day + dt.timedelta(days=3)).isoformat()
    code, out = ctx.std([os.path.join(SHARED, "check_freshness.py"), "--dir", d, "--today", before])
    c.check(f"{before}：过运快照仍有效", "没有慢行星换座" in out)
    code, out = ctx.std([os.path.join(SHARED, "check_freshness.py"), "--dir", d, "--today", after])
    c.check(f"{after}：检出已换座并要求更新（退出码 1）", code == 1 and "已换座" in out and first["planet"] in out)
    code, out = ctx.run([os.path.join(CALC, "transit.py"), "--chart", os.path.join(d, "chart_data.json"),
                         "--date", after, "--write"])
    c.check("transit.py --write 刷新快照", code == 0)
    code, out = ctx.std([os.path.join(SHARED, "check_freshness.py"), "--dir", d, "--today", after])
    c.check("刷新后过运快照有效、chart_id 不变", "没有慢行星换座" in out and
            load(os.path.join(d, "chart_data.json"))["chart_id"] == load(ctx.path("A", "chart_data.json"))["chart_id"])
    return c


def t11_grounding(ctx):
    c = Case("11", "缺少外部落地 skill", "内置基础流程可完成（静态检查：内置协议存在，外部 skill 只作增强）")
    g = os.path.join(SKILL, "shared", "grounding_basic.md")
    c.check("shared/grounding_basic.md 存在", os.path.exists(g))
    if os.path.exists(g):
        txt = read(g)
        c.check("内置协议有分节规则（≥3 节）", len(re.findall(r"(?m)^## ", txt)) >= 3)
    bad = []
    n = 0
    for root, _, files in os.walk(SKILL):
        for f in files:
            if not f.endswith(".md") or f == "CHANGELOG.md":
                continue
            for ln in read(os.path.join(root, f)).splitlines():
                if "oracle-grounding" in ln:
                    n += 1
                    if not any(k in ln for k in ("grounding_basic", "叠加", "增强", "没装", "未安装", "可选")):
                        bad.append(f"{os.path.relpath(os.path.join(root, f), SKILL)}: {ln.strip()[:60]}")
    c.check(f"提到 oracle-grounding 的 {n} 处都写明内置协议优先、外部只叠加", not bad)
    if bad:
        c.note = "；".join(bad[:3])
    c.check("根 SKILL.md 指向内置协议", "shared/grounding_basic.md" in read(os.path.join(SKILL, "SKILL.md")))
    return c


def t12_annual_missing(ctx):
    c = Case("12", "年盘关键数据缺失", "不生成伪精确结果")
    code, out = ctx.std([os.path.join(SKILL, "timing", "scripts", "varshaphala.py"), "--lagna", "Aries", "--age", "28"])
    c.check("退出码 2（未完成）", code == 2)
    c.check("Year Lord / Muntha 落宫标「不可算」", "Year Lord: 未提供年盘行星位置，不可算" in out and "Muntha 落宫: 未提供年盘 Lagna，不可算" in out)
    c.check("月盘 / Tajaka 标未计算", "Tajaka Yogas / 月盘: 未计算" in out)
    c.check("没有输出具体日期或月份窗口", not re.search(r"\d{4}-\d{2}-\d{2}|\d+ ?月", out))
    return c


def t13_legacy(ctx):
    c = Case("13", "旧版 Markdown 数据", "能导入，并准确标记缺项")
    if not need_calc(ctx, c):
        return c
    d = ctx.path("legacy")
    code, out = ctx.run([os.path.join(CALC, "import_legacy_md.py"), "--file",
                         os.path.join(SKILL, "tests", "fixtures", "legacy_v4_structured_data.md"), "--out", d, "--tz", "Asia/Shanghai"])
    c.check("导入退出码 0", code == 0)
    doc = load(os.path.join(d, "chart_data.json"))
    ch = doc["chart"]
    for key in ("graha_drishti", "functional", "yoga_prescan", "chara_dasha", "divisional_boundary_audit"):
        c.check(f"{key} 标「未计算」", isinstance(ch.get(key), dict) and ch[key].get("_missing") == "not_computed")
    c.check("8K 标缺失，不补算", isinstance(ch["karakas"].get("8k"), dict) and "_missing" in ch["karakas"]["8k"])
    c.check("有效精度标未声明（不沿用「±分钟级」）", doc["input"]["effective_label"] == "未声明" and doc["input"]["effective_minutes"] is None)
    md = read(os.path.join(d, "structured_data.md"))
    vr = read(os.path.join(d, "verification_record.md"))
    c.check("反馈节迁到 verification_record.md", "## 盘面初验结果" in vr and "## 信号修正日志" in vr)
    c.check("计算数据不再含反馈节", "盘面初验结果" not in md and "信号修正日志" not in md)
    c.check("原文件另存 structured_data.legacy.md", os.path.exists(os.path.join(d, "structured_data.legacy.md")))
    code, out = ctx.run([os.path.join(CALC, "check_chart.py"), "--dir", d])
    c.check("check_chart：精度项未完成、8K 未完成、缺 PD", "未完成" in line_of(out, "精度声明与审计范围")
            and "未完成" in line_of(out, "Karaka 7K/8K") and "缺 PD 层" in out)
    c.check("check_chart：旧引擎 MD 交界差 1 天记为说明（旧数据 ±1 天容差，不判失败），并提示交界日前后不下结论",
            "失败" not in line_of(out, "Vimsottari") and "交界差 1 天" in out and "不下结论" in out)
    c.check("能力范围：精度未知 → AD 条件使用、分盘未验证", "条件使用" in line_of(out, "阶段窗口（AD）")
            and "未验证" in line_of(out, "D9 宫位"))
    code, out = ctx.run([os.path.join(CALC, "build_chart.py"), "--from-json", os.path.join(d, "chart_data.json")])
    c.check("旧导入数据不能用 --from-json 冒充完整重排（退出码 2）", code == 2)
    return c


def t14_no_menu(ctx):
    c = Case("14", "用户已明确要求完整分析", "不因重复选择菜单而中断（静态检查文档规则；行为见场景试用）")
    root = read(os.path.join(SKILL, "SKILL.md"))
    c.check("根 SKILL.md：要完整分析时不弹选择菜单", "不再弹选择菜单中断，直接做" in root)
    c.check("根 SKILL.md：必须问的信息集中问一次", "必须问的信息集中问一次" in root)
    core = read(os.path.join(SKILL, "core", "MODULE.md"))
    c.check("core：完成后的提示不阻断，已点名专题直接进", "不阻断、不弹选择菜单" in core and "直接进对应模块，不再问" in core)
    c.check("calculator：排盘后按已说明目的继续", "不弹选择菜单" in read(os.path.join(SKILL, "calculator", "MODULE.md")))
    c.check("synastry：已给过的信息不再问", "已经给过的直接用，不再问" in read(os.path.join(SKILL, "synastry", "MODULE.md")))
    c.check("reader：缺的信息合并一次问完", "合成一条消息问完" in read(os.path.join(SKILL, "reader", "MODULE.md")))
    return c


# ---------------------------------------------------------------- 补充用例
def x01_regen(ctx):
    c = Case("X1", "JSON → Markdown 重新生成", "与排盘时写出的 structured_data.md 逐字一致")
    if not need_calc(ctx, c):
        return c
    d = ctx.path("regen")
    shutil.copytree(ctx.path("A"), d)
    code, _ = ctx.run([os.path.join(CALC, "build_chart.py"), "--from-json", os.path.join(d, "chart_data.json")])
    c.check("退出码 0", code == 0)
    c.check("逐字一致", read(os.path.join(d, "structured_data.md")) == read(ctx.path("A", "structured_data.md")))
    return c


def x02_dasha_errors(ctx):
    c = Case("X2", "Dasha 层级错误", "行星名错误、区间断档都判失败")
    if not need_calc(ctx, c):
        return c
    for tag, mutate in (("name", "name"), ("gap", "gap")):
        d = ctx.path("dasha_" + tag)
        shutil.copytree(ctx.path("A"), d)
        doc = load(os.path.join(d, "chart_data.json"))
        ad = doc["chart"]["dashas"][2]["antardashas"][3]
        if mutate == "name":
            ad["planet"] = "Pluto"
        else:
            nxt = ad["pratyantardashas"][5]
            k2 = "start_time" if "start_time" in nxt else "start"
            d0 = dt.date.fromisoformat(str(nxt[k2])[:10]) + dt.timedelta(days=9)
            nxt[k2] = d0.isoformat() + str(nxt[k2])[10:]
        dump(doc, os.path.join(d, "chart_data.json"))
        code, out = ctx.run([os.path.join(CALC, "dasha_query.py"), "--file", os.path.join(d, "chart_data.json"), "--check"])
        c.check(f"{'行星名改成 Pluto' if tag == 'name' else 'PD 断档 9 天'} → 失败（退出码 1）", code == 1)
    return c


def x03_shadbala(ctx):
    c = Case("X3", "Shadbala PDF 逐行合并", "只改 PDF 有的行，保留 calc 基准；出生时刻不符或行星名非法 → 拒绝")
    if not need_calc(ctx, c):
        return c
    d = ctx.path("shadbala")
    shutil.copytree(ctx.path("A"), d)
    pdf = os.path.join(d, "pdf.json")
    dump({"source": "JHora PDF p.3（测试值）", "birth": f"{A['date']} {A['time']}",
          "rows": {"Sun": {"total_rupas": 7.11, "ishta_phala": 30.0, "kashta_phala": 20.0},
                   "Mars": {"total_rupas": 5.55}}}, pdf)
    code, out = ctx.run([os.path.join(CALC, "merge_shadbala.py"), "--chart", os.path.join(d, "chart_data.json"), "--pdf-data", pdf])
    c.check("合并退出码 0", code == 0)
    doc = load(os.path.join(d, "chart_data.json"))
    ov = doc.get("overrides", {}).get("shadbala", {})
    c.check("只覆盖 Sun、Mars 两行", set(ov) == {"Sun", "Mars"})
    md = read(os.path.join(d, "structured_data.md"))
    sec = md.split("### Shadbala", 1)[1].split("###", 1)[0]
    sun = next((ln for ln in sec.splitlines() if ln.startswith("| Sun")), "")
    moon = next((ln for ln in sec.splitlines() if ln.startswith("| Moon")), "")
    c.check("Sun 行采用 PDF 值 7.11 并注明来源", "7.11" in sun and "PDF" in sun)
    c.check("Moon 行保持 calc", "PDF" not in moon and moon != "")
    bad = os.path.join(d, "pdf_bad.json")
    dump({"source": "x", "birth": f"{A['date']} 14:40", "rows": {"Sun": {"total_rupas": 7.0}}}, bad)
    code, _ = ctx.run([os.path.join(CALC, "merge_shadbala.py"), "--chart", os.path.join(d, "chart_data.json"), "--pdf-data", bad])
    c.check("出生时刻不符 → 拒绝（退出码 1）", code == 1)
    bad2 = os.path.join(d, "pdf_bad2.json")
    dump({"source": "x", "birth": f"{A['date']} {A['time']}", "rows": {"Pluto": {"total_rupas": 7.0}}}, bad2)
    code, _ = ctx.run([os.path.join(CALC, "merge_shadbala.py"), "--chart", os.path.join(d, "chart_data.json"), "--pdf-data", bad2])
    c.check("行星名非法 → 拒绝（退出码 1）", code == 1)
    return c


def x04_leak_and_source(ctx):
    c = Case("X4", "计算数据混入反馈 / 两份产物不同源", "都判失败")
    if not need_calc(ctx, c):
        return c
    d = ctx.path("leak")
    shutil.copytree(ctx.path("A"), d)
    md = read(os.path.join(d, "structured_data.md"))
    write(os.path.join(d, "structured_data.md"), md + "\n## 信号修正日志\n- 用户说 2019 年不准\n")
    code, out = ctx.run([os.path.join(CALC, "check_chart.py"), "--dir", d])
    c.check("混入「信号修正日志」→ 失败", code == 1 and "失败" in line_of(out, "计算数据不含反馈信息"))
    d2 = ctx.path("mismatch")
    shutil.copytree(ctx.path("A"), d2)
    doc = load(os.path.join(d2, "chart_data.json"))
    write(os.path.join(d2, "structured_data.md"), md.replace(doc["chart_id"], "000000000000"))
    code, out = ctx.run([os.path.join(CALC, "check_chart.py"), "--dir", d2])
    c.check("md 与 JSON 的 chart_id 不同 → 失败", code == 1 and "失败" in line_of(out, "两份产物同源"))
    return c


def x05_report(ctx):
    c = Case("X5", "报告打包", "缺章节时标「部分报告」，齐全时不标")
    try:
        import markdown  # noqa: F401
    except ImportError:
        code, _ = ctx.run(["-c", "import markdown"])
        if code != 0:
            c.incomplete("没有安装 markdown 包（report_builder 依赖），未执行")
            return c
    rb = os.path.join(SKILL, "core", "scripts", "report_builder.py")
    d = ctx.path("report_partial")
    write(os.path.join(d, "parts", "p2a_planets.md"), "# P1\n测试内容\n")
    code, out = ctx.run([rb, d, "--name", "测试"], py=sys.executable if _has_markdown() else None)
    c.check("只有 1 份 core 文件 → 「部分报告」", code == 0 and "部分报告" in out and "缺 p2b_planets.md" in out)
    d2 = ctx.path("report_full")
    for f in ("p2a_planets.md", "p2b_planets.md", "p2c_planets.md", "p3_divisional.md",
              "p4_houses.md", "p5a_life.md", "p5b_life.md", "appendix.md"):
        write(os.path.join(d2, "parts", f), f"# {f}\n测试内容\n")
    code, out = ctx.run([rb, d2, "--name", "测试"], py=sys.executable if _has_markdown() else None)
    c.check("8 份 core 文件齐全 → 不标部分报告", code == 0 and "部分报告" not in out and "应收录 8 · 实际 8" in out)
    return c


def _has_markdown():
    try:
        import markdown  # noqa: F401
        return True
    except ImportError:
        return False


def x06_analysis_record(ctx):
    c = Case("X6", "冻结与变更日志", "未冻结不能进入反馈复核；改结论必须写 原结论→新证据→原因→新结论")
    if not need_calc(ctx, c):
        return c
    d = ctx.path("arec")
    shutil.copytree(ctx.path("A"), d)
    ar = os.path.join(SHARED, "analysis_record.py")
    f = os.path.join(d, "analysis_record_core.json")
    ctx.std([ar, "init", "--dir", d, "--module", "core", "--mode", "chart_derived", "--as-of", SNAP])
    c.check("默认文件名 analysis_record_core.json", os.path.exists(f))
    code, _ = ctx.std([ar, "add", "--file", f, "--id", "C1", "--claim", "事业在 AD 内有调整", "--evidence", "10L 在 8 宫", "--resolution", "AD"])
    c.check("add 退出码 0", code == 0)
    code, _ = ctx.std([ar, "stage", "--file", f, "--set", "reviewed", "--read-feedback"])
    c.check("未冻结就读反馈 → 拒绝", code != 0)
    ctx.std([ar, "freeze", "--file", f])
    code, _ = ctx.std([ar, "change", "--file", f, "--id", "C1", "--new-evidence", "x", "--reason", "y", "--new", "z"])
    c.check("change 不写类别 → 拒绝", code != 0)
    code, _ = ctx.std([ar, "change", "--file", f, "--id", "C1", "--new-evidence", "用户反馈 2024 年换岗",
                       "--reason", "AD 窗口内事件形态更贴近调岗", "--new", "AD 内调岗", "--kind", "反馈复核"])
    c.check("change 带类别 → 记入", code == 0)
    code, _ = ctx.std([ar, "stage", "--file", f, "--set", "reviewed", "--read-feedback"])
    rec = load(f)
    log = rec.get("change_log") or rec.get("changes") or []
    c.check("冻结后读反馈 → mode=calibrated", code == 0 and rec.get("mode") == "calibrated")
    c.check("变更日志四要素齐全", bool(log) and all(k in json.dumps(log[-1], ensure_ascii=False) for k in ("事业在 AD 内有调整", "用户反馈 2024 年换岗", "AD 内调岗")))
    c.check("记录绑定 chart_id / 规则 / 基准日", rec.get("chart_id") == load(os.path.join(d, "chart_data.json"))["chart_id"]
            and rec.get("rules_version") == "vedic-5.2" and rec.get("as_of") == SNAP)
    return c


def x07_clock(ctx):
    c = Case("X7", "标准时 + 夏令时、校时参数", "标准时报时换成当地钟表时间；校时不给误差 → 拒绝")
    if not need_calc(ctx, c):
        return c
    d = ctx.path("dst")
    code, _ = build(ctx, d, dict(A, date="1988-07-01", time="14:00"), ["--clock-type", "标准时", "--no-transit"])
    inp = load(os.path.join(d, "chart_data.json"))["input"] if code in (0, 1) else {}
    c.check("1988-07-01 14:00 标准时 → 计算用 15:00、夏令时=是", inp.get("time_used") == "15:00" and inp.get("is_dst") is True)
    code, out = build(ctx, ctx.path("rect_bad"), dict(A, source="校时"), ["--no-transit"])
    c.check("--source 校时 不给 --declared-min → 退出码 2", code == 2)
    return c


def x08_date_only_chart(ctx):
    c = Case("X8", "仅日期排盘自检", "Moon 经度标不适用；check_chart 不判通过也不判失败")
    if not need_calc(ctx, c):
        return c
    d = ctx.path("B_date")
    if not os.path.exists(os.path.join(d, "chart_data.json")):
        c.incomplete("依赖用例 08 的仅日期盘")
        return c
    doc = load(os.path.join(d, "chart_data.json"))
    moon = doc["chart"]["planets"].get("Moon", {})
    c.check("Moon 经度 = 不适用", isinstance(moon.get("longitude"), dict) and moon["longitude"].get("_missing") == "not_applicable")
    code, out = ctx.run([os.path.join(CALC, "check_chart.py"), "--dir", d])
    c.check("check_chart 退出码 2（未完成）", code == 2)
    return c


BENCH = [
    ("A", None), ("B", None),
    ("bench_ba", dict(date="1985-03-14", time="06:45", tz="America/Argentina/Buenos_Aires", lat="-34.6037",
                      lon="-58.3816", place="布宜诺斯艾利斯（虚构）", source="出生证")),
    ("bench_ny", dict(date="2001-12-01", time="23:50", tz="America/New_York", lat="40.7128", lon="-74.0060",
                      place="纽约（虚构）", source="出生证")),
    ("bench_del", dict(date="1975-08-30", time="03:05", tz="Asia/Kolkata", lat="28.6139", lon="77.2090",
                       place="新德里（虚构）", source="出生证")),
    ("bench_osl", dict(date="1968-01-09", time="17:20", tz="Europe/Oslo", lat="59.9139", lon="10.7522",
                       place="奥斯陆（虚构）", source="出生证")),
    # 回归：PyJHora 4.8.6 原版真恒星年在 2001-04 ~ 2002-04 出生的盘多算 1 天（Dasha 表整体拉伸 0.27%）
    ("bench_sh2001", dict(date="2001-09-01", time="12:00", tz="Asia/Shanghai", lat="31.2304", lon="121.4737",
                          place="上海 2001（虚构，年长回归）", source="出生证")),
]


def b01_independent(ctx):
    c = Case("B1", "独立星历对照（数值基准）",
             "7 张虚构盘（南北半球、东西经、高纬、年长回归盘）的 Ayanamsa、七星、Rahu、Lagna 与 astropy/ERFA 独立复算相差 ≤ 2′；"
             "首段与第 9 段 Vimsottari 结束日与独立推算相差 ≤ 1 天")
    if not need_calc(ctx, c):
        return c
    worst = 0.0
    for tag, person in BENCH:
        if person:
            build(ctx, ctx.path(tag), person, ["--no-transit"])
        code, out = ctx.run([os.path.join(SKILL, "tests", "bench_positions.py"), "--chart",
                             ctx.path(tag, "chart_data.json"), "--json"])
        if code == 2:
            c.incomplete("没有 astropy（pip install astropy），未执行独立对照")
            return c
        try:
            r = json.JSONDecoder().raw_decode(out[out.index("{"):])[0]
        except ValueError:
            c.check(f"{tag}: 对照脚本输出可解析", False)
            continue
        worst = max(worst, r["max_diff_arcmin"])
        place = (person or (A if tag == "A" else B))["place"]
        v = r["vimsottari"]
        c.check(f"{place}: 位置最大差 {r['max_diff_arcmin']:.2f}′ ≤ 2′；MD 结束日差 首段 {v['diff_days']} 天 / "
                f"第 9 段 {v['last_diff_days']} 天（≤ 1）", code == 0)
    c.note = f"全部盘最大偏差 {worst:.2f}′"
    return c


def x10_synastry_record(ctx):
    c = Case("X10", "合盘子目录的分析记录与时效", "登记双方 chart_id；任一方盘变了能检出")
    if not need_calc(ctx, c):
        return c
    sub = ctx.path("syn_rec")
    shutil.copytree(ctx.path("B"), os.path.join(sub, "B"))
    rec = os.path.join(sub, "analysis_record_synastry.json")
    code, out = ctx.std([os.path.join(SHARED, "analysis_record.py"), "init", "--dir", sub, "--module", "synastry",
                         "--chart", "A=" + ctx.path("A", "chart_data.json"),
                         "--chart", "B=" + os.path.join(sub, "B", "chart_data.json"), "--as-of", SNAP])
    r = load(rec) if os.path.exists(rec) else {}
    c.check("init 在没有 chart_data.json 的子目录成功，登记 2 张盘", code == 0 and len(r.get("charts", [])) == 2)
    code, out = ctx.std([os.path.join(SHARED, "check_freshness.py"), "--dir", sub, "--today", SNAP])
    c.check("双方盘未变 → 有效（退出码 0）", code == 0)
    build(ctx, os.path.join(sub, "B"), dict(B, time="08:30"), ["--no-transit"])
    code, out = ctx.std([os.path.join(SHARED, "check_freshness.py"), "--dir", sub, "--today", SNAP])
    c.check("B 的盘变了 → 需更新并点名 B（退出码 1）", code == 1 and "B 的盘已变" in out)
    code, out = ctx.std([os.path.join(SHARED, "analysis_record.py"), "init", "--dir", sub, "--module", "synastry",
                         "--chart", "A=" + ctx.path("A", "chart_data.json"),
                         "--chart", "B=" + os.path.join(sub, "B", "chart_data.json"), "--as-of", SNAP])
    c.check("直接重建记录被拒，并提示对子目录运行 archive_chart.py", code == 1 and "archive_chart.py" in out)
    write(os.path.join(sub, "synastry_data.md"), "# old\n")
    code, out = ctx.std([os.path.join(SHARED, "archive_chart.py"), "--dir", sub, "--reason", "B 更正出生时间"])
    c.check("合盘子目录归档：记录与 synastry_data 移走，B/ 不动", code == 0 and not os.path.exists(rec)
            and not os.path.exists(os.path.join(sub, "synastry_data.md")) and os.path.isdir(os.path.join(sub, "B")))
    code, out = ctx.std([os.path.join(SHARED, "analysis_record.py"), "init", "--dir", sub, "--module", "synastry",
                         "--chart", "A=" + ctx.path("A", "chart_data.json"),
                         "--chart", "B=" + os.path.join(sub, "B", "chart_data.json"), "--as-of", SNAP])
    c.check("归档后可以按新盘建记录", code == 0)
    return c


def x11_engine_rules(ctx):
    c = Case("X11", "引擎或规则升级后的旧产物", "按当前 skill 的引擎/规则版本判需更新，而不是只比盘内字段")
    if not need_calc(ctx, c):
        return c
    d = ctx.path("oldengine")
    shutil.copytree(ctx.path("A"), d)
    _seed_records(ctx, d, SNAP)
    doc = load(os.path.join(d, "chart_data.json"))
    doc["engine_version"] = "calculator-0.9+vedic5.1"
    dump(doc, os.path.join(d, "chart_data.json"))
    r = load(os.path.join(d, "analysis_record.json"))
    r["rules_version"] = "vedic-5.0"
    dump(r, os.path.join(d, "analysis_record.json"))
    code, out = ctx.std([os.path.join(SHARED, "check_freshness.py"), "--dir", d, "--today", SNAP])
    c.check("旧引擎生成的盘 → 需更新（重排）", code == 1 and "由引擎 calculator-0.9+vedic5.1 生成" in out)
    c.check("旧规则写成的分析 → 需复核", "用规则 vedic-5.0 写成" in out)
    return c


def x12_koota_reduction(ctx):
    c = Case("X12", "月宿筛查的 dosha 减免", "按 koota-policy §3 判减免并写明原因；不满足条件时保持制约")
    from types import SimpleNamespace as NS
    sys.path.insert(0, os.path.join(SKILL, "synastry", "scripts"))
    try:
        import build_synastry_data as bsd
    finally:
        sys.path.pop(0)

    def mk(sign, nak, pada=1):
        si = bsd.SIGNS.index(sign)
        return NS(planets={"Moon": {"sign": sign, "sidx": si}}, moon_nak=nak, moon_pada=pada)

    def tier(a, b, item):
        return next((r["tier"] for r in bsd.ashtakoota(a, b) if r["item"] == item), "")
    t = tier(mk("Aries", "Ashwini"), mk("Scorpio", "Anuradha"), "Bhakoot")
    c.check(f"Aries×Scorpio（相对 8，座主同为 Mars）→ Bhakoot 已减免：{t}", "已减免" in t and "相同" in t)
    t = tier(mk("Aries", "Ashwini"), mk("Virgo", "Hasta"), "Bhakoot")
    c.check(f"Aries×Virgo（相对 6，Mars 视 Mercury 为敌）→ 保持制约：{t}", "制约" in t and "已减免" not in t)
    t = tier(mk("Aries", "Ashwini", 1), mk("Aries", "Ashwini", 3), "Nadi")
    c.check(f"同宿不同 Pada → Nadi 已减免：{t}", "已减免" in t)
    rows = bsd.ashtakoota(mk("Aries", "Ashwini"), NS(planets={"Moon": {"sign": "Leo", "sidx": 4}}, moon_nak=None, moon_pada=None))
    na = [r["item"] for r in rows if r["tier"].startswith("不适用")]
    c.check(f"一方宿不稳定 → 宿相关四项明确标不适用：{na}", set(na) == {"Tara", "Yoni", "Gana", "Nadi"})
    return c


# ---------------------------------------------------------------- 5.2 新增
M = dict(date="2007-02-14", time="04:01", tz="Pacific/Auckland", lat="-36.85", lon="174.76",
         place="奥克兰（虚构测试盘）", source="出生证")          # Moon 在 Mula
V = dict(date="1990-12-15", time="10:20", tz="Asia/Shanghai", lat="31.2304", lon="121.4737",
         place="上海（虚构测试盘）", source="出生证")            # Venus 在 Mula
K = dict(date="1952-08-24", time="00:30", tz="America/St_Johns", lat="47.56", lon="-52.71",
         place="圣约翰斯（虚构测试盘）", source="出生证")        # Mars 在 Scorpio、Ketu 在 Cancer
BJ = ["--tz", "Asia/Shanghai", "--lat", "39.9042", "--lon", "116.4074", "--place", "北京（虚构测试盘）", "--no-transit"]


def _bc(ctx, out_dir, *args):
    return ctx.run([os.path.join(CALC, "build_chart.py"), "--out", out_dir] + list(args))


def x13_mula(ctx):
    c = Case("X13", "行星落在第 19 宿（Mula）", "排盘、总检查、合盘都正常；旧盘里的 Moola 写法按同一宿接受")
    if not need_calc(ctx, c):
        return c
    for tag, person in (("M", M), ("V", V)):
        build(ctx, ctx.path(tag), person)
    m = load(ctx.path("M", "chart_data.json"))
    v = load(ctx.path("V", "chart_data.json"))
    c.check("Moon 的宿名写作 Mula", m["chart"]["planets"]["Moon"]["nakshatra"]["name"] == "Mula")
    c.check("Venus 的宿名写作 Mula", v["chart"]["planets"]["Venus"]["nakshatra"]["name"] == "Mula")
    for tag in ("M", "V"):
        code, out = ctx.run([os.path.join(CALC, "check_chart.py"), "--dir", ctx.path(tag)])
        c.check(f"{tag} 盘 check_chart 总体通过", code == 0 and "总体: 通过" in out)
    syn = os.path.join(SKILL, "synastry", "scripts")
    code, out = ctx.std([os.path.join(syn, "validate_synastry_data.py"),
                         ctx.path("A", "structured_data.md"), ctx.path("M", "structured_data.md")])
    c.check("合盘自检通过（一方 Moon 在 Mula）", code == 0)
    code, out = ctx.std([os.path.join(syn, "build_synastry_data.py"), ctx.path("A", "structured_data.md"),
                         ctx.path("M", "structured_data.md"), ctx.path("syn_mula")])
    c.check("合盘数据生成（退出码 0）", code == 0 and os.path.exists(ctx.path("syn_mula", "synastry_data.md")))
    # 5.1 及更早的引擎写的是 Moola：旧盘不应因此判失败
    old = ctx.path("M_old")
    shutil.copytree(ctx.path("M"), old)
    for fn in ("chart_data.json", "structured_data.md"):
        write(os.path.join(old, fn), read(os.path.join(old, fn)).replace("Mula", "Moola"))
    code, out = ctx.run([os.path.join(CALC, "check_chart.py"), "--dir", old])
    c.check("旧盘写 Moola → 字段合法性通过", "字段合法性（chart_data.json）" in out
            and "失败" not in line_of(out, "字段合法性（chart_data.json）"))
    code, out = ctx.std([os.path.join(syn, "build_synastry_data.py"), ctx.path("A", "structured_data.md"),
                         os.path.join(old, "structured_data.md"), ctx.path("syn_moola")])
    c.check("旧盘写 Moola → 合盘照常生成", code == 0)
    bad = ctx.path("M_bad")
    shutil.copytree(ctx.path("M"), bad)
    write(os.path.join(bad, "chart_data.json"), read(os.path.join(bad, "chart_data.json")).replace("Mula", "Mulaa"))
    code, out = ctx.run([os.path.join(CALC, "check_chart.py"), "--dir", bad])
    c.check("真正的非法宿名仍判失败", code == 1 and "非法宿名" in out)
    return c


def x14_chara_colord(ctx):
    c = Case("X14", "Chara Dasha 双主座（Scorpio / Aquarius）",
             "两主都在本座 12 年 → 一主在本座数到另一主 → 同座行星更多 → 变动>固定>启动 → 年数较大；两处实现一致")
    sys.path.insert(0, CALC)
    try:
        import chara_dasha as cd
    finally:
        sys.path.pop(0)
    base = {"Sun": 3, "Moon": 1, "Mars": 0, "Mercury": 4, "Jupiter": 3, "Venus": 3, "Saturn": 8, "Rahu": 9, "Ketu": 3}
    exp = {6: [9, 8, 7, 1, 2, 8, 12, 2, 2, 2, 1, 1], 5: [1, 9, 8, 7, 1, 2, 8, 12, 2, 2, 2, 1]}
    ok = all([m["years"] for m in cd.calc_chara_dasha(lg, base, 2448118.6)["mahadashas"]] == e for lg, e in exp.items())
    c.check("JHora 双盘 24 个大运数据点仍然 24/24 一致", ok)
    rows = [
        ("一主在本座（Mars 在 Sc、Ketu 在 Cn）→ 数到 Ketu，8 年（旧规则 12 年）",
         dict(base, Mars=7, Ketu=3, Rahu=9), 7, (8, "Ketu", "other_lord")),
        ("两主都在本座 → 12 年", dict(base, Saturn=10, Rahu=10, Ketu=4), 10, (12, "Saturn", "both_in_sign")),
        ("同座行星更多（Rahu 伴 2 星、Saturn 独处）→ 数到 Rahu，6 年（旧规则 11 年）",
         {"Sun": 4, "Moon": 0, "Mars": 1, "Mercury": 4, "Jupiter": 2, "Venus": 5, "Saturn": 11, "Rahu": 4, "Ketu": 10},
         10, (6, "Rahu", "more_conjunct")),
        ("同座行星数相同，Mars 在变动座、Ketu 在启动座 → 数到 Mars，1 年（旧规则 2 年）",
         {"Sun": 0, "Moon": 1, "Mars": 8, "Mercury": 0, "Jupiter": 2, "Venus": 11, "Saturn": 4, "Rahu": 3, "Ketu": 9},
         7, (1, "Mars", "sign_nature")),
        ("前几步都相同 → 年数较大者，7 年",
         {"Sun": 0, "Moon": 1, "Mars": 2, "Mercury": 0, "Jupiter": 3, "Venus": 9, "Saturn": 4, "Rahu": 5, "Ketu": 11},
         7, (7, "Mars", "larger_years")),
    ]
    for name, ps, sign, e in rows:
        r = cd.md_years(sign, ps)
        c.check(name, (r["years"], r["lord"], r["rule"]) == e)
    import importlib.util
    import random
    from datetime import datetime as _dtm
    spec = importlib.util.spec_from_file_location("timing_chara", os.path.join(SKILL, "timing", "scripts", "chara_dasha.py"))
    tm = importlib.util.module_from_spec(spec)
    sys.modules["timing_chara"] = tm
    spec.loader.exec_module(tm)
    rnd, same, n = random.Random(7), 0, 3000
    for _ in range(n):
        lag = rnd.randrange(12)
        pos = {p: rnd.randrange(12) for p in ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu")}
        pos["Ketu"] = (pos["Rahu"] + 6) % 12
        a = [(m["sign"], m["years"]) for m in cd.calc_chara_dasha(lag, pos, 2450000.0)["mahadashas"]]
        b = [(m.sign, m.years) for m in tm.generate_chara_md_sequence(
            cd.SIGNS[lag], {k: cd.SIGNS[v] for k, v in pos.items()}, _dtm(1990, 1, 1))]
        same += a == b
    c.check(f"timing 脚本与 calculator 在 {n} 张随机盘上逐段一致（{same}/{n}）", same == n)
    if not need_calc(ctx, c):
        return c
    build(ctx, ctx.path("K"), K)
    doc = load(ctx.path("K", "chart_data.json"))
    sc = next(m for m in doc["chart"]["chara_dasha"]["mahadashas"] if m["sign"] == "Scorpio")
    c.check("实盘（Mars 在 Scorpio、Ketu 在 Cancer）：Scorpio 8 年，数到 Ketu",
            sc["years"] == 8 and sc["lord"] == "Ketu" and sc["rule"] == "other_lord")
    md = read(ctx.path("K", "structured_data.md"))
    c.check("阅读版写明所数宫主与依据", "| Scorpio |" in md and "Mars 在本座，数到 Ketu" in md)
    c.check("Chara 时间线第一段从出生地日期起（不早一天）", "| Gemini | 1952-08-24 |" in md)
    old = ctx.path("K_old")
    shutil.copytree(ctx.path("K"), old)
    d2 = load(os.path.join(old, "chart_data.json"))
    for m in d2["chart"]["chara_dasha"]["mahadashas"]:
        for k in ("lord", "rule", "alt_years"):
            m.pop(k, None)
    dump(d2, os.path.join(old, "chart_data.json"))
    code, out = ctx.run([os.path.join(CALC, "build_chart.py"), "--from-json", os.path.join(old, "chart_data.json")])
    c.check("旧引擎排的 Chara 表：阅读版提示先重排", code in (0, 1) and "由 5.1 及更早的引擎生成" in read(os.path.join(old, "structured_data.md")))
    return c


def x15_inputs(ctx):
    c = Case("X15", "输入校验", "经纬度越界或传反、时区名、时间格式、校时缺原来源：明确报出并且不写出文件")
    if not need_calc(ctx, c):
        return c

    def rejected(tag, args, key):
        d = ctx.path("in_" + tag)
        code, out = _bc(ctx, d, *args)
        return code == 2 and "输入有误" in out and key in out and not os.path.exists(os.path.join(d, "chart_data.json"))
    base = ["--date", "1990-05-21", "--time", "14:23", "--source", "出生证", "--no-transit"]
    sh = ["--tz", "Asia/Shanghai"]
    c.check("经纬度传反（--lat 116.4 --lon 39.9）→ 拒绝并指出可能传反",
            rejected("swap", base + sh + ["--lat", "116.4074", "--lon", "39.9042"], "传反"))
    c.check("纬度 139.9 → 拒绝", rejected("lat", base + sh + ["--lat", "139.9", "--lon", "116.4"], "纬度"))
    c.check("经度 200 → 拒绝", rejected("lon", base + sh + ["--lat", "39.9", "--lon", "200"], "经度"))
    c.check("时区写 Asia/Beijing → 拒绝并给出 IANA 写法",
            rejected("tz", base + ["--tz", "Asia/Beijing", "--lat", "39.9", "--lon", "116.4"], "IANA"))
    c.check("时间带秒 → 拒绝并说明只到分钟",
            rejected("sec", ["--date", "1990-05-21", "--time", "14:23:40", "--source", "出生证"] + BJ, "分钟"))
    c.check("日期不存在（2 月 30 日）→ 拒绝",
            rejected("date", ["--date", "1990-02-30", "--time", "14:23", "--source", "出生证"] + BJ, "不是一个存在的日期"))
    c.check("校时不给 --original-source → 拒绝",
            rejected("rect", ["--date", "1990-05-21", "--time", "14:23", "--source", "校时", "--declared-min", "3"] + BJ,
                     "--original-source"))
    d = ctx.path("in_warn")
    code, out = _bc(ctx, d, "--date", "1990-05-21", "--time", "14:23", "--source", "出生证", "--no-transit",
                    "--tz", "Europe/London", "--lat", "-0.12", "--lon", "51.5")
    c.check("经度与时区相差过大（伦敦时区、经度 51.5）→ 提示核对，但不拦截", code == 0 and "请确认" in out)
    code, out = _bc(ctx, ctx.path("in_ok"), "--date", "1990-05-21", "--time", "14:23", "--source", "出生证", *BJ)
    c.check("正常输入不出提示", code == 0 and "请确认" not in out and "输入有误" not in out)
    return c


def x16_dst_switch(ctx):
    c = Case("X16", "夏令时切换当天", "不存在的钟表时刻报错并指路；重复的钟表时刻必须指明哪一次；切换点附近的盘照常排出")
    if not need_calc(ctx, c):
        return c
    src = ["--source", "出生证"]
    code, out = _bc(ctx, ctx.path("dst_gap"), "--date", "1988-04-17", "--time", "02:30", *src, *BJ)
    c.check("1988-04-17 02:30（钟表上不存在）→ 拒绝，并提示 --clock-type 标准时", code == 2 and "不存在" in out and "--clock-type 标准时" in out)
    code, out = _bc(ctx, ctx.path("dst_gap_std"), "--date", "1988-04-17", "--time", "02:30", "--clock-type", "标准时", *src, *BJ)
    i = load(ctx.path("dst_gap_std", "chart_data.json"))["input"] if code == 0 else {}
    c.check("同一时刻按标准时 → 计算用 03:30、夏令时=是", i.get("time_used") == "03:30" and i.get("is_dst") is True)
    code, out = _bc(ctx, ctx.path("dst_amb"), "--date", "1988-09-11", "--time", "01:30", *src, *BJ)
    c.check("1988-09-11 01:30（钟表上出现两次）→ 拒绝，并提示 --repeated-hour", code == 2 and "--repeated-hour" in out)
    docs = {}
    for tag, side in (("a", "夏令时"), ("b", "标准时")):
        code, out = _bc(ctx, ctx.path("dst_amb_" + tag), "--date", "1988-09-11", "--time", "01:30",
                        "--repeated-hour", side, *src, *BJ)
        docs[tag] = load(ctx.path("dst_amb_" + tag, "chart_data.json")) if code == 0 else {}
    ia, ib = docs["a"].get("input", {}), docs["b"].get("input", {})
    c.check("指明拨回前 / 拨回后 → 两张不同的盘（UTC 偏移 9:00 与 8:00，chart_id 不同）",
            ia.get("utc_offset") == "9:00:00" and ib.get("utc_offset") == "8:00:00"
            and docs["a"].get("chart_id") != docs["b"].get("chart_id"))
    code, out = _bc(ctx, ctx.path("dst_amb_std"), "--date", "1988-09-11", "--time", "01:30", "--clock-type", "标准时", *src, *BJ)
    d = load(ctx.path("dst_amb_std", "chart_data.json")) if code == 0 else {}
    c.check("同一时刻按标准时 = 拨回后的那一次（chart_id 相同）", d.get("chart_id") == docs["b"].get("chart_id"))
    for tag, date, tm in (("near_start", "1988-04-17", "03:05"), ("near_end", "1988-09-11", "02:05")):
        code, out = _bc(ctx, ctx.path("dst_" + tag), "--date", date, "--time", tm, "--source", "未知", *BJ)
        a = (load(ctx.path("dst_" + tag, "chart_data.json"))["chart"].get("divisional_boundary_audit") or {}) if code == 0 else {}
        c.check(f"{date} {tm}，±15 分钟审计范围跨过切换点 → 照常排出并完成审计",
                code == 0 and a.get("status") == "ok" and a.get("uncertainty_minutes") == 15)
    code, out = _bc(ctx, ctx.path("dst_mid"), "--date", "1988-07-01", "--time", "23:30", "--clock-type", "标准时", *src, *BJ)
    i = load(ctx.path("dst_mid", "chart_data.json"))["input"] if code == 0 else {}
    c.check("标准时 23:30（夏令时期间）→ 计算用次日 00:30，两个日期都记录",
            i.get("date") == "1988-07-02" and i.get("time_used") == "00:30" and i.get("date_reported") == "1988-07-01")
    for tag, date in (("start", "1988-04-17"), ("end", "1988-09-11")):
        code, out = ctx.run([os.path.join(CALC, "build_chart.py"), "--date-only", "--date", date, "--tz", "Asia/Shanghai",
                             "--lat", "39.9042", "--lon", "116.4074", "--out", ctx.path("dst_do_" + tag)])
        c.check(f"仅日期模式：切换当天 {date} 也能排", code == 0)
    return c


def x17_hora(ctx):
    c = Case("X17", "D2 用传统 Parasara Hora", "D2 里行星只落 Cancer 或 Leo")
    if not need_calc(ctx, c):
        return c
    for tag in ("A", "B"):
        d2 = load(ctx.path(tag, "chart_data.json"))["chart"]["divisional_charts"]["D2"]
        signs = {k: (v.get("sign") if isinstance(v, dict) else v) for k, v in d2.items()}
        c.check(f"{tag} 盘 D2：{sorted(set(signs.values()))}", set(signs.values()) <= {"Cancer", "Leo"} and len(signs) >= 9)
    return c


def x18_small(ctx):
    c = Case("X18", "出生前的日期查询与修复提示", "查到出生日之前给出提示；环境修复命令把 venv 建在工作目录")
    if not need_calc(ctx, c):
        return c
    code, out = ctx.run([os.path.join(CALC, "dasha_query.py"), "--file", ctx.path("A", "structured_data.md"),
                         "--date", "1985-01-01"])
    c.check("查询日期早于出生日 → 输出里有提示", "出生日 1990-05-21 之前" in out)
    code, out = ctx.run([os.path.join(CALC, "dasha_query.py"), "--file", ctx.path("A", "structured_data.md"),
                         "--month", "2026-10"])
    c.check("出生之后的查询不带这条提示", "出生日" not in out and "命中窗口" in out)
    src = read(os.path.join(CALC, "check_env.py"))
    c.check("check_env.py 的修复命令带 --target <工作目录>/vedic-calc-env", src.count("--target {_target_dir()}") == 2)
    md = read(ctx.path("A", "structured_data.md"))
    row = line_of(md, "| Moon | ")
    fn = md.split("### 功能身份", 1)[1].split("###", 1)[0] if "### 功能身份" in md else ""
    moon = line_of(fn, "| Moon |")
    cells = [x.strip() for x in moon.strip("|").split("|")] if moon else []
    c.check(f"功能身份表：Moon 的 MT 宫一格不写它不掌管的宫（{cells[2] if len(cells) > 2 else '缺行'}）",
            len(cells) > 2 and (cells[2] == "—" or cells[2] in cells[1].split("/")))
    return c


# ---------------------------------------------------------------- 5.3 新增：提问盘（prashna）
PRASHNA_TESTS = os.path.join(SKILL, "prashna", "tests")


def _prashna_suite(ctx, cid, title, expected, script):
    c = Case(cid, title, expected)
    if not need_calc(ctx, c):
        return c
    code, out = ctx.run([os.path.join(PRASHNA_TESTS, script)])
    names = re.findall(r"^\[(PASS|FAIL)\] (\S+)", out, re.M)
    for st, name in names:
        c.check(name, st == "PASS")
    c.check(f"{script} 退出码 0 且全绿（{len(names)} 项）", code == 0 and "[GREEN]" in out and bool(names))
    if code != 0:
        c.note = out[-600:]
    return c


def p01_prashna_standard(ctx):
    return _prashna_suite(
        ctx, "P1", "提问盘：隔离断言、标准层与时间副层算例、秒级整盘",
        "七条隔离断言成立；时间副层与标准层算例、秒级整盘、判定算例（上游冻结账本）在本 skill 的引擎上复现",
        "test_prashna_isolation.py")


def p02_prashna_tajika(ctx):
    return _prashna_suite(
        ctx, "P2", "提问盘：Tajika 过程层与一条命令调度",
        "出版接触几何与 Hāyanaratna 正例复现；靠近／走远与真实星历独立复算一致；过程层不改标准层判定",
        "test_tajika_layer.py")


def x19_engine_seconds(ctx):
    c = Case("X19", "引擎秒级参数不改变本命盘", "second 缺省或为 0 时整张盘与不传相同；带秒时 Lagna 落在相邻两个整分之间")
    if not need_calc(ctx, c):
        return c
    probe = ctx.path("x19_probe.py")
    write(probe, f"""
import sys, io, json, contextlib
sys.path.insert(0, {CALC!r})
with contextlib.redirect_stdout(io.StringIO()):
    import engine
    args = (1990, 5, 21, 14, 23, 39.9042, 116.4074, 'Asia/Shanghai')
    a = engine.calculate_full_chart(*args)
    b = engine.calculate_full_chart(*args, second=0.0)
    m = engine.calculate_full_chart(*args, second=30.0)
    nxt = engine.calculate_full_chart(1990, 5, 21, 14, 24, 39.9042, 116.4074, 'Asia/Shanghai')
for ch in (a, b, m, nxt):
    ch.pop('transits', None)
dump = lambda ch: json.dumps(ch, sort_keys=True, default=str)
la, lm, ln = (ch['lagna']['longitude'] for ch in (a, m, nxt))
print(json.dumps({{
    'same': dump(a) == dump(b),
    'between': la < lm < ln,
    'half': abs((lm - la) - (ln - la) / 2) < 0.01,
    'jd': abs(engine.to_jd(1990, 5, 21, 14, 23, 'Asia/Shanghai', 30) - engine.to_jd(1990, 5, 21, 14, 23, 'Asia/Shanghai') - 30 / 86400) < 1e-8,
    'keys': sorted(a.keys()) == sorted(m.keys()),
    'd9': m['divisional_charts']['D9']['Lagna']['sign'] in (a['divisional_charts']['D9']['Lagna']['sign'], nxt['divisional_charts']['D9']['Lagna']['sign']),
}}))
""")
    code, out = ctx.run([probe])
    try:
        r = json.loads(out.strip().splitlines()[-1])
    except Exception:
        c.check(f"探针运行失败: {out[-300:]}", False)
        return c
    c.check("second=0.0 与不传 second：整张盘（不含过运）逐字段相同", r["same"])
    c.check("second=30：Lagna 落在 14:23 与 14:24 两张盘之间，且约在中点", r["between"] and r["half"])
    c.check("to_jd 带 30 秒 = 整分 JD + 30/86400 日", r["jd"])
    c.check("带秒的盘字段集合与整分盘相同（引擎返回值没有新增键）；D9 Lagna 取相邻两分钟之一", r["keys"] and r["d9"])
    src = read(os.path.join(CALC, "build_chart.py"))
    c.check("本命排盘入口仍只收到分钟（带秒的出生时间照旧拒收）", "带了秒" in src)
    return c


def x20_prashna_dir_inert(ctx):
    c = Case("X20", "提问盘目录不干扰本命检查", "本命工作目录下放了 prashna_* 目录，check_chart 与 check_freshness 的结果不变")
    if not need_calc(ctx, c):
        return c
    d = ctx.path("x20")
    build(ctx, d, A)
    cc = [os.path.join(CALC, "check_chart.py"), "--dir", d]
    cf = [os.path.join(SHARED, "check_freshness.py"), "--dir", d]
    before = (ctx.run(cc), ctx.std(cf))
    code, out = ctx.run([os.path.join(SKILL, "prashna", "scripts", "build_prashna_data.py"),
                         "--datetime", "2026-10-11 09:30:15", "--lat", A["lat"], "--lon", A["lon"], "--tz", A["tz"],
                         "--question", "虚构测试问题", "--label", "x20", "--out-parent", d])
    sub = [x for x in os.listdir(d) if x.startswith("prashna_")]
    c.check("提问盘写进独立的 prashna_* 子目录", code == 0 and len(sub) == 1
            and os.path.exists(os.path.join(d, sub[0], "structured_prashna.md")))
    after = (ctx.run(cc), ctx.std(cf))
    c.check("check_chart 的退出码与输出不变", before[0] == after[0])
    c.check("check_freshness 的退出码与输出不变", before[1] == after[1])
    names = set(os.listdir(os.path.join(d, sub[0]))) if sub else set()
    c.check("提问盘目录里没有 chart_data.json／structured_data.md／analysis_record",
            not any(n in ("chart_data.json", "structured_data.md") or n.startswith("analysis_record") for n in names))
    return c


CASES = [t01_two_full, t02_precision15, t03_karaka, t04_pd_only, t05_bad_sign, t06_empty_claims, t07_scoring,
         t08_date_only_synastry, t09_rectified, t10_ingress, t11_grounding, t12_annual_missing, t13_legacy,
         t14_no_menu, x01_regen, x02_dasha_errors, x03_shadbala, x04_leak_and_source, x05_report,
         x06_analysis_record, x07_clock, x08_date_only_chart, x09_archive_first, x10_synastry_record,
         x11_engine_rules, x12_koota_reduction, x13_mula, x14_chara_colord, x15_inputs, x16_dst_switch,
         x17_hora, x18_small, x19_engine_seconds, x20_prashna_dir_inert, p01_prashna_standard, p02_prashna_tajika,
         b01_independent]


# ---------------------------------------------------------------- 主流程
def setup(ctx):
    ctx.results = {}
    for tag, person in (("A", A), ("B", B)):
        ctx.results[f"build_{tag}"] = build(ctx, ctx.path(tag), person)
    ctx.calc_ok = all(ctx.results[k][0] in (0, 1) and os.path.exists(ctx.path(k[-1], "chart_data.json"))
                      for k in ctx.results)
    if not ctx.calc_ok:
        ctx.calc_err = "\n".join(v[1][-400:] for v in ctx.results.values())


def report(ctx, cases, started):
    lines = ["# vedic 5.3 回归测试结果", "",
             f"- 运行时间: {started:%Y-%m-%d %H:%M}（过运快照固定 {SNAP}）",
             f"- 计算环境: {'可用' if ctx.calc_ok else '不可用 — 依赖排盘的用例记为未完成'}",
             f"- 命令: `python tests/run_tests.py --python <计算环境解释器>`",
             "- 范围: 01–14 与 X 系列验证脚本按 5.2 规则执行、错误输入被拦住，属于内部一致性，不证明数值的外部准确性。"
             "B1 用独立星历（astropy/ERFA，与 Swiss Ephemeris 无关）对照行星位置、Lagna、Ayanamsa 与 Vimsottari 日期；"
             "Shadbala、SAV/BAV、分盘、Chara Dasha 仍没有独立基准（需要 JHora 导出逐项比对）。",
             "- P1、P2 是 5.3 的提问盘（prashna）模块：P1 是上游的隔离断言与算例在本 skill 引擎上的复现，"
             "P2 是 Tajika 过程层的出版接触几何、Hāyanaratna 正例、靠近／走远对真实星历的独立复算与调度脚本。"
             "它们证明规则实现与上游冻结账本一致、几何正确；标准层规则对现实的命中率没有验证。",
             "- 文档行为类用例（11、14）只做静态检查；按文档走完整流程的独立场景试用与复核记录见 `tests/SCENARIO_TRIALS.md`。", ""]
    cnt = {PASS: 0, FAIL: 0, INC: 0}
    for c in cases:
        cnt[c.status] += 1
    lines += [f"**汇总：通过 {cnt[PASS]} · 失败 {cnt[FAIL]} · 未完成 {cnt[INC]}（共 {len(cases)} 项）**", "",
              "| # | 用例 | 预期 | 实际 | 状态 |", "|---|---|---|---|---|"]
    for c in cases:
        ok = sum(1 for _, v in c.checks if v)
        actual = c.note if c.status == INC else (f"{ok}/{len(c.checks)} 项检查成立"
                                                 + ("" if c.status == PASS else "；未成立: " + "；".join(d for d, v in c.checks if not v)))
        lines.append(f"| {c.cid} | {c.title} | {c.expected} | {actual} | {c.status} |")
    lines += ["", "## 逐项检查", ""]
    for c in cases:
        lines.append(f"### {c.cid} {c.title} — {c.status}")
        for d, v in c.checks:
            lines.append(f"- {'✔' if v else '✘'} {d}")
        if c.note and c.status != INC:
            lines.append(f"- 备注: {c.note}")
        lines.append("")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--python", default=os.environ.get("VEDIC_PY", sys.executable),
                    help="装了 pysweph + PyJHora 的解释器（默认当前解释器或环境变量 VEDIC_PY）")
    ap.add_argument("--work", default=None, help="测试工作目录（默认新建临时目录）")
    ap.add_argument("--report", default=None, help="把结果写成 Markdown（如 tests/RESULTS.md）")
    ap.add_argument("--only", default=None, help="只跑指定编号，逗号分隔，如 01,09,X3")
    a = ap.parse_args()
    work = a.work or tempfile.mkdtemp(prefix="vedic-tests-")
    if a.work and os.path.exists(work):
        shutil.rmtree(work)
    os.makedirs(work, exist_ok=True)
    ctx = Ctx(a.python, work)
    started = dt.datetime.now()
    setup(ctx)
    if not ctx.calc_ok:
        print("计算环境不可用：\n" + ctx.calc_err[-800:])
    cases = []
    only = set(a.only.split(",")) if a.only else None
    for fn in CASES:
        head = fn.__name__.split("_")[0]
        cid = head[1:] if head.startswith("t") else head[0].upper() + str(int(head[1:]))
        if only and cid not in only:
            continue
        try:
            c = fn(ctx).finish()
        except Exception as exc:  # 用例本身出错 = 失败，附原因
            c = Case(cid, fn.__name__, "—")
            c.check(f"用例执行异常: {type(exc).__name__}: {exc}", False)
            c.finish()
        cases.append(c)
        print(f"[{c.status}] {c.cid} {c.title}" + ("" if c.status == PASS else
              "  — " + (c.note or "；".join(d for d, v in c.checks if not v))))
    text = report(ctx, cases, started)
    if a.report:
        write(os.path.abspath(a.report), text)
        print(f"\n结果已写入 {a.report}")
    print(f"工作目录: {work}")
    sts = {c.status for c in cases}
    sys.exit(1 if FAIL in sts else (2 if INC in sts else 0))


if __name__ == "__main__":
    main()
