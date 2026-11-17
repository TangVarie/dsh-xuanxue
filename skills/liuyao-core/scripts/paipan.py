#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""六爻装卦与核验（确定性部分）

把 references/14_装卦速查表.md 的查表规则做成可重复计算：爻值 → 本卦/变卦 → 卦宫世应 →
纳甲纳支 → 六亲 → 伏神 → 旬空、六神 → 甲类机械触发清单（references/20 第一节）。
只算确定的东西，不判吉凶，不评旺衰高低之外的任何事；"半"类触发只给前提事实。

用法
  python scripts/paipan.py --lines 787896 --month 申 --day 庚寅
  python scripts/paipan.py --lines "／ ／／ ○ × ／ ／" --month 申 --day 庚寅
  python scripts/paipan.py --gua 天火同人 --moving 3,5 --month 丑 --day 辛亥
  python scripts/paipan.py --gua 天火同人 --to 风雷益 --date "1993-01-20 10:00"
  python scripts/paipan.py --coins 字背背,字字背,字字字,背背背,字背背,字背背 --coin-rule 本包 --day 庚寅 --month 申
  python scripts/paipan.py --verify chart.json          # 截图读出的字段 → 差异清单
  python scripts/paipan.py --verify-template            # 打印 --verify 用的 JSON 模板（字段说明见 references/14 十一）
  python scripts/paipan.py ... --yongshen 妻财 --json

爻值：自初爻到上爻，6 老阴（×，动）、7 少阳、8 少阴、9 老阳（○，动）。
时间：--month 月建（地支或干支）、--day 日辰干支；或 --date 公历（调用 ganzhi.py，
      节气交接、23～24 点等边界会标 unconfirmed，并分别算出各候选下的结果）。
      --tz 写起卦地的 UTC 偏移；不写按 +08:00，节气交接离得近时会提示。
