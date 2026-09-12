# -*- coding: utf-8 -*-
"""resume_map.py — 把 AI 写出的简历内容翻译成模板字段值。

解决的核心问题：
    AI 产出的是「人读的简历」（resume.md），模板需要的是「机器读的字段」
    （{{NAME}} / {{W1R1}} …）。这一步此前完全缺失，导致渲染链路断了。

三级降级策略（优先级从高到低）：
    L1  旁路字段文件  resume.fields.json      —— 最可靠，AI 直接给字段字典
    L2  resume.md 内嵌「## 模板字段」表格      —— 可读可追溯
    L3  章节结构解析（教育/实习/项目/技能…）  —— 兜底，对已有 resume.md 生效

L3 解析约定（与 Agent 提示词中的产出格式对齐）：
    # 姓名 - 目标岗位
    **学校 | 专业 | 届别**
    **求职意向**：xxx
    > 个人简介 / 自我评价
    ## 教育经历      -> 段落标题 或 **学校 | 专业（学历）| 2023.09 - 2027.06**
    ## 项目经历      -> ### 项目名 | 角色 | 时间   + blockquote + bullets
    ## 实习经历      -> ### 公司 | 职位 | 时间     + blockquote + bullets
    ## 校园经历      -> ### 组织/角色
    ## 专业技能      -> **分类**：工具列表   + bullets
    ## 证书奖项
    ## 自我评价      -> 正文段落
    ## 基本信息      -> 标签行

本文件不含任何用户个人信息，不含任何绝对路径。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ============================================================================
# 字段别名表：模板字段名 -> 规范化取值路径
# ============================================================================

# 单个标量字段
SCALAR_ALIASES: Dict[str, List[str]] = {
    "NAME":  ["姓名", "名字", "name"],
    "OBJ":   ["求职意向", "目标岗位", "意向岗位", "应聘岗位", "objective", "期望职位"],
    "CITY":  ["求职城市", "所在城市", "城市", "现居地", "工作地点", "city"],
    "TEL":   ["电话", "手机", "手机号", "联系电话", "tel", "phone"],
    "EML":   ["邮箱", "电子邮箱", "email", "mail"],
    "ADDR":  ["地址", "住址", "现居地址", "通讯地址"],
    "BIR":   ["出生年月", "出生日期", "生日"],
    "ETH":   ["民族"],
    "POL":   ["政治面貌"],
    "HT":    ["身高"],
    "SCH":   ["学校", "毕业院校", "院校"],
    "MAJ":   ["专业", "主修专业"],
    "DG":    ["学历", "学位"],
    "EDD":   ["教育时间", "在校时间", "就读时间"],
    "CRS":   ["主修课程", "课程", "相关课程"],
    "SM":    ["自我评价", "个人简介", "个人优势", "自我介绍"],
    "SM2":   ["自我评价2", "自我评价二", "补充评价"],
    "CERTS": ["证书", "资格证书", "技能证书"],
    "INT":   ["兴趣爱好", "兴趣", "爱好"],
    "SK1":   ["技能1"], "SK2": ["技能2"], "SK3": ["技能3"],
    "SK4":   ["技能4"], "SK5": ["技能5"], "SK6": ["技能6"],
    "EX1":   ["优势1"], "EX2": ["优势2"], "EX3": ["优势3"],
    "CER1":  ["证书1"], "CER2": ["证书2"], "CER3": ["证书3"],
    "AW1":   ["奖项1"], "AW2": ["奖项2"], "AW3": ["奖项3"], "AW4": ["奖项4"],
    "HON1":  ["荣誉1"], "HON2": ["荣誉2"],
}

# 结构化序列字段：模板字段前缀 -> 内容来源
# {n} 是条目序号（1 起），{r} 是描述行序号
SEQUENCE_SPECS: Dict[str, str] = {
    # 实习 / 工作
    "W": "internships",
    # 项目
    "P": "projects",
    # 校园
    "C": "campus",
}

_SUFFIX_ROLE = {
    "D": "period",
    "C": "org",
    "N": "org",
    "P": "role",
    "A": "achievement",
}


def _seq_field(field: str) -> Optional[Tuple[str, int, str]]:
    """解析 W1R2 / P2N / C1D 这类字段。

    返回 (来源键, 序号, 后缀)，不是序列字段则返回 None。
    """
    m = re.fullmatch(r"([WPC])(\d+)([A-Z])(\d*)", field)
    if not m:
        return None
    prefix, index, suffix, extra = m.groups()
    source = SEQUENCE_SPECS.get(prefix)
    if not source:
        return None
    return (source, int(index), suffix + (extra or ""))


# ============================================================================
# L3：章节结构解析
# ============================================================================

_SECTION_ALIASES: Dict[str, List[str]] = {
    "education":  ["教育经历", "教育背景", "学历信息"],
    "projects":   ["项目经历", "项目经验", "主要项目"],
    "internships": ["实习经历", "工作经历", "工作经验", "实习经验", "实践经历"],
    "campus":     ["校园经历", "校园活动", "学生工作", "社团经历"],
    "skills":     ["专业技能", "技能", "技能证书", "技能特长"],
    "certs":      ["证书奖项", "荣誉奖项", "获奖情况", "证书", "奖项荣誉"],
    "summary":    ["自我评价", "个人评价", "个人优势", "自我介绍"],
    "basic":      ["基本信息", "个人信息", "联系方式"],
    "intent":     ["求职意向", "职业目标"],
}

_METADATA_KEYS = (
    "求职意向", "目标岗位", "意向岗位", "应聘岗位", "期望职位",
)


class ParsedResume:
    """解析结果容器。"""

    def __init__(self) -> None:
        self.name: Optional[str] = None
        self.headline: Optional[str] = None
        self.obj: Optional[str] = None
        self.school_line: Optional[str] = None
        self.summary: Optional[str] = None
        self.education: Dict[str, str] = {}
        self.internships: List[Dict[str, object]] = []
        self.projects: List[Dict[str, object]] = []
        self.campus: List[Dict[str, object]] = []
        self.skills: Dict[str, List[str]] = {}
        self.certs: List[str] = []
        self.basic: Dict[str, str] = {}
        self.warnings: List[str] = []
        # 技能「分类」的顺序标签（用于报告可读性）
        self.skill_categories: List[str] = []

    def entries(self, source_key: str) -> List[Dict[str, object]]:
        """按来源键取出条目列表（internships / projects / campus）。"""
        return getattr(self, source_key)

    def describe_entry(self, source_key: str, index: int) -> str:
        """给条目生成人类可读标签，用于「被丢弃内容」提示。"""
        records = self.entries(source_key)
        if not (1 <= index <= len(records)):
            return f"#{index}"
        rec = records[index - 1]
        org = str(rec.get("org", "") or "").strip()
        role = str(rec.get("role", "") or "").strip()
        period = str(rec.get("period", "") or "").strip()
        label = " / ".join(p for p in (org, role) if p) or f"#{index}"
        return f"{label}（{period}）" if period else label

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "headline": self.headline,
            "obj": self.obj,
            "school_line": self.school_line,
            "summary": self.summary,
            "education": self.education,
            "internships": self.internships,
            "projects": self.projects,
            "campus": self.campus,
            "skills": self.skills,
            "certs": self.certs,
            "basic": self.basic,
            "warnings": self.warnings,
        }


class MapReport:
    """映射过程的诊断报告。

    为什么需要它（真实痛点）：
        模板的槽位数是**固定**的（template_02 只有 W1/W2 两段实习，你的简历库有 4 段）。
        此前多余内容会被**静默丢弃** —— 用户以为都写进去了，实际少了三行。
        本报告把「哪些内容没进模板」显式列出来，让 AI 与用户都能发现并处理。
    """

    def __init__(self) -> None:
        self.truncated: List[str] = []      # 槽位不足被丢弃的条目
        self.slot_summary: Dict[str, str] = {}   # 来源 -> "用了 2 / 共 4"
        self.supplemented: Dict[str, str] = {}
        self.unmapped_fields: List[str] = []
        # 内容层声明了、但当前模板没有对应字段的键（会被静默丢弃）
        self.unknown_fields: List[str] = []
        self.unknown_values: Dict[str, str] = {}
        self.section_summary: Dict[str, int] = {}

    @property
    def has_drops(self) -> bool:
        return bool(self.truncated)

    def to_dict(self) -> Dict[str, object]:
        return {
            "truncated": list(self.truncated),
            "slot_summary": dict(self.slot_summary),
            "supplemented": dict(self.supplemented),
            "unmapped_fields": list(self.unmapped_fields),
            "unknown_fields": list(self.unknown_fields),
            "unknown_values": dict(self.unknown_values),
            "section_summary": dict(self.section_summary),
        }


def _clean(text: str) -> str:
    """去掉 markdown 强调与多余空白。"""
    text = text.strip()
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


# H1 里常见的文档标题前缀（不是姓名）
_TITLE_PREFIXES = (
    "简历内容", "简历", "个人简历", "中文简历", "求职简历",
    "Resume", "CV",
)

# 姓名的合理长度（CJK 2~4 字，英文名最多 40 个字符）
_MAX_NAME_LEN = 40


def _looks_like_name(text: str) -> bool:
    """判断一段文本是否像人名。

    真实 resume.md 的 H1 有两种写法，必须区分：
        # 张三 - 产品经理          -> 姓名 + 意向
        # 简历内容：张三 → 某公司 - 岗位  -> 文档标题，姓名藏在里面
    曾经的缺陷：把整串文档标题当成姓名，导致文件名叫
    「简历内容：张三 → 某公司 - 岗位_某公司_岗位.docx」。
    """
    t = text.strip()
    if not t or len(t) > _MAX_NAME_LEN:
        return False
    if any(t.startswith(p) for p in _TITLE_PREFIXES):
        return False
    # 含箭号/冒号/竖线/斜杠等结构符号 -> 是标题而非姓名
    if re.search(r"[→:：|｜/\\]", t):
        return False
    # CJK 姓名通常 2~4 字且不含空格
    if re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", t):
        return True
    # 英文名：允许字母、空格、点、连字符
    if re.fullmatch(r"[A-Za-z][A-Za-z .'\-]{1,38}", t):
        return True
    return False


def _split_title(title: str) -> Tuple[Optional[str], Optional[str]]:
    """从 H1 标题里拆出 (姓名, 求职意向)。

    兼容：
        '张三 - 产品经理'
        '张三 | 产品经理'
        '简历内容：张三 → 某公司 - AI 产品运营实习生'
        '个人简历 张三'
    拆不出姓名时返回 (None, ...)，绝不把整串标题当姓名。
    """
    text = title.strip()

    # 去掉「简历内容：」「简历：」等前缀
    text = re.sub(r"^(?:" + "|".join(_TITLE_PREFIXES) + r")\s*[:：]?\s*", "", text)

    # 先按箭号切：箭号左侧是「姓名」，右侧是「公司 - 岗位」
    if "→" in text:
        left, _, right = text.partition("→")
        name = left.strip()
        obj = right.strip() or None
        # 右侧可能还带 "- 岗位"，整体作为意向描述即可
        return (name if _looks_like_name(name) else None, obj)

    # 常规：按 - / | 切成「姓名」+「意向」
    parts = re.split(r"\s*[-–—|｜]\s*", text, maxsplit=1)
    head = parts[0].strip()
    tail = parts[1].strip() if len(parts) > 1 else None

    if _looks_like_name(head):
        return (head, tail or None)

    # 头部不像姓名（如「个人简历 张三」）：在里面找第一个像姓名的片段
    for token in re.split(r"[\s,，、]+", head):
        if _looks_like_name(token):
            return (token, tail or None)

    return (None, tail or None)


def _split_pipe(text: str) -> List[str]:
    """按全角/半角竖线切分。"""
    return [p.strip() for p in re.split(r"[|｜]", text) if p.strip()]


def parse_resume_md(text: str) -> ParsedResume:
    """解析 resume.md 的章节结构。"""
    r = ParsedResume()
    lines = text.splitlines()

    # ---------- 头部 ----------
    current_section: Optional[str] = None
    buffer: List[str] = []

    def section_of(heading: str) -> Optional[str]:
        h = heading.strip()
        for key, alias in _SECTION_ALIASES.items():
            if any(a in h for a in alias):
                return key
        return None

    i = 0
    # 1) H1 / 首行 -> 姓名 + 意向
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i < len(lines) and lines[i].lstrip().startswith("# "):
        title = _clean(lines[i][2:])
        name, obj = _split_title(title)
        r.name = name
        if obj:
            r.obj = obj
        i += 1

    # 2) 头部若干行：加粗行 -> 学校信息；求职意向行 -> OBJ；blockquote -> 个人简介
    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()
        if stripped.startswith("##"):
            break
        if not stripped or stripped in ("---", "***", "___"):
            i += 1
            continue

        meta = re.match(r"^\*\*\s*(.+?)\s*\*\*\s*[:：]\s*(.+)$", stripped)
        if meta:
            key, value = _clean(meta.group(1)), _clean(meta.group(2))
            if key in _METADATA_KEYS:
                r.obj = value
            else:
                r.basic[key] = value
            i += 1
            continue

        if stripped.startswith(">"):
            block = _collect_blockquote(lines, i)
            text_block = _clean(" ".join(block[0]))
            if r.summary is None:
                r.summary = text_block
            i = block[1]
            continue

        if stripped.startswith("**") and stripped.endswith("**"):
            r.school_line = _clean(stripped)
            i += 1
            continue

        # 普通文本行：若含学校/届别信息则作 school_line，否则忽略
        if r.school_line is None and re.search(r"大学|学院|届|本科|硕士|专科", stripped):
            r.school_line = _clean(stripped)
        i += 1

    # ---------- 各章节 ----------
    current_section = None
    buffer = []
    idx = i
    while idx <= len(lines):
        line = lines[idx] if idx < len(lines) else "## __EOF__"
        stripped = line.strip()
        if stripped.startswith("## "):
            if current_section:
                _dispatch(r, current_section, buffer)
            current_section = section_of(stripped[3:])
            buffer = []
        elif current_section and not stripped.startswith("# "):
            buffer.append(line)
        idx += 1

    _fill_from_school_line(r)
    return r


def _collect_blockquote(lines: List[str], start: int) -> Tuple[List[str], int]:
    """收集从 start 开始的 blockquote 行。返回 (文本行, 下一个索引)。"""
    collected: List[str] = []
    i = start
    while i < len(lines) and lines[i].strip().startswith(">"):
        collected.append(lines[i].strip().lstrip(">").strip())
        i += 1
    return collected, i


def _dispatch(r: ParsedResume, section: str, buffer: List[str]) -> None:
    handler = {
        "education": _parse_education,
        "projects": lambda rr, b: _parse_timeline(rr, b, "projects"),
        "internships": lambda rr, b: _parse_timeline(rr, b, "internships"),
        "campus": _parse_campus,
        "skills": _parse_skills,
        "certs": _parse_certs,
        "summary": _parse_summary,
        "basic": _parse_basic,
        "intent": _parse_intent,
    }.get(section)
    if handler:
        handler(r, buffer)


# 校园经历常见「角色 / 组织」混写形态，用于拆出 C{n}P
_ROLE_WORDS = (
    "主席", "副主席", "部长", "副部长", "班长", "团支书", "委员", "会长", "副会长",
    "社长", "队长", "组长", "干事", "负责人", "主管", "主任", "秘书", "成员",
)


def _split_role_from_org(text: str) -> Tuple[str, str]:
    """把校园经历标题拆成 (组织, 角色)。

    例：
        '校学生会 | 部长'                -> ('校学生会', '部长')
        '校园学生会部长 / 自律会主席'    -> ('校园学生会', '部长 / 自律会主席')
        '学生会主席'                     -> ('学生会', '主席')
        '班长 / 团支书'                  -> ('', '班长 / 团支书')

    最后一种情况组织位留空：整串都是职务、没有组织名，
    若回退成整串会让 C{n}N 与 C{n}P 填出同样的文字，简历上显得重复。
    """
    if not text:
        return ("", "")

    parts = [p.strip() for p in re.split(r"[/／|｜]", text) if p.strip()]

    if len(parts) >= 2:
        first = parts[0]

        # 情形 A：第一段本身是「组织 + 职务」（如 校园学生会部长 + 自律会主席）
        #         -> 把第一段再拆一次，取其组织部分
        m = re.match(
            r"^(.+?)(部长|副部长|主席|副主席|班长|团支书|会长|副会长|社长|队长|组长|"
            r"干事|委员|负责人|主管|主任|秘书|成员)$",
            first,
        )
        if m and len(m.group(1)) >= 2:
            org = m.group(1).strip()
            roles = [m.group(2).strip()] + parts[1:]
            return (org, " / ".join(roles))

        # 情形 B：第一段不含职务词 -> 它是组织名
        if not any(w in first for w in _ROLE_WORDS):
            return (first, " / ".join(parts[1:]))

        # 情形 C：第一段是纯职务 -> 没有组织名，组织位留空
        return ("", " / ".join(parts))

    # 无分隔符：尝试「组织 + 职务」从尾部锚定拆分
    m = re.match(
        r"^(.+?)(部长|副部长|主席|副主席|班长|团支书|会长|副会长|社长|队长|组长|"
        r"干事|委员|负责人|主管|主任|秘书|成员)$",
        text,
    )
    if m and len(m.group(1)) >= 2:
        return (m.group(1).strip(), m.group(2).strip())

    return (text, "")


# 占位符文本：这些值不得进入简历
_PLACEHOLDER_VALUES = {"待补充", "待确认", "待用户确认", "无", "N/A", "n/a", "-", "—", "/"}


def _is_placeholder(text: str) -> bool:
    """判断是否为「待补充」类占位文本。"""
    t = text.strip()
    if not t:
        return True
    if t in _PLACEHOLDER_VALUES:
        return True
    return bool(re.fullmatch(r"[（(]?待[补充确认]?[)）]?", t))


def _filter_placeholders(items: List[str]) -> List[str]:
    return [i for i in items if not _is_placeholder(i)]


def _condense_role(role: str) -> str:
    """把过长的角色串压缩到适合窄槽位。

    真实场景：resume.md 的校园经历标题常写成
        ### 校园学生会部长 / 自律会主席
    解析后角色位可能得到并列职务或「组织+职务」长串，
    塞进只有几个字符宽的模板角色槽会被挤成两行，破坏版式。

    处理顺序：
        1. 有分隔符 -> 只保留第一个职务（第一个通常是最主要的）；
        2. 「组织 + 职务」形态 -> 剥掉组织前缀，只留职务词；
        3. 仍然过长 -> 原样返回（宁可长一点，也不丢信息）。
    """
    if not role:
        return ""

    parts = [p.strip() for p in re.split(r"[/／|｜、,，]", role) if p.strip()]
    if len(parts) > 1:
        return parts[0]

    # 「组织 + 职务」-> 只留职务词。
    # 这一步与长度无关：即使整串不算长（如「校园学生会部长」宽 14），
    # 组织位已经单独填了组织名，角色位再重复组织名就是冗余。
    m = re.match(
        r"^(.+?)(部长|副部长|主席|副主席|班长|团支书|会长|副会长|社长|队长|组长|"
        r"干事|委员|负责人|主管|主任|秘书|成员)$",
        role,
    )
    if m and len(m.group(1)) >= 2:
        return m.group(2).strip()

    return role


def _visual_width(text: str) -> int:
    """视觉宽度：CJK 字符算 2，其余算 1。"""
    return sum(2 if ord(ch) > 0x2E80 else 1 for ch in text)


def _parse_education(r: ParsedResume, buffer: List[str]) -> None:
    for line in buffer:
        s = _clean(line)
        if not s or s == "---":
            continue
        if line.strip().startswith(">"):
            continue

        # **学校 | 专业（学历） | 2023.09 - 2027.06**
        if "|" in s or "｜" in s:
            parts = _split_pipe(s)
            if len(parts) >= 1:
                r.education.setdefault("SCH", parts[0])
            if len(parts) >= 2:
                major_raw = parts[1]
                # 专业（学历）
                m = re.match(r"^(.+?)\s*[（(](.+?)[)）]\s*$", major_raw)
                if m:
                    r.education.setdefault("MAJ", m.group(1).strip())
                    r.education.setdefault("DG", m.group(2).strip())
                else:
                    r.education.setdefault("MAJ", major_raw)
            if len(parts) >= 3:
                r.education.setdefault("EDD", parts[2])
            continue

        # - 主修课程：xxx
        kv = re.match(r"^[-*]?\s*(.+?)\s*[:：]\s*(.+)$", s)
        if kv:
            key, value = kv.group(1).strip(), kv.group(2).strip()
            if "课程" in key:
                r.education.setdefault("CRS", value)
            elif "GPA" in key.upper() or "绩点" in key:
                r.education.setdefault("GPA", value)
            elif "排名" in key:
                r.education.setdefault("RANK", value)
            continue

        # 兜底：含年份区间的行当作 EDD
        if re.search(r"\d{4}\s*[.\-/年]\s*\d{1,2}\s*[-–—~至]\s*", s):
            r.education.setdefault("EDD", s)


def _looks_like_entry_head(text: str) -> bool:
    """判断 ### 标题是否为「组织 | 角色 | 时间」形态。"""
    return bool(re.search(r"[|｜]", text))


