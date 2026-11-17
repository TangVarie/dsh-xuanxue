# -*- coding: utf-8 -*-
"""Jev 预判组件的异常处理测试：不联网，用假响应、假网络、假时钟。

验收标准：异常输出不会成为可用依据（usable 恒为 False）；任何失败都返回明确的 error_code，不抛异常。
"""

import copy
import io
import json
import math
import os
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import jev_judge as J  # noqa: E402

try:
    import yaml  # noqa: F401
    HAVE_YAML = True
except ImportError:
    HAVE_YAML = False

CASE = {"来意摘要": "女，问和前男友还有没有可能复合；想知道能不能成。", "求测者性别": "女", "关系": "双方"}


@unittest.skipUnless(HAVE_YAML, "缺 PyYAML")
class TestBankAndCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bank = J.load_bank()

    def test_bank_ok(self):
        self.assertEqual(J.check_bank(self.bank), [])
        self.assertEqual(self.bank["bank_version"], "jq-v0.2")
        wq = next(q for q in self.bank["questions"] if q["id"] == "wenfa_type")
        self.assertEqual([o["label"] for o in wq["options"]], ["能否成", "走向好坏", "该不该", "只问时间", "说不清"])

    def test_case_validation(self):
        self.assertEqual(J.validate_case(CASE)["来意摘要"], CASE["来意摘要"])
        bad = [
            ({}, "bad_input"),
            ([], "bad_input"),
            ({"来意原话": "我和前男友能不能复合"}, "bad_input"),
            ({"来意摘要": "x", "卦盘": "天火同人"}, "bad_input"),
            ({"来意摘要": 123}, "bad_input"),
            ({"来意摘要": "x", "求测者性别": "male"}, "bad_input"),
            ({"来意摘要": "x" * 3000}, "bad_input"),
            ({"来意摘要": "   "}, "bad_input"),
        ]
        for case, code in bad:
            with self.assertRaises(J.JevError) as cm:
                J.validate_case(case)
            self.assertEqual(cm.exception.code, code, case)

    def test_chart_rejected(self):
        for text in ("我摇到天火同人，三爻动，问复合", "世爻官鬼旬空，问工作", "庚寅日起卦，问财运",
                     "初爻老阳，问考试", "卦里亥水官鬼发动，问官司", "本卦是噬嗑", "九五动问升职"):
            with self.assertRaises(J.JevError) as cm:
                J.validate_case({"来意摘要": text})
            self.assertEqual(cm.exception.code, "chart_in_input", text)
        with self.assertRaises(J.JevError):
            J.validate_case({"来意摘要": "问复合", "追问补充": "变卦是风雷益"})

    def test_gold_not_rejected(self):
        gold = yaml.safe_load((Path(J.__file__).parent / "jev_gold.yaml").read_text(encoding="utf-8"))
        for c in gold["cases"]:
            J.validate_case({k: c[k] for k in J.ALLOWED_FIELDS if c.get(k)})


@unittest.skipUnless(HAVE_YAML, "缺 PyYAML")
class TestResponseValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bank = J.load_bank()
        cls.good = J.mock_response(J.build_body(J.validate_case(CASE), cls.bank, "zh"))

    def bad(self, mutate):
        r = copy.deepcopy(self.good)
        mutate(r)
        return J.validate_response(r, self.bank)

    def test_good_passes(self):
        self.assertEqual(J.validate_response(self.good, self.bank), [])

    def test_structural_errors(self):
        a = "yongshen_main"
        cases = {
            "缺题": lambda r: r["answers"].pop("motive"),
            "题型不符": lambda r: r["answers"][a].update(type="noul"),
            "选项不在题库": lambda r: r["answers"][a].update(choice="财运"),
            "概率越界": lambda r: r["answers"][a]["probabilities"].update({"妻财": 1.5}),
            "概率NaN": lambda r: r["answers"][a]["probabilities"].update({"妻财": math.nan}),
            "概率是字符串": lambda r: r["answers"][a]["probabilities"].update({"妻财": "0.3"}),
            "题库外选项": lambda r: r["answers"][a]["probabilities"].update({"财运": 0.0}),
            "缺probabilities": lambda r: r["answers"][a].pop("probabilities"),
            "noul越界": lambda r: r["answers"]["single_matter"].update(noul=1.2),
            "noul缺失": lambda r: r["answers"]["single_matter"].pop("noul"),
            "noul布尔": lambda r: r["answers"]["single_matter"].update(noul=True),
            "answers不是对象": lambda r: r.update(answers=[]),
        }
        for name, fn in cases.items():
            self.assertTrue(self.bad(fn), name)

    def test_sum_and_argmax(self):
        a = "yongshen_main"
        def skew(r):
            probs = r["answers"][a]["probabilities"]
            for k in probs:
                probs[k] = 0.5
        self.assertTrue(self.bad(skew))                                  # 总和远超 1
        def not_argmax(r):
            ans = r["answers"][a]
            low = min(ans["probabilities"], key=ans["probabilities"].get)
            ans["choice"] = low
            ans["confidence"] = ans["probabilities"][low]
        self.assertTrue(self.bad(not_argmax))
        def conf_mismatch(r):
            r["answers"][a]["confidence"] = 0.01
        self.assertTrue(self.bad(conf_mismatch))

    def test_top_level_not_dict(self):
        for resp in (None, [], "ok", 3):
            self.assertTrue(J.validate_response(resp, self.bank))