只依赖标准库。
"""

from __future__ import annotations

import argparse
import itertools
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ganzhi  # noqa: E402

STEMS = ganzhi.STEMS
BRANCHES = ganzhi.BRANCHES

# ── 基础表（出处：references/14、01、03、05、06、08）─────────────────────

# 三爻卦：自下而上 1=阳 0=阴
TRIGRAMS = {
    "乾": (1, 1, 1), "兑": (1, 1, 0), "离": (1, 0, 1), "震": (1, 0, 0),
    "巽": (0, 1, 1), "坎": (0, 1, 0), "艮": (0, 0, 1), "坤": (0, 0, 0),
}
TRIGRAM_BY_BITS = {v: k for k, v in TRIGRAMS.items()}
NATURE = {"乾": "天", "兑": "泽", "离": "火", "震": "雷", "巽": "风", "坎": "水", "艮": "山", "坤": "地"}
TRIGRAM_ELEMENT = {"乾": "金", "兑": "金", "离": "火", "震": "木", "巽": "木", "坎": "水", "艮": "土", "坤": "土"}
# 14 第二节：内卦纳支（初→三）、外卦纳支（四→六）
NAJIA_BRANCH = {
    "乾": ("子寅辰", "午申戌"), "震": ("子寅辰", "午申戌"), "坎": ("寅辰午", "申戌子"),
    "艮": ("辰午申", "戌子寅"), "坤": ("未巳卯", "丑亥酉"), "巽": ("丑亥酉", "未巳卯"),
    "离": ("卯丑亥", "酉未巳"), "兑": ("巳卯丑", "亥酉未"),
}
# 纳甲天干（内、外）
NAJIA_STEM = {
    "乾": ("甲", "壬"), "坤": ("乙", "癸"), "震": ("庚", "庚"), "巽": ("辛", "辛"),
    "坎": ("戊", "戊"), "离": ("己", "己"), "艮": ("丙", "丙"), "兑": ("丁", "丁"),
}
# 14 第三节：八宫六十四卦表（本宫·一世·二世·三世·四世·五世·游魂·归魂）
PALACE_TABLE = {
    "乾": ["乾为天", "天风姤", "天山遁", "天地否", "风地观", "山地剥", "火地晋", "火天大有"],
    "坎": ["坎为水", "水泽节", "水雷屯", "水火既济", "泽火革", "雷火丰", "地火明夷", "地水师"],
    "艮": ["艮为山", "山火贲", "山天大畜", "山泽损", "火泽睽", "天泽履", "风泽中孚", "风山渐"],
    "震": ["震为雷", "雷地豫", "雷水解", "雷风恒", "地风升", "水风井", "泽风大过", "泽雷随"],
    "巽": ["巽为风", "风天小畜", "风火家人", "风雷益", "天雷无妄", "火雷噬嗑", "山雷颐", "山风蛊"],
    "离": ["离为火", "火山旅", "火风鼎", "火水未济", "山水蒙", "风水涣", "天水讼", "天火同人"],
    "坤": ["坤为地", "地雷复", "地泽临", "地天泰", "雷天大壮", "泽天夬", "水天需", "水地比"],
    "兑": ["兑为泽", "泽水困", "泽地萃", "泽山咸", "水山蹇", "地山谦", "雷山小过", "雷泽归妹"],
}
GUA_TYPES = ["本宫", "一世", "二世", "三世", "四世", "五世", "游魂", "归魂"]
SHI_BY_TYPE = {"本宫": 6, "一世": 1, "二世": 2, "三世": 3, "四世": 4, "五世": 5, "游魂": 4, "归魂": 3}
NAME_ALIASES = {"遯": "遁", "天山遯": "天山遁"}

ELEMENT = {"子": "水", "亥": "水", "寅": "木", "卯": "木", "巳": "火", "午": "火",
           "申": "金", "酉": "金", "辰": "土", "戌": "土", "丑": "土", "未": "土"}
SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}   # 甲生乙
KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}      # 甲克乙
SIX_GODS = ["青龙", "朱雀", "勾陈", "腾蛇", "白虎", "玄武"]
SIX_GOD_START = {"甲": 0, "乙": 0, "丙": 1, "丁": 1, "戊": 2, "己": 3, "庚": 4, "辛": 4, "壬": 5, "癸": 5}
MU = {"金": "丑", "木": "未", "火": "戌", "水": "辰"}       # 03 二 / 06 一；土不论入墓（11 R10）
JUE = {"金": "寅", "木": "申", "火": "亥", "水": "巳"}
JIN = {"寅": "卯", "巳": "午", "申": "酉", "亥": "子", "丑": "辰", "辰": "未", "未": "戌", "戌": "丑"}  # 05 三
TUI = {v: k for k, v in JIN.items()}
SANHE = [("申子辰", "水"), ("寅午戌", "火"), ("亥卯未", "木"), ("巳酉丑", "金")]   # 中神为第二字
LIUQIN = ["父母", "兄弟", "子孙", "妻财", "官鬼"]
POS_NAME = {1: "初", 2: "二", 3: "三", 4: "四", 5: "五", 6: "上"}


class PaipanError(ValueError):
    """输入不合法。"""


# ── 关系 ──────────────────────────────────────────────────────────────

def chong(a: str, b: str) -> bool:
    return abs(BRANCHES.index(a) - BRANCHES.index(b)) == 6


def he(a: str, b: str) -> bool:
    return (BRANCHES.index(a) + BRANCHES.index(b)) % 12 == 1


def liuqin_of(palace_element: str, branch: str) -> str:
    e = ELEMENT[branch]
    if e == palace_element:
        return "兄弟"
    if SHENG[e] == palace_element:
        return "父母"
    if SHENG[palace_element] == e:
        return "子孙"
    if KE[e] == palace_element:
        return "官鬼"
    return "妻财"


def wangshuai(month_branch: str, branch: str) -> str:
    """03 一：当令旺、令生相、生令休、克令囚、令克死"""
    m, e = ELEMENT[month_branch], ELEMENT[branch]
    if m == e:
        return "旺"
    if SHENG[m] == e:
        return "相"
    if SHENG[e] == m:
        return "休"
    if KE[e] == m:
        return "囚"
    return "死"


def relation(src: str, dst: str) -> list[str]:
    """src（日、月、变爻等）对 dst 的关系事实"""
    out = []
    if src == dst:
        out.append("值")
    elif ELEMENT[src] == ELEMENT[dst]:
        out.append("临")
    if chong(src, dst):
        out.append("冲")
    if he(src, dst):
        out.append("合")
    es, ed = ELEMENT[src], ELEMENT[dst]
    if SHENG[es] == ed:
        out.append("生")
    if KE[es] == ed:
        out.append("克")
    if MU.get(ed) == src:
        out.append("墓")
    return out


# ── 卦 ────────────────────────────────────────────────────────────────

def _build_gua_index() -> dict:
    """由八宫表建 64 卦索引：bits(初→上) → 卦信息。bits 由卦名首两字的上下卦算出。"""
    idx = {}
    for palace, names in PALACE_TABLE.items():
        for k, full in enumerate(names):
            if "为" in full:
                upper = lower = full[0]
                short = full[0]
            else:
                upper = next(t for t, n in NATURE.items() if n == full[0])
                lower = next(t for t, n in NATURE.items() if n == full[1])
                short = full[2:]
            bits = TRIGRAMS[lower] + TRIGRAMS[upper]
            if bits in idx:
                raise RuntimeError(f"八宫表重复：{full}")
            idx[bits] = {"name": full, "short": short, "palace": palace,
                         "palace_element": TRIGRAM_ELEMENT[palace], "type": GUA_TYPES[k],
                         "shi": SHI_BY_TYPE[GUA_TYPES[k]], "upper": upper, "lower": lower}
    if len(idx) != 64:
        raise RuntimeError("八宫表不足 64 卦")
    for info in idx.values():
        info["ying"] = (info["shi"] + 2) % 6 + 1
    return idx


GUA = _build_gua_index()
GUA_BY_NAME = {}
for _bits, _info in GUA.items():
    GUA_BY_NAME[_info["name"]] = _bits
    GUA_BY_NAME[_info["short"]] = _bits
    if "为" in _info["name"]:
        GUA_BY_NAME[_info["name"][0] + "卦"] = _bits


def lookup_gua(name: str) -> tuple:
    n = NAME_ALIASES.get(name.strip(), name.strip()).replace("遯", "遁")
    n = n.removesuffix("卦") if n.endswith("卦") and n not in GUA_BY_NAME else n
    if n in GUA_BY_NAME:
        return GUA_BY_NAME[n]
    raise PaipanError(f"不认识的卦名：{name!r}")


def najia_lines(bits: tuple) -> list[tuple[str, str]]:
    """bits(初→上) → 每爻 (纳甲天干, 地支)"""
    lower = TRIGRAM_BY_BITS[bits[:3]]
    upper = TRIGRAM_BY_BITS[bits[3:]]
    out = []
    for i in range(3):
        out.append((NAJIA_STEM[lower][0], NAJIA_BRANCH[lower][0][i]))
    for i in range(3):
        out.append((NAJIA_STEM[upper][1], NAJIA_BRANCH[upper][1][i]))
    return out


def is_liuchong(bits: tuple) -> bool:
    br = [b for _, b in najia_lines(bits)]
    return all(chong(br[i], br[i + 3]) for i in range(3))


def is_liuhe(bits: tuple) -> bool:
    br = [b for _, b in najia_lines(bits)]
    return all(he(br[i], br[i + 3]) for i in range(3))


# ── 输入解析 ──────────────────────────────────────────────────────────

SYMBOL_VALUE = {"／／": 8, "//": 8, "--": 8, "x": 6, "×": 6, "X": 6, "o": 9, "○": 9, "O": 9,
                "／": 7, "/": 7, "—": 7, "-": 7,
                "少阳": 7, "少阴": 8, "老阳": 9, "老阴": 6, "阳": 7, "阴": 8}


def parse_lines(text: str) -> list[int]:
    t = text.strip()
    if re.fullmatch(r"[6789]{6}", t):
        return [int(c) for c in t]
    tokens = [x for x in re.split(r"[\s,，、]+", t) if x]
    if len(tokens) == 6 and all(x in "6789" and len(x) == 1 for x in tokens):
        return [int(x) for x in tokens]
    if len(tokens) == 6 and all(x in SYMBOL_VALUE for x in tokens):
        return [SYMBOL_VALUE[x] for x in tokens]
    raise PaipanError(f"爻值要恰好 6 个，自初爻到上爻（6/7/8/9 或 ／ ／／ ○ ×）：{text!r}")


def parse_coins(text: str, rule: str | None) -> list[int]:
    if rule not in ("本包", "背为阳"):
        raise PaipanError("铜钱字背有两种相反约定：请用 --coin-rule 本包（字记3、背记2）或 背为阳（背记3、字记2）")
    tokens = [x for x in re.split(r"[\s,，、]+", text.strip()) if x]
    if len(tokens) != 6:
        raise PaipanError(f"铜钱要 6 次（自初爻到上爻），收到 {len(tokens)} 次")
    vals = []
    for tok in tokens:
        if len(tok) != 3 or any(c not in "字背" for c in tok):
            raise PaipanError(f"每次写三个字，由'字''背'组成，如 字背背：{tok!r}")
        zi = tok.count("字")
        vals.append(zi * 3 + (3 - zi) * 2 if rule == "本包" else (3 - zi) * 3 + zi * 2)
    return vals


def lines_from_gua(name: str, moving: list[int] | None = None, to: str | None = None) -> list[int]:
    bits = lookup_gua(name)
    mv = set(moving or [])
    if to:
        tb = lookup_gua(to)
        diff = {i + 1 for i in range(6) if bits[i] != tb[i]}
        if moving and set(moving) != diff:
            raise PaipanError(f"动爻 {sorted(mv)} 与 {name}→{to} 的变化 {sorted(diff)} 不一致")
        mv = diff
    if any(p not in range(1, 7) for p in mv):
        raise PaipanError("动爻位置只能是 1～6")
    return [(9 if bits[i] else 6) if (i + 1) in mv else (7 if bits[i] else 8) for i in range(6)]


POS_WORDS = {"初": 1, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "上": 6}


def parse_moving(text: str | None) -> list[int] | None:
    """动爻位置：3、3,5、三、初,上、"三爻 五爻" 都认；认不出抛 PaipanError。"""
    if not text or not text.strip():
        return None
    out = []
    for tok in (x for x in re.split(r"[,，、\s]+", text.strip()) if x):
        t = tok.removesuffix("爻").removeprefix("第")
        if t.isdigit():
            out.append(int(t))
        elif t in POS_WORDS:
            out.append(POS_WORDS[t])
        else:
            raise PaipanError(f"动爻位置认不出：{tok!r}（写 1～6，或 初/二/三/四/五/上）")
    return out


def parse_branch_arg(text: str | None, what: str) -> str | None:
    if not text:
        return None
    t = text.strip()
    if len(t) == 1 and t in BRANCHES:
        return t
    if len(t) == 2:
        ganzhi.gz_index(t)
        return t[1]
    raise PaipanError(f"{what}写法不对：{text!r}（地支，或干支）")


def parse_day_arg(text: str | None) -> str | None:
    if not text:
        return None
    t = text.strip()
    try:
        ganzhi.gz_index(t)
    except ganzhi.GanzhiError as exc:
        raise PaipanError(f"日辰要写干支（如 庚寅）：{text!r}") from exc
    return t


# ── 装卦与触发 ────────────────────────────────────────────────────────

def analyze(values: list[int], month: str | None, day: str | None,
            yongshen: str | None = None) -> dict:
    """values: 6 个爻值（初→上）。month: 月建地支或 None。day: 日辰干支或 None。"""
    if len(values) != 6 or any(v not in (6, 7, 8, 9) for v in values):
        raise PaipanError("爻值必须是 6 个 6/7/8/9")
    if yongshen and yongshen not in LIUQIN + ["世爻", "应爻"]:
        raise PaipanError(f"--yongshen 只能是 {'、'.join(LIUQIN)}、世爻、应爻")
    bits = tuple(1 if v in (7, 9) else 0 for v in values)
    moving = [i + 1 for i, v in enumerate(values) if v in (6, 9)]
    bbits = tuple((1 - b) if (i + 1) in moving else b for i, b in enumerate(bits))
    ben = dict(GUA[bits])
    bian = dict(GUA[bbits]) if moving else None
    pe = ben["palace_element"]
    nj = najia_lines(bits)
    bnj = najia_lines(bbits) if moving else None
    kong = ganzhi.xunkong(day) if day else None
    day_branch = day[1] if day else None
    gods = None
    if day:
        start = SIX_GOD_START[day[0]]
        gods = [SIX_GODS[(start + i) % 6] for i in range(6)]

    lines = []
    for i in range(6):
        pos = i + 1
        stem, br = nj[i]
        yang = bits[i] == 1
        n = "九" if yang else "六"
        line = {
            "pos": pos,
            "label": f"初{n}" if pos == 1 else f"上{n}" if pos == 6 else f"{n}{POS_NAME[pos]}",
            "value": values[i], "yinyang": "阳" if yang else "阴",
            "moving": pos in moving, "symbol": {6: "×", 7: "／", 8: "／／", 9: "○"}[values[i]],
            "stem": stem, "branch": br, "element": ELEMENT[br], "liuqin": liuqin_of(pe, br),
            "shiying": "世" if pos == ben["shi"] else "应" if pos == ben["ying"] else "",
            "god": gods[i] if gods else None,
            "kong": (br in kong) if kong else None,
            "month_state": wangshuai(month, br) if month else None,
            "month_rel": relation(month, br) if month else None,
            "day_rel": relation(day_branch, br) if day else None,
        }
        if pos in moving:
            cs, cb = bnj[i]
            line["change"] = {
                "stem": cs, "branch": cb, "element": ELEMENT[cb], "liuqin": liuqin_of(pe, cb),
                "kong": (cb in kong) if kong else None,
                "month_state": wangshuai(month, cb) if month else None,
                "month_rel": relation(month, cb) if month else None,
                "day_rel": relation(day_branch, cb) if day else None,
                "to_line": relation(cb, br),
            }
        lines.append(line)

    # 伏神：主卦缺的六亲，于本宫首卦同爻位取
    present = {ln["liuqin"] for ln in lines}
    missing = [q for q in LIUQIN if q not in present]
    pure = najia_lines(TRIGRAMS[ben["palace"]] * 2)
    fushen = []
    for q in missing:
        for i, (st, br) in enumerate(pure):
            if liuqin_of(pe, br) == q:
                fly = lines[i]
                fs = {"pos": i + 1, "stem": st, "branch": br, "element": ELEMENT[br], "liuqin": q,
                      "under": f"{fly['label']} {fly['branch']}{fly['element']}{fly['liuqin']}",
                      "fly_to_fu": _flyfu(fly["branch"], br),
                      "kong": (br in kong) if kong else None,
                      "month_state": wangshuai(month, br) if month else None,
                      "month_rel": relation(month, br) if month else None,
                      "day_rel": relation(day_branch, br) if day else None}
                fushen.append(fs)
                lines[i]["fushen"] = fs

    chart = {
        "ben": {**ben, "liuchong": is_liuchong(bits), "liuhe": is_liuhe(bits)},
        "bian": ({**bian, "liuchong": is_liuchong(bbits), "liuhe": is_liuhe(bbits)} if bian else None),
        "month": month, "day": day, "xunkong": kong,
        "moving": moving, "lines": lines, "fushen": fushen,
        "liuqin_count": {q: [ln["pos"] for ln in lines if ln["liuqin"] == q] for q in LIUQIN},
        "missing_liuqin": missing,
    }
    chart["triggers"] = triggers(chart, yongshen)
    return chart


def _flyfu(fly: str, fu: str) -> str:
    ef, eu = ELEMENT[fly], ELEMENT[fu]
    if ef == eu:
        return "比和"
    if SHENG[ef] == eu:
        return "飞生伏"
    if SHENG[eu] == ef:
        return "伏生飞"
    if KE[ef] == eu:
        return "飞克伏"
    return "伏克飞"


def _yuepo(ln: dict, day_branch: str | None) -> bool:
    """此爻是否按月破论：月建冲之，且不是值日之爻（值日逢月冲按 11 R07 不论破）。"""
    return bool(ln.get("month_rel") and "冲" in ln["month_rel"] and ln["branch"] != day_branch)


def triggers(c: dict, yongshen: str | None) -> list[dict]:
    """甲类机械触发（references/20 第一节）。kind: 触发=已机械确定；前提=给出事实，结论待模型按旺衰判。"""
    T = []
    def add(step, name, where, detail, kind="触发"):
        T.append({"step": step, "name": name, "where": where, "detail": detail, "kind": kind})
    L = c["lines"]
    def tag(ln):
        return f"{ln['label']} {ln['branch']}{ln['element']}{ln['liuqin']}" + (f"（{ln['shiying']}）" if ln["shiying"] else "")
    month, day = c["month"], c["day"]
    db = day[1] if day else None

    # 第 1 步
    if c["xunkong"]:
        for ln in L:
            if ln["kong"]:
                add(1, "旬空", tag(ln), f"旬空 {c['xunkong']}；真空/假空按 07 一.2 判（"
                    + ("月破" if _yuepo(ln, db) else f"月令{ln['month_state'] or '?'}")
                    + ("，发动" if ln["moving"] else "") + "）", "前提")
            ch = ln.get("change")
            if ch and ch["kong"]:
                add(5, "动化空", tag(ln), f"化出 {ch['branch']}{ch['element']}{ch['liuqin']} 旬空")
        for fs in c["fushen"]:
            if fs["kong"]:
                add(6, "伏神旬空", f"伏神 {fs['branch']}{fs['element']}{fs['liuqin']}", "冲空、冲飞都解不了伏神的空（07 二.3）", "前提")
    if month:
        for ln in L:
            if "冲" in ln["month_rel"]:
                if db and ln["branch"] == db:
                    add(1, "月冲值日之爻", tag(ln),
                        f"月建{month}冲，而此爻值日辰{db}：曲炜称暗动（冲不败），《增删》称逢破不破，两派同判有力，不按月破论（11 R07）", "前提")
                    continue
                d = f"月建{month}冲；" + ("发动，可查破而不破（03 四）" if ln["moving"] else "静爻，逢生不起、逢克更凶")
                if ln["element"] == "土":
                    d += "；土爻逢土月冲，月令与爻同五行：默认以月破论，'旺'不作有气依据（11 R27，两条规则相抵，主判依赖时标源）"
                if db and ELEMENT[db] == ln["element"]:
                    d += f"；此爻临日辰{db}（同五行不同支）：曲炜派仍论月破（03 六）"
                add(1, "月破", tag(ln), d)
            if "合" in ln["month_rel"]:
                add(1, "月合", tag(ln), f"月建{month}合", "前提")
    if day:
        for ln in L:
            if "冲" in ln["day_rel"]:
                if ln["moving"]:
                    add(1, "日冲动爻", tag(ln), f"日辰{db}冲动爻（冲散等按 04 二判）", "前提")
                else:
                    st = ln["month_state"]
                    if _yuepo(ln, db):
                        st_txt, lean = "月破", "月破又逢日冲，倾向日破"
                    else:
                        st_txt = f"月令{st or '?'}"
                        lean = "倾向暗动" if st in ("旺", "相") else "倾向日破" if st else "旺衰未定"
                    add(1, "日冲静爻", tag(ln), f"日辰{db}冲静爻；{st_txt}，{lean}；日月一生一克时为临界（03 三）", "前提")
            if "合" in ln["day_rel"]:
                add(1, "日合", tag(ln), f"日辰{db}合" + ("（动爻被合＝合绊）" if ln["moving"] else "（静爻＝合起之象）"), "前提")
            if "墓" in ln["day_rel"]:
                add(6, "入日墓", tag(ln), f"日辰{db}为{ln['element']}之墓；旺相入库、休囚入墓（06 二）", "前提")
        if month:
            for ln in L:
                mr, dr = ln["month_rel"], ln["day_rel"]
                m_bad = bool({"克", "冲"} & set(mr))
                d_bad = bool({"克", "冲"} & set(dr))
                # 土逢土冲既"临"又"冲"：按冲算，不算生扶一侧（11 R27）
                m_good = bool({"生", "值", "临"} & set(mr)) and "冲" not in mr
                d_good = bool({"生", "值", "临"} & set(dr)) and "冲" not in dr
                if (m_good and d_bad) or (m_bad and d_good):
                    add(3, "日月一生一克", tag(ln), "月建与日辰对此爻一生一克（或一旺一破）：抛开日月看卦中旺衰（03 四）", "前提")
    if month:
        for ln in L:
            if "墓" in ln["month_rel"]:
                add(6, "入月墓", tag(ln), f"月建{month}为{ln['element']}之墓", "前提")
    b = c["ben"]
    if b["liuchong"]:
        add(1, "六冲卦", b["name"], "近、急、快、乱、短" + ("；六爻俱静，只有冲象" if not c["moving"] else ""))
    if b["liuhe"]:
        add(1, "六合卦", b["name"], "远、缓、慢、稳、久")
    if c["bian"]:
        v = c["bian"]
        kinds = [("冲" if b["liuchong"] else "合" if b["liuhe"] else None),
                 ("冲" if v["liuchong"] else "合" if v["liuhe"] else None)]
        if kinds[0] and kinds[1]:
            add(1, f"{kinds[0]}变{kinds[1]}", f"{b['name']}之{v['name']}", "卦变冲合")
        elif kinds[1]:
            add(1, f"化六{kinds[1]}卦", f"{b['name']}之{v['name']}", f"变卦为六{kinds[1]}卦")
        # 卦象反吟只取象（11 R19）
        pairs = {frozenset(p) for p in (("离", "坎"), ("乾", "巽"), ("艮", "坤"), ("兑", "震"))}
        for part, a1, a2 in (("内卦", b["lower"], v["lower"]), ("外卦", b["upper"], v["upper"])):
            if frozenset((a1, a2)) in pairs:
                add(5, "卦象反吟（只取象）", f"{part} {a1}→{a2}", "方位对冲之卦互变；不作吉凶依据（11 R19）", "前提")
    if b["type"] in ("游魂", "归魂"):
        add(1, b["type"], b["name"], "游魂主变、归魂难改；只定世应，不单独定吉凶")
    if len(c["moving"]) == 1:
        add(1, "独发", tag(L[c["moving"][0] - 1]), "该爻所值日月常为应期；仍须紧扣用神")
    if len(c["moving"]) == 5:
        idle = [p for p in range(1, 7) if p not in c["moving"]][0]
        add(1, "独静", tag(L[idle - 1]), "主要矛盾常集中于独静爻；仍须紧扣用神")

    # 第 3 步
    if month:
        for ln in L:
            if ln["shiying"] or ln["moving"]:
                add(3, "旺相休囚死", tag(ln), f"月令{month}：{ln['month_state']}"
                    + ("（月冲值日，不按月破论，11 R07）" if ("冲" in ln["month_rel"] and not _yuepo(ln, db))
                       else "（逢月冲，以月破论" + ("，11 R27" if ln["element"] == "土" else "") + "）" if _yuepo(ln, db) else ""),
                    "前提")
    if day:
        for ln in L:
            ch = ln.get("change")
            if ln["moving"] and ch and ln["branch"] == db and (
                    ch["branch"] == MU.get(ln["element"]) or ch["branch"] == JUE.get(ln["element"])
                    or "克" in ch["to_line"]):
                add(3, "日建化坏", tag(ln), f"爻值日建{db}，自身动化{ch['branch']}（墓/绝/回头克）：日辰也救不了（03 四）")

    # 第 4 步：爻间相冲、两动相合（只看主卦六爻之间；变爻越位作用由模型按 03 五判）
    for i in range(6):
        for j in range(i + 1, 6):
            a, b2 = L[i], L[j]
            if chong(a["branch"], b2["branch"]) and (a["moving"] or b2["moving"]):
                if a["moving"] and b2["moving"]:
                    add(4, "论冲成立（两动相冲）", f"{tag(a)} ⇄ {tag(b2)}", "两爻皆发动而相冲；谁胜看旺衰与层次（04 二）")
                else:
                    src, dst = (a, b2) if a["moving"] else (b2, a)
                    add(4, "论冲成立（动爻冲静爻）", f"{tag(src)} 冲 {tag(dst)}",
                        "一方发动，论冲成立；被冲静爻旺→冲起、衰→冲破、旬空→冲实或又空又破，被日月合住者不散（04 二）")
            if he(a["branch"], b2["branch"]) and a["moving"] and b2["moving"]:
                add(4, "爻间六合（两动相合）", f"{tag(a)} 合 {tag(b2)}",
                    "两爻皆发动，六合成立；合化后五行与本性相同者仍能生克，不同者被绊（04 三）。一动一静只论合象，不列", "前提")

    # 第 4 步：三合候选
    pool = {}
    def put(branch, src):
        pool.setdefault(branch, []).append(src)
    for ln in L:
        put(ln["branch"], f"{ln['label']}{'动' if ln['moving'] else '静'}")
        if ln.get("change"):
            put(ln["change"]["branch"], f"{ln['label']}变出")
    if month:
        put(month, "月建")
    if day:
        put(db, "日辰")
    for trio, elem in SANHE:
        if all(x in pool for x in trio):
            mid = trio[1]
            members = "；".join(f"{x}:{'、'.join(pool[x])}" for x in trio)
            mid_moving = any("动" in s for s in pool[mid])
            add(4, f"三合{elem}局候选", trio,
                f"{members}。中神{mid}{'发动' if mid_moving else '不动'}；成局与合化/合绊按 11 R08 判，依赖静爻成局或日月补字时标源", "前提")

    # 第 5 步：动变
    for ln in L:
        ch = ln.get("change")
        if not ch:
            continue
        w = tag(ln) + f" 化 {ch['branch']}{ch['element']}{ch['liuqin']}"
        if JIN.get(ln["branch"]) == ch["branch"]:
            add(5, "化进神", w, "喜神化进吉、忌神化进凶（05 三）")
        if TUI.get(ln["branch"]) == ch["branch"]:
            add(5, "化退神", w, "旺相化退不立刻退尽（05 三）")
        r = ch["to_line"]
        if "生" in r:
            add(5, "回头生", w, "变爻生动爻")
        if "克" in r:
            add(5, "回头克", w, "须变爻有生克权（05 四）")
        if ln["element"] in MU and ch["branch"] == MU[ln["element"]]:
            closed = []
            if month and he(month, ch["branch"]):
                closed.append("月合")
            if day and he(db, ch["branch"]):
                closed.append("日合")
            add(5, "化墓", w, "以入墓论，待冲墓（05 四）" + (f"；墓爻逢{'、'.join(closed)}，按 06 三不入" if closed else ""))
        elif ln["element"] == "土" and ch["branch"] in "辰戌丑未":
            add(5, "土爻化墓库（默认不论）", w, "土不论入墓（11 R10）", "前提")
        if ln["element"] in JUE and ch["branch"] == JUE[ln["element"]]:
            add(5, "化绝", w, "化休（05 四）")
        if chong(ln["branch"], ch["branch"]):
            add(5, "爻变反吟", w, "反复不顺；用神旺相不被冲克照样成事（05 五）")
        if ln["branch"] == ch["branch"]:
            add(5, "伏吟", w, "所求不尽人意；吟待冲（05 六）")

    # 第 6 步
    for ln in L:
        if ln["moving"] or ln["element"] not in MU:
            continue
        for mv in L:
            if mv["moving"] and mv["branch"] == MU[ln["element"]]:
                extra = "；此爻又逢日冲，06 四：静而逢冲则不入" if (day and "冲" in ln["day_rel"]) else ""
                add(6, "静爻逢动爻为墓", f"{tag(ln)} ← 墓爻 {tag(mv)}",
                    "06 三.2 说静爻可入动爻之墓（墓爻须有生克权），06 四又说墓爻自身发动则不入：两说并存，"
                    "不作入墓/入库的唯一依据，主判依赖它时给双分支（11 R29）" + extra, "前提")
    for fs in c["fushen"]:
        add(6, "伏神", f"{fs['branch']}{fs['element']}{fs['liuqin']} 伏于 {fs['under']} 下",
            f"{fs['fly_to_fu']}；出现只靠值、临、冲伏、冲飞（07 二）")
    brs = [ln["branch"] for ln in L] + [ln["change"]["branch"] for ln in L if ln.get("change")]
    if month:
        brs.append(month)
    if day:
        brs.append(db)
    if all(x in brs for x in "辰戌丑未"):
        moving_brs = [ln["branch"] for ln in L if ln["moving"]]
        add(6, "四土俱全" + ("且俱动" if all(x in moving_brs for x in "辰戌丑未") else ""), "主变卦+日月",
            "仅当问事为测病、测灾时作加权警示（11 R09）", "前提")
    if yongshen in LIUQIN:
        pos = c["liuqin_count"][yongshen]
        if len(pos) >= 2:
            add(6, "用神两现", f"{yongshen}：" + "、".join(tag(L[p - 1]) for p in pos), "转乙′：各司其职还是取舍（11 R16）")
        elif not pos:
            add(6, "用神不上卦", yongshen, "取伏神（见伏神条）")
    return T


# ── 截图核验 ──────────────────────────────────────────────────────────

FIELD_CN = {"branch": "地支", "liuqin": "六亲", "god": "六神", "shiying": "世应"}


VERIFY_TEMPLATE = {
    "_说明": [
        "从截图读出的字段，读不清的一律写 null，不要补齐；以下划线开头的键会被忽略",
        "本卦、变卦：卦名（全称或简称，如 泽水困 / 困）；静卦或截图没有变卦时写 null",
        "月建：地支或干支；日辰：干支；旬空：两个地支连写，如 午未",
        "爻：恰好 6 项，自初爻到上爻；整爻看不清写 null",
        "爻.阴阳：阳 / 阴；爻.动：true / false；地支、六亲、六神写截图上的字；世应：世 / 应 / 空串",
        "爻.变支：动爻化出的地支，静爻写 null",
        "伏神：截图上标了才写，每项 位（1～6）、地支、六亲；没标写 null，标明没有伏神写 []",
    ],
    "本卦": None, "变卦": None, "月建": None, "日辰": None, "旬空": None,
    "爻": [{"阴阳": None, "动": None, "地支": None, "六亲": None, "六神": None, "世应": None, "变支": None}
          for _ in range(6)],
    "伏神": None,
}
_YAO_STR_KEYS = ("地支", "六亲", "六神", "世应", "变支")


def _check_verify_input(chart_in) -> list:
    """校验 --verify 的输入结构；不合格抛 PaipanError（说清哪一项、该怎么写）。返回 6 项的爻列表。"""
    hint = "（格式见 references/14 十一，或运行 paipan.py --verify-template）"
    if not isinstance(chart_in, dict):
        raise PaipanError("核验输入要是一个 JSON 对象" + hint)
    for key in ("本卦", "变卦", "月建", "日辰", "旬空"):
        if chart_in.get(key) is not None and not isinstance(chart_in[key], str):
            raise PaipanError(f"{key} 要写成字符串或 null" + hint)
    yao = chart_in.get("爻")
    if yao is None:
        yao = [None] * 6
    if not isinstance(yao, list) or len(yao) != 6:
        raise PaipanError("爻 要恰好 6 项（初→上），读不清的写 null" + hint)
    for i, y in enumerate(yao):
        name = f"{POS_NAME[i + 1]}爻"
        if y is None:
            continue
        if not isinstance(y, dict):
            raise PaipanError(f"{name} 要写成对象，如 {{\"阴阳\": \"阳\", \"动\": false, \"地支\": \"寅\"}}，收到 {y!r}" + hint)
        if y.get("阴阳") not in (None, "阳", "阴"):
            raise PaipanError(f"{name}.阴阳 只能是 阳 / 阴 / null，收到 {y.get('阴阳')!r}")
        if y.get("动") is not None and not isinstance(y.get("动"), bool):
            raise PaipanError(f"{name}.动 只能是 true / false / null，收到 {y.get('动')!r}")
        for k in _YAO_STR_KEYS:
            if y.get(k) is not None and not isinstance(y[k], str):
                raise PaipanError(f"{name}.{k} 要写成字符串或 null")
    fu = chart_in.get("伏神")
    if fu is not None and (not isinstance(fu, list) or any(not isinstance(f, dict) for f in fu)):
        raise PaipanError("伏神 要写成列表，每项含 位、地支、六亲；没标写 null" + hint)
    return yao


def verify(chart_in: dict) -> dict:
    """chart_in：从截图读出的字段，读不清的写 null。返回差异清单。字段格式见 VERIFY_TEMPLATE。"""
    diffs: list[dict] = []
    unconfirmed: list[str] = []
    yao = _check_verify_input(chart_in)
    chart_in = {k: v for k, v in chart_in.items() if not str(k).startswith("_")}
    # 卦名先各自认一遍：认不出的记一条输入类差异、按未确认处理，不中止核验
    for key in ("本卦", "变卦"):
        if chart_in.get(key):
            try:
                lookup_gua(chart_in[key])
            except PaipanError:
                diffs.append({"kind": "输入", "field": key, "shown": chart_in[key],
                              "detail": f"卦名认不出（可能读错字），{key}按未确认处理，请向用户确认"})
                unconfirmed.append(key)
                chart_in[key] = None
    # 1) 定卦形
    vals_from_yao = None
    if all(y and y.get("阴阳") in ("阳", "阴") and isinstance(y.get("动"), bool) for y in yao):
        vals_from_yao = [(9 if y["动"] else 7) if y["阴阳"] == "阳" else (6 if y["动"] else 8) for y in yao]
    vals_from_name = None
    if chart_in.get("本卦"):
        try:
            if chart_in.get("变卦"):
                vals_from_name = lines_from_gua(chart_in["本卦"], None, chart_in["变卦"])
            else:
                known = [y.get("动") if y else None for y in yao]
                if any(k is None for k in known):
                    unconfirmed.append("动爻（截图未标全，变卦也未给）")
                vals_from_name = lines_from_gua(chart_in["本卦"], [i + 1 for i, k in enumerate(known) if k is True])
        except PaipanError as exc:
            diffs.append({"kind": "输入", "field": "本卦/变卦/动爻", "detail": str(exc)})
    values = vals_from_yao or vals_from_name
    if vals_from_yao and vals_from_name and vals_from_yao != vals_from_name:
        diffs.append({"kind": "输入", "field": "卦形",
                      "detail": f"爻象读出 {GUA[tuple(1 if v in (7, 9) else 0 for v in vals_from_yao)]['name']}，"
                                f"与截图卦名 {chart_in.get('本卦')}{'之' + chart_in['变卦'] if chart_in.get('变卦') else ''} 不一致"})
    if values is None:
        miss = [f"{POS_NAME[i + 1]}爻" for i, y in enumerate(yao) if not (y and y.get("阴阳") and y.get("动") is not None)]
        return {"status": "unconfirmed", "reason": "卦形定不下来：缺" + "、".join(miss) + "的阴阳或动静，也没有可用的卦名",
                "diffs": diffs, "unconfirmed": miss}
    # 2) 时间
    month = chart_in.get("月建")
    day = chart_in.get("日辰")
    try:
        month = parse_branch_arg(month, "月建") if month else None
        day = parse_day_arg(day) if day else None
    except PaipanError as exc:
        diffs.append({"kind": "输入", "field": "月建/日辰", "detail": str(exc)})
        month = day = None
    if not month:
        unconfirmed.append("月建")
    if not day:
        unconfirmed.append("日辰")
    c = analyze(values, month, day)
    # 3) 逐项比对
    if chart_in.get("旬空") and c["xunkong"] and set(chart_in["旬空"]) != set(c["xunkong"]):
        diffs.append({"kind": "推算", "field": "旬空", "shown": chart_in["旬空"], "computed": c["xunkong"],
                      "detail": "旬空按起卦日干支查（07 一.1）；若截图按别的柱查或换日约定不同会出现此差异"})
    if chart_in.get("变卦") and c["bian"] and lookup_gua(chart_in["变卦"]) != tuple(
            1 if (v in (7, 9)) != (v in (6, 9)) else 0 for v in values):
        diffs.append({"kind": "输入", "field": "变卦", "shown": chart_in["变卦"], "computed": c["bian"]["name"]})
    for i, y in enumerate(yao):
        if not y:
            unconfirmed.append(f"{POS_NAME[i + 1]}爻全部")
            continue
        ln = c["lines"][i]
        for key_cn, key in (("地支", "branch"), ("六亲", "liuqin"), ("六神", "god"), ("世应", "shiying")):
            shown = y.get(key_cn)
            if shown is None:
                unconfirmed.append(f"{POS_NAME[i + 1]}爻{key_cn}")
                continue
            comp = ln.get(key)
            if comp is None:
                continue
            if (shown or "") != (comp or ""):
                hint = {"branch": "纳支不同：可能是装卦约定不同（如乾卦改纳甲说，11 R17）或读错",
                        "liuqin": "六亲不同：先查卦宫是否认错（六亲按主卦卦宫五行配）",
                        "god": "六神不同：六神按日干起，查日干支或换日约定",
                        "shiying": "世应不同：查卦宫与世位"}[key]
                diffs.append({"kind": "推算", "field": f"{POS_NAME[i + 1]}爻{key_cn}",
                              "shown": shown, "computed": comp, "detail": hint})
        if y.get("变支") and ln.get("change") and y["变支"] != ln["change"]["branch"]:
            diffs.append({"kind": "推算", "field": f"{POS_NAME[i + 1]}爻变支", "shown": y["变支"],
                          "computed": ln["change"]["branch"], "detail": "变爻纳支按变卦上下卦取（14 七）"})
    if chart_in.get("伏神") is not None:
        shown = {(f.get("位"), f.get("地支"), f.get("六亲")) for f in chart_in["伏神"]}
        comp = {(f["pos"], f["branch"], f["liuqin"]) for f in c["fushen"]}
        if shown != comp:
            diffs.append({"kind": "推算", "field": "伏神", "shown": sorted(shown, key=str),
                          "computed": sorted(comp, key=str), "detail": "伏神取本宫首卦同爻位，只在六亲缺位时取（14 八）"})
    status = "ok" if not diffs and not unconfirmed else ("diff" if diffs else "unconfirmed")
    return {"status": status, "chart": c, "diffs": diffs, "unconfirmed": unconfirmed,
            "advice": ("输入类差异（爻象、动爻、卦名、日期）要向用户确认；推算类差异以本包规则为准，并在简明卦盘后注明差异"
                       if diffs else "")}


# ── 输出 ──────────────────────────────────────────────────────────────

def render(c: dict, header_extra: str = "") -> str:
    b, v = c["ben"], c["bian"]
    title = b["name"] + (f"之{v['name']}" if v else "（静卦）")
    head = f"{title}（{b['palace']}宫{b['type']}，世{b['shi']}应{b['ying']}）"
    tm = f"月建{c['month'] or '未确认'}·日辰{c['day'] or '未确认'}｜旬空{c['xunkong'] or '未确认'}"
    out = [head + ("｜" + header_extra if header_extra else ""), tm,
           "爻位｜纳甲｜六亲｜六神｜世应｜动变｜伏神｜标记"]
    for ln in reversed(c["lines"]):
        ch = ln.get("change")
        mv = f"{ln['symbol']}→{ch['branch']}{ch['element']}{ch['liuqin']}" if ch else ""
        fs = ln.get("fushen")
        fsx = f"{fs['branch']}{fs['element']}{fs['liuqin']}" if fs else ""
        marks = []
        if ln["kong"]:
            marks.append("空")
        dbr = c["day"][1] if c["day"] else None
        if _yuepo(ln, dbr):
            marks.append("月破")
        elif ln["month_rel"] and "冲" in ln["month_rel"]:
            marks.append("月冲值日")
        if ln["day_rel"] and "冲" in ln["day_rel"]:
            marks.append("日冲")
        if ln["month_state"]:
            marks.append("（月令同五行，旺不作有气依据）" if _yuepo(ln, dbr) and ln["month_state"] == "旺"
                         else ln["month_state"])
        out.append(f"{ln['label']}｜{ln['stem']}{ln['branch']}{ln['element']}｜{ln['liuqin']}｜{ln['god'] or '—'}｜"
                   f"{ln['shiying'] or ''}｜{mv}｜{fsx}｜{'、'.join(marks)}")
    if c["triggers"]:
        out.append("甲类机械触发（触发＝已确定；前提＝事实已给，结论按旺衰判）：")
        for t in sorted(c["triggers"], key=lambda t: t["step"]):
            out.append(f"  第{t['step']}步 [{t['kind']}] {t['name']}：{t['where']}——{t['detail']}")
    return "\n".join(out)


def run(args) -> dict:
    """命令行主流程；返回结果 dict（含 text）。"""
    if getattr(args, "verify_template", False):
        return {"status": "template", "template": VERIFY_TEMPLATE,
                "text": json.dumps(VERIFY_TEMPLATE, ensure_ascii=False, indent=2)}
    if args.verify:
        data = json.loads(Path(args.verify).read_text(encoding="utf-8"))
        r = verify(data)
        if "chart" in r:
            r["text"] = render(r["chart"])
        return r
    # 卦形
    srcs = [bool(args.lines), bool(args.gua), bool(args.coins)]
    if sum(srcs) != 1:
        raise PaipanError("卦形只能用 --lines、--gua 或 --coins 其中一种给出")
    if args.lines:
        values = parse_lines(args.lines)
    elif args.coins:
        values = parse_coins(args.coins, args.coin_rule)
    else:
        values = lines_from_gua(args.gua, parse_moving(args.moving), args.to)
    # 时间
    month = parse_branch_arg(args.month, "月建")
    day = parse_day_arg(args.day)
    conv = None
    variants = [(month, day)]
    if args.date:
        tz_arg = getattr(args, "tz", None)
        conv = ganzhi.convert(args.date, tz_arg or ganzhi.TZ_ASSUMED, args.zi_rule, tz_assumed=tz_arg is None)
        if conv["status"] == "error":
            raise PaipanError("公历换算失败：" + conv["reason"])
        mcands = [month] if month else ([conv["month"]["branch"]] if conv["month"]["status"] == "ok"
                                        else [m[1] for m in conv["month"]["candidates"]])
        dcands = [day] if day else ([conv["day"]["ganzhi"]] if conv["day"]["status"] == "ok"
                                    else conv["day"]["candidates"])
        variants = list(itertools.product(mcands, dcands))
    results = [analyze(values, m, d, args.yongshen) for m, d in variants]
    extra = ""
    if conv:
        def show(k):
            x = conv[k]
            return x["ganzhi"] or ("未确认(" + "/".join(c for c in (x.get("candidates") or []) if c) + ")")
        tzs = conv["tz"] + ("，默认北京时间" if conv.get("tz_assumed") else "")
        extra = f"{show('year')}年{show('month')}月{show('day')}日{show('hour')}时（公历 {args.date} {tzs} 换算）"
        given = [n for n, v in (("月建", month), ("日辰", day)) if v]
        if given:
            extra += f"｜{'、'.join(given)}取用户给定值"
    if len(results) == 1:
        r = {"status": "ok" if (results[0]["month"] and results[0]["day"]) else "unconfirmed",
             "chart": results[0], "conversion": conv}
        r["text"] = render(results[0], extra)
        if not (results[0]["month"] and results[0]["day"]):
            r["text"] += "\n⚠ 月建或日辰未给：旺衰、月破日破、暗动、旬空、六神、应期都暂不能断（00 十一）"
    else:
        r = {"status": "unconfirmed", "variants": results, "conversion": conv}
        texts = [f"—— 候选 {i + 1}：月建{x['month']}·日辰{x['day']} ——\n" + render(x, extra) for i, x in enumerate(results)]
        diff = _variant_diff(results)
        r["variant_diff"] = diff
        r["text"] = ("⚠ 起卦时间有边界未确认，下面分别列出各候选；结论一致可继续，不一致写双分支（00 十一）\n"
                     + "\n".join(texts) + "\n各候选间不同的触发：" + ("；".join(diff) or "无"))
    if conv and conv["warnings"]:
        r["text"] += "\n" + "\n".join("⚠ " + w for w in conv["warnings"])
    return r


def _variant_diff(results: list[dict]) -> list[str]:
    sets = [{(t["name"], t["where"]) for t in x["triggers"]} for x in results]
    common = set.intersection(*sets)
    out = []
    for i, s in enumerate(sets):
        for name, where in sorted(s - common):
            out.append(f"候选{i + 1}独有 {name}（{where}）")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="六爻装卦与核验（只算确定性数据）")
    ap.add_argument("--lines", help="爻值，自初至上：787896 或 '／ ／／ ○ × ／ ／'")
    ap.add_argument("--coins", help="铜钱，自初至上：字背背,字字背,…（须配 --coin-rule）")
    ap.add_argument("--coin-rule", choices=("本包", "背为阳"))
    ap.add_argument("--gua", help="本卦名，如 天火同人 / 同人")
    ap.add_argument("--moving", help="动爻位置，如 3 或 3,5")
    ap.add_argument("--to", help="变卦名（与 --gua 同用，自动推出动爻）")
    ap.add_argument("--month", help="月建：地支或干支")
    ap.add_argument("--day", help="日辰干支")
    ap.add_argument("--date", help="起卦公历时间，自动换算干支")
    ap.add_argument("--tz", default=None, help="起卦地钟表时间的 UTC 偏移，如 +08:00、+00:00；不给按 +08:00")
    ap.add_argument("--zi-rule", choices=("23", "00"))
    ap.add_argument("--yongshen", help="主用神（六亲名或 世爻/应爻），用于两现/伏神提示")
    ap.add_argument("--verify", help="截图读出的字段 JSON，输出差异清单")
    ap.add_argument("--verify-template", action="store_true", help="打印 --verify 用的 JSON 模板")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        r = run(a)
    except (PaipanError, ganzhi.GanzhiError, json.JSONDecodeError, OSError) as exc:
        r = {"status": "error", "reason": str(exc)}
    except Exception as exc:  # noqa: BLE001  任何意外都要落成明确的失败，不把 Python 报错直接甩出去
        r = {"status": "error", "reason": f"内部错误（{type(exc).__name__}: {exc}）；请检查输入格式"}
    if r.get("status") == "template":
        print(r["text"])
        return 0
    if a.json:
        print(json.dumps({k: v for k, v in r.items() if k != "text"}, ensure_ascii=False, indent=2))
    else:
        if r.get("status") == "error":
            print(f"装卦失败：{r['reason']}")
        else:
            if "diffs" in r:
                print(f"核验结果：{r['status']}")
                for d in r["diffs"]:
                    print(f"  [{d['kind']}] {d['field']}：截图 {d.get('shown', '—')}，本包 {d.get('computed', '—')}——{d['detail']}")
                if r.get("unconfirmed"):
                    print("  未确认（不补齐）：" + "、".join(r["unconfirmed"]))
                if r.get("advice"):
                    print("  " + r["advice"])
            if r.get("text"):
                print(r["text"])
    return {"error": 2}.get(r.get("status"), 0)


if __name__ == "__main__":
    sys.exit(main())
