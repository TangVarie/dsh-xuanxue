#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""六爻来意预判（乙类）· 调用 Jev（可选组件）

只看来意摘要，不看卦盘；在看盘之前跑。题目在 references/21_Jev判断题.yaml，
用法见 references/00 第 0.6 节、references/20 第二节。

用法
  python scripts/jev_judge.py case.json             调 Jev，结果 JSON 打到标准输出
  python scripts/jev_judge.py - < case.json         从标准输入读
  python scripts/jev_judge.py case.json --mock      不联网，出格式相同的假结果（只测流程）
  python scripts/jev_judge.py case.json --dry-run   只打印将要发送的请求体，不发送
  python scripts/jev_judge.py case.json --lang en   用英文题干（对比中英文效果用）
  python scripts/jev_judge.py --check               只校验题库

case.json 只接受这四个字段（其余一律拒收）
  来意摘要     必填  模型写的来意摘要：谁测、测什么、关心哪一面、动机、时限。
                     不含卦名、爻象、干支、动爻等任何卦盘信息——含了就拒收（chart_in_input）
  追问补充     可选  追问后补充的话（动机、关系、时限等），同样不能含卦盘
  求测者性别   可选  男 / 女 / 未知
  关系         可选  本人 / 代测 / 双方 / 未知

输出（永远是一个 JSON 对象，不抛异常）
  status   ok / mock / skipped / error
  usable   只有 status=ok 时为 true；其余一律当"没有预判"，转人工判断（20 第二节）
  error_code（status 为 error 或 skipped 时）：
           bad_input          case 不合法（缺字段、多字段、类型不对）
           chart_in_input     来意里含卦盘信息
           no_key             没有找到密钥（status=skipped）
           no_yaml            缺 PyYAML，读不了题库（status=skipped）
           bank_invalid       题库读不了或校验不过
           http_error         Jev 返回非 2xx
           network            连不上、读到一半断开
           timeout_budget     重试用完了总时长上限
           invalid_response   返回结构不对：缺题、题型不符、选项不在题库里、概率越界或总和不对、答案与概率不一致
           internal           脚本自身出错（已捕获）
  answers / ambiguous_items / next_actions  只在 ok 与 mock 时给出

密钥（按顺序找；都没有就 status=skipped，skill 照常断卦，不追问密钥）
  1. 环境变量 TYPESAFE_API_KEY  2. TYPESAFE_KEY_FILE 指向的文件  3. ~/.config/typesafe/key
其他环境变量
  JEV_MODEL           覆盖题库里固定的模型版本（默认不用 jev-latest，免得答案随版本漂）
  TYPESAFE_BASE_URL   默认 https://api.typesafe.ai
依赖：Python 3.9+，PyYAML（读题库）。网络请求只用标准库。
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import math
import os
import random
import re
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
BANK_PATH = SKILL_DIR / "references" / "21_Jev判断题.yaml"
ENDPOINT = "/v1/systemone"
USER_AGENT = "liuyao-core-jev-judge/0.2"

ALLOWED_FIELDS = ("来意摘要", "追问补充", "求测者性别", "关系")
REQUIRED_FIELD = "来意摘要"
FIELD_VALUES = {"求测者性别": ("男", "女", "未知"), "关系": ("本人", "代测", "双方", "未知")}
STATE_KEYS_EN = {"来意摘要": "request_summary", "追问补充": "follow_up",
                 "求测者性别": "asker_gender", "关系": "relation"}
RETRY_STATUSES = {429, 500, 502, 503, 504}
MAX_TEXT = 2000

DEFAULT_TIMEOUT = 15.0        # 单次请求
DEFAULT_TOTAL_TIMEOUT = 25.0  # 含重试的总时长上限
DEFAULT_RETRIES = 2
PROB_SUM_TOL = 0.05
CONF_TOL = 0.02


class JevError(Exception):
    """调用失败。code 是机器可读的错误码，message 给人读。"""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


# ── 卦盘信息检测（来意里不许出现）─────────────────────────────────────

