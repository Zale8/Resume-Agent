# -*- coding: utf-8 -*-
"""test_renderer_stability.py — Phase 3A Renderer 基础稳定化回归测试。

覆盖：
    1. usable_width 单一几何来源
    2. minimal 表宽 == usable_width（Bug2 回归）
    3. 列比例切分后列宽之和 == 表宽
    4. 照片等比保护（同比例/不同比例都不变形）
    5. 缺失照片不崩溃
    6. 日期右制表位定位（禁止空格）
    7. 旧调用签名向后兼容
    8. build_document(design_spec=...) 兼容入口（P1/P2）

所有图片用 stdlib 现场合成纯色 PNG；简历数据全部虚构（张三），不含个人事实。

用法：python tests/test_renderer_stability.py
"""
from __future__ import annotations

import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from docx import Document  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402
from docx.shared import Cm  # noqa: E402

from resume_generator.layout_kit import (  # noqa: E402
    insert_photo,
    split_columns_cm,
    usable_width_cm,
    BulletBlock,
    ResumeBlocks,
)
from resume_generator.skeletons import build_document  # noqa: E402


# ---------------------------------------------------------------------------
# 虚构夹具
# ---------------------------------------------------------------------------

def write_png(path: Path, w: int, h: int, rgb=(90, 120, 180)) -> Path:
    """用 stdlib 合成纯色 PNG（不依赖 Pillow，不使用任何真实证件照）。"""
    def chunk(typ: bytes, data: bytes) -> bytes:
        crc = struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + typ + data + crc

    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", zlib.compress(raw))
           + chunk(b"IEND", b""))
    path.write_bytes(png)
    return path


def fake_blocks(**overrides) -> ResumeBlocks:
    blocks = ResumeBlocks(
        name="张三",
        intent="测试岗位",
        contact_lines=["138-0000-0000", "zhangsan@example.com", "测试市"],
        summary="虚构的个人优势简介，用于渲染稳定性测试。",
        education_lines=["XX大学  测试专业（本科）    2023.09 - 2027.06"],
        internships=[
            BulletBlock(
                title="某某有限公司",
                role="测试实习生",
                meta="2025.06 - 2025.09",
                tags="标签甲 · 标签乙",
                bullets=["完成了一项虚构的测试工作。", "完成了另一项虚构工作。"],
            )
        ],
        projects=[
            BulletBlock(
                title="虚构项目甲",
                role="负责人",
                meta="2025.03 - 至今",
                bullets=["虚构项目 bullet 一。", "虚构项目 bullet 二。"],
            )
        ],
        campus=["虚构校园经历甲", "虚构校园经历乙"],
        skills=["技能甲", "技能乙"],
        certs=["虚构证书甲"],
    )
    for k, v in overrides.items():
        setattr(blocks, k, v)
    return blocks


def first_table_grid_widths_cm(doc) -> list:
    """读第一个表 tblGrid 的真实列宽（cm）。"""
    tbl = doc.tables[0]._tbl
    grid = tbl.find(qn("w:tblGrid"))
    cols = grid.findall(qn("w:gridCol"))
    return [int(c.get(qn("w:w"))) / 567.0 for c in cols]  # twips→cm（1cm=567twips 近似）


def table_grid_twips(doc) -> int:
    tbl = doc.tables[0]._tbl
    grid = tbl.find(qn("w:tblGrid"))
    return sum(int(c.get(qn("w:w"))) for c in grid.findall(qn("w:gridCol")))


