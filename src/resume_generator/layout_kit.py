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
# 骨架 ID（产品约定，与 agent_entry.md 设计范式一致）
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


# ---------------------------------------------------------------------------
# 几何单一来源（Phase 3A Bug1）
#
# 所有表格宽度只能由这条链路算出，禁止 builder 自己写 21 - a - b：
#     margins ──► usable_width_cm ──► split_columns_cm ──► 列宽
# 且最后一列吸收浮点误差，保证 sum(列宽) == usable_width。
# ---------------------------------------------------------------------------

def usable_width_cm(left_margin_cm: float, right_margin_cm: float,
                    page_width_cm: float = A4_WIDTH_CM) -> float:
    """页面有效内容宽 = 页宽 - 左边距 - 右边距。"""
    return page_width_cm - left_margin_cm - right_margin_cm


def split_columns_cm(total_width_cm: float, ratios) -> list:
    """按比例把总宽切成列宽；最后一列吸收舍入误差，保证和恰好等于总宽。"""
    ratios = list(ratios)
    if not ratios:
        raise ValueError("ratios 不能为空")
    if abs(sum(ratios) - 1.0) > 1e-6:
        raise ValueError(f"column ratios 之和必须为 1.0，当前={sum(ratios)}")
    widths = [total_width_cm * r for r in ratios[:-1]]
    widths.append(total_width_cm - sum(widths))
    return widths


def cell_text_width_cm(cell_width_cm: float, left_margin_cm: float,
                       right_margin_cm: float) -> float:
    """单元格文本区宽 = 格宽 - 左内边距 - 右内边距（用于格内右制表位定位）。"""
    return cell_width_cm - left_margin_cm - right_margin_cm


def add_right_tab_stop(paragraph, position_cm: float):
    """在段落指定位置加右对齐制表位（日期等行尾信息的稳定定位，替代空格推位置）。"""
    from docx.enum.text import WD_TAB_ALIGNMENT
    from docx.shared import Cm

    paragraph.paragraph_format.tab_stops.add_tab_stop(
        Cm(position_cm), WD_TAB_ALIGNMENT.RIGHT)


def set_run_font(run, size_pt, *, bold=False, color="#1A1A1A", name=FONT_CN,
                 italic=False, latin_font: Optional[str] = None):
    """设置 run 字体/字号/字重/颜色。

    latin_font 提供时：w:ascii/w:hAnsi = latin_font（拉丁字体），
    w:eastAsia = name（CJK 字体）；None 时三者同写 name（旧路径保值）。
    run.font.name（python-docx 高层 API）写 latin_font 以让 Latin 文本
    走正确字体；CJK 文本由 w:eastAsia 接管。
    """
    run.font.name = latin_font if latin_font is not None else name
    run.font.size = _pt(size_pt)
    run.bold = bold
    run.italic = italic
    run.font.color.rgb = hex_rgb(color)
    _east_asia(run, name, latin_font=latin_font)


def set_paragraph_spacing(paragraph, *, before=0, after=0, line=1.08, align=None):
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt

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


def add_text(paragraph, text, size_pt, **kwargs):
    # latin_font 由调用方经 kwargs 透传；None → set_run_font 三者同写 name
    run = paragraph.add_run(text)
    set_run_font(run, size_pt, **kwargs)
    return run


def add_hairline(doc, color="#E0E0E0", *, before_pt=0.0, after_pt=3.0,
                 sz="6", line_pt=None, border_space=None):
    """段落下发丝线（底边框）。

    before_pt / after_pt / sz 为 Phase 3B-3 起可注入的间距/厚度参数，
    默认值保持工具层历史原值；颜色仍由 Phase 3B-2 Palette 决定。

    v0.9.0 新增两个可选几何参数（此前只能靠事后改 XML）：

    line_pt
        该**空段落**的固定行高（pt）。None = 自动行高（历史行为 ≈12pt）。
        定稿样本上「标题 → 分割线」距离的大头就是这个空段的行高：
        auto 段比 2pt 固定段高约 0.35cm，一份 6 板块的简历差 2cm。
        本段无文字无图片，使用 exact 行高不会裁切任何内容
        （含图片的段落仍禁止 exact —— Golden Sample 验收规则 4）。
    border_space
        ``w:pBdr/w:bottom/@w:space``（pt），边框与文字底线的距离。
        None = 历史值 1pt。
    """
    p = doc.add_paragraph()
    if line_pt is None:
        set_paragraph_spacing(p, before=before_pt, after=after_pt, line=1.0)
    else:
        set_paragraph_spacing(p, before=before_pt, after=after_pt, line=1.0)
        pf = p.paragraph_format
        from docx.enum.text import WD_LINE_SPACING
        from docx.shared import Pt

        pf.line_spacing_rule = WD_LINE_SPACING.EXACTLY
        pf.line_spacing = Pt(float(line_pt))
    pPr = p._p.get_or_add_pPr()
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), str(sz))
    bottom.set(qn("w:space"),
               str(border_space) if border_space is not None else "1")
    bottom.set(qn("w:color"), color.lstrip("#"))
    pBdr.append(bottom)
    pPr.append(pBdr)
    return p


