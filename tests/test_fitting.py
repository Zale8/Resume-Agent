# -*- coding: utf-8 -*-
"""test_fitting.py — auto-fit 引擎（fitting.py）测试。

覆盖契约（对应审计 §R4「验证闭环几乎为零」与 §R5 的收益）：
    1. 高度估算修正版：单位换算正确、**浮动照片（wp:anchor）计入**
       （历史 check_pages.py 只认 wp:inline，对浮动照片完全失明）；
    2. 测量三态：word_com / estimate / unavailable，绝不把估算伪装成实测；
    3. audit 出齐八维（页数/溢出/末行/寡行/密度/边距/字号/照片）；
    4. 收敛梯：档位顺序确定（间距→行距→边距→[字号]）、可复现、有上限；
    5. 用尽仍不达标 → 停 + 归因（提示删内容，而非继续压字号）；
    6. 字号档默认关闭（规范：禁止靠缩字号硬塞），显式开启才走；
    7. 已到下限的档不再产生「假进展」（回归：数值不变但 Sourced 对象变新）；
    8. 字号判定容忍 OOXML 半磅量化，且以 Spec 声明值为基准。

所有人物 / 学校 / 公司 / 号码均为**虚构夹具**，不含任何真实个人数据。
"""
from __future__ import annotations

import struct
import sys
import tempfile
import unittest
import zlib
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from resume_generator.design import (  # noqa: E402
    PhotoBorder,
    PhotoFloating,
    Sourced,
    assemble_job_spec,
    build_p3_spec,
    validate_spec,
)
from resume_generator.design.presets import build_p3_spec as _p3  # noqa: E402,F401
from resume_generator.fitting import (  # noqa: E402
    FONT_QUANTIZATION_TOL_PT,
    MARGIN_FLOOR_CM,
    STAGE_FONT,
    STAGE_LINE,
    STAGE_MARGIN,
    STAGE_SPACING,
    FitError,
    audit,
    declared_min_font_pt,
    estimate_height,
    fit,
    measure_pages,
)
from resume_generator.layout_kit import BulletBlock, ResumeBlocks  # noqa: E402
from resume_generator.skeletons import build_document  # noqa: E402


# ---------------------------------------------------------------------------
# 虚构夹具
# ---------------------------------------------------------------------------

def write_png(path: Path, w: int, h: int, rgb=(90, 120, 180)) -> Path:
    """stdlib 合成纯色 PNG（无 Pillow 依赖，不使用真实证件照）。"""
    def chunk(typ: bytes, data: bytes) -> bytes:
        crc = struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + typ + data + crc

    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b""))
    return path


def fake_blocks(**overrides) -> ResumeBlocks:
    blocks = ResumeBlocks(
        name="测试同学",
        intent="虚构测试岗位",
        contact_lines=["138-0000-0000", "tester@example.invalid"],
        summary="虚构的个人优势简介，仅用于 auto-fit 测试。",
        education_lines=["虚构大学｜虚构专业（本科）｜2023.09-2027.06"],
        internships=[
            BulletBlock(title="虚构有限公司", role="测试实习生",
                        meta="2025.06-2025.09",
                        bullets=["完成了一项虚构的测试工作。"]),
        ],
        projects=[
            BulletBlock(title="虚构项目甲", role="负责人",
                        meta="2025.03-至今", bullets=["虚构项目 bullet 一。"]),
        ],
        campus=["虚构校园经历甲"],
        skills=["技能甲"],
        certs=["虚构证书甲"],
    )
    for k, v in overrides.items():
        setattr(blocks, k, v)
    return blocks


def floating_photo(base_photo, *, ratio: float = 0.70):
    """在基线上派生一份浮动照片 delta（虚构数值）。"""
    return replace(
        base_photo,
        enabled=True,
        position="header_top_right_floating",
        width=Sourced.kv1(2.212, "cm"),
        height=Sourced.kv1(3.16, "cm"),
        aspect_ratio=Sourced.kv1(ratio, "ratio"),
        floating=PhotoFloating(
            enabled=True, position_h="column", position_v="page",
            offset_x_cm=Sourced.kv1(1.0, "cm"),
            offset_y_cm=Sourced.kv1(2.0, "cm")),
        border=PhotoBorder(Sourced.kv1("#BFBFBF"), Sourced.kv1(2.25, "pt")),
    )


