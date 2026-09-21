# -*- coding: utf-8 -*-
"""render_style.py — DesignSpec → Renderer 的排版参数解析层（Phase 3B-1）。

链路位置：
    DesignSpec（应该长什么样）
        ↓ 本模块：字段级解析 / 令牌映射 / 缺口回退
    RenderStyle（Renderer 唯一可读的排版参数包，纯数值、不可变）
        ↓
    skeletons（只决定如何用 python-docx 实现，不再做视觉决策）

原则：
    1. Renderer 禁止再出现字号/字体/行距字面量作为最终视觉决策；
       旧路径（无 Spec）使用「骨架默认 Profile」，取值 = 改造前审计原值，
       保证 build_document(blocks, skeleton_id) 视觉不变。
    2. Spec 中 undetermined 的字段绝不编造，回退到骨架 Profile，
       并在 RenderStyle.spec_fallbacks 中登记，供报告与后续审计。
    3. TypographySpec 由 Phase 3B-1 解析；ColorSpec 由 Phase 3B-2 解析；
       间距/组件后续 Phase 接入。
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, List, Optional, Tuple

from resume_generator.layout_kit import (
    FONT_CN,
    Palette,
    SKELETON_BANNER,
    SKELETON_MINIMAL,
    SKELETON_SIDEBAR,
)

# ---------------------------------------------------------------------------
# 字体令牌映射（工程决策：Spec 只给字体令牌/名称，Renderer 按本机可用字体落地）
# 候选名统一落到中文环境最稳的族名，ascii / eastAsia 写同一个值。
# ---------------------------------------------------------------------------

_FONT_TOKEN_MAP = {
    "sans_zh": "微软雅黑",
    "microsoft yahei": "微软雅黑",
    "微软雅黑": "微软雅黑",
}


def resolve_font_family(spec_value: Any) -> str:
    """把 Spec 的字体令牌/名称映射为本机字体族名；无法识别时原样返回。"""
    if not spec_value:
        return FONT_CN
    key = str(spec_value).strip().lower()
    return _FONT_TOKEN_MAP.get(key, str(spec_value).strip())


def resolve_latin_font(spec_value: Any) -> Optional[str]:
    """TypographySpec.latin_font → 西文字体族名。

    None / undetermined / not_applicable（value=None）→ None，
    表示与 font_family 共用（旧路径与 P1/P2 行为保值，ascii/hAnsi/eastAsia
    写同一字体）；明确字符串（如 P3 "ArialMT"）原样透传给 set_run_font。
    """
    if spec_value is None:
        return None
    if getattr(spec_value, "is_undetermined", False):
        return None
    val = getattr(spec_value, "value", None)
    if isinstance(val, str) and val.strip():
        return val.strip()
    return None


# ---------------------------------------------------------------------------
# RenderPalette：Renderer 唯一消费的颜色参数包（Phase 3B-2）
#
# 字段名严格对齐 DesignSpec ColorSpec 的颜色角色（角色即稳定 API）：
#   ink / accent / muted / paper / hairline / dark_block / light_sidebar /
#   on_dark_primary / on_dark_secondary / on_dark_tertiary
# 另含一个渲染槽位：
#   sidebar_heading —— 浅侧栏上的姓名/分组标签深色文字。
#     ColorSpec 无此角色（Schema Gap，P2 范式把姓名定义在主栏），
#     永远由骨架 Profile 提供，Spec 路径显式登记 fallback，不猜测、不新增 Schema。
# 某骨架不消费的角色为 None（如 minimal 无 dark_block），Renderer 不得读取。
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RenderPalette:
    ink: Optional[str] = None
    accent: Optional[str] = None
    muted: Optional[str] = None
    paper: Optional[str] = None
    hairline: Optional[str] = None
    dark_block: Optional[str] = None
    light_sidebar: Optional[str] = None
    on_dark_primary: Optional[str] = None
    on_dark_secondary: Optional[str] = None
    on_dark_tertiary: Optional[str] = None
    sidebar_heading: Optional[str] = None


# banner 深块上的三个固定文字色：改造前 builder 硬编码值，现正式登记为
# 「Skeleton Default Palette」。它们与运行时所选行业色板无关（旧行为如此），
# 仅 Spec 路径才由 ColorSpec.on_dark_* 覆盖。禁止"顺手规范化"。
_BANNER_ON_DARK_PRIMARY = "#FFFFFF"    # 深块上的姓名（原硬编码）
_BANNER_ON_DARK_SECONDARY = "#EAECEE"  # 深块上的联系方式行（原硬编码）
_BANNER_ON_DARK_TERTIARY = "#F7DC6F"   # 深块上的意向标签（原硬编码，骨架黄）


def build_palette_for_skeleton(skeleton_id: str,
                               palette: Palette) -> RenderPalette:
    """旧路径：把行业 Palette 的 7 个字段按骨架语义映射到标准颜色角色。

    Palette.header / Palette.rule 在不同骨架中语义重载，在此一次性消解，
    Renderer 内不再出现 header/rule 这类歧义引用。
    """
    common = dict(
        ink=palette.ink, accent=palette.accent, muted=palette.muted,
        paper=palette.paper,
    )
    if skeleton_id == SKELETON_BANNER:
        # 深块横幅：header=深块底；rule=发丝线；三个深块文字色固定
        return RenderPalette(
            **common,
            hairline=palette.rule,
            dark_block=palette.header,
            on_dark_primary=_BANNER_ON_DARK_PRIMARY,
            on_dark_secondary=_BANNER_ON_DARK_SECONDARY,
            on_dark_tertiary=_BANNER_ON_DARK_TERTIARY,
        )
    if skeleton_id == SKELETON_MINIMAL:
        # 单栏：rule=发丝线；无深块/侧栏
        return RenderPalette(**common, hairline=palette.rule)
    if skeleton_id == SKELETON_SIDEBAR:
        # 浅侧栏：rule 同时是侧栏浅底与发丝线（旧行为，保持同源）；
        # header 复用为侧栏深色文字（sidebar_heading，Spec 无对应角色）
        return RenderPalette(
            **common,
            hairline=palette.rule,
            light_sidebar=palette.rule,
            sidebar_heading=palette.header,
        )
    raise KeyError(f"未知骨架 {skeleton_id}")


# 各骨架实际消费的颜色角色（只对这些角色做 Spec 覆盖与 fallback 登记，
# 不消费的角色不产生无意义 warning）
_COLOR_ROLES_BY_SKELETON = {
    SKELETON_BANNER: (
        "ink", "accent", "muted", "hairline", "dark_block",
        "on_dark_primary", "on_dark_secondary", "on_dark_tertiary",
    ),
    SKELETON_MINIMAL: ("ink", "accent", "muted", "hairline"),
    SKELETON_SIDEBAR: (
        "ink", "accent", "muted", "hairline", "light_sidebar",
    ),
}


def _resolve_colors_for_spec(spec, skeleton_id: str,
                             base_palette: RenderPalette,
                             fb: List[str]) -> RenderPalette:
    """ColorSpec → RenderPalette：逐角色覆盖；None/undetermined 回退 Profile。

    - ColorSpec 字段为 None：该范式显式不使用此角色；若骨架仍消费则回退登记。
    - Sourced.is_undetermined：知识缺口，回退 Profile 并登记。
    - 其余（含 derived/observed）：原样使用值，Renderer 不猜测、不替换 token；
      非 hex 值的合法性属于 Validator 职责，本函数不静默改写。
    """
    colors = spec.colors
    resolved: dict = {}
    for role in _COLOR_ROLES_BY_SKELETON[skeleton_id]:
        sourced = getattr(colors, role, None)
        fallback = getattr(base_palette, role)
        if sourced is None:
            resolved[role] = fallback
            fb.append(f"colors.{role}<not_defined>")
        elif getattr(sourced, "is_undetermined", False):
            resolved[role] = fallback
            fb.append(f"colors.{role}")
        else:
            resolved[role] = str(sourced.value)

    # sidebar_heading 是渲染槽位，ColorSpec 无对应角色（Schema Gap）
    if skeleton_id == SKELETON_SIDEBAR:
        resolved["sidebar_heading"] = base_palette.sidebar_heading
        fb.append("colors.sidebar_heading<schema_gap>")

    # paper 当前无渲染消费点；有值则透传备用，不登记 fallback
    if colors.paper is not None and not colors.paper.is_undetermined:
        resolved["paper"] = str(colors.paper.value)
    else:
        resolved["paper"] = base_palette.paper

    # 该骨架不消费的角色保留 Profile（通常为 None）
    for role in ("dark_block", "light_sidebar",
                 "on_dark_primary", "on_dark_secondary", "on_dark_tertiary",
                 "sidebar_heading"):
        resolved.setdefault(role, getattr(base_palette, role))
    return RenderPalette(**resolved)


# ---------------------------------------------------------------------------
# RenderSpacing：Renderer 唯一消费的间距参数包（Phase 3B-3）
#
# 单位约定：段前/段后均为 pt；*_sz 为 OOXML 边框厚度单位 1/8 pt；
#           cell_*_cm 为 (上, 下, 左, 右) cm 四元组（页面边距不在此层）。
# 角色按设计语义拆分，禁止「一个 spacing 数值到处用」。
# 某骨架不消费的槽位为 None（如 minimal 无 cell 边距/无 banner 色条）。
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RenderSpacing:
    # --- 板块标题 / divider ---
    section_before: float          # 标题段前（spec.section.spacing_before）
    title_after: float             # 标题行后（标题文字 → divider）
    hairline_before: float         # 独立 divider 段的段前
    hairline_after: float          # divider → 首行（spec.divider_to_first_line）
    hairline_sz: int               # divider 厚度 1/8pt（spec.divider.weight）
    # --- 经历 / bullet / 标签链 ---
    entry_before: float            # 经历条目前（= 条目间距 entry_spacing）
    entry_after: float
    bullet_before: float
    bullet_after: float            # spec.experience.bullet_spacing_after
    # v0.9.0：divider 空段的固定行高（pt，None=自动）与 pBdr 的 w:space（pt）。
    # 这两个槽位此前是 schema_gap，每份简历都得靠一次性脚本后处理。
    hairline_height: Optional[float] = None
    hairline_border_space: Optional[float] = None
    tags_before: Optional[float] = None
    tags_after: Optional[float] = None
    # --- 普通板块尾距 ---
    summary_before: float = 0.0
    summary_after: float = 0.0
    edu_before: float = 0.0
    edu_after: float = 0.0
    certs_before: Optional[float] = None
    certs_after: Optional[float] = None
    # --- 身份区内部（banner/minimal/sidebar 各有审计原值）---
    id_name_before: float = 0.0
    id_name_after: float = 0.0
    id_intent_before: float = 0.0
    id_intent_after: float = 0.0
    id_contact_before: float = 0.0
    id_contact_after: float = 0.0
    id_photo_before: Optional[float] = None
    id_photo_after: Optional[float] = None
    # --- banner 身份区底部强调色条（spec.header.accent_line.height）---
    bar_before: Optional[float] = None
    bar_after: Optional[float] = None
    bar_sz: Optional[int] = None
    # --- minimal 身份区下分隔线（无对应 Spec 范式，永久 Profile）---
    rule_before: Optional[float] = None
    rule_after: Optional[float] = None
    rule_sz: Optional[int] = None
    # --- sidebar 侧栏分组标签 / 侧栏条目节奏 ---
    side_label_before: Optional[float] = None
    side_label_after: Optional[float] = None
    side_label_sz: Optional[int] = None
    sidebar_item_before: Optional[float] = None
    sidebar_item_after: Optional[float] = None    # 技能/校园等非经历条目
    sidebar_cert_before: Optional[float] = None
    sidebar_cert_after: Optional[float] = None
    # --- cell 内边距（cm，上/下/左/右）；与 Page Margin 严格分离 ---
    cell_left_cm: Optional[Tuple[float, float, float, float]] = None
    cell_right_cm: Optional[Tuple[float, float, float, float]] = None


# 渲染槽位 → Spec 取值路径。只登记 DesignSpec 已明确表达的间距语义；
# DensitySpec.section_spacing 是 density 节点的镜像杠杆（density 不属本阶段），
# 故以 SectionSpec.spacing_before 为权威来源。
# Phase 2B-5 Step 1：title_after / entry_after 正式从 Spec 取值，取代旧路径
# 「永久 Profile」回退（P1/P2/P3 默认值已与各骨架 Profile 保值）。
# v0.9.0（2026-09-21）：hairline_before / hairline_height /
# hairline_border_space / summary_after / edu_after 五个 schema_gap 槽位
# 正式接到 Spec（SectionSpec / Divider 新增字段）。此前它们只能取骨架
# Profile，导致「每份简历都要写一段后处理脚本才能调分割线与普通板块节奏」。
_SPACING_SPEC_SOURCES = {
    "section_before": lambda s: s.section.spacing_before,
    "title_after": lambda s: s.section.title_spacing_after,
    "hairline_before": lambda s: s.section.divider_spacing_before,
    "hairline_after": lambda s: s.section.divider_to_first_line,
    "hairline_sz": lambda s: s.section.divider.weight,
    "hairline_height": lambda s: s.section.divider.line_height,
    "hairline_border_space": lambda s: s.section.divider.border_space,
    "entry_before": lambda s: s.experience.entry_spacing,
    "entry_after": lambda s: s.experience.entry_spacing_after,
    "bullet_after": lambda s: s.experience.bullet_spacing_after,
    "summary_after": lambda s: s.section.summary_spacing_after,
    "edu_after": lambda s: s.section.education_spacing_after,
    "bar_sz": lambda s: (s.header.accent_line.height
                         if s.header.accent_line is not None
                         and s.header.accent_line.enabled else None),
}

# pt 值需要换算成 OOXML 边框 1/8pt 的槽位
_SPACING_EIGHTH_PT = {"hairline_sz", "bar_sz"}

# 各骨架实际消费的间距槽位；未列入的槽位（None）不产生 fallback 登记。
_SPACING_ROLES_BY_SKELETON = {
    SKELETON_BANNER: (
        "section_before", "title_after", "hairline_before", "hairline_after",
        "hairline_sz", "hairline_height", "hairline_border_space",
        "entry_before", "entry_after", "bullet_before", "bullet_after",
        "tags_before", "tags_after",
        "summary_before", "summary_after", "edu_before", "edu_after",
        "certs_before", "certs_after",
        "id_name_before", "id_name_after", "id_intent_before",
        "id_intent_after", "id_contact_before", "id_contact_after",
        "id_photo_before", "id_photo_after",
        "bar_before", "bar_after", "bar_sz",
        "cell_left_cm", "cell_right_cm",
    ),
    SKELETON_MINIMAL: (
        "section_before", "title_after", "hairline_before", "hairline_after",
        "hairline_sz", "hairline_height", "hairline_border_space",
        "entry_before", "entry_after", "bullet_before", "bullet_after",
        "summary_before", "summary_after", "edu_before", "edu_after",
        "certs_before", "certs_after",
        "id_name_before", "id_name_after", "id_intent_before",
        "id_intent_after", "id_contact_before", "id_contact_after",
        "rule_before", "rule_after", "rule_sz",
    ),
    SKELETON_SIDEBAR: (
        # sidebar 标题边框直接附在标题段（无独立 divider 段）：
        # 标题段 after 即 divider→首行，title_after/hairline_before 不消费；
        # 同理没有独立空段，hairline_height 不消费（行高即标题行高）。
        "section_before", "hairline_after", "hairline_sz",
        "hairline_border_space",
        "entry_before", "entry_after", "bullet_before", "bullet_after",
        "summary_before", "summary_after", "edu_before", "edu_after",
        "id_name_before", "id_name_after", "id_intent_before",
        "id_intent_after", "id_contact_before", "id_contact_after",
        "side_label_before", "side_label_after", "side_label_sz",
        "sidebar_item_before", "sidebar_item_after",
        "sidebar_cert_before", "sidebar_cert_after",
        "cell_left_cm", "cell_right_cm",
    ),
}


def _spacing_value(sourced, fallback):
    """返回 (值, 状态)；状态：ok / not_defined / undetermined。

    厚度槽位（pt）由调用方负责 *8 换算；cm 元组槽位不经此函数。
    """
    if sourced is None:
        return fallback, "not_defined"
    if getattr(sourced, "is_undetermined", False):
        return fallback, "undetermined"
    val = getattr(sourced, "value", None)
    if isinstance(val, (int, float)):
        return float(val), "ok"
    return fallback, "not_defined"


def _resolve_spacing_for_spec(spec, skeleton_id: str,
                              base: RenderSpacing,
                              fb: List[str]) -> RenderSpacing:
    """SpacingSpec → RenderSpacing：逐槽位覆盖；缺失/未确定回退 Profile。

    - Spec 无对应设计概念的槽位：永久 Profile，登记 <schema_gap>（不脑补）。
    - 字段存在但值为 None：登记 <not_defined>。
    - undetermined：登记裸键名（与 Typography/Color 口径一致）。
    - page margin 属 Phase 3A 几何层，cell margin 在此层且单位 cm，二者不混。
    """
    resolved = {}
    for role in _SPACING_ROLES_BY_SKELETON[skeleton_id]:
        fallback = getattr(base, role)
        extractor = _SPACING_SPEC_SOURCES.get(role)
        if extractor is None:
            # 该骨架消费但 DesignSpec 无此设计概念
            resolved[role] = fallback
            fb.append(f"spacing.{role}<schema_gap>")
            continue
        try:
            sourced = extractor(spec)
        except AttributeError:
            sourced = None
        val, status = _spacing_value(sourced, fallback)
        if status == "ok" and role in _SPACING_EIGHTH_PT:
            val = int(round(val * 8))
        resolved[role] = val
        if status == "not_defined":
            fb.append(f"spacing.{role}<not_defined>")
        elif status == "undetermined":
            fb.append(f"spacing.{role}")
    return replace(base, **resolved)


# ---------------------------------------------------------------------------
# RenderComponents：Renderer 唯一消费的组件结构参数包（Phase 3B-4）
#
# 这里只回答「组件本身怎么组织」：marker / 分隔符 / 编号 / 对齐模式 /
# 等比保护等。颜色仍归 RenderPalette，间距仍归 RenderSpacing，
# 字号字重行距仍归 RenderStyle 扁平字段，不重复建模。
# 某骨架不消费的槽位为 None（如 minimal 无 ▍符号、sidebar 无证书标签行）。
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RenderComponents:
    # --- SectionTitle：符号式标题（banner/sidebar）---
    section_title_symbol: Optional[str] = None   # "▍"；None = 该骨架不用符号
    section_title_gap: str = ""                  # 符号 → 标题文字的间隙
    # --- SectionTitle：编号式标题（minimal）---
    title_numbering_template: Optional[str] = None  # printf 模板，如 "%02d"
    title_numbering_gap: str = ""                   # 编号 → 标题文字的间隙
    # 符号式标题符号颜色（hex）：仅 minimal Spec symbol_hairline 路径解析；
    # None = 旧行为（banner/sidebar 符号与文字同色 ink；minimal 走编号式）
    section_title_symbol_color: Optional[str] = None
    # --- ExperienceHeader：角色分隔符 / 日期定位 ---
    role_separator: str = ""       # 机构 → 角色；banner"  ·  " / minimal"  "
    date_mode: str = "tab_stop"    # tab_stop / column（当前均以右制表位落地）
    date_prefix: str = ""          # 日期 run 前缀（"\t"，禁止空格推位置）
    # --- Bullet：marker 与正文同 run（独立着色/悬挂缩进见能力缺口登记）---
    bullet_symbol: str = "·"
    bullet_gap: str = " "
    # --- 证书行（banner/minimal；sidebar 证书走 bullet 列表，不消费）---
    cert_label: Optional[str] = None   # "证书  " / "证书资质  "
    cert_separator: str = "  ·  "
    # --- 侧栏分组标签大小写变换：upper_ascii / None ---
    side_label_transform: Optional[str] = None
    # --- 身份区 / 联系方式 / 照片对齐（"left" = 不写 w:jc，保持 OOXML 默认）---
    identity_text_align: str = "left"
    contact_align: str = "left"
    photo_align: str = "right"
    # --- Photo 等比硬规则（Spec：distortion_allowed 必须为 False）---
    photo_preserve_aspect: bool = True


# 组件槽位 → Spec 取值路径。只登记 DesignSpec 已表达的组件结构语义。
# 普通字符串字段（非 Sourced）：None / 非空串判定；不经过 Sourced 状态机。
_COMPONENT_SPEC_SOURCES = {
    "section_title_symbol": lambda s: s.section.prefix,
    "role_separator": lambda s: s.experience.role.separator,
    "bullet_symbol": lambda s: s.experience.bullet.symbol,
    "date_mode": lambda s: s.experience.date_alignment,
}

# header.identity_alignment 复合描述 → (身份文字对齐, 照片对齐)
_IDENTITY_ALIGNMENT_MAP = {
    "left_text_right_photo": ("left", "right"),
    "photo_center_aligns_name_baseline_band": ("center", "center"),
}

# date_mode 允许的 Spec 取值（spaces 由 Validator 拒绝，这里再守一次）
_DATE_MODES = ("tab_stop", "column")

# 与 design.spec.TITLE_SYMBOL 同源（本层按 _DATE_MODES 同口径保留本地常量）：
# minimal 仅在该标题模式下才把 section.prefix 解析为标题符号。
_TITLE_STYLE_SYMBOL = "symbol_hairline"
# minimal 符号式标题的符号→文字间隙：与 banner/sidebar Profile 同为一个
# 半角空格的组装规则（尾空格不进 Spec；Spec 只给 title_indent 厘米值，本阶段不消费）
_SYMBOL_TITLE_GAP = " "
# section.symbol_color_role 允许映射的 RenderPalette 颜色角色
_SYMBOL_COLOR_DEFAULT_ROLE = "accent"
_SYMBOL_COLOR_ROLES = frozenset(
    ("ink", "accent", "muted", "paper", "hairline"))

# 各骨架实际消费的组件槽位；未列入的槽位不产生 fallback 登记。
_COMPONENT_ROLES_BY_SKELETON = {
    SKELETON_BANNER: (
        "section_title_symbol", "section_title_gap",
        "role_separator", "date_mode", "date_prefix",
        "bullet_symbol", "bullet_gap",
        "cert_label", "cert_separator",
        "identity_text_align", "contact_align", "photo_align",
        "photo_preserve_aspect",
    ),
    SKELETON_MINIMAL: (
        "title_numbering_template", "title_numbering_gap",
        "role_separator", "date_mode", "date_prefix",
        "bullet_symbol", "bullet_gap",
        "cert_label", "cert_separator",
        "identity_text_align", "contact_align", "photo_align",
        "photo_preserve_aspect",
    ),
    SKELETON_SIDEBAR: (
        "section_title_symbol", "section_title_gap",
        "role_separator", "date_mode", "date_prefix",
        "bullet_symbol", "bullet_gap",
        "side_label_transform",
        "identity_text_align", "contact_align", "photo_align",
        "photo_preserve_aspect",
    ),
}


def _sourced_str(sourced, fallback):
    """Sourced(字符串值) → (值, ok/not_defined/undetermined)。"""
    if sourced is None:
        return fallback, "not_defined"
    if getattr(sourced, "is_undetermined", False):
        return fallback, "undetermined"
    val = getattr(sourced, "value", None)
    if isinstance(val, str) and val != "":
        return val, "ok"
    return fallback, "not_defined"


def _resolve_symbol_title_color(spec, palette: RenderPalette,
                                fb: List[str]) -> Optional[str]:
    """section.symbol_color_role → 已解析 RenderPalette 角色的颜色 hex。

    角色名与 RenderPalette 字段同源（accent/ink/…）；未知角色回退 accent
    （SectionSpec.symbol_color_role 的默认角色）。角色颜色缺失（None）时
    登记并返回 None，由 Renderer 回退当前编号色 palette.accent。
    """
    role = getattr(spec.section, "symbol_color_role",
                   _SYMBOL_COLOR_DEFAULT_ROLE)
    if not isinstance(role, str) or role not in _SYMBOL_COLOR_ROLES:
        role = _SYMBOL_COLOR_DEFAULT_ROLE
    color = getattr(palette, role, None)
    if color is None:
        fb.append("components.section_title_symbol_color<not_defined>")
        return None
    return str(color)


def _resolve_components_for_spec(spec, skeleton_id: str,
                                 base: RenderComponents,
                                 fb: List[str],
                                 palette: Optional[RenderPalette] = None,
                                 ) -> RenderComponents:
    """组件 Spec → RenderComponents：逐槽位覆盖；缺失/未确定回退 Profile。

    - Spec 无对应设计概念的槽位：永久 Profile，登记 <schema_gap>。
    - 图标式标题（icon_hairline）资源缺口：登记 <capability_gap>，
      回退 section.prefix 符号（Renderer 无图标库，禁止自造图标）。
    - 复合身份对齐 header.identity_alignment 一次解析两个对齐槽位。
    - minimal 仅在 title_style=symbol_hairline 时把 section.prefix 解析为
      标题符号（含 symbol_color_role 符号色）；其余模式保持编号式 Profile。
    """
    resolved = {}

    # --- 复合字段 1：身份文字对齐 + 照片对齐 ---
    id_desc = None
    try:
        id_desc = spec.header.identity_alignment
    except AttributeError:
        id_desc = None
    id_pair = _IDENTITY_ALIGNMENT_MAP.get(id_desc) if id_desc else None
    if id_pair is not None:
        resolved["identity_text_align"], resolved["photo_align"] = id_pair
    else:
        resolved["identity_text_align"] = base.identity_text_align
        resolved["photo_align"] = base.photo_align
        fb.append("components.identity_alignment<not_defined>")

    # --- 复合字段 2：照片等比保护（bool，Validator 已禁止 distortion）---
    try:
        resolved["photo_preserve_aspect"] = \
            not bool(spec.photo.distortion_allowed)
    except AttributeError:
        resolved["photo_preserve_aspect"] = base.photo_preserve_aspect
        fb.append("components.photo_preserve_aspect<not_defined>")

    # --- 图标标题能力缺口：只登记，渲染回退符号标题 ---
    try:
        if spec.section.title_style == "icon_hairline":
            icon_res = spec.section.icon.resource
            if icon_res is None or icon_res.is_undetermined:
                fb.append("components.section_icon<capability_gap>")
    except AttributeError:
        pass

    # --- minimal 符号式标题（P3 symbol_hairline）---
    # 仅该模式下 section.prefix 才成为标题符号；其余 title_style（含旧路径）
    # minimal 继续走 01 编号式：section_title_symbol 保持 Profile 的 None。
    # banner/sidebar 不经此块，其符号标题解析与颜色行为完全不变。
    if skeleton_id == SKELETON_MINIMAL:
        symbol = None
        try:
            if spec.section.title_style == _TITLE_STYLE_SYMBOL:
                symbol, sym_status = _sourced_str(
                    spec.section.prefix, base.section_title_symbol)
                if sym_status == "not_defined":
                    fb.append(
                        "components.section_title_symbol<not_defined>")
                elif sym_status == "undetermined":
                    fb.append("components.section_title_symbol")
        except AttributeError:
            symbol = None
        resolved["section_title_symbol"] = symbol
        if symbol:
            # 符号→文字间隙是组装规则（同 banner/sidebar Profile），Spec 无槽位
            resolved["section_title_gap"] = _SYMBOL_TITLE_GAP
            fb.append("components.section_title_gap<schema_gap>")
            if palette is not None:
                resolved["section_title_symbol_color"] = \
                    _resolve_symbol_title_color(spec, palette, fb)

    for role in _COMPONENT_ROLES_BY_SKELETON[skeleton_id]:
        if role in resolved:
            continue  # 复合字段已解析
        fallback = getattr(base, role)
        extractor = _COMPONENT_SPEC_SOURCES.get(role)
        if extractor is None:
            resolved[role] = fallback          # Spec 无此设计概念
            fb.append(f"components.{role}<schema_gap>")
            continue
        try:
            raw = extractor(spec)
        except AttributeError:
            raw = None
        if role == "section_title_symbol":
            val, status = _sourced_str(raw, fallback)
        elif role in ("role_separator", "bullet_symbol"):
            # 普通字符串字段：非空即用；None/空串 = 未定义 → Profile
            if isinstance(raw, str) and raw != "":
                val, status = raw, "ok"
            else:
                val, status = fallback, "not_defined"
        elif role == "date_mode":
            if raw in _DATE_MODES:
                val, status = raw, "ok"
            else:
                val, status = fallback, "not_defined"
        else:
            val, status = fallback, "not_defined"
        resolved[role] = val
        if status == "not_defined":
            fb.append(f"components.{role}<not_defined>")
        elif status == "undetermined":
            fb.append(f"components.{role}")
    return replace(base, **resolved)


# ---------------------------------------------------------------------------
# RenderStyle：Renderer 唯一消费的排版参数包
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RenderStyle:
    """已解析的排版参数（单位：字号 pt；行距为倍数）。

    字号角色：
        name / intent / contact   身份区
        title                     板块标题
        org / role / meta / tags  经历表头与标签链
        body                      正文 / 教育 / bullet / 证书
        side_label / sidebar_body 双栏骨架侧栏
    行距角色：
        line_body        正文段落
        line_bullet      bullet 段落（旧骨架与正文有 0.02 级差异，独立保留）
        line_title       板块标题行
        line_exp_header  经历表头行（机构/角色/日期同行）
        line_sidebar     侧栏短行
    字重：对应 TypographyWeights 的 5 个粗体角色（正文/元数据恒 regular）。
    """

    font_family: str
    name_size: float
    intent_size: float
    contact_size: float
    title_size: float
    org_size: float
    role_size: float
    body_size: float
    meta_size: float
    tags_size: float
    side_label_size: float
    sidebar_body_size: float
    line_body: float
    line_bullet: float
    line_title: float
    line_exp_header: float
    line_sidebar: float
    w_name: bool = True
    w_title: bool = True
    w_org: bool = True
    w_role: bool = True
    w_side_label: bool = True
    source: str = "skeleton_default"   # skeleton_default / design_spec
    spec_fallbacks: Tuple[str, ...] = field(default=())
    palette: Optional[RenderPalette] = None  # Phase 3B-2；旧 Profile 构建时挂载
    spacing: Optional[RenderSpacing] = None  # Phase 3B-3；骨架 Profile 内嵌审计原值
    components: Optional[RenderComponents] = None  # Phase 3B-4；组件结构参数
    # P-4：西文字体（ascii/hAnsi）；None = 与 font_family 共用，旧路径与
    # P1/P2 三槽位写同一字体（字节保值）；P3 由 typography.latin_font 解析
    latin_font: Optional[str] = None


# ---------------------------------------------------------------------------
# 骨架默认 Profile：改造前硬编码值的唯一登记处（旧路径视觉保值）
# ---------------------------------------------------------------------------

def _profile(**kw) -> RenderStyle:
    return RenderStyle(font_family=FONT_CN, **kw)


# 间距骨架默认值：逐 pt / 逐 cm 审计自改造前 skeletons.py / _LAYOUT_CONFIG，
# 旧路径消费它们必须产出与改造前完全相同的 DOCX（见 smoke 字节数保值）。
_DEFAULT_SPACING = {
    SKELETON_BANNER: RenderSpacing(
        section_before=5, title_after=1, hairline_before=0,
        hairline_after=3, hairline_sz=6,
        entry_before=2, entry_after=1, bullet_before=0, bullet_after=1.5,
        tags_before=0, tags_after=1,
        summary_before=0, summary_after=6, edu_before=0, edu_after=4,
        certs_before=2, certs_after=0,
        id_name_before=0, id_name_after=2,
        id_intent_before=0, id_intent_after=4,
        id_contact_before=0, id_contact_after=0,
        id_photo_before=0, id_photo_after=0,
        bar_before=0, bar_after=8, bar_sz=18,
        cell_left_cm=(0.25, 0.25, 0.35, 0.2),
        cell_right_cm=(0.2, 0.2, 0.1, 0.25),
    ),
    SKELETON_MINIMAL: RenderSpacing(
        section_before=5, title_after=1, hairline_before=0,
        hairline_after=3, hairline_sz=6,
        # minimal 各 bullet 走共享 _body_bullet（审计原值 1.5，勿与
        # sidebar cell 内 bullet 的 1.0 混淆）
        entry_before=3, entry_after=1, bullet_before=0, bullet_after=1.5,
        summary_before=0, summary_after=6, edu_before=0, edu_after=4,
        certs_before=2, certs_after=0,
        id_name_before=0, id_name_after=0,
        id_intent_before=2, id_intent_after=4,
        id_contact_before=0, id_contact_after=0,
        rule_before=4, rule_after=7, rule_sz=12,
    ),
    SKELETON_SIDEBAR: RenderSpacing(
        section_before=6, title_after=2, hairline_before=0,
        hairline_after=2, hairline_sz=6,
        entry_before=2, entry_after=1, bullet_before=0, bullet_after=1,
        summary_before=0, summary_after=6, edu_before=0, edu_after=4,
        id_name_before=8, id_name_after=2,
        id_intent_before=0, id_intent_after=8,
        id_contact_before=0, id_contact_after=1,
        side_label_before=10, side_label_after=3, side_label_sz=8,
        sidebar_item_before=0, sidebar_item_after=2,
        sidebar_cert_before=0, sidebar_cert_after=1,
        cell_left_cm=(0.3, 0.3, 0.28, 0.28),
        cell_right_cm=(0.2, 0.2, 0.4, 0.2),
    ),
}


# 组件结构骨架默认值：逐字符审计自改造前 skeletons.py（"· "/"▍ "/"  ·  "等），
# 旧路径消费它们必须产出与改造前完全相同的 DOCX（见 smoke 字节数保值）。
_DEFAULT_COMPONENTS = {
    SKELETON_BANNER: RenderComponents(
        section_title_symbol="▍", section_title_gap=" ",
        role_separator="  ·  ", date_mode="tab_stop", date_prefix="\t",
        bullet_symbol="·", bullet_gap=" ",
        cert_label="证书  ", cert_separator="  ·  ",
        identity_text_align="left", contact_align="left", photo_align="right",
        photo_preserve_aspect=True,
    ),
    SKELETON_MINIMAL: RenderComponents(
        title_numbering_template="%02d", title_numbering_gap="  ",
        role_separator="  ", date_mode="tab_stop", date_prefix="\t",
        bullet_symbol="·", bullet_gap=" ",
        cert_label="证书资质  ", cert_separator="  ·  ",
        identity_text_align="left", contact_align="left", photo_align="right",
        photo_preserve_aspect=True,
    ),
    SKELETON_SIDEBAR: RenderComponents(
        section_title_symbol="▍", section_title_gap=" ",
        role_separator="  ·  ", date_mode="column", date_prefix="\t",
        bullet_symbol="·", bullet_gap=" ",
        side_label_transform="upper_ascii",
        identity_text_align="center", contact_align="left",
        photo_align="center",
        photo_preserve_aspect=True,
    ),
}


SKELETON_DEFAULT_STYLE = {
    # banner：审计自 2026-09 改造前硬编码
    SKELETON_BANNER: _profile(
        name_size=18, intent_size=10.5, contact_size=9,
        title_size=12, org_size=10.5, role_size=10,
        body_size=9.5, meta_size=9, tags_size=8.5,
        side_label_size=9, sidebar_body_size=8.5,
        line_body=1.08, line_bullet=1.08, line_title=1.0,
        line_exp_header=1.05, line_sidebar=1.05,
        spacing=_DEFAULT_SPACING[SKELETON_BANNER],
        components=_DEFAULT_COMPONENTS[SKELETON_BANNER],
    ),
    # minimal
    SKELETON_MINIMAL: _profile(
        name_size=20, intent_size=11, contact_size=9,
        title_size=12, org_size=10.5, role_size=10,
        body_size=9.5, meta_size=9, tags_size=8.5,
        side_label_size=9, sidebar_body_size=8.5,
        line_body=1.06, line_bullet=1.08, line_title=1.0,
        line_exp_header=1.05, line_sidebar=1.05,
        spacing=_DEFAULT_SPACING[SKELETON_MINIMAL],
        components=_DEFAULT_COMPONENTS[SKELETON_MINIMAL],
    ),
    # sidebar
    SKELETON_SIDEBAR: _profile(
        name_size=14, intent_size=8.5, contact_size=8.5,
        title_size=12, org_size=10.5, role_size=10,
        body_size=9.5, meta_size=9, tags_size=8.5,
        side_label_size=9, sidebar_body_size=8.5,
        line_body=1.08, line_bullet=1.06, line_title=1.0,
        line_exp_header=1.05, line_sidebar=1.05,
        spacing=_DEFAULT_SPACING[SKELETON_SIDEBAR],
        components=_DEFAULT_COMPONENTS[SKELETON_SIDEBAR],
    ),
}


# ---------------------------------------------------------------------------
# Spec → RenderStyle
# ---------------------------------------------------------------------------

def _num(sourced, fallback: float) -> Tuple[float, bool]:
    """返回 (取值, 是否走了回退)。undetermined / 非数值一律回退。"""
    try:
        if sourced is not None and not sourced.is_undetermined \
                and isinstance(sourced.value, (int, float)):
            return float(sourced.value), False
    except AttributeError:
        pass
    return fallback, True


def _bold(weight: str, fallback: bool) -> Tuple[bool, bool]:
    """字重解析；裸字符串 'undetermined' 回退骨架值。"""
    if weight in ("bold", "regular"):
        return weight == "bold", False
    return fallback, True


def resolve_style_for_spec(spec, base: RenderStyle, skeleton_id: str,
                           palette: Palette) -> RenderStyle:
    """以骨架 Profile 为底，逐字段用已确定的 Typography/Color Spec 覆盖。

    未确定 / Spec 未覆盖的字段保留 base（不编造），并登记到 spec_fallbacks。
    字号下限等契约由 Validator 负责，本函数不二次"设计"。
    palette 为运行时行业色板（Spec 路径取骨架默认色板），仅作颜色 fallback 基础。
    """
    ty = spec.typography
    fb: List[str] = []

    def n(sourced, fallback: float, key: str) -> float:
        val, used_fb = _num(sourced, fallback)
        if used_fb:
            fb.append(key)
        return val

    # 身份区：intent 在 TypographySpec 中无字段（知识缺口），保留 Profile
    intent_size = base.intent_size
    fb.append("typography.intent_size<spec_missing>")

    # 联系方式：P1 用深块元信息第一档；P2 header_meta_sizes=None → Profile
    if ty.header_meta_sizes:
        contact_size = n(ty.header_meta_sizes[0], base.contact_size,
                         "typography.header_meta_sizes[0]")
    else:
        contact_size = base.contact_size
        fb.append("typography.header_meta_sizes")

    # 标签链字号：P1 启用取 experience.tags.size；P2 禁用 → Profile（不会渲染）
    if spec.experience.tags.enabled:
        tags_size = n(spec.experience.tags.size, base.tags_size,
                      "experience.tags.size")
    else:
        tags_size = base.tags_size

    # 侧栏
    side_label_size = n(ty.sidebar_group_label_size,
                        base.side_label_size,
                        "typography.sidebar_group_label_size")
    sidebar_body_size = n(ty.sidebar_body_size, base.sidebar_body_size,
                          "typography.sidebar_body_size")

    # 行距
    line_body = n(ty.line_spacing.body, base.line_body,
                  "typography.line_spacing.body")
    line_title = n(ty.line_spacing.title, base.line_title,
                   "typography.line_spacing.title")
    if ty.line_spacing.sidebar_body is not None:
        line_sidebar = n(ty.line_spacing.sidebar_body, base.line_sidebar,
                         "typography.line_spacing.sidebar_body")
    else:
        line_sidebar = line_body  # 单栏范式无独立侧栏行距

    # 字重（P2 role=undetermined → Profile 粗体兜底）
    w_name, f1 = _bold(ty.weights.name, base.w_name)
    w_title, f2 = _bold(ty.weights.section_title, base.w_title)
    w_org, f3 = _bold(ty.weights.organization, base.w_org)
    w_role, f4 = _bold(ty.weights.role, base.w_role)
    w_side_label, f5 = _bold(ty.weights.sidebar_group_label,
                             base.w_side_label)
    for key, fellback in (("typography.weights.name", f1),
                          ("typography.weights.section_title", f2),
                          ("typography.weights.organization", f3),
                          ("typography.weights.role", f4),
                          ("typography.weights.sidebar_group_label", f5)):
        if fellback:
            fb.append(key)

    # --- ColorSpec → RenderPalette（Phase 3B-2）---
    base_palette = build_palette_for_skeleton(skeleton_id, palette)
    render_palette = _resolve_colors_for_spec(
        spec, skeleton_id, base_palette, fb)

    # --- SpacingSpec → RenderSpacing（Phase 3B-3）---
    render_spacing = _resolve_spacing_for_spec(
        spec, skeleton_id, base.spacing, fb)

    # --- 组件结构 → RenderComponents（Phase 3B-4）---
    render_components = _resolve_components_for_spec(
        spec, skeleton_id, base.components, fb, render_palette)

    # P-4：西文字体（None = 与中文同族，旧路径/P1/P2 字节保值）
    latin_font = resolve_latin_font(ty.latin_font)

    return RenderStyle(
        font_family=resolve_font_family(ty.font_family.value),
        latin_font=latin_font,
        name_size=n(ty.name_size, base.name_size, "typography.name_size"),
        intent_size=intent_size,
        contact_size=contact_size,
        title_size=n(ty.title_size, base.title_size, "typography.title_size"),
        org_size=n(ty.organization_size, base.org_size,
                   "typography.organization_size"),
        role_size=n(ty.role_size, base.role_size, "typography.role_size"),
        body_size=n(ty.body_size, base.body_size, "typography.body_size"),
        meta_size=n(ty.metadata_size, base.meta_size,
                    "typography.metadata_size"),
        tags_size=tags_size,
        side_label_size=side_label_size,
        sidebar_body_size=sidebar_body_size,
        line_body=line_body,
        line_bullet=line_body,   # bullet 与正文同行距；骨架旧 0.02 差异仅旧 Profile 保留
        line_title=line_title,
        line_exp_header=line_title,  # Spec 只定义 title/body 两档，表头行归 title 档
        line_sidebar=line_sidebar,
        w_name=w_name, w_title=w_title, w_org=w_org, w_role=w_role,
        w_side_label=w_side_label,
        source="design_spec",
        spec_fallbacks=tuple(fb),
        palette=render_palette,
        spacing=render_spacing,
        components=render_components,
    )
