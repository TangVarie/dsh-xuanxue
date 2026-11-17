#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
jev_extract_claims.py —— 用 Jev 做闭集抽取：解读 skill 的输出 → skill_claims_<skill>.json

  用法:
    python3 jev_extract_claims.py <报告.md> --skill career --out fixtures/<chart>/skill_claims_career.json
    python3 jev_extract_claims.py <报告.md> --skill career --out ... --baseline   # 不调 Jev，用字符串匹配基线
    python3 jev_extract_claims.py <报告.md> --skill career --dry-run              # 只打印要问的题，不调用
    python3 jev_extract_claims.py --check                                          # 只校验题库

  做法（每个字段一道闭集选择题）:
    1. 代码先把报告里相关的句子捞出来（带所在小节标题），整篇不塞给 Jev；
    2. 问 Jev：报告把 L10 说成了哪颗星？把 Saturn 的本命落座说成了哪个星座？……
       选项只有行星 / 星座 / 尊贵度 + 「未陈述」「前后不一」「其他说法」，编不出别的值；
    3. 第一名够高、领先够多 → 写进 claims；「未陈述」→ 不写；其余一律「待复核」，不写进 claims。

  覆盖字段: ak / d9_lagna / house_lords / planet_sign / planet_dignity。
  不覆盖 dasha（日期对 Jev 只是文字）：dasha 仍由 Claude 按 schema 抽，--keep-dasha 可保留输出文件里已有的 dasha。

  纪律: 抽取器看不到 canonical_facts，也看不到别的 skill 的 claims——只抽"这份报告说了什么"。

  输出:
    --out 指定的 skill_claims_<skill>.json（格式同 schema.md；带一个 _extractor 字段，check_consistency 会忽略）
    同目录下的 jev_review_<skill>.json：每个字段的判定、前三名概率、依据句子（待复核项在这里看）
    ⚠️ 复核文件故意不叫 skill_claims_*，免得被 check_consistency 的目录模式当成一份 claims。

  退出码: 0 完成且无待复核；3 完成但有待复核（claims 的 _extractor.pending 列出是哪几项）；
          4 没找到 Jev 密钥（未抽取）；2 输入错误；1 调用失败

  密钥: 环境变量 TYPESAFE_API_KEY → TYPESAFE_KEY_FILE 指向的文件 → ~/.config/typesafe/key
  模型: 题库里固定版本；JEV_MODEL 可覆盖。依赖: Python 3.9+、PyYAML；网络请求只用标准库。
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
BANK_PATH = HERE / "jev_claims_questions.yaml"
ENDPOINT = "/v1/systemone"
USER_AGENT = "vedic-consistency-eval-jev/0.1"
RETRY_STATUSES = {429, 500, 502, 503, 504}
CN_NUM = {1: "一", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六", 7: "七", 8: "八", 9: "九",
          10: "十", 11: "十一", 12: "十二"}


class JevError(Exception):
    pass


# ── 题库 ──────────────────────────────────────────────────────────────

def load_bank(path: Path = BANK_PATH) -> dict:
    try:
        import yaml  # noqa: PLC0415
    except ImportError as exc:
        raise JevError("缺 PyYAML，先 pip install pyyaml") from exc
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def check_bank(bank: dict) -> list[str]:
    problems = []
    planet_labels = [p["label"] for p in bank.get("planets", [])]
    if len(planet_labels) != len(set(planet_labels)):
        problems.append("planets 里 label 重复")
    for key in ("lord_planets", "ak_planets", "sign_planets", "dignity_planets"):
        for p in bank.get(key, []):
            if p not in planet_labels:
                problems.append(f"{key} 里的 {p} 不在 planets 里")
    ns = [s["n"] for s in bank.get("signs", [])]
    if ns != list(range(1, 13)):
        problems.append("signs 必须是 n=1..12 按顺序")
    dig = [d["label"] for d in bank.get("dignity", [])]
    if sorted(dig) != sorted(["Exalted", "Debilitated", "Own", "Other"]):
        problems.append("dignity 必须正好是 Exalted / Debilitated / Own / Other 四档（与 cutil 一致）")
    specials = [v.get("label") for v in (bank.get("special") or {}).values()]
    if len(specials) != 3 or len(set(specials)) != 3:
        problems.append("special 必须有三个不同的 label（未陈述 / 前后不一 / 其他说法）")
    overlap = set(specials) & (set(planet_labels) | {s["label"] for s in bank.get("signs", [])} | set(dig))
    if overlap:
        problems.append(f"特殊选项名与普通选项重名：{overlap}")
    d = bank.get("decision", {})
    if not (0 < d.get("min_top", 0) < 1 and 0 <= d.get("min_margin", -1) < 1):
        problems.append("decision.min_top / min_margin 应在 0 到 1 之间")
    for q in ("ak", "d9_lagna", "house_lord", "planet_sign", "planet_dignity"):
        if not (bank.get("questions", {}).get(q) or {}).get("zh"):
            problems.append(f"questions.{q} 缺 zh 题干")
    for name, pats in (bank.get("cues") or {}).items():
        for pat in pats:
            try:
                re.compile(pat)
            except re.error as exc:
                problems.append(f"cues.{name} 的正则写错了：{pat}（{exc}）")
    return problems


