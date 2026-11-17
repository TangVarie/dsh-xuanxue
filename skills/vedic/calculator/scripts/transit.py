"""过运计算模块 - 计算当前行星位置、Sade Sati、双过运"""
import swisseph as swe
from datetime import datetime
import pytz

# 与 engine 共用同一套 flags 与 swisseph 线程状态，避免过运与本命分属两套基准
# （此处原先只 set_sid_mode 不设 ephe_path，子线程里会静默退回 MOSEPH）。
from engine import PLANET_FLAGS, _ensure_swe_state

SIGNS = ['Aries','Taurus','Gemini','Cancer','Leo','Virgo',
         'Libra','Scorpio','Sagittarius','Capricorn','Aquarius','Pisces']

def calc_transit(lagna_sign_idx, moon_sign_idx, tz_str="Asia/Kolkata", on_date=None):
    """计算过运数据。on_date='YYYY-MM-DD' 时取该日当地正午（可复现的快照）；缺省为当前时刻。"""
    _ensure_swe_state()
    flags = PLANET_FLAGS

    zone = pytz.timezone(tz_str)
    if on_date:
        now = zone.localize(datetime.strptime(str(on_date)[:10] + " 12:00", "%Y-%m-%d %H:%M"))
    else:
        now = datetime.now(zone)
    utc = now.astimezone(pytz.utc)
    jd = swe.julday(utc.year, utc.month, utc.day, 
                     utc.hour + utc.minute/60.0)
    
    # 慢行星过运
    slow_planets = {
        'Saturn': (swe.SATURN, '~2.5年/星座'),
        'Jupiter': (swe.JUPITER, '~1年/星座'),
        'Rahu': (swe.MEAN_NODE, '~1.5年/星座')
    }
    
    transit = {}
    for name, (pid, cycle) in slow_planets.items():
        result = swe.calc_ut(jd, pid, flags)
        lon = result[0][0]
        sign_idx = int(lon / 30)
        house = ((sign_idx - lagna_sign_idx) % 12) + 1
        transit[name] = {
            'sign': SIGNS[sign_idx], 'sign_idx': sign_idx,
            'house': house, 'cycle': cycle
        }
    
    # Ketu = Rahu对冲
    rahu_idx = transit['Rahu']['sign_idx']
    ketu_idx = (rahu_idx + 6) % 12
    transit['Ketu'] = {
        'sign': SIGNS[ketu_idx], 'sign_idx': ketu_idx,
        'house': ((ketu_idx - lagna_sign_idx) % 12) + 1,
        'cycle': '自动取Rahu对冲'
    }
    
    # Sade Sati
    saturn_idx = transit['Saturn']['sign_idx']
    relative = (saturn_idx - moon_sign_idx) % 12
    if relative == 11:
        sade_sati = '第一阶段(升起)'
        position = 'Moon前1宫'
    elif relative == 0:
        sade_sati = '第二阶段(顶峰)'
        position = 'Moon本宫'
    elif relative == 1:
        sade_sati = '第三阶段(消退)'
        position = 'Moon后1宫'
    else:
        sade_sati = '未激活'
        position = '非Sade Sati'
    
    sade_sati_data = {
        'moon_sign': SIGNS[moon_sign_idx],
        'saturn_sign': transit['Saturn']['sign'],
        'position': position,
        'status': sade_sati
    }
    
    # 双过运 (Saturn-Jupiter Double Transit)
    saturn_house = transit['Saturn']['house']
    jupiter_house = transit['Jupiter']['house']
    
    # Saturn aspects: 合相(1), 3rd, 7th, 10th
    saturn_covers = set()
    for offset in [0, 2, 6, 9]:
        saturn_covers.add(((saturn_house - 1 + offset) % 12) + 1)
    
    # Jupiter aspects: 合相(1), 5th, 7th, 9th
    jupiter_covers = set()
    for offset in [0, 4, 6, 8]:
        jupiter_covers.add(((jupiter_house - 1 + offset) % 12) + 1)
    
    double_transit = sorted(saturn_covers & jupiter_covers)
    
    return {
        'planets': transit,
        'sade_sati': sade_sati_data,
        'saturn_covers': sorted(saturn_covers),
        'jupiter_covers': sorted(jupiter_covers),
        'double_transit': double_transit,
        'future_ingress': future_ingress_table(jd, years=5),
        'date': now.strftime('%Y-%m-%d')
    }


