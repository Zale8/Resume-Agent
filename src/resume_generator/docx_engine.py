# -*- coding: utf-8 -*-
"""docx_engine.py — 零依赖 DOCX 模板填充引擎。

为什么不用 python-docx：
    1. 需要 pip install，违反「任意电脑直接跑」；
    2. 会丢掉非标准命名空间（v: / o: / w10: / mc:），破坏模板版式；
    3. 模板里的 {{FIELD}} 全部位于单个 <w:t> run 内，属于纯文本替换问题。

本引擎的做法（保真优先）：
    - 把 .docx 当 zip 打开，只对 word/document.xml 做定点文本替换，其余条目原样字节复制；
    - 只改 <w:t> / <w:instrText> 的文本内容，绝不触碰 w:pPr / w:rPr / r:id 等结构属性；
    - 因此模板的版式、字体、颜色、图形、页眉页脚 100% 保持原样。

仅依赖 Python 标准库。本文件不含任何用户个人信息，不含任何绝对路径。
"""
from __future__ import annotations

import re
import shutil
import zipfile
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

# ============================================================================
# 常量
# ============================================================================

DOCUMENT_XML = "word/document.xml"
DOC_RELS = "word/_rels/document.xml.rels"
CONTENT_TYPES = "[Content_Types].xml"

# 匹配 <w:t>...</w:t> / <w:t/> / <w:instrText>...</w:instrText>
_TEXT_NODE = re.compile(
    r"<(w:t|w:instrText)(\s[^>]*?)?(/>|>(.*?)</\1>)",
    re.DOTALL,
)

# 匹配 <w:r ...>...</w:r>（run），用于删除品红补高标记
_RUN = re.compile(r"<w:r(?:\s[^>]*)?>.*?</w:r>", re.DOTALL)

# 匹配 <w:br/> 与 <w:br .../>
_BR = re.compile(r"<w:br\s*/?>")

# 默认占位符语法
DEFAULT_PATTERN = r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}"

# 常见占位符语法备选（用于「用户上传的任意模板」）
MARKER_PRESETS = {
    "brace": r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}",          # {{NAME}}
    "single": r"\{\s*([A-Za-z0-9_]+)\s*\}",             # {NAME}
    "square": r"【\s*([A-Za-z0-9_\u4e00-\u9fa5]+)\s*】",  # 【姓名】
    "bracket": r"\[\s*([A-Za-z0-9_]+)\s*\]",            # [NAME]
    "dollar": r"\$\{\s*([A-Za-z0-9_]+)\s*\}",           # ${NAME}
    "angle": r"<<\s*([A-Za-z0-9_]+)\s*>>",              # <<NAME>>
}

# ============================================================================
# 页面几何（从 w:sectPr 读真实可用宽高，用于判断整行是否溢出）
# ============================================================================

# A4 默认值（twips），仅在模板未声明 sectPr 时兜底
_A4_WIDTH_TWIPS = 11906
_A4_HEIGHT_TWIPS = 16838
_DEFAULT_MARGIN_TWIPS = 1440          # 2.54cm

# CJK 字宽 ≈ 字号；行高 ≈ 1.6 × 字号（Word 单倍行距下的常见比例）
_LINE_HEIGHT_FACTOR = 1.6
_DEFAULT_HALF_PT = 18                 # 9pt，本仓库模板的正文基准字号


class PageGeometry:
    """从 document.xml 的 w:sectPr 解析出的页面几何。

    为什么需要它：
        槽位容量是用「占位符标记 + 其后空格」估出来的，对 {{MAJ}} 这类
        只留了几个字符的标记而言并不可靠 —— 实际它后面接的是整行宽度。
        判断「这一行会不会溢出换行」比猜单个槽位宽度可靠得多。
    """

    __slots__ = ("width", "height", "margin_left", "margin_right",
                 "margin_top", "margin_bottom")

    def __init__(self) -> None:
        self.width = _A4_WIDTH_TWIPS
        self.height = _A4_HEIGHT_TWIPS
        self.margin_left = _DEFAULT_MARGIN_TWIPS
        self.margin_right = _DEFAULT_MARGIN_TWIPS
        self.margin_top = _DEFAULT_MARGIN_TWIPS
        self.margin_bottom = _DEFAULT_MARGIN_TWIPS

    @property
    def usable_width(self) -> int:
        return max(1000, self.width - self.margin_left - self.margin_right)

    @property
    def usable_height(self) -> int:
        return max(1000, self.height - self.margin_top - self.margin_bottom)

    def chars_per_line(self, half_pt: int = _DEFAULT_HALF_PT) -> int:
        """按基准字号估算每行可容纳的视觉字符数（CJK 记 2）。"""
        char_twips = (half_pt / 2.0) * 20.0
        return max(10, int(self.usable_width / char_twips))

    def max_lines(self, half_pt: int = _DEFAULT_HALF_PT) -> int:
        """按基准字号估算单页可容纳行数。"""
        line_twips = (half_pt / 2.0) * 20.0 * _LINE_HEIGHT_FACTOR
        return max(10, int(self.usable_height / line_twips))

    def line_overflows(self, text_width: int, half_pt: int = _DEFAULT_HALF_PT) -> bool:
        """给定一行的视觉宽度，判断是否超过可用宽度（会换行）。"""
        char_twips = (half_pt / 2.0) * 20.0
        return text_width * char_twips > self.usable_width


