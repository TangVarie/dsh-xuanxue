# -*- coding: utf-8 -*-
"""排盘计算测试：六十四卦、动爻组合、世应、六亲、伏神、旬空、六神与明显边界。

两类检查：
1. 自洽：八宫表（14 第三节）与"八宫生成法""世应口诀""寻宫歌"三种独立推法互相核对；
2. 对照原书：13 卦例集里写明了卦、爻支、六亲、世应、六神、旬空的例子，逐项比对。
"""

import itertools
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import paipan as P  # noqa: E402
import ganzhi as G  # noqa: E402


def flip(bits, positions):
    return tuple((1 - b) if (i + 1) in positions else b for i, b in enumerate(bits))


class TestPalaceTable(unittest.TestCase):
    def test_64_unique(self):
        self.assertEqual(len(P.GUA), 64)
        self.assertEqual(len({v["name"] for v in P.GUA.values()}), 64)

    def test_palace_generation(self):
        """八宫生成法：本宫→逐爻变至五世→游魂（四爻变回）→归魂（内卦复本宫）"""
        for palace, tri in P.TRIGRAMS.items():
            pure = tri + tri
            seq = [pure] + [flip(pure, range(1, k + 1)) for k in range(1, 6)]
            youhun = flip(seq[5], {4})
            guihun = tri + youhun[3:]
            seq += [youhun, guihun]
            for k, bits in enumerate(seq):
                info = P.GUA[bits]
                self.assertEqual(info["palace"], palace, info["name"])
                self.assertEqual(info["type"], P.GUA_TYPES[k], info["name"])

    def test_shi_by_rhyme(self):
        """世应口诀：天同二世天变五，地同四世地变初，本宫六世三世异，人同游魂人变归"""
        for bits, info in P.GUA.items():
            lo, up = bits[:3], bits[3:]
            di, ren, tian = lo[0] == up[0], lo[1] == up[1], lo[2] == up[2]
            same = (di, ren, tian)
            expect = {
                (True, True, True): 6, (False, False, False): 3,
                (False, False, True): 2, (True, True, False): 5,
                (True, False, False): 4, (False, True, True): 1,
                (False, True, False): 4, (True, False, True): 3,
            }[same]
            self.assertEqual(info["shi"], expect, info["name"])
            if same == (False, True, False):
                self.assertEqual(info["type"], "游魂", info["name"])
            if same == (True, False, True):
                self.assertEqual(info["type"], "归魂", info["name"])

    def test_palace_by_song(self):
        """寻宫歌：一二三六外卦宫，四五游魂内变更，归魂内卦是本宫"""
        inv = lambda t: tuple(1 - x for x in t)  # noqa: E731
        for bits, info in P.GUA.items():
            lo, up = bits[:3], bits[3:]
            t = info["type"]
            if t in ("本宫", "一世", "二世", "三世"):
                expect = P.TRIGRAM_BY_BITS[up]
            elif t in ("四世", "五世", "游魂"):
                expect = P.TRIGRAM_BY_BITS[inv(lo)]
            else:
                expect = P.TRIGRAM_BY_BITS[lo]
            self.assertEqual(info["palace"], expect, info["name"])

    def test_ying(self):
        for info in P.GUA.values():
            self.assertEqual(abs(info["shi"] - info["ying"]), 3)

    def test_liuchong_liuhe(self):
        ch = {i["name"] for b, i in P.GUA.items() if P.is_liuchong(b)}
        he = {i["name"] for b, i in P.GUA.items() if P.is_liuhe(b)}
        self.assertEqual(ch, {"乾为天", "坎为水", "艮为山", "震为雷", "巽为风", "离为火", "坤为地", "兑为泽",
                              "天雷无妄", "雷天大壮"})
        self.assertEqual(he, {"天地否", "地天泰", "雷地豫", "地雷复", "水泽节", "泽水困", "火山旅", "山火贲"})

    def test_najia_pure(self):
        """纯卦纳支 = 内卦纳支 + 外卦纳支（14 第二节）"""
        for tri, (inner, outer) in P.NAJIA_BRANCH.items():
            got = "".join(b for _, b in P.najia_lines(P.TRIGRAMS[tri] * 2))
            self.assertEqual(got, inner + outer, tri)

    def test_name_lookup(self):
        self.assertEqual(P.GUA[P.lookup_gua("同人")]["name"], "天火同人")
        self.assertEqual(P.GUA[P.lookup_gua("乾")]["name"], "乾为天")
        self.assertEqual(P.GUA[P.lookup_gua("天山遯")]["name"], "天山遁")
        with self.assertRaises(P.PaipanError):
            P.lookup_gua("天天天")


