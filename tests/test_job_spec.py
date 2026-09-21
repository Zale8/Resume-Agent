# -*- coding: utf-8 -*-
"""test_job_spec.py — design.json（本份 Design Decision）→ DesignSpec 与 `gen.py build`。

覆盖契约（对应审计 §R3「套用上一份」的结构性根因）：
    1. design.json **必须每份新建**：缺文件 → 拒绝；没有默认设计、没有兜底；
    2. 未定义的键（顶层与嵌套）→ 报错，**不静默忽略**（否则「改了没生效」
       会变成新的静默失败源）；
    3. design_intent 必填且不得是模板占位符（照抄模板也不算「做了设计」）；
    4. 取值下界：正文 9pt 下限、边距下界、照片必须显式宽高（禁变形）；
    5. margins → safe_area / content_width 同步派生（防历史「改了边距忘版心」）；
    6. 三范式均可装配且 validate_spec 零 ERROR；
    7. `gen.py build` 端到端：内容层诊断 → 设计 → auto-fit → QA → 退出码语义。

所有人物 / 学校 / 公司 / 号码均为**虚构夹具**，不含任何真实个人数据。
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from resume_generator.design import (  # noqa: E402
    DESIGN_TEMPLATE,
    JobSpecError,
    design_to_spec,
    load_design,
    load_job_spec,
    validate_spec,
)
from resume_generator.design.spec import PARADIGM_P1, PARADIGM_P2  # noqa: E402

CANONICAL_MD = """# 简历内容：李雷 → 演示科技 - 示例岗位

> 生成日期：2026-01-01

## 个人信息

| 项 | 值 |
|---|---|
| 姓名 | 李雷 |
| 意向 | 示例岗位 |
| 电话 | 13800000000 |
| 邮箱 | lilei@example.com |
| 城市 | 示例市 |

## 个人优势

示例优势第一句。

## 教育经历

示例大学｜示例专业（本科）｜2021.09-2025.06

## 实习经历

### 虚构科技有限公司 - 示例实习生（2024.01-2024.06）
- 完成示例任务甲

## 项目经历

### 示例项目 - 负责人（2023.01-2023.12）
- 主导示例项目从 0 到 1

## 专业技能

- 掌握示例技能甲

## 证书奖项