def set_page_background(doc, hex_color: str):
    """整页背景色（OOXML w:background + settings 的 displayBackgroundShape）。

    产品化来源：Golden Sample 产物化清单里的「页面级背景色」（PDF_1 主区
    #F4F4F4 / PDF_4 整页 #EDF4F1）。DesignSpec 侧由
    ``ColorSpec.page_background`` 表达（值为 None = 不消费，保持纯白）。

    实现要点：
    - ``w:background`` 必须是 ``w:document`` 的**首个子元素**（在 ``w:body``
      之前），故用 insert(0, ...) 而非 append；
    - 只有 settings.xml 里开了 ``w:displayBackgroundShape``，Word/WPS 才会
      真正把底色画出来（否则仅存在于 XML、打印与屏幕都不显示）；
    - 只写颜色，不写主题色引用（themeColor），避免随 Office 主题漂移。
    """
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    color = hex_color.lstrip("#")
    if len(color) != 6:
        raise ValueError(f"页面底色必须是 #RRGGBB，收到：{hex_color!r}")

    document = doc.element
    bg = document.find(qn("w:background"))
    if bg is None:
        bg = OxmlElement("w:background")
        document.insert(0, bg)
    bg.set(qn("w:color"), color)

    settings = doc.settings.element
    if settings.find(qn("w:displayBackgroundShape")) is None:
        settings.append(OxmlElement("w:displayBackgroundShape"))


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
    """cell 内边距，单位厘米。keys: top/bottom/left/right。

    注意：w:tcMar 的 w 值单位是 **twips（dxa）**，不是 EMU。
    python-docx 的 Cm() 返回 EMU，直接当 dxa 写会放大 567 倍
    （0.25cm 会变成 ~142cm 的内边距，把分页探成几十页）。
    因此统一用 Cm(cm).twips 换算。
    """
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm

    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcMar = OxmlElement("w:tcMar")
    for key, val in cm_kwargs.items():
        node = OxmlElement(f"w:{key}")
        node.set(qn("w:w"), str(int(Cm(val).twips)))
        node.set(qn("w:type"), "dxa")
        tcMar.append(node)
    tcPr.append(tcMar)


def set_table_fixed_layout(table, total_width_cm: float, column_widths_cm=None):
    """把表格设为固定布局，并显式设置总宽 + 列宽（tblGrid）。

    为什么必需：python-docx 只给 `cell.width` 赋值时，Word 仍会按内容
    自动重新分配列宽，导致窄栏（如侧边栏）塔陷成一个字一行、总分页几十页。
    真正的列宽由 `<w:tblGrid><w:gridCol w:w=.../>` 决定；必须重写它，
    再配合 tblLayout=fixed 与 tcW 才能彻底生效。

    column_widths_cm 传入每列宽度（厘米）；不传则均分总宽。
    """
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm

    tbl = table._tbl
    tblPr = tbl.tblPr if tbl.tblPr is not None else OxmlElement("w:tblPr")

    # ① 固定布局
    for old in tblPr.findall(qn("w:tblLayout")):
        tblPr.remove(old)
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    tblPr.append(layout)

    # ② 总宽
    for old in tblPr.findall(qn("w:tblW")):
        tblPr.remove(old)
    tblW = OxmlElement("w:tblW")
    tblW.set(qn("w:w"), str(int(Cm(total_width_cm).twips)))
    tblW.set(qn("w:type"), "dxa")
    tblPr.append(tblW)

    # ③ 重写 tblGrid（真正的列宽来源）
    # ncols 从行单元格数取，不能依赖 table.columns（它本身就依赖 tblGrid）
    ncols = len(table.rows[0].cells)
    grid = tbl.find(qn("w:tblGrid"))
    if grid is not None:
        tbl.remove(grid)
    grid = OxmlElement("w:tblGrid")
    if column_widths_cm is None:
        column_widths_cm = [total_width_cm / ncols] * ncols
    for w_cm in column_widths_cm:
        gc = OxmlElement("w:gridCol")
        gc.set(qn("w:w"), str(int(Cm(w_cm).twips)))
        grid.append(gc)
    # tblGrid 必须紧跟 tblPr
    tblPr.addnext(grid)