class TestAllCombos(unittest.TestCase):
    def test_4096_line_combos(self):
        """4^6 种爻值组合全部能装，变卦、变爻纳支、六亲、伏神自洽"""
        for vals in itertools.product((6, 7, 8, 9), repeat=6):
            c = P.analyze(list(vals), None, None)
            bits = tuple(1 if v in (7, 9) else 0 for v in vals)
            moving = [i + 1 for i, v in enumerate(vals) if v in (6, 9)]
            self.assertEqual(c["moving"], moving)
            if moving:
                bb = flip(bits, set(moving))
                self.assertEqual(c["bian"]["name"], P.GUA[bb]["name"])
                bnj = P.najia_lines(bb)
                for p in moving:
                    ch = c["lines"][p - 1]["change"]
                    self.assertEqual(ch["branch"], bnj[p - 1][1])
                    self.assertEqual(ch["liuqin"], P.liuqin_of(c["ben"]["palace_element"], ch["branch"]))
            else:
                self.assertIsNone(c["bian"])
            covered = {ln["liuqin"] for ln in c["lines"]} | {f["liuqin"] for f in c["fushen"]}
            self.assertEqual(covered, set(P.LIUQIN))
            for f in c["fushen"]:
                self.assertNotIn(f["liuqin"], {ln["liuqin"] for ln in c["lines"]})

    def test_fuyin_only_qian_zhen(self):
        """纳甲下爻变伏吟只出现在乾↔震互变（05 六）；反吟按动变相冲机械判"""
        for vals in itertools.product((6, 7, 8, 9), repeat=6):
            c = P.analyze(list(vals), None, None)
            for t in c["triggers"]:
                if t["name"] == "伏吟":
                    b, v = c["ben"], c["bian"]
                    pair = {(b["lower"], v["lower"]), (b["upper"], v["upper"])}
                    self.assertTrue(any(set(x) == {"乾", "震"} for x in pair), (b["name"], v["name"]))
                if t["name"] == "爻变反吟":
                    self.assertIn("化", t["where"])


class TestXunkongShen(unittest.TestCase):
    def test_xunkong_two_methods(self):
        """14 第六节两法互核：地支序 − 天干序；六甲旬"""
        table = {"甲子": "戌亥", "甲戌": "申酉", "甲申": "午未", "甲午": "辰巳", "甲辰": "寅卯", "甲寅": "子丑"}
        res = {2: "子丑", 4: "寅卯", 6: "辰巳", 8: "午未", 10: "申酉", 0: "戌亥"}
        for i in range(60):
            gz = G.gz_name(i)
            d = (G.BRANCHES.index(gz[1]) + 1 - (G.STEMS.index(gz[0]) + 1)) % 12
            self.assertEqual(G.xunkong(gz), res[d], gz)
            head = G.gz_name(i - i % 10)
            self.assertEqual(G.xunkong(gz), table[head], gz)

    def test_six_gods_start(self):
        expect = {"甲": "青龙", "乙": "青龙", "丙": "朱雀", "丁": "朱雀", "戊": "勾陈", "己": "腾蛇",
                  "庚": "白虎", "辛": "白虎", "壬": "玄武", "癸": "玄武"}
        for stem, god in expect.items():
            day = next(G.gz_name(i) for i in range(60) if G.gz_name(i)[0] == stem)
            c = P.analyze([7] * 6, "子", day)
            self.assertEqual(c["lines"][0]["god"], god)
            self.assertEqual([ln["god"] for ln in c["lines"]][1], P.SIX_GODS[(P.SIX_GODS.index(god) + 1) % 6])

    def test_wangshuai(self):
        self.assertEqual(P.wangshuai("寅", "卯"), "旺")
        self.assertEqual(P.wangshuai("寅", "午"), "相")
        self.assertEqual(P.wangshuai("寅", "子"), "休")
        self.assertEqual(P.wangshuai("寅", "申"), "囚")
        self.assertEqual(P.wangshuai("寅", "辰"), "死")


