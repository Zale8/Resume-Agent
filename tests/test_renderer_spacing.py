# -*- coding: utf-8 -*-
"""test_renderer_spacing.py — Phase 3B-3 Spacing / 间距 Spec 驱动接线回归。

验证：
    T1 Spacing Resolver：P1/P2 DesignSpec 的间距字段正确进入 RenderStyle.spacing。
    T2 Spec 缺失（None）→ 骨架 Profile fallback，登记 <not_defined>。
    T3 Spec undetermined → 骨架 Profile fallback，登记裸键名。
    T4 真实 DOCX XML 的 w:spacing before/after 与 RenderStyle 一致（twips 量化）。
    T5 真实 DOCX XML 的 w:tcMar（cell margin）与 RenderStyle 一致（dxa 量化）。
    T6 divider 厚度 w:pBdr/@w:sz（1/8pt）与 RenderStyle 一致。
    T7 旧路径 build_document(blocks, skeleton_id) 三骨架继续产出。
    T8/T9/T10 Typography / Palette / Stability 回归套件继续全绿（子进程）。
    另含源码守卫：skeletons.py 执行层不得再出现 spacing 数值硬编码。

简历数据全部虚构（张三）；Document 只在内存构建，不写用户数据目录。
用法：python tests/test_renderer_spacing.py
"""
from __future__ import annotations

import io
import subprocess
import sys
import tokenize
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from docx.oxml.ns import qn  # noqa: E402
from docx.shared import Cm  # noqa: E402

from resume_generator.design.spec import Sourced  # noqa: E402
from resume_generator.layout_kit import (  # noqa: E402
    BulletBlock,
    ResumeBlocks,
)
from resume_generator.render_style import (  # noqa: E402
    SKELETON_DEFAULT_STYLE,
    resolve_style_for_spec,
)
from resume_generator.skeletons import (  # noqa: E402
    SKELETON_BANNER,
    SKELETON_MINIMAL,
    SKELETON_SIDEBAR,
    build_document,
    resolve_palette,
)


# ---------------------------------------------------------------------------
# 虚构夹具（与 palette/typography 套件同口径，BulletBlock 一律关键字构造）
# ---------------------------------------------------------------------------

def fake_blocks():
    return ResumeBlocks(
        name="张三",
        intent="测试岗位",
        contact_lines=["138-0000-0000", "zhangsan@example.com"],
        summary="虚构的个人优势简介，用于间距接线测试。",
        education_lines=["XX大学  测试专业（本科）    2023.09 - 2027.06"],
        internships=[
            BulletBlock(
                title="某某有限公司",
                role="测试实习生",
                meta="2025.06 - 2025.09",
                tags="标签甲 · 标签乙",
                bullets=["完成了一项虚构的测试工作。"],
            )
        ],
        projects=[],
        campus=["虚构校园经历甲"],
        skills=["技能甲", "技能乙"],
        certs=["虚构证书甲"],
    )


def resolve_spec_style(spec, sk):
    """与 _build_from_spec 同口径地解析 RenderStyle（含 spacing）。"""
    return resolve_style_for_spec(
        spec, SKELETON_DEFAULT_STYLE[sk], sk, resolve_palette(None, sk))


# ---------------------------------------------------------------------------
# DOCX XML 读取 helper（只观察，不修改）
# ---------------------------------------------------------------------------

def spacing_of_para(p):
    """返回 (before_twips, after_twips)；缺失属性为 None。"""
    pPr = p._p.find(qn("w:pPr"))
    if pPr is None:
        return None, None
    spacing = pPr.find(qn("w:spacing"))
    if spacing is None:
        return None, None
    before = spacing.get(qn("w:before"))
    after = spacing.get(qn("w:after"))
    return (int(before) if before is not None else None,
            int(after) if after is not None else None)


def border_sz_of_para(p):
    pPr = p._p.find(qn("w:pPr"))
    if pPr is None:
        return None
    pBdr = pPr.find(qn("w:pBdr"))
    if pBdr is None:
        return None
    bottom = pBdr.find(qn("w:bottom"))
    return None if bottom is None else bottom.get(qn("w:sz"))