示例证书甲
"""


def minimal_design(**over) -> dict:
    d = {"paradigm": "p3", "design_intent": "虚构测试用的本份设计意图"}
    d.update(over)
    return d


class _Tmp(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory(prefix="jobspec_test_")
        self.tmp = Path(self._dir.name)

    def tearDown(self):
        self._dir.cleanup()

    def write_design(self, data: dict, name: str = "design.json") -> Path:
        p = self.tmp / name
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                     encoding="utf-8")
        return p


class TestDesignFile(_Tmp):
    def test_01_missing_file_is_refused(self):
        with self.assertRaises(JobSpecError) as ctx:
            load_design(self.tmp / "不存在.json")
        self.assertIn("找不到本份设计决策文件", str(ctx.exception))

    def test_02_required_keys(self):
        for key in ("paradigm", "design_intent"):
            d = minimal_design()
            d.pop(key)
            with self.assertRaises(JobSpecError) as ctx:
                load_design(self.write_design(d, f"{key}.json"))
            self.assertIn("缺必填项", str(ctx.exception))

    def test_03_placeholder_intent_is_refused(self):
        d = minimal_design(design_intent=DESIGN_TEMPLATE["design_intent"])
        with self.assertRaises(JobSpecError) as ctx:
            load_design(self.write_design(d))
        self.assertIn("占位符", str(ctx.exception))

    def test_04_comment_keys_are_ignored(self):
        """`_` 开头视为注释（JSON 无注释语法）；模板本身必须可用。"""
        d = dict(DESIGN_TEMPLATE)
        d["design_intent"] = "虚构：填写真实意图后模板即可直接使用"
        raw = load_design(self.write_design(d))       # 带 _说明 也须能读
        self.assertIn("_说明", raw)
        design_to_spec(raw)                            # 且能装配

    def test_05_unknown_top_level_key_is_refused(self):
        with self.assertRaises(JobSpecError) as ctx:
            load_design(self.write_design(minimal_design(paradigmx="p3")))
        self.assertIn("未定义的键", str(ctx.exception))

    def test_06_unknown_nested_key_is_refused(self):
        d = minimal_design(colors={"accentt": "#000000"})
        with self.assertRaises(JobSpecError) as ctx:
            load_design(self.write_design(d))
        self.assertIn("colors", str(ctx.exception))

    def test_07_unknown_divider_key_is_refused(self):
        d = minimal_design(section={"divider": {"lineheight": 2}})
        with self.assertRaises(JobSpecError):
            load_design(self.write_design(d))

    def test_08_bad_paradigm_is_refused(self):
        with self.assertRaises(JobSpecError) as ctx:
            load_design(self.write_design(minimal_design(paradigm="p9")))
        self.assertIn("paradigm", str(ctx.exception))

    def test_09_non_json_is_refused(self):
        p = self.tmp / "design.json"
        p.write_text("{ 不是 json", encoding="utf-8")
        with self.assertRaises(JobSpecError):
            load_design(p)


class TestDesignToSpec(_Tmp):
    def test_20_all_paradigms_assemble_without_errors(self):
        for paradigm, expected in (("p1", PARADIGM_P1),
                                   ("p2", PARADIGM_P2),
                                   ("p3", "p3_minimal_editorial")):
            spec, _ = load_job_spec(
                self.write_design(minimal_design(paradigm=paradigm),
                                  f"{paradigm}.json"))
            self.assertEqual(spec.metadata.paradigm, expected)
            self.assertFalse(validate_spec(spec).errors, paradigm)

    def test_21_margins_sync_safe_area_and_content_width(self):
        spec, _ = load_job_spec(self.write_design(
            minimal_design(margins_cm=[0.5, 0.5, 1.0, 1.0])))
        self.assertAlmostEqual(float(spec.page.margins.top.value), 0.5)
        self.assertAlmostEqual(float(spec.page.safe_area.top.value), 0.5)
        self.assertAlmostEqual(float(spec.page.safe_area.left.value), 1.0)
        self.assertAlmostEqual(float(spec.page.safe_area.content_width.value),
                               19.0, places=4)

    def test_22_negative_margin_is_refused(self):
        with self.assertRaises(JobSpecError):
            design_to_spec(minimal_design(margins_cm=[-1, 0.5, 0.5, 0.5]))

    def test_23_body_size_floor_is_enforced(self):
        with self.assertRaises(JobSpecError) as ctx:
            design_to_spec(minimal_design(typography={"body_size": 8.5}))
        self.assertIn("小于下限", str(ctx.exception))

    def test_24_colors_apply_by_role(self):
        spec, _ = load_job_spec(self.write_design(minimal_design(
            colors={"accent": "#DD001B", "page_background": "#F9F6F2"})))
        self.assertEqual(spec.colors.accent.value, "#DD001B")
        self.assertEqual(spec.colors.page_background.value, "#F9F6F2")
        # 未点名的角色保持基线
        self.assertEqual(spec.colors.ink.value,
                         design_to_spec(minimal_design()).colors.ink.value)

    def test_25_bad_hex_is_refused(self):
        with self.assertRaises(JobSpecError):
            design_to_spec(minimal_design(colors={"accent": "red"}))

    def test_26_divider_geometry_reaches_spec(self):
        spec, _ = load_job_spec(self.write_design(minimal_design(
            section={"divider": {"line_height": 2, "border_space": 0}})))
        self.assertAlmostEqual(float(spec.section.divider.line_height.value), 2.0)
        self.assertAlmostEqual(float(spec.section.divider.border_space.value), 0.0)

    def test_27_section_spacing_fields_reach_spec(self):
        spec, _ = load_job_spec(self.write_design(minimal_design(
            section={"spacing_before": 4, "summary_spacing_after": 2,
                     "education_spacing_after": 3})))
        self.assertAlmostEqual(float(spec.section.spacing_before.value), 4.0)
        self.assertAlmostEqual(float(spec.section.summary_spacing_after.value), 2.0)
        self.assertAlmostEqual(float(spec.section.education_spacing_after.value), 3.0)

    def test_28_photo_requires_explicit_dimensions(self):
        with self.assertRaises(JobSpecError) as ctx:
            design_to_spec(minimal_design(photo={"enabled": True}))
        self.assertIn("width_cm", str(ctx.exception))

    def test_29_photo_derives_aspect_ratio(self):
        spec, _ = load_job_spec(self.write_design(minimal_design(photo={
            "enabled": True, "width_cm": 2.2, "height_cm": 3.139,
            "offset_x_cm": 17.066, "offset_y_cm": 0.45,
            "border_color": "#BFBFBF", "border_width_pt": 2.25})))
        self.assertTrue(spec.photo.enabled)
        self.assertTrue(spec.photo.floating.enabled)
        self.assertAlmostEqual(float(spec.photo.aspect_ratio.value),
                               round(2.2 / 3.139, 4), places=6)
        self.assertEqual(spec.photo.border.color.value, "#BFBFBF")
        self.assertFalse(validate_spec(spec).errors)

    def test_30_photo_border_needs_both_fields(self):
        with self.assertRaises(JobSpecError):
            design_to_spec(minimal_design(photo={
                "enabled": True, "width_cm": 2.2, "height_cm": 3.1,
                "border_color": "#BFBFBF"}))

    def test_31_photo_disabled_is_the_default(self):
        spec = design_to_spec(minimal_design())
        self.assertFalse(spec.photo.enabled)

    def test_32_identity_band_ratio_is_normalized(self):
        spec, _ = load_job_spec(self.write_design(minimal_design(
            grid={"identity_band_ratio": [84, 104]})))
        ratio = spec.grid.identity_band_ratio
        self.assertAlmostEqual(sum(ratio), 1.0, places=6)
        self.assertAlmostEqual(ratio[0] / ratio[1], 84 / 104, places=6)

    def test_33_bad_density_level_is_refused(self):
        with self.assertRaises(JobSpecError):
            design_to_spec(minimal_design(density={"level": "超紧"}))

    def test_34_design_intent_is_recorded_in_spec(self):
        spec = design_to_spec(minimal_design(design_intent="本份：红主题 + 浮动照片"))
        self.assertEqual(spec.design_intent, "本份：红主题 + 浮动照片")

    def test_35_base_preset_is_not_mutated(self):
        from resume_generator.design.presets import build_p3_spec

        before = float(build_p3_spec().page.margins.top.value)
        design_to_spec(minimal_design(margins_cm=[0.5, 0.5, 0.5, 0.5]))
        self.assertAlmostEqual(
            float(build_p3_spec().page.margins.top.value), before)


class TestBuildCli(_Tmp):
    """`python gen.py build` 端到端（含退出码语义）。"""

    @classmethod
    def setUpClass(cls):
        import importlib.util

        spec = importlib.util.spec_from_file_location("gen_cli", ROOT / "gen.py")
        cls.gen = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.gen)

    def _run(self, argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            code = self.gen.main(argv)
        return code, buf.getvalue()

    def _prepare(self, design: dict | None) -> Path:
        md = self.tmp / "resume.md"
        md.write_text(CANONICAL_MD, encoding="utf-8")
        if design is not None:
            (self.tmp / "design.json").write_text(
                json.dumps(design, ensure_ascii=False, indent=2), encoding="utf-8")
        return md

    def test_50_missing_design_refuses_with_template(self):
        md = self._prepare(None)
        code, out = self._run(["build", str(md)])
        self.assertEqual(code, 2)
        self.assertIn("缺少本份设计决策文件", out)
        self.assertIn("design_intent", out)

    def test_51_write_template(self):
        md = self._prepare(None)
        code, out = self._run(["build", str(md), "--write-design-template"])
        self.assertEqual(code, 0)
        self.assertTrue((self.tmp / "design.json").is_file())

    def test_52_write_template_refuses_overwrite_without_force(self):
        md = self._prepare(minimal_design())
        code, out = self._run(["build", str(md), "--write-design-template"])
        self.assertEqual(code, 1)
        self.assertIn("--force", out)

    def test_53_build_produces_docx_and_qa(self):
        md = self._prepare(minimal_design())
        out_docx = self.tmp / "out.docx"
        code, out = self._run(["build", str(md), "--out", str(out_docx)])
        self.assertEqual(code, 0, out)
        self.assertTrue(out_docx.is_file())
        self.assertIn("排版 QA 报告", out)
        self.assertIn("达标", out)
        self.assertIn("李雷", out)      # 内容层解析摘要

    def test_54_bad_design_gives_exit_2(self):
        md = self._prepare(minimal_design(colors={"accentt": "#000000"}))
        code, out = self._run(["build", str(md)])
        self.assertEqual(code, 2)
        self.assertIn("未定义的键", out)

    def test_55_fatal_content_gives_exit_2(self):
        md = self.tmp / "resume.md"
        md.write_text("# 个人简历\n\n## 个人信息\n\n| 项 | 值 |\n|---|---|\n"
                      "| 电话 | 13800000000 |\n", encoding="utf-8")
        (self.tmp / "design.json").write_text(
            json.dumps(minimal_design(), ensure_ascii=False), encoding="utf-8")
        code, out = self._run(["build", str(md)])
        self.assertEqual(code, 2)
        self.assertIn("缺姓名" if "缺姓名" in out else "missing_name", out)

    def test_56_missing_resume_md_gives_exit_2(self):
        code, out = self._run(["build", str(self.tmp / "nope.md")])
        self.assertEqual(code, 2)
        self.assertIn("找不到内容层", out)


if __name__ == "__main__":
    unittest.main()
