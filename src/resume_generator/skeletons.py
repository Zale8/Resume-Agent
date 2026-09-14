# -*- coding: utf-8 -*-
"""三种可复用简历骨架。内容由调用方传入 ResumeBlocks，本文件不含个人事实。

选用规则：
    - 先定骨架 ID，再定色板。禁止「沿用上一份公司脚本、只改强调色」。
    - 核心板块顺序固定：个人信息 → 教育 → 实习 → 项目（次要板块可调）。
    - 正文不得低于 layout_kit.MIN_BODY_PT。
"""
from __future__ import annotations

from typing import Optional

from resume_generator.layout_kit import (
    A4_WIDTH_CM,
    FONT_CN,
    MIN_BODY_PT,
    PALETTES,
    Palette,
    ResumeBlocks,
    SKELETON_BANNER,
    SKELETON_MINIMAL,
    SKELETON_SIDEBAR,
    add_hairline,
    add_text,
    clear_table_borders,
    hex_rgb,
    insert_photo,
    set_cell_margins,
    set_cell_width,
    set_paragraph_spacing,
    set_run_font,
    set_table_fixed_layout,
    setup_a4,
    shade_cell,
)


def resolve_palette(palette_id: Optional[str], skeleton_id: str) -> Palette:
    from resume_generator.layout_kit import DEFAULT_PALETTE_FOR_SKELETON

    pid = palette_id or DEFAULT_PALETTE_FOR_SKELETON[skeleton_id]
    if pid not in PALETTES:
        raise KeyError(f"未知色板 {pid}，可选：{list(PALETTES)}")
    return PALETTES[pid]


def build_document(blocks: ResumeBlocks, skeleton_id: str, palette_id: Optional[str] = None):
    """按骨架构建 Document。调用方负责保存。"""
    builders = {
        SKELETON_BANNER: build_banner_card,
        SKELETON_MINIMAL: build_minimal,
        SKELETON_SIDEBAR: build_sidebar,
    }
    if skeleton_id not in builders:
        raise KeyError(f"未知骨架 {skeleton_id}，可选：{list(builders)}")
    return builders[skeleton_id](blocks, resolve_palette(palette_id, skeleton_id))


def build_banner_card(blocks: ResumeBlocks, palette: Palette):
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt

    doc = Document()
    setup_a4(doc, margins_cm=(0.55, 0.55, 1.0, 1.0))
    _set_doc_default_font(doc)

    table = doc.add_table(rows=1, cols=2)
    clear_table_borders(table)
    set_table_fixed_layout(table, A4_WIDTH_CM - 1.1 - 1.1, [8.4, 10.4])
    left, right = table.rows[0].cells
    shade_cell(left, palette.header)
    shade_cell(right, palette.header)
    set_cell_width(left, 8.4)
    set_cell_width(right, 10.4)
    set_cell_margins(left, top=0.25, bottom=0.25, left=0.35, right=0.2)
    set_cell_margins(right, top=0.2, bottom=0.2, left=0.1, right=0.25)

    p = left.paragraphs[0]
    set_paragraph_spacing(p, before=0, after=2, line=1.05)
    add_text(p, blocks.name, 18, bold=True, color="#FFFFFF")
    p2 = left.add_paragraph()
    set_paragraph_spacing(p2, before=0, after=4, line=1.05)
    add_text(p2, blocks.intent, 10.5, bold=True, color="#F7DC6F")
    for line in blocks.contact_lines:
        cp = left.add_paragraph()
        set_paragraph_spacing(cp, before=0, after=0, line=1.05)
        add_text(cp, line, 9, color="#EAECEE")

    rp = right.paragraphs[0]
    rp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    set_paragraph_spacing(rp, before=0, after=0, line=1.0)
    insert_photo(rp, blocks.photo_path, 1.85, 2.4)

    # 强调色条
    bar = doc.add_paragraph()
    set_paragraph_spacing(bar, before=0, after=8, line=0.4)
    _bottom_border(bar, palette.accent, sz="18")

    if blocks.summary:
        _section_title(doc, "个人优势", palette, numbered=False)
        sp = doc.add_paragraph()
        set_paragraph_spacing(sp, before=0, after=6, line=1.08)
        add_text(sp, blocks.summary, 9.5, color=palette.ink)

    _education(doc, blocks, palette)
    _experience_section(doc, "实习经历", blocks.internships, palette)
    _experience_section(doc, "项目经历", blocks.projects, palette)
    if blocks.campus:
        _bullet_section(doc, "校园经历", blocks.campus, palette)
    _skills_certs(doc, blocks, palette)
    _ = (qn, Cm, Pt, WD_ALIGN_PARAGRAPH)
    return doc


