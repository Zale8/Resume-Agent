# -*- coding: utf-8 -*-
"""test_renderer_photo_box_fallback.py — 照片盒 / 几何覆盖的「无真实数值」回归测试。

背景（2026-09-21 实测缺陷）
--------------------------
`Sourced.not_applicable()` 的 value 是 **None**，但 status 是 CONFIRMED，
因此 `is_undetermined` 为 False。旧 Renderer 只判 `is_undetermined` 就
`float(sv.value)`，于是：

    build_p3_spec()            # P3 Preset 的 photo.width/height 是 not_applicable
      + photo_delta(enabled=True)   # 按 agent_entry.md §5.1 给 P3 加照片
      → Validator 通过
      → skeletons._build_from_spec 里 float(None) → TypeError 崩溃

同类的潜在崩溃点还有 page.margins（某一项 not_applicable 时）。

修复语义：拿不到**真实数值**（未确定 / not_applicable / 非数值）
= 本份未指定 → 不覆盖，沿用骨架的范式级默认值；
既不得崩溃，也不得为填满字段编造数值。

覆盖：
    1. `_concrete_cm` / `_concrete_box_cm` 语义（not_applicable / undetermined / 真实值）
    2. P3 + 启用照片但未给尺寸 → 不崩溃，照片盒回退骨架默认（1.85×2.4cm）
    3. P3 + 启用照片且给定尺寸 → Spec 尺寸生效（覆盖骨架默认）
    4. P3 + 启用照片 + floating → 走 wp:anchor，且恰好 1 张图
    5. 页边距出现 not_applicable → 不崩溃，回退骨架默认边距

所有图片用 stdlib 现场合成纯色 PNG；简历数据全部虚构（张三），不含个人事实。

用法：python tests/test_renderer_photo_box_fallback.py
"""
from __future__ import annotations

import struct
import sys
import tempfile
import unittest
import zipfile
import zlib
from dataclasses import replace
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from resume_generator.design import (  # noqa: E402
    PhotoBorder,
    PhotoFloating,
    Sourced,
    assemble_job_spec,
    validate_spec,
)
from resume_generator.design.presets import build_p1_spec, build_p3_spec  # noqa: E402
from resume_generator.layout_kit import (  # noqa: E402
    BulletBlock,
    ResumeBlocks,
)
from resume_generator.skeletons import (  # noqa: E402
    _concrete_box_cm,
    _concrete_cm,
    _LAYOUT_CONFIG,
    build_document,
    SKELETON_MINIMAL,
)

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
}
EMU_PER_CM = 360000


# ---------------------------------------------------------------------------
# 虚构夹具
# ---------------------------------------------------------------------------

def write_png(path: Path, w: int, h: int, rgb=(90, 120, 180)) -> Path:
    """stdlib 合成纯色 PNG（不依赖 Pillow，不使用任何真实证件照）。"""
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


def fictional_blocks(photo: Path) -> ResumeBlocks:
    """虚构人物张三；无任何真实姓名/电话/经历。"""
    return ResumeBlocks(
        name="张三",
        intent="求职意向：测试岗位",
        contact_lines=["电话：13800000000", "邮箱：zhangsan@example.com"],
        summary="仅用于测试的虚构个人优势描述。",
        education_lines=["某虚构大学 / 本科 / 某专业 / 2022.09-2026.06"],
        internships=[BulletBlock("某科技公司", "2025.06-2025.06", "实习生",
                                 ["完成虚构测试任务"])],
        projects=[BulletBlock("校园信息服务", "2024.03-2024.06", "",
                              ["搭建虚构信息平台"])],
        campus=["班级体育委员"],
        skills=["Python"],
        certs=["CET-6"],
        photo_path=str(photo),
    )


def expected_contain(box_w: float, box_h: float, src_ar: float):
    """layout_kit.insert_photo 的 contain 等比规则（独立复算，作为断言依据）。"""
    box_ar = box_w / box_h
    if src_ar > box_ar:
        return box_w, box_w / src_ar
    return box_h * src_ar, box_h


def docx_geometry(docx_path: Path):
    """返回 (extent 列表[(cx,cy)], anchor 数, inline 数)。"""
    with zipfile.ZipFile(docx_path) as z:
        root = ET.fromstring(z.read("word/document.xml").decode("utf-8"))
    extents = [(int(e.get("cx")), int(e.get("cy")))
               for e in root.findall(".//wp:extent", NS)]
    return (extents,
            len(root.findall(".//wp:anchor", NS)),
            len(root.findall(".//wp:inline", NS)))


