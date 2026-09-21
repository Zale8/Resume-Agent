# -*- coding: utf-8 -*-
"""test_design_consumption.py — DesignSpec 字段消费矩阵与未消费 WARNING。

Phase 2B-2 验收：
    1. 矩阵登记完整且自洽（状态合法 / consumed_by 与状态一致）
    2. Phase 2B-2 审计首批 10 个缺口字段全部在矩阵中可查
    3. P1/P2/P3 校验产生准确的 spec_field_without_consumer WARNING
    4. 该规则永远是非阻断 WARNING（valid 不翻转、不进 errors）
    5. 负向对照：承诺撤回后 WARNING 消失
"""
from __future__ import annotations

import sys
import unittest
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
    RULE_UNCONSUMED_SPEC_FIELD,
    consumption_matrix,
    get_consumption,
    field_paths,
    evaluate_unconsumed,
    STATUS_CONSUMED,
    STATUS_PARTIALLY_CONSUMED,
    STATUS_FALLBACK,
    STATUS_UNCONSUMED,
)
from resume_generator.design.consumption import (  # noqa: E402
    P1, P2, P3, VALID_STATUSES,
)


def _unconsumed_paths(spec):
    result = validate_spec(spec)
    return set(result.warning_paths(RULE_UNCONSUMED_SPEC_FIELD)), result


# 审计首批 10 个重点核对字段（矩阵中必须可查）
FIRST_BATCH_PATHS = [
    ("grid.column_ratio", P2),
    ("photo.display_shape", P2),
    ("section.icon.resource", P2),
    ("achievement.enabled", P1),
    ("experience.tags.enabled", P3),
    ("experience.bullet_indent", P3),
    ("experience.bullet.symbol_color_role", P2),
    ("typography.intent_size", ""),
    ("colors.page_background", ""),
    ("colors.light_sidebar_secondary", ""),
]


class TestConsumptionMatrixIntegrity(unittest.TestCase):

    def test_01_all_statuses_valid(self):
        for item in consumption_matrix():
            self.assertIn(item.status, VALID_STATUSES,
                          msg=f"{item.path} 状态非法：{item.status}")

    def test_02_consumed_by_matches_status(self):
        for item in consumption_matrix():
            if item.status in (STATUS_CONSUMED, STATUS_PARTIALLY_CONSUMED):
                self.assertTrue(
                    item.consumed_by,
                    msg=f"{item.path} 标记 {item.status} 但 consumed_by 为空")
            if item.status == STATUS_UNCONSUMED:
                self.assertEqual(
                    item.consumed_by, (),
                    msg=f"{item.path} 标记 unconsumed 却登记了消费点："
                        f"{item.consumed_by}")
            if item.status == STATUS_FALLBACK:
                # fallback：允许登记 Profile 来源说明，但不允许有真实渲染函数
                self.assertTrue(item.notes,
                                msg=f"{item.path} fallback 必须有说明 notes")

    def test_03_paradigm_specific_rows_are_discoverable(self):
        # v0.9.0 变更：grid.column_ratio 在 P2 下**已被真实消费**
        # （_ratios_from_spec → _resolve_layout 切列宽）；P1/P3 仍为零读取，
        # 因为它们的正文本来就是单栏，该字段描述的是正文栅格而非身份区列比。
        row_p2 = get_consumption("grid.column_ratio", P2)
        self.assertIsNotNone(row_p2)
        self.assertEqual(row_p2.status, STATUS_CONSUMED)
        self.assertTrue(row_p2.consumed_by)
        for paradigm in (P1, P3):
            row = get_consumption("grid.column_ratio", paradigm)
            self.assertIsNotNone(row)
            self.assertEqual(row.status, STATUS_UNCONSUMED)
            self.assertEqual(row.consumed_by, ())
        # 身份区列比（v0.9.0 新增字段）三范式通用消费
        band = get_consumption("grid.identity_band_ratio")
        self.assertIsNotNone(band)
        self.assertEqual(band.status, STATUS_CONSUMED)
        # 范式专属行优先：tags.enabled P3 为 unconsumed，P1 为 consumed
        self.assertEqual(get_consumption("experience.tags.enabled", P3).status,
                         STATUS_UNCONSUMED)
        self.assertEqual(get_consumption("experience.tags.enabled", P1).status,
                         STATUS_CONSUMED)
        # 无范式入参时通用行兜底
        self.assertIsNotNone(get_consumption("colors.ink"))

    def test_04_first_batch_fields_all_registered(self):
        missing = []
        for path, paradigm in FIRST_BATCH_PATHS:
            row = get_consumption(path, paradigm)
            if row is None:
                missing.append((path, paradigm))
        self.assertEqual(missing, [], f"首批缺口字段未登记：{missing}")

    def test_05_intent_size_recorded_as_schema_gap_but_never_warned(self):
        # schema gap：矩阵可见（fallback），但 Spec 无字段 → 评估器永不产出
        row = get_consumption("typography.intent_size")
        self.assertEqual(row.status, STATUS_FALLBACK)
        for builder in (build_p1_spec, build_p2_spec, build_p3_spec):
            paths = {f.path for f in evaluate_unconsumed(builder())}
            self.assertNotIn("typography.intent_size", paths)

    def test_06_matrix_covers_all_primary_spec_subtrees(self):
        paths = field_paths()
        for prefix in ("metadata.", "page.", "architecture.", "grid.",
                       "header.", "typography.", "colors.", "photo.",
                       "section.", "experience.", "achievement.", "density.",
                       "constraints."):
            self.assertTrue(any(p.startswith(prefix) for p in paths),
                            msg=f"矩阵缺少 {prefix}* 子树登记")