class TestRendererStability(unittest.TestCase):

    # -- Test 1 -------------------------------------------------------------
    def test_01_usable_width_single_source(self):
        self.assertAlmostEqual(usable_width_cm(1.25, 1.25), 18.5, places=6)
        self.assertAlmostEqual(usable_width_cm(1.0, 1.0), 19.0, places=6)
        self.assertAlmostEqual(usable_width_cm(0.8, 0.8), 19.4, places=6)
        self.assertAlmostEqual(usable_width_cm(1.4, 1.4), 18.2, places=6)

    # -- Test 2 -------------------------------------------------------------
    def test_02_minimal_table_width_equals_usable_width(self):
        doc = build_document(fake_blocks(), "single_column_minimal")
        sec = doc.sections[0]
        # 边距确认为 1.25（Word 以整 twips 存储，回读有 ~0.0006cm 量化误差）
        self.assertAlmostEqual(sec.left_margin.cm, 1.25, places=2)
        self.assertAlmostEqual(sec.right_margin.cm, 1.25, places=2)
        # 表宽必须是 21 - 1.25 - 1.25 = 18.5（旧版错算成 18.0）
        self.assertAlmostEqual(table_grid_twips(doc), Cm(18.5).twips,
                               delta=2)  # 容差 2 twips（约 0.0004cm）

    # -- Test 3 -------------------------------------------------------------
    def test_03_column_widths_sum_to_table_width(self):
        for total, ratios in [(19.4, (5.9 / 19.4, 13.5 / 19.4)),
                              (18.5, (13.0 / 18.0, 5.0 / 18.0)),
                              (19.0, (0.32, 0.68))]:
            widths = split_columns_cm(total, ratios)
            self.assertEqual(len(widths), len(ratios))
            self.assertAlmostEqual(sum(widths), total, places=9)
        with self.assertRaises(ValueError):
            split_columns_cm(19.0, (0.3, 0.8))  # 和≠1 必须拒绝

    # -- Test 4 -------------------------------------------------------------
    def test_04_photo_aspect_ratio_protection(self):
        tmp = Path(tempfile.mkdtemp(prefix="photo_ratio_"))

        # 4a. 源图比例与目标盒一致 → inserted_equal，铺满
        same = write_png(tmp / "same.png", 185, 240)  # ar≈0.7708 = 盒比例
        doc = Document()
        r = insert_photo(doc.add_paragraph(), str(same), 1.85, 2.4)
        self.assertTrue(r.ok)
        self.assertEqual(r.status, "inserted_equal")
        shape = doc.inline_shapes[0]
        self.assertAlmostEqual(shape.width.cm, 1.85, places=3)
        self.assertAlmostEqual(shape.height.cm, 2.4, places=3)

        # 4b. 源图比例与目标盒不同（证件照 0.714 放进 0.771 的盒）→ contain 不变形
        diff = write_png(tmp / "diff.png", 100, 140)  # ar≈0.7143
        doc2 = Document()
        r2 = insert_photo(doc2.add_paragraph(), str(diff), 1.85, 2.4)
        self.assertTrue(r2.ok)
        self.assertEqual(r2.status, "inserted_contain")
        shape2 = doc2.inline_shapes[0]
        actual_ar = shape2.width / shape2.height
        src_ar = 100 / 140
        self.assertAlmostEqual(actual_ar, src_ar, places=4,
                               msg="实际渲染宽高比必须等于源图比例（禁止拉伸）")
        # contain 后图片不超出目标盒
        self.assertLessEqual(shape2.width, Cm(1.85) + 2000)
        self.assertLessEqual(shape2.height, Cm(2.4) + 2000)

    # -- Test 5 -------------------------------------------------------------
    def test_05_missing_photo_safe(self):
        doc = Document()
        r = insert_photo(doc.add_paragraph(), None, 1.85, 2.4)
        self.assertFalse(r.ok)
        self.assertEqual(r.status, "missing")
        self.assertEqual(len(doc.inline_shapes), 0)

        r2 = insert_photo(doc.add_paragraph(),
                          str(Path(tempfile.gettempdir()) / "__no_such__.png"),
                          1.85, 2.4)
        self.assertEqual(r2.status, "missing")

        # 整页渲染在无照片时也不崩溃
        built = build_document(fake_blocks(photo_path=None),
                               "single_column_minimal")
        self.assertEqual(len(built.inline_shapes), 0)

    # -- Test 6 -------------------------------------------------------------
    def test_06_date_uses_right_tab_stop_not_spaces(self):
        doc = build_document(fake_blocks(), "banner_card")
        target = None
        for p in doc.paragraphs:
            if "某某有限公司" in p.text:
                target = p
                break
        self.assertIsNotNone(target, "应找到实习经历表头行")

        # 右对齐制表位存在
        tabs = target._p.findall(".//" + qn("w:tabs") + "/" + qn("w:tab"))
        right_tabs = [t for t in tabs if t.get(qn("w:val")) == "right"]
        self.assertEqual(len(right_tabs), 1, "日期必须由一个右对齐 tab stop 定位")

        # 日期前是 tab 而不是 4 个空格
        self.assertIn("\t2025.06 - 2025.09", target.text)
        self.assertNotIn("    2025.06", target.text)
        # run 内有真实 <w:tab/> 元素
        self.assertTrue(target._p.findall(".//" + qn("w:tab")))

    # -- Test 7 -------------------------------------------------------------
    def test_07_backward_compatible_signature(self):
        tmp = Path(tempfile.mkdtemp(prefix="compat_"))
        # 位置参：build_document(blocks, skeleton_id)
        d1 = build_document(fake_blocks(), "banner_card")
        # 关键字 + 色板：build_document(blocks, skeleton_id, palette_id)
        d2 = build_document(fake_blocks(), "single_column_minimal",
                            "minimal_ink")
        d3 = build_document(fake_blocks(), "two_column_sidebar",
                            palette_id="manufacturing_steel")
        for i, d in enumerate((d1, d2, d3), 1):
            out = tmp / f"old_call_{i}.docx"
            d.save(str(out))
            self.assertGreater(out.stat().st_size, 10000)

    # -- Test 8 -------------------------------------------------------------
    def test_08_design_spec_entry(self):
        from resume_generator.design import build_p1_spec, build_p2_spec
        from resume_generator.design.validator import validate_spec

        tmp = Path(tempfile.mkdtemp(prefix="spec_entry_"))

        # P1：校验无 ERROR；边距/表宽来自 Spec（0.5/1.2/1.4/1.4 → usable 18.2）
        p1 = build_p1_spec()
        self.assertTrue(validate_spec(p1).valid)
        d1 = build_document(fake_blocks(), design_spec=p1)
        sec = d1.sections[0]
        self.assertAlmostEqual(sec.left_margin.cm, 1.4, places=2)
        self.assertAlmostEqual(sec.top_margin.cm, 0.5, places=2)
        self.assertAlmostEqual(table_grid_twips(d1), Cm(18.2).twips, delta=2)
        out1 = tmp / "p1_spec.docx"
        d1.save(str(out1))
        self.assertGreater(out1.stat().st_size, 10000)

        # P2：有 WARNING 但无 ERROR，仍可渲染（margins 未定 → 沿用 sidebar 默认）
        p2 = build_p2_spec()
        result2 = validate_spec(p2)
        self.assertTrue(result2.valid)
        self.assertGreater(len(result2.warnings), 0)
        d2 = build_document(fake_blocks(), design_spec=p2)
        self.assertAlmostEqual(table_grid_twips(d2), Cm(19.4).twips, delta=2)
        out2 = tmp / "p2_spec.docx"
        d2.save(str(out2))
        self.assertGreater(out2.stat().st_size, 10000)

        # strict 模式下 P2 的 WARNING 必须被拒绝
        with self.assertRaises(ValueError):
            build_document(fake_blocks(), design_spec=p2, strict=True)


