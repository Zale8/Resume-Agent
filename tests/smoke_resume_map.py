# -*- coding: utf-8 -*-
"""冒烟测试：resume_map 的解析与映射逻辑。

这些是**启发式**规则（从自然语言简历里抽字段），非常容易在后续改动中悄悄退化。
本测试把每条已修复的缺陷固化为断言，防止复发。

不依赖 pytest，直接 python 运行。
本文件不含任何用户个人信息（全部使用虚构数据）。
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "src"))

from resume_generator import resume_map as rm  # noqa: E402

FAILURES: list[str] = []


def check(label: str, actual: object, expected: object) -> None:
    if actual == expected:
        print(f"  ✅ {label}")
    else:
        print(f"  ❌ {label}\n      期望: {expected!r}\n      实际: {actual!r}")
        FAILURES.append(label)


# ============================================================================
# 1. 组织 / 角色拆分（曾出过错的地方）
# ============================================================================

def test_split_role_from_org() -> None:
    print("\n### 1. 组织 / 角色拆分")
    cases = [
        # 核心回归：分隔符两侧**都含职务词**时，曾把两段都判为角色
        ("校园学生会部长 / 自律会主席", ("校园学生会", "部长 / 自律会主席")),
        # 常见「组织 | 角色」
        ("校学生会 | 部长", ("校学生会", "部长")),
        ("某公司 | 制造工程实习生", ("某公司", "制造工程实习生")),
        # 无分隔符，从尾部锚定
        ("学生会主席", ("学生会", "主席")),
        ("某协会负责人", ("某协会", "负责人")),
        # 整串都是职务、没有组织名 -> 组织位留空（避免与角色位重复）
        ("班长 / 团支书", ("", "班长 / 团支书")),
        # 空输入
        ("", ("", "")),
    ]
    for text, expected in cases:
        check(f"{text!r}", rm._split_role_from_org(text), expected)


# ============================================================================
# 2. 窄槽位角色压缩
# ============================================================================

def test_condense_role() -> None:
    print("\n### 2. 窄槽位角色压缩")
    cases = [
        # 并列职务 -> 只留第一个
        ("部长 / 自律会主席", "部长"),
        ("主席 / 部长", "主席"),
        # 短串保持原样
        ("部长", "部长"),
        ("制造工程实习生", "制造工程实习生"),
        # 长串且无分隔符 -> 剥掉组织前缀只留职务
        ("校园学生会部长", "部长"),
        ("".join(["很长的组织名称"] * 4) + "主席", "主席"),
        # 空
        ("", ""),
    ]
    for text, expected in cases:
        check(f"{text!r}", rm._condense_role(text), expected)


# ============================================================================
# 3. 占位文本过滤（「待补充」绝不能进简历）
# ============================================================================

def test_placeholder_filtering() -> None:
    print("\n### 3. 占位文本过滤")
    for text in ["待补充", "待确认", "待用户确认", "无", "N/A", "-", "/", "  ", ""]:
        check(f"_is_placeholder({text!r})", rm._is_placeholder(text), True)
    for text in ["CET-4", "普通话二级乙等", "本科"]:
        check(f"_is_placeholder({text!r})", rm._is_placeholder(text), False)


def test_inline_fields_any_section() -> None:
    """内联字段表可能分散在各章节下，不只在「## 模板字段」里。

    真实案例：一份 resume.md 把字段表写在
        ## 个人信息 / | NAME | 张三 |
        ## 教育经历 / | SCH | 某大学 |
    旧实现只在「模板字段 / 字段映射」标题下扫描，提取到 0 项，
    渲染器退回章节解析后大量字段丢失（30/32 掉到 15/32）。
    """
    print("\n### 3b. 内联字段表跨章节提取")
    text = """# 简历内容：张三 → 某公司 - 产品经理

> 生成日期：2026-01-01

## 个人信息

| 字段 | 值 |
|------|-----|
| NAME | 张三 |
| TEL | 13900000001 |
| HT | 待补充 |

## 教育经历

| 字段 | 值 |
|------|-----|
| SCH | 某大学 |
| MAJ | 软件工程 |

## 技能