_GUA_FULL = [
    "乾为天", "天风姤", "天山遁", "天山遯", "天地否", "风地观", "山地剥", "火地晋", "火天大有",
    "坎为水", "水泽节", "水雷屯", "水火既济", "泽火革", "雷火丰", "地火明夷", "地水师",
    "艮为山", "山火贲", "山天大畜", "山泽损", "火泽睽", "天泽履", "风泽中孚", "风山渐",
    "震为雷", "雷地豫", "雷水解", "雷风恒", "地风升", "水风井", "泽风大过", "泽雷随",
    "巽为风", "风天小畜", "风火家人", "风雷益", "天雷无妄", "火雷噬嗑", "山雷颐", "山风蛊",
    "离为火", "火山旅", "火风鼎", "火水未济", "山水蒙", "风水涣", "天水讼", "天火同人",
    "坤为地", "地雷复", "地泽临", "地天泰", "雷天大壮", "泽天夬", "水天需", "水地比",
    "兑为泽", "泽水困", "泽地萃", "泽山咸", "水山蹇", "地山谦", "雷山小过", "雷泽归妹",
    # 不会在日常话里出现的简称
    "噬嗑", "明夷", "归妹", "中孚", "既济", "未济", "小畜", "无妄", "大畜",
]
_CHART_PATTERNS = [
    (re.compile("|".join(map(re.escape, _GUA_FULL))), "卦名"),
    (re.compile(r"[初一二三四五六上]爻|第[一二三四五六初上]爻|[九六][二三四五]|初[九六]|上[九六]"), "爻位"),
    (re.compile(r"动爻|静爻|变爻|世爻|应爻|本卦|变卦|之卦|伏神|飞神|旬空|月建|日辰|日建|用神|原神|忌神|六神|纳甲"), "卦盘术语"),
    (re.compile(r"老阳|老阴|少阳|少阴|[○×／]|字背|背字"), "爻象"),
    (re.compile(r"[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥][年月日时]"), "起卦干支"),
    (re.compile(r"[子丑寅卯辰巳午未申酉戌亥][水木火土金](?:父母|兄弟|子孙|妻财|官鬼)"), "爻支六亲"),
]


def find_chart_markers(text: str) -> list[str]:
    hits = []
    for pat, kind in _CHART_PATTERNS:
        for m in pat.finditer(text):
            hits.append(f"{kind}「{m.group(0)}」")
    return hits


# ── 题库 ──────────────────────────────────────────────────────────────

def load_bank(path: Path = BANK_PATH) -> dict:
    try:
        import yaml  # noqa: PLC0415
    except ImportError as exc:
        raise JevError("no_yaml", "缺 PyYAML，先 pip install pyyaml") from exc
    try:
        with open(path, encoding="utf-8") as fh:
            bank = yaml.safe_load(fh)
    except (OSError, yaml.YAMLError) as exc:
        raise JevError("bank_invalid", f"题库读不了：{exc}") from exc
    if not isinstance(bank, dict):
        raise JevError("bank_invalid", "题库顶层不是映射")
    return bank


def check_bank(bank: dict) -> list[str]:
    """返回问题清单；空列表 = 题库没问题。"""
    problems: list[str] = []
    qs = bank.get("questions")
    if not isinstance(qs, list) or not qs:
        return ["questions 不是非空列表"]
    ids = [q.get("id") for q in qs if isinstance(q, dict)]
    if len(ids) != len(qs):
        problems.append("questions 里有非映射项")
    if len(ids) != len(set(ids)):
        problems.append("题目 id 有重复")
    amb = bank.get("ambiguity") or {}
    if not 0 < (amb.get("choice_top_min") or 0) < 1:
        problems.append("ambiguity.choice_top_min 应在 0 到 1 之间")
    if not 0 <= (amb.get("choice_margin_min") if amb.get("choice_margin_min") is not None else -1) < 1:
        problems.append("ambiguity.choice_margin_min 应在 0 到 1 之间")
    band = amb.get("noul_band") or []
    if len(band) != 2 or not 0 <= band[0] < band[1] <= 1:
        problems.append("ambiguity.noul_band 应是 [下限, 上限]，且 0 ≤ 下限 < 上限 ≤ 1")
    for q in qs:
        if not isinstance(q, dict):
            continue
        qid = q.get("id", "?")
        for key in ("type", "instructions", "feeds", "on_ambiguous"):
            if key not in q:
                problems.append(f"{qid}: 缺 {key}")
        for lang in ("zh", "en"):
            if not (q.get("instructions") or {}).get(lang):
                problems.append(f"{qid}: instructions 缺 {lang}")
        if q.get("type") == "choice":
            labels = [o.get("label") for o in q.get("options", [])]
            if len(labels) < 2:
                problems.append(f"{qid}: 选项少于 2 个")
            if len(labels) != len(set(labels)):
                problems.append(f"{qid}: 选项名重复")
            for opt in q.get("options", []):
                for lang in ("zh", "en"):
                    if not opt.get(lang):
                        problems.append(f"{qid}/{opt.get('label')}: 缺 {lang} 定义")
            for lab in q.get("unclear_labels", []) or []:
                if lab not in labels:
                    problems.append(f"{qid}: unclear_labels 里的「{lab}」不是选项")
        elif q.get("type") == "noul":
            crit = q.get("criteria") or {}
            for side in ("true", "false"):
                for lang in ("zh", "en"):
                    if not (crit.get(side) or {}).get(lang):
                        problems.append(f"{qid}: criteria.{side} 缺 {lang}")
        else:
            problems.append(f"{qid}: type 只能是 choice 或 noul")
    return problems


