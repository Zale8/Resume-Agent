# -*- coding: utf-8 -*-
"""test_design_spec.py — DesignSpec 数据结构与 Validator 的最小测试集（Phase 2B）。

覆盖需求中的 8 个用例：
    1. 合法 P1                → PASS
    2. 合法 P2 fallback       → PASS + WARN
    3. 正文 8pt               → FAIL
    4. 两个 accent color      → FAIL
    5. 日期使用 spaces        → FAIL
    6. 图片允许 distortion    → FAIL
    7. P2 bleed 未确定        → PASS + WARNING
    8. P2 icon 使用 fallback  → PASS + WARNING

用法：python -m pytest tests/test_design_spec.py -v
      或：python tests/test_design_spec.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

# 让 import 能找到 src/
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from resume_generator.design import (  # noqa: E402
    build_p1_spec,
    build_p2_spec,
    build_p3_spec,
    validate_spec,
    Sourced,
    RULE_BODY_FONT_SIZE,
    RULE_SINGLE_ACCENT,
    RULE_DATE_ALIGNMENT,
    RULE_PHOTO_DISTORTION,
    RULE_PHOTO_FLOATING,
    RULE_PHOTO_BORDER,
    RULE_BLEED_UNDETERMINED,
    RULE_ICON_FALLBACK,
    PhotoFloating,
    PhotoBorder,
    get_consumption,
    evaluate_unconsumed,
    STATUS_CONSUMED,
)
from resume_generator.design.spec import DATE_SPACES  # noqa: E402


def _error_rule_ids(result):
    return {e.rule_id for e in result.errors}


class TestDesignSpec(unittest.TestCase):

    def test_01_valid_p1_passes(self):
        """合法 P1（Renderer-ready）应通过校验。"""
        result = validate_spec(build_p1_spec())
        self.assertTrue(
            result.valid,
            msg="P1 不应有 ERROR:\n" + "\n".join(e.render() for e in result.errors))

    def test_02_valid_p2_fallback_passes_with_warnings(self):
        """合法 P2（含 fallback）应 PASS，但必须带 WARNING。"""
        result = validate_spec(build_p2_spec())
        self.assertTrue(
            result.valid,
            msg="P2 不应有 ERROR:\n" + "\n".join(e.render() for e in result.errors))
        self.assertGreater(len(result.warnings), 0,
                           "P2 含 undetermined 缺口与 fallback，必须产生 WARNING")

    def test_03_body_8pt_fails(self):
        """正文低于 9pt 必须 FAIL。"""
        spec = build_p1_spec()
        spec.typography.body_size = Sourced.kv1(8.0, "pt")
        result = validate_spec(spec)
        self.assertFalse(result.valid)
        self.assertIn(RULE_BODY_FONT_SIZE, _error_rule_ids(result))

    def test_04_two_accents_fails(self):
        """出现第二个强调色必须 FAIL。"""
        spec = build_p1_spec()
        spec.colors.additional_accents = [
            Sourced.kv1("#0000FF", "hex", notes="测试注入的第二个 accent")]
        result = validate_spec(spec)
        self.assertFalse(result.valid)
        self.assertIn(RULE_SINGLE_ACCENT, _error_rule_ids(result))

    def test_05_space_based_date_fails(self):
        """日期用空格定位必须 FAIL。"""
        spec = build_p1_spec()
        spec.experience.date_alignment = DATE_SPACES
        result = validate_spec(spec)
        self.assertFalse(result.valid)
        self.assertIn(RULE_DATE_ALIGNMENT, _error_rule_ids(result))

    def test_06_photo_distortion_allowed_fails(self):
        """照片允许非等比变形必须 FAIL。"""
        spec = build_p1_spec()
        spec.photo.distortion_allowed = True
        result = validate_spec(spec)
        self.assertFalse(result.valid)
        self.assertIn(RULE_PHOTO_DISTORTION, _error_rule_ids(result))

    def test_07_p2_bleed_undetermined_warns_but_passes(self):
        """P2 bleed 未确定：PASS + 专项 WARNING（path=page.bleed）。"""
        result = validate_spec(build_p2_spec())
        self.assertTrue(result.valid)
        bleed_paths = result.warning_paths(RULE_BLEED_UNDETERMINED)
        self.assertIn("page.bleed", bleed_paths)

    def test_08_p2_icon_fallback_warns_but_passes(self):
        """P2 图标资源未确定走 fallback：PASS + 专项 WARNING。"""
        result = validate_spec(build_p2_spec())
        self.assertTrue(result.valid)
        icon_paths = result.warning_paths(RULE_ICON_FALLBACK)
        self.assertTrue(any("section.icon" in p for p in icon_paths),
                        msg=f"未找到图标 fallback 警告：{icon_paths}")


class TestP3MinimalEditorial(unittest.TestCase):
    """P3 minimal editorial（Phase 2B-1 Step 2 新增）。"""

    def test_p3_spec_builds_successfully(self):
        """build_p3_spec() 不抛异常，返回 DesignSpec 实例。"""
        spec = build_p3_spec()
        self.assertIsNotNone(spec)

    def test_p3_metadata_correct(self):
        """P3 metadata 字段断言。"""
        spec = build_p3_spec()
        self.assertEqual(spec.metadata.spec_id,
                         "designspec_p3_minimal_editorial")
        self.assertEqual(spec.metadata.paradigm, "p3_minimal_editorial")

    def test_p3_typography_values(self):
        """P3 排版核心字段断言。"""
        spec = build_p3_spec()
        ty = spec.typography
        self.assertEqual(ty.body_size.value, 9.0)
        self.assertEqual(ty.title_size.value, 10.56)
        self.assertEqual(ty.name_size.value, 17.04)
        self.assertEqual(ty.font_family.value, "Microsoft YaHei")
        self.assertEqual(ty.latin_font.value, "ArialMT")

    def test_p3_colors_values(self):
        """P3 颜色字段断言。"""
        spec = build_p3_spec()
        c = spec.colors
        self.assertEqual(c.accent.value, "#0A6B3C")
        self.assertEqual(c.ink.value, "#000000")
        self.assertIsNone(c.page_background)
        self.assertIsNone(c.light_sidebar_secondary)

    def test_p3_section_prefix(self):
        """P3 板块标题前缀为 ▌（区别于 P1 的 ▍）。"""
        spec = build_p3_spec()
        self.assertEqual(spec.section.prefix.value, "▌")

    def test_p3_bullet_symbol_color_role_is_ink(self):
        """P3 bullet 符号颜色角色为 ink。"""
        spec = build_p3_spec()
        self.assertEqual(spec.experience.bullet.symbol_color_role, "ink")

    def test_p3_divider_golden_aligned(self):
        """P3 板块 divider 对齐 Golden Sample CL-02：weight=2.25pt、绿 #007A37。"""
        spec = build_p3_spec()
        self.assertEqual(spec.section.divider.weight.value, 2.25)
        self.assertEqual(spec.colors.hairline.value, "#007A37")

    def test_p3_passes_validation(self):
        """P3 Spec 通过 Validator（无 ERROR；含 derived WARNING 属预期）。"""
        result = validate_spec(build_p3_spec())
        self.assertTrue(
            result.valid,
            msg="P3 不应有 ERROR:\n" + "\n".join(e.render() for e in result.errors))