| 字段 | 值 | 说明 |
|------|-----|------|
| SK1 | Python | JD 要求 |
| SK2 | SQL | JD 加分 |
"""
    fields = rm.extract_inline_fields(text)
    check("跨章节提取 NAME", fields.get("NAME"), "张三")
    check("跨章节提取 TEL", fields.get("TEL"), "13900000001")
    check("跨章节提取 SCH", fields.get("SCH"), "某大学")
    check("跨章节提取 SK1", fields.get("SK1"), "Python")
    check("三列表格取第二列", fields.get("SK2"), "SQL")
    check("「待补充」不写入", "HT" in fields, False)
    check("字段总数", len(fields), 6)

    # 普通表格（首列不是大写字段名）不应被误当字段表
    plain = """## 某章节

| 项目 | 说明 |
|---|---|
| 姓名 | 张三 |
| 电话 | 139 |
"""
    check("普通表格不误判", rm.extract_inline_fields(plain), {})


def test_title_name_parsing() -> None:
    """H1 可能是文档标题而非「姓名 - 岗位」，不能把整串当姓名。

    真实案例：H1 为「简历内容：<某人> → 某公司 - 岗位」时，
    旧实现把整串当姓名，产出文件名叫
    「简历内容：<某人> → 某公司 - 岗位_某公司_岗位.docx」。
    """
    print("\n### 3c. H1 姓名解析")
    cases = [
        ("张三 - 产品经理", ("张三", "产品经理")),
        ("张三 | 后端开发工程师", ("张三", "后端开发工程师")),
        ("简历内容：李四 → 某公司 - AI 运营实习生", ("李四", "某公司 - AI 运营实习生")),
        ("个人简历 王五", ("王五", None)),
        ("李示例 - 后端开发工程师", ("李示例", "后端开发工程师")),
    ]
    for title, expected in cases:
        check(f"_split_title({title!r})", rm._split_title(title), expected)

    # 纯文档标题（无姓名）不应编造姓名
    name, _ = rm._split_title("个人简历")
    check("无姓名时返回 None", name, None)

    # 端到端：解析整份文档，姓名必须正确
    p = rm.parse_resume_md(SAMPLE)
    check("SAMPLE 姓名", p.name, "张三")


# ============================================================================
# 4. 章节结构解析
# ============================================================================

SAMPLE = """# 张三 - 产品经理（实习）

**某虚构大学 | 电气工程及其自动化 | 2027届**

**求职意向**：产品经理（实习）

> 具备电气工程背景与产品项目落地经验，主导校园配送项目从 0 到 1。

---

## 教育经历

**某虚构大学 | 电气工程及其自动化（本科） | 2023.09 - 2027.06**

- 主修课程：自动控制原理、电力电子技术
- GPA：3.65/4.0

---

## 实习经历

### 某科技公司 | 硬件测试实习生 | 2023.12 - 2024.03

> 智能物联行业

- 参与安防硬件产品生产测试
- 负责 PCBA 外观及焊点质量检查

### 某汽车公司 | 制造工程实习生 | 2026.07 - 2026.09

- 参与自动化产线设备巡检

### 某餐饮公司 | 服务管理实习生 | 2025.01 - 2025.03

- 负责门店排班

### 某物流公司 | 仓储运营实习生 | 2025.06 - 2025.08

- 负责库存盘点

---

## 校园经历

### 校园学生会部长 / 自律会主席

- 统筹部门日常管理与任务分配
- 策划并组织校园赛事

---

## 专业技能

**AI与大模型**：ChatGPT / Claude / DeepSeek

- 深度使用主流 LLM

---

## 证书奖项

| 类别 | 名称 | 备注 |
|---|---|---|
| 证书 | 大学英语四级（CET-4） | |
| 比赛 | 待补充 | |
| 奖学金 | 待补充 | |

---

## 自我评价