def _split_entry_head(text: str) -> Dict[str, str]:
    """把 '某公司 | 职位 | 2023.12 - 2024.03' 拆成 org/role/period。

    兼容两段式：'某公司 | 职位'，以及顺序颠倒的写法。
    """
    parts = _split_pipe(text)
    out: Dict[str, str] = {}
    period_re = re.compile(
        r"(\d{4}\s*[.\-/年]?\s*\d{0,2}\s*[-–—~至]{1,2}\s*"
        r"(\d{4}\s*[.\-/年]?\s*\d{0,2}|至今|今|present))",
        re.I,
    )
    rest: List[str] = []
    for p in parts:
        m = period_re.search(p)
        if m and "period" not in out:
            out["period"] = _clean(m.group(1))
            leftover = (p[: m.start()] + p[m.end():]).strip(" ,，、")
            if leftover:
                rest.append(leftover)
        else:
            rest.append(p)

    if rest:
        out["org"] = rest[0]
    if len(rest) > 1:
        out["role"] = " ".join(rest[1:])
    return out


def _parse_timeline(r: ParsedResume, buffer: List[str], bucket: str) -> None:
    """解析实习 / 项目 这类「条目 + 描述」结构。"""
    target: List[Dict[str, object]] = getattr(r, bucket)
    current: Optional[Dict[str, object]] = None

    for line in buffer:
        stripped = line.strip()
        if not stripped or stripped == "---":
            continue

        if stripped.startswith("### "):
            head = _clean(stripped[4:])
            info = _split_entry_head(head)
            current = {
                "org": info.get("org", head),
                "role": info.get("role", ""),
                "period": info.get("period", ""),
                "context": "",
                "bullets": [],
                "achievement": "",
            }
            target.append(current)
            continue

        if current is None:
            # 无 ### 的退化情况：整段作为单条目
            if stripped.startswith(">"):
                continue
            if stripped.startswith("- ") or stripped.startswith("* "):
                if not target:
                    target.append({"org": "", "role": "", "period": "",
                                   "context": "", "bullets": [], "achievement": ""})
                target[-1]["bullets"].append(_clean(stripped[2:]))  # type: ignore[union-attr]
            continue

        if stripped.startswith(">"):
            current["context"] = _clean(stripped.lstrip(">").strip())
            continue

        if stripped.startswith("- ") or stripped.startswith("* "):
            bullet = _clean(stripped[2:])
            if bullet.startswith("项目成果") or bullet.startswith("成果"):
                current["achievement"] = re.sub(
                    r"^(项目)?成果\s*[:：]\s*", "", bullet
                )
            else:
                current["bullets"].append(bullet)  # type: ignore[union-attr]
            continue

        # **项目成果**：xxx
        achv = re.match(r"^\*{0,2}\s*(项目成果|成果|业绩)\s*\*{0,2}\s*[:：]\s*(.+)$", stripped)
        if achv:
            current["achievement"] = _clean(achv.group(2))
            continue


