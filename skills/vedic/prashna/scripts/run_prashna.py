#!/usr/bin/env python3
"""run_prashna.py — 取象单写好之后，一条命令跑完判定、时间副层与 Tajika 过程层。

    python prashna/scripts/run_prashna.py --dir <prashna_* 目录>

读当前目录的 prashna_meta.json（起盘时写下的时刻、地点、宫主）与 prashna_plan.json（取象单），
依次以子进程调用：

  1. judge_prashna_standard.py   → prashna_verdict.json / prashna_verdict.md（成事账、内部档）
  2. build_timing_overlay.py     → timing_overlay.md（只在判定给出 timing=general|return 时）
  3. build_tajika_overlay.py     → tajika_overlay.md（过程层：两边在靠近还是走远；能跑就跑）

本脚本只做调度：不导入判定、时间、Tajika 的任何模块，三者之间的隔离不变（各自是独立进程，
互不读取对方的结果）。它不算任何占星量，也不改任何一层的结论。

Tajika 过程层不运行的情况（与 resources/tajika-layer.md 一致）：描述型；问者星与事项星是同一颗。
查表题、不判题没有取象单，不会走到这里。

改了取象单重跑时，上一次留下、这一次不再适用的 timing_overlay.md / tajika_overlay.md 会改名为
*.superseded.md，避免判读单引用到旧结果。

退出码：0 全部完成 / 1 某一步出错 / 2 输入不全（缺 prashna_meta.json 或取象单）。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_TAJIKA_PLANETS = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn")
_TIMING_VERDICT = {"偏成": "favorable", "持平": "pending"}


def _fail(code: int, message: str) -> None:
    print(message, file=sys.stderr)
    sys.exit(code)


def _run(script: str, args: list[str]) -> str:
    proc = subprocess.run(
        [sys.executable, str(_HERE / script), *args],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        _fail(1, f"[出错] {script} 退出码 {proc.returncode}\n{proc.stdout}{proc.stderr}".rstrip())
    return proc.stdout.strip()


def _supersede(path: Path) -> bool:
    if not path.exists():
        return False
    path.replace(path.with_name(path.stem + ".superseded.md"))
    return True


def _line_starting(path: Path, prefix: str) -> str:
    if not path.exists():
        return ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return ""


def main() -> None:
    ap = argparse.ArgumentParser(description="Prashna：判定 + 时间副层 + Tajika 过程层")
    ap.add_argument("--dir", required=True, help="当前 prashna_* 目录（build_prashna_data.py 打印的那个）")
    ap.add_argument("--plan", help="取象单路径；缺省为 <dir>/prashna_plan.json")
    ap.add_argument("--no-tajika", action="store_true", help="这一次不跑 Tajika 过程层")
    a = ap.parse_args()

    out = Path(a.dir).expanduser().resolve()
    if not out.is_dir() or not out.name.startswith("prashna_"):
        _fail(2, f"[输入不全] {out} 不是 prashna_* 目录")
    meta_path = out / "prashna_meta.json"
    if not meta_path.exists():
        _fail(2, f"[输入不全] {out} 下没有 prashna_meta.json：这张盘不是本版 build_prashna_data.py 起的。"
                 "用 structured_prashna.md 元信息里的时刻与地点，按 MODULE.md 分步运行各脚本。")
    plan_path = Path(a.plan).expanduser().resolve() if a.plan else out / "prashna_plan.json"
    if not plan_path.exists():
        _fail(2, f"[输入不全] 没有取象单 {plan_path}：先按 resources/question-decomposition.md 第 5 节写好。")

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        _fail(2, f"[输入不全] 取象单不是合法 JSON：{exc}")
    common = ["--datetime", meta["instant"], "--lat", str(meta["lat"]), "--lon", str(meta["lon"]),
              "--tz", meta["tz"]]

    # 1. 判定
    judged = _run("judge_prashna_standard.py", [*common, "--plan", str(plan_path), "--out-dir", str(out)])
    verdict = json.loads((out / "prashna_verdict.json").read_text(encoding="utf-8"))
    print(judged.splitlines()[0] if judged else "[OK] 判定完成")

    # 2. 时间副层
    timing_path = out / "timing_overlay.md"
    timing_mode = verdict.get("timing", "none")
    if timing_mode != "none" and verdict.get("tier") in _TIMING_VERDICT:
        _run("build_timing_overlay.py", [
            *common, "--matter-house", str(verdict["matter_house"]), "--mode", timing_mode,
            "--verdict", _TIMING_VERDICT[verdict["tier"]], "--out-dir", str(out)])
        print(f"[OK] 时间副层：已运行（{timing_mode}）→ {timing_path.name}")
    else:
        why = _line_starting(out / "prashna_verdict.md", "**时间副层**：") or "不运行"
        moved = "；上一次的 timing_overlay.md 已改名为 .superseded.md" if _supersede(timing_path) else ""
        print(f"[--] 时间副层：{why}{moved}")

    # 3. Tajika 过程层
    tajika_path = out / "tajika_overlay.md"
    querent = meta["house_lords"]["1"]
    matter = (verdict.get("ability") or {}).get("planet") or meta["house_lords"].get(str(verdict.get("matter_house")))
    skip = ""
    if a.no_tajika:
        skip = "按 --no-tajika 跳过"
    elif plan.get("matter") == "描述" or verdict.get("tier") == "描述":
        skip = "描述型问的是局面，不是成败，接触过程没有可答的结果"
    elif not matter or matter not in _TAJIKA_PLANETS or querent not in _TAJIKA_PLANETS:
        skip = "取不到问者星或事项星"
    elif querent == matter:
        skip = f"问者星与事项星是同一颗（{querent}）；原典对主星相同的处理未核，不拿别的星顶替"
    if skip:
        moved = "；上一次的 tajika_overlay.md 已改名为 .superseded.md" if _supersede(tajika_path) else ""
        print(f"[--] Tajika 过程层：不运行（{skip}）{moved}")
    else:
        _run("build_tajika_overlay.py", [
            *common, "--querent-lord", querent, "--matter-lord", matter, "--out-dir", str(out)])
        head = _line_starting(tajika_path, "**结论**：")
        now = _line_starting(tajika_path, "- 当前关系：")
        print(f"[OK] Tajika 过程层：问者星 {querent} × 事项星 {matter} → {tajika_path.name}")
        if now:
            print(f"     当前关系：{now}")
        if head:
            print(f"     过程结论：{head}")

    print(f"[下一步] 读 prashna_verdict.md"
          + ("、timing_overlay.md" if timing_path.exists() else "")
          + ("、tajika_overlay.md" if tajika_path.exists() else "")
          + f"，按 resources/judgment-writing.md 写 prashna_judgment_{meta.get('label', '<label>')}.md")


if __name__ == "__main__":
    main()
