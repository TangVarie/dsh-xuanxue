#!/usr/bin/env python3
"""独立星历对照：用 astropy（ERFA 内置星历，与 Swiss Ephemeris 无关）复算 chart_data.json 的位置。

python tests/bench_positions.py --chart <目录>/chart_data.json [--tol-arcmin 2] [--json]

对照项（全部是恒星黄道 True Chitra）：
  - Ayanamsa：Spica（Hipparcos 位置 + 自行）当日平黄经 − 180°
  - Sun…Saturn：几何位置（不含光行时与光行差）、当日平黄道
  - Rahu：Meeus 平交点公式
  - Lagna：由当地恒星时、黄赤交角、纬度直接计算
  - Vimsottari 首段与第 9 段 MD 结束日：用盘内 Moon 经度 × 恒星年 365.256364 天独立推算（容差 1 天；
    第 9 段累计约 120 年，年长口径出错会被放大）
退出码: 0 全部在容差内 / 1 有超差 / 2 缺 astropy 或数据不全
说明：这验证的是位置与 Dasha 日期的数值，不验证解读规则。ERFA 内置星历（plan94）对木星、土星本身有约 1′ 的误差，
所以容差取 2′；Ayanamsa 一行的差主要是章动（盘内 Ayanamsa 数值含章动，行星位置不含，两者相减后抵消）。
"""
import argparse
import json
import math
import sys
from datetime import datetime, timedelta

try:
    import numpy as np
    import astropy.units as u
    from astropy.time import Time
    from astropy.coordinates import (SkyCoord, CartesianRepresentation, GCRS, GeocentricMeanEcliptic,
                                     get_body_barycentric, solar_system_ephemeris, Distance)
except ImportError as exc:  # 环境不具备时只报未完成
    print(f"未完成：缺 astropy（{exc}）")
    sys.exit(2)

LORDS = ['Ketu', 'Venus', 'Sun', 'Moon', 'Mars', 'Rahu', 'Jupiter', 'Saturn', 'Mercury']
YEARS = {'Ketu': 7, 'Venus': 20, 'Sun': 6, 'Moon': 10, 'Mars': 7, 'Rahu': 18, 'Jupiter': 16, 'Saturn': 19, 'Mercury': 17}
SIDEREAL_YEAR = 365.256364
BODIES = {'Sun': 'sun', 'Moon': 'moon', 'Mars': 'mars', 'Mercury': 'mercury',
          'Jupiter': 'jupiter', 'Venus': 'venus', 'Saturn': 'saturn'}


def wrap(d):
    return (d + 180.0) % 360.0 - 180.0


def mean_ecl_lon(cart_au, t):
    """GCRS 轴向的几何矢量 → 当日平黄道黄经（度）。"""
    c = SkyCoord(CartesianRepresentation(cart_au), frame=GCRS(obstime=t))
    e = c.transform_to(GeocentricMeanEcliptic(equinox=t, obstime=t))
    return float(e.lon.to_value(u.deg))


def spica_lon(t):
    s = SkyCoord(ra=201.29824736 * u.deg, dec=-11.16131949 * u.deg, distance=Distance(parallax=13.06 * u.mas),
                 pm_ra_cosdec=-42.35 * u.mas / u.yr, pm_dec=-30.67 * u.mas / u.yr, radial_velocity=1.0 * u.km / u.s,
                 obstime=Time("J1991.25"), frame="icrs")
    s2 = s.apply_space_motion(new_obstime=t)
    v = s2.cartesian.without_differentials()
    unit = v / v.norm()
    return mean_ecl_lon(CartesianRepresentation(unit.x.value, unit.y.value, unit.z.value) * u.au, t)


def mean_node(t):
    T = (t.tt.jd - 2451545.0) / 36525.0
    return (125.0445479 - 1934.1362891 * T + 0.0020754 * T ** 2 + T ** 3 / 467441 - T ** 4 / 60616000) % 360


def ascendant(t, lat, lon):
    T = (t.tt.jd - 2451545.0) / 36525.0
    eps = math.radians(23.439291111 - 0.0130041667 * T - 1.6667e-7 * T ** 2 + 5.0278e-7 * T ** 3)  # 平黄赤交角
    lst = math.radians(t.sidereal_time("mean", longitude=lon * u.deg).to_value(u.deg))
    phi = math.radians(lat)
    asc = math.degrees(math.atan2(math.cos(lst), -(math.sin(lst) * math.cos(eps) + math.tan(phi) * math.sin(eps))))
    return asc % 360