class TestP1Phase2BCorrections(unittest.TestCase):
    """P1 Phase 2B-1 修正回归：bullet 颜色 + divider weight。"""

    def test_p1_bullet_symbol_color_role_is_ink(self):
        """P1 bullet.symbol_color_role 修正为 ink（旧值 accent）。"""
        spec = build_p1_spec()
        self.assertEqual(spec.experience.bullet.symbol_color_role, "ink")

    def test_p1_divider_weight_zero(self):
        """P1 section.divider.weight 修正为 0.0pt（旧值 0.5pt）。"""
        spec = build_p1_spec()
        self.assertEqual(spec.section.divider.weight.value, 0.0)


class TestPhotoFloatingBorder(unittest.TestCase):
    """Photo floating / border Schema + Validator（Phase 2B-4 Step 4 / CL-01）。

    全部基于 P3 spec 的内存副本（dataclasses.replace），不修改任何 preset
    默认值；数值取自 Golden Sample 视觉规则，夹具人物仍为虚构。
    """

    def _p3_with_photo(self, *, floating=True, border=True,
                       photo_enabled=True, **float_kw):
        from dataclasses import replace
        spec = build_p3_spec()
        pf = PhotoFloating(enabled=floating, **float_kw) if floating else None
        pb = None
        if border is True:
            pb = PhotoBorder(Sourced.kv1("#BFBFBF"),
                             Sourced.kv1(2.25, "pt"))
        elif border is not None and border is not False:
            pb = border
        photo = replace(
            spec.photo,
            enabled=photo_enabled,
            position="header_top_right_floating",
            width=Sourced.kv1(2.212, "cm"),
            height=Sourced.kv1(3.156, "cm"),
            aspect_ratio=Sourced.kv1(0.70, "ratio"),
            container="floating_anchored_no_fill",
            floating=pf, border=pb)
        return replace(spec, photo=photo)

    # -- 合法值 -----------------------------------------------------------
    def test_golden_photo_shape_passes(self):
        result = validate_spec(self._p3_with_photo())
        self.assertTrue(
            result.valid,
            msg="Golden 照片形态不应有 ERROR:\n"
                + "\n".join(e.render() for e in result.errors))

    def test_offset_none_and_zero_valid(self):
        s1 = self._p3_with_photo(offset_x_cm=None, offset_y_cm=None)
        self.assertTrue(validate_spec(s1).valid)
        s2 = self._p3_with_photo(
            offset_x_cm=Sourced.kv1(0.0, "cm"),
            offset_y_cm=Sourced.kv1(0.09, "cm"))
        self.assertTrue(validate_spec(s2).valid)

    def test_zero_border_width_valid(self):
        pb = PhotoBorder(Sourced.kv1("#BFBFBF"), Sourced.kv1(0.0, "pt"))
        result = validate_spec(self._p3_with_photo(border=pb))
        self.assertTrue(result.valid)

    # -- 非法值必须识别 ---------------------------------------------------
    def test_bad_position_h_fails(self):
        result = validate_spec(self._p3_with_photo(position_h="table"))
        self.assertFalse(result.valid)
        self.assertIn(RULE_PHOTO_FLOATING, _error_rule_ids(result))

    def test_bad_position_v_fails(self):
        result = validate_spec(self._p3_with_photo(position_v="character"))
        self.assertFalse(result.valid)
        self.assertIn(RULE_PHOTO_FLOATING, _error_rule_ids(result))

    def test_negative_offset_fails(self):
        result = validate_spec(
            self._p3_with_photo(offset_x_cm=Sourced.kv1(-0.01, "cm")))
        self.assertFalse(result.valid)
        self.assertIn(RULE_PHOTO_FLOATING, _error_rule_ids(result))

    def test_bad_border_color_fails(self):
        pb = PhotoBorder(Sourced.kv1("BFBFBF"), Sourced.kv1(2.25, "pt"))
        result = validate_spec(self._p3_with_photo(border=pb))
        self.assertFalse(result.valid)
        self.assertIn(RULE_PHOTO_BORDER, _error_rule_ids(result))

    def test_negative_border_width_fails(self):
        pb = PhotoBorder(Sourced.kv1("#BFBFBF"), Sourced.kv1(-0.5, "pt"))
        result = validate_spec(self._p3_with_photo(border=pb))
        self.assertFalse(result.valid)
        self.assertIn(RULE_PHOTO_BORDER, _error_rule_ids(result))

    def test_floating_enabled_requires_photo_enabled(self):
        result = validate_spec(self._p3_with_photo(photo_enabled=False))
        self.assertFalse(result.valid)
        self.assertIn(RULE_PHOTO_FLOATING, _error_rule_ids(result))

    # -- 消费矩阵与默认值 -------------------------------------------------
    def test_new_fields_registered_consumed(self):
        for path in ("photo.floating.enabled", "photo.floating.position_h",
                     "photo.floating.position_v",
                     "photo.floating.offset_x_cm",
                     "photo.floating.offset_y_cm",
                     "photo.border.color", "photo.border.width_pt"):
            row = get_consumption(path)
            self.assertIsNotNone(row, msg=f"{path} 未登记消费矩阵")
            self.assertEqual(row.status, STATUS_CONSUMED, msg=path)
            self.assertTrue(row.consumed_by, msg=path)

    def test_new_fields_produce_no_unconsumed_warning(self):
        paths = {f.path for f in evaluate_unconsumed(self._p3_with_photo())}
        self.assertFalse(
            [p for p in paths if p.startswith("photo.floating")
             or p.startswith("photo.border")],
            msg=f"新字段不应产生未消费 WARNING：{paths}")

    def test_presets_default_to_no_floating_no_border(self):
        """P1/P2/P3 三个 preset 均不预置浮动/边框（旧行为字节级不变）。"""
        for builder in (build_p1_spec, build_p2_spec, build_p3_spec):
            self.assertIsNone(builder().photo.floating)
            self.assertIsNone(builder().photo.border)


if __name__ == "__main__":
    # 直接运行时先打印三份预设的校验摘要，再跑测试
    for name, builder in (("P1", build_p1_spec), ("P2", build_p2_spec),
                          ("P3", build_p3_spec)):
        print(f"\n{'=' * 70}\n# {name} DesignSpec validation summary\n{'=' * 70}")
        print(validate_spec(builder()).render_text())
    print(f"\n{'=' * 70}\n# unit tests\n{'=' * 70}")
    unittest.main(verbosity=2)
