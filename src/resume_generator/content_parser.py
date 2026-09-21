# -*- coding: utf-8 -*-
"""content_parser.py — resume.md（内容层）→ ResumeBlocks 的正式解析器。

为什么需要它
------------
历史上每份简历都在一次性脚本里自带一份 ``_parse_resume_md``，于是：

* 逻辑各不相同、跨份不可复现；
* 只认最规范的一种写法，遇到变体（标题层级 / 日期分隔 / 合并板块）
  **静默丢内容**——解析器没有 ``else`` 分支，只有「姓名解析不到」才报错。

本模块把解析提升为产品能力。核心契约只有一条：

    **识别不到的内容一律进 diagnostics，绝不静默丢弃。**

契约细则
--------
* 致命（ERROR，``strict=True`` 时抛 ``ResumeParseError``）：
  文件不可读 / 缺姓名 / 内容层为空。
* 警告（WARNING）：未识别的 ``##`` 章节、条目标题不符合任一格式、
  章节内无规则可消费的正文行、条目缺时间、个人信息区缺「个人信息」节。
* 提示（INFO）：已识别但当前布局无槽位的字段（如「民族」「政治面貌」）、
  刻意不渲染的章节（「待补充」）、条目内引用行。

**验收基准**：一份按 ``prompts/resume_writer.md`` 规范写出的 resume.md，
解析后 ``diagnostics`` 必须为空（0 ERROR / 0 WARNING / 0 INFO）。

依赖
----
纯标准库 + ``layout_kit``（后者模块级不依赖 python-docx），
因此本模块可在未装 python-docx 的环境里被 CLI 直接调用。

用法
----
    from resume_generator.content_parser import parse_resume_md
    parsed = parse_resume_md(Path(".../resume.md"), photo_root=resume_lib)
    parsed.blocks             # 官方 ResumeBlocks，直接喂 build_document
    print(parsed.diagnostics.render())

本文件不含任何个人事实；除读取传入路径外无任何副作用。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .layout_kit import BulletBlock, ResumeBlocks

__all__ = [
    "parse_resume_md",
    "parse_resume_md_text",
    "parse_blocks",
    "ParsedResume",
    "Diagnostics",
    "Diagnostic",
    "ResumeParseError",
    "SEV_ERROR",
    "SEV_WARNING",
    "SEV_INFO",
    "CANONICAL_SECTIONS",
    "SECTION_ALIASES",
]

# ---------------------------------------------------------------------------
# 诊断
# ---------------------------------------------------------------------------

SEV_ERROR = "ERROR"
SEV_WARNING = "WARNING"
SEV_INFO = "INFO"

_SEV_ORDER = {SEV_ERROR: 0, SEV_WARNING: 1, SEV_INFO: 2}
_SEV_TAG = {SEV_ERROR: "✗", SEV_WARNING: "!", SEV_INFO: "i"}


class ResumeParseError(ValueError):
    """内容层存在致命缺陷（不可读 / 缺姓名 / 空内容）时抛出。

    触发条件是 ``Diagnostics.has_errors`` 为真且调用方使用 ``strict=True``。
    异常消息恒为 ``Diagnostics.render()`` 的文本，便于 CLI 直接打印。
    """


@dataclass
class Diagnostic:
    """一条解析诊断。``raw`` 保留原始行文本，便于定位与人工核对。"""

    severity: str
    code: str
    message: str
    line_no: Optional[int] = None
    raw: str = ""

    def render(self) -> str:
        where = f" (line {self.line_no})" if self.line_no else ""
        head = f"[{self.severity}] {self.code}{where}: {self.message}"
        if self.raw:
            return f"{head}\n      raw: {self.raw}"
        return head


@dataclass
class Diagnostics:
    """解析过程中产生的全部诊断，按严重度分组可查。"""

    items: List[Diagnostic] = field(default_factory=list)

    def add(self, severity: str, code: str, message: str,
            line_no: Optional[int] = None, raw: str = "") -> Diagnostic:
        diag = Diagnostic(severity, code, message, line_no, raw)
        self.items.append(diag)
        return diag

    def error(self, code: str, message: str, **kw) -> Diagnostic:
        return self.add(SEV_ERROR, code, message, **kw)

    def warn(self, code: str, message: str, **kw) -> Diagnostic:
        return self.add(SEV_WARNING, code, message, **kw)

    def info(self, code: str, message: str, **kw) -> Diagnostic:
        return self.add(SEV_INFO, code, message, **kw)

    # -- 查询 ---------------------------------------------------------------

    @property
    def errors(self) -> List[Diagnostic]:
        return [d for d in self.items if d.severity == SEV_ERROR]

    @property
    def warnings(self) -> List[Diagnostic]:
        return [d for d in self.items if d.severity == SEV_WARNING]

    @property
    def infos(self) -> List[Diagnostic]:
        return [d for d in self.items if d.severity == SEV_INFO]

    @property
    def has_errors(self) -> bool:
        return any(d.severity == SEV_ERROR for d in self.items)

    @property
    def is_clean(self) -> bool:
        return not self.items

    def codes(self, severity: Optional[str] = None) -> List[str]:
        return [d.code for d in self.items
                if severity is None or d.severity == severity]

    def counts(self) -> Dict[str, int]:
        return {
            SEV_ERROR: len(self.errors),
            SEV_WARNING: len(self.warnings),
            SEV_INFO: len(self.infos),
        }

    def render(self, *, max_per_group: int = 20) -> str:
        """诊断报告；同 code 归为一组，避免重复噪声淹没关键项。"""
        if not self.items:
            return "内容层诊断：无（0 ERROR / 0 WARNING / 0 INFO）"

        counts = self.counts()
        lines = [f"内容层诊断：ERROR {counts[SEV_ERROR]} / "
                 f"WARNING {counts[SEV_WARNING]} / INFO {counts[SEV_INFO]}"]

        ordered = sorted(self.items, key=lambda d: _SEV_ORDER.get(d.severity, 9))
        grouped: Dict[str, List[Diagnostic]] = {}
        for d in ordered:
            grouped.setdefault(d.code, []).append(d)

        for code, group in grouped.items():
            sev = group[0].severity
            tag = _SEV_TAG.get(sev, "?")
            lines.append(f"  {tag} {code} × {len(group)}  [{sev}]")
            for d in group[:max_per_group]:
                where = f"line {d.line_no}: " if d.line_no else ""
                lines.append(f"      · {where}{d.message}")
                if d.raw:
                    lines.append(f"        raw: {d.raw}")
            if len(group) > max_per_group:
                lines.append(f"      · …（还有 {len(group) - max_per_group} 条同类）")
        return "\n".join(lines)


@dataclass
class ParsedResume:
    """解析结果：内容块 + 诊断 + 来源路径。"""

    blocks: ResumeBlocks
    diagnostics: Diagnostics
    source: Optional[Path] = None

    @property
    def fatal(self) -> bool:
        return self.diagnostics.has_errors

    def raise_if_fatal(self) -> "ParsedResume":
        if self.fatal:
            raise ResumeParseError(self.diagnostics.render())
        return self

    def summary_line(self) -> str:
        b = self.blocks
        return (f"姓名={b.name or '(缺)'} | 意向={b.intent or '(缺)'} | "
                f"实习 {len(b.internships)} / 项目 {len(b.projects)} / "
                f"校园 {len(b.campus)} / 技能 {len(b.skills)} / "
                f"证书 {len(b.certs)} | 联系行 {len(b.contact_lines)} | "
                f"照片={'有' if b.photo_path else '无'}")


# ---------------------------------------------------------------------------
# 章节注册表
# ---------------------------------------------------------------------------

SEC_PERSONAL = "personal"
SEC_SUMMARY = "summary"
SEC_EDUCATION = "education"
SEC_EXPERIENCE = "experience"
SEC_PROJECTS = "projects"
SEC_CAMPUS = "campus"
SEC_SKILLS = "skills"
SEC_CERTS = "certs"
SEC_SKILLS_CERTS = "skills_certs"   # 合并节「专业技能 / 证书奖项」
SEC_PENDING = "pending"             # 「待补充」：刻意不渲染，只登记

CANONICAL_SECTIONS = (
    SEC_PERSONAL, SEC_SUMMARY, SEC_EDUCATION, SEC_EXPERIENCE,
    SEC_PROJECTS, SEC_CAMPUS, SEC_SKILLS, SEC_CERTS,
    SEC_SKILLS_CERTS, SEC_PENDING,
)

# 章节标题别名 → 规范名。匹配的是「归一化后的标题」（去空格 / 全半角统一）。
SECTION_ALIASES: Dict[str, str] = {}
for _alias, _canon in {
    # 个人信息
    "个人信息": SEC_PERSONAL,
    "基本资料": SEC_PERSONAL,
    "基础信息": SEC_PERSONAL,
    "基本信息": SEC_PERSONAL,
    # 个人优势 / 简介 / 自我评价
    "个人优势": SEC_SUMMARY,
    "个人简介": SEC_SUMMARY,
    "自我评价": SEC_SUMMARY,
    "自我介绍": SEC_SUMMARY,
    "个人总结": SEC_SUMMARY,
    "优势概述": SEC_SUMMARY,
    # 教育
    "教育经历": SEC_EDUCATION,
    "教育背景": SEC_EDUCATION,
    "学历背景": SEC_EDUCATION,
    # 实习 / 工作
    "实习经历": SEC_EXPERIENCE,
    "工作经历": SEC_EXPERIENCE,
    "实习工作经历": SEC_EXPERIENCE,
    "实习与工作经历": SEC_EXPERIENCE,
    "职业经历": SEC_EXPERIENCE,
    # 项目
    "项目经历": SEC_PROJECTS,
    "项目经验": SEC_PROJECTS,
    # 校园
    "校园经历": SEC_CAMPUS,
    "校园活动": SEC_CAMPUS,
    "在校经历": SEC_CAMPUS,
    "校内经历": SEC_CAMPUS,
    # 技能
    "专业技能": SEC_SKILLS,
    "技能特长": SEC_SKILLS,
    "技能": SEC_SKILLS,
    # 证书 / 荣誉
    "证书奖项": SEC_CERTS,
    "荣誉奖项": SEC_CERTS,
    "获奖情况": SEC_CERTS,
    "证书": SEC_CERTS,
    "荣誉证书": SEC_CERTS,
    "奖项荣誉": SEC_CERTS,
    # 刻意不渲染
    "待补充": SEC_PENDING,
    "待办": SEC_PENDING,
}.items():
    SECTION_ALIASES[_alias] = _canon

# 归一化：全角→半角、去空白、去斜杠（合并节靠「技能 + 证书」关键词判定）
_FULLWIDTH_MAP = str.maketrans({
    "（": "(", "）": ")", "｜": "|", "／": "/", "，": ",", "：": ":",
    "　": "", " ": "", "\t": "",
})
# 半角分隔符（用于「专业技能 / 证书奖项」这类合并标题）
_SLASH_RE = re.compile(r"[/、,]+")
# 条目标题归一化：只统一全角竖线，保留空格（空格是内容的一部分）
_ENTRY_TITLE_MAP = str.maketrans({"｜": "|"})

# ---------------------------------------------------------------------------
# 行级正则
# ---------------------------------------------------------------------------

# 表格分隔行：| --- | --- |
_TABLE_SEP_RE = re.compile(r"^\|[\s:|-]+\|$")
# 水平分割线：--- / *** / ___
_HR_RE = re.compile(r"^(?:-{3,}|\*{3,}|_{3,})$")
# 个人信息表的表头行
_PERSONAL_HEADER_CELLS = {"项", "字段", "项目", "属性"}
# 条目时间（用于「日期格式可校验」）
_DATE_TOKEN = r"\d{4}\s*[.\-/]\s*\d{1,2}"
_META_RE = re.compile(
    rf"^\s*{_DATE_TOKEN}\s*[-–—~～至到]\s*(?:{_DATE_TOKEN}|至今|今|现在|now|present)\s*$"
)
# 条目标题：A - B（C） / A - B (C)
_ENTRY_DASH_RE = re.compile(
    r"^(?P<title>.+?)\s*[-–—]\s*(?P<role>.+?)\s*[（(](?P<meta>[^）)]+)[）)]\s*$"
)
# 条目标题：A | B | C
_ENTRY_PIPE3_RE = re.compile(
    r"^(?P<title>[^|]+?)\s*\|\s*(?P<role>[^|]+?)\s*\|\s*(?P<meta>[^|]+?)\s*$"
)
# 条目标题：A | B
_ENTRY_PIPE2_RE = re.compile(
    r"^(?P<title>[^|]+?)\s*\|\s*(?P<role>[^|]+?)\s*$"
)
# 「键：值」行（个人信息区 / 文档开头用）；容忍 `**加粗键**：值` 写法
_KV_RE = re.compile(
    r"^\s*\*{0,2}\s*(?P<key>.+?)\s*\*{0,2}\s*[:：]\s*(?P<val>.+?)\s*\*{0,2}\s*$"
)
# 一段里可能没有冒号，用于快速排除
_HAS_COLON_RE = re.compile(r"[:：]")

# ---------------------------------------------------------------------------
# 个人信息字段
# ---------------------------------------------------------------------------

# 字段别名 → 规范字段名
_PERSONAL_FIELD_ALIASES = {
    "姓名": "name",
    "名字": "name",
    "意向": "intent",
    "求职意向": "intent",
    "求职目标": "intent",
    "目标岗位": "intent",
    "应聘岗位": "intent",
    "电话": "phone",
    "手机": "phone",
    "手机号": "phone",
    "联系电话": "phone",
    "邮箱": "email",
    "电子邮箱": "email",
    "邮件": "email",
    "城市": "city",
    "求职城市": "city",
    "意向城市": "city",
    "所在地": "city",
    "出生年月": "birth",
    "出生日期": "birth",
    "生日": "birth",
    "地址": "address",
    "籍贯": "address",
    "现居": "address",
    "照片": "photo",
    "证件照": "photo",
}
# 已识别但当前头部区没有槽位的字段（只登记，不渲染）
_PERSONAL_UNMAPPED_KEYS = {
    "民族": "民族", "政治面貌": "政治面貌", "性别": "性别",
    "届别": "届别", "毕业年份": "毕业年份", "身高": "身高",
    "婚况": "婚况", "工作年限": "工作年限", "到岗时间": "到岗时间",
    "微信": "微信", "QQ": "QQ", "个人网站": "个人主页",
    "GitHub": "GitHub", "语言": "语言",
}

# 头部拼接分隔符：全角「｜」两侧各一个半角空格（规范 · 格式细则）
HEADER_SEP = " ｜ "


# ---------------------------------------------------------------------------
# 文本归一化
# ---------------------------------------------------------------------------

def _normalize_title(raw: str) -> str:
    """章节标题归一化：全角→半角、去空白，用于别名匹配。"""
    return raw.translate(_FULLWIDTH_MAP).strip()


def _canonical_section(raw_title: str) -> Optional[str]:
    """章节标题 → 规范名；识别不到返回 None。

    「专业技能 / 证书奖项」这类合并标题：同时含「技能」与「证书/奖项/荣誉」
    关键词时判定为合并节。
    """
    norm = _normalize_title(raw_title)
    if not norm:
        return None
    if norm in SECTION_ALIASES:
        return SECTION_ALIASES[norm]

    parts = [p for p in _SLASH_RE.split(norm) if p]
    if len(parts) > 1:
        canon_parts = {SECTION_ALIASES[p] for p in parts if p in SECTION_ALIASES}
        if {SEC_SKILLS, SEC_CERTS} <= canon_parts:
            return SEC_SKILLS_CERTS
        if len(canon_parts) == 1:
            return canon_parts.pop()
        if canon_parts:
            # 合并了多个可识别节但不含技能+证书组合（如「项目经历 / 校园经历」）
            return None

    # 关键词兜底：仅当标题以关键词为主体时命中，避免误吞长标题
    if "技能" in norm and ("证书" in norm or "奖项" in norm or "荣誉" in norm):
        return SEC_SKILLS_CERTS
    return None


def _split_entry_title(raw_title: str):
    """条目标题 → (BulletBlock, matched_pattern)；未命中返回 (block, None)。

    支持：
        A - B（C）   A - B (C)      → title / role / meta
        A | B | C                   → title / role / meta
        A | B                       → title / role

    只归一化全角竖线（``｜``→``|``），**不动空格**——标题里的空格是内容
    （如「AI 简历生成与网申辅助填写助手」），不能因归一化而丢失。
    """
    title = raw_title.strip().translate(_ENTRY_TITLE_MAP)
    for pattern in (_ENTRY_DASH_RE, _ENTRY_PIPE3_RE):
        m = pattern.match(title)
        if m:
            return BulletBlock(
                title=m.group("title").strip(),
                role=m.group("role").strip(),
                meta=m.group("meta").strip(),
            ), pattern.pattern
    m = _ENTRY_PIPE2_RE.match(title)
    if m:
        return BulletBlock(
            title=m.group("title").strip(),
            role=m.group("role").strip(),
        ), _ENTRY_PIPE2_RE.pattern
    return BulletBlock(title=title), None


def _match_kv(text: str):
    """单个片段 → (key, value)；不是「键：值」返回 None。"""
    m = _KV_RE.match(text.strip().lstrip("-").strip())
    if not m:
        return None
    return m.group("key").strip().strip("*").strip(), m.group("val").strip().strip("*").strip()


def _iter_kv_segments(text: str, *, split_pipes: bool = True):
    """把一行拆成若干「键：值」段。

    个人信息区里三种历史写法都要支持：
        | 姓名 | 张三 |                          （表格行，由调用方先拆列）
        - 出生年月：2004.11 | 民族：汉族           （bullet + 竖线逐段成对）
        **求职意向**：产品经理（实习）｜对…        （加粗键 + 全角竖线）

    判定规则：竖线切出的**每一段**都是「键：值」→ 逐段收录；
    否则整行只取第一个冒号前的部分作键（避免把「A：x ｜ B：y」整体当值）。
    """
    if split_pipes and re.search(r"[|｜]", text):
        segs = [s for s in (x.strip() for x in re.split(r"[|｜]", text)) if s]
        matched = [_match_kv(s) for s in segs]
        if segs and all(m is not None for m in matched):
            for m in matched:
                yield m
            return
    whole = _match_kv(text)
    if whole:
        yield whole


# ---------------------------------------------------------------------------
# 解析主流程
# ---------------------------------------------------------------------------

class _ParseState:
    """单次解析的可变状态（避免主循环里堆十几个局部变量）。"""

    def __init__(self, diagnostics: Diagnostics, *, photo_root: Optional[Path]):
        self.blocks = ResumeBlocks(name="", intent="")
        self.diag = diagnostics
        self.photo_root = photo_root
        self.section: Optional[str] = None
        self.section_title: str = ""
        self.section_line: int = 0
        self.current_item: Optional[BulletBlock] = None
        self.current_item_list: Optional[list] = None
        self.personal: Dict[str, str] = {}
        self.seen_sections: Dict[str, tuple] = {}
        self.content_lines = 0
        self.h1_title: Optional[str] = None
        self.h1_line: int = 0
        self.h2_count = 0
        # 已识别但当前头部区无槽位的字段：{展示名: (值, 行号)}
        self.unmapped: Dict[str, tuple] = {}

    # -- 章节 -------------------------------------------------------------

    def start_section(self, title: str, line_no: int) -> None:
        self.h2_count += 1
        canon = _canonical_section(title)
        self.current_item = None
        self.current_item_list = None
        self.section_title = title

        if canon is None:
            self.section = None
            self.diag.warn(
                "unknown_section",
                f"未识别的章节标题「## {title}」，该节内容不会进入简历",
                line_no=line_no, raw=f"## {title}")
            return

        if canon in self.seen_sections:
            first_line, first_title = self.seen_sections[canon]
            if first_title == title:
                self.diag.warn(
                    "duplicate_section",
                    f"章节「{title}」重复出现（首次在第 {first_line} 行），"
                    f"内容将追加合并",
                    line_no=line_no, raw=f"## {title}")
            else:
                self.diag.warn(
                    "alias_section_merge",
                    f"章节「{title}」与第 {first_line} 行的「{first_title}」"
                    f"映射到同一布局板块，两节内容将追加合并"
                    f"（如非本意，请只保留其一）",
                    line_no=line_no, raw=f"## {title}")
        else:
            self.seen_sections[canon] = (line_no, title)

        self.section = canon
        self.section_line = line_no

    # -- 正文行 -----------------------------------------------------------

    def handle_line(self, raw: str, line_no: int) -> None:
        s = raw.strip()

        # 空行 / 水平线 / 引用行 / 表格分隔行
        if not s:
            return
        if _HR_RE.match(s):
            return
        if _TABLE_SEP_RE.match(s):
            return
        if s.startswith(">"):
            self._handle_quote(s, line_no)
            return

        # H1：文档标题（仅用于「个人信息」缺失时的姓名兜底）
        if s.startswith("# ") and not s.startswith("## "):
            if self.h1_title is None:
                self.h1_title = s[2:].strip()
                self.h1_line = line_no
            return

        # H2：章节
        if s.startswith("## "):
            self.start_section(s[3:].strip(), line_no)
            return

        # H3：条目标题
        if s.startswith("### "):
            self._handle_entry_title(s[4:].strip(), line_no)
            return
        if s.startswith("#### "):
            self.diag.warn(
                "unsupported_heading_depth",
                "四级标题「####」不受支持；规范只使用 ## 章节与 ### 条目",
                line_no=line_no, raw=s)
            return

        # 正文：交给当前章节的处理函数
        if self.section is None:
            if self._handle_preamble(s, line_no):
                return
            self.diag.warn(
                "orphan_line",
                "该行不在任何已知章节内，内容不会进入简历",
                line_no=line_no, raw=s)
            return

        handler = _SECTION_HANDLERS.get(self.section)
        if handler is None:
            # 刻意不渲染的章节（待补充）
            self.diag.info(
                "section_not_rendered",
                f"章节「{self.section_title}」刻意不进入简历（仅登记）",
                line_no=line_no, raw=s)
            return

        consumed = handler(self, s, line_no)
        if consumed:
            self.content_lines += 1
        else:
            self.diag.warn(
                "unrecognized_line",
                f"章节「{self.section_title}」内该行不符合任何已知格式，"
                f"内容不会进入简历",
                line_no=line_no, raw=s)

    def _handle_preamble(self, s: str, line_no: int) -> bool:
        """文档开头（首个 ``##`` 之前）的「键：值」行。

        历史写法把「求职意向」等信息写在标题下方的独立行里；这类行能被识别
        就收录，避免因为没放进「## 个人信息」表而整体丢失。
        """
        if self.h2_count > 0:
            return False
        segments = list(_iter_kv_segments(s))
        if not segments:
            return False
        used = False
        for key, value in segments:
            if key in _PERSONAL_FIELD_ALIASES or key in _PERSONAL_UNMAPPED_KEYS:
                self.record_personal(key, value, line_no)
                used = True
        if used:
            self.diag.info(
                "preamble_field_used",
                "该行位于首个 ## 之前（文档抬头区），已按个人信息字段收录；"
                "规范写法是放进「## 个人信息」表",
                line_no=line_no, raw=s)
        return used

    def _handle_quote(self, s: str, line_no: int) -> None:
        text = s.lstrip(">").strip()
        if not text:
            return
        # 首个 ## 之前的引用是文档级元信息（生成日期 / 数据来源），静默跳过
        if self.h2_count == 0:
            return
        if self.section is None:
            self.diag.info(
                "unmapped_quote",
                "该引用行所在章节未识别，内容不会进入简历",
                line_no=line_no, raw=s)
            return
        # 条目内的引用行（历史写法，如项目一句话简介）无法定位到槽位
        self.diag.info(
            "unmapped_quote",
            f"章节「{self.section_title}」内的引用行未映射到任何布局槽位"
            f"（ResumeBlocks 无对应字段）",
            line_no=line_no, raw=s)

    def _handle_entry_title(self, title: str, line_no: int) -> None:
        if self.section not in (SEC_EXPERIENCE, SEC_PROJECTS, SEC_CAMPUS):
            self.diag.warn(
                "entry_title_outside_entry_section",
                f"章节「{self.section_title}」不应出现 ### 条目；已忽略该标题",
                line_no=line_no, raw=f"### {title}")
            return

        block, matched = _split_entry_title(title)

        if self.section == SEC_CAMPUS:
            # 校园经历渲染为纯文本列表：条目标题即一行内容
            self.blocks.campus.append(
                block.title if not block.role
                else f"{block.title}｜{block.role}")
            self.current_item = None
            self.current_item_list = self.blocks.campus
            if matched is None:
                self.diag.info(
                    "campus_entry_title",
                    "校园经历条目按整行文本收录（该节渲染为纯文本列表）",
                    line_no=line_no, raw=f"### {title}")
            return

        if matched is None:
            self.diag.warn(
                "unparsed_entry_title",
                "条目标题不符合任一格式"
                "（应形如「### 组织 - 角色（时间）」或「### 组织 | 角色 | 时间」），"
                "已按整串作为标题收录，角色与时间缺失",
                line_no=line_no, raw=f"### {title}")
        elif not block.meta:
            self.diag.warn(
                "entry_without_meta",
                "条目缺时间；规范要求「### 组织 - 角色（时间）」带时间",
                line_no=line_no, raw=f"### {title}")
        elif not _META_RE.match(block.meta):
            self.diag.warn(
                "entry_meta_not_date",
                f"条目的时间「{block.meta}」不符合日期格式"
                f"（应形如 2023.12-2024.03 或 2026.07-至今）",
                line_no=line_no, raw=f"### {title}")

        target = (self.blocks.internships if self.section == SEC_EXPERIENCE
                  else self.blocks.projects)
        target.append(block)
        self.current_item = block
        self.current_item_list = target

    # -- 收尾 -------------------------------------------------------------

    def finalize(self) -> None:
        self._fill_header()

        if not self.blocks.name:
            self.diag.error(
                "missing_name",
                "内容层未解析出姓名：请在「## 个人信息」表里提供「姓名」行"
                "（或让文档 H1 以姓名开头）",
                line_no=self.h1_line or None,
                raw=f"# {self.h1_title}" if self.h1_title else "")
        if SEC_PERSONAL not in self.seen_sections:
            self.diag.warn(
                "personal_section_missing",
                "缺「## 个人信息」章节（应含 姓名/意向/电话/邮箱/城市 等字段）",
                line_no=self.h1_line or None)

        has_body = any((
            self.blocks.summary.strip(),
            self.blocks.education_lines,
            self.blocks.internships,
            self.blocks.projects,
            self.blocks.campus,
            self.blocks.skills,
            self.blocks.certs,
        ))
        if not has_body:
            self.diag.error(
                "empty_content",
                "内容层未解析出任何正文（优势/教育/实习/项目/校园/技能/证书全为空）",
            )

    def _fill_header(self) -> None:
        p = self.personal
        b = self.blocks

        b.name = p.get("name", "") or _name_from_h1(self.h1_title)
        if p.get("name"):
            pass
        elif b.name and self.h1_title:
            self.diag.warn(
                "name_from_h1_fallback",
                "「个人信息」表缺「姓名」字段，已回退从文档 H1 提取；"
                "请在个人信息表中显式给出「姓名」",
                line_no=self.h1_line or None, raw=f"# {self.h1_title}")

        b.intent = p.get("intent", "")

        area = HEADER_SEP.join(x for x in (
            f"求职城市：{p['city']}" if p.get("city") else "",
            f"出生年月：{p['birth']}" if p.get("birth") else "",
            f"籍贯：{p['address']}" if p.get("address") else "",
        ) if x)
        contact = HEADER_SEP.join(x for x in (
            f"电话：{p['phone']}" if p.get("phone") else "",
            f"邮箱：{p['email']}" if p.get("email") else "",
        ) if x)
        b.contact_lines = [x for x in (area, contact) if x]

        if p.get("photo"):
            b.photo_path = self._resolve_photo(p["photo"])
        # 「照片」是可选字段：缺失属正常（照片用不用是本份 Design Decision，
        # 不是内容层缺陷），故**不产生诊断**；调用方按 blocks.photo_path
        # 是否为 None 自行决定提示。

        # 已识别但无布局槽位的字段，逐条登记（不渲染、不静默丢弃）
        for label, (value, line_no) in sorted(self.unmapped.items()):
            self.diag.info(
                "unmapped_personal_field",
                f"个人字段「{label}」已识别，但当前头部区无对应槽位"
                f"（头部规范固定 4 行：姓名 / 意向 / 属地 / 联系）",
                line_no=line_no,
                raw=f"| {label} | {value} |",
            )

    def _resolve_photo(self, raw_value: str) -> str:
        value = raw_value.strip().strip("`").strip()
        candidate = Path(value)
        if not candidate.is_absolute() and self.photo_root is not None:
            candidate = Path(self.photo_root) / value
        if self.photo_root is not None and not candidate.is_file():
            self.diag.warn(
                "photo_not_found",
                f"照片文件不存在：{candidate}",
                raw=value)
        return str(candidate)

    def record_unmapped(self, key: str, value: str, line_no: int) -> None:
        self.unmapped[_PERSONAL_UNMAPPED_KEYS[key]] = (value, line_no)

    def record_personal(self, key: str, value: str, line_no: int) -> None:
        """登记一个个人信息字段；识别不到则告警。"""
        key = key.strip().strip("*").strip()
        value = value.strip().strip("*").strip()
        if not key or not value:
            return
        canon = _PERSONAL_FIELD_ALIASES.get(key)
        if canon:
            if canon in self.personal and self.personal[canon] != value:
                self.diag.warn(
                    "duplicate_personal_field",
                    f"个人字段「{key}」重复出现，后者覆盖前者"
                    f"（原值：{self.personal[canon]}）",
                    line_no=line_no, raw=f"| {key} | {value} |")
            self.personal[canon] = value
            return
        if key in _PERSONAL_UNMAPPED_KEYS:
            self.record_unmapped(key, value, line_no)
            return
        self.diag.warn(
            "unknown_personal_field",
            f"个人信息的字段名「{key}」不认识，该值不会进入简历",
            line_no=line_no, raw=f"| {key} | {value} |")


# H1 兜底取姓名时要排除的「标题词」——它们是文档标题，不是人名
_H1_STOPWORDS = {
    "简历", "个人简历", "求职简历", "简历内容", "简历摘要",
    "中文简历", "英文简历", "简历文档",
}


def _name_from_h1(h1_title: Optional[str]) -> str:
    """从 H1 提取姓名：支持「姓名 - 岗位」「姓名｜岗位」「简历内容：姓名 → 公司」等。

    只在 H1 形如「人名开头」时才返回；无法判定返回空串（由调用方报致命错误），
    绝不猜一个像人名的词出来。
    """
    if not h1_title:
        return ""
    text = h1_title
    for prefix in ("简历内容：", "简历内容:", "简历：", "简历:"):
        if text.startswith(prefix):
            text = text[len(prefix):]
    # 只取第一个分隔符之前的部分
    head = re.split(r"\s*(?:[-–—|｜／/]|->|→)\s*", text.strip(), maxsplit=1)[0]
    head = head.strip(" *_")
    if head in _H1_STOPWORDS:
        return ""
    # 姓名一般 2–4 个汉字
    if re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", head):
        return head
    return ""


# ---------------------------------------------------------------------------
# 章节处理函数（返回 True 表示该行已被消费）
# ---------------------------------------------------------------------------

def _h_personal(st: _ParseState, s: str, line_no: int) -> bool:
    if s.startswith("|"):
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 2:
            return False
        key, value = cells[0].strip(), cells[1].strip()
        if key in _PERSONAL_HEADER_CELLS and value in ("值", "内容", "信息"):
            return True  # 表头行
        if len(cells) > 2:
            st.diag.warn(
                "personal_row_extra_columns",
                f"个人信息应为两列（| 字段 | 值 |），该行有 {len(cells)} 列，"
                f"仅取前两列，其余内容不会进入简历",
                line_no=line_no, raw=s)
        st.record_personal(key, value, line_no)
        return True

    segments = list(_iter_kv_segments(s))
    if segments:
        for key, value in segments:
            st.record_personal(key, value, line_no)
        return True
    return False


def _h_summary(st: _ParseState, s: str, line_no: int) -> bool:
    text = s[2:].strip() if s.startswith("- ") else s
    if not text:
        return False
    if s.startswith("- "):
        st.diag.info(
            "bullet_in_summary",
            "「个人优势」规范上是整段文字；该 bullet 已按段落文本并入",
            line_no=line_no, raw=s)
    st.blocks.summary = (st.blocks.summary + text).strip()
    return True


def _h_education(st: _ParseState, s: str, line_no: int) -> bool:
    text = s[2:].strip() if s.startswith("- ") else s
    if not text:
        return False
    st.blocks.education_lines.append(text)
    return True


def _h_experience(st: _ParseState, s: str, line_no: int) -> bool:
    return _bullet_into_entry(st, s, line_no)


def _h_projects(st: _ParseState, s: str, line_no: int) -> bool:
    return _bullet_into_entry(st, s, line_no)


def _bullet_into_entry(st: _ParseState, s: str, line_no: int) -> bool:
    """把一行收进当前 ### 条目。

    规范写法是 ``- bullet``。历史文件里出现过 **非 bullet 的行**（如
    ``**项目成果**：日均订单 500+ | …``）。这类行**不丢弃**——按 bullet
    收进当前条目并给出告警，做到「不静默丢内容」且输出仍完整。
    """
    text = s[2:].strip() if s.startswith("- ") else s
    if not text:
        return False
    if st.current_item is None:
        st.diag.warn(
            "bullet_without_entry",
            f"章节「{st.section_title}」内的内容前没有 ### 条目标题，无法归属",
            line_no=line_no, raw=s)
        return False
    if not s.startswith("- "):
        st.diag.warn(
            "non_bullet_line_kept",
            "条目的要点应以「- 」开头；该行已按要点收录，请改写为 bullet",
            line_no=line_no, raw=s)
    st.current_item.bullets.append(text)
    return True


def _h_campus(st: _ParseState, s: str, line_no: int) -> bool:
    text = s[2:].strip() if s.startswith("- ") else s
    if not text:
        return False
    st.blocks.campus.append(text)
    return True


def _h_skills(st: _ParseState, s: str, line_no: int) -> bool:
    text = s[2:].strip() if s.startswith("- ") else s
    if not text:
        return False
    st.blocks.skills.append(text)
    return True


def _h_certs(st: _ParseState, s: str, line_no: int) -> bool:
    text = s[2:].strip() if s.startswith("- ") else s
    if not text:
        return False
    # 段落里可能是「A｜B｜C」一行多证；bullet 视作一条
    if s.startswith("- "):
        st.blocks.certs.append(text)
    else:
        st.blocks.certs.extend(
            c.strip() for c in re.split(r"[|｜、]", text) if c.strip())
    return True


def _h_skills_certs(st: _ParseState, s: str, line_no: int) -> bool:
    """合并节「## 专业技能 / 证书奖项」：按行前缀分派。"""
    text = s[2:].strip() if s.startswith("- ") else s
    if not text:
        return False
    m = _KV_RE.match(text)
    if m:
        key = m.group("key").strip()
        val = m.group("val").strip()
        if "技能" in key:
            st.blocks.skills.append(val)
            return True
        if "证书" in key or "奖项" in key or "荣誉" in key:
            st.blocks.certs.extend(
                c.strip() for c in re.split(r"[|｜、]", val) if c.strip())
            return True
    # 无前缀：默认按技能收（证书通常会有前缀），并提示
    st.diag.info(
        "merged_section_unlabeled",
        "合并节内该行无「技能/证书」前缀，已按技能收录",
        line_no=line_no, raw=s)
    st.blocks.skills.append(text)
    return True


