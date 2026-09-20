# -*- coding: utf-8 -*-
"""test_schema_gap_title_entry_spacing.py — Phase 2B-5 Step 1 最小 Schema Gap 接线测试。

覆盖任务书 5 个用例：
    Test 1：默认值（SectionSpec.title_spacing_after=1pt，
            ExperienceSpec.entry_spacing_after=1pt）
    Test 2：P1/P2/P3 三个 Preset 的 title_after / entry_after 与当前 Profile 保值
    Test 3：Renderer consumption（DesignSpec → RenderStyle 传递）
    Test 4：Delta 链路（assemble_job_spec + section/experience delta 进入 Renderer）
    Test 5：默认值视觉行为保持（P1/P2/P3 旧行为不变 + Golden Sample 不动）

只触及 spec.py / presets.py / render_style.py / consumption.py / validator.py 的
公开 API；不修改 assembly / skeletons / layout_kit / Renderer 实现。
"""
from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from resume_generator.design import (  # noqa: E402
    build_p1_spec,
    build_p2_spec,
    build_p3_spec,
    validate_spec,
    assemble_job_spec,
    Sourced,
    SectionSpec,
    ExperienceSpec,
    get_consumption,
    evaluate_unconsumed,
    STATUS_CONSUMED,
    RULE_UNCONSUMED_SPEC_FIELD,
)
from resume_generator.render_style import (  # noqa: E402
    SKELETON_DEFAULT_STYLE,
    resolve_style_for_spec,
)
from resume_generator.skeletons import (  # noqa: E402
    SKELETON_BANNER,
    SKELETON_MINIMAL,
    SKELETON_SIDEBAR,
    resolve_palette,
)


def _resolve(spec, sk):
    """与 _build_from_spec 同口径解析 RenderStyle（含 spacing/palette/components）。"""
    return resolve_style_for_spec(
        spec, SKELETON_DEFAULT_STYLE[sk], sk, resolve_palette(None, sk))


# ===========================================================================
# Test 1：Schema 默认值
# ===========================================================================

class TestSchemaDefaults(unittest.TestCase):
    """SectionSpec / ExperienceSpec 新增字段不带值时的默认值 = 1pt。"""

    def test_01_section_default_title_spacing_after_1pt(self):
        """SectionSpec 不显式传 title_spacing_after 时默认 1pt。"""
        # 用最小必填字段构造一个 SectionSpec（其余字段用 preset P1 的值，
        # 但 title_spacing_after 不显式传入 → 走 dataclass field default）
        p1 = build_p1_spec()
        default_section = SectionSpec(
            title_style=p1.section.title_style,
            prefix=p1.section.prefix,
            icon=p1.section.icon,
            divider=p1.section.divider,
        )
        self.assertEqual(default_section.title_spacing_after.value, 1)
        self.assertEqual(default_section.title_spacing_after.unit, "pt")

    def test_02_experience_default_entry_spacing_after_1pt(self):
        """ExperienceSpec 不显式传 entry_spacing_after 时默认 1pt。"""
        p1 = build_p1_spec()
        # ExperienceSpec 必填字段较多，用 replace 抹掉 entry_spacing_after
        # 再验证默认：通过 replace(None) 等价手法不可行（frozen=False 但字段无默认），
        # 改为构造一个最小实例，使用 P1 各必填值
        default_exp = ExperienceSpec(
            organization=p1.experience.organization,
            role=p1.experience.role,
            date=p1.experience.date,
            date_alignment=p1.experience.date_alignment,
            tags=p1.experience.tags,
            bullet=p1.experience.bullet,
            bullet_indent=p1.experience.bullet_indent,
            bullet_spacing_after=p1.experience.bullet_spacing_after,
            entry_spacing=p1.experience.entry_spacing,
            # entry_spacing_after 不传 → 走 dataclass field default
        )
        self.assertEqual(default_exp.entry_spacing_after.value, 1)
        self.assertEqual(default_exp.entry_spacing_after.unit, "pt")


# ===========================================================================
# Test 2：P1/P2/P3 Preset 保值（与当前 Profile 实际值一致）
# ===========================================================================