# "Neecha Bhanga"（陷落被抵消）里的 Neecha 不是在说句中那颗星陷落——实测会把充当抵消条件的星误判成落陷
_NOT_AFTER = {"Neecha": r"(?!\s*-?\s*Bhanga)"}


def _alias_regex(aliases: list[str]) -> re.Pattern:
    parts = []
    for a in sorted(aliases, key=len, reverse=True):
        if re.fullmatch(r"[A-Za-z ]+", a):
            parts.append(r"(?<![A-Za-z])" + re.escape(a) + r"(?![A-Za-z])" + _NOT_AFTER.get(a, ""))
        else:
            parts.append(re.escape(a))
    return re.compile("|".join(parts))


def _any_regex(patterns: list[str]) -> re.Pattern:
    return re.compile("|".join(f"(?:{p})" for p in patterns))


def house_lord_regex(n: int) -> re.Pattern:
    num = rf"(?<![0-9]){n}(?![0-9])"
    if n in (1, 2):
        cn = rf"(?<!十){CN_NUM[n]}"
    elif n == 10:
        cn = r"十(?![一二])"
    else:
        cn = CN_NUM[n]
    pats = [
        rf"(?<![A-Za-z0-9])L{n}(?![0-9])",
        rf"(?:第\s*)?{num}\s*宫\s*(?:的)?\s*宫?\s*主",
        rf"(?:第)?{cn}宫(?:的)?宫?主",
        rf"(?<![0-9]){n}(?:st|nd|rd|th)\s+(?:house\s+)?lord",
        rf"lord\s+of\s+(?:the\s+)?{n}(?:st|nd|rd|th)",
    ]
    return re.compile("|".join(pats), re.IGNORECASE)


# ── 切句 + 检索 ───────────────────────────────────────────────────────

_TABLE_SEP = re.compile(r"^\|?\s*:?-{2,}")


def split_units(text: str) -> list[dict]:
    """按行、按句切；记下每句所在的小节标题和所在行（同一行里的下一句可能用代词接着说）。
    表格行整行作一句，并带上表头（不然 "| L10 | Mars | 12 |" 看不出哪列是宫主）。"""
    units, heading, table_header, prev_was_row = [], "", "", False
    for line_no, line in enumerate(text.splitlines()):
        s = line.strip()
        if not s:
            prev_was_row = False
            continue
        if s.startswith("#"):
            heading, prev_was_row = s.lstrip("#").strip(), False
            continue
        if s.startswith("|"):
            if _TABLE_SEP.match(s):
                continue
            if not prev_was_row:
                table_header, prev_was_row = s, True
                continue
            units.append({"text": s, "heading": heading, "line": line_no, "table_header": table_header})
            continue
        prev_was_row = False
        for part in re.split(r"(?<=[。！？!?；;])|(?<=\.)\s+(?=[A-Z])", s):
            part = (part or "").strip()
            if part:
                units.append({"text": part, "heading": heading, "line": line_no})
    return units


