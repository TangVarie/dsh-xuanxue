"""
Tajika 过程层与调度脚本的回归测（vedic 5.3 新增；上游公开仓没有 Tajika 的测试）。

  1. 出版接触几何：Journal of Astrology article 153（1994-06-11 18:45 IST）——
     Scorpio 20°08′ 上升、Mars Aries 20°02′、Saturn Aquarius 18°30′，Mars–Saturn sextile。
     （tajika-layer.md「进入可用状态的门」记的那一张；地点原文未单列，Delhi 坐标可复现公开 Lagna。）
  2. 规则级出版正例：Hāyanaratna 3.3 的 Sun Leo 2°／Mars Scorpio 16°，14° × 12 = 168 日，
     接触边界用较快星自己的 deeptamsha（两星平均会错拒这个例子）。
  3. 靠近／走远的独立复算：不用被测公式里的"有符号相对速度"，直接取 10 分钟后的真实星历位置，
     看离精确相位的距离是变小还是变大；对 40 个随机时刻的全部容许度内接触逐个比对（含逆行）。
  4. run_prashna.py：一条命令跑出判定、时间副层、过程层；描述型与主星相同的题不跑过程层；
     跑不跑过程层，标准层的 prashna_verdict.json 逐字节相同（过程层不进账本、不改档）。

用 calculator 的计算环境解释器运行。
"""
import contextlib
import io
import json
import random
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]            # <vedic>
SCRIPTS = ROOT / "prashna" / "scripts"
CALC = ROOT / "calculator" / "scripts"
for p in (str(CALC), str(SCRIPTS)):
    if p not in sys.path:
        sys.path.insert(0, p)

with contextlib.redirect_stdout(io.StringIO()):
    import engine
    import prashna_time as pt
    import calc_optional_tajika as tj


def _chart(dt, lat, lon, tz):
    with contextlib.redirect_stdout(io.StringIO()):
        return pt.calculate_prashna_chart(dt, lat, lon, tz)


def _deg(sign_deg, minutes):
    return sign_deg + minutes / 60.0


def test_published_contact_geometry() -> None:
    dt = datetime(1994, 6, 11, 18, 45, tzinfo=ZoneInfo("Asia/Kolkata"))
    c = _chart(dt, 28.6139, 77.2090, "Asia/Kolkata")
    lagna, mars, saturn = c["lagna"], c["planets"]["Mars"], c["planets"]["Saturn"]
    assert lagna["sign"] == "Scorpio" and abs(lagna["degree"] - _deg(20, 8)) < 0.25, lagna
    assert mars["sign"] == "Aries" and abs(mars["degree"] - _deg(20, 2)) < 0.1, mars
    assert saturn["sign"] == "Aquarius" and abs(saturn["degree"] - _deg(18, 30)) < 0.1, saturn
    rec = tj._contact(c["planets"], "Mars", "Saturn")
    assert rec and rec["aspect_name"] == "sextile" and rec["quality"] == "friendly", rec
    assert rec["faster"] == "Mars" and abs(rec["distance_from_exact_deg"] - 1.53) < 0.15, rec


def test_hayanaratna_sun_mars_example() -> None:
    planets = {
        "Sun": {"longitude": 120.0 + 2.0, "speed": 0.96, "retrograde": False},
        "Mars": {"longitude": 210.0 + 16.0, "speed": 0.60, "retrograde": False},
    }
    rec = tj._contact(planets, "Sun", "Mars")
    assert rec is not None, "较快星 Sun 的 deeptamsha 是 15°，14° 的方照应在边界内"
    assert (rec["faster"], rec["aspect_name"], rec["yoga"]) == ("Sun", "square", "itthasala"), rec
    assert abs(rec["distance_from_exact_deg"] - 14.0) < 1e-6 and rec["orb_limit_deg"] == 15.0, rec
    assert abs(rec["distance_from_exact_deg"] * 12.0 - 168.0) < 1e-4
    # 两星平均容许度（(15+8)/2 = 11.5°）会把它拒掉：确认边界不是平均值
    assert rec["orb_limit_deg"] > 14.0 > (tj.TAJIKA_ORBS["Sun"] + tj.TAJIKA_ORBS["Mars"]) / 2


def _separation(jd, a, b, branch):
    """a 相对 b 的黄经差离 branch（度）有多远；用真实星历位置。"""
    la = engine.calc_planet(jd, engine.PLANETS_SWE[a])["longitude"]
    lb = engine.calc_planet(jd, engine.PLANETS_SWE[b])["longitude"]
    return abs(((la - lb - branch + 180.0) % 360.0) - 180.0)