def render(docx_path: Path, blocks=None, spec=None) -> Path:
    blocks = blocks or fake_blocks()
    spec = spec or _p3()
    doc = build_document(blocks, design_spec=spec)
    docx_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(docx_path))
    return docx_path


class _Temp(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory(prefix="fitting_test_")
        self.tmp = Path(self._dir.name)

    def tearDown(self):
        self._dir.cleanup()


# ---------------------------------------------------------------------------
# 估算（修正版）
# ---------------------------------------------------------------------------

class TestEstimator(_Temp):
    def test_01_usable_height_matches_a4_minus_margins(self):
        path = render(self.tmp / "a.docx")
        est = estimate_height(path)
        spec = _p3()
        expected = 29.7 - float(spec.page.margins.top.value) \
            - float(spec.page.margins.bottom.value)
        self.assertAlmostEqual(est.usable_cm, expected, places=2)
        self.assertGreater(est.body_cm, 0)
        self.assertGreater(est.total_cm, 0)

    def test_02_floating_photo_is_counted(self):
        """回归：历史估算器只遍历 wp:inline，浮动照片高度算作 0。"""
        png = write_png(self.tmp / "fictional_id.png", 100, 143)
        base = _p3()
        spec = assemble_job_spec(base, photo_delta=floating_photo(base.photo))
        self.assertTrue(validate_spec(spec).valid)
        path = render(self.tmp / "floating.docx",
                      blocks=fake_blocks(photo_path=str(png)), spec=spec)

        est = estimate_height(path)
        self.assertAlmostEqual(est.photo_cm, 3.16, delta=0.05,
                               msg="浮动照片（wp:anchor）高度必须计入估算")

        report = audit(path, spec=spec, blocks=fake_blocks(photo_path=str(png)))
        self.assertEqual(report.photo.count, 1)
        self.assertEqual(report.photo.floating, 1)
        self.assertEqual(report.photo.inline, 0)

    def test_03_broken_docx_is_reported_unavailable(self):
        bad = self.tmp / "broken.docx"
        bad.write_bytes(b"not a docx")
        pages, source = measure_pages(bad)
        self.assertIsNone(pages)
        self.assertEqual(source, "unavailable")


# ---------------------------------------------------------------------------
# 审计（八维）
# ---------------------------------------------------------------------------

class TestAudit(_Temp):
    def test_10_all_eight_dimensions_present(self):
        path = render(self.tmp / "a.docx")
        report = audit(path, spec=_p3(), blocks=fake_blocks())
        names = [row[0] for row in report.dimension_table()]
        self.assertEqual(
            names,
            ["页数", "溢出", "末行位置", "寡行", "内容密度",
             "边距安全区", "字号下限", "照片"])
        text = report.render()
        for name in names:
            self.assertIn(name, text)

    def test_11_pages_source_is_never_faked(self):
        path = render(self.tmp / "a.docx")
        report = audit(path, spec=_p3())
        self.assertIn(report.pages_source, ("word_com", "estimate", "unavailable"))

    def test_12_density_counts_entries_and_bullets(self):
        blocks = fake_blocks()
        path = render(self.tmp / "a.docx", blocks=blocks)
        report = audit(path, spec=_p3(), blocks=blocks)
        self.assertEqual(report.entry_count, 2)     # 1 实习 + 1 项目
        self.assertGreaterEqual(report.bullet_count, 3)

    def test_13_renderer_honours_declared_photo_ratio(self):
        """声明比例与落盘 extents 一致 → 不判变形（渲染器忠实执行 Spec）。"""
        png = write_png(self.tmp / "fictional_id.png", 100, 143)
        base = _p3()
        spec = assemble_job_spec(base, photo_delta=floating_photo(base.photo))
        path = render(self.tmp / "f.docx",
                      blocks=fake_blocks(photo_path=str(png)), spec=spec)
        report = audit(path, spec=spec)
        self.assertFalse(report.photo.distorted)
        self.assertEqual(report.photo.exact_line_with_image, 0,
                         "浮动照片锚点段不得使用 exact 行高（验收规则 4）")

    def test_14_photo_ratio_mismatch_is_flagged(self):
        png = write_png(self.tmp / "fictional_id.png", 100, 143)
        base = _p3()
        spec = assemble_job_spec(base, photo_delta=floating_photo(base.photo))
        path = render(self.tmp / "f.docx",
                      blocks=fake_blocks(photo_path=str(png)), spec=spec)
        # 人为把声明比例改错（audit 不做校验，用于验证判定逻辑本身）
        bad = replace(spec, photo=replace(spec.photo,
                                          aspect_ratio=Sourced.kv1(0.5, "ratio")))
        report = audit(path, spec=bad)
        self.assertTrue(report.photo.distorted)
        self.assertIn("照片比例与声明不符（变形）", report.problems)

    def test_15_font_check_tolerates_half_point_quantization(self):
        path = render(self.tmp / "a.docx")
        report = audit(path, spec=_p3())
        self.assertIsNotNone(report.min_font_pt)
        self.assertIsNotNone(report.declared_min_pt)
        self.assertGreaterEqual(FONT_QUANTIZATION_TOL_PT, 0.25)
        self.assertTrue(report.font_ok,
                        f"min={report.min_font_pt} declared={report.declared_min_pt}")

    def test_16_declared_min_font_reads_metadata_sizes(self):
        spec = _p3()
        declared = declared_min_font_pt(spec)
        floor = spec.constraints.minimum_body_font_size_pt
        self.assertIsNotNone(declared)
        # 元信息档允许小于正文下限
        self.assertLessEqual(declared, floor + 1e-9)

    def test_17_non_overflow_page_mismatch_is_explained(self):
        path = render(self.tmp / "a.docx")
        report = audit(path, spec=_p3(), target_pages=1,
                       measurer=lambda p: (2, "word_com"))
        report.estimate = None if report.estimate is None else report.estimate
        text = report.render()
        self.assertIn("以实测页数为准", text)


# ---------------------------------------------------------------------------
# 收敛梯
# ---------------------------------------------------------------------------

def scripted_measurer(sequence):
    """按序列返回页数的测页器（用完后保持最后一个值）。"""
    box = {"i": 0}

    def _fn(path):
        i = box["i"]
        box["i"] = i + 1
        return sequence[min(i, len(sequence) - 1)], "fake"
    return _fn


class TestFit(_Temp):
    def test_20_already_fitting_needs_no_convergence(self):
        result = fit(fake_blocks(), _p3(), self.tmp / "o.docx",
                     measurer=lambda p: (1, "fake"))
        self.assertTrue(result.converged)
        self.assertEqual(result.steps, [])
        self.assertTrue((self.tmp / "o.docx").is_file())

    def test_21_converges_and_reports_steps(self):
        m = scripted_measurer([2, 2, 1])
        result = fit(fake_blocks(), _p3(), self.tmp / "o.docx", measurer=m)
        self.assertTrue(result.converged)
        self.assertGreaterEqual(len(result.steps), 1)
        # 顺序：先动间距
        self.assertEqual(result.steps[0].stage, STAGE_SPACING)

    def test_22_stage_order_is_deterministic(self):
        result = fit(fake_blocks(), _p3(), self.tmp / "o.docx",
                     measurer=scripted_measurer([3, 3, 3, 3, 3, 3, 3, 2]))
        order = []
        for s in result.steps:
            if not order or order[-1] != s.stage:
                order.append(s.stage)
        self.assertEqual(order[:3], [STAGE_SPACING, STAGE_LINE, STAGE_MARGIN])

    def test_23_same_input_same_output(self):
        r1 = fit(fake_blocks(), _p3(), self.tmp / "a.docx",
                 measurer=scripted_measurer([2, 2, 1]))
        r2 = fit(fake_blocks(), _p3(), self.tmp / "b.docx",
                 measurer=scripted_measurer([2, 2, 1]))
        self.assertEqual([(s.stage, s.intensity) for s in r1.steps],
                         [(s.stage, s.intensity) for s in r2.steps])

    def test_24_stops_with_attribution_when_exhausted(self):
        result = fit(fake_blocks(), _p3(), self.tmp / "o.docx",
                     measurer=lambda p: (2, "word_com"))
        self.assertFalse(result.converged)
        self.assertTrue(result.attribution)
        self.assertIn("不自动缩字号", result.attribution)
        self.assertIn("删减内容", result.attribution)
        # 三档用尽后不再无谓重渲染
        self.assertLessEqual(len(result.steps), 6)

    def test_25_font_stage_is_off_by_default(self):
        result = fit(fake_blocks(), _p3(), self.tmp / "o.docx",
                     measurer=lambda p: (2, "word_com"))
        self.assertNotIn(STAGE_FONT, {s.stage for s in result.steps})

    def test_26_font_stage_opt_in(self):
        """字号档开启后才会被使用 —— 前提是正文有可压空间。

        注意：P3 预设的正文本来就是 9pt（= 规范下限），字号档对它天然无空间；
        这里显式造一份正文 9.5pt 的 spec，验证「有空间时字号档确实会走」。
        """
        base = _p3()
        taller = assemble_job_spec(
            base,
            typography_delta=replace(base.typography,
                                     body_size=Sourced.kv1(9.5, "pt")))
        result = fit(fake_blocks(), taller, self.tmp / "o.docx",
                     allow_font_reduction=True,
                     measurer=scripted_measurer([2, 2, 2, 2, 2, 2, 2, 1]))
        self.assertIn(STAGE_FONT, {s.stage for s in result.steps})
        self.assertTrue(result.converged)
        # 字号档只压到「刚好达标」为止（不是一路压到下限）
        final_pt = float(result.spec.typography.body_size.value)
        self.assertLess(final_pt, 9.5)
        self.assertGreaterEqual(final_pt, 9.0 - 1e-6)

    def test_27_max_steps_is_respected(self):
        result = fit(fake_blocks(), _p3(), self.tmp / "o.docx",
                     allow_font_reduction=True, max_steps=2,
                     measurer=lambda p: (3, "fake"))
        self.assertLessEqual(len(result.steps), 2)

    def test_28_result_reports_final_spec_and_report(self):
        result = fit(fake_blocks(), _p3(), self.tmp / "o.docx",
                     measurer=lambda p: (1, "fake"))
        self.assertIsNotNone(result.spec)
        self.assertEqual(result.report.pages, 1)
        self.assertTrue(result.report.ok, result.report.render())
        self.assertIn("auto-fit", result.render())


class TestStageFloors(_Temp):
    """到下限的档不得再产生「假进展」（否则空转到 max_steps）。"""

    def test_30_spacing_stage_at_floor_is_idempotent(self):
        from resume_generator.fitting import _spacing_stage, _tunables

        spec = _p3()
        once = _spacing_stage(spec, 1.0)
        twice = _spacing_stage(once, 1.0)
        self.assertEqual(_tunables(once), _tunables(twice))
        self.assertNotEqual(_tunables(once), _tunables(spec))

    def test_31_margin_stage_at_floor_is_idempotent(self):
        from resume_generator.fitting import _margin_stage, _tunables

        spec = _p3()
        once = _margin_stage(spec, 1.0)
        twice = _margin_stage(once, 1.0)
        self.assertEqual(_tunables(once), _tunables(twice))
        self.assertAlmostEqual(float(once.page.margins.top.value),
                               MARGIN_FLOOR_CM, places=4)
        # safe_area 必须与 margins 同步（防「改了边距忘改版心」的历史事故）
        self.assertAlmostEqual(float(once.page.safe_area.top.value),
                               MARGIN_FLOOR_CM, places=4)
        self.assertAlmostEqual(
            float(once.page.safe_area.content_width.value),
            21.0 - 2 * MARGIN_FLOOR_CM, places=4)

    def test_32_font_stage_respects_body_floor(self):
        from resume_generator.fitting import _font_stage

        base = _p3()
        floor = float(base.constraints.minimum_body_font_size_pt)
        taller = assemble_job_spec(
            base,
            typography_delta=replace(base.typography,
                                     body_size=Sourced.kv1(9.5, "pt")))
        reduced = _font_stage(taller, 1.0)
        self.assertAlmostEqual(float(reduced.typography.body_size.value),
                               floor, places=4)
        # 原 spec 不被原地修改
        self.assertAlmostEqual(float(taller.typography.body_size.value),
                               9.5, places=4)

    def test_34_font_stage_is_noop_when_body_already_at_floor(self):
        """P3 预设正文即 9pt：字号档必须识别「无空间」而不是造出假进展。"""
        from resume_generator.fitting import _font_stage, _tunables

        spec = _p3()
        reduced = _font_stage(spec, 1.0)
        self.assertEqual(_tunables(reduced), _tunables(spec))

    def test_33_line_spacing_stage_floor(self):
        from resume_generator.fitting import _line_stage

        spec = _p3()
        reduced = _line_stage(spec, 1.0)
        self.assertAlmostEqual(float(reduced.typography.line_spacing.body.value),
                               1.0, places=4)


class TestFitError(_Temp):
    def test_40_unmeasurable_raises_fit_error(self):
        with self.assertRaises(FitError):
            fit(fake_blocks(), _p3(), self.tmp / "o.docx",
                measurer=lambda p: (None, "unavailable"))


if __name__ == "__main__":
    unittest.main()