def set_cell_width(cell, width_cm: float):
    """显式设置单元格宽度（tcW），配合 set_table_fixed_layout 使用才可靠。"""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm

    tcPr = cell._tc.get_or_add_tcPr()
    for old in tcPr.findall(qn("w:tcW")):
        tcPr.remove(old)
    tcW = OxmlElement("w:tcW")
    tcW.set(qn("w:w"), str(int(Cm(width_cm).twips)))
    tcW.set(qn("w:type"), "dxa")
    tcPr.append(tcW)


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


@dataclass
class PhotoInsertResult:
    """照片插入结果（Phase 3A Bug3）。

    status:
        inserted_equal        目标盒与源图同比例，等比铺满
        inserted_contain      比例不一致，已等比缩放进盒（盒内留白，未变形、未裁剪）
        inserted_width_only   未给目标高，按宽等比（python-docx 自动保比例）
        missing               路径为空或文件不存在，已安全跳过
        distorted_forced      调用方显式 preserve_aspect=False（危险，需知情）
    兼容旧代码：bool(result) == ok。
    """

    status: str
    ok: bool = False
    target_width_cm: Optional[float] = None
    target_height_cm: Optional[float] = None
    applied_width_cm: Optional[float] = None
    applied_height_cm: Optional[float] = None
    source_aspect: Optional[float] = None
    note: str = ""

    def __bool__(self) -> bool:
        return self.ok


def _read_image_aspect(photo_path) -> Optional[float]:
    """读取源图片宽高比；失败返回 None（不抛异常，保证渲染不被图片问题击垮）。"""
    try:
        from docx.image.image import Image

        with open(photo_path, "rb") as f:
            img = Image.from_blob(f.read())
        if img.px_height:
            return img.px_width / img.px_height
    except Exception:
        return None
    return None


def insert_photo(paragraph, photo_path: Optional[str], width_cm: float,
                 height_cm: Optional[float] = None, *,
                 preserve_aspect: bool = True) -> PhotoInsertResult:
    """插入证件照（等比保护）。

    - 路径无效：返回 missing，不插入，不抛异常。
    - preserve_aspect=True（默认，硬规则）：
        * 只给宽 → 按宽等比；
        * 给宽+高 → contain 进目标盒（等比缩放，盒内可能留白），
          绝不强制拉伸；当前 Renderer 不做像素裁剪，留白即安全 fallback。
    - preserve_aspect=False：调用方明确知情才允许强制宽高（status 会标记）。
    """
    from docx.shared import Cm

    if not photo_path:
        return PhotoInsertResult("missing", note="photo_path 为空，已跳过")
    path = Path(photo_path)
    if not path.is_file():
        return PhotoInsertResult("missing", note=f"照片文件不存在：{path}，已跳过")

    src_ar = _read_image_aspect(path)

    # 只给宽：python-docx 单维度即等比
    if height_cm is None:
        run = paragraph.add_run()
        run.add_picture(str(path), width=Cm(width_cm))
        applied_h = (width_cm / src_ar) if src_ar else None
        return PhotoInsertResult(
            "inserted_width_only", ok=True,
            target_width_cm=width_cm, target_height_cm=None,
            applied_width_cm=width_cm, applied_height_cm=applied_h,
            source_aspect=src_ar,
            note="未给目标高，按宽等比插入")

    if not preserve_aspect:
        run = paragraph.add_run()
        run.add_picture(str(path), width=Cm(width_cm), height=Cm(height_cm))
        return PhotoInsertResult(
            "distorted_forced", ok=True,
            target_width_cm=width_cm, target_height_cm=height_cm,
            applied_width_cm=width_cm, applied_height_cm=height_cm,
            source_aspect=src_ar,
            note="显式关闭等比保护；源比例与目标不一致时人物会变形")

    # 读不到源比例时，退化为只按宽等比（最安全的兜底）
    if not src_ar:
        run = paragraph.add_run()
        run.add_picture(str(path), width=Cm(width_cm))
        return PhotoInsertResult(
            "inserted_width_only", ok=True,
            target_width_cm=width_cm, target_height_cm=height_cm,
            applied_width_cm=width_cm, applied_height_cm=None,
            source_aspect=None,
            note="无法读取源图尺寸，退化为按宽等比（不强制目标高）")

    # contain：按宽高约束中更紧的一边等比缩放，保证不超出目标盒且不变形
    box_ar = width_cm / height_cm
    if src_ar > box_ar:
        applied_w = width_cm
        applied_h = width_cm / src_ar
    else:
        applied_h = height_cm
        applied_w = height_cm * src_ar

    run = paragraph.add_run()
    run.add_picture(str(path), width=Cm(applied_w), height=Cm(applied_h))
    same = abs(applied_w - width_cm) < 1e-6 and abs(applied_h - height_cm) < 1e-6
    status = "inserted_equal" if same else "inserted_contain"
    note = "目标盒与源图同比例" if same else (
        "源比例与目标盒不一致，已 contain 等比适配（盒内留白，未变形、未裁剪）")
    return PhotoInsertResult(
        status, ok=True,
        target_width_cm=width_cm, target_height_cm=height_cm,
        applied_width_cm=applied_w, applied_height_cm=applied_h,
        source_aspect=src_ar, note=note)