class TestUnconsumedWarningPresets(unittest.TestCase):
    """三范式 preset 的 WARNING 路径快照（非阻断）。"""

    def test_10_p1_warnings(self):
        paths, result = _unconsumed_paths(build_p1_spec())
        expected = {
            "header.height",
            "header.text_inset",
            "colors.paper",
            "section.title_indent",
            "section.symbol_color_role",
            "typography.header_meta_sizes[1]",
            "experience.bullet.text_size",
            "experience.bullet_indent",
            "achievement.enabled",
        }
        self.assertEqual(paths, expected,
                         msg=f"P1 未消费 WARNING 集合漂移：{paths ^ expected}")

    def test_11_p2_warnings(self):
        paths, result = _unconsumed_paths(build_p2_spec())
        # v0.9.0：grid.column_ratio 已真实消费，从预警集合移除
        expected = {
            "grid.gutter",
            "colors.paper",
            "photo.display_shape",
            "photo.crop_allowed",
            "section.title_indent",
            "section.symbol_color_role",
            "experience.bullet.symbol_color_role",
            "experience.bullet.text_size",
            "experience.bullet_indent",
        }
        self.assertEqual(paths, expected,
                         msg=f"P2 未消费 WARNING 集合漂移：{paths ^ expected}")

    def test_12_p3_warnings(self):
        paths, result = _unconsumed_paths(build_p3_spec())
        expected = {
            "header.height",
            "colors.paper",
            "section.title_indent",
            "experience.tags.enabled",
            "experience.bullet.text_size",
            "experience.bullet_indent",
        }
        self.assertEqual(paths, expected,
                         msg=f"P3 未消费 WARNING 集合漂移：{paths ^ expected}")

    def test_13_never_blocks_validation(self):
        for builder in (build_p1_spec, build_p2_spec, build_p3_spec):
            result = validate_spec(builder())
            self.assertTrue(
                result.valid,
                msg="未消费契约只能产生 WARNING，不得翻转 valid：\n"
                    + "\n".join(e.render() for e in result.errors))
            error_ids = {e.rule_id for e in result.errors}
            self.assertNotIn(RULE_UNCONSUMED_SPEC_FIELD, error_ids)
            self.assertGreaterEqual(
                len(result.warning_paths(RULE_UNCONSUMED_SPEC_FIELD)), 1)

    def test_14_rule_registered_in_all_rules(self):
        from resume_generator.design import ALL_RULES
        self.assertIn(RULE_UNCONSUMED_SPEC_FIELD, ALL_RULES)