class Retriever:
    def __init__(self, bank: dict):
        self.bank = bank
        self.planet = {p["label"]: _alias_regex(p["aliases"]) for p in bank["planets"]}
        self.planet_zh = {p["label"]: p["aliases"][1] for p in bank["planets"]}
        all_sign_aliases = [a for s in bank["signs"] for a in s["aliases"]]
        cues = bank["cues"]
        self.sign_cue = _any_regex([_alias_regex(all_sign_aliases).pattern] + cues["sign_word"])
        dig_aliases = [a for d in bank["dignity"] for a in d["aliases"]] + bank.get("dignity_extra_cues", [])
        self.dignity_cue = _alias_regex(dig_aliases)
        self.ak = _any_regex(cues["ak"])
        self.d9 = _any_regex(cues["d9"])
        self.lagna = _any_regex(cues["lagna"])
        self.pronoun = _any_regex(cues["pronoun_start"])
        self.house = {n: house_lord_regex(n) for n in range(1, 13)}

    def _cap(self, units: list[dict]) -> list[dict]:
        r = self.bank["retrieval"]
        out, seen = [], set()
        for u in units:
            key = (u["line"], u["text"])
            if key in seen:
                continue
            seen.add(key)
            out.append({**u, "text": u["text"][: r["max_chars_per_unit"]]})
        return out[: r["max_units"]]

    def ak_units(self, units):
        return self._cap([u for u in units if self.ak.search(u["text"])])

    def d9_units(self, units):
        hits = [u for u in units if self.lagna.search(u["text"])
                and (self.d9.search(u["text"]) or self.d9.search(u["heading"]))]
        return self._cap(hits)

    def house_units(self, units, n):
        return self._cap([u for u in units if self.house[n].search(u["text"])])

    DIGNITY_WINDOW = 20  # 尊贵度词必须紧挨着这颗星（前后 20 个字符内），防止把别的星的"陷落"算到它头上

    def _near(self, text: str, planet_rx, cue_rx, window: int) -> bool:
        for m in planet_rx.finditer(text):
            lo, hi = max(0, m.start() - window), min(len(text), m.end() + window)
            if cue_rx.search(text[lo:hi]):
                return True
        return False

    def planet_units(self, units, planet, kind):
        """kind = 'sign'：句子里有这颗星 + 任一星座词；kind = 'dignity'：尊贵度词紧挨着这颗星。
        同一行里紧跟着的代词句（"它落在 Aquarius，处于中性星座"）一起带上。"""
        rx = self.planet[planet]
        if kind == "sign":
            def has_cue(u):
                return bool(self.sign_cue.search(u["text"]))
            def own_hit(u):
                return has_cue(u)
        else:
            def has_cue(u):
                return bool(self.dignity_cue.search(u["text"]))
            def own_hit(u):
                return self._near(u["text"], rx, self.dignity_cue, self.DIGNITY_WINDOW)
        hits = []
        for i, u in enumerate(units):
            if not rx.search(u["text"]):
                continue
            if own_hit(u):
                hits.append(u)
            if i + 1 < len(units):
                nxt = units[i + 1]
                if nxt["line"] == u["line"] and self.pronoun.search(nxt["text"]) and has_cue(nxt):
                    hits += [u, nxt]
        return self._cap(hits)


# ── 出题 ──────────────────────────────────────────────────────────────

def _special_options(bank: dict, with_other: bool) -> dict:
    sp = bank["special"]
    opts = {sp["not_stated"]["label"]: sp["not_stated"]["zh"],
            sp["conflicting"]["label"]: sp["conflicting"]["zh"]}
    if with_other:
        opts[sp["other"]["label"]] = sp["other"]["zh"]
    return opts


def _planet_options(bank: dict, labels: list[str]) -> dict:
    by = {p["label"]: p for p in bank["planets"]}
    return {lab: f"{by[lab]['aliases'][1]}（{'、'.join(a for a in by[lab]['aliases'] if a != by[lab]['aliases'][1])}）"
            for lab in labels}


def _sign_options(bank: dict) -> dict:
    return {s["label"]: f"{s['aliases'][1]}座（{'、'.join(a for a in s['aliases'] if a != s['aliases'][1])}）"
            for s in bank["signs"]}


def _dignity_options(bank: dict) -> dict:
    return {d["label"]: d["zh"] for d in bank["dignity"]}


def build_state(units: list[dict]) -> dict:
    return {"说明": "以下句子摘自一份吠陀占星解读报告，方括号里是句子所在的小节标题。只根据这些句子判断。",
            "句子": [f"[{u['heading'] or '无标题'}] "
                     + (f"（表头 {u['table_header']}）" if u.get("table_header") else "") + u["text"]
                     for u in units]}


