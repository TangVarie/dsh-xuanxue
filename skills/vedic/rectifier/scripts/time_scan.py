"""
rectifier 模块 — Time Scanner（swisseph 版 + 候选时刻各自的 Vimsottari Dasha）
=========================================================================
逐分钟扫描出生时间 ±N 分钟，输出 Lagna / D9 / D10 / Moon Nakshatra 的变化点；
传入事件日期时，**每个候选时刻都用它自己的出生时刻重算 Vimsottari**，给出该事件
落在哪个 MD/AD（加 --pd 时再给 PD），并标出事件归属在扫描范围内哪一分钟切换。

天文口径与 calculator 模块 engine.py 一致：swisseph + True Chitra Ayanamsa，
Lagna 用 houses_ex(…, b'W', FLG_SIDEREAL)，Moon 用 engine.PLANET_FLAGS(66386)。
Dasha 直接调用同一 skill 下 calculator/scripts/dasha_pyjhora.py 的
calculate_dasha_fixed（与排盘同一个函数），不另写近似算法。

用法（--date/--time 一律是 --tz 下的当地钟表时间；已是 UTC 时传 --tz UTC）:
  python time_scan.py --date 1990-05-21 --time 14:23 --tz Asia/Shanghai \\
      --lat 39.9042 --lon 116.4074 --range 30 --save rectification_scan.md
  # 带事件日期（YYYY / YYYY-MM / YYYY-MM-DD，可加 "=标签"，可重复）
  python time_scan.py ... --event-date 2015-09-01=入学 --event-date 2019-07 --event-date 2023
  # 有可靠到月/日的事件、需要三级运审计时再加 --pd
  python time_scan.py ... --event-date 2019-07-01 --pd

⚠️ 与上游版本的差异：上游 --date/--time 是 UTC、--tz 是数字偏移；
   本模块 --date/--time 是当地时间、--tz 接受 IANA 名（推荐，自动处理夏令时，
   如中国 1986-1991）或数字偏移（固定偏移，不处理夏令时）。--local-date/--local-time
   作为别名保留，含义相同。

依赖: 用 calculator 模块的 venv 运行（pysweph + PyJHora + pytz，见 calculator/scripts/setup_env.py）。
"""

import argparse
import calendar
import contextlib
import io
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import swisseph as swe
except ImportError as _e:  # 用错 python 时给出可执行的纠正
    sys.stderr.write(
        "❌ swisseph 不可用——请用 calculator 模块的 venv 运行本脚本：\n"
        "   Linux/Mac: <vedic skill>/calculator/venv/bin/python rectifier/scripts/time_scan.py ...\n"
        "   Windows  : <vedic skill>\\calculator\\venv\\Scripts\\python.exe rectifier\\scripts\\time_scan.py ...\n"
        "   没有 venv → 先运行 calculator/scripts/setup_env.py（或 check_env.py 自检）。\n"
        f"   原始错误: {_e}\n")
    sys.exit(1)

# === 同一 skill 内的 calculator 模块（相对定位，不写死绝对路径）===
_CALC_DIR = Path(__file__).resolve().parents[2] / 'calculator'
_CALC_SCRIPTS = _CALC_DIR / 'scripts'
if (_CALC_SCRIPTS / 'dasha_pyjhora.py').is_file():
    sys.path.insert(0, str(_CALC_SCRIPTS))
try:
    with contextlib.redirect_stdout(io.StringIO()):  # PyJHora 导入时会打印 sys.path，屏蔽
        from dasha_pyjhora import calculate_dasha_fixed
    _HAS_DASHA = True
    _DASHA_ERR = None
except Exception as _e:  # noqa: BLE001
    _HAS_DASHA = False
    _DASHA_ERR = f'{type(_e).__name__}: {_e}（calculator 路径: {_CALC_SCRIPTS}）'

# === 与 engine.py 一致的天文配置 ===
swe.set_sid_mode(swe.SIDM_TRUE_CITRA)
_EPHE_DIR = _CALC_SCRIPTS / 'ephe'
if _EPHE_DIR.is_dir():
    swe.set_ephe_path(str(_EPHE_DIR))