# ── 组请求 ────────────────────────────────────────────────────────────

def validate_case(case) -> dict:
    """返回清洗后的 case；不合法抛 JevError(bad_input / chart_in_input)。"""
    if not isinstance(case, dict):
        raise JevError("bad_input", "case 必须是 JSON 对象")
    extra = [k for k in case if k not in ALLOWED_FIELDS]
    if extra:
        hint = "（旧字段「来意原话」已停用：先写来意摘要，不含卦盘）" if "来意原话" in extra else ""
        raise JevError("bad_input", f"只接受 {', '.join(ALLOWED_FIELDS)}；拒收：{', '.join(extra)}{hint}")
    clean = {}
    for k in ALLOWED_FIELDS:
        v = case.get(k)
        if v is None:
            continue
        if not isinstance(v, str):
            raise JevError("bad_input", f"「{k}」必须是字符串")
        v = v.strip()
        if not v:
            continue
        if len(v) > MAX_TEXT:
            raise JevError("bad_input", f"「{k}」超过 {MAX_TEXT} 字，请压缩成摘要")
        if k in FIELD_VALUES and v not in FIELD_VALUES[k]:
            raise JevError("bad_input", f"「{k}」只能是 {'/'.join(FIELD_VALUES[k])}")
        clean[k] = v
    if REQUIRED_FIELD not in clean:
        raise JevError("bad_input", f"缺「{REQUIRED_FIELD}」")
    hits = [h for k in ("来意摘要", "追问补充") if k in clean for h in find_chart_markers(clean[k])]
    if hits:
        raise JevError("chart_in_input", "来意里含卦盘信息，按纪律不传给 Jev："
                       + "、".join(dict.fromkeys(hits)) + "。请重写来意摘要，只留谁测、测什么、关心哪一面、动机、时限")
    return clean


def build_state(case: dict, lang: str) -> dict:
    if lang == "en":
        return {STATE_KEYS_EN[k]: v for k, v in case.items()}
    return dict(case)


def build_questions(bank: dict, lang: str) -> dict:
    questions = {}
    for q in bank["questions"]:
        if q["type"] == "choice":
            questions[q["id"]] = {"type": "choice", "instructions": q["instructions"][lang],
                                  "criteria": {o["label"]: o[lang] for o in q["options"]}}
        else:
            questions[q["id"]] = {"type": "noul", "instructions": q["instructions"][lang],
                                  "criteria": {"true": q["criteria"]["true"][lang],
                                               "false": q["criteria"]["false"][lang]}}
    return questions


def build_body(case: dict, bank: dict, lang: str) -> dict:
    model = os.environ.get("JEV_MODEL") or bank.get("model") or "jev-latest"
    return {"state": build_state(case, lang), "model": model, "questions": build_questions(bank, lang)}


# ── 调用 ──────────────────────────────────────────────────────────────

def find_api_key() -> str | None:
    key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if key:
        return key
    candidates = []
    if os.environ.get("TYPESAFE_KEY_FILE"):
        candidates.append(Path(os.environ["TYPESAFE_KEY_FILE"]).expanduser())
    candidates.append(Path.home() / ".config" / "typesafe" / "key")
    for path in candidates:
        try:
            text = path.read_text(encoding="utf-8").strip()
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
                return max(0.0, min(float(raw) * scale, 30.0))
            except ValueError:
                pass
    return min(0.5 * (2 ** attempt), 8.0)