def L(c, pos):
    return c["lines"][pos - 1]


def names(c):
    return {t["name"] for t in c["triggers"]}


class TestSourceCases(unittest.TestCase):
    """13 卦例集与 14 示范里写明的盘面事实"""

    def test_demo_a(self):  # 14 示范A 乾为天 庚寅日
        c = P.analyze(P.lines_from_gua("乾为天"), None, "庚寅")
        self.assertEqual([ln["branch"] for ln in c["lines"]], list("子寅辰午申戌"))
        self.assertEqual([ln["liuqin"] for ln in c["lines"]], ["子孙", "妻财", "父母", "官鬼", "兄弟", "父母"])
        self.assertEqual([ln["god"] for ln in c["lines"]], ["白虎", "玄武", "青龙", "朱雀", "勾陈", "腾蛇"])
        self.assertEqual((c["ben"]["shi"], c["ben"]["ying"]), (6, 3))
        self.assertEqual(c["xunkong"], "午未")

    def test_demo_b(self):  # 14 示范B 泽火革 六二动（老阴）
        c = P.analyze(P.lines_from_gua("泽火革", [2]), None, "庚寅")
        self.assertEqual(c["lines"][1]["value"], 6)
        self.assertEqual(c["lines"][1]["symbol"], "×")
        self.assertEqual(c["bian"]["name"], "泽天夬")
        self.assertEqual(c["lines"][1]["change"]["branch"], "寅")
        self.assertEqual(c["lines"][1]["change"]["liuqin"], "子孙")
        self.assertEqual((c["ben"]["palace"], c["ben"]["shi"], c["ben"]["ying"]), ("坎", 4, 1))
        self.assertEqual([(f["pos"], f["branch"], f["liuqin"]) for f in c["fushen"]], [(3, "午", "妻财")])
        self.assertEqual(c["fushen"][0]["fly_to_fu"], "飞克伏")
        self.assertTrue(c["fushen"][0]["kong"])

    def test_case1(self):  # 例1 地泽临之地水师 寅月乙酉日
        c = P.analyze(P.lines_from_gua("地泽临", to="地水师"), "寅", "乙酉")
        self.assertEqual((L(c, 2)["branch"], L(c, 2)["liuqin"], L(c, 2)["shiying"]), ("卯", "官鬼", "世"))
        self.assertEqual((L(c, 5)["branch"], L(c, 5)["liuqin"], L(c, 5)["shiying"]), ("亥", "妻财", "应"))
        self.assertIn("冲", L(c, 2)["day_rel"])      # 酉日冲卯

    def test_case2(self):  # 例2 火雷噬嗑之震为雷 寅月庚寅日：世未土旬空
        c = P.analyze(P.lines_from_gua("火雷噬嗑", to="震为雷"), "寅", "庚寅")
        shi = L(c, c["ben"]["shi"])
        self.assertEqual((shi["branch"], shi["kong"]), ("未", True))

    def test_case3(self):  # 例3 天火同人之风雷益 丑月辛亥日：日建化坏
        c = P.analyze(P.lines_from_gua("天火同人", to="风雷益"), "丑", "辛亥")
        shi = L(c, 3)
        self.assertEqual((shi["branch"], shi["liuqin"], shi["shiying"]), ("亥", "官鬼", "世"))
        self.assertEqual(shi["change"]["branch"], "辰")
        self.assertTrue({"日建化坏", "化墓", "回头克"} <= names(c))
        self.assertEqual((L(c, 6)["branch"], L(c, 6)["shiying"]), ("戌", "应"))

    def test_case5(self):  # 例5 雷天大壮之火天大有 亥月辛酉日
        c = P.analyze(P.lines_from_gua("雷天大壮", to="火天大有"), "亥", "辛酉")
        self.assertEqual((L(c, 6)["branch"], L(c, 6)["liuqin"]), ("戌", "兄弟"))
        self.assertEqual((L(c, 5)["branch"], L(c, 5)["liuqin"]), ("申", "子孙"))
        self.assertEqual((L(c, 1)["branch"], L(c, 1)["liuqin"], L(c, 1)["shiying"]), ("子", "妻财", "应"))
        ch = L(c, 6)["change"]
        self.assertEqual(ch["branch"], "巳")
        self.assertIn("冲", ch["month_rel"])           # 化巳火月破

    def test_case6(self):  # 例6 地山谦之水山蹇 申月甲辰日
        c = P.analyze(P.lines_from_gua("地山谦", to="水山蹇"), "申", "甲辰")
        shi = L(c, 5)
        self.assertEqual((shi["branch"], shi["liuqin"], shi["shiying"]), ("亥", "子孙", "世"))
        self.assertIn("墓", shi["day_rel"])            # 入日库辰
        self.assertEqual(shi["change"]["branch"], "戌")
        self.assertIn("回头克", names(c))
        self.assertEqual([(f["pos"], f["branch"], f["liuqin"]) for f in c["fushen"]], [(2, "卯", "妻财")])
        self.assertEqual(L(c, 2)["liuqin"], "官鬼")     # 卯财伏官午下

    def test_case8(self):  # 例8 山火贲之风火家人 子月甲辰日
        c = P.analyze(P.lines_from_gua("山火贲", to="风火家人"), "子", "甲辰")
        shi = L(c, 1)
        self.assertEqual((shi["branch"], shi["shiying"], shi["kong"]), ("卯", "世", True))
        self.assertEqual((L(c, 5)["branch"], L(c, 5)["liuqin"]), ("子", "妻财"))
        self.assertIn("墓", L(c, 5)["day_rel"])         # 财子水入日墓

    def test_case10(self):  # 例10 天风姤之兑为泽 子月己巳日
        c = P.analyze(P.lines_from_gua("天风姤", to="兑为泽"), "子", "己巳")
        self.assertEqual([(f["pos"], f["branch"], f["liuqin"]) for f in c["fushen"]], [(2, "寅", "妻财")])
        self.assertEqual((L(c, 2)["branch"], L(c, 2)["liuqin"]), ("亥", "子孙"))
        self.assertIn("冲", L(c, 2)["day_rel"])         # 亥逢日冲

    def test_case12(self):  # 例12 风火家人之水火既济 辰月己未日
        c = P.analyze(P.lines_from_gua("风火家人", to="水火既济"), "辰", "己未")
        self.assertEqual(c["moving"], [6])
        self.assertIn("独发", names(c))
        top = L(c, 6)
        self.assertEqual((top["branch"], top["liuqin"], top["god"]), ("卯", "兄弟", "勾陈"))
        self.assertIn("墓", top["day_rel"])             # 入日墓
        self.assertIn("回头生", names(c))
        self.assertEqual((L(c, 2)["shiying"], L(c, 2)["god"]), ("世", "白虎"))
        self.assertEqual((L(c, 5)["shiying"], L(c, 5)["god"]), ("应", "朱雀"))