# 与 engine.PLANET_FLAGS / PyJHora drik.PLANET_FLAGS 同值(66386)；改 engine 时同步改这里
PLANET_FLAGS = (swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED
                | swe.FLG_TRUEPOS | swe.FLG_NONUT | swe.FLG_NOGDEFL)

SIGNS = ['Ar', 'Ta', 'Ge', 'Cn', 'Le', 'Vi', 'Li', 'Sc', 'Sg', 'Cp', 'Aq', 'Pi']
SIGNS_CN = ['白羊', '金牛', '双子', '巨蟹', '狮子', '处女', '天秤', '天蝎', '射手', '摩羯', '水瓶', '双鱼']
NAKSHATRAS = ['Ashwini', 'Bharani', 'Krittika', 'Rohini', 'Mrigashira', 'Ardra',
              'Punarvasu', 'Pushya', 'Ashlesha', 'Magha', 'P.Phalguni', 'U.Phalguni',
              'Hasta', 'Chitra', 'Swati', 'Vishakha', 'Anuradha', 'Jyeshtha', 'Mula',
              'P.Ashadha', 'U.Ashadha', 'Shravana', 'Dhanishta', 'Shatabhisha',
              'P.Bhadra', 'U.Bhadra', 'Revati']
NAK_LORDS = ['Ketu', 'Venus', 'Sun', 'Moon', 'Mars', 'Rahu', 'Jupiter', 'Saturn', 'Mercury'] * 3


# ---------------------------------------------------------------------------
# 天文计算（与 engine.calc_lagna / calc_navamsha / calc_dashamsha 同算法）
# ---------------------------------------------------------------------------

def calc_sidereal_asc(jd, lat, lon):
    _cusps, ascmc = swe.houses_ex(jd, lat, lon, b'W', swe.FLG_SIDEREAL)[:2]
    return ascmc[0]


def calc_d9(asc_deg):
    """Navamsha：每座 9 份(3°20')；火→Ar、土→Cp、风→Li、水→Cn 起。"""
    sign = int(asc_deg / 30) % 12
    nav_part = int((asc_deg % 30) / (30.0 / 9))
    d9 = ([0, 9, 6, 3][sign % 4] + nav_part) % 12
    return SIGNS[d9], SIGNS_CN[d9]


def calc_d10(asc_deg):
    """Dashamsha：每座 10 份(3°)；奇座从本座起，偶座从第 9 座起（0-index 为 +8）。"""
    sign = int(asc_deg / 30) % 12
    part = min(int((asc_deg % 30) / 3.0), 9)
    d10 = (sign + part) % 12 if sign % 2 == 0 else (sign + part + 8) % 12
    return SIGNS[d10], SIGNS_CN[d10]


# ---------------------------------------------------------------------------
# 时区：IANA（优先 pytz，与 calculator 同一时区库）或数字偏移
# ---------------------------------------------------------------------------

