"""chart_data.json 读写与公共工具（vedic 5.1 数据契约）。

一次计算，同一份数据生成两种产物：
  chart_data.json     机器读取、校验、跨模块传递（本模块负责）
  structured_data.md  阅读、引用、核对（formatter.render 从同一份数据生成）

缺失值一律用 {"_missing": <状态>, "reason": ...} 表示，状态只有四种：
  not_provided 未提供 / not_computed 未计算 / failed 计算失败 / not_applicable 不适用
"""
import datetime
import hashlib
import json
import math
import os

SCHEMA_VERSION = "vedic-chart/1.0"
ENGINE_VERSION = "calculator-0.9.2+vedic5.2"  # 0.9.2: Chara 双主座规则、宿名 Mula、D2 传统 Hora、夏令时切换时段
RULES_VERSION = "vedic-5.2"
# 版本升级后哪些旧结论要复核（check_freshness.py 把这句话接在「需更新」后面，避免整份分析被当成作废）
ENGINE_CHANGE_NOTE = ("0.9.2 改了 Chara Dasha 的 Scorpio/Aquarius 双主座年数（该座及其后各段的起止可能变）、"
                      "D2 改为传统 Hora、第 19 宿统一写 Mula；Vimsottari、D1、D9/D10/D4/D5、Shadbala、SAV 的数值不变。"
                      "重排后只需复核引用了 Chara Dasha 时间线的时机结论")
RULES_CHANGE_NOTE = ("5.2 相对 5.1 只改了 Chara Dasha 双主座的取主规则（timing/resources/chara_dasha_rules.md）："
                     "写过「双系统确认 / 共振」的时机结论按重排后的 Chara 表复核，其余结论不受影响")

MISSING_LABEL = {
    "not_provided": "未提供",
    "not_computed": "未计算",
    "failed": "计算失败",
    "not_applicable": "不适用",
}

SIGNS = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
         'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces']
NAKSHATRAS = [
    'Ashwini', 'Bharani', 'Krittika', 'Rohini', 'Mrigashira', 'Ardra', 'Punarvasu',
    'Pushya', 'Ashlesha', 'Magha', 'Purva Phalguni', 'Uttara Phalguni', 'Hasta',
    'Chitra', 'Swati', 'Vishakha', 'Anuradha', 'Jyeshtha', 'Mula', 'Purva Ashadha',
    'Uttara Ashadha', 'Shravana', 'Dhanishta', 'Shatabhisha', 'Purva Bhadrapada',
    'Uttara Bhadrapada', 'Revati']
PLANETS9 = ['Sun', 'Moon', 'Mars', 'Mercury', 'Jupiter', 'Venus', 'Saturn', 'Rahu', 'Ketu']
# 同一宿的其他拼法 → 规范名。5.1 及更早的引擎把第 19 宿写成 Moola，旧盘、旧导出、JHora 文本都可能带这些写法。
NAKSHATRA_ALIASES = {
    'Moola': 'Mula', 'Moolam': 'Mula', 'Mulam': 'Mula',
    'Aswini': 'Ashwini', 'Asvini': 'Ashwini', 'Mrigasira': 'Mrigashira', 'Mrigashirsha': 'Mrigashira',
    'Aridra': 'Ardra', 'Arudra': 'Ardra', 'Pushyami': 'Pushya', 'Aslesha': 'Ashlesha',
    'Makha': 'Magha', 'Chitta': 'Chitra', 'Swathi': 'Swati', 'Visakha': 'Vishakha',
    'Jyeshta': 'Jyeshtha', 'Sravana': 'Shravana', 'Dhanishtha': 'Dhanishta', 'Satabhisha': 'Shatabhisha',
    'Shatabhishak': 'Shatabhisha', 'Poorvabhadra': 'Purva Bhadrapada', 'Uttarabhadra': 'Uttara Bhadrapada',
    'Poorvaphalguni': 'Purva Phalguni', 'Uttaraphalguni': 'Uttara Phalguni',
    'Poorvashadha': 'Purva Ashadha', 'Uttarashadha': 'Uttara Ashadha',
}


def canon_nakshatra(name):
    """把宿名的常见异写归到规范名；认不出的原样返回，由调用方判非法。"""
    if not isinstance(name, str):
        return name
    n = name.strip()
    return n if n in NAKSHATRAS else NAKSHATRA_ALIASES.get(n, n)

