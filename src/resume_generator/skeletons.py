# -*- coding: utf-8 -*-
"""三种可复用简历骨架。内容由调用方传入 ResumeBlocks，本文件不含个人事实。

选用规则：
    - 先定骨架 ID，再定色板。禁止「沿用上一份公司脚本、只改强调色」。
    - 核心板块顺序固定：个人信息 → 教育 → 实习 → 项目（次要板块可调）。
    - 正文不得低于 layout_kit.MIN_BODY_PT。
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional, Tuple

from resume_generator.layout_kit import (
    MIN_BODY_PT,
    PALETTES,
    Palette,
    ResumeBlocks,
    SKELETON_BANNER,
    SKELETON_MINIMAL,
    SKELETON_SIDEBAR,
    add_hairline,
    add_right_tab_stop,
    add_text,
    cell_text_width_cm,
    clear_table_borders,
    hex_rgb,
    insert_photo,
    insert_floating_photo,
    set_cell_margins,
    set_cell_width,
    set_page_background,
    set_paragraph_spacing,
    set_run_font,
    set_table_fixed_layout,
    setup_a4,
    shade_cell,
    split_columns_cm,
    usable_width_cm,
)
from resume_generator.render_style import (
    RenderStyle,
    SKELETON_DEFAULT_STYLE,
    build_palette_for_skeleton,
    resolve_style_for_spec,
)

# ---------------------------------------------------------------------------
# 骨架布局配置（Phase 3A）：margin / 列比例 / 照片盒的唯一登记处。
# 列宽不再手算：usable_width = 21 - 左 - 右 → 按 col_ratios 切分。
# col_ratios 取改造前各骨架原列宽的比例，视觉结构保持不变（仅修正总宽错算）。
# cell 内边距属 Spacing 语义，Phase 3B-3 起登记于 render_style 的
# RenderSpacing Profile（cell_left_cm / cell_right_cm），不再混放在此处。
# ---------------------------------------------------------------------------

_LAYOUT_CONFIG = {
    SKELETON_BANNER: {
        "margins_cm": (0.55, 0.55, 1.0, 1.0),
        "col_ratios": (8.4 / 18.8, 10.4 / 18.8),
        "photo_box_cm": (1.85, 2.4),
    },
    SKELETON_MINIMAL: {
        "margins_cm": (0.7, 0.7, 1.25, 1.25),
        "col_ratios": (13.0 / 18.0, 5.0 / 18.0),
        "photo_box_cm": (1.85, 2.4),
    },
    SKELETON_SIDEBAR: {
        "margins_cm": (0.8, 0.8, 0.8, 0.8),
        "col_ratios": (5.9 / 19.4, 13.5 / 19.4),
        "photo_box_cm": (3.2, 4.0),
    },
}

# DesignSpec 范式 → 现有骨架（Phase 3A 兼容入口；不新增范式）
PARADIGM_TO_SKELETON = {
    "p1_banner_single": SKELETON_BANNER,
    "p2_sidebar_two_column": SKELETON_SIDEBAR,
    "p3_minimal_editorial": SKELETON_MINIMAL,
}


@dataclass(frozen=True)
class PhotoAnchorConfig:
    """浮动照片几何/描边（由 DesignSpec.photo.floating/border 解析）。

    仅 build_minimal 消费；banner/sidebar 不读。坐标全部来自 Spec，
    骨架不固化任何具体简历的偏移值。
    """

    position_h: str = "column"
    position_v: str = "page"
    offset_x_cm: float = 0.0
    offset_y_cm: float = 0.0
    border_color: Optional[str] = None
    border_width_pt: float = 0.0


@dataclass
class RenderOverrides:
    """Spec 驱动路径对 Renderer 的覆盖。

    None 字段表示沿用骨架默认常量。
    margins/photo_box：Phase 3A 几何/照片；style：Phase 3B-1 排版参数。
    has_photo：Phase 2B-2 / P-2 Header 结构开关。None=沿用骨架默认（True，
    即旧路径与 P1/P2 spec 路径仍走 2 列含照片格的 Header）；P3 spec 在
    _build_from_spec 由 spec.photo.enabled 解析为 False，触发单列 Header。
    仅 build_minimal 消费；build_banner_card / build_sidebar 不读此字段，
    其 Header 行为字节级零变化。
    """

    margins_cm: Optional[Tuple[float, float, float, float]] = None
    photo_box_cm: Optional[Tuple[float, float]] = None
    style: Optional[RenderStyle] = None
    has_photo: Optional[bool] = None
    # P-3：spec.header.accent_line.enabled 决定 minimal 是否绘制 Header 顶部
    # 强调线。None=沿用骨架默认（True，即旧路径与 P1/P2 spec 路径不经
    # build_minimal，行为字节级零变化）；P3 spec 在 _build_from_spec 由
    # spec.header.accent_line.enabled 解析为 False，跳过 rule 段创建。
    accent_line_enabled: Optional[bool] = None
    # Golden Sample CL-01：非 None 时 minimal 照片段走 wp:anchor
    # （衬于文字下方 + 上下型环绕 + posOffset 定位 + a:ln 边框）；
    # None=保持 wp:inline 旧行为。banner/sidebar 不读。
    photo_anchor: Optional[PhotoAnchorConfig] = None
    # 页面级背景色（spec.colors.page_background）。None=不消费，保持纯白
    # （旧路径与 P1/P2 spec 均为 None，字节级不变）；仅 build_minimal 读。
    page_background: Optional[str] = None


def _concrete_cm(sv) -> Optional[float]:
    """从 Sourced 取真实厘米数值；未确定 / not_applicable / 非数值 → None。

    为什么不能只看 is_undetermined：`Sourced.not_applicable()` 的
    status 是 CONFIRMED（is_undetermined=False）**但 value=None**
    （例如 P3 Preset 的 photo.width / photo.height ——「P3 不使用照片」）。
    旧实现只判 is_undetermined 就 `float(sv.value)`，于是「P3 Preset 上
    启用照片」会直接 TypeError 崩溃。

    语义：拿不到真实数值 = 本份未指定尺寸 → 返回 None，
    由调用方沿用骨架的范式级默认照片盒（不猜、不编数值）。
    """
    if sv is None or sv.is_undetermined:
        return None
    v = sv.value
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return float(v)


def _concrete_box_cm(width_sv, height_sv) -> Optional[Tuple[float, float]]:
    """宽高都能取到真实数值时才返回 (宽, 高)；否则 None（保持默认盒）。"""
    w = _concrete_cm(width_sv)
    h = _concrete_cm(height_sv)
    if w is None or h is None:
        return None
    return (w, h)


def _resolve_style(skeleton_id: str,
                   overrides: Optional[RenderOverrides]) -> RenderStyle:
    """取排版参数包：Spec 路径用 overrides.style，旧路径用骨架默认 Profile
    （= 改造前审计原值，保证旧调用视觉不变）。"""
    if overrides is not None and overrides.style is not None:
        return overrides.style
    return SKELETON_DEFAULT_STYLE[skeleton_id]


def _resolve_context(skeleton_id: str, palette: Palette,
                     overrides: Optional[RenderOverrides]) -> RenderStyle:
    """取完整渲染参数（Typography + Palette）。

    Spec 路径的 style 已在 resolve_style_for_spec 中带好颜色；
    旧路径在此按「骨架 + 运行时所选行业色板」挂载 Skeleton Default Palette。
    """
    st = _resolve_style(skeleton_id, overrides)
    if st.palette is None:
        st = replace(st, palette=build_palette_for_skeleton(skeleton_id,
                                                            palette))
    return st


def resolve_palette(palette_id: Optional[str], skeleton_id: str) -> Palette:
    from resume_generator.layout_kit import DEFAULT_PALETTE_FOR_SKELETON

    pid = palette_id or DEFAULT_PALETTE_FOR_SKELETON[skeleton_id]
    if pid not in PALETTES:
        raise KeyError(f"未知色板 {pid}，可选：{list(PALETTES)}")
    return PALETTES[pid]


def build_document(blocks: ResumeBlocks, skeleton_id: Optional[str] = None,
                   palette_id: Optional[str] = None, *,
                   design_spec=None, strict: bool = False,
                   overrides: Optional[RenderOverrides] = None):
    """按骨架构建 Document。调用方负责保存。

    旧路径（完全向后兼容）：
        build_document(blocks, "single_column_minimal")
        build_document(blocks, "banner_card", "tech_navy")
    Spec 路径（Phase 3A 基础接线）：
        build_document(blocks, design_spec=spec)
        —— 先过 Validator（ERROR 直接拒绝；strict 时 WARNING 也拒绝），
           映射范式→骨架，几何/照片从 Spec 覆盖，其余仍走骨架常量。
    """
    if design_spec is not None:
        return _build_from_spec(blocks, design_spec, strict=strict)

    if skeleton_id is None:
        raise KeyError("必须提供 skeleton_id 或 design_spec")
    builders = {
        SKELETON_BANNER: build_banner_card,
        SKELETON_MINIMAL: build_minimal,
        SKELETON_SIDEBAR: build_sidebar,
    }
    if skeleton_id not in builders:
        raise KeyError(f"未知骨架 {skeleton_id}，可选：{list(builders)}")
    return builders[skeleton_id](
        blocks, resolve_palette(palette_id, skeleton_id), overrides=overrides)


def _build_from_spec(blocks: ResumeBlocks, spec, *, strict: bool):
    """DesignSpec → Renderer 的最小接线（不自行创造视觉规则）。"""
    from resume_generator.design import validate_spec

    result = validate_spec(spec)
    if result.errors:
        detail = "\n".join("  - " + e.render() for e in result.errors)
        raise ValueError(f"DesignSpec 未通过校验，拒绝渲染：\n{detail}")
    if strict and result.warnings:
        detail = "\n".join("  - " + w.render() for w in result.warnings)
        raise ValueError(f"strict 模式下不允许 WARNING：\n{detail}")

    sk = PARADIGM_TO_SKELETON.get(spec.architecture.paradigm)
    if sk is None:
        raise KeyError(
            f"范式 {spec.architecture.paradigm} 暂无已验证骨架映射，"
            f"当前仅支持：{list(PARADIGM_TO_SKELETON)}")

    # --- 几何覆盖：仅当 Spec 的四个边距都给出真实数值（P1）；
    #     P2 bleed 缺口 / not_applicable（value=None）→ 沿用骨架默认 ---
    ov = RenderOverrides()
    m = spec.page.margins
    margin_vals = [m.top, m.bottom, m.left, m.right]
    resolved_margins = [_concrete_cm(v) for v in margin_vals]
    if all(v is not None for v in resolved_margins):
        ov.margins_cm = tuple(resolved_margins)  # type: ignore

    # --- 列比例覆盖（v0.9.0）：grid.identity_band_ratio / grid.column_ratio ---
    # 此前 grid 的列比例是死字段（改它不生效），身份区两列宽度硬编码在
    # _LAYOUT_CONFIG。现在 Spec 给了合法比例就用它，给不出就沿用骨架默认。
    ov.col_ratios = _ratios_from_spec(spec, sk)

    # --- 照片 / 顶部强调线覆盖 ---
    # P-2：spec.photo.enabled 决定 minimal Header 是否含照片格（P3 False → 单列）
    # P-3：spec.header.accent_line.enabled 决定 minimal Header 顶部强调线是否绘制
    ov.has_photo = spec.photo.enabled
    ov.accent_line_enabled = spec.header.accent_line.enabled
    if spec.photo.enabled:
        photo = spec.photo
        # 只有 Spec 给出**真实数值**时才覆盖照片盒；给不出（未确定 /
        # not_applicable，如 P3 Preset 的 photo.width=None）→ 不覆盖，
        # 交回 _LAYOUT_CONFIG 的骨架默认照片盒。
        # 「未明确的字段保持 Preset 默认语义」——不得 float(None) 崩溃，
        # 也不得为填满字段编造数值。
        if photo.display_shape == "circle":
            fb = photo.fallback
            box = _concrete_box_cm(fb.width, fb.height) if fb is not None else None
        else:
            box = _concrete_box_cm(photo.width, photo.height)
        if box is not None:
            ov.photo_box_cm = box

        # CL-01：浮动照片（wp:anchor）。仅 floating.enabled=True 时接线，
        # 其余 Spec/Preset 保持 wp:inline；偏移缺省按 0 处理，坐标不写死。
        pf = getattr(photo, "floating", None)
        if pf is not None and pf.enabled:
            def _offset_cm(sv):
                if sv is None or sv.is_undetermined:
                    return 0.0
                return float(sv.value) \
                    if isinstance(sv.value, (int, float)) else 0.0

            border_color = None
            border_width = 0.0
            pbd = getattr(photo, "border", None)
            if pbd is not None:
                bw_val = pbd.width_pt.value
                if isinstance(bw_val, (int, float)) and bw_val > 0:
                    border_width = float(bw_val)
                    if isinstance(pbd.color.value, str):
                        border_color = pbd.color.value
            ov.photo_anchor = PhotoAnchorConfig(
                position_h=pf.position_h, position_v=pf.position_v,
                offset_x_cm=_offset_cm(pf.offset_x_cm),
                offset_y_cm=_offset_cm(pf.offset_y_cm),
                border_color=border_color,
                border_width_pt=border_width)

    # --- 页面级背景色（Phase 3C）：spec.colors.page_background ---
    # 只有 Spec 给出真实 #RRGGBB 字符串时才写 w:background；
    # None / undetermined（缺知识依据）→ 不写，保持纯白纸面。
    pb = getattr(spec.colors, "page_background", None)
    if pb is not None and not pb.is_undetermined \
            and isinstance(pb.value, str) and pb.value:
        ov.page_background = pb.value

    # 色板：Spec 颜色角色经 resolve_style_for_spec 进入 RenderPalette；
    # palette 仅作为颜色缺口的 fallback 基础（取骨架默认行业色板）。
    palette = resolve_palette(None, sk)
    # TypographySpec + ColorSpec → RenderStyle（缺口字段回退骨架 Profile）
    ov.style = resolve_style_for_spec(spec, SKELETON_DEFAULT_STYLE[sk],
                                      sk, palette)
    builders = {
        SKELETON_BANNER: build_banner_card,
        SKELETON_MINIMAL: build_minimal,
        SKELETON_SIDEBAR: build_sidebar,
    }
    return builders[sk](blocks, palette, overrides=ov)


def _resolve_layout(skeleton_id: str, overrides: Optional[RenderOverrides]):
    """合并骨架默认布局与 Spec 覆盖，返回 (margins, usable_width, col_widths,
    photo_box)。所有表宽都从这里取，禁止在 builder 内再手算。"""
    cfg = _LAYOUT_CONFIG[skeleton_id]
    margins = overrides.margins_cm if overrides and overrides.margins_cm \
        else cfg["margins_cm"]
    usable = usable_width_cm(margins[2], margins[3])
    ratios = (overrides.col_ratios
              if overrides and overrides.col_ratios else cfg["col_ratios"])
    col_widths = split_columns_cm(usable, ratios)
    photo_box = overrides.photo_box_cm if overrides and overrides.photo_box_cm \
        else cfg["photo_box_cm"]
    return margins, usable, col_widths, photo_box


def _valid_ratio(candidate, expected_len: int) -> Optional[Tuple[float, ...]]:
    """校验 Spec 给的列比例是否可用：长度匹配、元素为正、和≈1。

    不合法一律返回 None（沿用骨架默认），**不报错也不猜** —— 合法性属于
    Validator 的职责（RULE_COLUMN_RATIO），这里只判断「能不能用」。
    """
    if candidate is None:
        return None
    try:
        vals = tuple(float(v) for v in candidate)
    except (TypeError, ValueError):
        return None
    if len(vals) != expected_len or any(v <= 0 for v in vals):
        return None
    if abs(sum(vals) - 1.0) > 0.02:
        return None
    return vals


def _ratios_from_spec(spec, skeleton_id: str) -> Optional[Tuple[float, ...]]:
    """从 DesignSpec 解析本份的列比例；给不出真实值时返回 None。

    优先级（按语义对应，不做几何猜测）：
      1. ``grid.identity_band_ratio`` —— 身份区表格列比例，三骨架通用。
      2. 仅 sidebar：``grid.column_ratio`` —— 正文双栏栅格的正式声明；
         单栏范式（[1.0]）对 2 列骨架无意义，长度不匹配自然被拒。
    """
    expected_len = len(_LAYOUT_CONFIG[skeleton_id]["col_ratios"])
    grid = getattr(spec, "grid", None)
    if grid is None:
        return None

    band = _valid_ratio(getattr(grid, "identity_band_ratio", None), expected_len)
    if band is not None:
        return band

    if skeleton_id == SKELETON_SIDEBAR:
        col = _valid_ratio(getattr(grid, "column_ratio", None), expected_len)
        if col is not None:
            return col
    return None


def build_banner_card(blocks: ResumeBlocks, palette: Palette,
                      overrides: Optional[RenderOverrides] = None):
    from docx import Document

    margins, usable, col_widths, photo_box = _resolve_layout(
        SKELETON_BANNER, overrides)
    st = _resolve_context(SKELETON_BANNER, palette, overrides)
    sp = st.spacing
    w_left, w_right = col_widths

    doc = Document()
    setup_a4(doc, margins_cm=margins)
    _set_doc_default_font(doc, st)

    table = doc.add_table(rows=1, cols=2)
    clear_table_borders(table)
    set_table_fixed_layout(table, usable, col_widths)
    left, right = table.rows[0].cells
    shade_cell(left, st.palette.dark_block)
    shade_cell(right, st.palette.dark_block)
    set_cell_width(left, w_left)
    set_cell_width(right, w_right)
    cm_l = sp.cell_left_cm
    cm_r = sp.cell_right_cm
    set_cell_margins(left, top=cm_l[0], bottom=cm_l[1], left=cm_l[2], right=cm_l[3])
    set_cell_margins(right, top=cm_r[0], bottom=cm_r[1], left=cm_r[2], right=cm_r[3])

    p = left.paragraphs[0]
    set_paragraph_spacing(p, before=sp.id_name_before,
                          after=sp.id_name_after, line=st.line_exp_header)
    _apply_align(p, st.components.identity_text_align)
    add_text(p, blocks.name, st.name_size, bold=st.w_name,
             color=st.palette.on_dark_primary, name=st.font_family, latin_font=st.latin_font)
    p2 = left.add_paragraph()
    set_paragraph_spacing(p2, before=sp.id_intent_before,
                          after=sp.id_intent_after, line=st.line_exp_header)
    _apply_align(p2, st.components.identity_text_align)
    add_text(p2, blocks.intent, st.intent_size, bold=True,
             color=st.palette.on_dark_tertiary, name=st.font_family, latin_font=st.latin_font)
    for line in blocks.contact_lines:
        cp = left.add_paragraph()
        set_paragraph_spacing(cp, before=sp.id_contact_before,
                              after=sp.id_contact_after,
                              line=st.line_exp_header)
        _apply_align(cp, st.components.contact_align)
        add_text(cp, line, st.contact_size,
                 color=st.palette.on_dark_secondary, name=st.font_family, latin_font=st.latin_font)

    rp = right.paragraphs[0]
    _apply_align(rp, st.components.photo_align)
    set_paragraph_spacing(rp, before=sp.id_photo_before,
                          after=sp.id_photo_after, line=1.0)
    insert_photo(rp, blocks.photo_path, photo_box[0], photo_box[1],
                 preserve_aspect=st.components.photo_preserve_aspect)

    # 强调色条（厚度由 Spec header.accent_line 或骨架 Profile 决定）
    bar = doc.add_paragraph()
    set_paragraph_spacing(bar, before=sp.bar_before, after=sp.bar_after,
                          line=0.4)
    _bottom_border(bar, st.palette.accent, sz=sp.bar_sz)

    if blocks.summary:
        _section_title(doc, "个人优势", st, numbered=False)
        summary_p = doc.add_paragraph()
        set_paragraph_spacing(summary_p, before=sp.summary_before,
                              after=sp.summary_after, line=st.line_body)
        add_text(summary_p, blocks.summary, st.body_size,
                 color=st.palette.ink, name=st.font_family, latin_font=st.latin_font)

    _education(doc, blocks, st)
    _experience_section(doc, "实习经历", blocks.internships, st,
                        body_width_cm=usable)
    _experience_section(doc, "项目经历", blocks.projects, st,
                        body_width_cm=usable)
    if blocks.campus:
        _bullet_section(doc, "校园经历", blocks.campus, st)
    _skills_certs(doc, blocks, st)
    return doc


def build_minimal(blocks: ResumeBlocks, palette: Palette,
                  overrides: Optional[RenderOverrides] = None):
    from docx import Document

    margins, usable, col_widths, photo_box = _resolve_layout(
        SKELETON_MINIMAL, overrides)
    st = _resolve_context(SKELETON_MINIMAL, palette, overrides)
    sp = st.spacing
    w_left, w_right = col_widths

    # P-2：spec.photo.enabled=False（P3 photo_zone="none"）→ Header 单列，
    # 不再保留右侧空照片格；None/True（旧路径与 P1/P2 spec 路径不经
    # build_minimal）沿用 2 列 + 照片格原行为，字节级保持不变。
    has_photo = True
    if overrides is not None and overrides.has_photo is not None:
        has_photo = overrides.has_photo
    # P-3：spec.header.accent_line.enabled=False（P3）→ 跳过 Header 顶部
    # 强调线段创建（不写空段、不写 w:pBdr、不写 rule_sz）；None/True
    # （旧路径与 P1/P2 spec 路径不经 build_minimal）沿用原 rule 行为。
    draw_rule = True
    if overrides is not None and overrides.accent_line_enabled is not None:
        draw_rule = overrides.accent_line_enabled

    doc = Document()
    setup_a4(doc, margins_cm=margins)
    _set_doc_default_font(doc, st)
    # 页面底色：仅当 Spec 给出 page_background 时写 w:background
    # （旧路径 / P3 Preset 默认 None → 零变化，纯白纸面）。
    if overrides is not None and overrides.page_background:
        set_page_background(doc, overrides.page_background)

    head = doc.add_table(rows=1, cols=2 if has_photo else 1)
    clear_table_borders(head)
    # 表宽严格等于 usable_width（21 - 左 - 右），修复旧版按 1.5cm 边距错算
    if has_photo:
        set_table_fixed_layout(head, usable, col_widths)
        c0, c1 = head.rows[0].cells
        set_cell_width(c0, w_left)
        set_cell_width(c1, w_right)
    else:
        # P3 单列 Header：tblGrid 单列、列宽 = usable_width，文本占满整宽
        set_table_fixed_layout(head, usable, [usable])
        c0 = head.rows[0].cells[0]
        set_cell_width(c0, usable)
    p = c0.paragraphs[0]
    set_paragraph_spacing(p, before=sp.id_name_before,
                          after=sp.id_name_after, line=st.line_exp_header)
    _apply_align(p, st.components.identity_text_align)
    add_text(p, blocks.name, st.name_size, bold=st.w_name,
             color=st.palette.ink, name=st.font_family, latin_font=st.latin_font)
    p2 = c0.add_paragraph()
    set_paragraph_spacing(p2, before=sp.id_intent_before,
                          after=sp.id_intent_after, line=st.line_exp_header)
    _apply_align(p2, st.components.identity_text_align)
    add_text(p2, blocks.intent, st.intent_size, color=st.palette.accent,
             bold=True, name=st.font_family, latin_font=st.latin_font)
    for line in blocks.contact_lines:
        cp = c0.add_paragraph()
        set_paragraph_spacing(cp, before=sp.id_contact_before,
                              after=sp.id_contact_after,
                              line=st.line_exp_header)
        _apply_align(cp, st.components.contact_align)
        add_text(cp, line, st.contact_size, color=st.palette.muted,
                 name=st.font_family, latin_font=st.latin_font)

    if has_photo:
        rp = c1.paragraphs[0]
        _apply_align(rp, st.components.photo_align)
        anchor = overrides.photo_anchor if overrides is not None else None
        if anchor is not None:
            # v0.9.0 产品级修复（2026-09-21）：锚点段此前**完全没有**被
            # set_paragraph_spacing 触碰，于是继承 docDefaults 的
            # ``w:after=200``（10pt）与 ``w:line=276``（1.15 倍）。
            # 浮动照片用「上下型环绕 + layoutInCell=1」锚在单元格里，
            # Word 必须为它预留纵向空间 → 该表格行被撑到图片高度，
            # 而这段继承来的段后/行距就在图片高度之外又白占约 0.82cm，
            # 把头部表撑高，形成「个人信息 → 个人优势」之间的莫名空缺。
            # 定稿样本上标题被推到 5.02cm，压紧后 4.05cm。
            # 只改这一条分支：旧路径（无 anchor，含 wp:inline）字节级不变。
            set_paragraph_spacing(
                rp,
                before=sp.id_photo_before or 0,
                after=sp.id_photo_after or 0,
                line=1.0)
            # Golden Sample CL-01：浮动锚定照片（wp:anchor），不占内联流；
            # insert_floating_photo 内部强制锚点段自动行距，防 exact 裁图。
            insert_floating_photo(
                rp, blocks.photo_path, photo_box[0], photo_box[1],
                position_h=anchor.position_h, position_v=anchor.position_v,
                offset_x_cm=anchor.offset_x_cm, offset_y_cm=anchor.offset_y_cm,
                border_color=anchor.border_color,
                border_width_pt=anchor.border_width_pt,
                preserve_aspect=st.components.photo_preserve_aspect)
        else:
            insert_photo(rp, blocks.photo_path, photo_box[0], photo_box[1],
                         preserve_aspect=st.components.photo_preserve_aspect)

    # P-3：accent_line.enabled=False 时不创建顶部强调线段（不写空段 /
    # w:pBdr / rule_sz）；True/None（旧路径与 P1/P2 不经 build_minimal）
    # 保持原行为：空段 + 底边框 + rule_sz 厚度。
    if draw_rule:
        rule = doc.add_paragraph()
        set_paragraph_spacing(rule, before=sp.rule_before, after=sp.rule_after,
                              line=0.5)
        _bottom_border(rule, st.palette.accent, sz=sp.rule_sz)

    idx = 1
    if blocks.summary:
        _minimal_title(doc, idx, "个人优势", st)
        idx += 1
        summary_p = doc.add_paragraph()
        set_paragraph_spacing(summary_p, before=sp.summary_before,
                              after=sp.summary_after, line=st.line_body)
        add_text(summary_p, blocks.summary, st.body_size,
                 color=st.palette.ink, name=st.font_family, latin_font=st.latin_font)

    _minimal_title(doc, idx, "教育经历", st)
    idx += 1
    for line in blocks.education_lines:
        ep = doc.add_paragraph()
        set_paragraph_spacing(ep, before=sp.edu_before, after=sp.edu_after,
                              line=st.line_body)
        add_text(ep, line, st.body_size, color=st.palette.ink,
                 name=st.font_family, latin_font=st.latin_font)

    if blocks.internships:
        _minimal_title(doc, idx, "实习经历", st)
        idx += 1
        _experience_blocks_minimal(doc, blocks.internships, st,
                                   body_width_cm=usable)

    if blocks.projects:
        _minimal_title(doc, idx, "项目经历", st)
        idx += 1
        _experience_blocks_minimal(doc, blocks.projects, st,
                                   body_width_cm=usable)

    if blocks.campus:
        _minimal_title(doc, idx, "校园经历", st)
        idx += 1
        for item in blocks.campus:
            _body_bullet(doc, item, st)

    _minimal_title(doc, idx, "专业技能与证书", st)
    for s in blocks.skills:
        _body_bullet(doc, s, st)
    if blocks.certs:
        cp = doc.add_paragraph()
        set_paragraph_spacing(cp, before=sp.certs_before,
                              after=sp.certs_after, line=st.line_body)
        add_text(cp, st.components.cert_label, st.body_size, bold=True,
                 color=st.palette.ink, name=st.font_family, latin_font=st.latin_font)
        add_text(cp, st.components.cert_separator.join(blocks.certs),
                 st.body_size, color=st.palette.ink, name=st.font_family, latin_font=st.latin_font)
    return doc


def build_sidebar(blocks: ResumeBlocks, palette: Palette,
                  overrides: Optional[RenderOverrides] = None):
    from docx import Document

    margins, usable, col_widths, photo_box = _resolve_layout(
        SKELETON_SIDEBAR, overrides)
    st = _resolve_context(SKELETON_SIDEBAR, palette, overrides)
    spacing = st.spacing
    w_left, w_right = col_widths
    cm_l = spacing.cell_left_cm
    cm_r = spacing.cell_right_cm
    # 右栏文本区宽（格宽减去左右内边距），格内右制表位按此定位
    right_text_w = cell_text_width_cm(w_right, cm_r[2], cm_r[3])

    doc = Document()
    setup_a4(doc, margins_cm=margins)
    _set_doc_default_font(doc, st)

    table = doc.add_table(rows=1, cols=2)
    clear_table_borders(table)
    set_table_fixed_layout(table, usable, col_widths)
    left, right = table.rows[0].cells
    set_cell_width(left, w_left)
    set_cell_width(right, w_right)
    shade_cell(left, st.palette.light_sidebar)
    set_cell_margins(left, top=cm_l[0], bottom=cm_l[1], left=cm_l[2], right=cm_l[3])
    set_cell_margins(right, top=cm_r[0], bottom=cm_r[1], left=cm_r[2], right=cm_r[3])

    lp = left.paragraphs[0]
    _apply_align(lp, st.components.photo_align)
    insert_photo(lp, blocks.photo_path, photo_box[0], photo_box[1],
                 preserve_aspect=st.components.photo_preserve_aspect)

    np = left.add_paragraph()
    _apply_align(np, st.components.identity_text_align)
    set_paragraph_spacing(np, before=spacing.id_name_before,
                          after=spacing.id_name_after, line=st.line_sidebar)
    add_text(np, blocks.name, st.name_size, bold=st.w_name,
             color=st.palette.sidebar_heading, name=st.font_family, latin_font=st.latin_font)

    ip = left.add_paragraph()
    _apply_align(ip, st.components.identity_text_align)
    set_paragraph_spacing(ip, before=spacing.id_intent_before,
                          after=spacing.id_intent_after, line=st.line_sidebar)
    add_text(ip, blocks.intent, st.intent_size, color=st.palette.accent,
             bold=True, name=st.font_family, latin_font=st.latin_font)

    _side_label(left, "联系方式", st)
    for line in blocks.contact_lines:
        cp = left.add_paragraph()
        set_paragraph_spacing(cp, before=spacing.id_contact_before,
                              after=spacing.id_contact_after,
                              line=st.line_sidebar)
        _apply_align(cp, st.components.contact_align)
        add_text(cp, line, st.sidebar_body_size, color=st.palette.ink,
                 name=st.font_family, latin_font=st.latin_font)

    if blocks.skills:
        _side_label(left, "专业技能", st)
        for s in blocks.skills:
            skp = left.add_paragraph()
            set_paragraph_spacing(skp, before=spacing.sidebar_item_before,
                                  after=spacing.sidebar_item_after,
                                  line=st.line_sidebar)
            add_text(skp, st.components.bullet_symbol
                     + st.components.bullet_gap + s,
                     st.sidebar_body_size, color=st.palette.ink,
                     name=st.font_family, latin_font=st.latin_font)

    if blocks.certs:
        _side_label(left, "证书", st)
        for c in blocks.certs:
            cp = left.add_paragraph()
            set_paragraph_spacing(cp, before=spacing.sidebar_cert_before,
                                  after=spacing.sidebar_cert_after,
                                  line=st.line_sidebar)
            add_text(cp, st.components.bullet_symbol
                     + st.components.bullet_gap + c,
                     st.sidebar_body_size, color=st.palette.ink,
                     name=st.font_family, latin_font=st.latin_font)

    if blocks.summary:
        _main_title(right, "个人优势", st)
        summary_p = right.add_paragraph()
        set_paragraph_spacing(summary_p, before=spacing.summary_before,
                              after=spacing.summary_after, line=st.line_body)
        add_text(summary_p, blocks.summary, st.body_size,
                 color=st.palette.ink, name=st.font_family, latin_font=st.latin_font)

    _main_title(right, "教育经历", st)
    for line in blocks.education_lines:
        ep = right.add_paragraph()
        set_paragraph_spacing(ep, before=spacing.edu_before,
                              after=spacing.edu_after, line=st.line_body)
        add_text(ep, line, st.body_size, color=st.palette.ink,
                 name=st.font_family, latin_font=st.latin_font)

    if blocks.internships:
        _main_title(right, "实习经历", st)
        _experience_in_cell(right, blocks.internships, st,
                            body_width_cm=right_text_w)

    if blocks.projects:
        _main_title(right, "项目经历", st)
        _experience_in_cell(right, blocks.projects, st,
                            body_width_cm=right_text_w)

    if blocks.campus:
        _main_title(right, "校园经历", st)
        for item in blocks.campus:
            bp = right.add_paragraph()
            set_paragraph_spacing(bp, before=spacing.sidebar_item_before,
                                  after=spacing.sidebar_item_after,
                                  line=st.line_body)
            add_text(bp, st.components.bullet_symbol
                     + st.components.bullet_gap + item,
                     st.body_size, color=st.palette.ink,
                     name=st.font_family, latin_font=st.latin_font)

    return doc


# ---- internals -------------------------------------------------------------

def _apply_align(paragraph, mode: str):
    """组件对齐槽位 → 段落对齐。

    "left" 不写 w:jc（OOXML 默认即左对齐），保证旧路径 XML 无多余节点；
    "right"/"center" 才写枚举。对齐语义属 Component 结构参数（3B-4）。
    """
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    if mode == "right":
        paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    elif mode == "center":
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER


def _set_doc_default_font(doc, style: RenderStyle):
    from docx.oxml.ns import qn

    normal = doc.styles["Normal"]
    normal.font.name = style.font_family
    # 10pt 仅为 Normal 工程基线；所有可见段落 run 均显式使用 style.* 字号
    normal.font.size = _pt(10)
    rFonts = normal.element.rPr.rFonts
    rFonts.set(qn("w:eastAsia"), style.font_family)
    # P-4：latin_font 非空时 Normal 默认西文槽位改写；None（旧路径/P1/P2）
    # 不产生任何多余 XML 写入，ascii/hAnsi 维持 font.name 的原值。
    if style.latin_font:
        rFonts.set(qn("w:ascii"), style.latin_font)
        rFonts.set(qn("w:hAnsi"), style.latin_font)


def _pt(n):
    from docx.shared import Pt

    return Pt(n)


def _space_str(v):
    """pBdr 的 w:space 取值格式化。

    OOXML ``ST_PointMeasure`` 是十进制 pt；Word 自身写整数。None 原样返回
    （由 _bottom_border 落到历史值 "1"）；整数值去掉小数点（0.0 → "0"），
    非整数保留有效位（0.5 → "0.5"）。
    """
    if v is None:
        return None
    f = float(v)
    if abs(f - round(f)) < 1e-9:
        return str(int(round(f)))
    return f"{f:g}"


def _bottom_border(paragraph, color: str, sz, *, border_space=None):
    """段落底边框。sz 为 OOXML 边框厚度（1/8 pt），必须由调用方从
    RenderSpacing 显式传入，本执行层不提供视觉默认值。

    border_space（v0.9.0）：``w:pBdr/w:bottom/@w:space``（pt）。None 时写
    历史值 "1"，旧路径与 P1/P2 字节级不变。
    """
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    pPr = paragraph._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), str(sz))
    bottom.set(qn("w:space"),
               str(border_space) if border_space is not None else "1")
    bottom.set(qn("w:color"), color.lstrip("#"))
    pBdr.append(bottom)
    pPr.append(pBdr)


def _divider_enabled(style: RenderStyle) -> bool:
    """P-5：板块 divider 启用判定（执行层，不做视觉决策）。

    section.divider.weight 经 3B-3 换算为 hairline_sz（1/8pt）：
      - <=0 / None：Spec 显式禁用（P1/P3 均声明 0pt=禁用）→ 不创建
        w:pBdr、不创建独立 divider 空段、不产生 hairline_before/after；
      - >0 但 palette.hairline 缺失：同样不绘制（避免 None.lstrip 崩溃）；
      - 旧路径三骨架 Profile hairline_sz=6 且 hairline 有色 → 恒启用，
        smoke 字节保值不受影响。
    标题段自身的 section_before / title_after 不在此判定内，保持不动。
    """
    sz = style.spacing.hairline_sz
    if not sz or sz <= 0:
        return False
    return style.palette.hairline is not None


def _emit_section_divider(doc, style: RenderStyle):
    """仅在 divider 启用时创建独立 hairline 段（含其专属段前/段后）。

    v0.9.0：divider 空段的固定行高（spec.section.divider.line_height）与
    pBdr 的 w:space（spec.section.divider.border_space）正式接通；两者
    None 时保持历史行为（自动行高 / space=1），旧路径字节不变。
    """
    if not _divider_enabled(style):
        return
    sp = style.spacing
    add_hairline(doc, style.palette.hairline,
                 before_pt=sp.hairline_before, after_pt=sp.hairline_after,
                 sz=sp.hairline_sz,
                 line_pt=sp.hairline_height,
                 border_space=_space_str(sp.hairline_border_space))


def _section_title(doc, text, style: RenderStyle, numbered=False):
    sp = style.spacing
    cp = style.components
    p = doc.add_paragraph()
    set_paragraph_spacing(p, before=sp.section_before,
                          after=sp.title_after, line=style.line_title)
    if numbered:
        prefix = ""
    else:
        prefix = (cp.section_title_symbol or "") + cp.section_title_gap
    add_text(p, prefix + text, style.title_size,
             bold=style.w_title, color=style.palette.ink,
             name=style.font_family, latin_font=style.latin_font)
    _emit_section_divider(doc, style)


def _numbered_title(doc, n: int, text: str, style: RenderStyle):
    sp = style.spacing
    cp = style.components
    p = doc.add_paragraph()
    set_paragraph_spacing(p, before=sp.section_before,
                          after=sp.title_after, line=style.line_title)
    number = (cp.title_numbering_template % n) if cp.title_numbering_template \
        else ""
    add_text(p, number + cp.title_numbering_gap, style.title_size,
             bold=style.w_title, color=style.palette.accent,
             name=style.font_family, latin_font=style.latin_font)
    add_text(p, text, style.title_size, bold=style.w_title,
             color=style.palette.ink, name=style.font_family,
             latin_font=style.latin_font)
    _emit_section_divider(doc, style)


def _symbol_title(doc, text: str, style: RenderStyle):
    """minimal 符号式板块标题（P3 symbol_hairline）：彩色符号 run + 标题 run。

    与 _numbered_title 的唯一差异：不输出编号 run；符号独立着色
    （components.section_title_symbol_color，缺省回退编号色 accent），
    标题文字保持 ink。段前/段后/行距一致；divider 由 P-5 闸门统一控制。
    """
    sp = style.spacing
    cp = style.components
    p = doc.add_paragraph()
    set_paragraph_spacing(p, before=sp.section_before,
                          after=sp.title_after, line=style.line_title)
    symbol_color = cp.section_title_symbol_color or style.palette.accent
    add_text(p, cp.section_title_symbol + cp.section_title_gap,
             style.title_size, bold=style.w_title, color=symbol_color,
             name=style.font_family, latin_font=style.latin_font)
    add_text(p, text, style.title_size, bold=style.w_title,
             color=style.palette.ink, name=style.font_family,
             latin_font=style.latin_font)
    _emit_section_divider(doc, style)


def _minimal_title(doc, n: int, text: str, style: RenderStyle):
    """minimal 板块标题分发：Spec symbol_hairline 解析到非空符号时走符号式
    （无编号）；旧路径及其余 title_style 保持 _numbered_title 原行为。"""
    if style.components.section_title_symbol:
        _symbol_title(doc, text, style)
    else:
        _numbered_title(doc, n, text, style)


def _education(doc, blocks: ResumeBlocks, style: RenderStyle):
    _section_title(doc, "教育经历", style)
    for line in blocks.education_lines:
        p = doc.add_paragraph()
        set_paragraph_spacing(p, before=style.spacing.edu_before,
                              after=style.spacing.edu_after,
                              line=style.line_body)
        add_text(p, line, style.body_size, color=style.palette.ink,
                 name=style.font_family, latin_font=style.latin_font)


def _add_experience_header(container, item, style: RenderStyle, *,
                           body_width_cm: float):
    """经历条目表头行：机构（黑粗）+ 角色（强调粗）+ 右对齐日期。

    日期用右对齐制表位定位（Phase 3A Bug4），不再用空格推位置：
    字体替换、日期长短变化都不会导致日期漂移。
    字号/字重/字体/颜色来自 RenderStyle（3B-1/3B-2），
    段前段后来自 RenderSpacing（3B-3），
    角色分隔符/日期模式/日期前缀来自 RenderComponents（3B-4），
    Renderer 不做视觉决策。
    """
    cp = style.components
    hp = container.add_paragraph()
    set_paragraph_spacing(hp, before=style.spacing.entry_before,
                          after=style.spacing.entry_after,
                          line=style.line_exp_header)
    add_text(hp, item.title, style.org_size, bold=style.w_org,
             color=style.palette.ink, name=style.font_family, latin_font=style.latin_font)
    if item.role:
        add_text(hp, cp.role_separator + item.role, style.role_size,
                 bold=style.w_role, color=style.palette.accent,
                 name=style.font_family, latin_font=style.latin_font)
    if item.meta:
        # date_mode 两种取值当前共用「右缘制表位」原语：
        # tab_stop = 版心右缘；column = 栏内右缘（body_width_cm 已由调用方
        # 按所在栏传入）。未来真双栏排版分化点留在这里。
        if cp.date_mode in ("tab_stop", "column"):
            add_right_tab_stop(hp, body_width_cm)
        add_text(hp, cp.date_prefix + item.meta, style.meta_size,
                 color=style.palette.muted, name=style.font_family, latin_font=style.latin_font)
    return hp


def _experience_section(doc, title, items, style: RenderStyle, *,
                        body_width_cm: float):
    if not items:
        return
    _section_title(doc, title, style)
    for item in items:
        _add_experience_header(doc, item, style,
                               body_width_cm=body_width_cm)
        if item.tags:
            tp = doc.add_paragraph()
            # tags 行行距属 experience/density 细化项，暂保持 1.0（未 Spec 化）
            set_paragraph_spacing(tp, before=style.spacing.tags_before,
                                  after=style.spacing.tags_after, line=1.0)
            add_text(tp, item.tags, style.tags_size,
                     color=style.palette.muted, name=style.font_family, latin_font=style.latin_font)
        for b in item.bullets:
            _body_bullet(doc, b, style)


def _experience_blocks_minimal(doc, items, style: RenderStyle, *,
                               body_width_cm: float):
    for item in items:
        _add_experience_header(doc, item, style,
                               body_width_cm=body_width_cm)
        for b in item.bullets:
            _body_bullet(doc, b, style)


def _experience_in_cell(cell, items, style: RenderStyle, *,
                        body_width_cm: float):
    for item in items:
        _add_experience_header(cell, item, style,
                               body_width_cm=body_width_cm)
        for b in item.bullets:
            bp = cell.add_paragraph()
            set_paragraph_spacing(bp, before=style.spacing.bullet_before,
                                  after=style.spacing.bullet_after,
                                  line=style.line_bullet)
            add_text(bp, style.components.bullet_symbol
                     + style.components.bullet_gap + b,
                     style.body_size, color=style.palette.ink,
                     name=style.font_family, latin_font=style.latin_font)


def _bullet_section(doc, title, items, style: RenderStyle):
    _section_title(doc, title, style)
    for item in items:
        _body_bullet(doc, item, style)


def _skills_certs(doc, blocks: ResumeBlocks, style: RenderStyle):
    if not blocks.skills and not blocks.certs:
        return
    _section_title(doc, "专业技能 / 证书", style)
    for s in blocks.skills:
        _body_bullet(doc, s, style)
    if blocks.certs:
        p = doc.add_paragraph()
        set_paragraph_spacing(p, before=style.spacing.certs_before,
                              after=style.spacing.certs_after,
                              line=style.line_body)
        add_text(p, style.components.cert_label, style.body_size, bold=True,
                 color=style.palette.ink, name=style.font_family, latin_font=style.latin_font)
        add_text(p, style.components.cert_separator.join(blocks.certs),
                 style.body_size, color=style.palette.ink,
                 name=style.font_family, latin_font=style.latin_font)


def _body_bullet(doc, text, style: RenderStyle):
    p = doc.add_paragraph()
    set_paragraph_spacing(p, before=style.spacing.bullet_before,
                          after=style.spacing.bullet_after,
                          line=style.line_bullet)
    # MIN_BODY_PT 仅作工程兜底；字号下限契约由 Validator 强制执行
    add_text(p, style.components.bullet_symbol
             + style.components.bullet_gap + text,
             max(style.body_size, MIN_BODY_PT),
             color=style.palette.ink, name=style.font_family, latin_font=style.latin_font)


def _side_label(cell, text, style: RenderStyle):
    p = cell.add_paragraph()
    set_paragraph_spacing(p, before=style.spacing.side_label_before,
                          after=style.spacing.side_label_after, line=1.0)
    cp = style.components
    if cp.side_label_transform == "upper_ascii":
        shown = text.upper() if text.isascii() else text
    else:
        shown = text
    add_text(p, shown,
             style.side_label_size, bold=style.w_side_label,
             color=style.palette.sidebar_heading, name=style.font_family, latin_font=style.latin_font)
    _bottom_border(p, style.palette.accent, sz=style.spacing.side_label_sz)


def _main_title(cell, text, style: RenderStyle):
    p = cell.add_paragraph()
    # sidebar 标题边框附在标题段：after 同时承担 divider→首行
    set_paragraph_spacing(p, before=style.spacing.section_before,
                          after=style.spacing.hairline_after,
                          line=style.line_title)
    cp = style.components
    add_text(p, (cp.section_title_symbol or "") + cp.section_title_gap + text,
             style.title_size, bold=style.w_title,
             color=style.palette.ink, name=style.font_family, latin_font=style.latin_font)
    # P-5：divider.weight<=0 / hairline 无色时不附边框（P2=0.5pt、旧路径=6
    # 均 >0，行为字节级不变）
    if _divider_enabled(style):
        _bottom_border(p, style.palette.hairline, sz=style.spacing.hairline_sz,
                       border_space=_space_str(
                           style.spacing.hairline_border_space))