class TZ:
    def __init__(self, raw):
        self.raw = raw.strip()
        self.fixed = None
        self.name = None
        up = self.raw.upper()
        if up in ('UTC', 'GMT', 'Z'):
            self.fixed = 0.0
        else:
            try:
                self.fixed = float(self.raw)
            except ValueError:
                self.name = self.raw
        if self.name:
            self._init_named()

    def _init_named(self):
        try:
            import pytz
            try:
                self._pytz = pytz.timezone(self.name)
            except pytz.exceptions.UnknownTimeZoneError:
                raise ValueError(self._unknown())
            self._zi = None
        except ImportError:
            from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
            self._pytz = None
            try:
                self._zi = ZoneInfo(self.name)
            except ZoneInfoNotFoundError:
                raise ValueError(self._unknown())

    def _unknown(self):
        return (f'未知时区: {self.raw}。用 IANA 名（中国大陆 Asia/Shanghai、印度 Asia/Kolkata、'
                f'美东 America/New_York）或数字偏移（如 8、5.5），已是 UTC 传 UTC。')

    def label(self):
        if self.name:
            return self.name
        return 'UTC' if self.fixed == 0 else f'UTC{self.fixed:+g}（固定偏移，不处理夏令时）'

    def local_to_utc(self, naive):
        """当地钟表时间 → UTC(naive)。夏令时重复/跳过时段明确报错，不静默猜（同 engine._localize_strict）。"""
        if self.fixed is not None:
            return naive - timedelta(hours=self.fixed)
        if self._pytz is not None:
            import pytz
            try:
                aware = self._pytz.localize(naive, is_dst=None)
            except pytz.exceptions.AmbiguousTimeError:
                raise ValueError(f'{naive} 落在夏令时结束的重复时段（钟表回拨，出现两次）；请确认是夏令时钟还是标准时。')
            except pytz.exceptions.NonExistentTimeError:
                raise ValueError(f'{naive} 落在夏令时开始的跳过时段（该钟表时刻不存在）；记录可能是标准时，请核实。')
            return aware.astimezone(timezone.utc).replace(tzinfo=None)
        a0 = naive.replace(tzinfo=self._zi, fold=0)
        a1 = naive.replace(tzinfo=self._zi, fold=1)
        if a0.utcoffset() != a1.utcoffset():
            raise ValueError(f'{naive} 落在夏令时切换的重复/跳过时段；请确认钟表性质。')
        utc = a0.astimezone(timezone.utc).replace(tzinfo=None)
        if self.utc_to_local(utc)[0] != naive:
            raise ValueError(f'{naive} 落在夏令时开始的跳过时段（该钟表时刻不存在）。')
        return utc

    def utc_to_local(self, utc_naive):
        """UTC(naive) → (当地钟表时间 naive, 当时 UTC 偏移小时)。"""
        if self.fixed is not None:
            return utc_naive + timedelta(hours=self.fixed), self.fixed
        aware = utc_naive.replace(tzinfo=timezone.utc)
        loc = aware.astimezone(self._pytz if self._pytz is not None else self._zi)
        return loc.replace(tzinfo=None), loc.utcoffset().total_seconds() / 3600.0


# ---------------------------------------------------------------------------
# 逐分钟扫描
# ---------------------------------------------------------------------------

def scan(base_utc, tz, lat, lon, range_min):
    results = []
    prev = None
    base_jd = swe.julday(base_utc.year, base_utc.month, base_utc.day,
                         base_utc.hour + base_utc.minute / 60.0)
    for delta in range(-range_min, range_min + 1):
        jd = base_jd + delta / 1440.0
        asc = calc_sidereal_asc(jd, lat, lon)
        sign_idx = int(asc / 30) % 12
        d9, d9_cn = calc_d9(asc)
        d10, d10_cn = calc_d10(asc)
        moon = swe.calc_ut(jd, swe.MOON, PLANET_FLAGS)[0][0]
        nak = int(moon / (360.0 / 27)) % 27
        local, off = tz.utc_to_local(base_utc + timedelta(minutes=delta))
        markers = []
        if prev:
            if sign_idx != prev['sign_idx']:
                markers.append(f"★ LAGNA换座→{SIGNS_CN[sign_idx]}")
            if d9 != prev['d9']:
                markers.append(f"◆ D9换座→{d9_cn}")
            if d10 != prev['d10']:
                markers.append(f"◇ D10换座→{d10_cn}")
            if nak != prev['nak']:
                markers.append(f"⚠️Moon跨Nak→{NAKSHATRAS[nak]}（出生大运主星 {NAK_LORDS[prev['nak']]}→{NAK_LORDS[nak]}）")
        row = {
            'delta': delta, 'local': local, 'utc_offset': off, 'asc': asc,
            'sign_idx': sign_idx, 'sign': SIGNS[sign_idx], 'sign_cn': SIGNS_CN[sign_idx],
            'deg_in_sign': asc % 30, 'd9': d9, 'd9_cn': d9_cn, 'd10': d10, 'd10_cn': d10_cn,
            'nak': nak, 'moon_nak': NAKSHATRAS[nak], 'moon_lon': moon,
            'markers': ' '.join(markers),
        }
        results.append(row)
        prev = row
    return results