def build_minimal(blocks: ResumeBlocks, palette: Palette):
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Cm, Pt, Twips

    doc = Document()
    setup_a4(doc, margins_cm=(0.7, 0.7, 1.25, 1.25))
    _set_doc_default_font(doc)

    head = doc.add_table(rows=1, cols=2)
    clear_table_borders(head)
    # 页边距左右各 1.5cm
    set_table_fixed_layout(head, A4_WIDTH_CM - 1.5 - 1.5, [13.0, 5.0])
    c0, c1 = head.rows[0].cells
    set_cell_width(c0, 13.0)
    set_cell_width(c1, 5.0)
    p = c0.paragraphs[0]
    set_paragraph_spacing(p, before=0, after=0, line=1.05)
    add_text(p, blocks.name, 20, bold=True, color=palette.ink)
    p2 = c0.add_paragraph()
    set_paragraph_spacing(p2, before=2, after=4, line=1.05)
    add_text(p2, blocks.intent, 11, color=palette.accent, bold=True)
    for line in blocks.contact_lines:
        cp = c0.add_paragraph()
        set_paragraph_spacing(cp, before=0, after=0, line=1.05)
        add_text(cp, line, 9, color=palette.muted)

    rp = c1.paragraphs[0]
    rp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    insert_photo(rp, blocks.photo_path, 1.85, 2.4)

    rule = doc.add_paragraph()
    set_paragraph_spacing(rule, before=4, after=7, line=0.5)
    _bottom_border(rule, palette.accent, sz="12")

    idx = 1
    if blocks.summary:
        _numbered_title(doc, idx, "个人优势", palette)
        idx += 1
        sp = doc.add_paragraph()
        set_paragraph_spacing(sp, before=0, after=6, line=1.06)
        add_text(sp, blocks.summary, 9.5, color=palette.ink)

    _numbered_title(doc, idx, "教育经历", palette)
    idx += 1
    for line in blocks.education_lines:
        ep = doc.add_paragraph()
        set_paragraph_spacing(ep, before=0, after=4, line=1.06)
        add_text(ep, line, 9.5, color=palette.ink)

    if blocks.internships:
        _numbered_title(doc, idx, "实习经历", palette)
        idx += 1
        _experience_blocks_minimal(doc, blocks.internships, palette)

    if blocks.projects:
        _numbered_title(doc, idx, "项目经历", palette)
        idx += 1
        _experience_blocks_minimal(doc, blocks.projects, palette)

    if blocks.campus:
        _numbered_title(doc, idx, "校园经历", palette)
        idx += 1
        for item in blocks.campus:
            _body_bullet(doc, item, palette, size=9.5)

    _numbered_title(doc, idx, "专业技能与证书", palette)
    for s in blocks.skills:
        _body_bullet(doc, s, palette, size=9.5)
    if blocks.certs:
        cp = doc.add_paragraph()
        set_paragraph_spacing(cp, before=2, after=0, line=1.06)
        add_text(cp, "证书资质  ", 9.5, bold=True, color=palette.ink)
        add_text(cp, "  ·  ".join(blocks.certs), 9.5, color=palette.ink)
    _ = (Cm, Pt, Twips)
    return doc


