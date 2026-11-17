# -*- coding: utf-8 -*-
"""公历换算测试。装了 sxtwl（寿星天文历）时，与它全量比对；没装时只跑锚点与边界测试。"""

import random
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import ganzhi as G  # noqa: E402

try:
    import sxtwl  # noqa: F401
    HAVE_SXTWL = True
except ImportError:
    HAVE_SXTWL = False

JQ_NAMES = "冬至 小寒 大寒 立春 雨水 惊蛰 春分 清明 谷雨 立夏 小满 芒种 夏至 小暑 大暑 立秋 处暑 白露 秋分 寒露 霜降 立冬 小雪 大雪".split()


class TestAnchors(unittest.TestCase):
    def test_known_days(self):
        # 2026-10-12 己未；1984 年为甲子年
        self.assertEqual(G.day_gz_of(date(2026, 10, 12)), "己未")
        r = G.convert("1984-06-01 12:00")
        self.assertEqual(r["year"]["ganzhi"], "甲子")

    def test_wuhu_wushu(self):
        # 五虎遁：甲己之年丙作首；五鼠遁：甲己还加甲
        self.assertEqual(G.month_gz(G.STEMS.index("甲"), 0), "丙寅")
        self.assertEqual(G.month_gz(G.STEMS.index("戊"), 0), "甲寅")
        self.assertEqual(G.hour_gz(G.STEMS.index("甲"), 0), "甲子")
        self.assertEqual(G.hour_gz(G.STEMS.index("乙"), 0), "丙子")
        self.assertEqual(G.hour_gz(G.STEMS.index("己"), 4), "丙寅")

    def test_gz_index_rejects(self):
        for bad in ("甲丑", "子甲", "甲", "乙乙"):
            with self.assertRaises(G.GanzhiError):
                G.gz_index(bad)


class TestBoundaries(unittest.TestCase):
    def test_zi_hour_unconfirmed(self):
        r = G.convert("2026-10-12 23:20")
        self.assertEqual(r["day"]["status"], "unconfirmed")
        self.assertEqual(r["day"]["candidates"], ["己未", "庚申"])
        self.assertEqual(r["status"], "unconfirmed")
        self.assertEqual(r["hour"]["branch"], "子")

    def test_zi_rules(self):
        self.assertEqual(G.convert("2026-10-12 23:20", zi_rule="23")["day"]["ganzhi"], "庚申")
        self.assertEqual(G.convert("2026-10-12 23:20", zi_rule="00")["day"]["ganzhi"], "己未")
        self.assertEqual(G.convert("2026-10-12 22:59")["day"]["ganzhi"], "己未")
        self.assertEqual(G.convert("2026-10-13 00:10")["day"]["ganzhi"], "庚申")

    def test_jieqi_margin(self):
        # 2026 立春约 04:02（北京时间）
        self.assertEqual(G.convert("2026-02-04 04:30")["month"]["status"], "unconfirmed")
        self.assertEqual(G.convert("2026-02-04")["month"]["status"], "unconfirmed")      # 只给日期，当天交节
        r = G.convert("2026-02-04 06:30")
        self.assertEqual((r["month"]["ganzhi"], r["year"]["ganzhi"]), ("庚寅", "丙午"))
        r = G.convert("2026-02-04 01:30")
        self.assertEqual((r["month"]["ganzhi"], r["year"]["ganzhi"]), ("己丑", "乙巳"))
        cands = G.convert("2026-02-04 04:30")["month"]["candidates"]
        self.assertEqual(set(cands), {"己丑", "庚寅"})

    def test_hour_precision_and_tz(self):
        r = G.convert("2026-10-12 14")
        self.assertEqual(r["precision"], "hour")
        # 时辰边界都在单数整点，整小时不会跨时辰：不再给"只给到小时"的提示
        self.assertFalse(any("只给到小时" in w for w in r["warnings"]))
        self.assertEqual(r["hour"]["ganzhi"], G.convert("2026-10-12 14:59")["hour"]["ganzhi"])
        # 同一时刻在不同时区：日期跨日时日干支随钟表日期走
        a = G.convert("2026-10-12 07:00", tz_text="+08:00")
        b = G.convert("2026-10-11 23:00", tz_text="+00:00", zi_rule="00")
        self.assertEqual(a["month"]["ganzhi"], b["month"]["ganzhi"])
        self.assertEqual(a["day"]["ganzhi"], "己未")
        self.assertEqual(b["day"]["ganzhi"], "戊午")

    def test_errors(self):
        for t in ("2026-13-01", "2026-02-30", "1850-01-01", "2200-01-01", "昨天", "2026-10-12 24:30"):
            self.assertEqual(G.convert(t)["status"], "error", t)
        self.assertEqual(G.convert("2026-10-12", tz_text="北京")["status"], "error")
        self.assertEqual(G.convert("2026-10-12", zi_rule="22")["status"], "error")

    def test_expect_check(self):
        r = G.convert("2026-10-12 14:30", expect={"day": "庚寅", "month": "戌"})
        self.assertFalse(r["expect_check"]["ok"])
        self.assertEqual(len(r["expect_check"]["mismatches"]), 1)
        r = G.convert("2026-10-12 14:30", expect={"day": "己未", "month": "戊戌"})
        self.assertTrue(r["expect_check"]["ok"])


