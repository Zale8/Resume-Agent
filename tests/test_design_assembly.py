# -*- coding: utf-8 -*-
"""test_design_assembly.py — 最小 Design Engine 装配层测试（Phase 2B-4 Step 6）。

覆盖契约：
    1. photo_delta=None → 与基线等价（同一对象，绝不自动启用浮动照片）；
    2. photo_delta → 仅替换 photo 节点，其余 12 个一级节点身份不变；
    3. immutable 装配：base_spec 不被 mutation；
    4. 非法 floating/border 参数由【现有】validate_spec 拦截（不复制校验）；
    5. 装配产物可直接进入 build_document(design_spec=...) 端到端渲染；
    6. PhotoFloating/PhotoBorder 子节点「提供才覆盖」语义；
    7. 类型边界（TypeError）与包级公开导出。

所有人物 / 坐标 / 图片均为虚构测试夹具，不含任何真实个人数据。
"""
from __future__ import annotations

import struct
import sys
import tempfile
import unittest
import zlib
from dataclasses import fields, replace
from pathlib import Path

# 让 import 能找到 src/（与其他 tests 文件一致）
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from resume_generator.design import (  # noqa: E402
    ExperienceSpec,
    LineSpacing,
    PhotoBorder,
    PhotoFloating,
    PhotoSpec,
    SectionSpec,
    Sourced,
    TypographySpec,
    assemble_job_spec,
    build_p1_spec,
    build_p3_spec,
    validate_spec,
    RULE_PHOTO_BORDER,
    RULE_PHOTO_FLOATING,
)
from resume_generator.layout_kit import (  # noqa: E402
    BulletBlock,
    ResumeBlocks,
)
from resume_generator.skeletons import build_document  # noqa: E402