def plan_tasks(text: str, bank: dict) -> tuple[list[dict], list[dict]]:
    """返回 (要问的任务, 没有候选句子的字段)。每个任务 = 一次调用：同一批句子 + 一到两道题。"""
    rt = Retriever(bank)
    units = split_units(text)
    qz = bank["questions"]
    tasks, absent = [], []

    def add(task_id, found, questions, fields):
        if found:
            tasks.append({"id": task_id, "units": found, "state": build_state(found),
                          "questions": questions, "fields": fields})
        else:
            absent.extend(fields)

    found = rt.ak_units(units)
    add("ak", found,
        {"ak": {"type": "choice", "instructions": qz["ak"]["zh"],
                "criteria": {**_planet_options(bank, bank["ak_planets"]), **_special_options(bank, True)}}},
        [{"field": "ak", "key": None, "q": "ak", "kind": "planet"}])

    found = rt.d9_units(units)
    add("d9_lagna", found,
        {"d9_lagna": {"type": "choice", "instructions": qz["d9_lagna"]["zh"],
                      "criteria": {**_sign_options(bank), **_special_options(bank, False)}}},
        [{"field": "d9_lagna", "key": None, "q": "d9_lagna", "kind": "sign"}])

    for n in range(1, 13):
        found = rt.house_units(units, n)
        add(f"house_lords.{n}", found,
            {"lord": {"type": "choice", "instructions": qz["house_lord"]["zh"].format(n=n),
                      "criteria": {**_planet_options(bank, bank["lord_planets"]), **_special_options(bank, True)}}},
            [{"field": "house_lords", "key": str(n), "q": "lord", "kind": "planet"}])

    for planet in bank["sign_planets"]:
        fmt = {"planet": planet, "planet_zh": rt.planet_zh[planet]}
        add(f"planet_sign.{planet}", rt.planet_units(units, planet, "sign"),
            {"sign": {"type": "choice", "instructions": qz["planet_sign"]["zh"].format(**fmt),
                      "criteria": {**_sign_options(bank), **_special_options(bank, False)}}},
            [{"field": "planet_sign", "key": planet, "q": "sign", "kind": "sign"}])
        if planet in bank["dignity_planets"]:
            add(f"planet_dignity.{planet}", rt.planet_units(units, planet, "dignity"),
                {"dignity": {"type": "choice", "instructions": qz["planet_dignity"]["zh"].format(**fmt),
                             "criteria": {**_dignity_options(bank), **_special_options(bank, False)}}},
                [{"field": "planet_dignity", "key": planet, "q": "dignity", "kind": "dignity"}])
    return tasks, absent


# ── 两种引擎 ──────────────────────────────────────────────────────────

def find_api_key() -> str | None:
    key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if key:
        return key
    paths = []
    if os.environ.get("TYPESAFE_KEY_FILE"):
        paths.append(Path(os.environ["TYPESAFE_KEY_FILE"]).expanduser())
    paths.append(Path.home() / ".config" / "typesafe" / "key")
    for p in paths:
        try:
            text = p.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if text:
            return text
    return None


def _retry_wait(headers, attempt: int) -> float:
    for name, scale in (("retry-after-ms", 0.001), ("retry-after", 1.0)):
        raw = headers.get(name) if headers else None
        if raw:
            try:
                return min(float(raw) * scale, 30.0)
            except ValueError:
                pass
    return min(0.5 * (2 ** attempt), 8.0)


class JevEngine:
    name = "jev"

    def __init__(self, api_key: str, model: str, timeout: float = 20.0, retries: int = 3):
        self.key, self.model, self.timeout, self.retries = api_key, model, timeout, retries
        self.base = os.environ.get("TYPESAFE_BASE_URL", "https://api.typesafe.ai").rstrip("/")

    def ask(self, task: dict) -> dict:
        body = {"state": task["state"], "model": self.model, "questions": task["questions"]}
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers = {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json",
                   "Accept": "application/json", "User-Agent": USER_AGENT}
        last = "未知错误"
        for attempt in range(self.retries + 1):
            req = urllib.request.Request(self.base + ENDPOINT, data=data, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                    return {"model": payload.get("model"), "answers": payload.get("answers") or {}}
            except urllib.error.HTTPError as exc:
                text = exc.read().decode("utf-8", "replace").strip().replace("\n", " ")[:300]
                if exc.code in RETRY_STATUSES and attempt < self.retries:
                    time.sleep(_retry_wait(exc.headers, attempt))
                    continue
                hint = "（检查 TYPESAFE_API_KEY）" if exc.code in (401, 403) else ""
                raise JevError(f"Jev 返回 HTTP {exc.code}{hint}：{text}") from exc
            except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError) as exc:
                last = f"连不上 Jev：{getattr(exc, 'reason', exc)}"
                if attempt < self.retries:
                    time.sleep(_retry_wait(None, attempt))
                    continue
                raise JevError(last) from exc
        raise JevError(last)