def segments_of(results):
    """按 Lagna/D9/D10/Moon-Nak 任一变化切段；每段 = 一个候选（或候选的子段）。"""
    segs = []
    for r in results:
        key = (r['sign_idx'], r['d9'], r['d10'], r['nak'])
        if segs and segs[-1]['key'] == key:
            segs[-1]['end'] = r['delta']
            segs[-1]['end_local'] = r['local']
        else:
            segs.append({'key': key, 'start': r['delta'], 'end': r['delta'],
                         'start_local': r['local'], 'end_local': r['local'],
                         'sign': r['sign'], 'sign_cn': r['sign_cn'], 'd9': r['d9'],
                         'd10': r['d10'], 'moon_nak': r['moon_nak']})
    return segs


# ---------------------------------------------------------------------------
# Dasha：每个候选时刻各算各的
# ---------------------------------------------------------------------------

class DashaProbe:
    """按偏移分钟缓存 calculate_dasha_fixed 的结果（每个探测点都是 calculator 真算）。"""

    def __init__(self, base_utc, tz, lat, lon, include_pd):
        self.base_utc, self.tz, self.lat, self.lon = base_utc, tz, lat, lon
        self.include_pd = include_pd
        self.cache = {}

    def at(self, delta):
        if delta not in self.cache:
            local, off = self.tz.utc_to_local(self.base_utc + timedelta(minutes=delta))
            with contextlib.redirect_stdout(io.StringIO()):
                self.cache[delta] = calculate_dasha_fixed(
                    local.year, local.month, local.day, local.hour, local.minute,
                    self.lat, self.lon, off, include_pd=self.include_pd)
        return self.cache[delta]


def parse_event(raw):
    """'2019-07-01' / '2019-07' / '2019'，可带 '=标签'。返回 dict(raw,label,precision,start,end)。"""
    text, _, label = raw.partition('=')
    text = text.strip()
    parts = text.split('-')
    try:
        if len(parts) == 3:
            d = datetime.strptime(text, '%Y-%m-%d').date()
            return {'raw': text, 'label': label.strip(), 'precision': '日', 'start': d, 'end': d}
        if len(parts) == 2:
            y, m = int(parts[0]), int(parts[1])
            last = calendar.monthrange(y, m)[1]
            return {'raw': text, 'label': label.strip(), 'precision': '月',
                    'start': datetime(y, m, 1).date(), 'end': datetime(y, m, last).date()}
        if len(parts) == 1 and len(text) == 4:
            y = int(text)
            return {'raw': text, 'label': label.strip(), 'precision': '年',
                    'start': datetime(y, 1, 1).date(), 'end': datetime(y, 12, 31).date()}
    except ValueError:
        pass
    raise ValueError(f'事件日期须为 YYYY / YYYY-MM / YYYY-MM-DD（可加 =标签）：{raw}')


def _d(s):
    return datetime.strptime(s[:10], '%Y-%m-%d').date()


def periods_in_span(dashas, start, end, level):
    """事件日期区间 [start,end] 覆盖到的全部 MD/AD(/PD)，按时间顺序；区间按 [start,end) 解释。"""
    out = []
    for md in dashas or []:
        for ad in md.get('antardashas', []):
            if level == 2:
                if _d(ad['start']) <= end and start < _d(ad['end']):
                    out.append(f"{md['planet']}/{ad['planet']}")
            else:
                for pd in ad.get('pratyantardashas', []):
                    if _d(pd['start']) <= end and start < _d(pd['end']):
                        out.append(f"{md['planet']}/{ad['planet']}/{pd['planet']}")
    return ' → '.join(out) if out else '超出时间线'