@unittest.skipUnless(HAVE_YAML, "缺 PyYAML")
class TestJudgeStatuses(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bank = J.load_bank()

    def run_judge(self, call, case=CASE):
        with mock.patch.object(J, "find_api_key", return_value="k"):
            return J.judge(case, bank=self.bank, _call=call)

    def assertUnusable(self, r, code):
        self.assertEqual(r["status"], "error")
        self.assertFalse(r["usable"])
        self.assertEqual(r["error_code"], code)
        self.assertNotIn("answers", r)

    def test_ok(self):
        good = J.mock_response(J.build_body(J.validate_case(CASE), self.bank, "zh"))
        r = self.run_judge(lambda *a, **k: good)
        self.assertEqual((r["status"], r["usable"]), ("ok", True))
        self.assertIn("wenfa_type", r["answers"])

    def test_invalid_response(self):
        self.assertUnusable(self.run_judge(lambda *a, **k: {"answers": {}}), "invalid_response")
        self.assertUnusable(self.run_judge(lambda *a, **k: ["not", "dict"]), "invalid_response")

    def test_call_errors(self):
        def net(*a, **k):
            raise J.JevError("network", "连不上")
        self.assertUnusable(self.run_judge(net), "network")
        def boom(*a, **k):
            raise ValueError("意外")
        self.assertUnusable(self.run_judge(boom), "internal")

    def test_chart_case(self):
        self.assertUnusable(self.run_judge(lambda *a, **k: None, {"来意摘要": "天火同人三爻动"}), "chart_in_input")

    def test_mock_not_usable(self):
        r = J.judge(CASE, bank=self.bank, mock=True)
        self.assertEqual((r["status"], r["usable"]), ("mock", False))

    def test_no_key_skipped(self):
        with tempfile.TemporaryDirectory() as home, mock.patch.dict(os.environ, {"HOME": home, "USERPROFILE": home}, clear=True):
            r = J.judge(CASE, bank=self.bank)
        self.assertEqual((r["status"], r["usable"], r["error_code"]), ("skipped", False, "no_key"))

    def test_bank_invalid(self):
        broken = copy.deepcopy(self.bank)
        broken["questions"][0]["type"] = "multi"
        r = J.judge(CASE, bank=broken, mock=True)
        self.assertEqual((r["status"], r["error_code"]), ("error", "bank_invalid"))


class FakeClock:
    def __init__(self):
        self.t = 0.0
        self.sleeps = []

    def clock(self):
        return self.t

    def sleep(self, s):
        self.sleeps.append(s)
        self.t += s


class TestCallJev(unittest.TestCase):
    BODY = {"state": {}, "model": "m", "questions": {}}

    def http_error(self, code, headers=None):
        return urllib.error.HTTPError("u", code, "x", headers or {}, io.BytesIO(b"busy"))

    def test_retry_then_budget(self):
        clk = FakeClock()
        def opener(req, timeout):
            clk.t += timeout                        # 每次都等满单次超时
            raise self.http_error(503)
        with self.assertRaises(J.JevError) as cm:
            J.call_jev(self.BODY, "k", timeout=10, retries=5, total_timeout=25,
                       _urlopen=opener, _sleep=clk.sleep, _clock=clk.clock)
        self.assertIn(cm.exception.code, ("timeout_budget", "http_error"))
        self.assertLessEqual(clk.t, 25 + 1e-9)       # 总耗时不超过上限

    def test_long_retry_after_respects_budget(self):
        clk = FakeClock()
        def opener(req, timeout):
            raise self.http_error(429, {"retry-after": "30"})
        with self.assertRaises(J.JevError) as cm:
            J.call_jev(self.BODY, "k", timeout=5, retries=3, total_timeout=20,
                       _urlopen=opener, _sleep=clk.sleep, _clock=clk.clock)
        self.assertEqual(cm.exception.code, "timeout_budget")
        self.assertEqual(clk.sleeps, [])             # 不会去睡超出预算的 30 秒

    def test_no_retry_on_auth(self):
        calls = []
        def opener(req, timeout):
            calls.append(1)
            raise self.http_error(401)
        with self.assertRaises(J.JevError) as cm:
            J.call_jev(self.BODY, "k", _urlopen=opener, _sleep=lambda s: None)
        self.assertEqual((cm.exception.code, len(calls)), ("http_error", 1))

    def test_non_json(self):
        class Resp(io.BytesIO):
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False
        with self.assertRaises(J.JevError) as cm:
            J.call_jev(self.BODY, "k", _urlopen=lambda req, timeout: Resp(b"<html>"), _sleep=lambda s: None)
        self.assertEqual(cm.exception.code, "invalid_response")

    def test_network_errors_retry(self):
        clk = FakeClock()
        errs = [ConnectionResetError("reset"), urllib.error.URLError("dns"), OSError("other")]
        def opener(req, timeout):
            raise errs.pop(0) if errs else ConnectionError("x")
        with self.assertRaises(J.JevError) as cm:
            J.call_jev(self.BODY, "k", timeout=1, retries=2, total_timeout=60,
                       _urlopen=opener, _sleep=clk.sleep, _clock=clk.clock)
        self.assertEqual(cm.exception.code, "network")
        self.assertEqual(len(clk.sleeps), 2)


class TestNoYaml(unittest.TestCase):
    def test_missing_yaml_is_skipped(self):
        def no_yaml(*a, **k):
            raise J.JevError("no_yaml", "缺 PyYAML")
        with mock.patch.object(J, "load_bank", no_yaml):
            r = J.judge(CASE)
        self.assertEqual((r["status"], r["usable"], r["error_code"]), ("skipped", False, "no_yaml"))


class TestCli(unittest.TestCase):
    def test_bad_json_file(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            fh.write("{not json")
        out = io.StringIO()
        with mock.patch("sys.stdout", out):
            rc = J.main([fh.name])
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out.getvalue())["error_code"], "bad_input")


if __name__ == "__main__":
    unittest.main()