def _parse_campus(r: ParsedResume, buffer: List[str]) -> None:
    current: Optional[Dict[str, object]] = None
    for line in buffer:
        stripped = line.strip()
        if not stripped or stripped == "---":
            continue
        if stripped.startswith("### "):
            head = _clean(stripped[4:])
            info = _split_entry_head(head)
            org = info.get("org", head)
            role = info.get("role", "")
            # 校园经历常见「组织 / 角色」混写，需要拆开才能填 C{n}N + C{n}P
            if not role:
                org, role = _split_role_from_org(org)
            current = {
                "org": org,
                "role": role,
                "period": info.get("period", ""),
                "bullets": [],
            }
            r.campus.append(current)
            continue
        if stripped.startswith("- ") or stripped.startswith("* "):
            if current is None:
                current = {"org": "", "role": "", "period": "", "bullets": []}
                r.campus.append(current)
            current["bullets"].append(_clean(stripped[2:]))  # type: ignore[union-attr]


def _parse_skills(r: ParsedResume, buffer: List[str]) -> None:
    """支持 '**分类**：工具列表' 与 '- 工具：熟练度' 两种写法。"""
    flat: List[str] = []
    for line in buffer:
        stripped = line.strip()
        if not stripped or stripped == "---":
            continue
        if stripped.startswith(">"):
            continue
        kv = re.match(r"^\*{0,2}\s*(.+?)\s*\*{0,2}\s*[:：]\s*(.+)$", stripped)
        if kv:
            category = _clean(kv.group(1))
            value = _clean(kv.group(2))
            if category and value and len(category) <= 12:
                # 分类行里的工具用分隔符切开，并去掉全角空格（模板常写成「A ／ B」）
                r.skills[category] = [
                    item.strip().strip("\u3000\u2007\u2002")
                    for item in re.split(r"[/、,，;；]", value)
                    if item.strip()
                ]
                r.skill_categories.append(category)
                continue
        if stripped.startswith("- ") or stripped.startswith("* "):
            flat.append(_clean(stripped[2:]).strip())
            continue
        if stripped.startswith("**") and stripped.endswith("**"):
            category = _clean(stripped)
            r.skills.setdefault(category, [])
            r.skill_categories.append(category)
            continue

    if flat:
        r.skills.setdefault("其他技能", []).extend(flat)