def event_ranges(probe, ev, level, lo, hi):
    """[lo,hi] 内该事件归属的分段：[(起, 止, 归属)]。

    依据：出生时刻每晚 1 分钟，Moon 前进约 0.5′，全部 Dasha 边界单调提前（约 1.5-5 天/分钟），
    所以同一事件的归属随出生分钟单调推进——两端相同则整段相同，不同则二分到相邻分钟。
    每个探测点都是 calculate_dasha_fixed 真算，结果按分钟精确，不是插值。
    """
    key = lambda t: periods_in_span(probe.at(t), ev['start'], ev['end'], level)  # noqa: E731
    flips = []

    def walk(a, b):
        ka, kb = key(a), key(b)
        if ka == kb:
            return
        if b - a == 1:
            flips.append(b)
            return
        cached = [t for t in probe.cache if a < t < b]
        mid = min(cached, key=lambda t: abs(t - (a + b) / 2)) if cached else (a + b) // 2
        walk(a, mid)
        walk(mid, b)

    walk(lo, hi)
    flips.sort()
    bounds = [lo] + flips
    ranges = []
    for i, s in enumerate(bounds):
        e = (flips[i] - 1) if i < len(flips) else hi
        ranges.append((s, e, key(s)))
    return ranges


def collapse_level(ranges, keep):
    """把 PD 级分段收拢为 MD/AD 级（截断到前 keep 层后合并相邻相同项）。"""
    out = []
    for s, e, lab in ranges:
        short = ' → '.join(dict.fromkeys('/'.join(p.split('/')[:keep]) for p in lab.split(' → ')))
        if out and out[-1][2] == short:
            out[-1] = (out[-1][0], e, short)
        else:
            out.append((s, e, short))
    return out


def label_in_segment(ranges, s, e):
    hit = [(max(a, s), min(b, e), lab) for a, b, lab in ranges if a <= e and b >= s]
    if len(hit) == 1:
        return hit[0][2]
    return '；'.join(f"{lab}（{a:+d}~{b:+d}）" for a, b, lab in hit)


def _fmt_timeline(dashas):
    if not dashas:
        return '  [空]'
    lines = []
    for md in dashas:
        ads = md.get('antardashas', [])
        ad_txt = ' '.join(f"{a['planet'][:2]} {a['start']}" for a in ads)
        end = ads[-1]['end'] if ads else md.get('end', '')
        lines.append(f"  {md['planet']:<8} {ads[0]['start'] if ads else md['start']} ~ {end} ｜AD起: {ad_txt}")
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------