class TestPresetParity(unittest.TestCase):
    """三 Preset 的新增字段值必须与改造前 Profile fallback 数值一致。

    Profile（_DEFAULT_SPACING）原值：
        banner    title_after=1  entry_after=1
        minimal   title_after=1  entry_after=1
        sidebar   title_after=2  entry_after=1
    """

    def test_10_p1_title_after_1pt(self):
        self.assertEqual(build_p1_spec().section.title_spacing_after.value, 1)

    def test_11_p1_entry_after_1pt(self):
        self.assertEqual(
            build_p1_spec().experience.entry_spacing_after.value, 1)

    def test_12_p2_title_after_2pt(self):
        """P2 sidebar Profile 原 title_after=2，Preset 必须显式 2pt 保持视觉。"""
        self.assertEqual(build_p2_spec().section.title_spacing_after.value, 2)

    def test_13_p2_entry_after_1pt(self):
        self.assertEqual(
            build_p2_spec().experience.entry_spacing_after.value, 1)

    def test_14_p3_title_after_1pt(self):
        self.assertEqual(build_p3_spec().section.title_spacing_after.value, 1)

    def test_15_p3_entry_after_1pt(self):
        self.assertEqual(
            build_p3_spec().experience.entry_spacing_after.value, 1)

    def test_16_all_presets_pass_validator(self):
        """三 Preset 仍通过 Validator（无 ERROR；新字段不引入 unconsumed WARNING）。"""
        for builder in (build_p1_spec, build_p2_spec, build_p3_spec):
            result = validate_spec(builder())
            self.assertTrue(
                result.valid,
                msg=f"{builder.__name__} 不应有 ERROR:\n"
                    + "\n".join(e.render() for e in result.errors))
            # 新字段不在 evaluate_unconsumed 硬编码列表中，且已被 Renderer 消费
            unconsumed = {f.path for f in evaluate_unconsumed(builder())}
            self.assertNotIn("section.title_spacing_after", unconsumed)
            self.assertNotIn("experience.entry_spacing_after", unconsumed)


# ===========================================================================
# Test 3：Renderer consumption（DesignSpec → RenderStyle 传递）
# ===========================================================================