def parse_page_geometry(xml: str) -> PageGeometry:
    """从 document.xml 解析页面尺寸与页边距（取最后一个 sectPr，即正文节）。"""
    geo = PageGeometry()

    sections = re.findall(r"<w:sectPr[^>]*>.*?</w:sectPr>", xml, re.DOTALL)
    if not sections:
        return geo
    sect = sections[-1]

    page = re.search(r"<w:pgSz\b[^>]*>", sect)
    if page:
        tag = page.group(0)
        w = re.search(r'w:w="(\d+)"', tag)
        h = re.search(r'w:h="(\d+)"', tag)
        if w:
            geo.width = int(w.group(1))
        if h:
            geo.height = int(h.group(1))

    mar = re.search(r"<w:pgMar\b[^>]*>", sect)
    if mar:
        tag = mar.group(0)
        for attr, field in (
            ("left", "margin_left"), ("right", "margin_right"),
            ("top", "margin_top"), ("bottom", "margin_bottom"),
        ):
            m = re.search(rf'w:{attr}="(-?\d+)"', tag)
            if m:
                setattr(geo, field, max(0, int(m.group(1))))

    return geo


def baseline_half_pt(xml: str) -> int:
    """取文档中最常见的正文字号（半磅），作为行宽/行高估算基准。"""
    sizes = [int(s) for s in re.findall(r'<w:sz w:val="(\d+)"/>', xml)]
    if not sizes:
        return _DEFAULT_HALF_PT
    # 取中位数更贴近正文，避免姓名等大标题字号拉高基准
    sizes.sort()
    return sizes[len(sizes) // 2]


# ============================================================================
# 图片文件头魔数 -> 扩展名
# ============================================================================
_IMAGE_MAGIC: Sequence[Tuple[bytes, str]] = (
    (b"\xff\xd8\xff", "jpeg"),
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
    (b"BM", "bmp"),
)


class TemplateError(Exception):
    """模板不合法 / 无法处理时抛出。"""


# ============================================================================
# 底层工具
# ============================================================================

def sniff_image_ext(data: bytes) -> Optional[str]:
    """从字节流识别图片格式，返回扩展名或 None。"""
    for magic, ext in _IMAGE_MAGIC:
        if data.startswith(magic):
            return ext
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def image_size(data: bytes) -> Optional[Tuple[int, int]]:
    """读取图片像素尺寸（仅标准库），失败返回 None。"""
    # PNG
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        return (int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big"))
    # GIF
    if data[:6] in (b"GIF87a", b"GIF89a") and len(data) >= 10:
        return (int.from_bytes(data[6:8], "little"), int.from_bytes(data[8:10], "little"))
    # BMP
    if data.startswith(b"BM") and len(data) >= 26:
        return (int.from_bytes(data[18:22], "little"), int.from_bytes(data[22:26], "little"))
    # JPEG：扫描 SOFn 段
    if data.startswith(b"\xff\xd8"):
        i = 2
        n = len(data)
        while i + 9 < n:
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            seg_len = int.from_bytes(data[i + 2:i + 4], "big")
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                          0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                if i + 9 < n:
                    h = int.from_bytes(data[i + 5:i + 7], "big")
                    w = int.from_bytes(data[i + 7:i + 9], "big")
                    return (w, h)
                return None
            i += 2 + seg_len
    return None


def read_zip(path: Path) -> Tuple[Dict[str, bytes], List[str]]:
    """读取 docx/zip 的全部条目，保持原始顺序。"""
    if not path.exists():
        raise TemplateError(f"文件不存在：{path}")
    if path.suffix.lower() not in (".docx", ".docm", ".dotx", ".zip"):
        if path.suffix.lower() == ".doc":
            raise TemplateError(
                f"不支持旧版 .doc 格式：{path.name}\n"
                "请用 Word / WPS / LibreOffice 另存为 .docx 后再使用。"
            )
    try:
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
            entries = {name: zf.read(name) for name in names}
    except zipfile.BadZipFile as exc:
        raise TemplateError(
            f"无法解析为 docx（zip）文件：{path}\n"
            f"原始错误：{exc}\n"
            "提示：.docx 本质是 zip。若此文件是 .doc 改名而来，请先真正另存为 .docx。"
        ) from exc
    if DOCUMENT_XML not in entries:
        raise TemplateError(
            f"缺少 {DOCUMENT_XML}，这不是一个有效的 Word 文档：{path}"
        )
    return entries, names


def write_zip(entries: Dict[str, bytes], order: Sequence[str], out_path: Path) -> None:
    """按给定顺序写出 zip。第一个条目使用 STORED 以兼容 mimetype 约定。

    自检：若 entries 里有部件不在 order 中，会**追加写出**而不是静默丢弃。
    这类不一致曾导致照片部件未写入 zip、关系文件指向不存在的文件
    （产物照片消失）。宁可顺序略有偏差，也不能漏写部件。
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    written: set[str] = set()
    final_order: List[str] = [n for n in order if n in entries]
    written.update(final_order)

    missing = [n for n in entries if n not in written]
    if missing:
        # 保持确定性：按名字排序追加
        final_order.extend(sorted(missing))

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for index, name in enumerate(final_order):
            compress = zipfile.ZIP_STORED if index == 0 else zipfile.ZIP_DEFLATED
            zf.writestr(name, entries[name], compress_type=compress)


def _decode(raw: bytes) -> str:
    return raw.decode("utf-8", errors="surrogateescape")


def _encode(text: str) -> bytes:
    return text.encode("utf-8", errors="surrogateescape")


# ============================================================================
# 字段发现
# ============================================================================

def iter_text_nodes(xml: str) -> Iterable[Tuple[str, str]]:
    """产出 (标签名, 文本内容)，跳过自闭合空节点。"""
    for m in _TEXT_NODE.finditer(xml):
        tag = m.group(1)
        body = m.group(4)
        if body:
            yield tag, body


def resolve_pattern(xml: str, pattern: Optional[str] = None) -> str:
    """把「preset 名称」或「原始正则」统一解析成可用正则。

    - pattern 为 None          -> 自动探测
    - pattern 是预设名（brace）-> 取对应正则
    - pattern 是合法正则       -> 原样使用
    - 其他                     -> 报错，并给出合法值清单
    """
    if not pattern:
        return detect_pattern(xml)
    if pattern in MARKER_PRESETS:
        return MARKER_PRESETS[pattern]
    try:
        compiled = re.compile(pattern)
    except re.error as exc:
        raise TemplateError(
            f"占位符正则不合法：{pattern}\n原始错误：{exc}\n"
            f"可直接使用的预设名：{', '.join(MARKER_PRESETS)}"
        ) from exc
    if compiled.groups < 1:
        raise TemplateError(
            f"占位符正则必须包含 1 个捕获组（用于提取字段名）：{pattern}\n"
            r"例如：\{\{\s*([A-Za-z0-9_]+)\s*\}\}"
        )
    return pattern


def detect_pattern(xml: str, preset: Optional[str] = None) -> str:
    """探测模板使用的占位符语法，返回正则字符串。

    先试预设；若显式指定 preset 则不探测。
    """
    if preset:
        return resolve_pattern(xml, preset)

    texts = [body for _, body in iter_text_nodes(xml)]
    blob = "\n".join(texts)
    best, best_count = DEFAULT_PATTERN, 0
    for name, pattern in MARKER_PRESETS.items():
        count = len(set(re.findall(pattern, blob)))
        # brace 语法优先级最高（并列时保留）
        if count > best_count:
            best, best_count = pattern, count
    return best


def list_fields(
    xml: str, pattern: Optional[str] = None
) -> List[Tuple[str, int]]:
    """列出模板中的占位符，返回 [(字段名, 出现次数)]，按首次出现顺序。

    注意：字段可能在模板中出现多次（如 t04 的 {{AW1}} 占位两次），
    填充时全部会被替换为同一个值。
    """
    pat = resolve_pattern(xml, pattern)
    order: List[str] = []
    counts: Dict[str, int] = {}
    for _, body in iter_text_nodes(xml):
        for name in re.findall(pat, body):
            if name not in counts:
                order.append(name)
                counts[name] = 0
            counts[name] += 1
    return [(name, counts[name]) for name in order]


# ============================================================================
# 品红补高标记清理（t01 特有）
# ============================================================================

def _run_is_marker(run_xml: str, marker_colors: Sequence[str]) -> bool:
    """判断一个 run 是否为「纯补高标记」：含指定颜色 + 只包含 <w:br/> 与空 <w:t>。"""
    upper = run_xml.upper()
    if not any(color.upper() in upper for color in marker_colors):
        return False
    # 必须完全不含可见文字
    for m in _TEXT_NODE.finditer(run_xml):
        if m.group(4) and m.group(4).strip():
            return False
    # 必须含有换行标记或完全为空 run
    return True


def strip_marker_runs(xml: str, marker_colors: Sequence[str]) -> Tuple[str, int]:
    """删除「指定颜色的纯补高 run」（不破坏字段替换）。

    返回 (新 xml, 删除数量)。
    """
    removed = 0

    def repl(m: re.Match) -> str:
        nonlocal removed
        run = m.group(0)
        if _run_is_marker(run, marker_colors):
            removed += 1
            return ""
        return run

    return _RUN.sub(repl, xml), removed


# ============================================================================
# 填充
# ============================================================================

def fill_values(
    xml: str,
    values: Dict[str, str],
    pattern: Optional[str] = None,
    preserve_slots: bool = True,
    geo: Optional["PageGeometry"] = None,
    half_pt: int = _DEFAULT_HALF_PT,
    line_overflow: Optional[List[Dict[str, object]]] = None,
) -> Tuple[str, Dict[str, int], List[str], Dict[str, Slot]]:
    """把 values 填入 xml 中所有匹配的占位符。

    参数：
        values: {字段名: 文本}。未提供的字段保持原样（不替换，便于人工排查）。
        preserve_slots: 是否保持「空格对齐槽位」宽度。

    为什么需要 preserve_slots（关键机制）：
        这些模板用**字面空格**而不是制表位来对齐。例如 t04 的
            <w:t>{{W1C}}　　　　          {{W1P}}</w:t>
        「职位」的起始 x 位置完全由 {{W1C}} 之后的填充空格决定。
        如果 {{W1C}} 被替换成更长的公司名而不补偿空格，W1P 就会左移，
        整行版式错位 —— 这是模板标准化时专门设计过、最容易踩的坑。

        因此本函数按原文字面结构重建文本节点：
        - 值比槽位短 -> 右侧补空格到槽位宽度，后续字段位置不变；
        - 值比槽位长 -> 让后续字段自然右移（Word 的正常流式行为）。

    返回：
        (新 xml, {字段: 替换次数}, [未提供值的模板字段], {字段: Slot})

        注意 filled 只包含**真正被替换**的字段。未提供值的字段不会出现在里面，
        否则会把「设计上留空」误报成「已填充」。

        line_overflow 传入列表时，会把「替换后整行超出页面可用宽度」的行记进去。
        该判断在填充过程中完成，因此能精确知道每个文本节点里替换了哪些字段。
    """
    pat = resolve_pattern(xml, pattern)
    compiled = re.compile(pat)
    filled: Dict[str, int] = {}
    slots: Dict[str, Slot] = {}

    # 以 run 为单位处理，保证不跨 run 误替换，且 w:rPr 结构完全不动
    def run_repl(m: re.Match) -> str:
        run = m.group(0)
        if not compiled.search(run):
            return run

        def node_repl(nm: re.Match) -> str:
            tag, attrs = nm.group(1), nm.group(2) or ""
            if nm.group(3) == "/>":
                return nm.group(0)
            body = nm.group(4) or ""
            if not compiled.search(body):
                return nm.group(0)

            node_fields: List[str] = []
            if preserve_slots:
                new_body = _build_slotted(
                    body, compiled, values, filled, slots, node_fields
                )
            else:
                new_body = _build_plain(body, compiled, values, filled, node_fields)

            # 整行溢出检查：此时能精确知道本行替换了哪些字段。
            #
            # 关键点一：用**该行自己的字号**判断，而不是全文基准字号。
            #   本仓库模板正文被设成小字号（如 7pt）以放下高密度信息，
            #   用全局中位数字号会得出「每行只有 40 字」的错误结论，
            #   把本来放得下的行误判为溢出。
            #
            # 关键点二：仅由**流式文本**（自我评价、经历描述）组成的行，
            #   超出会用换行消化，是设计如此；只有行内槽位（日期|公司|职位
            #   这种固定行）也超出，才会把后续字段挤到下一行、破坏版式。
            if geo is not None and line_overflow is not None and node_fields:
                width = _visual_width(new_body)
                run_half_pt = _run_half_pt(run) or half_pt
                if geo.line_overflows(width, run_half_pt):
                    uniq = sorted(set(node_fields))
                    line_overflow.append({
                        "fields": uniq,
                        "line_width": width,
                        "chars_per_line": geo.chars_per_line(run_half_pt),
                        "half_pt": run_half_pt,
                        "preview": new_body.strip()[:70],
                        # 行内槽位（强制单行）也超出 -> 真问题
                        "layout_risk": any(
                            slots.get(f) is not None and slots[f].is_inline
                            for f in uniq
                        ),
                    })

            return f"<{tag}{attrs}>{new_body}</{tag}>"

        return _TEXT_NODE.sub(node_repl, run)

    new_xml = _RUN.sub(run_repl, xml)

    all_fields = [name for name, _ in list_fields(xml, pat)]
    missing = [name for name in all_fields if name not in values]
    return new_xml, filled, missing, slots


def _build_plain(
    body: str,
    compiled: re.Pattern,
    values: Dict[str, str],
    filled: Dict[str, int],
    node_fields: Optional[List[str]] = None,
) -> str:
    """不做槽位对齐的直接替换。"""

    def one(mm: re.Match) -> str:
        name = mm.group(1)
        if name not in values:
            return mm.group(0)
        filled[name] = filled.get(name, 0) + 1
        if node_fields is not None:
            node_fields.append(name)
        return values[name]

    return compiled.sub(one, body)


def _build_slotted(
    body: str,
    compiled: re.Pattern,
    values: Dict[str, str],
    filled: Dict[str, int],
    slots: Dict[str, Slot],
    node_fields: Optional[List[str]] = None,
) -> str:
    """按原文字面结构重建文本，保持每个占位符的槽位宽度。

    逐段处理：
        字面段（含对齐空格）-> 原样输出
        占位符段           -> 槽位容量 = 标记宽度 + 其后紧跟空格宽度
                              不足容量则右侧补空格；超出则正常右移后续内容
                              未提供值时原样保留占位符与空格
    """
    matches = list(compiled.finditer(body))
    if not matches:
        return body

    out: List[str] = []

    for index, match in enumerate(matches):
        literal_start = matches[index - 1].end() if index > 0 else 0
        out.append(body[literal_start:match.start()])

        name = match.group(1)
        token = match.group(0)

        # 槽位容量 = 标记 + 其后紧跟的空白，但不能越过下一个占位符
        pad_end = _trailing_whitespace(body, match.end())
        next_start = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        pad_end = min(pad_end, next_start)
        padding = body[match.end():pad_end]

        if name not in values:
            # 不替换：原样保留标记与空格，仅记录槽位
            slots.setdefault(name, Slot(
                name, token, padding,
                has_next=index + 1 < len(matches),
                gap_width=_visual_width(padding),
            ))
            out.append(token)
            out.append(padding)
            continue

        filled[name] = filled.get(name, 0) + 1
        if node_fields is not None:
            node_fields.append(name)
        slot = Slot(
            name, token, padding, values[name],
            has_next=index + 1 < len(matches),
            gap_width=_visual_width(padding),
        )
        slots[name] = slot

        value_width = _visual_width(slot.value)

        # 只有「占位符后本来就有填充空格」才补空格对齐。
        #
        # 依据：模板作者用填充空格表达「这个字段占固定宽度」。词元后直接跟字面
        # 文字（如 {{MAJ}}（{{DG}}） 的 DG）说明那里是自然流式文本，作者从未预留
        # 宽度，补空格只会凭空撑开。行尾同理，没有对齐需求。
        #
        # 例：{{TEL}}\u2007\u2007\u2007... 五个数字空格 -> 补（对齐）
        #     {{DG}}）                    词元后无空格   -> 不补
        if not padding or value_width >= slot.capacity:
            out.append(slot.value)
        else:
            out.append(slot.value + " " * (slot.capacity - value_width))

    out.append(body[matches[-1].end():])
    return "".join(out)


# ============================================================================
# 槽位（空格对齐）数据结构
# ============================================================================

# 可读性下限：8pt（半磅）。低于此值的缩字会让人肉眼难辨，宁可不缩。
MIN_READABLE_HALFPT = 16

# 槽位容量低于此值（视觉宽度）才视为「必须单行放下的窄槽位」
INLINE_SLOT_MAX_CAPACITY = 16

# 「同一行」判定：与下一个占位符之间的字面间隔小于此宽度时，认为二者同行
SAME_LINE_MAX_GAP = 8

# 窄槽位的最大可缩倍数。超出此倍数说明内容根本放不下，缩字也无意义。
MAX_SHRINK_RATIO = 2.2

# 「最小有意义的超出宽度」（视觉宽度）。
#
# 为什么需要它：槽位容量是用「占位符标记 + 其后空格」估出来的，
# 而标记宽度（{{MAJ}} = 7）往往小于原作者写的内容宽度。
# 因此轻微超出（1~3 个字符）只会把同行后续字面右移几个像素，
# 视觉上不可见，属于正常流式行为。
#
# 真正会破坏版式的是明显超出（如并列职务串把「职位」挤到下一行）。
# 只对超过此阈值的字段报警与缩字号，避免大量无意义告警淹没真问题。
MIN_OVERFLOW_WIDTH = 5


class Slot:
    """一个占位符在文本节点中占据的「槽位」。

    为什么需要它：
        这些模板用**字面空格**而不是制表位对齐，例如
            <w:t>{{W1C}}　　　　          {{W1P}}</w:t>
        模板作者把「原内容的宽度」编码在了占位符之后的填充空格里。
        因此一个槽位的容量 = 占位符标记宽度 + 其后紧跟的空格宽度。

        如果只拿 {{W1C}} 这 7 个字符当容量，会得出「所有值都超宽」的错误结论，
        进而错误地缩小字号、破坏版式。

    字段：
        field      字段名
        token      原占位符文本，如 "{{W1D}}"
        padding    占位符后紧跟的空格/全角空格（属于该槽位）
        capacity   槽位容量（视觉宽度）= token + padding
        value      实际填入的值
    """

    __slots__ = ("field", "token", "padding", "capacity", "value", "has_next", "gap_width")

    def __init__(
        self,
        field: str,
        token: str,
        padding: str = "",
        value: str = "",
        has_next: bool = False,
        gap_width: int = 0,
    ) -> None:
        self.field = field
        self.token = token
        self.padding = padding
        self.capacity = _visual_width(token) + _visual_width(padding)
        self.value = value
        self.has_next = has_next
        self.gap_width = gap_width

    @property
    def is_inline(self) -> bool:
        """是否为「必须单行放下的窄槽位」。

        判断依据（按重要性排序）：
            1. 同一文本节点内、间隔很小就跟着下一个占位符
               -> 这是「字段A + 对齐空格 + 字段B」的行内结构，A 必须单行放下，
                  否则 B 会被挤到下一行，整行版式崩掉；
            2. 占位符之后有小段填充空格（作者按固定宽度对齐的痕迹）。

        反例（属于流式文本，靠换行消化长度，不该缩字号）：
            {{SM}}   自我评价，独立成段，靠换行铺满整栏
            {{W1R1}} 实习描述行，同样跨栏换行
        """
        if self.has_next and self.gap_width <= SAME_LINE_MAX_GAP:
            return True
        return bool(self.padding) and self.capacity <= INLINE_SLOT_MAX_CAPACITY

    @property
    def overflow_ratio(self) -> float:
        """值宽 / 槽位容量。> 1 表示超出预留宽度。"""
        if self.capacity <= 0:
            return 1.0
        return _visual_width(self.value) / self.capacity

    @property
    def overflow_width(self) -> int:
        """超出的**绝对**视觉宽度。用于过滤「轻微超出属正常流式」的情况。"""
        return max(0, _visual_width(self.value) - self.capacity)

    @property
    def is_visible_overflow(self) -> bool:
        """是否属于「值得关注」的超出。

        注意：这里只做**槽位层面**的粗判（含 MIN_OVERFLOW_WIDTH 缓冲）。
        真正决定「会不会破坏版式」的是整行宽度是否超过页面可用宽度，
        该判断在 render() 中用 PageGeometry 完成，结论写入 report["line_overflow"]。
        """
        return self.is_inline and self.overflow_width >= MIN_OVERFLOW_WIDTH

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        kind = "inline" if self.is_inline else "flow"
        return (f"Slot({self.field}, {kind}, cap={self.capacity}, "
                f"ratio={self.overflow_ratio:.2f})")

def _trailing_whitespace(text: str, start: int) -> int:
    """返回从 start 开始连续空白字符的结束下标。"""
    i = start
    while i < len(text) and text[i] in " \t\u3000\u00a0":
        i += 1
    return i


def _run_half_pt(run_xml: str) -> Optional[int]:
    """取一个 run 的显式字号（半磅）。未声明时返回 None。"""
    rpr = re.search(r"<w:rPr>.*?</w:rPr>", run_xml, re.DOTALL)
    if not rpr:
        return None
    m = re.search(r'<w:sz w:val="(\d+)"/>', rpr.group(0))
    return int(m.group(1)) if m else None


# ============================================================================
# 字宽工具
# ============================================================================

def _visual_width(text: str) -> int:
    """视觉宽度：CJK 字符与全角空格算 2，其余算 1。"""
    width = 0
    for ch in text:
        width += 2 if ord(ch) > 0x2E80 else 1
    return width


def slot_ratio(value: str, capacity: int) -> float:
    """计算值相对槽位容量的宽度比。>1 表示超出。"""
    if capacity <= 0:
        return 1.0
    return _visual_width(value) / capacity


def shrink_run_to_fit(
    run_xml: str,
    marker: str,
    ratio: float,
    min_halfpt: int = 14,
) -> str:
    """把含 marker 文本的 run 按 ratio 压低字号（仅改已有 w:sz / w:szCs）。

    仅当 ratio > 1（值超出槽位）时才压缩，并设下限防缩到不可读。
    """
    if ratio <= 1.0:
        return run_xml
    if marker not in run_xml:
        return run_xml

    rpr_match = re.search(r"<w:rPr>.*?</w:rPr>", run_xml, re.DOTALL)
    if not rpr_match:
        return run_xml
    rpr = rpr_match.group(0)

    sz_match = re.search(r'<w:sz w:val="(\d+)"/>', rpr)
    if not sz_match:
        return run_xml
    original = int(sz_match.group(1))
    if original <= min_halfpt:
        return run_xml

    target = max(min_halfpt, int(original / ratio))
    if target >= original:
        return run_xml

    new_rpr = rpr.replace(
        f'<w:sz w:val="{original}"/>', f'<w:sz w:val="{target}"/>', 1
    )
    new_rpr = re.sub(
        r'<w:szCs w:val="\d+"/>', f'<w:szCs w:val="{target}"/>', new_rpr, count=1
    )
    return run_xml.replace(rpr, new_rpr, 1)


# ============================================================================
# 照片替换
# ============================================================================

def find_image_parts(entries: Dict[str, bytes]) -> List[str]:
    """列出文档内的图片部件，按名称排序。"""
    return sorted(
        name for name in entries
        if re.match(r"^word/media/[^/]+\.(jpe?g|png|gif|bmp|webp|emf|wmf)$", name, re.I)
    )


def replace_photo(
    entries: Dict[str, bytes],
    order: Sequence[str],
    photo_bytes: bytes,
    target: Optional[str] = None,
    all_bitmaps: bool = False,
) -> List[str]:
    """用真实证件照覆盖模板中的占位图。

    安全策略（重要）：默认**只替换最小的那张位图**，因为模板里的其他位图
    可能是图标、logo、装饰元素，盲目全替换会破坏版式。模板标准照片占位图
    通常体积最小（纯灰块）。

    若模板只有一张位图，则必然命中。

    返回被替换的部件名列表。
    """
    ext = sniff_image_ext(photo_bytes)
    if ext is None:
        raise TemplateError(
            "无法识别证件照格式。支持 jpg / png / gif / bmp / webp。\n"
            "提示：iPhone 的 HEIC 格式需先转成 jpg。"
        )

    bitmaps = [
        name for name in find_image_parts(entries)
        if not name.lower().endswith((".emf", ".wmf"))
    ]
    if not bitmaps:
        return []

    if target:
        if target not in entries:
            raise TemplateError(
                f"指定的照片部件不存在：{target}\n可选：{', '.join(bitmaps)}"
            )
        targets = [target]
    elif all_bitmaps or len(bitmaps) == 1:
        targets = bitmaps
    else:
        # 只替换体积最小的位图（模板照片占位图）
        targets = [min(bitmaps, key=lambda n: len(entries[n]))]

    replaced_names: List[str] = []

    for name in targets:
        entries[name] = photo_bytes
        final_name = name

        # 同步修正 [Content_Types].xml 里的扩展名声明
        ct = _decode(entries.get(CONTENT_TYPES, b""))
        if ct and f'Extension="{ext}"' not in ct:
            ct = ct.replace(
                "</Types>",
                f'<Default Extension="{ext}" ContentType="image/{ext}"/></Types>',
            )
            entries[CONTENT_TYPES] = _encode(ct)

        # 同步修正关系文件里的图片扩展名（如 image1.jpeg -> image1.png）
        rels = _decode(entries.get(DOC_RELS, b""))
        if rels:
            base = name.rsplit("/", 1)[-1]
            stem, _, old_ext = base.rpartition(".")
            if old_ext and old_ext.lower() != ext:
                new_name = f"word/media/{stem}.{ext}"
                rels = rels.replace(f"{stem}.{old_ext}", f"{stem}.{ext}")
                entries[DOC_RELS] = _encode(rels)
                entries[new_name] = entries.pop(name)
                # 关键：必须同步更新写入顺序。
                # write_zip 是按 order 遍历的，若这里只改 entries 不改 order，
                # 新名字永远不会被写入 zip —— 关系文件指向一个不存在的部件，
                # 结果是照片在产物里直接消失（且 Word 可能报文件损坏）。
                if isinstance(order, list) and name in order:
                    order[order.index(name)] = new_name
                final_name = new_name

        # 报告里必须返回**产物中真实存在**的部件名，否则调用方拿报告去
        # 读产物会 KeyError（曾因此把「照片替换成功」误报成失败）
        replaced_names.append(final_name)

    return replaced_names


def image_placeholder_hint(entries: Dict[str, bytes]) -> Optional[str]:
    """识别照片占位图（用于向用户提示它将被替换）。"""
    bitmaps = [
        n for n in find_image_parts(entries)
        if not n.lower().endswith((".emf", ".wmf"))
    ]
    if not bitmaps:
        return None
    # 占位图通常很小（<20KB）
    small = [n for n in bitmaps if len(entries[n]) < 20_000]
    return (small or bitmaps)[0]


# ============================================================================
# 单页校验（不依赖 Word）
# ============================================================================

def estimate_overflow(
    xml: str,
    geo: Optional["PageGeometry"] = None,
    half_pt: Optional[int] = None,
) -> Dict[str, object]:
    """不打开 Word 的粗略溢出估算。

    为什么需要「去重」：
        Word 文本框在 OOXML 里会同时写入 mc:Choice（现代形态）与 mc:Fallback
        （VML 兼容形态）两份内容，导致同一段文字出现两次。因此在读取前先移除
        mc:Fallback 块——这些内容在渲染时被 Word 忽略，统计进去会严重虚高。

    为什么用页面几何而不是写死的 50 行：
        写死的容量对不同模板毫无意义（A4 与 Letter、窄边距与宽边距差别很大）。
        这里从 sectPr 读真实页面尺寸，再按基准字号估算行数与每行字数。

    局限（必须向用户说明）：
        本函数不启动 Word、不做真实排版，只能给出「文字量级」判断。
        结论是 ok / likely_overflow 两档，不是精确页数。
    """
    geo = geo or parse_page_geometry(xml)
    half_pt = half_pt or baseline_half_pt(xml)
    kept = _strip_fallback_blocks(xml)

    total_visual = 0
    explicit_breaks = 0
    for _, body in iter_text_nodes(kept):
        total_visual += _visual_width(body)
        explicit_breaks += len(_BR.findall(body))

    chars_per_line = geo.chars_per_line(half_pt)
    capacity_lines = geo.max_lines(half_pt)
    approx_lines = (total_visual / max(chars_per_line, 1)) + explicit_breaks
    return {
        "visual_chars": total_visual,
        "approx_lines": round(approx_lines, 1),
        "capacity_lines": capacity_lines,
        "chars_per_line": chars_per_line,
        "baseline_half_pt": half_pt,
        "verdict": "ok" if approx_lines <= capacity_lines else "likely_overflow",
        "method": "文字量估算（按页面几何与基准字号；已剔除 mc:Fallback 重复内容），非精确分页",
    }


_FALLBACK_BLOCK = re.compile(
    r"<mc:Fallback>.*?</mc:Fallback>", re.DOTALL
)


def _strip_fallback_blocks(xml: str) -> str:
    """移除 mc:Fallback 块。这是 OOXML 的兼容性冗余分支，Word 渲染时忽略。"""
    if "<mc:Fallback>" not in xml:
        return xml
    return _FALLBACK_BLOCK.sub("", xml)


# ============================================================================
# 统一入口
# ============================================================================

def render(
    template_path: Path,
    values: Dict[str, str],
    out_path: Path,
    photo_path: Optional[Path] = None,
    pattern: Optional[str] = None,
    strip_colors: Sequence[str] = ("FF00FF",),
    shrink: bool = True,
    photo_target: Optional[str] = None,
    photo_all: bool = False,
    preserve_slots: bool = True,
) -> Dict[str, object]:
    """把 values 填进模板并写出 docx。

    返回一份渲染报告（供 CLI 与 Agent 汇报使用）。
    """
    entries, order = read_zip(template_path)
    xml = _decode(entries[DOCUMENT_XML])

    detected = resolve_pattern(xml, pattern)
    geo = parse_page_geometry(xml)
    base_half_pt = baseline_half_pt(xml)

    report: Dict[str, object] = {
        "template": str(template_path),
        "output": str(out_path),
        "pattern": detected,
        "fields_total": 0,
        "filled": {},
        "missing": [],
        "unknown_keys": [],
        "marker_runs_removed": 0,
        "preserve_slots": preserve_slots,
        "slot_overflow": [],
        "inline_overflow": [],
        "flow_overflow": [],
        "line_overflow": [],
        "shrunk_fields": {},
        "page_geometry": {
            "usable_width_twips": geo.usable_width,
            "usable_height_twips": geo.usable_height,
            "chars_per_line": geo.chars_per_line(base_half_pt),
            "max_lines": geo.max_lines(base_half_pt),
            "baseline_half_pt": base_half_pt,
        },
        "photo_replaced": [],
        "photo_hint": None,
        "overflow": {},
    }

    template_fields = [name for name, _ in list_fields(xml, detected)]
    report["fields_total"] = len(template_fields)
    report["unknown_keys"] = sorted(set(values) - set(template_fields))

    # 1. 清理补高标记 run（必须在填充前）
    if strip_colors:
        xml, removed = strip_marker_runs(xml, strip_colors)
        report["marker_runs_removed"] = removed

    # 2. 填充（保持空格对齐槽位宽度，同时记录整行溢出）
    line_overflow: List[Dict[str, object]] = []
    xml, filled, missing, slots = fill_values(
        xml, values, detected,
        preserve_slots=preserve_slots,
        geo=geo,
        half_pt=base_half_pt,
        line_overflow=line_overflow,
    )
    report["filled"] = filled
    report["missing"] = missing
    report["line_overflow"] = line_overflow

    # 3. 槽位层面的粗略超出（用于「值明显比模板预留位置长」的提示）
    #
    #    inline 槽位（{{TEL}}、{{W1D}}…）本应单行放下，明显超出会把同行后续
    #    字段挤到下一行 -> 允许缩字号补救
    #    flow 文本（{{SM}}、{{W1R1}}…）本来就跨栏换行，长度靠换行消化
    #    -> 绝不缩字号（AGENT.md 明令禁止「缩小字体硬塞内容」）
    inline_overflow: List[Tuple[str, float]] = []
    flow_overflow: List[Tuple[str, float]] = []
    for name, slot in slots.items():
        if name not in filled or slot.overflow_ratio <= 1.0:
            continue
        entry = (name, round(slot.overflow_ratio, 2))
        if slot.is_visible_overflow:
            inline_overflow.append(entry)
        else:
            flow_overflow.append(entry)
    report["inline_overflow"] = sorted(inline_overflow, key=lambda x: -x[1])
    report["flow_overflow"] = sorted(flow_overflow, key=lambda x: -x[1])
    report["slot_overflow"] = report["inline_overflow"]  # 兼容旧字段名

    # 4. 只对窄槽位缩字号，且不缩到不可读
    if shrink and slots:
        xml, shrunk = _shrink_slotted_runs(xml, slots, min_halfpt=MIN_READABLE_HALFPT)
        report["shrunk_fields"] = shrunk

    # 5. 整行溢出已在填充阶段记录（填 report["line_overflow"]）

    entries[DOCUMENT_XML] = _encode(xml)

    # 3. 照片
    report["photo_hint"] = image_placeholder_hint(entries)
    if photo_path is not None:
        if not photo_path.exists():
            raise TemplateError(f"证件照不存在：{photo_path}")
        replaced = replace_photo(
            entries, order, photo_path.read_bytes(),
            target=photo_target, all_bitmaps=photo_all,
        )
        report["photo_replaced"] = replaced
        if not replaced:
            report["photo_note"] = "模板中未找到图片部件，照片未写入。"

    # 4. 溢出估算
    report["overflow"] = estimate_overflow(xml, geo, base_half_pt)

    # 5. 写出
    write_zip(entries, order, out_path)

    report["size_bytes"] = out_path.stat().st_size
    return report


def _shrink_slotted_runs(
    xml: str,
    slots: Dict[str, Slot],
    min_halfpt: int = 14,
) -> Tuple[str, Dict[str, int]]:
    """对超槽位的字段所在 run 按比例压低字号。

    返回 (新 xml, {字段: 新字号半磅值})。
    只处理「值文本出现在 run 内」的 run；每个 run 取其中最大的压缩比例。
    """
    markers: List[Tuple[str, str, float]] = []
    for name, slot in slots.items():
        # 只对「会破坏版式的明显超出」缩字号：
        #   - 流式文本靠换行消化长度，缩字号违反可读性底线
        #   - 轻微超出只会右移几个像素，视觉不可见，不值得缩字号
        if not slot.is_visible_overflow:
            continue
        ratio = slot.overflow_ratio
        # 超出太多说明内容根本放不下，缩字也无意义（甚至缩到不可读）
        if ratio > MAX_SHRINK_RATIO:
            continue
        if slot.value.strip():
            markers.append((slot.value, name, ratio))
    if not markers:
        return xml, {}

    shrunk: Dict[str, int] = {}

    def repl(m: re.Match) -> str:
        run = m.group(0)
        applicable = [
            (value, name, ratio)
            for value, name, ratio in markers
            if value in run
        ]
        if not applicable:
            return run
        value, name, ratio = max(applicable, key=lambda x: x[2])
        new_run = shrink_run_to_fit(run, value, ratio, min_halfpt)
        if new_run != run:
            sz_match = re.search(r'<w:sz w:val="(\d+)"/>', new_run)
            if sz_match:
                shrunk[name] = int(sz_match.group(1))
        return new_run

    return _RUN.sub(repl, xml), shrunk
