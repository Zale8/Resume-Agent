# -*- coding: utf-8 -*-
"""test_data_loader.py — data_loader.py 和 paths.py 的单元测试。

用虚构数据验证解析逻辑，不含任何真实个人信息。
用法：python -m pytest tests/test_data_loader.py -v
      或：python tests/test_data_loader.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

# 让 import 能找到 src/
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "fake_resume_lib"


class TestParseMdTable(unittest.TestCase):
    """测试 _parse_md_table 的各种输入。"""

    def test_normal_table(self):
        from resume_generator.data_loader import _parse_md_table
        lines = [
            "| 字段 | 内容 |",
            "|------|------|",
            "| 姓名 | 张三 |",
            "| 手机号 | 13800000000 |",
        ]
        result = _parse_md_table(lines)
        self.assertEqual(result["姓名"], "张三")
        self.assertEqual(result["手机号"], "13800000000")

    def test_empty_input(self):
        from resume_generator.data_loader import _parse_md_table
        self.assertEqual(_parse_md_table([]), {})

    def test_no_table_rows(self):
        from resume_generator.data_loader import _parse_md_table
        lines = ["# 标题", "普通文本", "- 列表项"]
        self.assertEqual(_parse_md_table(lines), {})

    def test_skips_header_label_row(self):
        from resume_generator.data_loader import _parse_md_table
        lines = [
            "| 字段 | 内容 |",
            "|------|------|",
            "| 姓名 | 张三 |",
        ]
        result = _parse_md_table(lines)
        self.assertNotIn("字段", result)
        self.assertEqual(result["姓名"], "张三")

    def test_extra_columns_uses_first_two(self):
        """三列表格只取前两列作为 key/value。"""
        from resume_generator.data_loader import _parse_md_table
        lines = ["| 类别 | 名称 | 备注 |", "|------|------|------|", "| 英语 | 四级 | 550分 |"]
        result = _parse_md_table(lines)
        # 表头行也被解析（key="类别", value="名称"），数据行 key="英语", value="四级"
        self.assertEqual(result["类别"], "名称")
        self.assertEqual(result["英语"], "四级")

    def test_malformed_row_missing_pipe(self):
        from resume_generator.data_loader import _parse_md_table
        lines = ["姓名 张三"]  # 缺少 |
        result = _parse_md_table(lines)
        self.assertEqual(result, {})

    # --- skip_header=True：表头按结构（分隔行紧邻上一行）识别 ---

    def test_skip_header_named_header(self):
        """表头名不固定为「字段」（如技能表）时精确跳过表头。"""
        from resume_generator.data_loader import _parse_md_table
        lines = [
            "| 技能 | 水平 |",
            "|---|---|",
            "| Python | L3 |",
        ]
        result = _parse_md_table(lines, skip_header=True)
        self.assertNotIn("技能", result)
        self.assertEqual(result, {"Python": "L3"})

    def test_skip_header_with_leading_blanks_and_separators(self):
        """表格前多个空行/分隔行/普通文本不应消费跳过，数据行不丢。"""
        from resume_generator.data_loader import _parse_md_table
        lines = [
            "",
            "前置说明文字",
            "",
            "|---|---|",
            "",
            "| 技能 | 水平 |",
            "|---|---|",
            "| Python | L3 |",
            "| Git | L2 |",
        ]
        result = _parse_md_table(lines, skip_header=True)
        self.assertEqual(result, {"Python": "L3", "Git": "L2"})

    def test_skip_header_when_header_key_is_field(self):
        """表头 key 恰为「字段」时跳过仍须落在表头，不误删首条数据。"""
        from resume_generator.data_loader import _parse_md_table
        lines = [
            "| 字段 | 内容 |",
            "|---|---|",
            "| 第一项 | 值A |",
            "| 第二项 | 值B |",
        ]
        result = _parse_md_table(lines, skip_header=True)
        self.assertEqual(result, {"第一项": "值A", "第二项": "值B"})

    def test_skip_header_multiple_tables(self):
        """传入整文件含多个表时，每个表的表头都被识别跳过。"""
        from resume_generator.data_loader import _parse_md_table
        lines = [
            "# 标题",
            "",
            "| 技能 | 水平 |",
            "|---|---|",
            "| Python | L3 |",
            "",
            "| 技能 | 水平 |",
            "|---|---|",
            "| Excel | L4 |",
        ]
        result = _parse_md_table(lines, skip_header=True)
        self.assertEqual(result, {"Python": "L3", "Excel": "L4"})


class TestParseSection(unittest.TestCase):
    """测试 _parse_section 的章节提取。"""

    def test_extract_section(self):
        from resume_generator.data_loader import _parse_section
        lines = [
            "# 标题",
            "## 原始事实",
            "- 事实1",
            "- 事实2",
            "## 其他章节",
            "- 其他内容",
        ]
        result = _parse_section(lines, "原始事实")
        self.assertEqual(result, ["- 事实1", "- 事实2"])

    def test_section_not_found(self):
        from resume_generator.data_loader import _parse_section
        lines = ["## 其他", "- 内容"]
        result = _parse_section(lines, "原始事实")
        self.assertEqual(result, [])

    def test_partial_title_match(self):
        """验证 '原始事实' 能匹配 '## 原始事实（Level 1）' 这样的标题。"""
        from resume_generator.data_loader import _parse_section
        lines = ["## 原始事实（Level 1）", "- 事实1"]
        result = _parse_section(lines, "原始事实")
        self.assertEqual(result, ["- 事实1"])


class TestParseBulletList(unittest.TestCase):

    def test_dash_items(self):
        from resume_generator.data_loader import _parse_bullet_list
        lines = ["- 项目1", "- 项目2", "不是列表"]
        result = _parse_bullet_list(lines)
        self.assertEqual(result, ["项目1", "项目2"])

    def test_numbered_items(self):
        from resume_generator.data_loader import _parse_bullet_list
        lines = ["1. 第一项", "2. 第二项"]
        result = _parse_bullet_list(lines)
        self.assertEqual(result, ["第一项", "第二项"])

    def test_mixed_items(self):
        from resume_generator.data_loader import _parse_bullet_list
        lines = ["- 破折号项", "1. 编号项", "普通文本"]
        result = _parse_bullet_list(lines)
        self.assertEqual(result, ["破折号项", "编号项"])


class TestLoadPersonalData(unittest.TestCase):
    """使用虚构简历库端到端测试 load_personal_data。"""

    @classmethod
    def setUpClass(cls):
        if not FIXTURES.exists():
            raise unittest.SkipTest("fixtures 不存在")
        from resume_generator.data_loader import load_personal_data
        cls.data = load_personal_data(FIXTURES)

    def test_personal_info(self):
        p = self.data["personal"]
        self.assertEqual(p["name"], "张三")
        self.assertEqual(p["phone"], "13800000000")
        self.assertEqual(p["email"], "zhangsan@example.com")
        self.assertEqual(p["wechat"], "zhangsan_wx")
        self.assertEqual(p["location"], "北京")
        self.assertEqual(p["job_cities"], "北京 / 上海")
        self.assertEqual(p["birth"], "2001.06")
        self.assertEqual(p["ethnicity"], "汉族")
        self.assertEqual(p["political_status"], "中共党员")
        self.assertEqual(p["graduation_year"], "2027届")
        self.assertIsNone(p["photo"], "无照片文件时应返回 None")

    def test_education(self):
        edu = self.data["education"]
        self.assertEqual(len(edu), 1)
        e = edu[0]
        self.assertEqual(e["school"], "某虚构大学")
        self.assertEqual(e["major"], "计算机科学与技术")
        self.assertEqual(e["degree"], "本科")
        self.assertEqual(e["gpa"], "3.6/4.0")
        self.assertIsNotNone(e["courses"])
        self.assertIn("数据结构与算法", e["courses"])

    def test_internships(self):
        interns = self.data["internships"]
        self.assertEqual(len(interns), 1)
        i = interns[0]
        self.assertEqual(i["company"], "某科技公司")
        self.assertEqual(i["role"], "产品实习生")
        self.assertEqual(i["period"], "2025.07-2025.09")
        self.assertIn("协助完成需求文档与验收", i["level1_facts"][0])
        self.assertIn("主导需求文档编写", i["level2_expressions"][0])
        self.assertIn("某科技公司 - AI产品运营", i["level3_versions"])

    def test_projects(self):
        projs = self.data["projects"]
        self.assertEqual(len(projs), 1)
        p = projs[0]
        self.assertEqual(p["name"], "校园信息服务")
        self.assertEqual(p["role"], "负责人")
        self.assertEqual(p["results"].get("日均订单"), "500+")

    def test_campus(self):
        campus = self.data["campus"]
        self.assertEqual(len(campus), 1)
        c = campus[0]
        self.assertEqual(c["role"], "班级体育委员")
        level2_text = " ".join(c["level2_expressions"])
        self.assertIn("统筹组织班级参加校级运动会", level2_text)

    def test_skills(self):
        skills = self.data["skills"]
        self.assertIn("技能", skills)
        self.assertIn("Python", skills["技能"]["tools"])

    def test_certificates(self):
        certs = self.data["certificates"]
        names = [c["name"] for c in certs]
        self.assertIn("大学英语四级", names)
        self.assertIn("大学英语六级", names)
        self.assertIn("校级编程大赛二等奖", names)

    def test_job_intent(self):
        intent = self.data["job_intent"]
        self.assertEqual(intent["identity"], "2027届应届生")
        self.assertEqual(intent["arrival"], "2026.07")
        self.assertIn("北京", intent["cities"])
        self.assertEqual(len(intent["directions"]), 2)
        self.assertEqual(intent["directions"][0]["direction"], "产品经理")

    def test_self_evaluation(self):
        se = self.data["self_evaluation"]
        self.assertIn("学习能力强", se["original"])
        self.assertIn("某虚构大学", se["summary"])
        self.assertIn("数据驱动", se["advantages"])


class TestPaths(unittest.TestCase):
    """测试 paths.py 的路径发现逻辑。"""

    def test_looks_like_resume_lib_valid(self):
        from resume_generator.paths import _looks_like_resume_lib
        self.assertTrue(_looks_like_resume_lib(FIXTURES))

    def test_looks_like_resume_lib_invalid(self):
        from resume_generator.paths import _looks_like_resume_lib
        self.assertFalse(_looks_like_resume_lib(Path("/nonexistent")))
        self.assertFalse(_looks_like_resume_lib(ROOT))  # 产品仓库不是简历库

    def test_resolve_lib_from_fixtures(self):
        """resolve_lib 带显式路径应直接返回，不走向上搜索。"""
        from resume_generator.paths import resolve_lib
        lib = resolve_lib(str(FIXTURES))
        self.assertEqual(lib, FIXTURES.resolve())

    def test_resolve_lib_explicit(self):
        from resume_generator.paths import resolve_lib
        lib = resolve_lib(str(FIXTURES))
        self.assertEqual(lib, FIXTURES.resolve())

    def test_resolve_lib_explicit_invalid(self):
        from resume_generator.paths import resolve_lib, ResumeLibNotFound
        with self.assertRaises(ResumeLibNotFound):
            resolve_lib("/nonexistent/path")

    def test_find_product_root(self):
        from resume_generator.paths import find_product_root
        root = find_product_root(start=SRC / "resume_generator")
        self.assertTrue((root / "AGENT.md").is_file())

    def test_describe_paths_runs(self):
        from resume_generator.paths import describe_paths
        output = describe_paths()
        self.assertIn("cwd", output)
        self.assertIn("product_root", output)


class TestGetResumeTextField(unittest.TestCase):

    def test_simple_path(self):
        from resume_generator.data_loader import get_resume_text_field
        data = {"personal": {"name": "张三"}}
        self.assertEqual(get_resume_text_field(data, "personal.name"), "张三")

    def test_nested_list_path(self):
        from resume_generator.data_loader import get_resume_text_field
        data = {"education": [{"school": "某大学"}]}
        self.assertEqual(get_resume_text_field(data, "education.0.school"), "某大学")

    def test_missing_path(self):
        from resume_generator.data_loader import get_resume_text_field
        data = {"personal": {"name": "张三"}}
        self.assertIsNone(get_resume_text_field(data, "personal.phone"))
        self.assertIsNone(get_resume_text_field(data, "nonexistent"))

    def test_non_string_value(self):
        from resume_generator.data_loader import get_resume_text_field
        data = {"count": 42}
        self.assertIsNone(get_resume_text_field(data, "count"))


if __name__ == "__main__":
    unittest.main()