class TestRendererConsumption(unittest.TestCase):

    def test_20_p1_title_after_resolves_to_renderstyle(self):
        """P1 title_spacing_after (1pt) → RenderSpacing.title_after = 1.0。"""
        sp = _resolve(build_p1_spec(), SKELETON_BANNER).spacing
        self.assertEqual(sp.title_after, 1.0)
        # 不再登记为 schema_gap（Resolver 不应产出 spacing.title_after<schema_gap>）
        st = _resolve(build_p1_spec(), SKELETON_BANNER)
        self.assertNotIn("spacing.title_after<schema_gap>", st.spec_fallbacks)
        self.assertNotIn("spacing.title_after<not_defined>", st.spec_fallbacks)

    def test_21_p1_entry_after_resolves_to_renderstyle(self):
        """P1 entry_spacing_after (1pt) → RenderSpacing.entry_after = 1.0。"""
        sp = _resolve(build_p1_spec(), SKELETON_BANNER).spacing
        self.assertEqual(sp.entry_after, 1.0)
        st = _resolve(build_p1_spec(), SKELETON_BANNER)
        self.assertNotIn("spacing.entry_after<schema_gap>", st.spec_fallbacks)
        self.assertNotIn("spacing.entry_after<not_defined>", st.spec_fallbacks)

    def test_22_p3_title_after_resolves_to_renderstyle(self):
        sp = _resolve(build_p3_spec(), SKELETON_MINIMAL).spacing
        self.assertEqual(sp.title_after, 1.0)

    def test_23_p3_entry_after_resolves_to_renderstyle(self):
        sp = _resolve(build_p3_spec(), SKELETON_MINIMAL).spacing
        self.assertEqual(sp.entry_after, 1.0)

    def test_24_p2_entry_after_resolves(self):
        """P2 sidebar 三槽位均消费 entry_after。"""
        sp = _resolve(build_p2_spec(), SKELETON_SIDEBAR).spacing
        self.assertEqual(sp.entry_after, 1.0)

    def test_25_p2_title_after_profile_only(self):
        """P2 sidebar 不在 _SPACING_ROLES_BY_SKELETON 中（标题边框附在标题段），
        Spec.title_spacing_after=2pt 在 sidebar 不生效，title_after 保持
        Profile=2 → 与改造前行为一致（旧行为也是 Profile=2，无视觉漂移）。
        不再走 schema_gap 分支，但 role 不在消费列表 → 不进入 resolved；行为等价。
        """
        sp = _resolve(build_p2_spec(), SKELETON_SIDEBAR).spacing
        # sidebar Profile title_after=2，与 P2 Spec title_spacing_after=2pt 数值相同
        self.assertEqual(sp.title_after, 2)

    def test_26_override_propagates_to_renderstyle(self):
        """显式覆盖 Spec 字段值 → RenderSpacing 跟随变化。"""
        base = build_p1_spec()
        # title_after 4pt
        s4 = replace(base,
                     section=replace(base.section,
                                     title_spacing_after=Sourced.kv1(4, "pt")))
        self.assertEqual(_resolve(s4, SKELETON_BANNER).spacing.title_after, 4.0)
        # entry_after 7pt
        e7 = replace(base,
                     experience=replace(
                         base.experience,
                         entry_spacing_after=Sourced.kv1(7, "pt")))
        self.assertEqual(_resolve(e7, SKELETON_BANNER).spacing.entry_after, 7.0)

    def test_27_undetermined_falls_back_with_log(self):
        """新字段设为 undetermined → 回退 Profile + 裸键登记（与既有 spacing 口径一致）。"""
        base = build_p1_spec()
        spec = replace(
            base,
            section=replace(
                base.section,
                title_spacing_after=Sourced.undetermined("测试：title 缺口")))
        st = _resolve(spec, SKELETON_BANNER)
        self.assertEqual(st.spacing.title_after, 1)  # banner Profile=1
        self.assertIn("spacing.title_after", st.spec_fallbacks)
        self.assertNotIn("spacing.title_after<not_defined>", st.spec_fallbacks)

    def test_28_none_falls_back_with_not_defined(self):
        """新字段设为 None → 回退 Profile + <not_defined> 登记。"""
        base = build_p1_spec()
        spec = replace(
            base,
            experience=replace(base.experience, entry_spacing_after=None))
        st = _resolve(spec, SKELETON_BANNER)
        self.assertEqual(st.spacing.entry_after, 1)  # banner Profile=1
        self.assertIn("spacing.entry_after<not_defined>", st.spec_fallbacks)


# ===========================================================================
# Test 4：Delta 链路（assemble_job_spec + section/experience delta）
# ===========================================================================

class TestDeltaChain(unittest.TestCase):
    """不修改 Assembly，只验证 section_delta / experience_delta 携带新字段
    通过 assemble_job_spec 进入 Renderer。"""

    def test_30_section_delta_carries_title_spacing_after(self):
        base = build_p1_spec()
        delta = replace(base.section,
                        title_spacing_after=Sourced.kv1(3, "pt"))
        assembled = assemble_job_spec(base, section_delta=delta)
        self.assertEqual(assembled.section.title_spacing_after.value, 3)
        # 基线不被 mutation
        self.assertEqual(base.section.title_spacing_after.value, 1)
        # 进入 RenderStyle
        self.assertEqual(
            _resolve(assembled, SKELETON_BANNER).spacing.title_after, 3.0)

    def test_31_experience_delta_carries_entry_spacing_after(self):
        base = build_p3_spec()
        delta = replace(base.experience,
                        entry_spacing_after=Sourced.kv1(5, "pt"))
        assembled = assemble_job_spec(base, experience_delta=delta)
        self.assertEqual(assembled.experience.entry_spacing_after.value, 5)
        self.assertEqual(base.experience.entry_spacing_after.value, 1)
        self.assertEqual(
            _resolve(assembled, SKELETON_MINIMAL).spacing.entry_after, 5.0)

    def test_32_combined_section_and_experience_delta(self):
        base = build_p3_spec()
        assembled = assemble_job_spec(
            base,
            section_delta=replace(base.section,
                                  title_spacing_after=Sourced.kv1(2, "pt")),
            experience_delta=replace(base.experience,
                                     entry_spacing_after=Sourced.kv1(4, "pt")),
        )
        sp = _resolve(assembled, SKELETON_MINIMAL).spacing
        self.assertEqual(sp.title_after, 2.0)
        self.assertEqual(sp.entry_after, 4.0)

    def test_33_delta_assembled_spec_passes_validator(self):
        base = build_p3_spec()
        assembled = assemble_job_spec(
            base,
            section_delta=replace(base.section,
                                  title_spacing_after=Sourced.kv1(2, "pt")),
            experience_delta=replace(base.experience,
                                     entry_spacing_after=Sourced.kv1(3, "pt")),
        )
        result = validate_spec(assembled)
        self.assertTrue(
            result.valid,
            msg="合法 delta 装配产物不应产生 ERROR:\n"
                + "\n".join(e.render() for e in result.errors))
        # 新字段不应触发 unconsumed WARNING
        unconsumed = {f.path for f in evaluate_unconsumed(assembled)}
        self.assertNotIn("section.title_spacing_after", unconsumed)
        self.assertNotIn("experience.entry_spacing_after", unconsumed)