class BaselineEngine:
    """字符串匹配基线：候选句子里只出现一个选项 → 选它；没出现 → 未陈述；出现多个 → 前后不一。
    它不懂假设、否定、D9 与 D1、AK 与 AmK——是 Jev 必须赢过的下限，也用来在没有密钥时测流程。"""
    name = "baseline"

    def __init__(self, bank: dict):
        self.bank = bank
        self.planet_rx = {p["label"]: _alias_regex(p["aliases"]) for p in bank["planets"]}
        self.sign_rx = {s["label"]: _alias_regex(s["aliases"]) for s in bank["signs"]}
        self.dig_rx = {d["label"]: _alias_regex(d["aliases"]) for d in bank["dignity"]}
        self.sp = bank["special"]

    def ask(self, task: dict) -> dict:
        text = "\n".join(u["text"] for u in task["units"])
        answers = {}
        for f in task["fields"]:
            q = task["questions"][f["q"]]
            options = [o for o in q["criteria"] if o not in {v["label"] for v in self.sp.values()}]
            pool = {"planet": self.planet_rx, "sign": self.sign_rx, "dignity": self.dig_rx}[f["kind"]]
            hits = [o for o in options if pool[o].search(text)]
            if not hits:
                choice = self.sp["not_stated"]["label"]
            elif len(hits) == 1:
                choice = hits[0]
            else:
                choice = self.sp["conflicting"]["label"]
            answers[f["q"]] = {"type": "choice", "choice": choice, "confidence": 1.0,
                               "probabilities": {choice: 1.0}}
        return {"model": "baseline", "answers": answers}


# ── 判定 ──────────────────────────────────────────────────────────────

def decide(answer: dict | None, bank: dict) -> dict:
    sp = bank["special"]
    d = bank["decision"]
    if not answer:
        return {"status": "needs_review", "answer": None, "top3": [], "why": "没有返回这题"}
    probs = sorted(((k, float(v)) for k, v in (answer.get("probabilities") or {}).items()),
                   key=lambda kv: -kv[1])
    top = answer.get("choice") or (probs[0][0] if probs else None)
    p1 = probs[0][1] if probs else 0.0
    p2 = probs[1][1] if len(probs) > 1 else 0.0
    top3 = [[k, round(v, 3)] for k, v in probs[:3]]
    if p1 < d["min_top"] or p1 - p2 < d["min_margin"]:
        return {"status": "needs_review", "answer": top, "top3": top3,
                "why": f"第一名 {p1:.2f}，领先 {p1 - p2:.2f}（门槛 {d['min_top']} / {d['min_margin']}）"}
    if top == sp["not_stated"]["label"]:
        return {"status": "not_stated", "answer": top, "top3": top3, "why": ""}
    if top in (sp["conflicting"]["label"], sp["other"]["label"]):
        return {"status": "needs_review", "answer": top, "top3": top3, "why": f"选了「{top}」"}
    return {"status": "claimed", "answer": top, "top3": top3, "why": ""}


def extract(text: str, skill: str, engine, bank: dict, workers: int = 6) -> tuple[dict, list[dict], dict]:
    """返回 (claims, 逐字段记录, 元信息)。claims 只含判为 claimed 的字段。"""
    tasks, absent = plan_tasks(text, bank)
    sign_n = {s["label"]: s["n"] for s in bank["signs"]}
    results: dict[str, dict] = {}
    if isinstance(engine, JevEngine) and len(tasks) > 1:
        with cf.ThreadPoolExecutor(max_workers=workers) as pool:
            futs = {pool.submit(engine.ask, t): t["id"] for t in tasks}
            for fut in cf.as_completed(futs):
                results[futs[fut]] = fut.result()
    else:
        for t in tasks:
            results[t["id"]] = engine.ask(t)

    claims: dict = {"skill": skill}
    records: list[dict] = []
    models = set()
    for t in tasks:
        res = results[t["id"]]
        models.add(res.get("model"))
        for f in t["fields"]:
            verdict = decide(res["answers"].get(f["q"]), bank)
            records.append({"field": f["field"], "key": f["key"], **verdict,
                            "evidence": [s for s in t["state"]["句子"]]})
            if verdict["status"] != "claimed":
                continue
            value = verdict["answer"]
            if f["kind"] == "sign":
                value = sign_n[value]
            if f["key"] is None:
                claims[f["field"]] = value
            else:
                claims.setdefault(f["field"], {})[f["key"]] = value
    for f in absent:
        records.append({"field": f["field"], "key": f["key"], "status": "not_mentioned",
                        "answer": None, "top3": [], "why": "报告里没有相关句子", "evidence": []})
    pending = [f"{r['field']}.{r['key']}" if r["key"] else r["field"]
               for r in records if r["status"] == "needs_review"]
    meta = {"engine": engine.name, "models": sorted(m for m in models if m),
            "bank_version": bank.get("bank_version"), "calls": len(tasks),
            "pending_review": len(pending), "pending": pending}
    return claims, records, meta