def _explain_http(status: int, text: str) -> str:
    snippet = text.strip().replace("\n", " ")[:300]
    if status in (401, 403):
        return f"鉴权失败（HTTP {status}）：检查 TYPESAFE_API_KEY。{snippet}"
    if status == 404:
        return f"找不到接口或模型（HTTP 404）：检查 JEV_MODEL / TYPESAFE_BASE_URL。{snippet}"
    if status in (400, 422):
        return f"请求被拒（HTTP {status}），多半是题库格式问题：{snippet}"
    if status == 429:
        return f"限流（HTTP 429），重试后仍失败：{snippet}"
    return f"Jev 返回 HTTP {status}：{snippet}"


def call_jev(body: dict, api_key: str, timeout: float = DEFAULT_TIMEOUT, retries: int = DEFAULT_RETRIES,
             total_timeout: float = DEFAULT_TOTAL_TIMEOUT, *, _urlopen=urllib.request.urlopen,
             _sleep=time.sleep, _clock=time.monotonic) -> dict:
    """调 Jev。所有失败都转成 JevError；总时长（含重试与等待）不超过 total_timeout。"""
    base = os.environ.get("TYPESAFE_BASE_URL", "https://api.typesafe.ai").rstrip("/")
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
               "Accept": "application/json", "User-Agent": USER_AGENT}
    deadline = _clock() + total_timeout
    last = JevError("network", "未知错误")
    for attempt in range(retries + 1):
        remaining = deadline - _clock()
        if remaining <= 0.5:
            raise JevError("timeout_budget", f"已用完总时长上限 {total_timeout:.0f} 秒；最后一次错误：{last}")
        req = urllib.request.Request(base + ENDPOINT, data=data, headers=headers, method="POST")
        wait = None
        try:
            with _urlopen(req, timeout=min(timeout, remaining)) as resp:
                raw = resp.read()
            try:
                return json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise JevError("invalid_response", "Jev 返回的不是 JSON") from exc
        except JevError:
            raise
        except urllib.error.HTTPError as exc:
            try:
                text = exc.read().decode("utf-8", "replace")
            except Exception:  # noqa: BLE001
                text = ""
            last = JevError("http_error", _explain_http(exc.code, text))
            if exc.code not in RETRY_STATUSES:
                raise last from exc
            wait = _retry_wait(exc.headers, attempt)
        except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError,
                http.client.HTTPException, OSError) as exc:
            last = JevError("network", f"连不上 Jev：{getattr(exc, 'reason', exc)}")
            wait = _retry_wait(None, attempt)
        if attempt < retries:
            remaining = deadline - _clock()
            if wait >= remaining:
                raise JevError("timeout_budget", f"下次重试需等 {wait:.1f} 秒，超出总时长上限；最后一次错误：{last}")
            _sleep(wait)
    raise last


def mock_response(body: dict) -> dict:
    """确定性的假结果：同一来意永远同一答案。数字没有意义，只用来测流程。"""
    seed = hashlib.sha256(json.dumps(body["state"], ensure_ascii=False, sort_keys=True)
                          .encode("utf-8")).hexdigest()
    rnd = random.Random(int(seed, 16))
    answers = {}
    for name, q in body["questions"].items():
        if q["type"] == "choice":
            labels = list(q["criteria"])
            weights = [rnd.random() ** 3 + 1e-9 for _ in labels]
            total = sum(weights)
            probs = {lab: w / total for lab, w in zip(labels, weights)}
            top = max(probs, key=probs.get)
            answers[name] = {"type": "choice", "choice": top, "confidence": probs[top], "probabilities": probs}
        else:
            answers[name] = {"type": "noul", "noul": rnd.random()}
    return {"model": "mock", "answers": answers, "usage": {"input_tokens": 0, "output_tokens": 0}}


# ── 校验与解读 ────────────────────────────────────────────────────────

def _num(x) -> float | None:
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return None
    x = float(x)
    return x if math.isfinite(x) else None