def render(args, tz, base_local, base_utc, results, segs, events, ev_data, endpoints, dasha_err):
    off0 = results[len(results) // 2]['utc_offset']

    def hm(dt):  # 本地日期与基准日不同（跨零点）时带上月-日，避免把次日 00:05 误读成当天
        return f"{dt:%H:%M}" if dt.date() == base_local.date() else f"{dt:%m-%d %H:%M}"

    L = []
    L.append('# 时间扫描结果\n')
    L.append(f"> 基准: 本地 {base_local:%Y-%m-%d %H:%M}（{tz.label()}，当时 UTC{off0:+g}）"
             f" = UTC {base_utc:%Y-%m-%d %H:%M}")
    L.append(f"> 坐标: ({args.lat}, {args.lon})｜范围: ±{args.range} 分钟")
    L.append('> 引擎: swisseph + True Chitra（与 calculator engine 同口径）；Dasha = calculator dasha_pyjhora，'
             '每个探测时刻按它自己的出生时刻重算')
    L.append('> 先核对上面"本地"日期时间与用户报的一致（跨零点、夏令时都在这里暴露）。\n')
    L.append('| 偏移 | 本地时间 | Lagna度数 | 星座 座内度数 | D9 | D10 | Moon宿 | 标记 |')
    L.append('|------|---------|----------|--------------|----|-----|--------|------|')
    for r in results:
        mark = r['markers'] + (' ← 原始' if r['delta'] == 0 else '')
        L.append(f"| {r['delta']:+d}min | {hm(r['local'])} | {r['asc']:.2f}° | {r['sign']}{r['sign_cn']} "
                 f"{r['deg_in_sign']:.2f}° | {r['d9']} | {r['d10']} | {r['moon_nak']} | {mark} |")

    L.append('\n## 关键变化点（Lagna/D9/D10 换座 + Moon 跨 Nakshatra）')
    changes = [r for r in results if r['markers']]
    if changes:
        for r in changes:
            L.append(f"- {r['delta']:+d}min（本地 {hm(r['local'])}）: {r['markers']}")
    else:
        L.append('- 扫描范围内无换座/跨宿。')

    L.append('\n## 候选段（按 Lagna/D9/D10/Moon宿 切段）')
    head = '| 段 | 偏移 | 本地时间 | Lagna | D9 | D10 | Moon宿 |'
    sep = '|----|------|---------|-------|----|-----|--------|'
    if ev_data:
        for i, ev in enumerate(events, 1):
            head += f" 事件{i} {ev['raw']}{(' ' + ev['label']) if ev['label'] else ''} |"
            sep += '------|'
    L.append(head)
    L.append(sep)
    for n, s in enumerate(segs, 1):
        row = (f"| S{n} | {s['start']:+d}~{s['end']:+d} | {hm(s['start_local'])}-{hm(s['end_local'])} | "
               f"{s['sign']}{s['sign_cn']} | {s['d9']} | {s['d10']} | {s['moon_nak']} |")
        for ed in ev_data or []:
            row += f" {label_in_segment(ed['shown'], s['start'], s['end'])} |"
        L.append(row)
    if ev_data:
        L.append('\n> 事件列显示的是**该段内每个出生时刻各自的** Dasha 归属；同一格出现多个归属 = 段内某分钟切换，'
                 '括号是各归属对应的偏移分钟。PD 只在加了 --pd 且事件精度到月/日时出现。')

    if events:
        L.append('\n## 事件日期 × 候选时刻 Dasha（腿二数据源）')
        if dasha_err:
            L.append(f"⚠️⚠️ **DASHA_UNAVAILABLE**：{dasha_err}")
            L.append('→ ❌ 禁止在没有候选时刻 Dasha 的情况下进 3c 定盘；先修 calculator 环境后重跑。')
        else:
            for i, (ev, ed) in enumerate(zip(events, ev_data), 1):
                L.append(f"\n### 事件{i}：{ev['raw']}{('（' + ev['label'] + '）') if ev['label'] else ''}"
                         f"｜日期精度={ev['precision']}")
                L.append('| 偏移区间 | 本地时间 | MD/AD | PD |')
                L.append('|---------|---------|-------|----|')
                for s, e, lab in ed['mdad']:
                    pd_txt = '; '.join(f"{lb}（{a:+d}~{b:+d}）" for a, b, lb in ed['pd'] if a <= e and b >= s) \
                        if ed['pd'] is not None else ed['pd_note']
                    ls = results[s + args.range]['local']
                    le = results[e + args.range]['local']
                    L.append(f"| {s:+d}~{e:+d} | {hm(ls)}-{hm(le)} | {lab} | {pd_txt} |")
                if len(ed['mdad']) == 1:
                    L.append('→ MD/AD 在整个扫描范围内不变：此事件对本范围内的候选没有 MD/AD 区分力。')

    L.append('\n## 两点法 Dasha（段首 / 段末完整 MD/AD 时间线；日期=出生地当地时区）')
    if dasha_err:
        L.append(f"⚠️⚠️ **DASHA_UNAVAILABLE**：{dasha_err}")
        L.append('→ ❌ 禁止在没有候选时刻 Dasha 的情况下进 3c 定盘；先修 calculator 环境后重跑。')
    else:
        for label, dashas in endpoints:
            L.append(f"\n### {label}")
            L.append(_fmt_timeline(dashas))
    return '\n'.join(L) + '\n'


def main():
    p = argparse.ArgumentParser(
        description='rectifier 时间扫描（swisseph + 候选时刻各自的 Vimsottari Dasha）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=('示例:\n  python time_scan.py --date 1990-05-21 --time 14:23 --tz Asia/Shanghai '
                '--lat 39.9042 --lon 116.4074 --range 30 --event-date 2019-07=入职 --pd'))
    p.add_argument('--date', '--local-date', dest='date', required=True,
                   help='出生日期 YYYY-MM-DD（--tz 下的当地日期；--tz UTC 时即 UTC 日期）')
    p.add_argument('--time', '--local-time', dest='time', required=True,
                   help='预估出生时间 HH:MM（--tz 下的当地钟表时间）')
    p.add_argument('--tz', required=True,
                   help='必填。IANA 时区名（推荐，自动处理夏令时；中国大陆 Asia/Shanghai、印度 Asia/Kolkata）'
                        '，或数字偏移（8 / 5.5，固定偏移不处理夏令时），已是 UTC 传 UTC')
    p.add_argument('--lat', required=True, type=float, help='出生地纬度')
    p.add_argument('--lon', required=True, type=float, help='出生地经度')
    p.add_argument('--range', type=int, default=30, help='扫描范围 ±分钟（默认 30）')
    p.add_argument('--event-date', action='append', default=[],
                   help='事件日期 YYYY / YYYY-MM / YYYY-MM-DD，可带 =标签，可重复；输出每个候选时刻的 MD/AD 归属')
    p.add_argument('--pd', action='store_true',
                   help='对精度到月/日的事件再给 PD（三级运）归属；只在 MD/AD 矩阵填完、仍需 PD 分辨时用')
    p.add_argument('--endpoint-start', type=int, help='两点法时间线的段首偏移（分钟），须与 --endpoint-end 同传')
    p.add_argument('--endpoint-end', type=int, help='两点法时间线的段末偏移（分钟），须与 --endpoint-start 同传')
    p.add_argument('--save', type=str, help='把结果保存为 Markdown 文件')
    args = p.parse_args()

    if args.range < 1:
        p.error('--range 至少为 1 分钟')
    try:
        tz = TZ(args.tz)
        base_local = datetime.strptime(f"{args.date} {args.time}", '%Y-%m-%d %H:%M')
        base_utc = tz.local_to_utc(base_local)
        events = [parse_event(e) for e in args.event_date]
    except ValueError as exc:
        p.error(str(exc))
    if (args.endpoint_start is None) != (args.endpoint_end is None):
        p.error('--endpoint-start 与 --endpoint-end 必须同时传入')
    ep_start = -args.range if args.endpoint_start is None else args.endpoint_start
    ep_end = args.range if args.endpoint_end is None else args.endpoint_end
    if not (-args.range <= ep_start < ep_end <= args.range):
        p.error('段首/段末必须在 --range 范围内且段首 < 段末')

    results = scan(base_utc, tz, args.lat, args.lon, args.range)
    segs = segments_of(results)

    ev_data, endpoints, dasha_err = [], [], None
    if not _HAS_DASHA:
        dasha_err = _DASHA_ERR
    else:
        probe = DashaProbe(base_utc, tz, args.lat, args.lon, include_pd=args.pd)
        try:
            for ev in events:
                print(f"… 计算事件 {ev['raw']} 的候选时刻归属", file=sys.stderr)
                pd_ok = args.pd and ev['precision'] in ('日', '月')
                if pd_ok:
                    pd_ranges = event_ranges(probe, ev, 3, -args.range, args.range)
                    mdad = collapse_level(pd_ranges, 2)
                    ev_data.append({'mdad': mdad, 'pd': pd_ranges, 'shown': pd_ranges, 'pd_note': ''})
                else:
                    mdad = event_ranges(probe, ev, 2, -args.range, args.range)
                    note = ('—（年精度，PD 不可用）' if ev['precision'] == '年' else '—（未加 --pd）')
                    ev_data.append({'mdad': mdad, 'pd': None, 'shown': mdad, 'pd_note': note})
            endpoints = [(f'段首({ep_start:+d}min)', probe.at(ep_start)),
                         (f'段末({ep_end:+d}min)', probe.at(ep_end))]
            print(f"… Dasha 探测点 {len(probe.cache)} 个（每点都是 calculator 真算）", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001
            dasha_err = f'Dasha 计算失败: {type(exc).__name__}: {exc}'
            ev_data, endpoints = [], []

    text = render(args, tz, base_local, base_utc, results, segs, events, ev_data, endpoints, dasha_err)
    print(text)
    if args.save:
        with open(args.save, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"已保存: {args.save}", file=sys.stderr)


if __name__ == '__main__':
    main()