def future_ingress_table(jd_start, years=5):
    """未来 N 年 Saturn/Jupiter/Rahu 的恒星黄道(True Chitra)换座时间表。

    真实天文计算，替代模型凭记忆写未来过运（LLM 心算换座日期常错数月到一年）。
    逆行导致的回跨也如实记录（同一边界可能出现 进→退→再进 多条）。
    Returns: [{'planet','date','from_sign','to_sign'}, ...] 按日期排序
    """
    _ensure_swe_state()
    flags = PLANET_FLAGS
    bodies = {'Saturn': swe.SATURN, 'Jupiter': swe.JUPITER, 'Rahu': swe.MEAN_NODE}
    events = []
    jd_end = jd_start + years * 365.25
    for name, pid in bodies.items():
        step = 5.0
        prev_idx = int(swe.calc_ut(jd_start, pid, flags)[0][0] / 30)
        jd = jd_start + step
        while jd <= jd_end:
            idx = int(swe.calc_ut(jd, pid, flags)[0][0] / 30)
            if idx != prev_idx:
                lo, hi = jd - step, jd  # 二分到 0.01 天
                while hi - lo > 0.01:
                    mid = (lo + hi) / 2
                    if int(swe.calc_ut(mid, pid, flags)[0][0] / 30) == prev_idx:
                        lo = mid
                    else:
                        hi = mid
                y, m, d, _ = swe.revjul(hi)
                events.append({'planet': name, 'date': f'{y:04d}-{m:02d}-{d:02d}',
                               'from_sign': SIGNS[prev_idx], 'to_sign': SIGNS[idx]})
                prev_idx = idx
            jd += step
    return sorted(events, key=lambda e: e['date'])

def degree_hits(target_deg, planets, start, end):
    """指定行星（恒星黄道 True Chitra）经过某一黄经度数的日期，含逆行回跨。
    target_deg: 0-360；start/end: 'YYYY-MM-DD'（UTC 日期）。返回 [{'planet','date','motion'}...]"""
    _ensure_swe_state()
    flags = PLANET_FLAGS
    ids = {'Sun': swe.SUN, 'Mars': swe.MARS, 'Jupiter': swe.JUPITER, 'Saturn': swe.SATURN,
           'Rahu': swe.MEAN_NODE, 'Ketu': swe.MEAN_NODE}

    def lon(name, jd):
        r = swe.calc_ut(jd, ids[name], flags)[0]
        v = (r[0] + (180.0 if name == 'Ketu' else 0.0)) % 360
        return v, r[3]

    def diff(name, jd):
        return ((lon(name, jd)[0] - target_deg + 180.0) % 360.0) - 180.0

    y0, m0, d0 = map(int, start.split('-'))
    y1, m1, d1 = map(int, end.split('-'))
    jd0, jd1 = swe.julday(y0, m0, d0, 0.0), swe.julday(y1, m1, d1, 0.0)
    out = []
    for name in planets:
        if name not in ids:
            raise ValueError(f"不支持的行星 {name}（可用: {', '.join(ids)}）")
        jd, prev = jd0, diff(name, jd0)
        while jd < jd1:
            nxt_jd = min(jd + 1.0, jd1)
            cur = diff(name, nxt_jd)
            if (prev < 0 <= cur or prev >= 0 > cur) and abs(prev - cur) < 30:
                lo, hi = jd, nxt_jd
                while hi - lo > 0.01:
                    mid = (lo + hi) / 2
                    if (diff(name, mid) < 0) == (prev < 0):
                        lo = mid
                    else:
                        hi = mid
                y, m, d, _ = swe.revjul(hi)
                speed = lon(name, hi)[1]
                out.append({'planet': name, 'date': f'{y:04d}-{m:02d}-{d:02d}',
                            'motion': '逆行' if speed < 0 else '顺行'})
            jd, prev = nxt_jd, cur
    return sorted(out, key=lambda e: (e['date'], e['planet']))


