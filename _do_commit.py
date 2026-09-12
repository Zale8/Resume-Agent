# -*- coding: utf-8 -*-
"""临时提交脚本（用完即删）：分两批提交，并保持每批都通过审计。

批 1：零依赖可移植核心（gen.py / src / agent_entry / 测试 / 文档）
批 2：数据隔离审计 + 仓库外敏感词表 + 整理收尾

为什么分批：审计是「原始状态」的一部分，先提交它、再提交它发现的修复，
历史本身就是一份可追溯的记录。

本脚本不含任何用户个人信息。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )


def commit(message: str) -> bool:
    audit = subprocess.run(
        [sys.executable, "tests/check_privacy.py"],
        cwd=REPO, text=True, encoding="utf-8", errors="replace",
    )
    if audit.returncode != 0:
        print("❌ 审计未通过，中止提交")
        return False
    result = git("commit", "-m", message)
    if result.returncode != 0:
        print(f"❌ 提交失败：{result.stdout}\n{result.stderr}")
        return False
    print(result.stdout.strip().splitlines()[0])
    return True


# ---- 批 1：可移植核心 ----
BATCH_1 = [
    "gen.py", "commit.py", "agent_entry.md",
    "src/resume_generator/paths.py",
    "src/resume_generator/docx_engine.py",
    "src/resume_generator/resume_map.py",
    "src/resume_generator/template_kit.py",
    "src/resume_generator/data_loader.py",
    "src/README.md",
    "tests/smoke_docx_engine.py",
    "tests/smoke_resume_map.py",
    "tests/smoke_other_user.py",
    "templates/template_06",
    "prompts/README.md",
    "prompts/expression_optimizer.md",
    "prompts/jd_analyst.md",
    "prompts/matcher.md",
    "prompts/resume_writer.md",
    "scripts/README.md",
    "workflows/README.md",
    "docs/architecture.md",
    ".gitignore",
    "PRD.md",
]
BATCH_1_DELETE = [
    "scripts/render_templates.py",
    "scripts/gen_template_configs.py",
]

MSG_1 = """feat: 零依赖可移植改造 —— 打通「一条 JD → DOCX 成品」链路

背景：此前渲染环节完全断裂——AGENT.md 引用的生成脚本已被 revert，
仓库内没有任何脚本能把 resume.md 填进 template.docx。同时渲染链路依赖
C:\\Users\\...\\Desktop 绝对路径 + 扫描桌面目录名 + Word COM，换电脑即失效，
macOS/Linux 完全无法运行。

新增：
- gen.py          统一 CLI：doctor / list-templates / standardize / render
- paths.py        跨平台路径自动发现（消灭全部绝对路径）
- docx_engine.py  零依赖 DOCX 填充引擎
  - 空格对齐槽位保持：模板用字面空格对齐，替换值短于槽位须补空格，
    否则同行后续字段左移、版式错位
  - mc:Choice / mc:Fallback 双分支同步替换，保证 Word 与其他阅读器一致
  - t01 品红(FF00FF) <w:br/> 补高 run 自动清理
  - 照片替换（默认只替换最小位图，防误伤图标）
  - 包完整性校验 + 页面几何溢出诊断
- resume_map.py   resume.md → 模板字段映射（三级降级：字段 JSON > 内嵌表 > 章节解析）
  - 槽位不足导致的丢弃内容显式报告（模板槽位固定，多余内容曾被静默丢弃）
  - generation_notes.md 自动产出
- template_kit.py 任意 docx 标准化为可用模板
- agent_entry.md  自包含通用主提示词（任意 AI 加载即用）

删除：
- scripts/render_templates.py / gen_template_configs.py（绝对路径 + Word COM 依赖）

测试：
- tests/smoke_docx_engine.py  5 套模板填充 + 包完整性 + 照片字节
- tests/smoke_resume_map.py   75 项解析与映射断言
- tests/smoke_other_user.py   跨用户 / 跨位置 / 不改代码 通用性验证

自检：5/5 通过（doctor / 填充 / 解析 / 跨用户 / 模板清单）"""

# ---- 批 2：数据隔离审计 + 收尾 ----
BATCH_2 = [
    "tests/check_privacy.py",
    "AGENT.md",
    "README.md",
    "CHANGELOG.md",
    "docs/architecture.md",
]

MSG_2 = """feat(privacy): 数据隔离审计 + 提交守卫，并修复文档示例中的真实信息

起因：复查发现「个人数据已删除」并不等于「历史里没有」。审计脚本扫出：
- 提交历史中 4 个文件版本含个人数据（测试手机号/邮箱、真实姓名、公司名）
- 提交信息正文含真实姓名
- 文档与代码示例里混入了真实公司名与学校名

新增：
- tests/check_privacy.py  数据隔离审计
  - 覆盖工作区（含未跟踪）+ 全部提交历史 + 提交信息 + 被忽略文件 + 作者身份
  - 强标识：手机号/邮箱/身份证/银行卡 + 仓库外自定义敏感词表
  - 词表解析带防护：剥离 markdown 标记、丢弃过长或含标点的说明行
  - --install-hook 可安装 pre-commit 守卫
- commit.py  零依赖提交入口，先审计后提交
  - 不依赖 sh，规避 Windows 上 Git 钩子 couldn't create signal pipe 失败

修复：
- 文档/代码示例中的真实公司名、学校名全部改为虚构值（某科技公司 / 某虚构大学）
- tests/smoke_other_user.py 不再硬编码真实信息作为禁用词，
  改为从仓库外的 简历库/99_配置/privacy_terms.txt 读取

文档：
- AGENT.md §二 新增 4 条红线：文档示例一律用虚构值、删除文件不等于删除历史
- AGENT.md §九 第 6 项自检改为可执行审计命令
- docs/architecture.md 新增「数据隔离的可执行验证」与「跨用户通用性验证」，
  更正原先「个人数据从未存在于任何提交中」的不实陈述

注：历史中已存在的个人数据需重写 Git 历史清除，不在本次提交范围内。

自检：11/11 通过"""


def main() -> int:
    print("=" * 68)
    print("批 1/2：零依赖可移植核心")
    print("=" * 68)
    result = git("add", "--", *BATCH_1)
    if result.returncode != 0:
        print(f"❌ git add 失败：{result.stderr}")
        return 1
    result = git("rm", "-r", "--cached", "--quiet", "--", *BATCH_1_DELETE)
    if result.returncode != 0:
        # 文件可能已不在索引中
        print(f"  （git rm --cached 提示：{result.stderr.strip()[:120]}）")
    staged = git("diff", "--cached", "--name-only").stdout.split()
    print(f"暂存 {len(staged)} 个文件")
    if not commit(MSG_1):
        return 1

    print()
    print("=" * 68)
    print("批 2/2：数据隔离审计 + 收尾")
    print("=" * 68)
    result = git("add", "-A")
    if result.returncode != 0:
        print(f"❌ git add 失败：{result.stderr}")
        return 1
    staged = git("diff", "--cached", "--name-only").stdout.split()
    print(f"暂存 {len(staged)} 个文件")
    for f in staged:
        print(f"    {f}")
    if not commit(MSG_2):
        return 1

    print()
    print("=" * 68)
    print("提交完成")
    print("=" * 68)
    print(git("log", "--oneline", "-4").stdout)
    print("工作区状态：")
    status = git("status", "--short").stdout.strip()
    print(status if status else "  （干净）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