# ── 命令行 ────────────────────────────────────────────────────────────

def _summary(records: list[dict]) -> str:
    counts = {}
    for r in records:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    names = {"claimed": "写入", "needs_review": "待复核", "not_stated": "未陈述", "not_mentioned": "未提及"}
    return "，".join(f"{names[k]} {counts[k]}" for k in names if k in counts)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Jev 闭集抽取 → skill_claims_<skill>.json")
    ap.add_argument("report", nargs="?", help="解读 skill 的输出（markdown / 文本）")
    ap.add_argument("--skill", choices=("core", "career", "love", "soul"))
    ap.add_argument("--out", help="输出的 skill_claims_<skill>.json 路径")
    ap.add_argument("--baseline", action="store_true", help="不调 Jev，用字符串匹配基线（只用于对照和测流程）")
    ap.add_argument("--dry-run", action="store_true", help="只打印要问的题，不调用")
    ap.add_argument("--keep-dasha", action="store_true", help="输出文件已存在且带 dasha 时保留它")
    ap.add_argument("--check", action="store_true", help="只校验题库")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--timeout", type=float, default=20.0)
    args = ap.parse_args(argv)

    try:
        bank = load_bank()
    except (JevError, OSError) as exc:
        print(f"题库读不了：{exc}", file=sys.stderr)
        return 2
    if args.check:
        problems = check_bank(bank)
        if problems:
            print("题库有问题：\n  " + "\n  ".join(problems), file=sys.stderr)
            return 2
        print(f"题库 {bank['bank_version']} 通过（模型 {bank['model']}；判定门槛 "
              f"{bank['decision']['min_top']} / {bank['decision']['min_margin']}）")
        return 0

    if not args.report or not args.skill:
        ap.error("需要 <报告> 和 --skill（或 --check）")
    try:
        text = Path(args.report).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"读不了报告：{exc}", file=sys.stderr)
        return 2

    if args.dry_run:
        tasks, absent = plan_tasks(text, bank)
        print(json.dumps({"calls": len(tasks), "no_candidates": [f"{a['field']}.{a['key']}" if a["key"] else a["field"] for a in absent],
                          "tasks": [{"id": t["id"], "state": t["state"], "questions": list(t["questions"])} for t in tasks]},
                         ensure_ascii=False, indent=2))
        return 0

    if not args.out:
        ap.error("需要 --out")
    if args.baseline:
        engine = BaselineEngine(bank)
    else:
        key = find_api_key()
        if not key:
            print("没有找到 Jev 密钥（TYPESAFE_API_KEY 等），未抽取。可改用 Claude 按 schema 抽，或加 --baseline 只测流程。",
                  file=sys.stderr)
            return 4
        engine = JevEngine(key, os.environ.get("JEV_MODEL") or bank["model"], timeout=args.timeout)

    try:
        claims, records, meta = extract(text, args.skill, engine, bank, workers=args.workers)
    except JevError as exc:
        print(f"抽取失败：{exc}", file=sys.stderr)
        return 1

    out = Path(args.out)
    if args.keep_dasha and out.exists():
        try:
            old = json.loads(out.read_text(encoding="utf-8"))
            if old.get("dasha"):
                claims["dasha"] = old["dasha"]
        except (OSError, json.JSONDecodeError):
            pass
    claims["_extractor"] = {**meta, "source": str(args.report)}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(claims, ensure_ascii=False, indent=2), encoding="utf-8")
    review_path = out.parent / f"jev_review_{args.skill}.json"
    review_path.write_text(json.dumps({"skill": args.skill, **meta, "fields": records},
                                      ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[{meta['engine']}] {args.skill}：{_summary(records)}；调用 {meta['calls']} 次")
    print(f"  claims → {out}")
    print(f"  复核文件 → {review_path}")
    if meta["pending_review"]:
        print(f"  ⚠️ 有 {meta['pending_review']} 项待复核（没写进 claims）：{', '.join(meta['pending'])}")
        print("     看复核文件里的依据句子，确认后把值手动写进 claims，再从 _extractor.pending 里删掉那一项；"
              "pending 没清空之前，check_consistency 不会给 PASS。")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
