#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""selftest.py —— 排盘脚本的确定性自检。升级 lunar_python 或改动脚本后跑一遍：

    python3 scripts/selftest.py          # 全部
    python3 scripts/selftest.py -q       # 只报失败

验的是工程行为（正排与反查一致、口径有记录、输入错误不出堆栈、统计分母完整），
不是历法口径本身对不对：口径是约定，见 chart_core.py 开头。
"""
import datetime as dt
import json
import os
import random
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import chart_core as C  # noqa: E402
import check_chart as K  # noqa: E402

FAILS = []
QUIET = "-q" in sys.argv


def ok(cond, name, detail=""):
    if not cond:
        FAILS.append("%s %s" % (name, detail))
    if not QUIET or not cond:
        print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  " + str(detail)))


def run(script, *args):
    p = subprocess.run([sys.executable, os.path.join(HERE, script)] + list(args),
                       capture_output=True, text=True, env=dict(os.environ))
    return p.returncode, p.stdout, p.stderr


def P(s):
    return dt.datetime.strptime(s, "%Y-%m-%d %H:%M")


# 1. 节气边界正排（立春、惊蛰、白露两侧）
cases = [("2024-02-04 16:20", "癸卯 乙丑 戊戌 庚申"), ("2024-02-04 20:00", "甲辰 丙寅 戊戌 壬戌"),
         ("2024-03-05 08:00", "甲辰 丙寅 戊辰 丙辰"), ("2024-03-05 12:00", "甲辰 丁卯 戊辰 戊午"),
         ("2024-09-07 01:00", "甲辰 壬申 甲戌 乙丑"), ("2024-09-07 12:00", "甲辰 癸酉 甲戌 庚午"),
         ("1997-09-07 20:38", "丁丑 戊申 壬子 庚戌")]
for t, want in cases:
    got = " ".join(C.pillars_at(P(t), P(t)))
    ok(got == want, "正排 %s" % t, got)

# 2. 上面每个时刻反查回来都要落在某个候选区间里
for t, want in cases:
    cs = K.find_candidates(want.split(), 1840, 2100)
    hit = any(c["start"] <= P(t) < c["end"] for c in cs)
    ok(hit, "反查 %s" % want, [(str(c["start"]), str(c["end"])) for c in cs])

# 3. 随机抽样：正排→反查闭环（含交节前后 ±10 分钟、23 点）
rnd = random.Random(20261011)
samples = []
for _ in range(60):
    samples.append(dt.datetime(1900, 1, 1) + dt.timedelta(minutes=rnd.randrange(0, 130 * 365 * 24 * 60)))
for _ in range(30):
    t = dt.datetime(rnd.randrange(1901, 2029), rnd.randrange(1, 13), 15, 12)
    j = C.jie_around(t)["next"]["time_beijing"]
    base = P(j)
    samples += [base - dt.timedelta(minutes=10), base + dt.timedelta(minutes=10)]
for _ in range(20):
    samples.append(dt.datetime(rnd.randrange(1901, 2029), rnd.randrange(1, 13), rnd.randrange(1, 28), 23, rnd.randrange(0, 60)))
bad = []
for zd in ("23", "0"):
    for t in samples:
        ps = list(C.pillars_at(t, t, zd))
        if not C.hour_stem_ok(ps[2], ps[3], zd):
            bad.append(("遁法", zd, str(t), ps))
            continue
        cs = K.find_candidates(ps, t.year - 1, t.year + 1, zd)
        if not any(c["start"] <= t < c["end"] for c in cs):
            bad.append(("反查", zd, str(t), ps))
ok(not bad, "随机闭环 %d 个时刻×两种换日口径" % len(samples), bad[:5])

# 4. 同一候选联合满足：生年由 1877 候选满足、起运由 1997 候选满足，不能算通过
r = K.check("丁丑 戊申 壬子 庚戌", "male", qiyun=10, born=1877)
ok(r["verdict"] == "与所称信息不符", "联合约束不拆开通过", r["verdict"])
r = K.check("丁丑 戊申 壬子 庚戌", "male", qiyun=10, born=1997)
ok(r["verdict"] == "通过" and len(r["matched"]) == 1, "联合约束正常通过", r["verdict"])

# 5. 范围语义
r = K.check("甲子 丙寅 戊戌 壬戌", lo=2020, hi=2030)
ok(r["verdict"] == "范围内未找到" and "不等于历法上绝对不存在" in r["problems"][-1], "范围内未找到的措辞", r["problems"])

# 6. 晚子时提示
r = K.check("戊午 甲子 庚戌 戊子")
ok(r["verdict"] == "遁法不符" and r.get("ziday_hint") == "0", "晚子时口径提示", r["problems"])
ok(K.check("戊午 甲子 庚戌 戊子", ziday="0")["verdict"] == "通过", "晚子时口径下通过")

# 7. 时间口径
tr = C.resolve_time("1997-09-07 20:38", lon=106.08)
ok(tr["main"]["local"].strftime("%H:%M") == "19:42", "经度时差修正", tr["main"]["local"])
tr = C.resolve_time("1997-09-07 19:42", basis="mean-solar", lon=106.08)
ok(tr["main"]["local"].strftime("%H:%M") == "19:42" and abs((tr["main"]["beijing"] - P("1997-09-07 20:38")).total_seconds()) < 60,
   "已校正时间不重复校正", (tr["main"]["local"], tr["main"]["beijing"]))
tr = C.resolve_time("1990-05-01 09:00", tz="America/New_York")
ok(tr["main"]["beijing"].strftime("%m-%d %H:%M") == "05-01 21:00", "时区库换算（纽约夏令时）", tr["main"]["beijing"])
tr = C.resolve_time("1988-06-01 12:00")
ok(any("夏令时" in v["label"] for v in tr["variants"]), "中国夏令时期间给候选", [v["label"] for v in tr["variants"]])
for day, want, tol in ((dt.datetime(2021, 11, 3, 12), 16.4, 0.8), (dt.datetime(2021, 2, 11, 12), -14.2, 0.8),
                       (dt.datetime(2021, 7, 26, 12), -6.5, 0.8)):
    e = C.eot_minutes(day)
    ok(abs(e - want) <= tol, "均时差 %s" % day.date(), round(e, 2))

# 8. 农历闰月
try:
    C.resolve_time("2023-02-10 08:00", calendar="lunar")
    ok(False, "闰月未说明应要求补参数")
except C.NeedsChoice as e:
    ok([o["solar"] for o in e.options] == ["2023-03-01", "2023-03-31"], "闰月候选", e.options)
tr = C.resolve_time("2023-02-10 08:00", calendar="lunar", leap=True)
ok(tr["main"]["local"].strftime("%Y-%m-%d") == "2023-03-31", "闰月换算")

# 9. CLI：输入错误不出堆栈、退出码
for args in (["--date", "1997-13-01 10:00"], ["--date", "1997-09-07 20:38", "--gender", "x"],
             ["--pillars", "甲丑 丙寅 戊戌 壬戌"], ["--date", "1997-09-07 20:38", "--eot"],
             ["--date", "1997-09-07 20:38", "--lon", "200"]):
    code, out, err = run("paipan.py", *args)
    ok(code == 2 and "Traceback" not in out + err, "paipan 输入错误 %s" % " ".join(args), (code, err[-200:]))
code, out, err = run("paipan.py", "--date", "1997-09-07 20:38", "--json")
j = json.loads(out)
ok(code == 0 and j["params"]["性别"]["value"] == "未提供" and len(j["yun"]) == 2, "不给性别不默认男", j["params"].get("性别"))
code, out, err = run("paipan.py", "--date", "1997-09-05", "--gender", "male", "--json")
j = json.loads(out)
ok(code == 0 and j["status"] == "部分完成" and "start_range" in j["yun"][0], "只给日期：部分完成+起运区间", j["status"])
code, out, err = run("paipan.py", "--date", "1997-09-07", "--gender", "male", "--json")
j = json.loads(out)
ok(code == 0 and j["status"] == "候选并行" and len(j["candidates"]) == 2, "只给日期且当天交节：候选并行", j["status"])
ok(code == 0 and len(j["yun"]) == 2 and {y["candidate"] for y in j["yun"]} == {"交节前", "交节后"}, "交节日只给日期：大运按候选分开", [y.get("candidate") for y in j["yun"]])
code, out, err = run("paipan.py", "--date", "1988-07-01 13:30", "--tz", "Asia/Shanghai", "--json")
j = json.loads(out)
ok(code == 0 and j["status"] == "候选并行" and any("标准时" in l for c in j["candidates"] for l in c["labels"]), "时区名下夏令时也列候选", j["status"])
code, out, err = run("paipan.py", "--date", "2024-02-04 16:20", "--gender", "male", "--uncertainty", "15", "--json")
j = json.loads(out)
ok(len(j["yun"]) == 2 and j["yun"][0]["forward"] != j["yun"][1]["forward"], "年柱候选不同：大运按候选分开", [y.get("candidate") for y in j["yun"]])
code, out, err = run("paipan.py", "--date", "2023-02-10 08:00", "--lunar")
ok(code == 2 and "闰" in out, "paipan 闰月要求补参数", out[:80])
code, out, err = run("paipan.py", "--pillars", "丁丑 戊申 壬子 庚戌", "--json")
j = json.loads(out)
types = {(x["type"], x["adopted"]) for x in j["facts"]["relations"]}
ok(("刑（丑戌未两字）", True) in types and ("六合", True) in types, "关系扫描带采用状态", types)
ok(any("驿马" in x and "时戌" in x for x in j["facts"]["shensha"]["duan"]), "驿马按宽口径（日支子见时戌）", j["facts"]["shensha"])
ok(not any("聪明" in s or "表象" in s for s in json.dumps(j, ensure_ascii=False).split(",")), "计算输出不含解读语")
for args, want in ((["--pillars", "甲辰 丙寅"], 2), (["--pillars", "甲丑 丙寅 戊戌 壬戌"], 1),
                   (["--pillars", "甲辰 丙寅 戊戌 壬戌"], 0), (["--batch", "/nonexistent"], 2)):
    code, out, err = run("check_chart.py", *args)
    ok(code == want and "Traceback" not in out + err, "check_chart 退出码 %s" % " ".join(args), (code, err[-200:]))

# 10. 批量统计：每行都进分母
import tempfile
with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf8") as f:
    f.write("# c\n甲辰 丙寅 戊戌 壬戌,男,9,2024\n甲辰 丙寅,男\n甲丑 丙寅 戊戌 壬戌\n甲辰 丙寅 戊戌 壬戌,x\n\n戊午 甲子 庚戌 戊子\n")
    path = f.name
b = K.run_batch(path, None, None)
ok(b["total"] == 5 and sum(b["stat"].values()) == 5 and b["stat"]["通过"] == 1 and b["stat"]["遁法不符"] == 1
   and b["stat"]["结构非法"] == 1 and b["stat"]["输入缺失或无法检查"] == 2, "批量分类与分母", b["stat"])
ok(all("line" in r for r in b["rows"]), "批量逐行带行号")
ok(b["extra"].get("ziday_hint") == {"0": 1}, "批量统计换口径即合的盘数", b["extra"])
code, out, err = run("check_chart.py", "--batch", path)
ok("构造" not in out and "真盘" not in out, "批量不做真假人推论")
os.unlink(path)

print("\n%d 项失败" % len(FAILS) if FAILS else "\n全部通过")
sys.exit(1 if FAILS else 0)