# ---------------------------------------------------------------------------
# 浮动照片（wp:anchor；Golden Sample CL-01 产品化，Phase 2B-4 Step 4）
# ---------------------------------------------------------------------------

_EMU_PER_CM = 360000
_EMU_PER_PT = 12700


def _force_anchor_paragraph_auto_line(paragraph) -> None:
    """行高保护：浮动照片锚点段禁止 exact/atLeast 行距（会裁切图片）。

    做法：若段落级 spacing 声明了固定行距，移除 line/lineRule 两个属性，
    让段落回到自动行距（继承样式/默认单倍多倍行距）。
    """
    from docx.oxml.ns import qn

    p_pr = paragraph._p.find(qn("w:pPr"))
    if p_pr is None:
        return
    spacing = p_pr.find(qn("w:spacing"))
    if spacing is None:
        return
    if spacing.get(qn("w:lineRule")) in ("exact", "atLeast"):
        spacing.attrib.pop(qn("w:line"), None)
        spacing.attrib.pop(qn("w:lineRule"), None)


def _apply_picture_border(sp_pr, *, color_hex: str, width_pt: float) -> None:
    """在 pic:spPr 上写 a:ln 实线边框（CT_ShapeProperties 顺序：ln 位于填充后）。"""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    ln = OxmlElement("a:ln")
    ln.set("w", str(int(round(width_pt * _EMU_PER_PT))))
    ln.set("cap", "flat")
    ln.set("cmpd", "sng")
    ln.set("algn", "ctr")
    solid = OxmlElement("a:solidFill")
    clr = OxmlElement("a:srgbClr")
    clr.set("val", color_hex)
    solid.append(clr)
    ln.append(solid)
    dash = OxmlElement("a:prstDash")
    dash.set("val", "solid")
    ln.append(dash)
    sp_pr.append(ln)