def build_sidebar(blocks: ResumeBlocks, palette: Palette):
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.shared import Cm, Emu

    doc = Document()
    setup_a4(doc, margins_cm=(0.8, 0.8, 0.8, 0.8))
    _set_doc_default_font(doc)

    table = doc.add_table(rows=1, cols=2)
    clear_table_borders(table)
    # 页边距左右各 0.8cm，可用宽 = A4宽 - 1.6
    set_table_fixed_layout(table, A4_WIDTH_CM - 0.8 - 0.8, [5.9, 13.5])
    left, right = table.rows[0].cells
    # 约 32% / 68%，显式写 tcW 才会生效
    set_cell_width(left, 5.9)
    set_cell_width(right, 13.5)
    shade_cell(left, palette.rule)
    set_cell_margins(left, top=0.3, bottom=0.3, left=0.28, right=0.28)
    set_cell_margins(right, top=0.2, bottom=0.2, left=0.4, right=0.2)

    lp = left.paragraphs[0]
    lp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    insert_photo(lp, blocks.photo_path, 3.2, 4.0)

    np = left.add_paragraph()
    np.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_paragraph_spacing(np, before=8, after=2, line=1.05)
    add_text(np, blocks.name, 14, bold=True, color=palette.header)

    ip = left.add_paragraph()
    ip.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_paragraph_spacing(ip, before=0, after=8, line=1.05)
    add_text(ip, blocks.intent, 8.5, color=palette.accent, bold=True)

    _side_label(left, "联系方式", palette)
    for line in blocks.contact_lines:
        cp = left.add_paragraph()
        set_paragraph_spacing(cp, before=0, after=1, line=1.05)
        add_text(cp, line, 8.5, color=palette.ink)

    if blocks.skills:
        _side_label(left, "专业技能", palette)
        for s in blocks.skills:
            sp = left.add_paragraph()
            set_paragraph_spacing(sp, before=0, after=2, line=1.05)
            add_text(sp, "· " + s, 8.5, color=palette.ink)

    if blocks.certs:
        _side_label(left, "证书", palette)
        for c in blocks.certs:
            cp = left.add_paragraph()
            set_paragraph_spacing(cp, before=0, after=1, line=1.05)
            add_text(cp, "· " + c, 8.5, color=palette.ink)

    if blocks.summary:
        _main_title(right, "个人优势", palette)
        sp = right.add_paragraph()
        set_paragraph_spacing(sp, before=0, after=6, line=1.08)
        add_text(sp, blocks.summary, 9.5, color=palette.ink)

    _main_title(right, "教育经历", palette)
    for line in blocks.education_lines:
        ep = right.add_paragraph()
        set_paragraph_spacing(ep, before=0, after=4, line=1.08)
        add_text(ep, line, 9.5, color=palette.ink)

    if blocks.internships:
        _main_title(right, "实习经历", palette)
        _experience_in_cell(right, blocks.internships, palette)

    if blocks.projects:
        _main_title(right, "项目经历", palette)
        _experience_in_cell(right, blocks.projects, palette)

    if blocks.campus:
        _main_title(right, "校园经历", palette)
        for item in blocks.campus:
            bp = right.add_paragraph()
            set_paragraph_spacing(bp, before=0, after=2, line=1.08)
            add_text(bp, "· " + item, 9.5, color=palette.ink)

    _ = (qn, Emu, MIN_BODY_PT)
    return doc


# ---- internals -------------------------------------------------------------

def _set_doc_default_font(doc):
    style = doc.styles["Normal"]
    style.font.name = FONT_CN
    style.font.size = _pt(10)
    from docx.oxml.ns import qn

    style.element.rPr.rFonts.set(qn("w:eastAsia"), FONT_CN)


def _pt(n):
    from docx.shared import Pt

    return Pt(n)


def _bottom_border(paragraph, color: str, sz="8"):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    pPr = paragraph._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), sz)
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), color.lstrip("#"))
    pBdr.append(bottom)
    pPr.append(pBdr)


def _section_title(doc, text, palette: Palette, numbered=False):
    p = doc.add_paragraph()
    set_paragraph_spacing(p, before=5, after=1, line=1.0)
    add_text(p, ("▍ " if not numbered else "") + text, 12, bold=True, color=palette.ink)
    add_hairline(doc, palette.rule)


def _numbered_title(doc, n: int, text: str, palette: Palette):
    p = doc.add_paragraph()
    set_paragraph_spacing(p, before=5, after=1, line=1.0)
    add_text(p, f"{n:02d}  ", 12, bold=True, color=palette.accent)
    add_text(p, text, 12, bold=True, color=palette.ink)
    add_hairline(doc, palette.rule)