class TestCanonicalExamples(unittest.TestCase):
    """24 规范示例里的卦盘必须与脚本一致"""

    def test_example_one(self):
        c = P.analyze(P.parse_lines("878978"), "亥", "丁亥")
        self.assertEqual((c["ben"]["name"], c["bian"]["name"]), ("泽水困", "坎为水"))
        self.assertEqual((c["ben"]["palace"], c["ben"]["type"], c["ben"]["shi"], c["ben"]["ying"]), ("兑", "一世", 1, 4))
        self.assertEqual([ln["branch"] + ln["liuqin"] for ln in c["lines"]],
                         ["寅妻财", "辰父母", "午官鬼", "亥子孙", "酉兄弟", "未父母"])
        self.assertEqual([ln["god"] for ln in c["lines"]], ["朱雀", "勾陈", "腾蛇", "白虎", "玄武", "青龙"])
        self.assertEqual(c["xunkong"], "午未")
        self.assertEqual(c["lines"][3]["change"]["branch"] + c["lines"][3]["change"]["liuqin"], "申兄弟")
        self.assertTrue({"六合卦", "合变冲", "回头生", "独发"} <= names(c))

    def test_example_three_revision(self):
        c = P.analyze(P.parse_lines("878978"), "亥", "戊子")
        self.assertEqual([ln["god"] for ln in c["lines"]], ["勾陈", "腾蛇", "白虎", "玄武", "青龙", "朱雀"])
        self.assertEqual(c["xunkong"], "午未")
        self.assertIn("冲", c["lines"][2]["day_rel"])          # 子冲午
        self.assertEqual(G.day_gz_of(G.date(2026, 11, 18)), "丙申")
        self.assertEqual(G.day_gz_of(G.date(2026, 11, 12)), "庚寅")