def insert_floating_photo(paragraph, photo_path: Optional[str], width_cm: float,
                          height_cm: Optional[float] = None, *,
                          position_h: str = "column",
                          position_v: str = "page",
                          offset_x_cm: float = 0.0,
                          offset_y_cm: float = 0.0,
                          border_color: Optional[str] = None,
                          border_width_pt: float = 0.0,
                          behind_doc: bool = True,
                          preserve_aspect: bool = True) -> PhotoInsertResult:
    """插入浮动照片（wp:anchor）。

    Golden Sample CL-01 产品化：behindDoc=1（衬于文字下方）、
    wrapTopAndBottom（上下型环绕）、layoutInCell=1（允许锚在表格单元格段）、
    相对锚点（column/page）+ posOffset（cm→EMU）、图片 a:ln 边框。

    等比策略与 insert_photo 一致（读不到源比例或未给高时按宽等比）；
    路径无效同样安全跳过。插入后强制锚点段自动行距（exact 会裁图）。
    """
    from docx.shared import Cm
    from docx.oxml import OxmlElement, parse_xml
    from docx.oxml.ns import nsdecls, qn

    if not photo_path:
        return PhotoInsertResult("missing", note="photo_path 为空，已跳过")
    path = Path(photo_path)
    if not path.is_file():
        return PhotoInsertResult("missing",
                                 note=f"照片文件不存在：{path}，已跳过")

    src_ar = _read_image_aspect(path)

    # 等比适配（与 insert_photo 同规则；浮动图同样禁止变形）
    if height_cm is None or not src_ar:
        applied_w = width_cm
        applied_h = (width_cm / src_ar) if src_ar else None
        fit_note = "未给目标高（或读不到源比例），按宽等比浮动插入"
    elif not preserve_aspect:
        applied_w, applied_h = width_cm, height_cm
        fit_note = "显式关闭等比保护（危险）"
    else:
        box_ar = width_cm / height_cm
        if src_ar > box_ar:
            applied_w, applied_h = width_cm, width_cm / src_ar
        else:
            applied_h, applied_w = height_cm, height_cm * src_ar
        fit_note = "contain 等比适配浮动盒"

    run = paragraph.add_run()
    if applied_h is None:
        run.add_picture(str(path), width=Cm(applied_w))
    else:
        run.add_picture(str(path), width=Cm(applied_w), height=Cm(applied_h))

    # 定位刚生成的 wp:inline，并把其 graphic/extent/docPr 搬入 wp:anchor
    drawing = run._r.find(qn("w:drawing"))
    inline = drawing.find(qn("wp:inline"))
    graphic = inline.find(qn("a:graphic"))
    extent = inline.find(qn("wp:extent"))
    doc_pr = inline.find(qn("wp:docPr"))

    # 边框：写在 pic:spPr/a:ln（跟随图形，Word/WPS 都能渲染）
    border_hex = ""
    if border_color and border_width_pt and border_width_pt > 0:
        border_hex = str(border_color).strip().lstrip("#").upper()
        sp_pr = graphic.find(".//" + qn("pic:spPr"))
        if sp_pr is not None:
            _apply_picture_border(sp_pr, color_hex=border_hex,
                                  width_pt=float(border_width_pt))

    anchor = parse_xml(
        "<wp:anchor %s distT=\"0\" distB=\"0\" distL=\"0\" distR=\"0\" "
        "simplePos=\"0\" relativeHeight=\"0\" behindDoc=\"%d\" locked=\"0\" "
        "layoutInCell=\"1\" allowOverlap=\"1\"></wp:anchor>"
        % (nsdecls("wp", "a"), 1 if behind_doc else 0))

    def _sub(parent, tag, **attrs):
        el = OxmlElement(tag)
        for key, val in attrs.items():
            el.set(key, str(val))
        parent.append(el)
        return el

    _sub(anchor, "wp:simplePos", x=0, y=0)
    pos_h = _sub(anchor, "wp:positionH", relativeFrom=position_h)
    _sub(pos_h, "wp:posOffset").text = str(
        int(round(float(offset_x_cm) * _EMU_PER_CM)))
    pos_v = _sub(anchor, "wp:positionV", relativeFrom=position_v)
    _sub(pos_v, "wp:posOffset").text = str(
        int(round(float(offset_y_cm) * _EMU_PER_CM)))
    anchor.append(extent)                    # 移动：extent
    _sub(anchor, "wp:effectExtent", l=0, t=0, r=0, b=0)
    _sub(anchor, "wp:wrapTopAndBottom")
    anchor.append(doc_pr)                    # 移动：docPr（保持图片 id）
    _sub(anchor, "wp:cNvGraphicFramePr")
    anchor.append(graphic)                   # 移动：graphic（含 a:ln）

    drawing.replace(inline, anchor)

    # 行高保护：锚点段强制自动行距
    _force_anchor_paragraph_auto_line(paragraph)

    return PhotoInsertResult(
        "inserted_floating", ok=True,
        target_width_cm=width_cm, target_height_cm=height_cm,
        applied_width_cm=applied_w, applied_height_cm=applied_h,
        source_aspect=src_ar,
        note=(f"浮动锚定 posH={position_h}+{offset_x_cm}cm "
              f"posV={position_v}+{offset_y_cm}cm "
              f"behindDoc={int(behind_doc)} wrap=topAndBottom"
              + (f" border=#{border_hex}@{border_width_pt}pt"
                 if border_hex else " border=none")
              + f"；{fit_note}"))


def count_pages_com(docx_path: str | Path) -> Optional[int]:
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


def _east_asia(run, name: str, *, latin_font: Optional[str] = None):
    """设置 run 的 rFonts。latin_font 提供时 ascii/hAnsi 用拉丁字体、
    eastAsia 用 name（CJK 字体）；None 时三者同写 name（旧路径行为保值）。
    """
    from docx.oxml.ns import qn

    r = run._element
    rPr = r.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        from docx.oxml import OxmlElement

        rFonts = OxmlElement("w:rFonts")
        rPr.append(rFonts)
    latin = latin_font if latin_font is not None else name
    rFonts.set(qn("w:eastAsia"), name)
    rFonts.set(qn("w:ascii"), latin)
    rFonts.set(qn("w:hAnsi"), latin)
