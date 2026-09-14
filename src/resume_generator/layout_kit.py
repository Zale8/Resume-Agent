# -*- coding: utf-8 -*-
"""layout_kit — 通用 DOCX 排版积木（不含任何个人事实、不含完整简历成品）。

v0.4 起，Agent 生成简历时必须复用本模块的页面 / 字体 / 色板 / 照片 / 间距原语，
再调用 skeletons 里的三种骨架。禁止复制上一份公司的生成脚本只改 RGB。

依赖：构建 DOCX 需要 python-docx（doctor 会检测）。本模块在未安装时仍可
被 import（色板与骨架元数据可用）；真正操作 Document 时再导入 docx。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# 骨架 ID（产品约定，与 agent_entry / 母版映射表一致）
# ---------------------------------------------------------------------------

SKELETON_SIDEBAR = "two_column_sidebar"
SKELETON_BANNER = "banner_card"
SKELETON_MINIMAL = "single_column_minimal"

SKELETONS = {
    SKELETON_SIDEBAR: {
        "name_zh": "双栏侧边栏式",
        "shape": "左窄栏（信息+照片+技能）/ 右宽栏经历，浅色块底",
        "use": "信息密度高、技能多的通用/技术岗、硬件制造岗",
        "photo": "侧边栏近方形",
    },
    SKELETON_BANNER: {
        "name_zh": "横幅工牌卡式",
        "shape": "顶部深色 Header（姓名+信息+照片）+ 白卡板块 + 成果色条",
        "use": "单岗位精准投递、品牌感行业（产品/运营/医药/消费）",
        "photo": "Header 右侧竖版",
    },
    SKELETON_MINIMAL: {
        "name_zh": "单栏极简编辑风",
        "shape": "纯白、1 字体族、黑+1 强调色、编号标题、量化数字前置",
        "use": "外企/大厂/ATS 严格场景",
        "photo": "右上小证件照",
    },
}

# ---------------------------------------------------------------------------
# 行业色板（不含任何公司品牌名；按岗位气质选用，不要「换色当新骨架」）
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Palette:
    id: str
    ink: str
    accent: str
    muted: str
    paper: str
    header: str
    rule: str


PALETTES = {
    "tech_navy": Palette(
        "tech_navy", "#1A1A1A", "#1B4F72", "#5D6D7E", "#FFFFFF", "#1B3A4B", "#D6EAF8"
    ),
    "pharma_teal": Palette(
        "pharma_teal", "#1A1A1A", "#0E6655", "#5D6D7E", "#F7FBFA", "#0B3D36", "#D5F5E3"
    ),
    "finance_gold": Palette(
        "finance_gold", "#1A1A1A", "#7D6608", "#6E6E6E", "#FFFCF5", "#2C2416", "#F9E79F"
    ),
    "education_warm": Palette(
        "education_warm", "#1A1A1A", "#B85C38", "#6D6D6D", "#FFF8F4", "#3D2B22", "#FAD7C7"
    ),
    "manufacturing_steel": Palette(
        "manufacturing_steel", "#1A1A1A", "#34495E", "#7F8C8D", "#F4F6F7", "#2C3E50", "#D5D8DC"
    ),
    "minimal_ink": Palette(
        "minimal_ink", "#111111", "#C0392B", "#8A8A8A", "#FFFFFF", "#111111", "#E0E0E0"
    ),
}

DEFAULT_PALETTE_FOR_SKELETON = {
    SKELETON_SIDEBAR: "manufacturing_steel",
    SKELETON_BANNER: "pharma_teal",
    SKELETON_MINIMAL: "minimal_ink",
}

FONT_CN = "微软雅黑"
MIN_BODY_PT = 9.0
A4_WIDTH_CM = 21.0
A4_HEIGHT_CM = 29.7


@dataclass
class BulletBlock:
    title: str
    meta: str = ""
    role: str = ""
    bullets: list = field(default_factory=list)
    tags: str = ""


@dataclass
class ResumeBlocks:
    """内容块。由调用方从简历库 / resume.md 填入，本模块不读个人文件。"""

    name: str
    intent: str
    contact_lines: list = field(default_factory=list)
    summary: str = ""
    education_lines: list = field(default_factory=list)
    internships: list = field(default_factory=list)
    projects: list = field(default_factory=list)
    campus: list = field(default_factory=list)
    skills: list = field(default_factory=list)
    certs: list = field(default_factory=list)
    photo_path: Optional[str] = None


def hex_rgb(color: str):
    """#RRGGBB → python-docx RGBColor。未安装 python-docx 时抛 ImportError。"""
    from docx.shared import RGBColor

    h = color.lstrip("#")
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def setup_a4(doc, margins_cm=(1.2, 1.2, 1.0, 1.0)):
    """A4 + 页边距（上, 下, 左, 右）厘米。"""
    from docx.enum.section import WD_ORIENT
    from docx.shared import Cm, Mm

    sec = doc.sections[0]
    sec.orientation = WD_ORIENT.PORTRAIT
    sec.page_width = Mm(210)
    sec.page_height = Mm(297)
    top, bottom, left, right = margins_cm
    sec.top_margin = Cm(top)
    sec.bottom_margin = Cm(bottom)
    sec.left_margin = Cm(left)
    sec.right_margin = Cm(right)
    return sec