class TestUnconsumedWarningNegativeControls(unittest.TestCase):
    """承诺撤回 / 取值改为可实现形态后，对应 WARNING 必须消失。"""

    def test_20_achievement_disabled_clears_warning(self):
        spec = build_p1_spec()
        spec.achievement.enabled = False
        paths, result = _unconsumed_paths(spec)
        self.assertNotIn("achievement.enabled", paths)
        self.assertTrue(result.valid)

    def test_21_bullet_symbol_same_color_clears_warning(self):
        spec = build_p2_spec()
        spec.experience.bullet.symbol_color_role = "ink"
        paths, _ = _unconsumed_paths(spec)
        self.assertNotIn("experience.bullet.symbol_color_role", paths)

    def test_22_p3_tags_disabled_clears_warning(self):
        spec = build_p3_spec()
        spec.experience.tags.enabled = False
        paths, _ = _unconsumed_paths(spec)
        self.assertNotIn("experience.tags.enabled", paths)

    def test_23_zero_value_geometry_does_not_warn(self):
        # gutter/bleed=0 表示「关闭」，不应误报
        spec = build_p1_spec()
        paths, _ = _unconsumed_paths(spec)
        self.assertNotIn("grid.gutter", paths)
        self.assertNotIn("page.bleed", paths)

    def test_24_undetermined_field_does_not_double_warn(self):
        # P2 gutter 之外：header.height 为 undetermined，由既有
        # parameter_undetermined 覆盖，新规则不得重复报同一路径
        spec = build_p2_spec()
        result = validate_spec(spec)
        new_rule_paths = result.warning_paths(RULE_UNCONSUMED_SPEC_FIELD)
        self.assertNotIn("header.height", new_rule_paths)
        undetermined_paths = result.warning_paths("parameter_undetermined")
        self.assertIn("header.height", undetermined_paths)

    def test_25_circle_photo_flag_is_caught(self):
        spec = build_p2_spec()
        paths, _ = _unconsumed_paths(spec)
        self.assertIn("photo.display_shape", paths)

    def test_26_p2_column_ratio_is_no_longer_a_dead_field(self):
        """v0.9.0 回归：P2 的列比不再「声明了却零读取」。

        历史行为：Spec 声明 [0.32, 0.68]，Renderer 用骨架常量
        ≈[0.304, 0.696]，差异静默 —— 这正是审计报告里
        「改了它不生效，还不报错」的典型。本测试锁住修复后的两个事实：
        ① 评估器不再对 P2 报 grid.column_ratio 未消费；
        ② 列宽确实按 Spec 值切分（0.32 → 6.208cm@19.4 版心）。
        """
        self.assertNotIn("grid.column_ratio",
                         _unconsumed_paths(build_p2_spec())[0])
        self.assertNotIn("grid.column_ratio",
                         _unconsumed_paths(build_p1_spec())[0])
        self.assertNotIn("grid.column_ratio",
                         _unconsumed_paths(build_p3_spec())[0])

        # ② 端到端：P2 spec 的列比真的进了 tblGrid
        from docx.oxml.ns import qn

        from resume_generator.layout_kit import BulletBlock, ResumeBlocks
        from resume_generator.skeletons import build_document

        blocks = ResumeBlocks(
            name="张三", intent="测试岗位",
            contact_lines=["138-0000-0000", "zhangsan@example.com"],
            internships=[BulletBlock(title="某某有限公司", role="实习生",
                                     meta="2025.06 - 2025.09",
                                     bullets=["虚构条目。"])],
        )
        doc = build_document(blocks, design_spec=build_p2_spec())
        grid = doc.tables[0]._tbl.find(qn("w:tblGrid"))
        cols = [int(c.get(qn("w:w"))) for c in grid.findall(qn("w:gridCol"))]
        total = sum(cols)
        self.assertEqual(len(cols), 2)
        # 19.4cm 版心按 0.32/0.68 切 → 约 6.208 / 13.192 cm
        self.assertAlmostEqual(cols[0] / total, 0.32, places=3,
                               msg=f"P2 列比未按 Spec 落地：{cols}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
