# -*- coding: utf-8 -*-
"""spec.py — DesignSpec 数据结构（Phase 2B）。

定位：
    Resume Design Knowledge v1（设计知识）
        ↓（本模块承载）
    DesignSpec（可序列化的设计规格，只描述“怎么设计”，不含任何个人事实）
        ↓
    Validator（design/validator.py）
        ↓
    Renderer（后续阶段接入；本阶段不修改 skeletons.py / layout_kit.py）

设计原则：
    1. 零第三方依赖，仅用 stdlib dataclasses（与 layout_kit.py 风格一致）。
    2. 每一个设计取值都用 Sourced 包装，强制带来源 / 置信度 / 状态，
       杜绝把推测值伪装成知识库事实。
    3. 知识库没有依据的参数一律 undetermined（value=None），禁止编造。
    4. 结构内禁止出现姓名、电话、学校、公司、照片路径等个人信息。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional

# ---------------------------------------------------------------------------
# 来源 / 置信度 / 状态常量
# ---------------------------------------------------------------------------

# source：这个值从哪里来
SOURCE_KNOWLEDGE = "knowledge_v1"      # Resume Design Knowledge v1 明文范围/规则
SOURCE_SAMPLE = "sample_observed"      # 真实样本直接观察/实测（含 v1 未完全覆盖的灰度）
SOURCE_DERIVED = "derived"             # 由 v1 规则推导（如日期制表位、派生列宽）
SOURCE_UNDETERMINED = "undetermined"   # 知识库未覆盖，禁止填值
SOURCE_NOT_APPLICABLE = "not_applicable"  # 显式不适用（如 P1 不用图标），区别于缺口

# confidence：证据强度
CONF_HIGH = "high"          # 样本 A 实测，且落在 v1 范围内
CONF_MEDIUM = "medium"      # 样本 B 图片目测区间
CONF_INFERRED = "inferred"  # 规则推导
CONF_LOW = "low"            # 弱证据
CONF_UNDETERMINED = "undetermined"

# status：执行成熟度
STATUS_CONFIRMED = "confirmed"        # Renderer 可直接执行
STATUS_DERIVED = "derived"            # 可执行但属于推导值，改动需回看规则
STATUS_UNDETERMINED = "undetermined"  # 不可执行，必须走 fallback 或人工确认

# 范式 / 枚举常量
PARADIGM_P1 = "p1_banner_single"
PARADIGM_P2 = "p2_sidebar_two_column"

# 日期定位（硬规则：禁止 spaces）
DATE_TAB_STOP = "tab_stop"
DATE_COLUMN = "column"
DATE_SPACES = "spaces"  # 反模式，Validator 必须报错

# 标题样式
TITLE_SYMBOL = "symbol_hairline"   # ▍ + 粗标题 + 发丝线（P1）
TITLE_ICON = "icon_hairline"       # 语义图标 + 粗标题 + 发丝线（P2 首选）

# 密度档
DENSITY_COMPACT = "compact"
DENSITY_MEDIUM = "medium"
DENSITY_SPACIOUS = "spacious"

# 颜色角色名（Renderer 应只引用角色，不直接写 hex）
ROLE_INK = "ink"
ROLE_ACCENT = "accent"
ROLE_MUTED = "muted"
ROLE_PAPER = "paper"
ROLE_DARK_BLOCK = "dark_block"
ROLE_LIGHT_SIDEBAR = "light_sidebar"
ROLE_HAIRLINE = "hairline"
ROLE_ON_DARK_PRIMARY = "on_dark_primary"
ROLE_ON_DARK_SECONDARY = "on_dark_secondary"
ROLE_ON_DARK_TERTIARY = "on_dark_tertiary"


@dataclass(frozen=True)
class Sourced:
    """带来源证据的设计取值。

    value       实际值（None 表示未确定）
    unit        单位：pt / cm / ratio / hex / text ...
    source      SOURCE_* 常量
    confidence  CONF_* 常量
    status      STATUS_* 常量
    notes       说明（选取理由、偏差、与样本的关系）
    """

    value: Any = None
    unit: str = ""
    source: str = SOURCE_KNOWLEDGE
    confidence: str = CONF_HIGH
    status: str = STATUS_CONFIRMED
    notes: str = ""

    # --- 便于 presets 书写的工厂函数 ---
    @staticmethod
    def kv1(value: Any, unit: str = "", confidence: str = CONF_HIGH,
            notes: str = "") -> "Sourced":
        """来自 Resume Design Knowledge v1 的明文范围/规则。"""
        return Sourced(value, unit, SOURCE_KNOWLEDGE, confidence,
                       STATUS_CONFIRMED, notes)

    @staticmethod
    def observed(value: Any, unit: str = "", confidence: str = CONF_HIGH,
                 notes: str = "") -> "Sourced":
        """来自真实样本观察/实测（可能超出 v1 通用范围，如深底第三级灰）。"""
        return Sourced(value, unit, SOURCE_SAMPLE, confidence,
                       STATUS_CONFIRMED, notes)

    @staticmethod
    def derived(value: Any, unit: str = "", confidence: str = CONF_INFERRED,
                notes: str = "") -> "Sourced":
        """由 v1 规则推导得出（可执行，但 Validator 会给 WARNING）。"""
        return Sourced(value, unit, SOURCE_DERIVED, confidence,
                       STATUS_DERIVED, notes)

    @staticmethod
    def undetermined(notes: str = "") -> "Sourced":
        """知识库缺口：禁止填值，Validator 给 WARNING，Renderer 必须走 fallback。"""
        return Sourced(None, "", SOURCE_UNDETERMINED, CONF_UNDETERMINED,
                       STATUS_UNDETERMINED, notes)

    @staticmethod
    def not_applicable(notes: str = "") -> "Sourced":
        """显式不适用（如 P1 不使用图标）。不是知识缺口，Validator 不报警。"""
        return Sourced(None, "", SOURCE_NOT_APPLICABLE, CONF_HIGH,
                       STATUS_CONFIRMED, notes)

    @property
    def is_undetermined(self) -> bool:
        # 只认真缺口；not_applicable 的 value 也是 None 但状态是 confirmed
        return self.status == STATUS_UNDETERMINED


# ---------------------------------------------------------------------------
# 复合样式小结构
# ---------------------------------------------------------------------------

@dataclass
class Margins:
    """页边距（cm），顺序：上/下/左/右。"""
    top: Sourced
    bottom: Sourced
    left: Sourced
    right: Sourced


@dataclass
class SafeArea:
    """安全区（cm），通常由 page size - margins 派生；bleed 未定时整体 undetermined。"""
    top: Sourced
    bottom: Sourced
    left: Sourced
    right: Sourced
    content_width: Sourced


@dataclass
class AccentLine:
    """身份区底部强调色条。"""
    enabled: bool
    height: Sourced
    color_role: str = ROLE_ACCENT
    placement: str = "header_bottom_full_width"


@dataclass
class TextStyle:
    """一段文字的排版样式。weight 允许 "undetermined"（P2 角色行字重缺口）。"""
    size: Sourced
    weight: str = "regular"          # regular / bold / undetermined
    color_role: str = ROLE_INK
    separator: Optional[str] = None  # 如角色前的 ｜


@dataclass
class Divider:
    """板块标题下发丝线。"""
    style: str = "hairline"
    weight: Sourced = field(default_factory=lambda: Sourced.kv1(0.5, "pt"))
    color_role: str = ROLE_HAIRLINE
    width_rule: str = "column_content_width"  # 单栏=正文宽；双栏=所在栏宽
    bleed: Sourced = field(default_factory=lambda: Sourced.kv1(0.0, "cm"))


@dataclass
class IconSpec:
    """P2 语义图标契约。知识库无图标资源，resource 必须保持 undetermined。"""
    primary: str = "semantic_icon"
    fallback: str = TITLE_SYMBOL
    resource: Sourced = field(default_factory=lambda: Sourced.undetermined(
        "v1 未定义图标集/尺寸/风格/文件格式，Renderer 必须回退 symbol_title"))
    icon_color_role: str = ROLE_ACCENT


@dataclass
class TagLine:
    """经历条目下的能力标签链（· 分隔的灰色关键词行，P1 启用）。"""
    enabled: bool
    size: Sourced
    color_role: str = ROLE_MUTED
    separator: str = "·"


@dataclass
class BulletStyle:
    symbol: str = "•"
    symbol_color_role: str = ROLE_ACCENT
    text_size: Sourced = field(default_factory=lambda: Sourced.kv1(9.5, "pt"))
    text_color_role: str = ROLE_INK
    count_min: int = 1
    count_max: int = 4


@dataclass
class PhotoFallback:
    """照片主方案无法稳定实现时的降级（P2 圆形 → 直角）。"""
    container: str
    width: Sourced
    height: Sourced
    aspect_ratio: Sourced


@dataclass(frozen=True)
class PhotoFloating:
    """浮动定位（wp:anchor；Golden Sample CL-01 产品化）。

    仅 minimal 范式消费；None 或 enabled=False 时照片保持内联（wp:inline）
    旧行为，P1/P2 与所有旧路径字节级不变。
    位置用相对锚点 + posOffset 表达，禁止在产品代码固化某份简历的坐标。

    position_h / position_v：OOXML wp:positionH/V 的 relativeFrom。
    当前仅验证 Golden Sample 确认的锚点（horizontal=column「列内」、
    vertical=page「页面顶」），白名单见 validator。
    offset_x_cm / offset_y_cm：相对锚点的绝对偏移（cm）；None=0。
    """
    enabled: bool
    position_h: str = "column"
    position_v: str = "page"
    offset_x_cm: Optional[Sourced] = None
    offset_y_cm: Optional[Sourced] = None


@dataclass(frozen=True)
class PhotoBorder:
    """照片边框（作用于图片图形 a:ln；Golden Sample CL-01 产品化）。

    width_pt=0 表示无边框；有宽度时 color 必须为合法 #RRGGBB。
    """
    color: Sourced
    width_pt: Sourced


# ---------------------------------------------------------------------------
# 一级 Spec 节点
# ---------------------------------------------------------------------------

@dataclass
class MetaSpec:
    spec_id: str
    version: str
    paradigm: str
    source_knowledge_version: str = "v1"
    confidence: str = CONF_HIGH
    notes: str = ""


@dataclass
class PageSpec:
    size: Sourced                       # value: "A4"
    width_cm: Sourced
    height_cm: Sourced
    orientation: str                    # portrait
    target_pages: Sourced               # value: 1（目标声明，非渲染结果保证）
    margins: Margins
    bleed: Sourced                      # P2 缺口：undetermined
    safe_area: SafeArea


@dataclass
class ArchitectureSpec:
    paradigm: str
    column_count: int
    content_flow: List[str]             # 板块顺序（核心四板块固定）
    sidebar_enabled: bool = False
    sidebar_contains: List[str] = field(default_factory=list)
    main_contains: List[str] = field(default_factory=list)


@dataclass
class GridSpec:
    column_ratio: List[float]           # 如 [1.0] 或 [0.32, 0.68]
    gutter: Sourced                     # 双栏中缝
    width_rule: str                     # 表宽单一来源公式
    column_widths_cm: Sourced           # 派生列宽；依赖未定边距时 undetermined


@dataclass
class HeaderSpec:
    type: str
    height: Sourced                     # P2 缺口：undetermined
    background_role: Optional[str]      # dark_block / None
    accent_line: AccentLine
    identity_alignment: str
    photo_zone: str
    text_inset: Optional[Sourced] = None


@dataclass
class TypographyWeights:
    name: str = "bold"
    section_title: str = "bold"
    organization: str = "bold"
    role: str = "bold"
    body: str = "regular"
    metadata: str = "regular"
    sidebar_group_label: str = "bold"


@dataclass
class LineSpacing:
    body: Sourced
    title: Sourced
    sidebar_body: Optional[Sourced] = None


@dataclass
class TypographySpec:
    font_family: Sourced                # sans_zh 令牌；单字体族
    weights: TypographyWeights
    name_size: Sourced
    title_size: Sourced
    organization_size: Sourced
    role_size: Sourced
    body_size: Sourced
    metadata_size: Sourced
    line_spacing: LineSpacing
    minimum_body_size: Sourced
    header_meta_sizes: Optional[List[Sourced]] = None  # P1 深块内 8.0/8.5
    sidebar_body_size: Optional[Sourced] = None        # P2 侧栏小一档
    sidebar_group_label_size: Optional[Sourced] = None # P2 缺口：undetermined
    # 西文字体（PDF_2 ArialMT / PDF_1 侧栏 Calibri）；默认 None 表示与
    # font_family 共用。本阶段 Renderer 不消费，仅 schema 层表达。
    latin_font: Optional[Sourced] = None


@dataclass
class ColorSpec:
    ink: Optional[Sourced]
    accent: Optional[Sourced]
    muted: Optional[Sourced]
    paper: Optional[Sourced]
    dark_block: Optional[Sourced]
    light_sidebar: Optional[Sourced]
    hairline: Optional[Sourced]
    on_dark_primary: Optional[Sourced] = None
    on_dark_secondary: Optional[Sourced] = None
    on_dark_tertiary: Optional[Sourced] = None
    accent_area_limit: Sourced = field(
        default_factory=lambda: Sourced.kv1(0.05, "ratio"))
    # 防御性槽位：正常 Spec 必须为空；Validator 用它检测“第二个强调色”
    additional_accents: List[Sourced] = field(default_factory=list)
    # 页面级背景色（PDF_1 主区 #F4F4F4 / PDF_4 整页 #EDF4F1）；默认 None 表示
    # 不消费。本阶段 Renderer 不消费，仅 schema 层表达。
    page_background: Optional[Sourced] = None
    # P2 侧栏第二色（PDF_1 #B8C9D4）；默认 None 表示不消费。
    # 本阶段 Renderer 不消费，仅 schema 层表达。
    light_sidebar_secondary: Optional[Sourced] = None


@dataclass
class PhotoSpec:
    enabled: bool
    position: str
    width: Sourced
    height: Sourced
    aspect_ratio: Sourced
    container: str
    display_shape: str                  # rect / circle
    distortion_allowed: bool = False    # 硬规则：必须 False
    crop_allowed: bool = False
    source_crop: str = "none"
    fallback: Optional[PhotoFallback] = None
    floating: Optional[PhotoFloating] = None   # None=内联旧行为
    border: Optional[PhotoBorder] = None       # None=无边框


@dataclass
class SectionSpec:
    title_style: str
    prefix: Sourced
    icon: IconSpec
    divider: Divider
    title_weight: str = "bold"
    title_color_role: str = ROLE_INK
    symbol_color_role: str = ROLE_ACCENT
    title_indent: Sourced = field(default_factory=lambda: Sourced.kv1(0.25, "cm"))
    spacing_before: Sourced = field(default_factory=lambda: Sourced.kv1(22, "pt"))
    divider_to_first_line: Sourced = field(default_factory=lambda: Sourced.kv1(6, "pt"))
    title_spacing_after: Sourced = field(
        default_factory=lambda: Sourced.kv1(1, "pt"))
    styles_per_document: Sourced = field(
        default_factory=lambda: Sourced.kv1(1, "count"))


@dataclass
class ExperienceSpec:
    organization: TextStyle
    role: TextStyle
    date: TextStyle
    date_alignment: str                 # tab_stop / column；spaces 非法
    tags: TagLine
    bullet: BulletStyle
    bullet_indent: Sourced
    bullet_spacing_after: Sourced
    entry_spacing: Sourced
    entry_spacing_after: Sourced = field(
        default_factory=lambda: Sourced.kv1(1, "pt"))


@dataclass
class AchievementSpec:
    enabled: bool
    maximum_count: int                  # 硬规则：<= 1
    height: Sourced
    background_role: str = ROLE_ACCENT
    text_color_role: str = ROLE_ON_DARK_PRIMARY
    alignment: str = "center"
    inset: Optional[Sourced] = None


@dataclass
class DensitySpec:
    level: str
    body_line_spacing: Sourced
    section_spacing: Sourced
    content_priority: List[str]
    overflow_strategy: List[str]


@dataclass
class ConstraintsSpec:
    """硬约束清单，Validator 直接读取；Renderer 与 Engine 均不得绕过。"""
    single_page: bool = True
    minimum_body_font_size_pt: float = 9.0
    single_font_family: bool = True
    single_accent_color: bool = True
    single_section_title_style: bool = True
    maximum_achievement_banner: int = 1
    no_space_based_date_alignment: bool = True
    photo_no_distortion: bool = True
    narrow_column_min_ratio: float = 0.28
    bottom_reserve_cm: float = 1.0
    column_height_imbalance_max_lines: int = 3
    table_width_rule: str = "A4_width - margin_left - margin_right"


@dataclass
class DesignSpec:
    """完整设计规格根节点。只描述“怎么设计”，禁止任何个人事实。"""
    metadata: MetaSpec
    page: PageSpec
    architecture: ArchitectureSpec
    grid: GridSpec
    header: HeaderSpec
    typography: TypographySpec
    colors: ColorSpec
    photo: PhotoSpec
    section: SectionSpec
    experience: ExperienceSpec
    achievement: AchievementSpec
    density: DensitySpec
    constraints: ConstraintsSpec
    design_intent: str = ""
    tradeoffs: List[str] = field(default_factory=list)