# 时间来源 → 来源允许的最小误差（分钟）。用户声明更宽时取更宽者；不会因验前事命中而收窄。
SOURCE_FLOOR = {
    "出生证": 1, "医院记录": 1,
    "家人明确记忆": 5, "家人记忆": 5,
    "本人记忆": 15, "模糊记忆": 15,
    "未追问": 15, "未知": 15,
    # rectifier 校准后：用校准达成的窗口半宽作 --declared-min，来源写「校时」，--original-source 记原来源
    "校时": 1,
}


# ---------- 缺失值 ----------
def missing(status, reason=""):
    if status not in MISSING_LABEL:
        raise ValueError(f"unknown missing status: {status}")
    return {"_missing": status, "reason": reason}


def is_missing(value):
    return isinstance(value, dict) and "_missing" in value


def missing_label(value):
    if not is_missing(value):
        return ""
    text = MISSING_LABEL[value["_missing"]]
    return f"{text}（{value['reason']}）" if value.get("reason") else text


# ---------- 精度 ----------
def precision_label(minutes):
    if minutes is None:
        return "不确定"
    if minutes <= 2:
        return "±分钟级"
    if minutes <= 5:
        return "±5分钟"
    if minutes <= 15:
        return "±15分钟"
    if minutes <= 60:
        return "±1小时"
    return "不确定"


def resolve_precision(time_source, declared_minutes=None):
    """返回 (有效误差分钟, 说明)。有效误差 = max(用户声明, 来源下限)。"""
    floor = SOURCE_FLOOR.get(time_source)
    notes = []
    if time_source == "校时" and declared_minutes is None:
        raise ValueError("来源为「校时」时必须用 --declared-min 传入校准达成的窗口半宽（分钟）")
    if floor is None:
        floor = 15
        notes.append(f"来源「{time_source or '未提供'}」不在来源表内，按 ±15 分钟保守处理")
    if declared_minutes is None:
        eff = floor
        notes.append(f"未声明误差，按来源下限 ±{floor} 分钟")
    else:
        eff = max(int(declared_minutes), floor)
        if eff > declared_minutes:
            notes.append(f"声明 ±{declared_minutes} 分钟窄于来源下限，按来源放宽到 ±{eff} 分钟")
    return eff, "；".join(notes)


# ---------- JSON 化 ----------
def to_jsonable(obj):
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(x) for x in obj]
    if isinstance(obj, set):
        return sorted(to_jsonable(x) for x in obj)
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    if hasattr(obj, "item") and not isinstance(obj, (str, bytes)):
        try:
            return to_jsonable(obj.item())
        except Exception:
            return str(obj)
    return obj


_INT_KEY_FIELDS = ("house_lords", "sav_by_house", "bhava_bala")


def restore_int_keys(chart):
    """JSON 只有字符串键；formatter 按 1..12 整数取宫位，读回时恢复。"""
    def fix(d):
        if isinstance(d, dict) and d and all(isinstance(k, str) and k.isdigit() for k in d):
            return {int(k): v for k, v in d.items()}
        return d
    for f in _INT_KEY_FIELDS:
        if f in chart:
            chart[f] = fix(chart[f])
    vi = chart.get("varga_internal")
    if isinstance(vi, dict):
        for d in vi.values():
            if isinstance(d, dict) and "house_lords" in d:
                d["house_lords"] = fix(d["house_lords"])
    return chart


# ---------- 版本标识 ----------
def _hash(payload):
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def compute_ids(inp, settings):
    """chart_id 只随出生数据与计算设置变化；audit_id 另含误差审计范围。"""
    base = {k: inp.get(k) for k in ("date", "time_used", "tz", "lat", "lon", "mode")}
    if inp.get("repeated_hour"):   # 夏令时结束当晚同一钟表时刻的两次是两张不同的盘
        base["repeated_hour"] = inp["repeated_hour"]
    chart_id = _hash({"input": base, "settings": settings})
    audit_id = _hash({"chart_id": chart_id, "audit_minutes": inp.get("audit_minutes")})
    return chart_id, audit_id


# ---------- 读写 ----------
def save_doc(doc, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(to_jsonable(doc), f, ensure_ascii=False, indent=1)


def load_doc(path):
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    if doc.get("schema") != SCHEMA_VERSION:
        raise ValueError(f"{path}: schema 不是 {SCHEMA_VERSION}（得到 {doc.get('schema')}）")
    if isinstance(doc.get("chart"), dict):
        restore_int_keys(doc["chart"])
    return doc


def sibling_json(md_path):
    """structured_data.md 同目录的 chart_data.json（存在才返回）。"""
    p = os.path.join(os.path.dirname(os.path.abspath(md_path)), "chart_data.json")
    return p if os.path.exists(p) else None


def now_iso():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")