class TestFloatingPhoto(unittest.TestCase):
    """浮动照片 wp:anchor（Golden Sample CL-01 产品化，Phase 2B-4 Step 4）。

    合成 PNG + 虚构张三；Golden 坐标值仅用于验证参数透传，不写入 preset。
    """

    def _anchor(self, doc):
        anchors = doc.element.body.findall(".//" + qn("wp:anchor"))
        self.assertEqual(len(anchors), 1, "必须恰好 1 个 wp:anchor")
        return anchors[0]

    def test_01_anchor_xml_matches_cl01(self):
        from resume_generator.layout_kit import insert_floating_photo

        tmp = Path(tempfile.mkdtemp(prefix="float_photo_"))
        png = write_png(tmp / "id.png", 100, 143)  # ar≈0.699 虚构图
        doc = Document()
        r = insert_floating_photo(
            doc.add_paragraph(), str(png), 2.212, 3.156,
            position_h="column", position_v="page",
            offset_x_cm=2.574, offset_y_cm=0.09,
            border_color="#BFBFBF", border_width_pt=2.25)
        self.assertTrue(r.ok)
        self.assertEqual(r.status, "inserted_floating")
        self.assertEqual(len(doc.inline_shapes), 0,
                         "inline 必须被替换为 anchor（inline_shapes 计数为 0）")

        a = self._anchor(doc)
        # 衬于文字下方 / 单元格内锚定 / 允许重叠（CL-01）
        self.assertEqual(a.get("behindDoc"), "1")
        self.assertEqual(a.get("layoutInCell"), "1")
        self.assertEqual(a.get("allowOverlap"), "1")
        self.assertEqual(a.get("simplePos"), "0")
        # 上下型环绕，且不存在其它环绕方式
        self.assertIsNotNone(a.find(qn("wp:wrapTopAndBottom")))
        self.assertIsNone(a.find(qn("wp:wrapSquare")))
        self.assertIsNone(a.find(qn("wp:wrapNone")))
        # 相对锚点 + posOffset（cm→EMU，1cm=360000）
        ph = a.find(qn("wp:positionH"))
        self.assertEqual(ph.get("relativeFrom"), "column")
        self.assertEqual(int(ph.find(qn("wp:posOffset")).text), 926640)
        pv = a.find(qn("wp:positionV"))
        self.assertEqual(pv.get("relativeFrom"), "page")
        self.assertEqual(int(pv.find(qn("wp:posOffset")).text), 32400)
        # extent = 实际等比放置尺寸（contain，不拉伸）
        ext = a.find(qn("wp:extent"))
        self.assertEqual(int(ext.get("cx")),
                         int(round(r.applied_width_cm * 360000)))
        self.assertEqual(int(ext.get("cy")),
                         int(round(r.applied_height_cm * 360000)))
        # 边框 a:ln：2.25pt=28575 EMU，#BFBFBF
        ln = a.find(".//" + qn("a:ln"))
        self.assertIsNotNone(ln, "浮动照片必须带 a:ln 边框")
        self.assertEqual(int(ln.get("w")), 28575)
        clr = ln.find(qn("a:solidFill") + "/" + qn("a:srgbClr"))
        self.assertEqual(clr.get("val"), "BFBFBF")

    def test_02_no_border_when_width_zero(self):
        from resume_generator.layout_kit import insert_floating_photo

        tmp = Path(tempfile.mkdtemp(prefix="float_nb_"))
        png = write_png(tmp / "id.png", 100, 143)
        doc = Document()
        insert_floating_photo(doc.add_paragraph(), str(png), 2.0, 2.8,
                              border_color=None, border_width_pt=0.0)
        a = self._anchor(doc)
        self.assertIsNone(a.find(".//" + qn("a:ln")))

    def test_03_missing_photo_safe(self):
        from resume_generator.layout_kit import insert_floating_photo

        doc = Document()
        r = insert_floating_photo(doc.add_paragraph(), None, 2.0, 2.8)
        self.assertFalse(r.ok)
        self.assertEqual(r.status, "missing")
        self.assertFalse(doc.element.body.findall(".//" + qn("wp:anchor")))

    def test_04_exact_line_spacing_neutralized(self):
        """行高保护：锚点段原本 exact 行距必须被改回自动（防裁图）。"""
        from docx.oxml import OxmlElement
        from resume_generator.layout_kit import insert_floating_photo

        tmp = Path(tempfile.mkdtemp(prefix="float_line_"))
        png = write_png(tmp / "id.png", 100, 143)
        doc = Document()
        p = doc.add_paragraph()
        p_pr = p._p.get_or_add_pPr()
        spacing = OxmlElement("w:spacing")
        spacing.set(qn("w:line"), "400")
        spacing.set(qn("w:lineRule"), "exact")
        p_pr.append(spacing)

        insert_floating_photo(p, str(png), 2.0, 2.8)
        after = p._p.find(qn("w:pPr") + "/" + qn("w:spacing"))
        self.assertNotIn(after.get(qn("w:lineRule")), ("exact", "atLeast"),
                         msg="浮动照片锚点段禁止固定行距")
        self.assertIsNone(after.get(qn("w:line")),
                          msg="固定 line 值必须一并移除，回到自动行距")

    def test_05_spec_path_end_to_end(self):
        """P3 spec + Golden 照片形态（内存 replace）→ minimal 产出 anchor。"""
        from dataclasses import replace
        from resume_generator.design import (
            build_p3_spec, Sourced, PhotoFloating, PhotoBorder)

        tmp = Path(tempfile.mkdtemp(prefix="float_e2e_"))
        png = write_png(tmp / "zhangsan.png", 100, 143)
        spec = build_p3_spec()
        photo = replace(
            spec.photo, enabled=True, position="header_top_right_floating",
            width=Sourced.kv1(2.212, "cm"), height=Sourced.kv1(3.156, "cm"),
            aspect_ratio=Sourced.kv1(0.70, "ratio"),
            container="floating_anchored_no_fill",
            floating=PhotoFloating(
                enabled=True, position_h="column", position_v="page",
                offset_x_cm=Sourced.kv1(2.574, "cm"),
                offset_y_cm=Sourced.kv1(0.09, "cm")),
            border=PhotoBorder(Sourced.kv1("#BFBFBF"),
                               Sourced.kv1(2.25, "pt")))
        spec = replace(spec, photo=photo)

        doc = build_document(fake_blocks(photo_path=str(png)),
                             design_spec=spec)
        a = self._anchor(doc)
        self.assertEqual(a.find(qn("wp:positionV")).get("relativeFrom"), "page")
        self.assertEqual(a.get("behindDoc"), "1")
        self.assertEqual(int(a.find(".//" + qn("a:ln")).get("w")), 28575)
        # Header 为含照片格的 2 列表
        self.assertEqual(len(doc.tables[0].columns), 2)
        # 可落盘并重开（XML 良构）
        out = tmp / "p3_floating.docx"
        doc.save(str(out))
        Document(str(out))
        self.assertGreater(out.stat().st_size, 10000)

    def test_06_legacy_path_still_inline(self):
        """旧路径（skeleton_id 直调）照片保持 wp:inline，零行为变化。"""
        tmp = Path(tempfile.mkdtemp(prefix="float_legacy_"))
        png = write_png(tmp / "id.png", 100, 143)
        doc = build_document(fake_blocks(photo_path=str(png)),
                             "single_column_minimal")
        self.assertEqual(len(doc.inline_shapes), 1)
        self.assertFalse(doc.element.body.findall(".//" + qn("wp:anchor")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