def validate_response(resp, bank: dict) -> list[str]:
    """返回问题清单；空列表 = 结构可用。任何一题有问题，整份结果都不用。"""
    if not isinstance(resp, dict):
        return [f"返回的顶层不是对象（{type(resp).__name__}）"]
    answers = resp.get("answers")
    if not isinstance(answers, dict):
        return ["缺 answers 对象"]
    problems: list[str] = []
    for q in bank["questions"]:
        qid = q["id"]
        ans = answers.get(qid)
        if ans is None:
            problems.append(f"{qid}：缺题")
            continue
        if not isinstance(ans, dict):
            problems.append(f"{qid}：答案不是对象")
            continue
        if ans.get("type") != q["type"]:
            problems.append(f"{qid}：题型应为 {q['type']}，返回 {ans.get('type')!r}")
            continue
        if q["type"] == "choice":
            labels = [o["label"] for o in q["options"]]
            choice = ans.get("choice")
            if choice not in labels:
                problems.append(f"{qid}：选项 {choice!r} 不在题库里")
            probs = ans.get("probabilities")
            if not isinstance(probs, dict) or not probs:
                problems.append(f"{qid}：缺 probabilities")
                continue
            bad_keys = [k for k in probs if k not in labels]
            if bad_keys:
                problems.append(f"{qid}：probabilities 里有题库外的选项 {bad_keys}")
            vals = {k: _num(v) for k, v in probs.items()}
            if any(v is None or not 0 <= v <= 1 for v in vals.values()):
                problems.append(f"{qid}：概率不是 0～1 之间的数")
                continue
            s = sum(vals.values())
            if s > 1 + PROB_SUM_TOL or (len(vals) == len(labels) and s < 1 - PROB_SUM_TOL):
                problems.append(f"{qid}：概率总和 {s:.3f} 不对")
            if choice in vals and vals[choice] + 1e-6 < max(vals.values()):
                problems.append(f"{qid}：答案 {choice} 不是概率最高的选项")
            if choice in labels and choice not in vals:
                problems.append(f"{qid}：答案 {choice} 没有概率")
            conf = ans.get("confidence")
            if conf is not None:
                c = _num(conf)
                if c is None or not 0 <= c <= 1:
                    problems.append(f"{qid}：confidence 不是 0～1 之间的数")
                elif choice in vals and abs(c - vals[choice]) > CONF_TOL:
                    problems.append(f"{qid}：confidence {c:.3f} 与答案概率 {vals[choice]:.3f} 不一致")
        else:
            p = _num(ans.get("noul"))
            if p is None or not 0 <= p <= 1:
                problems.append(f"{qid}：noul 不是 0～1 之间的数（{ans.get('noul')!r}）")
    return problems


def interpret(resp: dict, bank: dict) -> tuple[dict, list[str], list[str]]:
    """（已通过校验的）Jev 答案 → 每题的答案 + 是否歧义 + 该做什么。"""
    amb = bank["ambiguity"]
    lo, hi = amb["noul_band"]
    items: dict = {}
    ambiguous: list[str] = []
    actions: list[str] = []
    for q in bank["questions"]:
        qid = q["id"]
        ans = resp["answers"][qid]
        if q["type"] == "choice":
            probs = sorted(((k, float(v)) for k, v in ans["probabilities"].items()), key=lambda kv: -kv[1])
            p1 = probs[0][1]
            p2 = probs[1][1] if len(probs) > 1 else 0.0
            reasons = []
            if p1 < amb["choice_top_min"]:
                reasons.append(f"第一名 {p1:.2f} < {amb['choice_top_min']}")
            if p1 - p2 < amb["choice_margin_min"]:
                reasons.append(f"前两名只差 {p1 - p2:.2f}")
            if ans["choice"] in (q.get("unclear_labels") or []):
                reasons.append(f"选了「{ans['choice']}」")
            item = {"type": "choice", "answer": ans["choice"],
                    "top3": [[k, round(v, 3)] for k, v in probs[:3]], "confidence": round(p1, 3)}
        else:
            p = float(ans["noul"])
            reasons = [f"概率 {p:.2f} 落在 {lo}–{hi}"] if lo <= p <= hi else []
            item = {"type": "noul", "p_true": round(p, 3), "answer": p > 0.5}
            if not reasons and p <= 0.5 and q.get("on_false"):
                actions.append(f"{qid}：{q['on_false']}")
        item.update({"ambiguous": bool(reasons), "why": "；".join(reasons),
                     "feeds": q["feeds"], "on_ambiguous": q["on_ambiguous"]})
        if reasons:
            ambiguous.append(qid)
            actions.append(f"{qid}：{q['on_ambiguous']}")
        items[qid] = item
    return items, ambiguous, actions


def _fail(base: dict, status: str, code: str, reason: str, **extra) -> dict:
    return {**base, "status": status, "usable": False, "error_code": code, "reason": reason, **extra}