def test_applying_separating_against_ephemeris() -> None:
    rng = random.Random(53)
    zone = ZoneInfo("Asia/Shanghai")
    checked = disagreements = retro_checked = 0
    for _ in range(40):
        dt = datetime(rng.randint(1990, 2035), rng.randint(1, 12), rng.randint(1, 28),
                      rng.randint(0, 23), rng.randint(0, 59), rng.randint(0, 59), tzinfo=zone)
        c = _chart(dt, 31.23, 121.47, "Asia/Shanghai")
        jd = pt.local_datetime_to_jd(dt, "Asia/Shanghai")
        for rec in tj._all_contacts(c["planets"]).values():
            if rec["motion_state"] not in ("applying", "separating"):
                continue
            f, s, branch = rec["faster"], rec["slower"], rec["aspect_branch"]
            now = _separation(jd, f, s, branch)
            assert abs(now - rec["distance_from_exact_deg"]) < 1e-4, (dt, rec, now)
            later = _separation(jd + 10.0 / 1440.0, f, s, branch)
            if abs(later - now) < 1e-7:        # 相对停滞，不比
                continue
            if later > now and now < 0.01:     # 十分钟内越过精确点，不比
                continue
            checked += 1
            retro_checked += any(rec["retrograde"].values())
            independent = "applying" if later < now else "separating"
            if independent != rec["motion_state"]:
                disagreements += 1
                print("  不一致:", dt, rec["pair"], rec["motion_state"], "独立复算", independent)
    assert checked >= 150 and retro_checked >= 20, (checked, retro_checked)
    assert disagreements == 0, f"{disagreements}/{checked} 个接触的靠近／走远与真实星历不一致"
    print(f"  独立复算 {checked} 个接触（其中 {retro_checked} 个含逆行星），全部一致")


def _cli(script, *args):
    proc = subprocess.run([sys.executable, str(SCRIPTS / script), *args], capture_output=True, text=True)
    assert proc.returncode == 0, f"{script} 退出码 {proc.returncode}\n{proc.stdout}\n{proc.stderr}"
    return proc.stdout


def test_runner_and_isolation() -> None:
    with tempfile.TemporaryDirectory(prefix="prashna-test-") as tmp:
        _cli("build_prashna_data.py", "--datetime", "2026-11-16 12:31:07.25", "--lat", "31.2304",
             "--lon", "121.4737", "--tz", "Asia/Shanghai", "--question", "这份合作能不能签下来",
             "--label", "deal", "--out-parent", tmp)
        out = next(Path(tmp).glob("prashna_*"))
        meta = json.loads((out / "prashna_meta.json").read_text(encoding="utf-8"))
        assert meta["instant"] == "2026-11-16 12:31:07.250000+08:00" and meta["house_lords"]["1"] == "Saturn", meta
        plan = out / "prashna_plan.json"

        # 事件型：三件产物都出；过程层跑不跑，标准层判定逐字节相同
        plan.write_text(json.dumps({"matter": "合作", "location": "city"}, ensure_ascii=False), encoding="utf-8")
        text = _cli("run_prashna.py", "--dir", str(out))
        assert "Tajika 过程层：问者星 Saturn × 事项星 Moon" in text, text
        with_layer = (out / "prashna_verdict.json").read_bytes()
        assert (out / "timing_overlay.md").exists() and (out / "tajika_overlay.md").exists()
        overlay = (out / "tajika_overlay.md").read_text(encoding="utf-8")
        assert "不改写标准层结论" in overlay and "偏成／持平／偏不成" in overlay, overlay[:400]
        _cli("run_prashna.py", "--dir", str(out), "--no-tajika")
        assert (out / "prashna_verdict.json").read_bytes() == with_layer
        assert not (out / "tajika_overlay.md").exists() and (out / "tajika_overlay.superseded.md").exists()

        # 主星相同（事项宫 1 宫）：不运行，不拿别的星顶替
        plan.write_text(json.dumps({"matter": "挽回", "location": "city"}, ensure_ascii=False), encoding="utf-8")
        text = _cli("run_prashna.py", "--dir", str(out))
        assert "Tajika 过程层：不运行（问者星与事项星是同一颗（Saturn）" in text, text
        assert not (out / "tajika_overlay.md").exists()

        # 描述型：不定档、不给时间、不跑过程层；上一次的时间副层不留在原名下
        plan.write_text(json.dumps({"matter": "描述", "matter_house": 7}, ensure_ascii=False), encoding="utf-8")
        text = _cli("run_prashna.py", "--dir", str(out))
        assert "Tajika 过程层：不运行（描述型" in text and "时间副层：不运行" in text, text
        assert not (out / "timing_overlay.md").exists()

        # 缺取象单：退出码 2，说明缺什么
        plan.unlink()
        proc = subprocess.run([sys.executable, str(SCRIPTS / "run_prashna.py"), "--dir", str(out)],
                              capture_output=True, text=True)
        assert proc.returncode == 2 and "没有取象单" in proc.stderr, (proc.returncode, proc.stderr)

    # 调度脚本只起子进程，不导入任何一层
    code = (SCRIPTS / "run_prashna.py").read_text(encoding="utf-8")
    for mod in ("prashna_rules", "judge_prashna_standard", "calc_timing", "build_timing_overlay",
                "calc_optional_tajika", "build_tajika_overlay", "engine"):
        assert f"import {mod}" not in code and f"from {mod}" not in code, mod


def _run(name, fn):
    try:
        fn()
        print(f"[PASS] {name}")
        return True
    except AssertionError as e:
        print(f"[FAIL] {name}\n{e}\n")
        return False


if __name__ == "__main__":
    results = [
        _run("published_contact_geometry", test_published_contact_geometry),
        _run("hayanaratna_sun_mars_example", test_hayanaratna_sun_mars_example),
        _run("applying_separating_against_ephemeris", test_applying_separating_against_ephemeris),
        _run("runner_and_isolation", test_runner_and_isolation),
    ]
    if all(results):
        print("\n[GREEN] Tajika 过程层几何、出版正例、独立复算与调度脚本全绿。")
        sys.exit(0)
    print("\n[RED] Tajika 过程层测试未全绿。")
    sys.exit(1)