@unittest.skipUnless(HAVE_SXTWL, "没有安装 sxtwl，跳过与寿星天文历的全量比对")
class TestAgainstSxtwl(unittest.TestCase):
    def test_day_ganzhi_1900_2100(self):
        d = date(1900, 1, 1)
        end = date(2100, 12, 31)
        n = 0
        while d <= end:
            day = sxtwl.fromSolar(d.year, d.month, d.day)
            gz = G.STEMS[day.getDayGZ().tg] + G.BRANCHES[day.getDayGZ().dz]
            self.assertEqual(G.day_gz_of(d), gz, d)
            d += timedelta(days=1)
            n += 1
        self.assertGreater(n, 73000)

    def test_jie_times(self):
        """十二节时刻误差：实测最大值必须小于默认未确认带宽的一半"""
        lon = dict(G.JIE)
        worst = 0.0
        for y in range(1900, 2101):
            for j in sxtwl.getJieQiByYear(y):
                name = JQ_NAMES[j.jqIndex]
                if name not in lon:
                    continue
                mine = G.solar_term_jd(lon[name], j.jd - 8 / 24) + 8 / 24   # sxtwl 的 JD 按北京时间
                worst = max(worst, abs(mine - j.jd) * 1440)
        self.assertLess(worst, 30.0, f"节气最大误差 {worst:.1f} 分钟")
        self.__class__.worst_minutes = worst

    def test_month_year_random(self):
        rnd = random.Random(20261012)
        checked = 0
        for _ in range(4000):
            d = date(1901, 1, 1) + timedelta(days=rnd.randrange(0, 365 * 199))
            day = sxtwl.fromSolar(d.year, d.month, d.day)
            if day.hasJieQi():
                continue
            r = G.convert(f"{d.isoformat()} 12:00")
            if r["month"]["status"] != "ok":
                continue
            m = G.STEMS[day.getMonthGZ().tg] + G.BRANCHES[day.getMonthGZ().dz]
            y = G.STEMS[day.getYearGZ().tg] + G.BRANCHES[day.getYearGZ().dz]
            self.assertEqual(r["month"]["ganzhi"], m, d)
            self.assertEqual(r["year"]["ganzhi"], y, d)
            checked += 1
        self.assertGreater(checked, 3000)


class TestTimezoneAssumed(unittest.TestCase):
    """没写时区按 +08:00 算时，节气交接落在"换个时区月建就不同"的时段内要提示（00 0.2）"""

    def test_same_clock_time_differs_by_tz(self):
        # 2026 立冬 11-07 17:49（北京时间）= 09:49 UTC
        self.assertEqual(G.convert("2026-11-07 12:00", "+08:00")["month"]["branch"], "戌")
        self.assertEqual(G.convert("2026-11-07 12:00", "+00:00")["month"]["branch"], "亥")

    def test_warn_only_when_assumed_and_near(self):
        def tz_warn(r):
            return any("时区未指明" in w for w in r["warnings"])
        r = G.convert("2026-11-07 12:00", tz_assumed=True)
        self.assertTrue(tz_warn(r)); self.assertEqual(r["status"], "ok"); self.assertTrue(r["tz_assumed"])
        self.assertEqual(r["tz_note"]["jieqi"][0]["name"], "立冬")
        self.assertTrue(tz_warn(G.convert("2026-11-07 12:00", None)))            # tz_text=None 等同未指明
        self.assertFalse(tz_warn(G.convert("2026-11-07 12:00", "+08:00")))       # 写明了就不提示
        self.assertFalse(tz_warn(G.convert("2026-11-09 14:30", tz_assumed=True)))  # 离节气远
        # 窗口是不对称的：真实时刻最多比假定时刻早 6 小时、晚 20 小时
        self.assertTrue(tz_warn(G.convert("2026-11-06 23:00", zi_rule="00", tz_assumed=True)))   # 交节前约 19 小时
        self.assertFalse(tz_warn(G.convert("2026-11-06 20:00", tz_assumed=True)))  # 交节前约 22 小时
        self.assertTrue(tz_warn(G.convert("2026-11-07 23:00", zi_rule="00", tz_assumed=True)))   # 交节后约 5 小时
        self.assertFalse(tz_warn(G.convert("2026-11-08 01:00", tz_assumed=True)))  # 交节后约 7 小时

    def test_default_library_call_unchanged(self):
        r = G.convert("2026-11-07 12:00")
        self.assertFalse(r["tz_assumed"]); self.assertNotIn("tz_note", r)


if __name__ == "__main__":
    unittest.main()