class TestInputsAndVerify(unittest.TestCase):
    def test_parse_lines(self):
        self.assertEqual(P.parse_lines("787896"), [7, 8, 7, 8, 9, 6])
        self.assertEqual(P.parse_lines("7,8,7,8,9,6"), [7, 8, 7, 8, 9, 6])
        self.assertEqual(P.parse_lines("／ ／／ ○ × ／ ／"), [7, 8, 9, 6, 7, 7])
        for bad in ("78789", "7878966", "787895", "", "a b c d e f"):
            with self.assertRaises(P.PaipanError):
                P.parse_lines(bad)

    def test_coins_need_rule(self):
        with self.assertRaises(P.PaipanError):
            P.parse_coins("字背背,字字背,字字字,背背背,字背背,字背背", None)
        a = P.parse_coins("字背背,字字背,字字字,背背背,字背背,字背背", "本包")
        b = P.parse_coins("字背背,字字背,字字字,背背背,字背背,字背背", "背为阳")
        self.assertEqual(a, [7, 8, 9, 6, 7, 7])
        self.assertEqual(b, [8, 7, 6, 9, 8, 8])     # 两种约定正好阴阳互换

    def test_gua_moving_conflict(self):
        with self.assertRaises(P.PaipanError):
            P.lines_from_gua("天火同人", [1], "风雷益")
        self.assertEqual(P.lines_from_gua("天火同人", [3, 4], "风雷益"), P.lines_from_gua("天火同人", to="风雷益"))
        with self.assertRaises(P.PaipanError):
            P.lines_from_gua("天火同人", [7])

    def _verify(self, data):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)
        return P.verify(json.loads(Path(fh.name).read_text(encoding="utf-8")))

    def test_verify_god_mismatch_and_unconfirmed(self):
        yao = [{"阴阳": "阳", "动": False, "地支": "卯", "六亲": "子孙", "六神": "白虎", "世应": "应"},
               {"阴阳": "阴", "动": True, "地支": "丑", "六亲": "官鬼", "六神": "玄武", "世应": ""},
               {"阴阳": "阳", "动": False, "地支": "亥", "六亲": "兄弟", "六神": None, "世应": ""},
               {"阴阳": "阳", "动": False, "地支": "亥", "六亲": "兄弟", "六神": "朱雀", "世应": "世"},
               {"阴阳": "阳", "动": False, "地支": "酉", "六亲": "父母", "六神": "勾陈", "世应": ""},
               {"阴阳": "阴", "动": False, "地支": "未", "六亲": "官鬼", "六神": "白虎", "世应": ""}]
        r = self._verify({"本卦": "泽火革", "变卦": "泽天夬", "月建": "申", "日辰": "庚寅", "旬空": "午未", "爻": yao})
        self.assertEqual(r["status"], "diff")
        self.assertEqual([d["field"] for d in r["diffs"]], ["上爻六神"])
        self.assertIn("三爻六神", r["unconfirmed"])          # 读不清的不补齐
        self.assertIsNone(yao[2]["六神"])

    def test_verify_input_conflict(self):
        yao = [{"阴阳": "阳", "动": False}] * 6               # 爻象是乾为天
        r = self._verify({"本卦": "坤为地", "日辰": "庚寅", "月建": "申", "爻": yao})
        self.assertTrue(any(d["kind"] == "输入" and d["field"] == "卦形" for d in r["diffs"]))

    def test_verify_cannot_determine(self):
        yao = [{"阴阳": "阳", "动": None}] + [{"阴阳": "阴", "动": False}] * 5
        r = self._verify({"爻": yao})
        self.assertEqual(r["status"], "unconfirmed")

    def test_date_variants(self):
        ns = P.argparse.Namespace(verify=None, lines="787896", coins=None, coin_rule=None, gua=None, moving=None,
                                  to=None, month=None, day=None, date="2026-10-12 23:20", tz="+08:00",
                                  zi_rule=None, yongshen=None)
        r = P.run(ns)
        self.assertEqual(r["status"], "unconfirmed")
        self.assertEqual({v["day"] for v in r["variants"]}, {"己未", "庚申"})

    def test_no_date_degrades(self):
        ns = P.argparse.Namespace(verify=None, lines="787896", coins=None, coin_rule=None, gua=None, moving=None,
                                  to=None, month=None, day=None, date=None, tz="+08:00", zi_rule=None, yongshen=None)
        r = P.run(ns)
        self.assertEqual(r["status"], "unconfirmed")
        self.assertIsNone(r["chart"]["xunkong"])
        self.assertTrue(all(ln["god"] is None and ln["kong"] is None for ln in r["chart"]["lines"]))
        self.assertIn("暂不能断", r["text"])

    def test_yongshen_two_and_hidden(self):
        c = P.analyze(P.lines_from_gua("乾为天"), "申", "庚寅", yongshen="父母")
        self.assertIn("用神两现", names(c))
        c = P.analyze(P.lines_from_gua("泽火革"), "申", "庚寅", yongshen="妻财")
        self.assertIn("用神不上卦", names(c))

    def test_tu_not_mu(self):
        """土爻化辰戌丑未不报化墓（11 R10）"""
        for vals in itertools.product((6, 7, 8, 9), repeat=6):
            c = P.analyze(list(vals), None, None)
            for t in c["triggers"]:
                if t["name"] == "化墓":
                    self.assertNotEqual(t["where"].split(" ")[1][1], "土", t["where"])