def _parse_certs(r: ParsedResume, buffer: List[str]) -> None:
    """解析证书奖项章节。

    兼容：
        | 类别 | 名称 | 备注 |   （取「名称」列）
        - CET-4、普通话二级乙等
        **荣誉**：xxx
    「待补充」等占位文本一律丢弃，绝不进入简历。
    """
    for line in buffer:
        stripped = line.strip()
        if not stripped or stripped == "---" or stripped.startswith(">"):
            continue

        if stripped.startswith("|"):
            if re.match(r"^\|[-: |]+\|$", stripped):
                continue
            cells = [_clean(c) for c in stripped.strip("|").split("|")]
            if len(cells) < 2:
                continue
            category, name = cells[0], cells[1]
            if category in ("类别", "分类") or name in ("名称", "证书名称"):
                continue
            if _is_placeholder(name):
                continue
            entry = name
            # 备注列若是有效信息且不是「待补充」，附在后面
            if len(cells) >= 3 and cells[2] and not _is_placeholder(cells[2]):
                entry = f"{name}（{cells[2]}）"
            if entry not in r.certs:
                r.certs.append(entry)
            continue

        clean = _clean(re.sub(r"^[-*]\s*", "", stripped))
        # 去掉「证书：」「奖项：」这类前缀
        clean = re.sub(r"^(证书|奖项|荣誉|资格证书)\s*[:：]\s*", "", clean)
        for item in re.split(r"[、;；,，]", clean):
            item = item.strip()
            if item and not _is_placeholder(item) and item not in r.certs:
                r.certs.append(item)


def _parse_summary(r: ParsedResume, buffer: List[str]) -> None:
    pieces: List[str] = []
    for line in buffer:
        stripped = line.strip()
        if not stripped or stripped == "---":
            continue
        if stripped.startswith(">"):
            text = _clean(stripped.lstrip(">").strip())
        elif stripped.startswith("- ") or stripped.startswith("* "):
            text = _clean(stripped[2:])
        else:
            text = _clean(stripped)
        if text:
            pieces.append(text)
    if pieces:
        r.summary = " ".join(pieces)