def _cli():
    import argparse
    import json
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser(description="""过运快照与换座/过点日期（真实星历计算，禁止凭记忆写日期）。
  刷新快照: transit.py --chart <目录>/chart_data.json [--date YYYY-MM-DD] --write
            （更新 chart_data.json 的过运快照并重新生成 structured_data.md；chart_id 不变）
  查看快照: transit.py --chart <目录>/chart_data.json --date 2027-03-01
  任意区间换座: transit.py --ingress-from 2016-01-01 --years 10
  过某度数: transit.py --hit 123.5 --planets Saturn,Jupiter --from 2016-01-01 --to 2030-12-31
退出码: 0 完成 / 2 参数或数据问题""", formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--chart", help="chart_data.json（快照需要上升与 Moon）")
    ap.add_argument("--date", help="快照日期 YYYY-MM-DD（当地正午）；缺省为现在")
    ap.add_argument("--write", action="store_true", help="把快照写回 chart_data.json 并重新生成 structured_data.md")
    ap.add_argument("--ingress-from", help="换座表起点 YYYY-MM-DD")
    ap.add_argument("--years", type=float, default=5)
    ap.add_argument("--hit", type=float, help="恒星黄经度数 0-360（如 Bhrigu Bindu）")
    ap.add_argument("--planets", default="Saturn,Jupiter,Rahu,Ketu")
    ap.add_argument("--from", dest="start")
    ap.add_argument("--to", dest="end")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if a.hit is not None:
        if not (a.start and a.end) or not (0 <= a.hit < 360):
            ap.error("--hit 需要 0-360 的度数和 --from/--to")
        res = degree_hits(a.hit, [p.strip() for p in a.planets.split(",") if p.strip()], a.start, a.end)
        if a.json:
            print(json.dumps(res, ensure_ascii=False, indent=1))
        else:
            print(f"经过恒星黄经 {a.hit:.2f}°（{SIGNS[int(a.hit // 30)]} {a.hit % 30:.2f}°）的日期，{a.start} ~ {a.end}：")
            for e in res:
                print(f"  {e['date']}  {e['planet']}  {e['motion']}")
            if not res:
                print("  区间内没有经过")
        return 0

    if a.ingress_from:
        y, m, d = map(int, a.ingress_from.split("-"))
        res = future_ingress_table(swe.julday(y, m, d, 0.0), years=a.years)
        if a.json:
            print(json.dumps(res, ensure_ascii=False, indent=1))
        else:
            print(f"Saturn/Jupiter/Rahu 换座（{a.ingress_from} 起 {a.years:g} 年，含逆行回跨）：")
            for e in res:
                print(f"  {e['date']}  {e['planet']}  {e['from_sign']} → {e['to_sign']}")
        return 0

    if not a.chart:
        ap.error("需要 --chart，或使用 --ingress-from / --hit")
    import chart_io as cio
    doc = cio.load_doc(a.chart)
    ch = doc.get("chart", {})
    if doc.get("input", {}).get("mode") != "full" or cio.is_missing(ch.get("lagna")) or not isinstance(ch.get("lagna"), dict):
        print("这份数据没有上升（仅日期或旧版导入），不能生成带宫位的过运快照；换座日期用 --ingress-from。", file=sys.stderr)
        return 2
    moon = (ch.get("planets") or {}).get("Moon")
    if not isinstance(moon, dict) or "sign_idx" not in moon:
        print("缺 Moon 星座，无法计算 Sade Sati。", file=sys.stderr)
        return 2
    tr = calc_transit(ch["lagna"]["sign_idx"], moon["sign_idx"], doc["input"].get("tz") or "UTC", on_date=a.date)
    if a.json:
        print(json.dumps(tr, ensure_ascii=False, indent=1))
    else:
        print(f"过运快照 {tr['date']}（chart_id={doc.get('chart_id')}）")
        for name, d in tr["planets"].items():
            print(f"  {name}: {d['sign']}（本命第 {d['house']} 宫）")
        print(f"  Sade Sati: {tr['sade_sati']['status']}；双过运宫位: {tr['double_transit']}")
    if a.write:
        doc["transit"] = tr
        doc.setdefault("provenance", {})["transit_refreshed_at"] = cio.now_iso()
        cio.save_doc(doc, a.chart)
        from build_chart import render_md
        md_path = os.path.join(os.path.dirname(os.path.abspath(a.chart)), "structured_data.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(render_md(doc))
        print(f"[写回] {a.chart}\n[重新生成] {md_path}")
    return 0


if __name__ == '__main__':
    import sys as _sys
    _sys.exit(_cli())