def trig(c, name):
    return [t for t in c["triggers"] if t["name"] == name]


class TestLineRelations(unittest.TestCase):
    """爻与爻之间：论冲成立、两动相合、静爻逢动爻为墓（20 一；11 R29）"""

    def test_moving_clashes_static(self):
        # 乾之姤：初爻子水动，四爻午火静，子午相冲
        c = P.analyze(P.lines_from_gua("乾为天", to="天风姤"), "卯", "甲寅")
        t = trig(c, "论冲成立（动爻冲静爻）")
        self.assertEqual(len(t), 1)
        self.assertTrue(t[0]["where"].startswith("初九 子水"))
        self.assertIn("九四 午火", t[0]["where"])
        self.assertEqual(t[0]["step"], 4)

    def test_static_hexagram_has_no_line_clash(self):
        # 六爻俱静的六冲卦只有冲象（04 二）
        for name in ("乾为天", "天雷无妄", "坤为地"):
            c = P.analyze(P.lines_from_gua(name), "卯", "甲寅")
            self.assertFalse([t for t in c["triggers"] if t["name"].startswith("论冲成立")], name)

    def test_two_moving_clash_and_combine(self):
        c = P.analyze(P.lines_from_gua("乾为天", [1, 4]), None, None)       # 子、午皆动
        self.assertEqual(len(trig(c, "论冲成立（两动相冲）")), 1)
        c = P.analyze(P.lines_from_gua("地天泰", [1, 4]), None, None)       # 子、丑皆动相合
        self.assertEqual(len(trig(c, "爻间六合（两动相合）")), 1)
        c = P.analyze(P.lines_from_gua("地天泰", [1]), None, None)          # 一动一静只论合象，不列
        self.assertEqual(trig(c, "爻间六合（两动相合）"), [])

    def test_every_pair_reported_exactly_when_rule_says(self):
        for vals in itertools.product((6, 7, 8, 9), repeat=6):
            c = P.analyze(list(vals), None, None)
            L = c["lines"]
            want_c = sum(1 for i in range(6) for j in range(i + 1, 6)
                         if P.chong(L[i]["branch"], L[j]["branch"]) and (L[i]["moving"] or L[j]["moving"]))
            want_h = sum(1 for i in range(6) for j in range(i + 1, 6)
                         if P.he(L[i]["branch"], L[j]["branch"]) and L[i]["moving"] and L[j]["moving"])
            want_m = sum(1 for a in L for b in L
                         if not a["moving"] and b["moving"] and P.MU.get(a["element"]) == b["branch"])
            got_c = sum(1 for t in c["triggers"] if t["name"].startswith("论冲成立"))
            self.assertEqual((got_c, len(trig(c, "爻间六合（两动相合）")), len(trig(c, "静爻逢动爻为墓"))),
                             (want_c, want_h, want_m), vals)

    def test_static_meets_moving_tomb(self):
        # 天火同人上爻戌土动：戌是火墓，四爻午火静
        c = P.analyze(P.lines_from_gua("天火同人", [6]), "申", "庚寅")
        t = trig(c, "静爻逢动爻为墓")
        self.assertEqual(len(t), 1)
        self.assertIn("九四 午火", t[0]["where"]); self.assertIn("R29", t[0]["detail"]); self.assertEqual(t[0]["kind"], "前提")
        # 土爻不论入墓（R10）：没有"土爻逢动爻为墓"
        for vals in itertools.product((7, 8, 9), repeat=6):
            for t in trig(P.analyze(list(vals), None, None), "静爻逢动爻为墓"):
                self.assertNotIn("土", t["where"].split(" ← ")[0])