def _parse_basic(r: ParsedResume, buffer: List[str]) -> None:
    for line in buffer:
        stripped = line.strip()
        if not stripped or stripped == "---":
            continue
        clean = _clean(re.sub(r"^[-*]\s*", "", stripped))
        for part in re.split(r"[|｜]", clean):
            kv = re.match(r"^(.+?)\s*[:：]\s*(.+)$", part.strip())
            if kv:
                r.basic.setdefault(kv.group(1).strip(), kv.group(2).strip())


def _parse_intent(r: ParsedResume, buffer: List[str]) -> None:
    for line in buffer:
        stripped = line.strip()
        if not stripped:
            continue
        clean = _clean(re.sub(r"^[-*]\s*", "", stripped))
        kv = re.match(r"^(.+?)\s*[:：]\s*(.+)$", clean)
        if kv:
            r.basic.setdefault(kv.group(1).strip(), kv.group(2).strip())
            if kv.group(1).strip() in _METADATA_KEYS and not r.obj:
                r.obj = kv.group(2).strip()
        elif not r.obj:
            r.obj = clean


def _fill_from_school_line(r: ParsedResume) -> None:
    """从 '**某虚构大学 | 电气工程及其自动化 | 2027届**' 反推教育字段。"""
    if not r.school_line:
        return
    parts = _split_pipe(r.school_line)
    if not parts:
        return
    for p in parts:
        if re.search(r"大学|学院|学校", p):
            r.education.setdefault("SCH", p)
        elif re.search(r"\d{4}", p) and "届" in p:
            r.education.setdefault("GRADUATION", p)
        elif re.search(r"本科|硕士|博士|专科|学士", p):
            r.education.setdefault("DG", p)
        elif p and "MAJ" not in r.education:
            r.education.setdefault("MAJ", p)
    if r.obj is None and len(parts) > 1 and not re.search(r"大学|学院", parts[1]):
        pass


# ============================================================================
# L2：resume.md 内嵌「## 模板字段」表格
# ============================================================================

def extract_inline_fields(text: str) -> Dict[str, str]:
    """提取 resume.md 中「字段名 -> 值」的表格行。

    真实的 resume.md 有两种写法，都必须支持：

        写法 A：集中在一节里
            ## 模板字段
            | 字段 | 值 |
            |---|---|
            | NAME | 张三 |

        写法 B：分散在各章节里（更常见，因为可读性更好）
            ## 个人信息
            | 字段 | 值 |
            |------|-----|
            | NAME | 张三 |
            ## 教育经历
            | 字段 | 值 |
            |------|-----|
            | SCH | 某大学 |

    曾经的缺陷：只在「模板字段 / 字段映射」标题下扫描表格，导致写法 B
    提取到 0 项，渲染器退回章节解析后大量字段丢失。

    判定标准只有一个：**表格首列是大写字段名**（NAME / W1R1 / SCH…），
    与所在章节标题无关。这样两种写法都能覆盖，且不会把普通表格误当字段表。
    """
    fields: Dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        if re.match(r"^\|[-: |]+\|$", stripped):        # 表头分隔行
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) < 2:
            continue
        key = _clean(cells[0])
        value = _clean(cells[1])
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
            continue                                     # 首列不是字段名
        if not value or value in ("值", "{值}"):
            continue                                     # 表头行
        if _is_placeholder(value):
            continue                                     # 「待补充」不写入
        fields[key] = value
    return fields


# ============================================================================
# L1：旁路字段文件
# ============================================================================