def parse_offset(s):
    """str(timedelta) → timedelta，如 '8:00:00'、'-1 day, 21:00:00'（= -3 小时）。"""
    import re
    m = re.fullmatch(r"\s*(?:(-?\d+) days?, )?(-?)(\d+):(\d+)(?::(\d+))?\s*", str(s))
    if not m:
        raise ValueError(f"无法解析 UTC 偏移: {s}")
    days = int(m.group(1) or 0)
    td = timedelta(hours=int(m.group(3)), minutes=int(m.group(4)), seconds=int(m.group(5) or 0))
    return timedelta(days=days) + (-td if m.group(2) else td)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chart", required=True)
    ap.add_argument("--tol-arcmin", type=float, default=2.0)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    doc = json.load(open(a.chart, encoding="utf-8"))
    inp, ch = doc["input"], doc["chart"]
    if inp.get("mode") != "full":
        print("未完成：只对完整盘做对照")
        sys.exit(2)
    local = datetime.strptime(f"{inp['date']} {inp['time_used']}", "%Y-%m-%d %H:%M")
    utc = local - parse_offset(inp["utc_offset"])
    t = Time(utc.strftime("%Y-%m-%d %H:%M:%S"), scale="utc")
    rows = []
    with solar_system_ephemeris.set("builtin"):
        earth = get_body_barycentric("earth", t)
        ayan = spica_lon(t) - 180.0
        rows.append(("Ayanamsa", ch["ayanamsa"], ayan))
        for name, body in BODIES.items():
            geo = get_body_barycentric(body, t) - earth
            sid = (mean_ecl_lon(geo, t) - ayan) % 360
            rows.append((name, ch["planets"][name]["longitude"], sid))
    rows.append(("Rahu", ch["planets"]["Rahu"]["longitude"], (mean_node(t) - ayan) % 360))
    rows.append(("Lagna", ch["lagna"]["longitude"], (ascendant(t, inp["lat"], inp["lon"]) - ayan) % 360))
    res = [{"item": n, "chart": round(c, 5), "independent": round(i, 5),
            "diff_arcmin": round(abs(wrap(c - i)) * 60, 3)} for n, c, i in rows]
    # Vimsottari 首段 MD 结束日（用盘内 Moon 经度，验证 Dasha 算术与年长口径）
    moon = ch["planets"]["Moon"]["longitude"]
    span = 360 / 27
    idx = int(moon // span)
    lord = LORDS[idx % 9]
    frac = (moon % span) / span
    md_end_expected = utc + timedelta(days=(1 - frac) * YEARS[lord] * SIDEREAL_YEAR)
    first = ch["dashas"][0]
    last_ad = first["antardashas"][-1]
    md_end_chart_local = datetime.strptime(last_ad.get("end_time") or last_ad["end"], "%Y-%m-%d %H:%M"
                                           if last_ad.get("end_time") else "%Y-%m-%d")
    md_end_chart = md_end_chart_local - parse_offset(inp["utc_offset"])
    dd = abs((md_end_chart - md_end_expected).total_seconds()) / 86400
    # 第 9 段 MD 结束日：累计约 120 年，能放大年长口径的错误（真恒星年与平均恒星年之差 120 年内 < 1 天）
    last = ch["dashas"][-1]
    total_years = (1 - frac) * YEARS[lord] + sum(YEARS[m["planet"]] for m in ch["dashas"][1:])
    last_expected = utc + timedelta(days=total_years * SIDEREAL_YEAR)
    la = last["antardashas"][-1]
    last_chart = datetime.strptime(la.get("end_time") or la["end"], "%Y-%m-%d %H:%M" if la.get("end_time") else "%Y-%m-%d") \
        - parse_offset(inp["utc_offset"])
    dl = abs((last_chart - last_expected).total_seconds()) / 86400
    dasha = {"first_md": first["planet"], "expected_lord": lord, "chart_end_utc": md_end_chart.isoformat(),
             "expected_end_utc": md_end_expected.isoformat(timespec="minutes"), "diff_days": round(dd, 3),
             "last_md": last["planet"], "last_end_chart_utc": last_chart.isoformat(),
             "last_end_expected_utc": last_expected.isoformat(timespec="minutes"), "last_diff_days": round(dl, 3)}
    bad = [r for r in res if r["diff_arcmin"] > a.tol_arcmin] + \
        ([dasha] if (dd > 1.0 or dl > 1.0 or first["planet"] != lord or len(ch["dashas"]) != 9) else [])
    out = {"chart_id": doc.get("chart_id"), "tolerance_arcmin": a.tol_arcmin, "positions": res, "vimsottari": dasha,
           "max_diff_arcmin": max(r["diff_arcmin"] for r in res), "status": "失败" if bad else "通过"}
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        print(f"chart_id={out['chart_id']} 独立星历对照（容差 {a.tol_arcmin}′）")
        for r in res:
            print(f"  {r['item']:<8} 盘内 {r['chart']:>10.4f}°  独立 {r['independent']:>10.4f}°  差 {r['diff_arcmin']:.2f}′")
        print(f"  Vimsottari 首段 {first['planet']}（应为 {lord}）结束: 盘内 {dasha['chart_end_utc']} UTC / 独立推算 "
              f"{dasha['expected_end_utc']} UTC，差 {dasha['diff_days']} 天")
        print(f"  Vimsottari 第 9 段 {last['planet']} 结束: 盘内 {dasha['last_end_chart_utc']} UTC / 独立推算 "
              f"{dasha['last_end_expected_utc']} UTC，差 {dasha['last_diff_days']} 天")
        print(f"状态: {out['status']}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