class TestEarthMonthClash(unittest.TestCase):
    """土爻逢土月冲（11 R27）与月冲值日之爻（11 R07）"""

    def test_earth_line_broken_by_earth_month(self):
        c = P.analyze(P.lines_from_gua("乾为天"), "辰", "乙卯")     # 上九戌土，辰月冲
        top = c["lines"][5]
        self.assertEqual(top["month_state"], "旺")                 # 事实层不改
        t = trig(c, "月破")
        self.assertEqual(len(t), 1); self.assertIn("R27", t[0]["detail"]); self.assertEqual(t[0]["kind"], "触发")
        # 月破又逢日克：不是"一生一克"
        self.assertFalse([x for x in trig(c, "日月一生一克") if "戌土" in x["where"]])
        text = P.render(c)
        self.assertIn("月破", text); self.assertIn("旺不作有气依据", text)

    def test_earth_month_clash_plus_day_support_is_mixed(self):
        c = P.analyze(P.lines_from_gua("乾为天"), "辰", "甲午")     # 月破而日生
        self.assertTrue([x for x in trig(c, "日月一生一克") if "戌土" in x["where"]])

    def test_non_earth_month_break_has_no_r27_note(self):
        c = P.analyze(P.lines_from_gua("乾为天"), "午", "乙卯")     # 初九子水，午月冲
        t = trig(c, "月破")
        self.assertEqual(len(t), 1); self.assertNotIn("R27", t[0]["detail"])

    def test_month_clash_on_day_valued_line(self):
        c = P.analyze(P.lines_from_gua("乾为天"), "辰", "甲戌")     # 戌值日而逢辰月冲
        self.assertEqual(trig(c, "月破"), [])
        t = trig(c, "月冲值日之爻")
        self.assertEqual(len(t), 1); self.assertIn("R07", t[0]["detail"]); self.assertEqual(t[0]["kind"], "前提")
        self.assertIn("月冲值日", P.render(c))

    def test_void_and_day_clash_use_month_break(self):
        c = P.analyze(P.lines_from_gua("乾为天"), "辰", "甲子")     # 甲子旬空戌亥：戌土旬空又月破
        t = trig(c, "旬空")
        self.assertTrue(any("戌土" in x["where"] and "（月破" in x["detail"] for x in t))
        c = P.analyze(P.lines_from_gua("乾为天"), "戌", "甲辰")     # 辰值日逢戌月冲 → R07；戌值月逢辰日冲
        self.assertEqual(len(trig(c, "月冲值日之爻")), 1)
        d = [x for x in trig(c, "日冲静爻") if "戌土" in x["where"]]
        self.assertTrue(d and "倾向暗动" in d[0]["detail"])