class PhotoBoxFallbackTest(unittest.TestCase):
    """照片盒「无真实数值 → 回退默认」的行为契约。"""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="photo_box_fallback_")
        cls.tmpdir = Path(cls.tmp.name)
        # 701 x 1000 → ar = 0.701，与 P1/P3 两个候选盒比例都不同，便于区分
        cls.photo = write_png(cls.tmpdir / "zhangsan.png", 701, 1000)
        cls.src_ar = 701 / 1000

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _render(self, spec, tag: str) -> Path:
        doc = build_document(fictional_blocks(self.photo), design_spec=spec)
        out = self.tmpdir / f"{tag}.docx"
        doc.save(str(out))
        return out

    # --- 1. _concrete_cm 语义 -------------------------------------------

    def test_01_concrete_cm_semantics(self):
        self.assertEqual(_concrete_cm(Sourced.kv1(2.2, "cm")), 2.2)
        # not_applicable：value=None 但 status=confirmed（is_undetermined=False）
        na = Sourced.not_applicable("P3 不使用照片")
        self.assertFalse(na.is_undetermined)
        self.assertIsNone(_concrete_cm(na))
        # 真缺口
        self.assertIsNone(_concrete_cm(Sourced.undetermined("知识库缺口")))
        self.assertIsNone(_concrete_cm(None))
        # 非数值（string Sourced）不得当成尺寸
        self.assertIsNone(_concrete_cm(Sourced.kv1("#BFBFBF", "hex")))
        # 布尔不是尺寸（bool 是 int 的子类，必须排除）
        self.assertIsNone(_concrete_cm(Sourced.kv1(True)))
        # 成对取值：任一缺失即整体 None
        self.assertIsNone(_concrete_box_cm(Sourced.kv1(2.0), na))
        self.assertEqual(_concrete_box_cm(Sourced.kv1(2.0), Sourced.kv1(3.0)),
                         (2.0, 3.0))

    # --- 2. P3 + 启用照片但未给尺寸 → 回退骨架默认盒 ----------------------

    def test_02_p3_photo_enabled_without_dims_falls_back(self):
        base = build_p3_spec()
        self.assertFalse(base.photo.enabled, "P3 Preset 预设应关闭照片")
        # 本份只声明「要照片」，不给尺寸（P3 Preset 的 width/height 是 not_applicable）
        spec = assemble_job_spec(
            base, photo_delta=replace(base.photo, enabled=True))
        self.assertTrue(spec.photo.enabled)
        self.assertIsNone(spec.photo.width.value)
        result = validate_spec(spec)
        self.assertFalse(result.errors, [e.render() for e in result.errors])

        # 修复前：此处 float(None) → TypeError
        out = self._render(spec, "p3_no_dims")
        extents, anchors, inlines = docx_geometry(out)
        self.assertEqual(len(extents), 1)
        self.assertEqual((anchors, inlines), (0, 1), "未声明 floating 应保持内联")

        # 照片盒应等于「骨架默认盒(1.85, 2.4) 的 contain 结果」，而不是崩溃或乱猜
        default_w, default_h = _LAYOUT_CONFIG[SKELETON_MINIMAL]["photo_box_cm"]
        exp_w, exp_h = expected_contain(default_w, default_h, self.src_ar)
        cx, cy = extents[0]
        self.assertAlmostEqual(cx, round(exp_w * EMU_PER_CM), delta=2000)
        self.assertAlmostEqual(cy, round(exp_h * EMU_PER_CM), delta=2000)

    # --- 3. P3 + 给定尺寸 → Spec 尺寸生效 -------------------------------

    def test_03_p3_declared_dims_win_over_default(self):
        base = build_p3_spec()
        spec = assemble_job_spec(base, photo_delta=replace(
            base.photo, enabled=True,
            width=Sourced.kv1(2.2, "cm"), height=Sourced.kv1(3.139, "cm")))
        out = self._render(spec, "p3_with_dims")
        extents, _, _ = docx_geometry(out)
        exp_w, exp_h = expected_contain(2.2, 3.139, self.src_ar)
        cx, cy = extents[0]
        self.assertAlmostEqual(cx, round(exp_w * EMU_PER_CM), delta=2000)
        self.assertAlmostEqual(cy, round(exp_h * EMU_PER_CM), delta=2000)
        # 必须与「回退默认盒」的结果不同，证明 Spec 真的生效了
        default_w, default_h = _LAYOUT_CONFIG[SKELETON_MINIMAL]["photo_box_cm"]
        self.assertNotAlmostEqual(
            cx, round(expected_contain(default_w, default_h, self.src_ar)[0]
                      * EMU_PER_CM), delta=2000)

    # --- 4. P3 + floating → wp:anchor ----------------------------------

    def test_04_p3_floating_photo_uses_anchor(self):
        base = build_p3_spec()
        spec = assemble_job_spec(base, photo_delta=replace(
            base.photo, enabled=True,
            floating=PhotoFloating(enabled=True),
            border=PhotoBorder(Sourced.kv1("#BFBFBF"), Sourced.kv1(2.25, "pt"))))
        result = validate_spec(spec)
        self.assertFalse(result.errors, [e.render() for e in result.errors])
        out = self._render(spec, "p3_floating")
        extents, anchors, inlines = docx_geometry(out)
        self.assertEqual(len(extents), 1)
        self.assertEqual((anchors, inlines), (1, 0), "floating 应写 wp:anchor")

    # --- 5. 页边距 not_applicable → 回退骨架默认边距 ---------------------

    def test_05_not_applicable_margin_does_not_crash(self):
        base = build_p1_spec()
        # 边距不在 assemble_job_spec 的 delta 白名单内，直接构造本份 Spec
        spec = replace(base, page=replace(
            base.page,
            margins=replace(base.page.margins,
                            left=Sourced.not_applicable("测试：不适用"))))
        # 任一页边距拿不到数值 → 整体回退骨架默认边距，不得 float(None)
        out = self._render(spec, "p1_na_margin")
        self.assertTrue(out.is_file())
        with zipfile.ZipFile(out) as z:
            xml = z.read("word/document.xml").decode("utf-8")
        self.assertIn("w:sectPr", xml)


if __name__ == "__main__":
    unittest.main(verbosity=2)