def cell_margins(cell):
    """返回 {top,bottom,left,right: twips}；无 tcMar 返回 {}。"""
    tcPr = cell._tc.find(qn("w:tcPr"))
    if tcPr is None:
        return {}
    tcMar = tcPr.find(qn("w:tcMar"))
    if tcMar is None:
        return {}
    out = {}
    for side in ("top", "bottom", "left", "right"):
        node = tcMar.find(qn(f"w:{side}"))
        if node is not None:
            out[side] = int(node.get(qn("w:w")))
    return out


def find_para_index(doc, fragment):
    for i, p in enumerate(doc.paragraphs):
        if fragment in p.text:
            return i
    raise AssertionError(f"未找到包含 {fragment!r} 的正文段落")


# ===========================================================================
# 测试
# ===========================================================================

class TestRendererSpacing(unittest.TestCase):

    # -- Test 1：Spec spacing → RenderStyle.spacing -------------------------
    def test_01_spec_spacing_resolves_to_renderstyle(self):
        from resume_generator.design import build_p1_spec, build_p2_spec

        # --- P1（banner 范式）---
        sp = resolve_spec_style(build_p1_spec(), SKELETON_BANNER).spacing
        # Spec 明确值（pt）
        self.assertEqual(sp.section_before, 22.0)      # section.spacing_before
        self.assertEqual(sp.hairline_after, 6.0)       # divider_to_first_line
        self.assertEqual(sp.entry_before, 20.0)        # experience.entry_spacing
        self.assertEqual(sp.bullet_after, 6.0)         # bullet_spacing_after
        # 边框厚度：pt → OOXML 1/8pt（P1 Phase 2B-1 修正：divider 0.0*8=0；
        # 身份区色条 2.16*8=17.28→17）
        self.assertEqual(sp.hairline_sz, 0)
        self.assertEqual(sp.bar_sz, 17)
        # Spec 无此设计概念 → 保留骨架 Profile（banner 审计原值）
        self.assertEqual(sp.title_after, 1)
        self.assertEqual(sp.entry_after, 1)
        self.assertEqual(sp.bullet_before, 0)
        self.assertEqual(sp.bar_after, 8)

        # --- P2（sidebar 范式）---
        sp2 = resolve_spec_style(build_p2_spec(), SKELETON_SIDEBAR).spacing
        self.assertEqual(sp2.section_before, 20.0)
        self.assertEqual(sp2.hairline_after, 6.0)
        self.assertEqual(sp2.hairline_sz, 4)
        self.assertEqual(sp2.entry_before, 20.0)
        self.assertEqual(sp2.bullet_after, 8.0)        # P2 medium 档
        # sidebar cell margin 是永久 Profile（Schema Gap），值必须逐值保值
        self.assertEqual(sp2.cell_left_cm, (0.3, 0.3, 0.28, 0.28))
        self.assertEqual(sp2.cell_right_cm, (0.2, 0.2, 0.4, 0.2))

    # -- Test 2：Spec 缺失（None）→ Profile fallback + not_defined ----------
    def test_02_missing_spacing_falls_back_with_log(self):
        from resume_generator.design import build_p1_spec
        spec = build_p1_spec()
        spec = replace(
            spec,
            section=replace(spec.section, spacing_before=None))
        st = resolve_spec_style(spec, SKELETON_BANNER)
        # banner Profile section_before=5
        self.assertEqual(st.spacing.section_before, 5)
        self.assertIn("spacing.section_before<not_defined>",
                      st.spec_fallbacks)
        # 同 Spec 内其它已定义间距不受影响
        self.assertEqual(st.spacing.hairline_after, 6.0)

    # -- Test 3：Spec undetermined → Profile fallback + 裸键登记 ------------
    def test_03_undetermined_spacing_falls_back_with_log(self):
        from resume_generator.design import build_p1_spec
        spec = build_p1_spec()
        spec = replace(
            spec,
            section=replace(
                spec.section,
                spacing_before=Sourced.undetermined("测试用：板块间距知识缺口")))
        st = resolve_spec_style(spec, SKELETON_BANNER)
        self.assertEqual(st.spacing.section_before, 5)
        # undetermined 登记裸键名（与 typography/colors 口径一致）
        self.assertIn("spacing.section_before", st.spec_fallbacks)
        self.assertNotIn("spacing.section_before<not_defined>",
                         st.spec_fallbacks)

    # -- Test 4：真实 XML w:spacing before/after ----------------------------
    def test_04_xml_paragraph_spacing_matches_renderstyle(self):
        from resume_generator.design import build_p1_spec
        spec = build_p1_spec()
        st = resolve_spec_style(spec, SKELETON_BANNER)
        d = build_document(fake_blocks(), design_spec=spec)

        # 板块标题段（"▍ 个人优势"）：before=22pt=440twips（Spec），
        # after=title_after Profile 1pt=20twips（Schema Gap fallback）
        i = find_para_index(d, "个人优势")
        title_p = d.paragraphs[i]
        before, after = spacing_of_para(title_p)
        self.assertEqual(before, round(st.spacing.section_before * 20))
        self.assertEqual(after, round(st.spacing.title_after * 20))

        # P-5：P1 divider.weight=0pt（hairline_sz=0）→ 不再创建独立 hairline
        # 空段。标题后紧邻段落是个人优势正文（非空、无 pBdr）。
        self.assertEqual(st.spacing.hairline_sz, 0)
        nxt_p = d.paragraphs[i + 1]
        self.assertNotEqual(nxt_p.text, "")
        self.assertIsNone(border_sz_of_para(nxt_p))
        self.assertIsNone(border_sz_of_para(title_p))

        # 经历 bullet 段：after=6pt（P1 bullet_spacing_after）
        j = find_para_index(d, "完成了一项虚构的测试工作")
        _, b_after = spacing_of_para(d.paragraphs[j])
        self.assertEqual(b_after, round(st.spacing.bullet_after * 20))

    # -- Test 5：真实 XML w:tcMar（cell margin）与 RenderStyle 一致 ---------
    def test_05_xml_cell_margins_match_renderstyle(self):
        # --- 旧路径 banner：Profile 四向 cm 值逐值保值（twips 取整量化）---
        d = build_document(fake_blocks(), SKELETON_BANNER, "tech_navy")
        st = SKELETON_DEFAULT_STYLE[SKELETON_BANNER]
        left, right = d.tables[0].rows[0].cells
        ml, mr = cell_margins(left), cell_margins(right)
        for side, cm_val in zip(("top", "bottom", "left", "right"),
                                st.spacing.cell_left_cm):
            self.assertEqual(ml[side], int(Cm(cm_val).twips))
        for side, cm_val in zip(("top", "bottom", "left", "right"),
                                st.spacing.cell_right_cm):
            self.assertEqual(mr[side], int(Cm(cm_val).twips))
        # 物理量级抽查：0.25cm≈142twips，0.35cm≈198twips，0.1cm≈57twips
        # （banner 左格 tuple 为 上0.25/下0.25/左0.35/右0.2）
        self.assertAlmostEqual(ml["top"], 142, delta=1)
        self.assertAlmostEqual(ml["left"], 198, delta=1)
        self.assertAlmostEqual(mr["left"], 57, delta=1)

        # --- sidebar 旧路径 ---
        d2 = build_document(fake_blocks(), SKELETON_SIDEBAR,
                            "manufacturing_steel")
        st2 = SKELETON_DEFAULT_STYLE[SKELETON_SIDEBAR]
        l2, r2 = d2.tables[0].rows[0].cells
        ml2, mr2 = cell_margins(l2), cell_margins(r2)
        for side, cm_val in zip(("top", "bottom", "left", "right"),
                                st2.spacing.cell_left_cm):
            self.assertEqual(ml2[side], int(Cm(cm_val).twips))
        for side, cm_val in zip(("top", "bottom", "left", "right"),
                                st2.spacing.cell_right_cm):
            self.assertEqual(mr2[side], int(Cm(cm_val).twips))
        self.assertAlmostEqual(ml2["top"], 170, delta=1)   # 0.3cm
        self.assertAlmostEqual(ml2["left"], 159, delta=1)  # 0.28cm

    # -- Test 6：divider 厚度 w:pBdr/@w:sz ----------------------------------
    def test_06_xml_divider_thickness_matches_renderstyle(self):
        # P1 Spec（Phase 2B-1 修正 + P-5）：发丝线 0.0pt = 禁用 → 不写任何
        # sz=0 的 w:pBdr；身份区色条 2.16pt→sz=17 保留（独立语义）
        from resume_generator.design import build_p1_spec
        spec = build_p1_spec()
        st = resolve_spec_style(spec, SKELETON_BANNER)
        self.assertEqual(st.spacing.hairline_sz, 0)
        d = build_document(fake_blocks(), design_spec=spec)
        sizes = {border_sz_of_para(p) for p in d.paragraphs}
        self.assertNotIn("0", sizes)                    # P-5：禁用即不写
        self.assertIn(str(st.spacing.bar_sz), sizes)   # "17"

        # 旧路径：发丝线 sz=6（审计原值），色条 sz=18（审计原值）
        d0 = build_document(fake_blocks(), SKELETON_BANNER, "tech_navy")
        sizes0 = [border_sz_of_para(p) for p in d0.paragraphs]
        self.assertIn("6", sizes0)
        self.assertIn("18", sizes0)

    # -- Test 7：旧路径三骨架继续产出 + 源码守卫 ----------------------------
    def test_07_legacy_paths_and_source_guard(self):
        for sid, pal in ((SKELETON_BANNER, "tech_navy"),
                         (SKELETON_MINIMAL, "minimal_ink"),
                         (SKELETON_SIDEBAR, "manufacturing_steel")):
            d = build_document(fake_blocks(), sid, pal)  # 旧式位置参数
            # sidebar 所有内容都在单元格内，body 级段落为 0，需合并计数
            total_ps = len(d.paragraphs) + sum(
                len(c.paragraphs)
                for t in d.tables for r in t.rows for c in r.cells)
            self.assertGreaterEqual(len(d.tables), 1)
            self.assertGreater(total_ps, 5)
        self._assert_no_spacing_literals_in_skeletons()

    @staticmethod
    def _assert_no_spacing_literals_in_skeletons():
        """tokenize 剥除 STRING/COMMENT 后扫描 skeletons.py：

        - before=/after=/before_pt=/after_pt= 的值禁止是数字字面量；
        - sz= 的值禁止是数字/字符串字面量（必须来自 RenderSpacing）；
        - 禁止再出现 "cell_margins" 字符串键（已迁至 RenderSpacing）。
        注意：line=1.0 / 0.4 / 0.5 属 Typography 行距（3B-1 保留值），不扫。
        """
        src_path = SRC / "resume_generator" / "skeletons.py"
        with tokenize.open(src_path) as f:
            toks = list(tokenize.generate_tokens(
                io.StringIO(f.read()).readline))
        bad = []
        spacing_kw = {"before", "after", "before_pt", "after_pt"}
        for i, tok in enumerate(toks):
            if tok.type != tokenize.NAME:
                continue
            nxt = toks[i + 1] if i + 1 < len(toks) else None
            val = toks[i + 2] if i + 2 < len(toks) else None
            if (nxt is not None and nxt.type == tokenize.OP
                    and nxt.string == "=" and val is not None):
                if tok.string in spacing_kw and val.type == tokenize.NUMBER:
                    bad.append((tok.start[0], f"{tok.string}={val.string}"))
                if tok.string == "sz" and val.type in (tokenize.NUMBER,
                                                       tokenize.STRING):
                    bad.append((tok.start[0], f"sz={val.string}"))
            if tok.type == tokenize.STRING:
                try:
                    if eval(tok.string) == "cell_margins":  # noqa: S307
                        bad.append((tok.start[0], '"cell_margins"'))
                except Exception:  # noqa: BLE001 - f-string/前缀串等直接跳过
                    pass
        assert not bad, f"skeletons.py 出现 spacing 硬编码：{bad}"

    # -- Test 8：Typography 回归 --------------------------------------------
    def test_08_typography_regression_suite(self):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "tests" /
                                 "test_renderer_typography.py")],
            cwd=str(ROOT), capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0,
                         msg=f"typography 回归失败：\n{proc.stdout}\n"
                             f"{proc.stderr}")

    # -- Test 9：Palette 回归 -----------------------------------------------
    def test_09_palette_regression_suite(self):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "tests" /
                                 "test_renderer_palette.py")],
            cwd=str(ROOT), capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0,
                         msg=f"palette 回归失败：\n{proc.stdout}\n"
                             f"{proc.stderr}")

    # -- Test 10：Renderer stability 回归 -----------------------------------
    def test_10_stability_regression_suite(self):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "tests" /
                                 "test_renderer_stability.py")],
            cwd=str(ROOT), capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0,
                         msg=f"stability 回归失败：\n{proc.stdout}\n"
                             f"{proc.stderr}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