具备电气工程专业背景与项目落地经验。善于用户洞察与流程设计。
"""


def test_parse_sections() -> None:
    print("\n### 4. 章节结构解析")
    p = rm.parse_resume_md(SAMPLE)

    check("H1 -> NAME", p.name, "张三")
    check("H1 -> OBJ", p.obj, "产品经理（实习）")
    check("学校行 -> SCH", p.education.get("SCH"), "某虚构大学")
    check("学校行 -> MAJ", p.education.get("MAJ"), "电气工程及其自动化")
    check("学校行 -> DG", p.education.get("DG"), "本科")
    check("教育段落 -> EDD", p.education.get("EDD"), "2023.09 - 2027.06")
    check("课程行 -> CRS", p.education.get("CRS"), "自动控制原理、电力电子技术")
    check("实习条数", len(p.internships), 4)
    check("第 1 段实习公司", p.internships[0].get("org"), "某科技公司")
    check("第 1 段实习职位", p.internships[0].get("role"), "硬件测试实习生")
    check("第 1 段实习时间", p.internships[0].get("period"), "2023.12 - 2024.03")
    check("第 1 段实习描述数", len(p.internships[0].get("bullets") or []), 2)
    check("校园条数", len(p.campus), 1)
    check("校园组织", p.campus[0].get("org"), "校园学生会")
    check("校园角色", p.campus[0].get("role"), "部长 / 自律会主席")
    # 分类行里的工具应被切开且去空白
    check("技能分类", list(p.skills.keys()), ["AI与大模型", "其他技能"])
    check("技能项已去空白",
          p.skills["AI与大模型"], ["ChatGPT", "Claude", "DeepSeek"])
    check("证书过滤「待补充」", p.certs, ["大学英语四级（CET-4）"])
    check("自我评价非空", bool(p.summary), True)


# ============================================================================
# 5. 序列字段取值
# ============================================================================

def test_extract_seq_value() -> None:
    print("\n### 5. 序列字段取值")
    p = rm.parse_resume_md(SAMPLE)
    w1 = p.internships[0]

    check("W1C", rm._extract_seq_value(w1, "C"), "某科技公司")
    check("W1P", rm._extract_seq_value(w1, "P"), "硬件测试实习生")
    check("W1D", rm._extract_seq_value(w1, "D"), "2023.12 - 2024.03")
    check("W1R1", rm._extract_seq_value(w1, "R1"), "参与安防硬件产品生产测试")
    check("W1R2", rm._extract_seq_value(w1, "R2"),
          "负责 PCBA 外观及焊点质量检查")
    # 越界描述行返回空串而不是抛异常
    check("W1R9（越界）", rm._extract_seq_value(w1, "R9"), "")

    c1 = p.campus[0]
    # 校园：组织与角色不同时都填；角色被压缩到窄槽位可容纳
    check("C1N", rm._extract_seq_value(c1, "N"), "校园学生会")
    check("C1P（已压缩）", rm._extract_seq_value(c1, "P"), "部长")


# ============================================================================
# 6. 槽位不足 -> 内容被丢弃必须被报告
# ============================================================================

def test_slot_drop_reporting() -> None:
    print("\n### 6. 槽位不足报告")
    p = rm.parse_resume_md(SAMPLE)

    # template_02 风格：只有 2 段实习槽位、1 段校园、3 个证书槽位
    tpl_fields = [
        "NAME", "SCH", "MAJ", "DG", "EDD", "CRS", "SM",
        "W1D", "W1C", "W1P", "W1R1", "W1R2",
        "W2D", "W2C", "W2P", "W2R1", "W2R2",
        "C1N", "C1P", "C1R1", "C1R2",
        "CER1", "CER2", "CER3",
        "SK1", "SK2", "SK3",
    ]
    rep = rm.MapReport()
    values, unmapped = rm.map_to_fields(p, tpl_fields, rep)

    # 简历有 4 段实习，模板只有 2 个槽位 -> 必须有 2 条被报告
    # 另有 1 条技能超出 3 个 SK 槽位 -> 合计 3 条
    drops_by_section = {
        "实习/工作经历": [i for i in rep.truncated if i.startswith("实习/工作经历")],
        "技能": [i for i in rep.truncated if i.startswith("技能")],
    }
    check("实习丢弃条数", len(drops_by_section["实习/工作经历"]), 2)
    check("技能丢弃条数", len(drops_by_section["技能"]), 1)
    check("丢弃内容含第 3 段",
          any("某餐饮公司" in item for item in rep.truncated), True)
    check("丢弃内容含第 4 段",
          any("某物流公司" in item for item in rep.truncated), True)
    check("has_drops", rep.has_drops, True)
    check("槽位摘要含实习",
          "实习/工作经历" in rep.slot_summary, True)
    check("W2C 取第 2 段", values.get("W2C"), "某汽车公司")

    # 实习槽位足够、技能槽位也足够时不应报告丢弃
    big_fields = tpl_fields + [
        "W3D", "W3C", "W3P", "W3R1", "W4D", "W4C", "W4P", "W4R1",
        "SK4",
    ]
    rep2 = rm.MapReport()
    rm.map_to_fields(p, big_fields, rep2)
    check("槽位足够时无丢弃", rep2.truncated, [])


# ============================================================================
# 7. 三级降级策略
# ============================================================================

def test_build_fields_layers() -> None:
    print("\n### 7. 三级降级策略")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        resume = tmp / "resume.md"
        resume.write_text(SAMPLE, encoding="utf-8")
        tpl_fields = ["NAME", "SCH", "MAJ", "W1C", "W1P"]

        # L3：仅章节解析
        rep = rm.MapReport()
        values, _, note, parsed = rm.build_fields(resume, tpl_fields, report=rep)
        check("L3 策略标识", note.startswith("L3"), True)
        check("L3 姓名", values.get("NAME"), "张三")
        check("L3 公司", values.get("W1C"), "某科技公司")

        # L2：resume.md 内嵌字段表优先
        embedded = SAMPLE + """
