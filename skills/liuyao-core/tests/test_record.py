# -*- coding: utf-8 -*-
"""复盘记录校验测试（字段定义见 references/22 第十节）"""

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import record as R  # noqa: E402

GOOD = {
    "记录编号": "2026-10-12-01",
    "起卦时间": {"公历": "2026-10-12 14:30", "时区": "+08:00", "四值": "丙午年 戊戌月 己未日 辛未时", "干支来源": "脚本换算"},
    "起卦方式": "铜钱",
    "卦": "水火既济之水雷屯",
    "问题": {"来意摘要": "本人问年底前尾款能否收回", "问法类型": "能否成", "时限": "2026-12-31"},
    "输入版本": "v1",
    "主用神": {"主": "妻财", "备选": []},
    "规则版本": "r6.0",
    "门派": "默认",
    "各镜独立结论": {"主流镜": "财爻旺而受克，先难后得", "张德镜": "应克世，对方压力找上门，钱款要靠催"},
    "最终主判": "先拖后得",
    "备选与触发条件": ["若子日前对方仍无回应，则时限内不定"],
    "关键反证": ["应爻旬空（假空）：对方暂未落实"],
    "应期候选": [{"时间": "子月", "依据": "子冲午，冲起财爻"}],
    "置信度": {"等级": "中", "理由": "来意清、用神清；结论依赖'静爻受生'一条，仅曲炜派成立，降一档"},
    "可观察结果": {"应验": "尾款到账（银行流水为准）", "未应": "年底前未到账；对方只口头答应付款不算到账",
              "时间窗口": {"起": "2026-10-12", "止": "2026-12-31"}},
    "修订记录": [],
    "事后结果": None,
}


class TestRecord(unittest.TestCase):
    def test_good(self):
        self.assertEqual(R.validate_record(GOOD), [])

    def test_template_is_not_complete(self):
        self.assertTrue(R.validate_record(R.TEMPLATE))   # 空模板必须填完才通过

    def mutated(self, fn):
        r = copy.deepcopy(GOOD)
        fn(r)
        return R.validate_record(r)

    def test_mirrors_required(self):
        self.assertTrue(self.mutated(lambda r: r["各镜独立结论"].pop("张德镜")))
        self.assertTrue(self.mutated(lambda r: r.update({"各镜独立结论": {}})))

    def test_observable_required(self):
        self.assertTrue(self.mutated(lambda r: r["可观察结果"].update({"未应": ""})))
        self.assertTrue(self.mutated(lambda r: r["可观察结果"].pop("时间窗口")))
        self.assertTrue(self.mutated(lambda r: r["可观察结果"]["时间窗口"].update({"起": "2027-01-01"})))

    def test_limits(self):
        self.assertTrue(self.mutated(lambda r: r.update({"应期候选": [{"时间": "a", "依据": "b"}] * 4})))
        self.assertTrue(self.mutated(lambda r: r["置信度"].update({"等级": "中高"})))
        self.assertTrue(self.mutated(lambda r: r["问题"].update({"问法类型": "问感情"})))

    def test_post_outcome(self):
        def in_window(r):
            r["事后结果"] = {"日期": "2026-12-05", "实际": "到账", "判定": "应验",
                          "各镜判定": {"主流镜": "应验", "张德镜": "应验"}}
        self.assertEqual(self.mutated(in_window), [])
        def outside(r):
            in_window(r)
            r["事后结果"]["日期"] = "2027-01-20"
        self.assertTrue(any("窗口" in x for x in self.mutated(outside)))
        def no_each(r):
            in_window(r)
            r["事后结果"].pop("各镜判定")
        self.assertTrue(self.mutated(no_each))
        def no_obs(r):
            in_window(r)
            r["可观察结果"] = {}
        self.assertTrue(any("无法判定" in x for x in self.mutated(no_obs)))

    def test_revision_fields(self):
        self.assertTrue(self.mutated(lambda r: r["修订记录"].append({"时间": "2026-10-13", "改动": "日辰"})))
        self.assertEqual(self.mutated(lambda r: r["修订记录"].append(
            {"时间": "2026-10-13", "改动": "日辰 己未→庚申", "原因": "用户纠正起卦日期", "受影响结论": "旬空、六神、应期日级"})), [])

    def test_one_line(self):
        line = R.one_line(GOOD)
        self.assertIn("先拖后得", line)
        self.assertIn("未复盘", line)


if __name__ == "__main__":
    unittest.main()


class TestCanonicalExample(unittest.TestCase):
    def test_example_record_in_24_is_valid(self):
        import json
        import re
        text = (Path(__file__).resolve().parent.parent / "references" / "24_规范示例.md").read_text(encoding="utf-8")
        block = re.search(r"```json\n(.*?)```", text, re.S).group(1)
        self.assertEqual(R.validate_record(json.loads(block)), [])