# ===========================================================================
# Test 5：默认值视觉行为保持（P1/P2/P3 旧行为不变）
# ===========================================================================

class TestDefaultVisualBehaviorUnchanged(unittest.TestCase):

    def test_40_p1_default_spacing_matches_profile(self):
        """P1 默认 Spec 的 title_after / entry_after 与改造前 Profile 数值一致。

        仅校验本次 Schema Gap 接线的两个字段；section_before / bullet_after 等
        早已在 Phase 3B-3 接线，Spec 自带 22pt / 6pt 取值（不与 Profile 相等，
        也与本任务无关）。
        """
        sp = _resolve(build_p1_spec(), SKELETON_BANNER).spacing
        profile = SKELETON_DEFAULT_STYLE[SKELETON_BANNER].spacing
        self.assertEqual(sp.title_after, profile.title_after)
        self.assertEqual(sp.entry_after, profile.entry_after)

    def test_41_p2_default_spacing_matches_profile(self):
        sp = _resolve(build_p2_spec(), SKELETON_SIDEBAR).spacing
        profile = SKELETON_DEFAULT_STYLE[SKELETON_SIDEBAR].spacing
        self.assertEqual(sp.entry_after, profile.entry_after)
        # sidebar title_after 不在 _SPACING_ROLES（旧行为也是 Profile=2）
        self.assertEqual(sp.title_after, profile.title_after)

    def test_42_p3_default_spacing_matches_profile(self):
        sp = _resolve(build_p3_spec(), SKELETON_MINIMAL).spacing
        profile = SKELETON_DEFAULT_STYLE[SKELETON_MINIMAL].spacing
        self.assertEqual(sp.title_after, profile.title_after)
        self.assertEqual(sp.entry_after, profile.entry_after)

    def test_43_no_unconsumed_warning_for_new_fields(self):
        """三 Preset 默认 Spec 经 Validator 不应给新字段产出 unconsumed WARNING。"""
        for builder in (build_p1_spec, build_p2_spec, build_p3_spec):
            result = validate_spec(builder())
            new_field_paths = {
                p for p in result.warning_paths(RULE_UNCONSUMED_SPEC_FIELD)
                if "title_spacing_after" in p or "entry_spacing_after" in p
            }
            self.assertEqual(
                new_field_paths, set(),
                msg=f"{builder.__name__} 新字段不应触发 unconsumed WARNING："
                    f"{new_field_paths}")


# ===========================================================================
# Consumption 矩阵登记
# ===========================================================================

class TestConsumptionMatrixRegistration(unittest.TestCase):

    def test_50_new_fields_registered_consumed(self):
        for path in ("section.title_spacing_after",
                     "experience.entry_spacing_after"):
            row = get_consumption(path)
            self.assertIsNotNone(row, msg=f"{path} 未登记消费矩阵")
            self.assertEqual(row.status, STATUS_CONSUMED, msg=path)
            self.assertTrue(row.consumed_by, msg=path)

    def test_51_entry_spacing_promoted_to_consumed(self):
        """experience.entry_spacing 字段单一职责（映射 entry_before）已完成，
        entry_after 由新字段独立提供 → 状态从 partial 升级为 consumed。"""
        row = get_consumption("experience.entry_spacing")
        self.assertEqual(row.status, STATUS_CONSUMED)
        self.assertTrue(row.consumed_by)


if __name__ == "__main__":
    unittest.main(verbosity=2)
