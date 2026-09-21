# -*- coding: utf-8 -*-
"""consumption.py — DesignSpec 字段消费矩阵（Phase 2B-2）。

定位（只做契约登记，不含任何渲染能力）：
    DesignSpec（写入端：presets / Design Engine）
        ↓ 本模块回答「每个字段有没有人读、被谁读」
    Renderer（消费端：skeletons.py / render_style.py / layout_kit.py）

四种状态：
    consumed            字段被渲染链路真实读取并进入 DOCX（或经 Validator
                        形成硬闸门）
    partially_consumed  仅在部分范式/部分取值下生效；或只被 Validator 读取、
                        Renderer 靠固定行为/骨架常量间接满足
    fallback            Spec 无此设计概念（schema gap），运行时恒回退骨架 Profile
    unconsumed          存在读取点为零的字段；若 Spec 显式给出可执行定值，
                        evaluate_unconsumed() 产出非阻断 WARNING

维护规则：
    1. consumed_by 必须写实际函数/模块名，禁止写「未来会消费」。
    2. 新增 DesignSpec 字段时必须同步登记本矩阵，无消费点即 unconsumed。
    3. 本模块不新增任何 Renderer 能力——矩阵只暴露契约缺口，不填补缺口。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from .spec import (
    SOURCE_NOT_APPLICABLE,
    Sourced,
    DesignSpec,
)

# ---------------------------------------------------------------------------
# 范式 / 状态常量
# ---------------------------------------------------------------------------

P1 = "p1_banner_single"
P2 = "p2_sidebar_two_column"
P3 = "p3_minimal_editorial"
ALL_PARADIGMS = (P1, P2, P3)

STATUS_CONSUMED = "consumed"
STATUS_PARTIALLY_CONSUMED = "partially_consumed"
STATUS_FALLBACK = "fallback"
STATUS_UNCONSUMED = "unconsumed"

VALID_STATUSES = (
    STATUS_CONSUMED, STATUS_PARTIALLY_CONSUMED,
    STATUS_FALLBACK, STATUS_UNCONSUMED,
)

# 消费端函数名（字符串登记，避免与渲染层产生 import 耦合）
F_BUILD_FROM_SPEC = "skeletons._build_from_spec"
F_BANNER = "skeletons.build_banner_card"
F_MINIMAL = "skeletons.build_minimal"
F_SIDEBAR = "skeletons.build_sidebar"
F_RESOLVE_STYLE = "render_style.resolve_style_for_spec"
F_RESOLVE_COLORS = "render_style._resolve_colors_for_spec"
F_RESOLVE_SPACING = "render_style._resolve_spacing_for_spec"
F_RESOLVE_COMPONENTS = "render_style._resolve_components_for_spec"
F_VALIDATOR = "design.validator.validate_spec"
F_LAYOUT = "skeletons._resolve_layout/layout_kit"
F_FLOATING_PHOTO = "layout_kit.insert_floating_photo"
F_PROFILE = "骨架 SKELETON_DEFAULT_STYLE Profile（Spec 无对应字段）"


@dataclass(frozen=True)
class FieldConsumption:
    """单个 DesignSpec 字段路径的消费登记。

    paradigm 为空串表示该登记适用全部范式；同一字段在不同范式下消费状态
    不同时（如 grid.column_ratio）分行登记。
    """

    path: str
    status: str
    consumed_by: Tuple[str, ...] = ()
    paradigm: str = ""
    notes: str = ""


# ---------------------------------------------------------------------------
# 消费矩阵（路径与 design/spec.py 数据结构一一对应）
# ---------------------------------------------------------------------------

_CONSUMPTION_MATRIX: Tuple[FieldConsumption, ...] = (
    # --- metadata ---------------------------------------------------------
    FieldConsumption("metadata.paradigm", STATUS_CONSUMED,
                     (F_BUILD_FROM_SPEC,),
                     notes="PARADIGM_TO_SKELETON 分发键"),
    FieldConsumption("metadata.spec_id", STATUS_UNCONSUMED,
                     notes="描述性元信息，无渲染语义"),
    FieldConsumption("metadata.version", STATUS_UNCONSUMED,
                     notes="描述性元信息，无渲染语义"),
    FieldConsumption("metadata.source_knowledge_version", STATUS_UNCONSUMED,
                     notes="描述性元信息，无渲染语义"),
    FieldConsumption("metadata.confidence", STATUS_UNCONSUMED,
                     notes="描述性元信息；Spec 内逐字段另有 Sourced.confidence"),
    FieldConsumption("metadata.notes", STATUS_UNCONSUMED,
                     notes="描述性元信息，无渲染语义"),

    # --- page -------------------------------------------------------------
    FieldConsumption("page.size", STATUS_PARTIALLY_CONSUMED,
                     (F_VALIDATOR,),
                     notes="Validator 强制 A4；setup_a4 自身固定 A4，不读值"),
    FieldConsumption("page.width_cm", STATUS_PARTIALLY_CONSUMED,
                     (F_VALIDATOR,),
                     notes="仅用于表宽校验；Renderer 几何固定 A4"),
    FieldConsumption("page.height_cm", STATUS_UNCONSUMED,
                     notes="A4 固定形态，无读取点（描述性）"),
    FieldConsumption("page.orientation", STATUS_UNCONSUMED,
                     notes="portrait 由 setup_a4 固定，无读取点（描述性）"),
    FieldConsumption("page.target_pages", STATUS_PARTIALLY_CONSUMED,
                     (F_VALIDATOR,),
                     notes="单页目标声明；最终页数以 Word COM 实测为准"),
    FieldConsumption("page.margins.top", STATUS_PARTIALLY_CONSUMED,
                     (F_BUILD_FROM_SPEC, F_LAYOUT),
                     notes="四边距全部确定才覆盖；P2 全 undetermined→骨架默认"),
    FieldConsumption("page.margins.bottom", STATUS_PARTIALLY_CONSUMED,
                     (F_BUILD_FROM_SPEC, F_LAYOUT),
                     notes="四边距全部确定才覆盖；P2→骨架默认 fallback"),
    FieldConsumption("page.margins.left", STATUS_PARTIALLY_CONSUMED,
                     (F_BUILD_FROM_SPEC, F_LAYOUT),
                     notes="四边距全部确定才覆盖；P2→骨架默认 fallback"),
    FieldConsumption("page.margins.right", STATUS_PARTIALLY_CONSUMED,
                     (F_BUILD_FROM_SPEC, F_LAYOUT),
                     notes="四边距全部确定才覆盖；P2→骨架默认 fallback"),
    FieldConsumption("page.bleed", STATUS_UNCONSUMED,
                     notes="无出血渲染；undetermined 由 RULE_BLEED_UNDETERMINED "
                           "覆盖，>0 定值由本契约 WARNING 暴露"),
    FieldConsumption("page.safe_area.top", STATUS_UNCONSUMED,
                     notes="margins 派生镜像（描述性），无独立消费点"),
    FieldConsumption("page.safe_area.bottom", STATUS_UNCONSUMED,
                     notes="margins 派生镜像（描述性），无独立消费点"),
    FieldConsumption("page.safe_area.left", STATUS_UNCONSUMED,
                     notes="margins 派生镜像（描述性），无独立消费点"),
    FieldConsumption("page.safe_area.right", STATUS_UNCONSUMED,
                     notes="margins 派生镜像（描述性），无独立消费点"),
    FieldConsumption("page.safe_area.content_width", STATUS_UNCONSUMED,
                     notes="派生镜像；表宽实际由 _resolve_layout 计算"),

    # --- architecture -----------------------------------------------------
    FieldConsumption("architecture.paradigm", STATUS_CONSUMED,
                     (F_BUILD_FROM_SPEC,),
                     notes="骨架分发键（与 metadata.paradigm 同源）"),
    FieldConsumption("architecture.column_count", STATUS_PARTIALLY_CONSUMED,
                     (F_VALIDATOR,),
                     notes="仅 Validator 列比校验读取；骨架由 paradigm 决定"),
    FieldConsumption("architecture.content_flow", STATUS_UNCONSUMED,
                     notes="板块顺序硬编码于各 builder；核心板块顺序为硬规则，"
                           "属内容组织策略描述"),
    FieldConsumption("architecture.sidebar_enabled", STATUS_UNCONSUMED,
                     notes="零读取点；是否双栏由 paradigm→sidebar 骨架间接保证"
                           "（描述性开关，改值不影响渲染）"),
    FieldConsumption("architecture.sidebar_contains", STATUS_UNCONSUMED,
                     notes="侧栏板块归属硬编码于 build_sidebar（内容组织策略）"),
    FieldConsumption("architecture.main_contains", STATUS_UNCONSUMED,
                     notes="主栏板块归属硬编码于各 builder（内容组织策略）"),

    # --- grid -------------------------------------------------------------
    # v0.9.0 状态变更：P2 的 grid.column_ratio 由「零读取 + 数值漂移（预警）」
    # 变为**真实消费** —— _ratios_from_spec 读它并交给 _resolve_layout 切列宽。
    # P1/P3 仍为零读取，但原因变了：这两族的正文本来就是单栏，
    # 「正文栅格」声明（[1.0]）与身份区那两列无关，身份区列比走
    # grid.identity_band_ratio。
    FieldConsumption("grid.column_ratio", STATUS_UNCONSUMED, (),
                     paradigm=P1,
                     notes="正文单栏范式的栅格声明，无读取点；身份区列比走"
                           "grid.identity_band_ratio，两者不混用"),
    FieldConsumption("grid.column_ratio", STATUS_CONSUMED,
                     (F_BUILD_FROM_SPEC, F_LAYOUT),
                     paradigm=P2,
                     notes="v0.9.0 起真实消费：_ratios_from_spec 取该值切列宽，"
                           "不再回退骨架常量（历史数值漂移 0.32/0.68 vs "
                           "0.304/0.696 已消除）"),
    FieldConsumption("grid.column_ratio", STATUS_UNCONSUMED, (),
                     paradigm=P3,
                     notes="正文单栏范式的栅格声明，无读取点；Header 单/双列"
                           "由 photo.enabled 分支决定，非列比驱动"),
    FieldConsumption("grid.identity_band_ratio", STATUS_CONSUMED,
                     (F_BUILD_FROM_SPEC, F_LAYOUT),
                     notes="v0.9.0 新增：身份区（Header）表格的列比例。此前该"
                           "几何硬编码在 skeletons._LAYOUT_CONFIG，Spec 改不动；"
                           "长度/和/正数校验不过则沿用骨架默认"),
    FieldConsumption("grid.gutter", STATUS_UNCONSUMED,
                     notes="split_columns_cm 无中缝概念，无读取点"),
    FieldConsumption("grid.width_rule", STATUS_UNCONSUMED,
                     notes="表宽公式描述文本（实际规则在 _resolve_layout）"),
    FieldConsumption("grid.column_widths_cm", STATUS_PARTIALLY_CONSUMED,
                     (F_VALIDATOR,),
                     notes="仅 Validator 表宽校验；列宽由边距+骨架比例计算"),

    # --- header -----------------------------------------------------------
    FieldConsumption("header.type", STATUS_UNCONSUMED,
                     notes="零读取点；Header 形态由 paradigm→builder 结构保证"
                           "（描述性枚举）"),
    FieldConsumption("header.height", STATUS_UNCONSUMED,
                     notes="身份区高度由内容行数+单元格边距派生，无读取点"),
    FieldConsumption("header.background_role", STATUS_UNCONSUMED,
                     notes="role 字符串零读取；深块由 build_banner_card 硬编码"
                           "绘制，颜色实际取 colors.dark_block"),
    FieldConsumption("header.accent_line.enabled", STATUS_PARTIALLY_CONSUMED,
                     (F_BUILD_FROM_SPEC, F_MINIMAL),
                     notes="minimal 为硬闸门（P-3）；banner 恒绘制色条不读本字段，"
                           "False 时 bar_sz 仅经 Resolver 回退 Profile 厚度"),
    FieldConsumption("header.accent_line.height", STATUS_PARTIALLY_CONSUMED,
                     (F_RESOLVE_SPACING, F_BANNER),
                     notes="banner enabled 时映射 bar_sz；minimal rule_sz 为 "
                           "永久 Profile（P3 disabled=N/A）"),
    FieldConsumption("header.accent_line.color_role", STATUS_UNCONSUMED,
                     notes="色条颜色硬编码 palette.accent，role 字符串零读取"),
    FieldConsumption("header.accent_line.placement", STATUS_UNCONSUMED,
                     notes="布局语义描述，无读取点"),
    FieldConsumption("header.identity_alignment", STATUS_PARTIALLY_CONSUMED,
                     (F_RESOLVE_COMPONENTS,),
                     notes="P1/P2 在映射表内；P3 'left_text_only' 未映射→"
                           "回退 Profile（left，视觉等价）并登记 not_defined"),
    FieldConsumption("header.photo_zone", STATUS_UNCONSUMED,
                     notes="零读取点；位置由 paradigm + photo.enabled 间接保证"
                           "（描述性枚举）"),
    FieldConsumption("header.text_inset", STATUS_UNCONSUMED,
                     notes="格内边距实际取 Profile cell_left_cm/cell_right_cm"),

    # --- typography -------------------------------------------------------
    FieldConsumption("typography.font_family", STATUS_CONSUMED,
                     (F_RESOLVE_STYLE,)),
    FieldConsumption("typography.latin_font", STATUS_CONSUMED,
                     (F_RESOLVE_STYLE,),
                     notes="P-4：None=与中文同族（P1/P2 保值）；P3 ArialMT 落地"),
    FieldConsumption("typography.weights.name", STATUS_CONSUMED,
                     (F_RESOLVE_STYLE,)),
    FieldConsumption("typography.weights.section_title", STATUS_CONSUMED,
                     (F_RESOLVE_STYLE,)),
    FieldConsumption("typography.weights.organization", STATUS_CONSUMED,
                     (F_RESOLVE_STYLE,)),
    FieldConsumption("typography.weights.role", STATUS_CONSUMED,
                     (F_RESOLVE_STYLE,)),
    FieldConsumption("typography.weights.body", STATUS_UNCONSUMED,
                     notes="正文 run 字重硬编码 regular，无读取点"),
    FieldConsumption("typography.weights.metadata", STATUS_UNCONSUMED,
                     notes="日期/元信息 run 字重硬编码 regular，无读取点"),
    FieldConsumption("typography.weights.sidebar_group_label", STATUS_CONSUMED,
                     (F_RESOLVE_STYLE,)),
    FieldConsumption("typography.name_size", STATUS_CONSUMED,
                     (F_RESOLVE_STYLE,)),
    FieldConsumption("typography.title_size", STATUS_CONSUMED,
                     (F_RESOLVE_STYLE,)),
    FieldConsumption("typography.organization_size", STATUS_CONSUMED,
                     (F_RESOLVE_STYLE,)),
    FieldConsumption("typography.role_size", STATUS_CONSUMED,
                     (F_RESOLVE_STYLE,)),
    FieldConsumption("typography.body_size", STATUS_CONSUMED,
                     (F_RESOLVE_STYLE,)),
    FieldConsumption("typography.metadata_size", STATUS_CONSUMED,
                     (F_RESOLVE_STYLE,)),
    FieldConsumption("typography.line_spacing.body", STATUS_CONSUMED,
                     (F_RESOLVE_STYLE,)),
    FieldConsumption("typography.line_spacing.title", STATUS_CONSUMED,
                     (F_RESOLVE_STYLE,)),
    FieldConsumption("typography.line_spacing.sidebar_body", STATUS_CONSUMED,
                     (F_RESOLVE_STYLE,),
                     notes="P2 消费；单栏范式 None→取 body 档"),
    FieldConsumption("typography.minimum_body_size", STATUS_PARTIALLY_CONSUMED,
                     (F_VALIDATOR,),
                     notes="Validator 硬下限；Renderer 另有独立常量 MIN_BODY_PT"),
    FieldConsumption("typography.header_meta_sizes[0]", STATUS_CONSUMED,
                     (F_RESOLVE_STYLE,),
                     notes="映射 contact_size"),
    FieldConsumption("typography.header_meta_sizes[1]", STATUS_UNCONSUMED,
                     notes="Resolver 仅读 [0]；第二档（深块教育行）无消费点"),
    FieldConsumption("typography.sidebar_body_size", STATUS_CONSUMED,
                     (F_RESOLVE_STYLE,)),
    FieldConsumption("typography.sidebar_group_label_size", STATUS_CONSUMED,
                     (F_RESOLVE_STYLE,)),
    FieldConsumption("typography.intent_size", STATUS_FALLBACK,
                     (F_PROFILE,),
                     notes="<schema_gap>：TypographySpec 无该字段，意向行字号"
                           "恒取骨架 Profile（Resolver 永久登记 spec_missing）"),

    # --- colors -----------------------------------------------------------
    FieldConsumption("colors.ink", STATUS_CONSUMED, (F_RESOLVE_COLORS,)),
    FieldConsumption("colors.accent", STATUS_CONSUMED, (F_RESOLVE_COLORS,)),
    FieldConsumption("colors.muted", STATUS_CONSUMED, (F_RESOLVE_COLORS,)),
    FieldConsumption("colors.hairline", STATUS_CONSUMED,
                     (F_RESOLVE_COLORS,),
                     notes="进入 RenderPalette；divider.weight=0 时无渲染落点"
                           "（P-5 设计行为）"),
    FieldConsumption("colors.paper", STATUS_UNCONSUMED,
                     notes="Resolver 透传备用但零渲染落点；实际依赖 DOCX 默认白底"),
    FieldConsumption("colors.dark_block", STATUS_CONSUMED,
                     (F_RESOLVE_COLORS, F_BANNER)),
    FieldConsumption("colors.light_sidebar", STATUS_CONSUMED,
                     (F_RESOLVE_COLORS, F_SIDEBAR)),
    FieldConsumption("colors.on_dark_primary", STATUS_CONSUMED,
                     (F_RESOLVE_COLORS, F_BANNER)),
    FieldConsumption("colors.on_dark_secondary", STATUS_CONSUMED,
                     (F_RESOLVE_COLORS, F_BANNER)),
    FieldConsumption("colors.on_dark_tertiary", STATUS_CONSUMED,
                     (F_RESOLVE_COLORS, F_BANNER)),
    FieldConsumption("colors.accent_area_limit", STATUS_UNCONSUMED,
                     notes="占比约束描述，无执行点（约束元数据）"),
    FieldConsumption("colors.additional_accents", STATUS_CONSUMED,
                     (F_VALIDATOR,),
                     notes="Validator 单一强调色 ERROR 闸门"),
    FieldConsumption("colors.page_background", STATUS_CONSUMED,
                     (F_BUILD_FROM_SPEC, F_MINIMAL),
                     notes="v0.8.2 起接通：layout_kit.set_page_background 写 "
                           "w:background（必须是 document 首个子元素）+ settings "
                           "的 displayBackgroundShape；仅 minimal 消费"),
    FieldConsumption("colors.light_sidebar_secondary", STATUS_UNCONSUMED,
                     notes="侧栏第二色无消费点（build_sidebar 仅用 light_sidebar）"),

    # --- photo ------------------------------------------------------------
    FieldConsumption("photo.enabled", STATUS_PARTIALLY_CONSUMED,
                     (F_BUILD_FROM_SPEC, F_MINIMAL),
                     notes="minimal 为硬闸门（P-2 单列）；banner/sidebar 恒 "
                           "insert_photo，不读本字段（当前 P1/P2 均 True）"),
    FieldConsumption("photo.position", STATUS_UNCONSUMED,
                     notes="零读取点；位置由 paradigm 间接固定（描述性枚举）"),
    FieldConsumption("photo.width", STATUS_PARTIALLY_CONSUMED,
                     (F_BUILD_FROM_SPEC,),
                     notes="rect：直接作照片盒宽；circle：不读，改用 fallback 宽"),
    FieldConsumption("photo.height", STATUS_PARTIALLY_CONSUMED,
                     (F_BUILD_FROM_SPEC,),
                     notes="rect：直接作照片盒高；circle：不读，改用 fallback 高"),
    FieldConsumption("photo.aspect_ratio", STATUS_PARTIALLY_CONSUMED,
                     (F_VALIDATOR,),
                     notes="仅声明比例校验；插入时等比保护基于原图实际比例"),
    FieldConsumption("photo.container", STATUS_UNCONSUMED,
                     notes="容器形态描述文本，无读取点"),
    FieldConsumption("photo.display_shape", STATUS_PARTIALLY_CONSUMED,
                     (F_BUILD_FROM_SPEC,),
                     notes="circle 仅切换到 fallback 矩形盒尺寸，无圆形裁切"),
    FieldConsumption("photo.distortion_allowed", STATUS_CONSUMED,
                     (F_VALIDATOR, F_RESOLVE_COMPONENTS),
                     notes="Validator 禁止 True；取反映射 photo_preserve_aspect"),
    FieldConsumption("photo.crop_allowed", STATUS_UNCONSUMED,
                     notes="无裁切流水线，crop 许可无任何执行点"),
    FieldConsumption("photo.source_crop", STATUS_UNCONSUMED,
                     notes="裁切方式描述文本，无读取点"),
    FieldConsumption("photo.fallback.container", STATUS_UNCONSUMED,
                     notes="降级形态名零读取；实际只消费 fallback.width/height"),
    FieldConsumption("photo.fallback.width", STATUS_CONSUMED,
                     (F_BUILD_FROM_SPEC,),
                     notes="circle 路径作矩形盒宽"),
    FieldConsumption("photo.fallback.height", STATUS_CONSUMED,
                     (F_BUILD_FROM_SPEC,),
                     notes="circle 路径作矩形盒高"),
    FieldConsumption("photo.fallback.aspect_ratio", STATUS_UNCONSUMED,
                     notes="fallback 比例无读取点（盒尺寸直接给定）"),
    # --- photo.floating / border（Golden Sample CL-01，2B-4 Step 4）------
    FieldConsumption("photo.floating.enabled", STATUS_CONSUMED,
                     (F_BUILD_FROM_SPEC, F_MINIMAL, F_FLOATING_PHOTO, F_VALIDATOR),
                     notes="True 时 minimal 照片段走 wp:anchor；False/None "
                           "保持 wp:inline 旧行为；banner/sidebar 不读"),
    FieldConsumption("photo.floating.position_h", STATUS_CONSUMED,
                     (F_FLOATING_PHOTO,),
                     notes="写 wp:positionH/@relativeFrom（白名单 column/page/margin）"),
    FieldConsumption("photo.floating.position_v", STATUS_CONSUMED,
                     (F_FLOATING_PHOTO,),
                     notes="写 wp:positionV/@relativeFrom（白名单 page/margin）"),
    FieldConsumption("photo.floating.offset_x_cm", STATUS_CONSUMED,
                     (F_BUILD_FROM_SPEC, F_FLOATING_PHOTO),
                     notes="cm→EMU 写 wp:positionH/wp:posOffset；None=0"),
    FieldConsumption("photo.floating.offset_y_cm", STATUS_CONSUMED,
                     (F_BUILD_FROM_SPEC, F_FLOATING_PHOTO),
                     notes="cm→EMU 写 wp:positionV/wp:posOffset；None=0"),
    FieldConsumption("photo.border.color", STATUS_CONSUMED,
                     (F_FLOATING_PHOTO, F_VALIDATOR),
                     notes="#RRGGBB 写 a:ln/a:solidFill/a:srgbClr；仅浮动照片消费"),
    FieldConsumption("photo.border.width_pt", STATUS_CONSUMED,
                     (F_FLOATING_PHOTO, F_VALIDATOR),
                     notes="pt→EMU 写 a:ln/@w；0=无边框；仅浮动照片消费"),

    # --- section ----------------------------------------------------------
    FieldConsumption("section.title_style", STATUS_PARTIALLY_CONSUMED,
                     (F_RESOLVE_COMPONENTS, F_MINIMAL),
                     notes="minimal symbol_hairline 分支生效；icon_hairline "
                           "无图标能力回退文本符号（缺口另由 RULE_ICON_FALLBACK）"),
    FieldConsumption("section.prefix", STATUS_CONSUMED,
                     (F_RESOLVE_COMPONENTS, F_BANNER, F_SIDEBAR, F_MINIMAL)),
    FieldConsumption("section.icon.resource", STATUS_PARTIALLY_CONSUMED,
                     (F_RESOLVE_COMPONENTS,),
                     notes="仅登记 capability_gap；无图标渲染，即使给定资源也不画"),
    FieldConsumption("section.icon.primary", STATUS_UNCONSUMED,
                     notes="图标主方案声明，无图标渲染能力"),
    FieldConsumption("section.icon.fallback", STATUS_UNCONSUMED,
                     notes="回退目标语义说明零读取；实际回退由 title_style 分支固定"),
    FieldConsumption("section.icon.icon_color_role", STATUS_UNCONSUMED,
                     notes="无图标渲染，图标色无消费点"),
    FieldConsumption("section.divider.style", STATUS_UNCONSUMED,
                     notes="线型描述文本；实现固定 single 实线"),
    FieldConsumption("section.divider.weight", STATUS_CONSUMED,
                     (F_RESOLVE_SPACING, F_BANNER, F_SIDEBAR, F_MINIMAL),
                     notes="映射 hairline_sz；0pt 经 P-5 闸门完全不生成 divider"),
    FieldConsumption("section.divider.color_role", STATUS_UNCONSUMED,
                     notes="role 字符串零读取；divider 颜色实际取 colors.hairline"),
    FieldConsumption("section.divider.width_rule", STATUS_UNCONSUMED,
                     notes="divider 宽度规则描述文本，无读取点"),
    FieldConsumption("section.divider.bleed", STATUS_UNCONSUMED,
                     notes="divider 外伸量无渲染参数，无读取点"),
    FieldConsumption("section.title_weight", STATUS_UNCONSUMED,
                     notes="重复槽位：字重权威来源是 weights.section_title"),
    FieldConsumption("section.title_color_role", STATUS_UNCONSUMED,
                     notes="标题文字色硬编码 ink，role 字符串无读取点"),
    FieldConsumption("section.symbol_color_role", STATUS_UNCONSUMED, (),
                     paradigm=P1,
                     notes="banner 符号与标题同 run 同色 ink；声明 accent 不落地"),
    FieldConsumption("section.symbol_color_role", STATUS_UNCONSUMED, (),
                     paradigm=P2,
                     notes="_main_title 单 run ink；声明 accent 不落地"),
    FieldConsumption("section.symbol_color_role", STATUS_CONSUMED,
                     (F_RESOLVE_COMPONENTS, F_MINIMAL),
                     paradigm=P3,
                     notes="P-1：符号独立 run，accent 色落地"),
    FieldConsumption("section.title_indent", STATUS_UNCONSUMED,
                     notes="符号→标题间隙实际为组装常量（单空格），厘米值无消费点"),
    FieldConsumption("section.spacing_before", STATUS_CONSUMED,
                     (F_RESOLVE_SPACING,)),
    FieldConsumption("section.divider_to_first_line", STATUS_CONSUMED,
                     (F_RESOLVE_SPACING,),
                     notes="映射 hairline_after；divider 禁用时该间距无落点"),
    # Phase 2B-5 Step 1：title_after 正式由 Spec 提供（取代永久 Profile）
    FieldConsumption("section.title_spacing_after", STATUS_CONSUMED,
                     (F_RESOLVE_SPACING,),
                     notes="映射 title_after；banner/minimal 消费。"
                           "sidebar 标题段 after 不在 _SPACING_ROLES_BY_SKELETON"
                           "（标题边框直接附在标题段，无独立 title_after 槽），"
                           "P2 Spec 值在该骨架不生效（保留旧行为）"),
    # v0.9.0 新增：四个此前只能靠「每份简历的临时脚本后处理」的间距字段，
    # 现已接通 Spec → RenderSpacing → Renderer 全链路。
    FieldConsumption("section.divider_spacing_before", STATUS_CONSUMED,
                     (F_RESOLVE_SPACING,),
                     notes="v0.9.0 新增：映射 hairline_before（独立 divider 空段"
                           "的段前）。此前是 schema_gap，恒回退骨架 Profile"),
    FieldConsumption("section.summary_spacing_after", STATUS_CONSUMED,
                     (F_RESOLVE_SPACING,),
                     notes="v0.9.0 新增：映射 summary_after（个人优势/简介段后）"),
    FieldConsumption("section.education_spacing_after", STATUS_CONSUMED,
                     (F_RESOLVE_SPACING,),
                     notes="v0.9.0 新增：映射 edu_after（教育经历各行段后）"),
    FieldConsumption("section.divider.line_height", STATUS_CONSUMED,
                     (F_RESOLVE_SPACING, F_LAYOUT),
                     notes="v0.9.0 新增：映射 hairline_height，写 divider 空段的"
                           "exact 行高（该段无文字无图片，不触发图片裁剪禁令）。"
                           "None 保持自动行高（历史行为）"),
    FieldConsumption("section.divider.border_space", STATUS_CONSUMED,
                     (F_RESOLVE_SPACING, F_LAYOUT),
                     notes="v0.9.0 新增：映射 hairline_border_space，写 "
                           "w:pBdr/w:bottom/@w:space。None 保持历史值 1pt"),
    FieldConsumption("section.styles_per_document", STATUS_UNCONSUMED,
                     notes="数量约束描述；等价约束在 ConstraintsSpec 表达"),

    # --- experience -------------------------------------------------------
    FieldConsumption("experience.organization.size", STATUS_CONSUMED,
                     (F_RESOLVE_STYLE,)),
    FieldConsumption("experience.organization.weight", STATUS_CONSUMED,
                     (F_RESOLVE_STYLE,)),
    FieldConsumption("experience.organization.color_role", STATUS_UNCONSUMED,
                     notes="机构名颜色硬编码 ink，role 字符串零读取（与 preset 巧合一致）"),
    FieldConsumption("experience.role.size", STATUS_CONSUMED,
                     (F_RESOLVE_STYLE,)),
    FieldConsumption("experience.role.weight", STATUS_CONSUMED,
                     (F_RESOLVE_STYLE,)),
    FieldConsumption("experience.role.color_role", STATUS_UNCONSUMED,
                     notes="角色色硬编码 palette.accent，role 字符串零读取"),
    FieldConsumption("experience.role.separator", STATUS_CONSUMED,
                     (F_RESOLVE_COMPONENTS,)),
    FieldConsumption("experience.date.size", STATUS_CONSUMED,
                     (F_RESOLVE_STYLE,)),
    FieldConsumption("experience.date.weight", STATUS_UNCONSUMED,
                     notes="日期字重硬编码 regular，无读取点"),
    FieldConsumption("experience.date.color_role", STATUS_UNCONSUMED,
                     notes="日期色硬编码 palette.muted，role 字符串零读取"),
    FieldConsumption("experience.date_alignment", STATUS_CONSUMED,
                     (F_RESOLVE_COMPONENTS, F_VALIDATOR)),
    FieldConsumption("experience.tags.enabled", STATUS_CONSUMED,
                     (F_RESOLVE_STYLE, F_BANNER),
                     paradigm=P1,
                     notes="banner _experience_section 渲染 tags 行；"
                           "注意渲染条件实际是 item.tags 非空"),
    FieldConsumption("experience.tags.enabled", STATUS_UNCONSUMED, (),
                     paradigm=P2,
                     notes="sidebar 经历渲染无 tags 行（enabled=False）"),
    FieldConsumption("experience.tags.enabled", STATUS_UNCONSUMED, (),
                     paradigm=P3,
                     notes="_experience_blocks_minimal 静默丢弃 tags；"
                           "enabled=True 无消费点"),
    FieldConsumption("experience.tags.size", STATUS_PARTIALLY_CONSUMED,
                     (F_RESOLVE_STYLE, F_BANNER),
                     notes="仅 banner tags 行消费；P3 无渲染落点"),
    FieldConsumption("experience.tags.color_role", STATUS_UNCONSUMED,
                     notes="tags 颜色硬编码 muted，role 字符串不读"),
    FieldConsumption("experience.tags.separator", STATUS_UNCONSUMED,
                     notes="tags 原文直出（分隔符已在内容串内），不拆分重组"),
    FieldConsumption("experience.bullet.symbol", STATUS_CONSUMED,
                     (F_RESOLVE_COMPONENTS,)),
    FieldConsumption("experience.bullet.symbol_color_role", STATUS_UNCONSUMED,
                     notes="符号与正文同 run，恒 ink；独立着色无执行点"),
    FieldConsumption("experience.bullet.text_size", STATUS_UNCONSUMED,
                     notes="bullet 实际用 body_size；text_size 无读取点"),
    FieldConsumption("experience.bullet.text_color_role", STATUS_UNCONSUMED,
                     notes="bullet 文字色硬编码 ink，role 字符串零读取"),
    FieldConsumption("experience.bullet.count_min", STATUS_UNCONSUMED,
                     notes="bullet 数量约束无执行点（内容组织策略）"),
    FieldConsumption("experience.bullet.count_max", STATUS_UNCONSUMED,
                     notes="bullet 数量约束无执行点（内容组织策略）"),
    FieldConsumption("experience.bullet_indent", STATUS_UNCONSUMED,
                     notes="无悬挂缩进参数；bullet 间隙仅为组装常量空格"),
    FieldConsumption("experience.bullet_spacing_after", STATUS_CONSUMED,
                     (F_RESOLVE_SPACING,)),
    # Phase 2B-5 Step 1：entry_after 已由 entry_spacing_after 字段独立提供，
    # entry_spacing 字段自身（映射 entry_before）已完成单一职责，不再 partial
    FieldConsumption("experience.entry_spacing", STATUS_CONSUMED,
                     (F_RESOLVE_SPACING,),
                     notes="映射 entry_before；entry_after 由 "
                           "experience.entry_spacing_after 独立提供"),
    FieldConsumption("experience.entry_spacing_after", STATUS_CONSUMED,
                     (F_RESOLVE_SPACING,),
                     notes="Phase 2B-5 Step 1：映射 entry_after；"
                           "banner/minimal/sidebar 三骨架 _SPACING_ROLES "
                           "均包含 entry_after，三范式均消费"),

    # --- achievement ------------------------------------------------------
    FieldConsumption("achievement.enabled", STATUS_UNCONSUMED,
                     notes="全仓无成果横幅渲染代码（P1 enabled=True 静默落空）"),
    FieldConsumption("achievement.maximum_count", STATUS_CONSUMED,
                     (F_VALIDATOR,),
                     notes="Validator ≤1 硬闸门"),
    FieldConsumption("achievement.height", STATUS_UNCONSUMED,
                     notes="无横幅渲染；随 enabled 子树一并失效"),
    FieldConsumption("achievement.background_role", STATUS_UNCONSUMED,
                     notes="无横幅渲染；随 enabled 子树一并失效"),
    FieldConsumption("achievement.text_color_role", STATUS_UNCONSUMED,
                     notes="无横幅渲染；随 enabled 子树一并失效"),
    FieldConsumption("achievement.alignment", STATUS_UNCONSUMED,
                     notes="无横幅渲染；随 enabled 子树一并失效"),
    FieldConsumption("achievement.inset", STATUS_UNCONSUMED,
                     notes="无横幅渲染；随 enabled 子树一并失效"),

    # --- density ----------------------------------------------------------
    FieldConsumption("density.level", STATUS_UNCONSUMED,
                     notes="自适应密度引擎未建立（未来杠杆，当前为策略声明）"),
    FieldConsumption("density.body_line_spacing", STATUS_UNCONSUMED,
                     notes="镜像杠杆；行距权威来源 typography.line_spacing.body"),
    FieldConsumption("density.section_spacing", STATUS_UNCONSUMED,
                     notes="镜像杠杆；权威来源 section.spacing_before"),
    FieldConsumption("density.content_priority", STATUS_UNCONSUMED,
                     notes="内容取舍策略描述，供未来 Engine 使用"),
    FieldConsumption("density.overflow_strategy", STATUS_UNCONSUMED,
                     notes="超页策略描述，供未来 Engine 使用"),

    # --- constraints / root ----------------------------------------------
    FieldConsumption("constraints.*", STATUS_CONSUMED, (F_VALIDATOR,),
                     notes="Validator 全部硬约束规则的输入；非渲染参数"),
    FieldConsumption("design_intent", STATUS_UNCONSUMED,
                     notes="设计意图说明文本，无渲染语义"),
    FieldConsumption("tradeoffs", STATUS_UNCONSUMED,
                     notes="设计权衡说明文本，无渲染语义"),
)


# ---------------------------------------------------------------------------
# 查询 API
# ---------------------------------------------------------------------------

def consumption_matrix() -> Tuple[FieldConsumption, ...]:
    """返回完整消费矩阵（不可变）。"""
    return _CONSUMPTION_MATRIX


def get_consumption(path: str, paradigm: str = "") -> Optional[FieldConsumption]:
    """按字段路径（+可选范式）查登记；范式专属行优先于通用行。"""
    generic = None
    for item in _CONSUMPTION_MATRIX:
        if item.path != path:
            continue
        if item.paradigm == paradigm:
            return item
        if item.paradigm == "" and generic is None:
            generic = item
    return generic


def field_paths() -> Tuple[str, ...]:
    """矩阵覆盖的全部去重字段路径。"""
    seen: List[str] = []
    for item in _CONSUMPTION_MATRIX:
        if item.path not in seen:
            seen.append(item.path)
    return tuple(seen)


# ---------------------------------------------------------------------------
# 未消费字段评估（供 Validator 非阻断 WARNING 使用）
# ---------------------------------------------------------------------------

def _definite(sv: Optional[Sourced]) -> bool:
    """Sourced 是否携带可执行定值（非 None / undetermined / not_applicable）。"""
    return (isinstance(sv, Sourced)
            and not sv.is_undetermined
            and sv.value is not None
            and sv.source != SOURCE_NOT_APPLICABLE)


def _positive_number(sv: Optional[Sourced]) -> bool:
    return _definite(sv) and isinstance(sv.value, (int, float)) and sv.value > 0


@dataclass(frozen=True)
class UnconsumedFinding:
    path: str
    actual: object
    message: str


def evaluate_unconsumed(spec: DesignSpec) -> List[UnconsumedFinding]:
    """找出「Spec 显式给了可执行承诺、但当前 Renderer 零消费点」的字段。

    只产出高信号项：
      - enabled 类：True 才构成承诺（False = 明确不用，不报警）；
      - Sourced 类：定值/positive 才报警，undetermined 已由既有规则覆盖，
        not_applicable 是显式放弃，0 值几何字段视为「关闭」不报警；
      - 枚举类：仅在选择了 Renderer 不具备的形态时报警；
      - 描述/策略/约束元数据与 schema_gap 不参与（矩阵中可见，此处不报警）。
    """
    p = spec.architecture.paradigm
    out: List[UnconsumedFinding] = []

    def add(path, actual, message):
        out.append(UnconsumedFinding(path, actual, message))

    # --- grid -------------------------------------------------------------
    # v0.9.0：P2 的 grid.column_ratio 已真实消费（见矩阵），不再出现在这里。
    # P1/P3 的 column_ratio 是「正文单栏栅格」声明，与身份区两列无关，
    # 不构成「声明了却没落地」的缺口，故也不预警。
    if _positive_number(spec.grid.gutter):
        add("grid.gutter", f"{spec.grid.gutter.value}cm",
            "栏间中缝已显式声明，但 Renderer 无中缝概念，该值零读取")

    # --- page -------------------------------------------------------------
    if _positive_number(spec.page.bleed):
        add("page.bleed", f"{spec.page.bleed.value}cm",
            "出血已显式声明，但 Renderer 无出血实现，该值零读取")

    # --- header -----------------------------------------------------------
    if _definite(spec.header.height):
        add("header.height", f"{spec.header.height.value}cm",
            "身份区高度已显式声明，但实际高度由内容行数与单元格边距派生")
    ti = spec.header.text_inset
    if _positive_number(ti):
        add("header.text_inset", f"{ti.value}cm",
            "文字内缩已显式声明，但格内边距实际取骨架 Profile（cell_*_cm）")

    # --- colors -----------------------------------------------------------
    if _definite(spec.colors.paper):
        add("colors.paper", spec.colors.paper.value,
            "纸张色已显式声明，但无底色渲染落点（依赖 DOCX 默认白底）")
    # v0.9.0：colors.page_background 已真实消费（w:background +
    # displayBackgroundShape），不再出现在这里。
    if _definite(spec.colors.light_sidebar_secondary):
        add("colors.light_sidebar_secondary",
            spec.colors.light_sidebar_secondary.value,
            "侧栏第二色已显式声明，但侧栏仅消费 light_sidebar 单色")

    # --- photo ------------------------------------------------------------
    if spec.photo.enabled and spec.photo.display_shape == "circle":
        add("photo.display_shape", "circle",
            "圆形照片已显式声明，但 Renderer 无圆形裁切，实际降级为矩形盒")
    if spec.photo.enabled and spec.photo.crop_allowed:
        add("photo.crop_allowed", True,
            "裁切许可已开启，但 Renderer 无裁切流水线，该许可无执行点")
    if not spec.photo.enabled and p in (P1, P2):
        add("photo.enabled", False,
            f"{p} 骨架恒插入照片，photo.enabled=False 在该骨架不生效")

    # --- section ----------------------------------------------------------
    if (spec.section.title_style == "icon_hairline"
            and _definite(spec.section.icon.resource)):
        add("section.icon.resource", spec.section.icon.resource.value,
            "图标资源已显式提供，但 Renderer 无图标渲染能力，仍回退文本符号")
    if _positive_number(spec.section.title_indent):
        add("section.title_indent", f"{spec.section.title_indent.value}cm",
            "标题缩进已显式声明，但符号间隙实际为组装常量（单空格）")
    dw = spec.section.divider.weight
    if (_positive_number(dw)
            and _positive_number(spec.section.divider.bleed)):
        add("section.divider.bleed",
            f"{spec.section.divider.bleed.value}cm",
            "divider 外伸量已显式声明，但 divider 渲染无 bleed 参数")
    # banner/sidebar 标题符号与文字同 run 同色 ink，symbol_color_role 不独立
    if p in (P1, P2) and spec.section.symbol_color_role != "ink":
        add("section.symbol_color_role", spec.section.symbol_color_role,
            f"{p} 标题符号与文字同 run（恒 ink），符号色角色在该骨架不生效")

    # --- typography -------------------------------------------------------
    if spec.typography.weights.body != "regular":
        add("typography.weights.body", spec.typography.weights.body,
            "正文字重已显式声明，但正文 run 字重硬编码 regular")
    if spec.typography.weights.metadata != "regular":
        add("typography.weights.metadata", spec.typography.weights.metadata,
            "元信息字重已显式声明，但日期/元信息 run 字重硬编码 regular")
    hms = spec.typography.header_meta_sizes
    if hms and len(hms) > 1 and _definite(hms[1]):
        add("typography.header_meta_sizes[1]", f"{hms[1].value}pt",
            "深块第二档字号已声明，但 Resolver 仅消费 [0]（contact_size）")

    # --- experience -------------------------------------------------------
    if spec.experience.tags.enabled and p == P3:
        add("experience.tags.enabled", True,
            "P3 已启用 tags 行，但 minimal 经历块不渲染 tags（静默丢弃）")
    bs = spec.experience.bullet
    if bs.symbol_color_role != bs.text_color_role:
        add("experience.bullet.symbol_color_role", bs.symbol_color_role,
            "bullet 符号色与文字色不同，但二者同 run 渲染（恒 ink），"
            "符号独立着色无执行点")
    if _definite(bs.text_size):
        add("experience.bullet.text_size", f"{bs.text_size.value}pt",
            "bullet 字号已显式声明，但实际使用 body_size，该字段零读取")
    bi = spec.experience.bullet_indent
    if _positive_number(bi):
        add("experience.bullet_indent", f"{bi.value}cm",
            "bullet 缩进已显式声明，但无悬挂缩进参数（间隙仅为空格常量）")

    # --- achievement（子树整体由 enabled 门控）----------------------------
    if spec.achievement.enabled:
        add("achievement.enabled", True,
            "成果横幅已启用，但 Renderer 无横幅渲染代码（height/角色色/"
            "alignment/inset 子字段一并落空）")

    return out