def set_run_font(run, size_pt, *, bold=False, color="#1A1A1A", name=FONT_CN, italic=False):
    run.font.name = name
    run.font.size = _pt(size_pt)
    run.bold = bold
    run.italic = italic
    run.font.color.rgb = hex_rgb(color)
    _east_asia(run, name)


def set_paragraph_spacing(paragraph, *, before=0, after=0, line=1.08, align=None):
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt, Twips

    pf = paragraph.paragraph_format
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    pf.line_spacing = line
    if align == "center":
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    elif align == "right":
        paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    elif align == "left":
        paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
    # 避免 Word 自动段前间距把单页撑爆
    pf.widow_control = True
    _ = Twips


def add_text(paragraph, text, size_pt, **kwargs):
    run = paragraph.add_run(text)
    set_run_font(run, size_pt, **kwargs)
    return run


def add_hairline(doc, color="#E0E0E0"):
    """段落下发丝线（底边框）。"""
    p = doc.add_paragraph()
    set_paragraph_spacing(p, before=0, after=4, line=1.0)
    pPr = p._p.get_or_add_pPr()
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), color.lstrip("#"))
    pBdr.append(bottom)
    pPr.append(pBdr)
    return p


def shade_cell(cell, hex_color: str):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), hex_color.lstrip("#"))
    shd.set(qn("w:val"), "clear")
    tcPr.append(shd)


def set_cell_margins(cell, **cm_kwargs):
    """cell 内边距，单位厘米。keys: top/bottom/left/right。"""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm

    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcMar = OxmlElement("w:tcMar")
    for key, val in cm_kwargs.items():
        node = OxmlElement(f"w:{key}")
        node.set(qn("w:w"), str(int(Cm(val))))
        node.set(qn("w:type"), "dxa")
        tcMar.append(node)
    tcPr.append(tcMar)


def clear_table_borders(table):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    tbl = table._tbl
    tblPr = tbl.tblPr if tbl.tblPr is not None else OxmlElement("w:tblPr")
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "nil")
        borders.append(el)
    tblPr.append(borders)


def insert_photo(paragraph, photo_path: Optional[str], width_cm: float, height_cm: Optional[float] = None):
    """插入证件照。路径无效则跳过（由调用方事先校验）。"""
    from docx.shared import Cm

    if not photo_path:
        return False
    path = Path(photo_path)
    if not path.is_file():
        return False
    run = paragraph.add_run()
    kwargs = {"width": Cm(width_cm)}
    if height_cm is not None:
        kwargs["height"] = Cm(height_cm)
    run.add_picture(str(path), **kwargs)
    return True


def count_pages_com(docx_path) -> Optional[int]:
    """Word/WPS COM 实测页数。不可用时返回 None。"""
    path = str(Path(docx_path).resolve())
    try:
        import win32com.client  # type: ignore
    except ImportError:
        return None
    word = None
    try:
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0
        doc = word.Documents.Open(path, ReadOnly=True)
        pages = int(doc.ComputeStatistics(2))
        doc.Close(False)
        return pages
    except Exception:
        return None
    finally:
        if word is not None:
            try:
                word.Quit()
            except Exception:
                pass


def describe_kit() -> str:
    lines = ["骨架："]
    for sid, meta in SKELETONS.items():
        lines.append(f"  - {sid}  {meta['name_zh']}  · {meta['use']}")
    lines.append("色板：" + ", ".join(PALETTES))
    lines.append(f"正文字号下限：{MIN_BODY_PT}pt；禁止换色冒充新骨架。")
    return "\n".join(lines)


def _pt(size_pt: float):
    from docx.shared import Pt

    return Pt(size_pt)


def _east_asia(run, name: str):
    from docx.oxml.ns import qn

    r = run._element
    rPr = r.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        from docx.oxml import OxmlElement

        rFonts = OxmlElement("w:rFonts")
        rPr.append(rFonts)
    rFonts.set(qn("w:eastAsia"), name)
    rFonts.set(qn("w:ascii"), name)
    rFonts.set(qn("w:hAnsi"), name)
