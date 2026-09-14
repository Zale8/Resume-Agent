# -*- coding: utf-8 -*-
"""data_loader.py — 从简历库只读解析个人信息的通用加载器。

红线：
- 本文件不含任何用户真实个人信息。
- 所有数据通过参数传入的简历库路径读取。
- 只读不改，绝不写入或修改简历库内任何文件。
- 解析失败的字段返回 None 或空列表，由调用方决定如何处理。

用法：
    from resume_generator.data_loader import load_personal_data
    data = load_personal_data(Path("../简历库"))
    name = data["personal"]["name"]   # 来自 00_个人信息/个人信息.md
    school = data["education"][0]["school"]  # 来自 01_教育经历/*.md
"""
from __future__ import annotations

from pathlib import Path
import re
from typing import Optional


def _parse_md_table(lines: list[str]) -> dict:
    """解析 markdown 表格 | 字段 | 内容 | 为 {字段: 内容} 字典。
    跳过表头分隔行（|---|---|）。"""
    result = {}
    for line in lines:
        line = line.strip()
        if not line.startswith("|"):
            continue
        if re.match(r"^\|[-: |]+\|$", line):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) >= 2:
            key = cells[0].strip()
            value = cells[1].strip()
            if key and key != "字段":
                result[key] = value
    return result


def _read_md(path: Path) -> list[str]:
    """读取 md 文件，返回行列表（跳过 > 开头的引用行）。"""
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    return text.splitlines()


def _parse_section(lines: list[str], section_title: str) -> list[str]:
    """提取 ## 指定章节的行（到下一个 ## 或文件末尾）。"""
    in_section = False
    collected = []
    for line in lines:
        if line.strip().startswith("## "):
            if section_title in line:
                in_section = True
                continue
            elif in_section:
                break
        elif in_section:
            collected.append(line)
    return collected


def _parse_bullet_list(lines: list[str]) -> list[str]:
    """从行列表中提取 - 开头的列表项。"""
    items = []
    for line in lines:
        line = line.strip()
        if line.startswith("- "):
            items.append(line[2:].strip())
        elif re.match(r"^\d+\.\s", line):
            items.append(re.sub(r"^\d+\.\s", "", line).strip())
    return items


def _parse_blockquote(lines: list[str]) -> str:
    """从行列表中提取 > 开头的引用文本，拼接为一段。"""
    texts = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(">"):
            text = stripped.lstrip(">").strip()
            if text:
                texts.append(text)
    return " ".join(texts) if texts else None


def _parse_section_lines(lines: list[str], section_title: str) -> list[str]:
    """提取 ## 指定章节的原始行（含引用行），到下一个 ## 或文件末尾。"""
    in_section = False
    collected = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            if section_title in stripped:
                in_section = True
                continue
            elif in_section:
                break
        elif in_section:
            collected.append(line)
    return collected


def _parse_level3_sections(lines: list[str]) -> dict:
    """解析 ## 岗位定制层 下的 ### 方向子章节。
    返回 {方向标题: [bullet 描述]}。"""
    result = {}
    in_level3 = False
    current_direction = None
    current_bullets = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            if "岗位定制层" in stripped or "岗位定制版本" in stripped:
                in_level3 = True
            elif in_level3:
                if current_direction:
                    result[current_direction] = current_bullets
                in_level3 = False
            continue
        if not in_level3:
            continue
        if stripped.startswith("### "):
            if current_direction:
                result[current_direction] = current_bullets
            current_direction = stripped[4:].strip()
            current_bullets = []
        elif stripped.startswith("- "):
            current_bullets.append(stripped[2:].strip())
        elif re.match(r"^\d+\.\s", stripped):
            current_bullets.append(re.sub(r"^\d+\.\s", "", stripped).strip())
    if current_direction:
        result[current_direction] = current_bullets
    return result