def load_fields_json(path: Path) -> Dict[str, str]:
    """读取 resume.fields.json。

    支持两种形态：
        {"NAME": "张三", "W1R1": "..."}
        {"fields": {...}, "notes": "..."}
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("fields"), dict):
        data = data["fields"]
    if not isinstance(data, dict):
        raise ValueError(f"{path} 必须是 JSON 对象")
    return {str(k): "" if v is None else str(v) for k, v in data.items()}


def save_fields_json(fields: Dict[str, str], path: Path, extra: Optional[dict] = None) -> None:
    payload: Dict[str, object] = {"fields": dict(fields)}
    if extra:
        payload.update(extra)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


# ============================================================================
# 主映射：ParsedResume -> 模板字段
# ============================================================================

def map_to_fields(
    parsed: ParsedResume,
    template_fields: List[str],
    report: Optional["MapReport"] = None,
) -> Tuple[Dict[str, str], List[str]]:
    """把解析结果映射到指定模板的字段集合。

    只产出模板真正需要的字段，避免 generate_notes 里塞满无用键。

    参数：
        report: 传入 MapReport 时，会记录「槽位不足导致哪些内容没进模板」等信息。

    返回 (字段值字典, 未映射上的模板字段列表)
    """
    rep = report if report is not None else MapReport()
    wanted = set(template_fields)
    values: Dict[str, str] = {}
    unmapped: List[str] = []

    # ---- 基本标量 ----
    scalar_source: Dict[str, str] = {}
    if parsed.name:
        scalar_source["NAME"] = parsed.name
    if parsed.obj:
        scalar_source["OBJ"] = parsed.obj
    if parsed.summary:
        # 自我评价按句切分为 SM / SM2，便于填入双段模板
        sentences = _split_sentences(parsed.summary)
        if sentences:
            scalar_source["SM"] = sentences[0]
            if len(sentences) > 1:
                scalar_source["SM2"] = "".join(sentences[1:])

    for key, value in parsed.education.items():
        if key in ("GPA", "RANK", "GRADUATION"):
            continue
        scalar_source[key] = value

    # 求职城市 / 学历 等来自 basic
    for canonical, aliases in SCALAR_ALIASES.items():
        if canonical in scalar_source:
            continue
        for alias in aliases:
            if alias in parsed.basic and parsed.basic[alias]:
                scalar_source[canonical] = parsed.basic[alias]
                break

    # 证书：过滤占位文本后再拼接
    certs = _filter_placeholders(parsed.certs)
    if certs:
        scalar_source["CERTS"] = "；".join(certs)
        for i, cert in enumerate(certs, start=1):
            scalar_source.setdefault(f"CER{i}", cert)
            scalar_source.setdefault(f"AW{i}", cert)

    # 技能槽位：按分类顺序展开
    skill_list: List[str] = []
    for _cat, items in parsed.skills.items():
        for item in _filter_placeholders(items):
            if item not in skill_list:
                skill_list.append(item)
    for i, skill in enumerate(skill_list, start=1):
        scalar_source.setdefault(f"SK{i}", skill)

    for key in ("EX1", "EX2", "EX3", "INT", "HT", "ETH", "POL", "ADDR", "BIR"):
        if key in parsed.basic and parsed.basic[key] and not _is_placeholder(parsed.basic[key]):
            scalar_source.setdefault(key, parsed.basic[key])

    # ---- 序列字段 ----
    for field in template_fields:
        if field in values:
            continue
        if field in scalar_source:
            values[field] = scalar_source[field]
            continue

        spec = _seq_field(field)
        if spec:
            source_key, index, suffix = spec
            records: List[Dict[str, object]] = getattr(parsed, source_key)
            if 1 <= index <= len(records):
                rec = records[index - 1]
                value = _extract_seq_value(rec, suffix)
                if value:
                    values[field] = value
                    continue

        # 未匹配上
        if field not in values:
            unmapped.append(field)

    # 对未映射字段再尝试一次别名表（模板可能用非标准命名）
    still_unmapped: List[str] = []
    for field in unmapped:
        matched = False
        for canonical, aliases in SCALAR_ALIASES.items():
            if field == canonical or field in aliases:
                if canonical in scalar_source:
                    values[field] = scalar_source[canonical]
                    matched = True
                    break
        if not matched:
            still_unmapped.append(field)

    _collect_slot_report(parsed, template_fields, rep)
    rep.unmapped_fields = list(still_unmapped)
    return values, still_unmapped


def _collect_slot_report(
    parsed: ParsedResume,
    template_fields: List[str],
    report: "MapReport",
) -> None:
    """统计「模板槽位 vs 实际内容量」，把被丢弃的条目显式记录下来。

    这是本工具最重要的诚实性保障之一：模板槽位固定（如只有 W1/W2），
    而用户简历库可能有 4 段实习。静默丢弃会让用户误以为都写进去了。
    """
    # 序列类：W / P / C 各自的最大槽位序号
    slot_max: Dict[str, int] = {}
    for field in template_fields:
        spec = _seq_field(field)
        if not spec:
            continue
        source_key, index, _suffix = spec
        slot_max[source_key] = max(slot_max.get(source_key, 0), index)

    labels = {
        "internships": "实习/工作经历",
        "projects": "项目经历",
        "campus": "校园经历",
    }
    for source_key, slots in slot_max.items():
        records = parsed.entries(source_key)
        report.slot_summary[labels.get(source_key, source_key)] = (
            f"模板 {slots} 个槽位 / resume.md 提供 {len(records)} 条"
        )
        for index in range(slots + 1, len(records) + 1):
            report.truncated.append(
                f"{labels.get(source_key, source_key)}：{parsed.describe_entry(source_key, index)}"
            )

    # 技能：模板 SK{n} 的槽位数
    skill_slots = max(
        (int(m.group(1)) for f in template_fields
         if (m := re.fullmatch(r"SK(\d+)", f))),
        default=0,
    )
    skill_total = len({
        item
        for items in parsed.skills.values()
        for item in _filter_placeholders(items)
    })
    if skill_slots:
        report.slot_summary["技能"] = f"模板 {skill_slots} 个槽位 / 提供 {skill_total} 项"
        if skill_total > skill_slots:
            report.truncated.append(f"技能：超出 {skill_total - skill_slots} 项未进入模板")

    # 证书：CER{n} / AW{n} 的槽位数
    cert_slots = max(
        (int(m.group(1)) for f in template_fields
         if (m := re.fullmatch(r"(?:CER|AW)(\d+)", f))),
        default=0,
    )
    cert_total = len(_filter_placeholders(parsed.certs))
    if cert_slots:
        report.slot_summary["证书奖项"] = f"模板 {cert_slots} 个槽位 / 提供 {cert_total} 项"
        if cert_total > cert_slots:
            report.truncated.append(f"证书奖项：超出 {cert_total - cert_slots} 项未进入模板")

    report.section_summary = {
        "实习/工作经历": len(parsed.internships),
        "项目经历": len(parsed.projects),
        "校园经历": len(parsed.campus),
        "技能项": skill_total,
        "证书奖项": cert_total,
        "技能分类": len(parsed.skills),
    }


def _extract_seq_value(rec: Dict[str, object], suffix: str) -> str:
    """从一条记录中取出模板字段需要的值。"""
    org = str(rec.get("org", "") or "")
    role = str(rec.get("role", "") or "")

    if suffix in ("C", "N"):
        # 组织位：若组织与角色完全相同（说明标题里只有职务、没有组织名），
        # 组织位留空，避免 N/P 两处填出同样的文字（简历上会显得重复）
        return "" if org and org == role else org

    if suffix == "P":
        # 角色位：同样避免与组织重复
        if role and role == org:
            return ""
        # 窄槽位容不下过长的角色串，超出时保留首个职务
        return _condense_role(role)

    if suffix == "D":
        return str(rec.get("period", "") or "")
    if suffix == "A":
        return str(rec.get("achievement", "") or "")

    # R / R1 / R2 … -> 描述行
    bullets = rec.get("bullets", []) or []
    if not isinstance(bullets, list):
        return ""
    match = re.fullmatch(r"R(\d*)", suffix)
    if not match:
        return ""
    number = match.group(1)
    if number:
        idx = int(number) - 1
        return str(bullets[idx]) if 0 <= idx < len(bullets) else ""
    return str(bullets[0]) if bullets else ""


def _split_sentences(text: str) -> List[str]:
    """按中文句号/分号/换行切句，用于 SM / SM2 双段填充。"""
    parts = re.split(r"(?<=[。！？；!?;])\s*", text)
    parts = [p.strip() for p in parts if p.strip()]
    if len(parts) <= 1:
        return parts
    half = max(1, len(parts) // 2)
    return ["".join(parts[:half]), "".join(parts[half:])] if len(parts) > 1 else parts


# ============================================================================
# 归档目录与生成说明
# ============================================================================

def find_resume_base(lib: Path, company: str, role: str) -> Path:
    """定位某个公司/岗位的归档目录。

    优先复用已有日期目录（避免同岗位重复生成时散落多个目录），
    没有则使用今天日期。
    """
    import datetime as _dt

    stem = lib / "09_岗位定制简历" / company / role
    if stem.is_dir():
        dates = sorted(
            (d for d in stem.iterdir() if d.is_dir() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", d.name)),
            reverse=True,
        )
        if dates:
            return dates[0]
    return stem / _dt.date.today().isoformat()


def generate_notes_md(
    *,
    company: Optional[str],
    role: Optional[str],
    jd_path: Optional[Path],
    template_name: str,
    template_style: str,
    resume_md: Optional[Path],
    fields_json: Optional[Path],
    photo: Optional[Path],
    source_note: str,
    values: Dict[str, str],
    template_fields: List[str],
    report: "MapReport",
    render_report: Dict[str, object],
    notes_path: Optional[Path],
    resume_sha256: Optional[str] = None,
) -> str:
    """自动生成 generation_notes.md（机器可验证的生成记录）。

    设计原则（重要）：
        本文件**只记录工具能观测到的事实**——用了哪个模板、映射了哪些字段、
        哪些内容因槽位不足被丢弃、哪些字段留空、有无超页风险。

        它**不编造**「为什么这样优化表达」这类属于 AI 判断的内容。
        那部分应由 AI 在生成 resume.md 时同步写下（见 agent_entry.md §5），
        或由 AI 追加到本文件末尾的「AI 优化说明」章节。

    这解决了两个真实问题：
        1. AGENT.md 要求产物目录必须有 generation_notes.md，但此前靠 AI 手写、经常漏；
        2. 以前无法回答「这次到底填进去了什么、丢了什么」，出问题只能靠猜。
    """
    import datetime as _dt

    lines: List[str] = []
    now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines.append(f"# 简历生成说明 — {company or '未指定公司'} / {role or '未指定岗位'}")
    lines.append("")
    lines.append("> 本文件由 `python gen.py render` **自动生成**，记录机器可验证的生成事实。")
    lines.append("> 其中「内容取舍逻辑」「表达优化说明」属于 AI 的判断，"
                 "应由 AI 在 `resume.md` 中说明或追加到本文末尾。")
    lines.append("")

    lines.append("## 一、基本信息")
    lines.append("")
    lines.append("| 项目 | 内容 |")
    lines.append("|---|---|")
    lines.append(f"| 目标公司 | {company or '（未提供）'} |")
    lines.append(f"| 目标岗位 | {role or '（未提供）'} |")
    lines.append(f"| 生成时间 | {now} |")
    lines.append(f"| 使用模板 | `{template_name}`（{template_style or '未标注风格'}） |")
    lines.append(f"| JD 原文 | `{jd_path.name}` |" if jd_path else "| JD 原文 | （未提供） |")
    lines.append(f"| 内容来源 | `{resume_md.name}` |" if resume_md else "| 内容来源 | — |")
    if fields_json:
        lines.append(f"| 字段覆盖 | `{fields_json.name}` |")
    lines.append(f"| 映射策略 | {source_note} |")
    if resume_sha256:
        lines.append(f"| 内容指纹 | `sha256:{resume_sha256[:16]}…` |")
    lines.append("")

    lines.append("## 二、模板槽位与内容量")
    lines.append("")
    if report.slot_summary:
        lines.append("| 类别 | 情况 |")
        lines.append("|---|---|")
        for key, value in report.slot_summary.items():
            lines.append(f"| {key} | {value} |")
    else:
        lines.append("本模板不含序列类槽位（实习/项目/校园/技能/证书）。")
    lines.append("")

    lines.append("## 三、未进入模板的内容（槽位不足）")
    lines.append("")
    if report.truncated:
        lines.append("> ⚠️ 以下内容**没有**出现在最终简历中。若其中包含与岗位高度相关的经历，")
        lines.append("> 请让 AI 重新排序 `resume.md`（最有价值的放最前），或改用槽位更多的模板。")
        lines.append("")
        for item in report.truncated:
            lines.append(f"- {item}")
    else:
        lines.append("无。所有内容都已放入模板。")
    lines.append("")

    lines.append("## 四、字段填充情况")
    lines.append("")
    lines.append(f"- 模板字段总数：{len(template_fields)}")
    lines.append(f"- 成功填充：{len(values)}")
    filled_report = render_report.get("filled") or {}
    if isinstance(filled_report, dict) and filled_report:
        replaced = sum(v for v in filled_report.values() if isinstance(v, int))
        lines.append(f"- 实际替换位置数：{replaced}"
                     "（同一字段在模板中出现多次时会替换多遍，如页眉+正文）")
    if report.supplemented:
        lines.append("")
        lines.append("### 由简历库事实层补齐的字段（`--supplement`）")
        lines.append("")
        lines.append("| 字段 | 值 |")
        lines.append("|---|---|")
        for key, value in report.supplemented.items():
            shown = value if len(value) <= 60 else value[:60] + "…"
            lines.append(f"| `{key}` | {shown} |")
    if report.unmapped_fields:
        lines.append("")
        lines.append("### 留空的模板字段")
        lines.append("")
        lines.append("以下字段在 `resume.md` 与简历库中都没有对应内容，保持空白"
                     "（**未编造**，符合 AGENT.md 事实优先原则）：")
        lines.append("")
        lines.append("```")
        lines.append(", ".join(report.unmapped_fields))
        lines.append("```")
    lines.append("")

    lines.append("## 五、版式与分页检查（工具自动记录）")
    lines.append("")
    marker_runs = render_report.get("marker_runs_removed") or 0
    lines.append(f"- 模板补高标记清理：{marker_runs} 个")
    photo_replaced = render_report.get("photo_replaced") or []
    lines.append(f"- 证件照替换：{', '.join(photo_replaced) if photo_replaced else '未替换'}"
                 + (f"（来源 `{photo.name}`）" if photo else ""))
    inline_ov = render_report.get("inline_overflow") or []
    if inline_ov:
        lines.append(f"- 窄槽位超出预留宽度：{len(inline_ov)} 个 —— "
                     + ", ".join(f"{n}({r}×)" for n, r in inline_ov[:8]))
    else:
        lines.append("- 窄槽位全部在模板预留宽度内")
    flow_ov = render_report.get("flow_overflow") or []
    if flow_ov:
        lines.append(f"- 流式文本较长（栏内自然换行，按规范不缩字号）：{len(flow_ov)} 个")
    shrunk = render_report.get("shrunk_fields") or {}
    if shrunk:
        lines.append(f"- 自动缩字号的字段（下限 8pt）：{shrunk}")
    overflow = render_report.get("overflow") or {}
    if overflow:
        lines.append(f"- 文字量估算：约 {overflow.get('approx_lines')} 行 / "
                     f"单页容量约 {overflow.get('capacity_lines')} 行 -> "
                     f"**{overflow.get('verdict')}**")
        lines.append("")
        lines.append("> 这是**文字量估算**，不是精确分页（本工具不启动 Word）。"
                     "请务必打开文档目视确认页码。")
    lines.append("")

    lines.append("## 六、AI 优化说明（待 AI 补充）")
    lines.append("")
    lines.append("以下内容属于 AI 的判断，工具无法自动生成，请由 AI 按下表补充：")
    lines.append("")
    lines.append("| 项目 | 说明 |")
    lines.append("|---|---|")
    lines.append("| 相对 JD 的经历排序依据 | 待补充 |")
    lines.append("| 弱化 / 删除的内容及原因 | 待补充 |")
    lines.append("| 表达层优化（STAR/PAR）要点 | 待补充 |")
    lines.append("| 未覆盖的 Gap 及诚实处理方式 | 待补充 |")
    lines.append("")
    lines.append("## 七、真实性自检（AI 须逐项确认）")
    lines.append("")
    lines.append("| 检查项 | 结果 |")
    lines.append("|---|---|")
    lines.append("| Level 1 事实层未被改写（时间/公司/学校/职位/数字） | 待确认 |")
    lines.append("| 未虚构经历、数据、证书、技能程度 | 待确认 |")
    lines.append("| 岗位定制内容全部来源于真实经历 | 待确认 |")
    lines.append("| 缺失信息已标记「待补充」而非编造 | 待确认 |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("> 本文件由 Resume-Agent `gen.py render` 生成；"
                 "「六、七」两节需 AI 填写后视为完整。")

    content = "\n".join(lines) + "\n"

    if notes_path is not None:
        notes_path.parent.mkdir(parents=True, exist_ok=True)
        existing = notes_path.read_text(encoding="utf-8") if notes_path.exists() else None
        if existing and "## 六、AI 优化说明" in existing and "待补充 |" not in existing.split("## 六")[-1][:400]:
            # 已有人工/AI 写过的优化说明 -> 不覆盖，另存为 .auto.md
            notes_path = notes_path.with_name(notes_path.stem + ".auto" + notes_path.suffix)
        notes_path.write_text(content, encoding="utf-8")

    return content


def sha256_of_file(path: Optional[Path]) -> Optional[str]:
    """计算文件 sha256（用于记录内容指纹，便于追溯同一次生成）。"""
    if path is None or not path.exists():
        return None
    import hashlib

    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ============================================================================
# 统一入口
# ============================================================================

def build_fields(
    resume_md: Optional[Path],
    template_fields: List[str],
    fields_json: Optional[Path] = None,
    library_data: Optional[Dict[str, object]] = None,
    report: Optional["MapReport"] = None,
) -> Tuple[Dict[str, str], List[str], str, Optional[ParsedResume]]:
    """生成模板字段值。

    返回 (字段值, 未映射字段, 使用的策略说明, 解析结果)
    诊断信息写入传入的 report（MapReport）。
    """
    rep = report if report is not None else MapReport()
    values: Dict[str, str] = {}
    source_note = ""
    supplemented: Dict[str, str] = {}

    # L1
    if fields_json is not None:
        if not fields_json.exists():
            raise FileNotFoundError(f"字段文件不存在：{fields_json}")
        values.update({k: v for k, v in load_fields_json(fields_json).items()})
        source_note = f"L1 旁路字段文件：{fields_json.name}"

    parsed: Optional[ParsedResume] = None
    if resume_md is not None:
        if not resume_md.exists():
            raise FileNotFoundError(f"resume.md 不存在：{resume_md}")
        text = resume_md.read_text(encoding="utf-8")

        # L2：内嵌字段表（优先级高于章节解析）
        inline = extract_inline_fields(text)
        if inline:
            for k, v in inline.items():
                values.setdefault(k, v)
            source_note = (source_note + " + " if source_note else "") + \
                f"L2 内嵌字段表（{len(inline)} 项）"

        # L3：章节结构解析 —— 始终执行，作为 L1/L2 的**补漏**而非替代。
        #
        # 曾经的缺陷：写成 `if not values:`，即「有内联表就不解析章节」。
        # 但内联表往往只写了部分字段（如只写个人信息 + 教育），
        # 剩下 17 个字段就白白空着。两者是互补关系，不是二选一。
        parsed = parse_resume_md(text)
        mapped, _ = map_to_fields(parsed, template_fields, rep)
        added = 0
        for k, v in mapped.items():
            if k not in values:
                values[k] = v
                added += 1
        if mapped:
            source_note = (source_note + " + " if source_note else "") + \
                f"L3 章节解析补漏（{added} 项）"

    if not values:
        raise ValueError(
            "没有解析出任何字段值。请确认：\n"
            "  1) 存在 resume.md 或 resume.fields.json；\n"
            "  2) resume.md 使用标准章节标题（## 教育经历 / ## 实习经历 …）；\n"
            "  3) 或直接在 resume.md 中加入「## 模板字段」表格。"
        )

    # 只保留模板需要的字段（多余键会让报告噪音很大），
    # 但必须**报告**被丢弃的键 —— 否则内容层写了字段、模板却没有对应位置，
    # 用户会以为已经写进去了（真实案例：resume.md 声明 SK1/SK2/SK3，
    # 而 template_02 根本没有技能字段，三个技能被静默丢弃）。
    allowed = set(template_fields)
    unknown = sorted(k for k in values if k not in allowed)
    rep.unknown_fields = unknown
    # 同时留存这些键的原值：调用方过滤后拿不到它们，报告里需要显示
    # 「到底丢了什么内容」才有意义
    rep.unknown_values = {k: values[k] for k in unknown}

    filtered = {k: v for k, v in values.items() if k in allowed}

    # ---- 可选：用简历库补齐 resume.md 没写到的标量字段 ----
    supplemented: Dict[str, str] = {}
    if library_data:
        filtered, supplemented = supplement_from_library(filtered, template_fields, library_data)
        rep.supplemented = dict(supplemented)
        if supplemented:
            source_note += f" + 简历库补齐 {len(supplemented)} 项"
        # 补齐发生在初次槽位统计之后，需按补齐结果刷新统计，
        # 否则报告会显示「证书提供 0 项」而实际已填入 3 项（自相矛盾）。
        if supplemented:
            _refresh_slot_summary_for_certs(parsed, template_fields, filtered, rep)

    unmapped = [f for f in template_fields if f not in filtered]
    rep.unmapped_fields = list(unmapped)
    return filtered, unmapped, source_note, parsed


def _refresh_slot_summary_for_certs(
    parsed: Optional[ParsedResume],
    template_fields: List[str],
    final_values: Dict[str, str],
    report: "MapReport",
) -> None:
    """按补齐后的最终值刷新「证书奖项」槽位统计。"""
    cert_slots = max(
        (int(m.group(1)) for f in template_fields
         if (m := re.fullmatch(r"(?:CER|AW)(\d+)", f))),
        default=0,
    )
    if not cert_slots:
        return
    if parsed is not None:
        report.truncated = [
            item for item in report.truncated if not item.startswith("证书奖项：")
        ]
    filled_certs = sum(
        1 for i in range(1, cert_slots + 1) if final_values.get(f"CER{i}")
    )
    report.slot_summary["证书奖项"] = (
        f"模板 {cert_slots} 个槽位 / 最终填入 {filled_certs} 项"
    )


# ============================================================================
# 简历库补齐（可选，必须显式开启）
# ============================================================================

def supplement_from_library(
    current: Dict[str, str],
    template_fields: List[str],
    library_data: Dict[str, object],
) -> Tuple[Dict[str, str], Dict[str, str]]:
    """用简历库事实层补齐 resume.md 没写到的**标量**字段。

    安全边界（重要）：
        - 只补「客观身份信息」与「证书」这类不可能被 AI 优化改写的字段；
        - 绝不补经历描述（实习/项目/校园的 R 行），那些必须由 AI 依 JD 定制；
        - 已存在的值不覆盖（resume.md 优先）；
        - 返回补齐明细，供 CLI 打印，杜绝「静默往简历里塞事实」。

    这解决了真实痛点：证书奖项目录里有 CET-4、驾驶证，但 resume.md 往往
    只写与岗位相关的部分，导致渲染出来这三个槽位空着。
    """
    out = dict(current)
    added: Dict[str, str] = {}
    wanted = set(template_fields)

    personal = library_data.get("personal") or {}
    if isinstance(personal, dict):
        mapping = {
            "NAME": personal.get("name"),
            "TEL": personal.get("phone"),
            "EML": personal.get("email"),
            "CITY": personal.get("location") or personal.get("job_cities"),
            "ADDR": personal.get("location"),
            "BIR": personal.get("birth"),
            "ETH": personal.get("ethnicity"),
            "POL": personal.get("political_status"),
        }
        for field, value in mapping.items():
            if field in wanted and field not in out and value:
                text = str(value).strip()
                if text and not _is_placeholder(text):
                    out[field] = text
                    added[field] = text

    certs = library_data.get("certificates") or []
    if isinstance(certs, list) and certs:
        names: List[str] = []
        for item in certs:
            if isinstance(item, dict):
                name = str(item.get("name", "")).strip()
            else:
                name = str(item).strip()
            if name and not _is_placeholder(name) and name not in names:
                names.append(name)
        if names:
            if "CERTS" in wanted and "CERTS" not in out:
                out["CERTS"] = "；".join(names)
                added["CERTS"] = out["CERTS"]
            for i, name in enumerate(names[:6], start=1):
                for prefix in ("CER", "AW"):
                    field = f"{prefix}{i}"
                    if field in wanted and field not in out:
                        out[field] = name
                        added[field] = name

    # 求职意向（客观部分）
    intent = library_data.get("job_intent") or {}
    if isinstance(intent, dict) and "OBJ" in wanted and "OBJ" not in out:
        directions = intent.get("directions") or []
        if isinstance(directions, list) and directions:
            first = directions[0]
            if isinstance(first, dict) and first.get("direction"):
                out["OBJ"] = str(first["direction"])
                added["OBJ"] = out["OBJ"]

    return out, added
