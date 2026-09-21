# -*- coding: utf-8 -*-
"""assembly.py — 最小 Design Engine 装配层（Phase 2B-4 Step 6 / v0.9.0 扩容）。

定位
----
    Preset 范式基线（design/presets.py，build_pX_spec）
        ↓  assemble_job_spec（本模块）：范式基线 + 本份设计 delta
    Job-specific DesignSpec
        ↓  validate_spec（design/validator.py，硬边界，不可绕过）
        ↓  build_document(design_spec=...)（skeletons._build_from_spec 内
           会再次校验，ERROR 直接拒绝渲染）

职责边界
--------
- 本模块只做「不可变装配」：用 dataclasses.replace 从基线派生新 Spec，
  绝不原地修改基线，也不产出新的配置类型（不允许出现与 DesignSpec
  平行的第二套 Job/Layout/Floating Config）。
- 本模块不重新实现任何校验：非法取值由现有 validate_spec 拦截。
- 本模块不读 JD / 简历库 / 用户偏好文件，不含任何个人事实；
  「本份 delta 由谁决定」是上游生成层的职责。

v0.9.0 变更（2026-09-21）
------------------------
**把「每个设计节点都有正式 delta 通道」补全。** 此前只有 photo /
typography / section / experience 四个 delta，而**页边距、配色、栅格、
身份区、密度五个节点没有通道**。后果不是「改不了」，而是「每个 agent
各自发明一套 `dataclasses.replace(spec.page, ...)` 土办法」——不可复现、
容易漏改派生字段（如 safe_area 与 margins 必须同步），且完全绕过
装配层的类型检查。而这五个节点恰恰是**每份简历最该变的东西**。

现在 page / grid / header / colors / density 五个节点都有了正式入口，
另提供两个防漏改的便捷构造器：

    page_delta_from_margins()   —— 同步推导 safe_area 与 content_width
    color_delta_from_roles()    —— 按颜色角色覆盖，其余保持基线

旧签名完全兼容：所有新增参数都有 None 默认值，不传即行为与 v0.8.x 一致。
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, Optional, Sequence, Tuple, Type

from .spec import (
    ColorSpec,
    DensitySpec,
    DesignSpec,
    ExperienceSpec,
    GridSpec,
    HeaderSpec,
    PageSpec,
    PhotoSpec,
    SectionSpec,
    Sourced,
    TypographySpec,
)

__all__ = [
    "assemble_job_spec",
    "page_delta_from_margins",
    "color_delta_from_roles",
    "DELTA_NODES",
]

# 参数名 → (DesignSpec 一级节点名, 期望类型)。装配循环与报错文案共用同一张表，
# 新增 delta 只需在这里登记一行，不会再出现「某个节点忘了加通道」。
DELTA_NODES: Dict[str, Tuple[str, Type]] = {
    "photo_delta": ("photo", PhotoSpec),
    "typography_delta": ("typography", TypographySpec),
    "section_delta": ("section", SectionSpec),
    "experience_delta": ("experience", ExperienceSpec),
    # --- v0.9.0 新增：此前无通道的五个节点 ---
    "page_delta": ("page", PageSpec),
    "grid_delta": ("grid", GridSpec),
    "header_delta": ("header", HeaderSpec),
    "color_delta": ("colors", ColorSpec),
    "density_delta": ("density", DensitySpec),
}

# 构造 delta 的推荐写法（报错文案里给出，避免 agent 另建配置类型）
_CONSTRUCT_HINT = {
    "photo_delta": "base_spec.photo",
    "typography_delta": "base_spec.typography",
    "section_delta": "base_spec.section",
    "experience_delta": "base_spec.experience",
    "page_delta": "base_spec.page",
    "grid_delta": "base_spec.grid",
    "header_delta": "base_spec.header",
    "color_delta": "base_spec.colors",
    "density_delta": "base_spec.density",
}

# A4 尺寸（cm）——page_delta_from_margins 推导 safe_area / content_width 用。
# 与 layout_kit.A4_WIDTH_CM / A4_HEIGHT_CM 同源；此处不 import 渲染层，
# 保持 design 包对渲染层零依赖（design 只描述「应该长什么样」）。
_A4_W_CM = 21.0
_A4_H_CM = 29.7


def assemble_job_spec(
    base_spec: DesignSpec,
    *,
    photo_delta: Optional[PhotoSpec] = None,
    typography_delta: Optional[TypographySpec] = None,
    section_delta: Optional[SectionSpec] = None,
    experience_delta: Optional[ExperienceSpec] = None,
    page_delta: Optional[PageSpec] = None,
    grid_delta: Optional[GridSpec] = None,
    header_delta: Optional[HeaderSpec] = None,
    color_delta: Optional[ColorSpec] = None,
    density_delta: Optional[DensitySpec] = None,
) -> DesignSpec:
    """把范式基线 Spec 与本份简历的设计 delta 装配成新的 DesignSpec。

    每个 delta 都是「**整节点替换**」（不是字段级补差量）：传了就整体换，
    不传就保持基线。这样语义只有一条，不需要记住「哪些字段会被合并」。

    :param base_spec: 范式基线（通常来自 build_p1/p2/p3_spec()）。
        调用方应把它视为只读；本函数绝不修改它。
    :param photo_delta: 本份完整 PhotoSpec。
        典型构造::

            photo_delta = dataclasses.replace(
                base_spec.photo, enabled=True,
                width=Sourced.kv1(2.2, "cm"),
                height=Sourced.kv1(3.139, "cm"),
                aspect_ratio=Sourced.kv1(2.2 / 3.139, "ratio"),
                floating=PhotoFloating(
                    enabled=True, position_h="column", position_v="page",
                    offset_x_cm=Sourced.kv1(17.066, "cm"),
                    offset_y_cm=Sourced.kv1(0.6, "cm")),
                border=PhotoBorder(Sourced.kv1("#BFBFBF"),
                                   Sourced.kv1(2.25, "pt")))

    :param typography_delta: 本份 TypographySpec（字号 / 行距 / 字重）。
    :param section_delta: 本份 SectionSpec（板块标题 / 分割线 / 板块间距）。
    :param experience_delta: 本份 ExperienceSpec（经历条目 / bullet 节奏）。
    :param page_delta: 本份 PageSpec（页边距 / 目标页数 / 安全区）。
        强烈建议用 :func:`page_delta_from_margins` 构造：它会同步推导
        ``safe_area`` 与 ``content_width``，避免只改 margins 而让派生字段
        停留在旧值（历史事故：改了边距忘了 safe_area，Validator 报
        table_width 超版心）。
    :param grid_delta: 本份 GridSpec（正文栏比例 / 身份区列比例）。
        ``identity_band_ratio`` 在本版起被 Renderer 真正消费
        （此前是死字段，列宽硬编码在 skeletons._LAYOUT_CONFIG）。
    :param header_delta: 本份 HeaderSpec（身份区形态 / 对齐 / 强调线）。
    :param color_delta: 本份 ColorSpec（配色角色）。
        建议用 :func:`color_delta_from_roles` 构造。
    :param density_delta: 本份 DensitySpec（密度等级 / 溢出策略声明）。

    :return: 装配后的新 DesignSpec。所有 delta 均为 None 时原样返回
        ``base_spec``（同一对象）；只要有任一 delta 提供，即用
        ``dataclasses.replace`` 生成新对象，被替换的一级节点换为 delta，
        其余节点保持身份共享。调用方必须再经 validate_spec 校验后才能
        送入 build_document；spec 渲染路径内部也会强制校验，ERROR 拒绝渲染。

    注意（深层不可变）：dataclasses.replace 是浅拷贝，DesignSpec 既有
    List 字段（architecture.content_flow / grid.column_ratio /
    colors.additional_accents / density.* / tradeoffs 等）会在新旧 Spec
    间共享同一 list 对象。当前所有生产代码对这些字段只读、只在 preset
    构造期赋值，因此无实际 alias 风险；调用方也不得在装配后原地改这些
    list。需要隔离时由上游构造全新 list，不在本层做深拷贝。
    """
    if not isinstance(base_spec, DesignSpec):
        raise TypeError(
            f"base_spec 必须是 DesignSpec 实例，收到 {type(base_spec).__name__}")

    provided = {
        "photo_delta": photo_delta,
        "typography_delta": typography_delta,
        "section_delta": section_delta,
        "experience_delta": experience_delta,
        "page_delta": page_delta,
        "grid_delta": grid_delta,
        "header_delta": header_delta,
        "color_delta": color_delta,
        "density_delta": density_delta,
    }

    # 所有 delta 均为 None：保持原行为，原样返回 base_spec（同一对象）。
    if all(v is None for v in provided.values()):
        return base_spec

    replacements: dict = {}
    for param, value in provided.items():
        if value is None:
            continue
        node_name, expected_type = DELTA_NODES[param]
        if not isinstance(value, expected_type):
            raise TypeError(
                f"{param} 必须是 {expected_type.__name__} 实例或 None，"
                f"收到 {type(value).__name__}；"
                f"请用 dataclasses.replace({_CONSTRUCT_HINT[param]}, ...) 构造，"
                f"不要另建配置类型")
        replacements[node_name] = value

    return replace(base_spec, **replacements)


def page_delta_from_margins(
    base_page: PageSpec,
    margins_cm: Sequence[float],
    *,
    notes: str = "",
    target_pages: Optional[int] = None,
) -> PageSpec:
    """由四个边距数值构造 PageSpec delta，并**同步推导** safe_area。

    为什么需要这个函数：``PageSpec.margins`` 与 ``PageSpec.safe_area`` 是
    必须保持一致的派生关系（safe_area 是版心、content_width = 21 - 左 - 右）。
    手写 ``dataclasses.replace(page, margins=...)`` 时极易只改一个而忘另一个，
    然后被 Validator 的 table_width 规则拦下，浪费时间排查。

    :param base_page: 范式基线的 page 节点（只读）。
    :param margins_cm: (top, bottom, left, right)，单位 cm。
    :param notes: 写入 Sourced.notes 的取舍说明（建议写清依据，便于追溯）。
    :param target_pages: 目标页数；None 保持基线（P1/P3 为 1）。
    :return: 新的 PageSpec（safe_area 已按边距重算）。
    """
    if len(margins_cm) != 4:
        raise ValueError(
            f"margins_cm 必须是 (top, bottom, left, right) 四元组，"
            f"收到 {len(margins_cm)} 个值：{tuple(margins_cm)}")
    top, bottom, left, right = (float(v) for v in margins_cm)
    if min(top, bottom, left, right) < 0:
        raise ValueError(f"页边距不得为负：{tuple(margins_cm)}")

    def _note(text: str) -> str:
        return f"{text}｜{notes}" if notes else text

    content_width = _A4_W_CM - left - right
    content_height = _A4_H_CM - top - bottom
    page = replace(
        base_page,
        margins=replace(
            base_page.margins,
            top=Sourced.kv1(top, "cm", notes=_note("本份 Design Decision：上边距")),
            bottom=Sourced.kv1(bottom, "cm", notes=_note("本份 Design Decision：下边距")),
            left=Sourced.kv1(left, "cm", notes=_note("本份 Design Decision：左边距")),
            right=Sourced.kv1(right, "cm", notes=_note("本份 Design Decision：右边距")),
        ),
        safe_area=replace(
            base_page.safe_area,
            top=Sourced.derived(top, "cm", notes=_note("= margins.top（派生）")),
            bottom=Sourced.derived(bottom, "cm", notes=_note("= margins.bottom（派生）")),
            left=Sourced.derived(left, "cm", notes=_note("= margins.left（派生）")),
            right=Sourced.derived(right, "cm", notes=_note("= margins.right（派生）")),
            content_width=Sourced.derived(
                round(content_width, 4), "cm",
                notes=_note(f"= {_A4_W_CM} - 左 - 右")),
        ),
    )
    if target_pages is not None:
        page = replace(
            page,
            target_pages=Sourced.kv1(int(target_pages), "count",
                                     notes=_note("本份目标页数")))
    # content_height 不是 PageSpec 的字段（PageSpec 只声明 content_width），
    # 版心高度由 Renderer 侧按 A4 - 上下边距 现算，这里不臆造字段。
    _ = content_height
    return page


def color_delta_from_roles(
    base_colors: ColorSpec,
    *,
    accent: Optional[str] = None,
    hairline: Optional[str] = None,
    page_background: Optional[str] = None,
    ink: Optional[str] = None,
    muted: Optional[str] = None,
    paper: Optional[str] = None,
    notes: str = "",
) -> ColorSpec:
    """按**颜色角色**覆盖 ColorSpec，未点名的角色保持基线。

    只接受已确定的角色值（hex 字符串）。需要「显式声明某角色不使用」
    （None）时直接改 dataclass 字段，不走本函数 —— 本函数的语义是
    「本份换掉这几个颜色」，不是「重定义全部颜色」。

    :param base_colors: 范式基线 colors 节点（只读）。
    :param accent: 强调色（意向行 / 标题符号 / bullet 符号）。
    :param hairline: 发丝线色（板块分割线）。
    :param page_background: 页面底色（Renderer 侧写 w:background）。
    :param ink: 正文墨色。:param muted: 次要信息色。:param paper: 纸面色。
    :return: 新的 ColorSpec。
    """
    overrides = {
        "accent": accent,
        "hairline": hairline,
        "page_background": page_background,
        "ink": ink,
        "muted": muted,
        "paper": paper,
    }
    kwargs: Dict[str, Sourced] = {}
    for role, value in overrides.items():
        if value is None:
            continue
        if not isinstance(value, str) or not value.strip():
            raise TypeError(
                f"{role} 必须是非空 hex 字符串（如 '#DD001B'）或 None，"
                f"收到 {value!r}")
        kwargs[role] = Sourced.kv1(
            value.strip(), "hex",
            notes=(f"{notes}｜" if notes else "") + f"本份 Design Decision：{role}")
    if not kwargs:
        return base_colors
    return replace(base_colors, **kwargs)