## 模板字段

| 字段 | 值 |
|---|---|
| NAME | 李四 |
| W1C | 内嵌公司 |
"""
        resume2 = tmp / "resume2.md"
        resume2.write_text(embedded, encoding="utf-8")
        rep2 = rm.MapReport()
        values2, _, note2, _ = rm.build_fields(resume2, tpl_fields, report=rep2)
        check("L2 策略标识", "L2" in note2, True)
        check("L2 覆盖 NAME", values2.get("NAME"), "李四")
        check("L2 覆盖 W1C", values2.get("W1C"), "内嵌公司")

        # L1：旁路字段 JSON 优先级最高
        fj = tmp / "resume.fields.json"
        rm.save_fields_json({"NAME": "王五", "W1C": "JSON公司"}, fj)
        rep3 = rm.MapReport()
        values3, _, note3, _ = rm.build_fields(
            resume2, tpl_fields, fields_json=fj, report=rep3
        )
        check("L1 策略标识", note3.startswith("L1"), True)
        check("L1 优先级最高", values3.get("NAME"), "王五")


# ============================================================================
# 8. 生成说明
# ============================================================================

def test_generate_notes() -> None:
    print("\n### 8. 生成说明自动产出")
    p = rm.parse_resume_md(SAMPLE)
    tpl_fields = ["NAME", "W1C", "W1P", "W1R1", "W2C"]
    rep = rm.MapReport()
    values, unmapped = rm.map_to_fields(p, tpl_fields, rep)

    with tempfile.TemporaryDirectory() as td:
        notes = Path(td) / "generation_notes.md"
        content = rm.generate_notes_md(
            company="某公司",
            role="产品经理",
            jd_path=None,
            template_name="template_99",
            template_style="测试风格",
            resume_md=None,
            fields_json=None,
            photo=None,
            source_note="L3 测试",
            values=values,
            template_fields=tpl_fields,
            report=rep,
            render_report={"filled": {"NAME": 1}, "overflow": {
                "approx_lines": 20, "capacity_lines": 50, "verdict": "ok"}},
            notes_path=notes,
        )
        check("文件已写出", notes.exists(), True)
        check("含被丢弃内容章节", "未进入模板的内容" in content, True)
        check("含丢弃条目", "某餐饮公司" in content, True)
        check("含 AI 待补充章节", "AI 优化说明" in content, True)
        check("含真实性自检章节", "真实性自检" in content, True)


def main() -> int:
    print("=" * 68)
    print("resume_map 解析与映射回归测试")
    print("=" * 68)
    test_split_role_from_org()
    test_condense_role()
    test_placeholder_filtering()
    test_inline_fields_any_section()
    test_title_name_parsing()
    test_parse_sections()
    test_extract_seq_value()
    test_slot_drop_reporting()
    test_build_fields_layers()
    test_generate_notes()
    print("\n" + "=" * 68)
    if FAILURES:
        print(f"❌ {len(FAILURES)} 项未通过：")
        for f in FAILURES:
            print(f"   - {f}")
        return 1
    print("✅ 全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