# ---------------------------------------------------------------------------
# 虚构夹具（与 test_renderer_stability.py 同款，保持测试文件可独立运行）
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
        contact_lines=["138-0000-0000", "tester@example.invalid", "虚构城市"],
        summary="虚构的个人优势简介，仅用于装配层渲染测试。",
        education_lines=["虚构大学  虚构专业（本科）    2023.09 - 2027.06"],
        internships=[
            BulletBlock(
                title="虚构有限公司",
                role="测试实习生",
                meta="2025.06 - 2025.09",
                tags="标签甲 · 标签乙",
                bullets=["完成了一项虚构的测试工作。", "另一项虚构工作。"],
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
        campus=["虚构校园经历甲"],
        skills=["技能甲", "技能乙"],
        certs=["虚构证书甲"],
    )
    for k, v in overrides.items():
        setattr(blocks, k, v)
    return blocks


def fictional_floating_photo(base: PhotoSpec, **floating_kw) -> PhotoSpec:
    """在基线上派生一份「本份照片 delta」（节点级 replace，虚构数值）。"""
    floating_kw.setdefault("enabled", True)
    floating_kw.setdefault("position_h", "column")
    floating_kw.setdefault("position_v", "page")
    floating_kw.setdefault("offset_x_cm", Sourced.kv1(1.0, "cm"))
    floating_kw.setdefault("offset_y_cm", Sourced.kv1(2.0, "cm"))
    return replace(
        base,
        enabled=True,
        position="header_top_right_floating",
        width=Sourced.kv1(2.212, "cm"),
        height=Sourced.kv1(3.156, "cm"),
        aspect_ratio=Sourced.kv1(0.70, "ratio"),
        container="floating_anchored_no_fill",
        floating=PhotoFloating(**floating_kw),
        border=PhotoBorder(Sourced.kv1("#BFBFBF"),
                           Sourced.kv1(2.25, "pt")),
    )


def compact_typography(base: TypographySpec, *, body=1.08, title=1.05) -> TypographySpec:
    """在基线 TypographySpec 上派生紧凑行距 delta（节点级 replace）。"""
    return replace(
        base,
        line_spacing=LineSpacing(
            body=Sourced.kv1(body, "ratio"),
            title=Sourced.kv1(title, "ratio"),
        ),
    )


def compact_section(base: SectionSpec, *, spacing_before=5,
                    divider_to_first_line=3) -> SectionSpec:
    """在基线 SectionSpec 上派生紧凑间距 delta。"""
    return replace(
        base,
        spacing_before=Sourced.kv1(spacing_before, "pt"),
        divider_to_first_line=Sourced.kv1(divider_to_first_line, "pt"),
    )


def compact_experience(base: ExperienceSpec, *, entry_spacing=3,
                       bullet_after=1.5) -> ExperienceSpec:
    """在基线 ExperienceSpec 上派生紧凑条目间距 delta。"""
    return replace(
        base,
        entry_spacing=Sourced.kv1(entry_spacing, "pt"),
        bullet_spacing_after=Sourced.kv1(bullet_after, "pt"),
    )


def _error_rule_ids(result) -> list:
    return [i.rule_id for i in result.errors]


# ---------------------------------------------------------------------------
# 测试
# ---------------------------------------------------------------------------

class TestAssembleJobSpec(unittest.TestCase):

    # -- Test 1：None 语义 ---------------------------------------------------
    def test_01_none_delta_keeps_base_unchanged(self):
        """photo_delta=None 必须保持基线照片设计，且不自动启用浮动照片。"""
        base = build_p3_spec()
        assembled = assemble_job_spec(base)  # photo_delta 默认 None
        self.assertEqual(assembled, base)
        self.assertIs(assembled, base)  # 无 delta：原样返回，无拷贝
        self.assertFalse(assembled.photo.enabled)
        self.assertIsNone(assembled.photo.floating)
        self.assertIsNone(assembled.photo.border)

    # -- Test 2：仅 photo 被替换 --------------------------------------------
    def test_02_delta_replaces_only_photo_node(self):
        base = build_p3_spec()
        delta = fictional_floating_photo(base.photo)

        assembled = assemble_job_spec(base, photo_delta=delta)

        self.assertEqual(assembled.photo, delta)
        self.assertIsNot(assembled, base)
        # 除 photo 外的 12 个一级节点身份必须保持（浅拷贝共享，值自然不变）
        for f in fields(base):
            if f.name == "photo":
                continue
            self.assertIs(
                getattr(assembled, f.name), getattr(base, f.name),
                msg=f"非 photo 节点被意外复制/修改：{f.name}")

    # -- Test 3：基线不被 mutation ------------------------------------------
    def test_03_base_spec_is_not_mutated(self):
        base = build_p3_spec()
        delta = fictional_floating_photo(base.photo)

        assembled = assemble_job_spec(base, photo_delta=delta)

        self.assertNotEqual(base.photo, assembled.photo)
        # 基线仍是 P3 preset 出厂状态
        self.assertFalse(base.photo.enabled)
        self.assertEqual(base.photo.position, "none")
        self.assertIsNone(base.photo.floating)
        self.assertIsNone(base.photo.border)
        # 装配结果携带本份决策
        self.assertTrue(assembled.photo.floating.enabled)
        self.assertEqual(assembled.photo.border.color.value, "#BFBFBF")

    # -- Test 3b：同一基线可反复装配出互不影响的多份 Spec -------------------
    def test_03b_repeated_assembly_from_same_base_independent(self):
        base = build_p3_spec()
        d1 = fictional_floating_photo(base.photo,
                                      offset_x_cm=Sourced.kv1(0.5, "cm"))
        d2 = fictional_floating_photo(base.photo,
                                      offset_x_cm=Sourced.kv1(3.0, "cm"))
        s1 = assemble_job_spec(base, photo_delta=d1)
        s2 = assemble_job_spec(base, photo_delta=d2)
        self.assertEqual(s1.photo.floating.offset_x_cm.value, 0.5)
        self.assertEqual(s2.photo.floating.offset_x_cm.value, 3.0)
        self.assertIsNone(base.photo.floating)

    # -- Test 4：非法参数由现有 Validator 拦截（装配层不复制校验）-----------
    def test_04_invalid_assembled_spec_caught_by_validator(self):
        # 4a 非法水平锚点
        base = build_p3_spec()
        bad_anchor = fictional_floating_photo(base.photo, position_h="table")
        assembled = assemble_job_spec(base, photo_delta=bad_anchor)
        result = validate_spec(assembled)
        self.assertFalse(result.valid)
        self.assertIn(RULE_PHOTO_FLOATING, _error_rule_ids(result))

        # 4b 非法边框颜色（缺 #）
        base = build_p3_spec()
        bad_border = replace(
            fictional_floating_photo(base.photo),
            border=PhotoBorder(Sourced.kv1("BFBFBF"),
                               Sourced.kv1(2.25, "pt")))
        result = validate_spec(
            assemble_job_spec(base, photo_delta=bad_border))
        self.assertFalse(result.valid)
        self.assertIn(RULE_PHOTO_BORDER, _error_rule_ids(result))

        # 4c 负偏移
        base = build_p3_spec()
        bad_offset = fictional_floating_photo(
            base.photo, offset_x_cm=Sourced.kv1(-0.01, "cm"))
        result = validate_spec(
            assemble_job_spec(base, photo_delta=bad_offset))
        self.assertFalse(result.valid)
        self.assertIn(RULE_PHOTO_FLOATING, _error_rule_ids(result))

    def test_04b_valid_assembled_spec_passes_validator(self):
        """合法虚构参数（任务书示例 1.0/2.0/#BFBFBF/2.25pt）必须通过。"""
        base = build_p3_spec()
        assembled = assemble_job_spec(
            base, photo_delta=fictional_floating_photo(base.photo))
        result = validate_spec(assembled)
        self.assertTrue(
            result.valid,
            msg="合法装配结果不应有 ERROR:\n"
                + "\n".join(e.render() for e in result.errors))

    # -- Test 4c：floating/border 子节点「提供才覆盖」-----------------------
    def test_04c_sub_nodes_only_override_when_provided(self):
        base = build_p3_spec()
        # 只挂 floating（且只给 enabled），不挂 border
        photo = replace(
            base.photo, enabled=True,
            position="header_top_right_floating",
            width=Sourced.kv1(2.212, "cm"),
            height=Sourced.kv1(3.156, "cm"),
            aspect_ratio=Sourced.kv1(0.70, "ratio"),
            container="floating_anchored_no_fill",
            floating=PhotoFloating(enabled=True),  # 其余走 frozen 默认
        )
        assembled = assemble_job_spec(base, photo_delta=photo)
        self.assertTrue(assembled.photo.floating.enabled)
        self.assertEqual(assembled.photo.floating.position_h, "column")
        self.assertEqual(assembled.photo.floating.position_v, "page")
        self.assertIsNone(assembled.photo.floating.offset_x_cm)
        self.assertIsNone(assembled.photo.border)  # 未提供 → 保持无边框

    # -- Test 5：端到端进入 build_document(design_spec=...) -----------------
    def test_05_assembled_spec_renders_end_to_end(self):
        from docx import Document
        from docx.oxml.ns import qn

        tmp = Path(tempfile.mkdtemp(prefix="assembly_e2e_"))
        png = write_png(tmp / "fictional_id.png", 100, 143)

        base = build_p3_spec()
        assembled = assemble_job_spec(
            base, photo_delta=fictional_floating_photo(base.photo))
        # 渲染路径自身也会强制校验；这里先显式走一遍边界
        self.assertTrue(validate_spec(assembled).valid)

        doc = build_document(fake_blocks(photo_path=str(png)),
                             design_spec=assembled)

        anchors = doc.element.body.findall(".//" + qn("wp:anchor"))
        self.assertEqual(len(anchors), 1, msg="浮动照片应产出 1 个 wp:anchor")
        self.assertEqual(len(doc.inline_shapes), 0,
                         msg="浮动路径不应再保留 wp:inline 照片")
        anchor = anchors[0]
        self.assertEqual(
            anchor.find(qn("wp:positionH")).get("relativeFrom"), "column")
        self.assertEqual(
            anchor.find(qn("wp:positionV")).get("relativeFrom"), "page")
        # 可落盘并重开（XML 良构）
        out = tmp / "assembled_floating.docx"
        doc.save(str(out))
        Document(str(out))
        self.assertGreater(out.stat().st_size, 10000)

    # -- Test 6：类型边界 ----------------------------------------------------
    def test_06_type_guards(self):
        base = build_p3_spec()
        with self.assertRaises(TypeError):
            assemble_job_spec(object())
        with self.assertRaises(TypeError):
            # 禁止用 dict / 新配置类型绕过 PhotoSpec 节点
            assemble_job_spec(base, photo_delta={"enabled": True})
        with self.assertRaises(TypeError):
            assemble_job_spec(base, photo_delta="floating")

    # -- Test 7：范式无关性 + 公开导出 --------------------------------------
    def test_07_works_on_other_paradigms_and_public_export(self):
        import resume_generator.design as design_pkg
        self.assertIs(design_pkg.assemble_job_spec, assemble_job_spec)
        self.assertIn("assemble_job_spec", design_pkg.__all__)

        p1 = build_p1_spec()
        delta = replace(p1.photo,
                        floating=PhotoFloating(enabled=True),
                        border=PhotoBorder(Sourced.kv1("#BFBFBF"),
                                           Sourced.kv1(2.25, "pt")))
        assembled = assemble_job_spec(p1, photo_delta=delta)
        self.assertTrue(assembled.photo.floating.enabled)
        self.assertIsNone(p1.photo.floating)  # P1 preset 出厂值不动

    # ==================================================================
    # Step 7-G：新增 delta 入口测试
    # ==================================================================

    # -- Test 8：只传 typography_delta -----------------------------------
    def test_08_typography_delta_only(self):
        base = build_p3_spec()
        delta = compact_typography(base.typography, body=1.08, title=1.05)

        assembled = assemble_job_spec(base, typography_delta=delta)

        # 行距 delta 进入返回 Spec
        self.assertEqual(assembled.typography.line_spacing.body.value, 1.08)
        self.assertEqual(assembled.typography.line_spacing.title.value, 1.05)
        # 其余一级节点保持基线身份
        self.assertIs(assembled.section, base.section)
        self.assertIs(assembled.experience, base.experience)
        self.assertIs(assembled.photo, base.photo)

    # -- Test 9：只传 section_delta --------------------------------------
    def test_09_section_delta_only(self):
        base = build_p3_spec()
        delta = compact_section(base.section, spacing_before=5,
                                divider_to_first_line=3)

        assembled = assemble_job_spec(base, section_delta=delta)

        self.assertEqual(assembled.section.spacing_before.value, 5)
        self.assertEqual(assembled.section.divider_to_first_line.value, 3)
        self.assertIs(assembled.typography, base.typography)
        self.assertIs(assembled.experience, base.experience)
        self.assertIs(assembled.photo, base.photo)

    # -- Test 10：只传 experience_delta ----------------------------------
    def test_10_experience_delta_only(self):
        base = build_p3_spec()
        delta = compact_experience(base.experience, entry_spacing=3,
                                   bullet_after=1.5)

        assembled = assemble_job_spec(base, experience_delta=delta)

        self.assertEqual(assembled.experience.entry_spacing.value, 3)
        self.assertEqual(assembled.experience.bullet_spacing_after.value, 1.5)
        self.assertIs(assembled.typography, base.typography)
        self.assertIs(assembled.section, base.section)
        self.assertIs(assembled.photo, base.photo)

    # -- Test 11：photo + typography + section + experience 组合 ---------
    def test_11_all_four_deltas_combined(self):
        base = build_p3_spec()

        assembled = assemble_job_spec(
            base,
            photo_delta=fictional_floating_photo(base.photo),
            typography_delta=compact_typography(base.typography),
            section_delta=compact_section(base.section),
            experience_delta=compact_experience(base.experience),
        )

        # 四类 delta 均生效
        self.assertTrue(assembled.photo.floating.enabled)
        self.assertEqual(assembled.typography.line_spacing.body.value, 1.08)
        self.assertEqual(assembled.section.spacing_before.value, 5)
        self.assertEqual(assembled.experience.entry_spacing.value, 3)
        self.assertEqual(assembled.experience.bullet_spacing_after.value, 1.5)
        # 未被替换的节点保持基线身份
        self.assertIs(assembled.page, base.page)
        self.assertIs(assembled.colors, base.colors)
        self.assertIs(assembled.grid, base.grid)

    # -- Test 12：非 photo delta 时 base_spec 不被 mutation ---------------
    def test_12_base_unchanged_with_other_deltas(self):
        base = build_p3_spec()
        # 快照基线四个目标节点的值
        ls_body = base.typography.line_spacing.body.value
        sec_before = base.section.spacing_before.value
        ent_spacing = base.experience.entry_spacing.value
        photo_enabled = base.photo.enabled

        assemble_job_spec(
            base,
            typography_delta=compact_typography(base.typography),
            section_delta=compact_section(base.section),
            experience_delta=compact_experience(base.experience),
        )

        # 基线完全不变
        self.assertEqual(base.typography.line_spacing.body.value, ls_body)
        self.assertEqual(base.section.spacing_before.value, sec_before)
        self.assertEqual(base.experience.entry_spacing.value, ent_spacing)
        self.assertEqual(base.photo.enabled, photo_enabled)
        self.assertFalse(base.photo.enabled)

    # -- Test 13：重复 Assembly 相互独立 ---------------------------------
    def test_13_repeated_assembly_independent(self):
        base = build_p3_spec()

        spec_a = assemble_job_spec(
            base,
            typography_delta=compact_typography(base.typography, body=1.08),
        )
        spec_b = assemble_job_spec(
            base,
            typography_delta=compact_typography(base.typography, body=1.3),
        )

        self.assertEqual(spec_a.typography.line_spacing.body.value, 1.08)
        self.assertEqual(spec_b.typography.line_spacing.body.value, 1.3)
        # 基线不受任何一次装配影响
        self.assertEqual(base.typography.line_spacing.body.value, 1.4)

    # -- Test 14：非 photo delta 类型边界 --------------------------------
    def test_14_type_guards_for_new_deltas(self):
        base = build_p3_spec()
        with self.assertRaises(TypeError):
            assemble_job_spec(base, typography_delta={"line_spacing": 1.0})
        with self.assertRaises(TypeError):
            assemble_job_spec(base, section_delta="compact")
        with self.assertRaises(TypeError):
            assemble_job_spec(base, experience_delta=object())

    # -- Test 15：仅非 photo delta 也能通过 validator --------------------
    def test_15_non_photo_deltas_pass_validator(self):
        base = build_p3_spec()
        assembled = assemble_job_spec(
            base,
            typography_delta=compact_typography(base.typography),
            section_delta=compact_section(base.section),
            experience_delta=compact_experience(base.experience),
        )
        result = validate_spec(assembled)
        self.assertTrue(
            result.valid,
            msg="合法密度 delta 不应产生 ERROR:\n"
                + "\n".join(e.render() for e in result.errors))


if __name__ == "__main__":
    unittest.main(verbosity=2)