def _education(doc, blocks: ResumeBlocks, palette: Palette):
    _section_title(doc, "教育经历", palette)
    for line in blocks.education_lines:
        p = doc.add_paragraph()
        set_paragraph_spacing(p, before=0, after=4, line=1.08)
        add_text(p, line, 9.5, color=palette.ink)


def _experience_section(doc, title, items, palette: Palette):
    if not items:
        return
    _section_title(doc, title, palette)
    for item in items:
        hp = doc.add_paragraph()
        set_paragraph_spacing(hp, before=2, after=1, line=1.05)
        add_text(hp, item.title, 10.5, bold=True, color=palette.ink)
        if item.role:
            add_text(hp, "  ·  " + item.role, 10, bold=True, color=palette.accent)
        if item.meta:
            add_text(hp, "    " + item.meta, 9, color=palette.muted)
        if item.tags:
            tp = doc.add_paragraph()
            set_paragraph_spacing(tp, before=0, after=1, line=1.0)
            add_text(tp, item.tags, 8.5, color=palette.muted)
        for b in item.bullets:
            _body_bullet(doc, b, palette, size=9.5)


def _experience_blocks_minimal(doc, items, palette: Palette):
    for item in items:
        hp = doc.add_paragraph()
        set_paragraph_spacing(hp, before=3, after=1, line=1.05)
        add_text(hp, item.title, 10.5, bold=True, color=palette.ink)
        if item.role:
            add_text(hp, "  " + item.role, 10, bold=True, color=palette.accent)
        if item.meta:
            add_text(hp, "    " + item.meta, 9, color=palette.muted)
        for b in item.bullets:
            _body_bullet(doc, b, palette, size=9.5)


def _experience_in_cell(cell, items, palette: Palette):
    for item in items:
        hp = cell.add_paragraph()
        set_paragraph_spacing(hp, before=2, after=1, line=1.05)
        add_text(hp, item.title, 10.5, bold=True, color=palette.ink)
        if item.role:
            add_text(hp, "  ·  " + item.role, 10, bold=True, color=palette.accent)
        if item.meta:
            add_text(hp, "    " + item.meta, 9, color=palette.muted)
        for b in item.bullets:
            bp = cell.add_paragraph()
            set_paragraph_spacing(bp, before=0, after=1, line=1.06)
            add_text(bp, "· " + b, 9.5, color=palette.ink)


def _bullet_section(doc, title, items, palette: Palette):
    _section_title(doc, title, palette)
    for item in items:
        _body_bullet(doc, item, palette, size=9.5)


def _skills_certs(doc, blocks: ResumeBlocks, palette: Palette):
    if not blocks.skills and not blocks.certs:
        return
    _section_title(doc, "专业技能 / 证书", palette)
    for s in blocks.skills:
        _body_bullet(doc, s, palette, size=9.5)
    if blocks.certs:
        p = doc.add_paragraph()
        set_paragraph_spacing(p, before=2, after=0, line=1.08)
        add_text(p, "证书  ", 9.5, bold=True, color=palette.ink)
        add_text(p, "  ·  ".join(blocks.certs), 9.5, color=palette.ink)


def _body_bullet(doc, text, palette: Palette, size=9.5):
    p = doc.add_paragraph()
    set_paragraph_spacing(p, before=0, after=1.5, line=1.08)
    add_text(p, "· " + text, max(size, MIN_BODY_PT), color=palette.ink)


def _side_label(cell, text, palette: Palette):
    p = cell.add_paragraph()
    set_paragraph_spacing(p, before=10, after=3, line=1.0)
    add_text(p, text.upper() if text.isascii() else text, 9, bold=True, color=palette.header)
    _bottom_border(p, palette.accent, sz="8")


def _main_title(cell, text, palette: Palette):
    p = cell.add_paragraph()
    set_paragraph_spacing(p, before=6, after=2, line=1.0)
    add_text(p, "▍ " + text, 12, bold=True, color=palette.ink)
    _bottom_border(p, palette.rule, sz="6")