class TestRobustInput(unittest.TestCase):
    def test_parse_moving(self):
        self.assertEqual(P.parse_moving("3"), [3])
        self.assertEqual(P.parse_moving("3,5"), [3, 5])
        self.assertEqual(P.parse_moving("三"), [3])
        self.assertEqual(P.parse_moving("初、上爻"), [1, 6])
        self.assertIsNone(P.parse_moving(None))
        with self.assertRaises(P.PaipanError):
            P.parse_moving("第七")
        self.assertEqual(P.main(["--gua", "同人", "--moving", "甲"]), 2)      # 明确失败，不抛 Python 异常

    def test_verify_bad_shapes_are_explained(self):
        for bad in (["阴"] * 6, [{"阴阳": "阴", "动": "否"}] * 6, [{"阴阳": "少阴", "动": False}] * 6, [None] * 5):
            with self.assertRaises(P.PaipanError):
                P.verify({"本卦": "泽水困", "爻": bad})
        with self.assertRaises(P.PaipanError):
            P.verify(["泽水困"])
        with self.assertRaises(P.PaipanError):
            P.verify({"本卦": "泽水困", "伏神": "无"})

    def test_verify_misread_bian_name_is_a_diff_not_abort(self):
        yao = [{"阴阳": a, "动": m} for a, m in zip("阴阳阴阳阳阴", (False, False, False, True, False, False))]
        r = P.verify({"本卦": "泽水困", "变卦": "坎为谁", "月建": "亥", "日辰": "丁亥", "爻": yao})
        self.assertEqual(r["status"], "diff")
        self.assertTrue(any(d["field"] == "变卦" and d["kind"] == "输入" for d in r["diffs"]))
        self.assertEqual(r["chart"]["bian"]["name"], "坎为水")       # 爻象齐全，照样装出来
        r = P.verify({"本卦": "泽水捆", "爻": yao})
        self.assertTrue(any(d["field"] == "本卦" for d in r["diffs"]))
        self.assertEqual(r["chart"]["ben"]["name"], "泽水困")

    def test_verify_template_roundtrip(self):
        tpl = json.loads(json.dumps(P.VERIFY_TEMPLATE, ensure_ascii=False))
        self.assertEqual(len(tpl["爻"]), 6)
        self.assertEqual(P.verify(tpl)["status"], "unconfirmed")     # 空模板：全部未确认，不报错
        tpl["本卦"], tpl["变卦"], tpl["月建"], tpl["日辰"] = "泽水困", "坎为水", "亥", "丁亥"
        r = P.verify(tpl)
        self.assertIn(r["status"], ("unconfirmed", "ok")); self.assertEqual(r["chart"]["ben"]["name"], "泽水困")

    def test_date_tz_note_passes_through(self):
        ns = P.argparse.Namespace(verify=None, lines="787896", coins=None, coin_rule=None, gua=None, moving=None,
                                  to=None, month=None, day=None, date="2026-11-07 12:00", tz=None,
                                  zi_rule=None, yongshen=None)
        r = P.run(ns)
        self.assertIn("时区未指明", r["text"]); self.assertIn("默认北京时间", r["text"])
        ns.tz = "+00:00"
        r = P.run(ns)
        self.assertNotIn("时区未指明", r["text"]); self.assertEqual(r["chart"]["month"], "亥")


if __name__ == "__main__":
    unittest.main()
