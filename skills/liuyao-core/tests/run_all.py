#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跑全部程序测试：python tests/run_all.py

覆盖三层里的前两层（排盘计算、程序异常）。第三层"使用情境"是模型行为测试，
清单在 tests/scenarios.yaml，跑法与结果见 docs/测试报告.md。
"""

import sys
import unittest
from pathlib import Path

if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    suite = unittest.defaultTestLoader.discover(str(here), pattern="test_*.py", top_level_dir=str(here.parent))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    print(f"\n共 {result.testsRun} 项；失败 {len(result.failures)}，出错 {len(result.errors)}，跳过 {len(result.skipped)}")
    for test, why in result.skipped:
        print(f"  跳过 {test.id()}：{why}")
    sys.exit(0 if result.wasSuccessful() else 1)
