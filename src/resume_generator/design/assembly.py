# -*- coding: utf-8 -*-
"""assembly.py — 最小 Design Engine 装配层（Phase 2B-4 Step 6）。

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
- 本模块不重新实现任何校验：非法 PhotoFloating / PhotoBorder 由
  现有 validate_spec 拦截（RULE_PHOTO_FLOATING / RULE_PHOTO_BORDER）。
- 本模块不读 JD / 简历库 / 用户偏好文件，不含任何个人事实；
  「本份 delta 由谁决定」是上游生成层的职责（见 Phase 2B-4 Step 5 分析）。

Step 6 范围：仅支持 PhotoSpec 节点级 delta；后续 delta（layout 等）
按相同模式追加关键字参数，不改变本函数语义。

Step 7-G：在不新建 Spec 类型的前提下，将已存在且 Renderer 已消费的
TypographySpec / SectionSpec / ExperienceSpec 节点级 delta 接入装配入口，
使正式链路可以表达已有 Design Decision。
"""
from __future__ import annotations

from dataclasses import replace
from typing import Optional

from .spec import (
    DesignSpec,
    ExperienceSpec,
    PhotoSpec,
    SectionSpec,
    TypographySpec,
)

__all__ = ["assemble_job_spec"]


def assemble_job_spec(
    base_spec: DesignSpec,
    *,
    photo_delta: Optional[PhotoSpec] = None,
    typography_delta: Optional[TypographySpec] = None,
    section_delta: Optional[SectionSpec] = None,
    experience_delta: Optional[ExperienceSpec] = None,
) -> DesignSpec:
    """把范式基线 Spec 与本份简历的设计 delta 装配成新的 DesignSpec。

    :param base_spec: 范式基线（通常来自 build_p1/p2/p3_spec()）。
        调用方应把它视为只读；本函数绝不修改它。
    :param photo_delta: 本份简历的完整 PhotoSpec 替换节点。
        - None（默认）：照片设计保持基线不变。
        - PhotoSpec：作为新 Spec 的 photo 节点（节点级替换）。
          其 ``floating`` / ``border`` 子节点同样是「提供才覆盖」：
          不挂 PhotoFloating/PhotoBorder 即保持 None（内联旧行为）；
          挂载时未给的字段使用这两个 frozen dataclass 自身的默认值
          （position_h="column" / position_v="page" / offset 默认 0）。
        典型构造方式（不可变、只改本份需要的字段）::

            photo_delta = dataclasses.replace(
                base_spec.photo, enabled=True,
                width=Sourced.kv1(2.212, "cm"), ...,
                floating=PhotoFloating(enabled=True,
                                       offset_x_cm=Sourced.kv1(1.0, "cm")),
                border=PhotoBorder(Sourced.kv1("#BFBFBF"),
                                   Sourced.kv1(2.25, "pt")))

    :param typography_delta: 本份 TypographySpec 替换节点（None 保持基线）。
        典型用法::

            typography_delta = dataclasses.replace(
                base_spec.typography,
                line_spacing=LineSpacing(
                    body=Sourced.kv1(1.08, "ratio"),
                    title=Sourced.kv1(1.05, "ratio")),
            )

    :param section_delta: 本份 SectionSpec 替换节点（None 保持基线）。
        典型用法::

            section_delta = dataclasses.replace(
                base_spec.section,
                spacing_before=Sourced.kv1(5, "pt"),
            )

    :param experience_delta: 本份 ExperienceSpec 替换节点（None 保持基线）。
        典型用法::

            experience_delta = dataclasses.replace(
                base_spec.experience,
                entry_spacing=Sourced.kv1(3, "pt"),
                bullet_spacing_after=Sourced.kv1(1.5, "pt"),
            )

    :return: 装配后的新 DesignSpec。
             当所有 delta 均为 None 时，原样返回 ``base_spec``（同一对象，
             无拷贝必要）；只要有任一 delta 提供，即通过 ``dataclasses.replace``
             生成新对象，被替换的一级节点换为 delta，其余节点保持身份共享。
             调用方必须再经 validate_spec 校验后才能送入 build_document；
             spec 渲染路径内部也会强制校验，ERROR 拒绝渲染。

    注意（深层不可变）：dataclasses.replace 是浅拷贝，DesignSpec 既有
    List 字段（architecture.content_flow / grid.column_ratio /
    colors.additional_accents / density.* / tradeoffs 等）会在新旧 Spec
    间共享同一 list 对象。当前所有生产代码对这些字段只读、只在 preset
    构造期赋值，因此无实际 alias 风险；调用方也不得在装配后原地改这些
    list。需要隔离时由上游构造全新 list，不在本层做深拷贝（避免赋予
    非冻结 Spec 虚假的可变性语义）。
    """
    if not isinstance(base_spec, DesignSpec):
        raise TypeError(
            f"base_spec 必须是 DesignSpec 实例，收到 {type(base_spec).__name__}")

    # 所有 delta 均为 None：保持原行为，原样返回 base_spec（同一对象）。
    if all(d is None for d in (photo_delta, typography_delta,
                               section_delta, experience_delta)):
        return base_spec

    replacements: dict = {}

    if photo_delta is not None:
        if not isinstance(photo_delta, PhotoSpec):
            raise TypeError(
                f"photo_delta 必须是 PhotoSpec 实例或 None，"
                f"收到 {type(photo_delta).__name__}；"
                f"请用 dataclasses.replace(base_spec.photo, ...) 构造，"
                f"不要另建配置类型")
        replacements["photo"] = photo_delta

    if typography_delta is not None:
        if not isinstance(typography_delta, TypographySpec):
            raise TypeError(
                f"typography_delta 必须是 TypographySpec 实例或 None，"
                f"收到 {type(typography_delta).__name__}；"
                f"请用 dataclasses.replace(base_spec.typography, ...) 构造，"
                f"不要另建配置类型")
        replacements["typography"] = typography_delta

    if section_delta is not None:
        if not isinstance(section_delta, SectionSpec):
            raise TypeError(
                f"section_delta 必须是 SectionSpec 实例或 None，"
                f"收到 {type(section_delta).__name__}；"
                f"请用 dataclasses.replace(base_spec.section, ...) 构造，"
                f"不要另建配置类型")
        replacements["section"] = section_delta

    if experience_delta is not None:
        if not isinstance(experience_delta, ExperienceSpec):
            raise TypeError(
                f"experience_delta 必须是 ExperienceSpec 实例或 None，"
                f"收到 {type(experience_delta).__name__}；"
                f"请用 dataclasses.replace(base_spec.experience, ...) 构造，"
                f"不要另建配置类型")
        replacements["experience"] = experience_delta

    return replace(base_spec, **replacements)