_SECTION_HANDLERS = {
    SEC_PERSONAL: _h_personal,
    SEC_SUMMARY: _h_summary,
    SEC_EDUCATION: _h_education,
    SEC_EXPERIENCE: _h_experience,
    SEC_PROJECTS: _h_projects,
    SEC_CAMPUS: _h_campus,
    SEC_SKILLS: _h_skills,
    SEC_CERTS: _h_certs,
    SEC_SKILLS_CERTS: _h_skills_certs,
}


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------

def parse_resume_md_text(text: str, *, source: Optional[Path] = None,
                         photo_root=None, strict: bool = True) -> ParsedResume:
    """解析 resume.md 文本（已读入内存）。测试与 ``parse_resume_md`` 共用。"""
    diag = Diagnostics()
    st = _ParseState(diag, photo_root=Path(photo_root) if photo_root else None)
    for i, raw in enumerate(text.splitlines(), start=1):
        st.handle_line(raw, i)
    st.finalize()

    parsed = ParsedResume(blocks=st.blocks, diagnostics=diag,
                          source=Path(source) if source else None)
    if strict:
        parsed.raise_if_fatal()
    return parsed


def parse_resume_md(path, *, photo_root=None, strict: bool = True) -> ParsedResume:
    """从文件路径解析 resume.md。

    参数：
        path       : resume.md 路径
        photo_root : 照片相对路径的基准目录（通常是简历库根目录）；
                     None 时保留原始相对路径，由调用方自行解析
        strict     : True（默认）时，遇致命缺陷抛 ``ResumeParseError``

    返回：``ParsedResume``（``.blocks`` 与 ``.diagnostics``）
    """
    p = Path(path)
    if not p.is_file():
        diag = Diagnostics()
        diag.error("file_not_found", f"内容层文件不存在：{p}")
        parsed = ParsedResume(blocks=ResumeBlocks(name="", intent=""),
                              diagnostics=diag, source=p)
        if strict:
            parsed.raise_if_fatal()
        return parsed
    try:
        text = p.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as exc:
        diag = Diagnostics()
        diag.error("file_unreadable", f"内容层文件不可读：{p}（{exc}）")
        parsed = ParsedResume(blocks=ResumeBlocks(name="", intent=""),
                              diagnostics=diag, source=p)
        if strict:
            parsed.raise_if_fatal()
        return parsed
    return parse_resume_md_text(text, source=p, photo_root=photo_root,
                                strict=strict)


def parse_blocks(path_or_text, *, photo_root=None, strict: bool = True):
    """便捷入口：只要 ``ResumeBlocks``，不要诊断对象。

    致命缺陷仍会抛 ``ResumeParseError``（``strict=True``）。
    """
    if isinstance(path_or_text, Path):
        return parse_resume_md(path_or_text, photo_root=photo_root,
                               strict=strict).blocks
    text = str(path_or_text)
    if "\n" not in text and Path(text).is_file():
        return parse_resume_md(text, photo_root=photo_root, strict=strict).blocks
    return parse_resume_md_text(text, photo_root=photo_root,
                                strict=strict).blocks