def load_personal_data(resume_lib_dir) -> dict:
    """从简历库只读解析所有个人信息。

    参数：
        resume_lib_dir: 简历库根目录 Path（如 Path("../简历库")）

    返回结构：
        {
            "personal": {name, phone, email, wechat, location, job_cities, photo},
            "education": [{school, department, major, degree, start, end, gpa, courses}],
            "internships": [{company, role, period, industry, direction,
                            level1_facts, level2_expressions, level3_versions}],
            "projects": [{name, type, period, role, results, level3_versions}],
            "skills": {category: {tools, proficiency}},
            "campus": [{role, period, description}],
            "certificates": [{category, name, remark, source_file}],
            "job_intent": {identity, arrival, cities, directions, source_file},
        }
    """
    lib = Path(resume_lib_dir)
    data = {
        "personal": {},
        "education": [],
        "internships": [],
        "projects": [],
        "skills": {},
        "campus": [],
        "certificates": [],
        "job_intent": {},
        "self_evaluation": {},
    }

    # ===== 00_个人信息 =====
    personal_dir = lib / "00_个人信息"
    personal_file = personal_dir / "个人信息.md"
    if personal_file.exists():
        lines = _read_md(personal_file)
        # 合并所有表格字段
        fields = _parse_md_table(lines)
        data["personal"]["name"] = fields.get("姓名")
        data["personal"]["phone"] = fields.get("手机号")
        data["personal"]["email"] = fields.get("邮箱")
        data["personal"]["wechat"] = fields.get("微信")
        data["personal"]["location"] = fields.get("所在城市")
        data["personal"]["job_cities"] = fields.get("求职城市")
        data["personal"]["birth"] = fields.get("出生年月")
        data["personal"]["ethnicity"] = fields.get("民族")
        data["personal"]["political_status"] = fields.get("政治面貌")
        data["personal"]["graduation_year"] = fields.get("届别")
        # 照片
        photo_dir = personal_dir / "photos"
        photos = (
            list(photo_dir.glob("*.jpg"))
            + list(photo_dir.glob("*.jpeg"))
            + list(photo_dir.glob("*.png"))
        ) if photo_dir.exists() else []
        data["personal"]["photo"] = str(photos[0]) if photos else None

    # ===== 01_教育经历 =====
    edu_dir = lib / "01_教育经历"
    if edu_dir.exists():
        for md_file in sorted(edu_dir.glob("*.md")):
            lines = _read_md(md_file)
            fields = _parse_md_table(lines)
            courses_section = _parse_section(lines, "主修课程")
            courses_text = "、".join(
                line.strip() for line in courses_section
                if line.strip() and not line.strip().startswith("#") and not line.strip().startswith(">")
            ).strip()
            data["education"].append({
                "school": fields.get("学校"),
                "department": fields.get("院系"),
                "major": fields.get("专业"),
                "degree": fields.get("学历"),
                "start": fields.get("入学时间"),
                "end": fields.get("毕业时间"),
                "gpa": fields.get("GPA"),
                "ranking": fields.get("排名"),
                "courses": courses_text or None,
            })

    # ===== 02_实习经历 =====
    exp_dir = lib / "02_实习经历"
    if exp_dir.exists():
        for md_file in sorted(exp_dir.glob("*.md")):
            lines = _read_md(md_file)
            fields = _parse_md_table(lines)
            level1 = _parse_bullet_list(_parse_section(lines, "原始事实"))
            level2 = _parse_bullet_list(_parse_section(lines, "专业表达层"))
            level3 = _parse_level3_sections(lines)
            data["internships"].append({
                "company": fields.get("公司"),
                "role": fields.get("岗位"),
                "period": fields.get("起止时间"),
                "industry": fields.get("行业"),
                "direction": fields.get("业务方向"),
                "level1_facts": level1,
                "level2_expressions": level2,
                "level3_versions": level3,
                "source_file": md_file.name,
            })

    # ===== 03_项目经历 =====
    proj_dir = lib / "03_项目经历"
    if proj_dir.exists():
        for md_file in sorted(proj_dir.glob("*.md")):
            lines = _read_md(md_file)
            fields = _parse_md_table(lines)
            # 项目结果表格
            results_section = _parse_section(lines, "项目结果")
            results = _parse_md_table(results_section)
            level3 = _parse_level3_sections(lines)
            data["projects"].append({
                "name": fields.get("项目名称") or fields.get("项目类型") or md_file.stem,
                "type": fields.get("项目类型"),
                "period": fields.get("项目时间"),
                "role": fields.get("我的角色"),
                "status": fields.get("项目状态"),
                "results": results,
                "level3_versions": level3,
                "source_file": md_file.name,
            })

    # ===== 04_校园经历 =====
    campus_dir = lib / "04_校园经历"
    if campus_dir.exists():
        for md_file in sorted(campus_dir.glob("*.md")):
            lines = _read_md(md_file)
            # 标题取文件 H1（如「# 校园经历 - 班级体育委员 / 文体活动组织」）
            title = None
            for line in lines:
                if line.strip().startswith("# "):
                    title = line.strip()[2:].strip()
                    break
            # 职务类校园经历从 Level 1「职务：」提取角色
            level1_bullets = _parse_bullet_list(_parse_section(lines, "原始事实"))
            role = None
            for b in level1_bullets:
                if b.startswith("职务："):
                    role = b.replace("职务：", "").strip()
                    break
            # 校园经历取 Level 2 专业表达层
            level2_bullets = _parse_bullet_list(_parse_section(lines, "专业表达层"))
            data["campus"].append({
                "title": title,
                "role": role,
                "level2_expressions": level2_bullets,
                "source_file": md_file.name,
            })

    # ===== 05_专业技能 =====
    skill_dir = lib / "05_专业技能"
    if skill_dir.exists():
        for md_file in sorted(skill_dir.glob("*.md")):
            lines = _read_md(md_file)
            category = md_file.stem
            tools_section = _parse_section(lines, "工具")
            tools = _parse_bullet_list(tools_section)
            proficiency = _parse_md_table(lines)
            data["skills"][category] = {
                "tools": tools,
                "proficiency": proficiency,
                "source_file": md_file.name,
            }

    # ===== 07_个人优势 =====
    eval_dir = lib / "07_个人优势"
    if eval_dir.exists():
        for md_file in sorted(eval_dir.glob("*.md")):
            lines = _read_md(md_file)
            # 原始自我评价（blockquote）
            eval_section = _parse_section(lines, "原始自我评价")
            data["self_evaluation"]["original"] = _parse_blockquote(eval_section)
            # 个人简介（blockquote）
            intro_section = _parse_section(lines, "个人简介")
            data["self_evaluation"]["summary"] = _parse_blockquote(intro_section)
            # 有事实支撑的优势（表格）
            adv_section = _parse_section(lines, "有事实支撑")
            data["self_evaluation"]["advantages"] = _parse_md_table(adv_section)
            data["self_evaluation"]["source_file"] = md_file.name

    # ===== 08_证书奖项 =====
    cert_dir = lib / "08_证书奖项"
    if cert_dir.exists():
        for md_file in sorted(cert_dir.glob("*.md")):
            lines = _read_md(md_file)
            in_table = False
            for line in lines:
                stripped = line.strip()
                if not stripped.startswith("|"):
                    continue
                if re.match(r"^\|[-: |]+\|$", stripped):
                    in_table = True
                    continue
                if stripped.startswith("| 类别") or stripped.startswith("|类别"):
                    in_table = True
                    continue
                if not in_table:
                    continue
                cells = [c.strip() for c in stripped.strip("|").split("|")]
                if len(cells) >= 2:
                    cat = cells[0].strip()
                    name = cells[1].strip()
                    remark = cells[2].strip() if len(cells) >= 3 else ""
                    if name and name != "待补充":
                        data["certificates"].append({
                            "category": cat,
                            "name": name,
                            "remark": remark,
                            "source_file": md_file.name,
                        })

    # ===== 06_求职意向 =====
    intent_dir = lib / "06_求职意向"
    if intent_dir.exists():
        for md_file in sorted(intent_dir.glob("*.md")):
            lines = _read_md(md_file)
            fields = _parse_md_table(lines)
            data["job_intent"]["identity"] = fields.get("求职身份")
            data["job_intent"]["arrival"] = fields.get("到岗时间")
            data["job_intent"]["source_file"] = md_file.name
            # 目标城市（从列表项提取）
            city_section = _parse_section(lines, "目标城市")
            cities = _parse_bullet_list(city_section)
            data["job_intent"]["cities"] = cities
            # 求职方向（从方向表格提取）
            direction_items = []
            in_direction_table = False
            for line in lines:
                stripped = line.strip()
                if "求职方向" in stripped and stripped.startswith("##"):
                    in_direction_table = True
                    continue
                if in_direction_table and stripped.startswith("##"):
                    break
                if in_direction_table and stripped.startswith("|"):
                    if re.match(r"^\|[-: |]+\|$", stripped):
                        continue
                    if stripped.startswith("| #") or stripped.startswith("|#"):
                        continue
                    cells = [c.strip() for c in stripped.strip("|").split("|")]
                    if len(cells) >= 3:
                        direction = cells[1].strip()
                        dtype = cells[2].strip()
                        if direction and direction != "方向":
                            direction_items.append({
                                "direction": direction,
                                "type": dtype,
                            })
            data["job_intent"]["directions"] = direction_items

    return data


def get_resume_text_field(data: dict, field_path: str) -> Optional[str]:
    """便捷函数：从 data 中按点号路径取值。
    如 get_resume_text_field(data, "personal.name") """
    keys = field_path.split(".")
    current = data
    for k in keys:
        if isinstance(current, dict) and k in current:
            current = current[k]
        elif isinstance(current, list) and k.isdigit() and int(k) < len(current):
            current = current[int(k)]
        else:
            return None
    return current if isinstance(current, str) else None