def judge(case, *, lang: str = "zh", mock: bool = False, timeout: float = DEFAULT_TIMEOUT,
          total_timeout: float = DEFAULT_TOTAL_TIMEOUT, retries: int = DEFAULT_RETRIES,
          bank: dict | None = None, _call=None) -> dict:
    """对一条来意跑预判。永远返回 dict，不抛异常；只有 status=ok（usable=true）能用。"""
    base: dict = {"lang": lang, "bank_version": None}
    try:
        if bank is None:
            try:
                bank = load_bank()
            except JevError as exc:
                return _fail(base, "skipped" if exc.code == "no_yaml" else "error", exc.code, str(exc))
        base["bank_version"] = bank.get("bank_version")
        problems = check_bank(bank)
        if problems:
            return _fail(base, "error", "bank_invalid", "题库校验不过：" + "；".join(problems[:5]))
        try:
            clean = validate_case(case)
        except JevError as exc:
            return _fail(base, "error", exc.code, str(exc))
        body = build_body(clean, bank, lang)
        started = time.monotonic()
        if mock:
            resp, status = mock_response(body), "mock"
        else:
            key = find_api_key()
            if not key:
                return _fail(base, "skipped", "no_key", "没有找到 Jev 密钥（TYPESAFE_API_KEY 等），本卦不做预判")
            try:
                resp = (_call or call_jev)(body, key, timeout=timeout, retries=retries, total_timeout=total_timeout)
            except JevError as exc:
                return _fail(base, "error", exc.code, str(exc))
            status = "ok"
        problems = validate_response(resp, bank)
        if problems:
            return _fail(base, "error", "invalid_response", "Jev 返回结构不可用，整份结果作废",
                         problems=problems[:20])
        items, ambiguous, actions = interpret(resp, bank)
        return {**base, "status": status, "usable": status == "ok", "model": resp.get("model"),
                "latency_ms": int((time.monotonic() - started) * 1000), "usage": resp.get("usage"),
                "answers": items, "ambiguous_items": ambiguous, "next_actions": actions}
    except Exception as exc:  # noqa: BLE001 — 任何意外都不能中断断卦流程
        return _fail(base, "error", "internal", f"{type(exc).__name__}: {exc}")


# ── 命令行 ────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="六爻来意预判（Jev，可选）")
    ap.add_argument("case", nargs="?", help="来意 JSON 文件路径；- 表示从标准输入读")
    ap.add_argument("--lang", choices=("zh", "en"), default="zh")
    ap.add_argument("--mock", action="store_true", help="不联网，出假结果（只测流程）")
    ap.add_argument("--dry-run", action="store_true", help="只打印请求体，不发送")
    ap.add_argument("--check", action="store_true", help="只校验题库")
    ap.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="单次请求秒数")
    ap.add_argument("--total-timeout", type=float, default=DEFAULT_TOTAL_TIMEOUT, help="含重试的总秒数")
    args = ap.parse_args(argv)

    if args.check:
        try:
            bank = load_bank()
        except JevError as exc:
            print(f"题库读不了：{exc}", file=sys.stderr)
            return 1
        problems = check_bank(bank)
        if problems:
            print("题库有问题：\n  " + "\n  ".join(problems), file=sys.stderr)
            return 1
        kinds = [q["type"] for q in bank["questions"]]
        print(f"题库 {bank.get('bank_version')} 通过：{len(kinds)} 题"
              f"（choice {kinds.count('choice')}，noul {kinds.count('noul')}），模型 {bank.get('model')}")
        return 0

    if not args.case:
        ap.error("需要 case.json（或 --check）")
    try:
        raw = sys.stdin.read() if args.case == "-" else Path(args.case).read_text(encoding="utf-8")
        case = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "usable": False, "error_code": "bad_input",
                          "reason": f"读不了来意 JSON：{exc}"}, ensure_ascii=False, indent=2))
        return 0

    if args.dry_run:
        try:
            body = build_body(validate_case(case), load_bank(), args.lang)
        except JevError as exc:
            print(json.dumps({"status": "error", "usable": False, "error_code": exc.code, "reason": str(exc)},
                             ensure_ascii=False, indent=2))
            return 0
        print(json.dumps(body, ensure_ascii=False, indent=2))
        return 0

    result = judge(case, lang=args.lang, mock=args.mock, timeout=args.timeout, total_timeout=args.total_timeout)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
