# -*- coding: utf-8 -*-
"""paths.py — 跨平台路径自动发现。

设计目标：本仓库复制到任意电脑、任意盘符、任意用户名下都能直接运行，
不需要修改任何一行代码，也不需要设置任何环境变量。

本文件不含任何用户个人信息，不含任何绝对路径。

发现顺序（先命中先返回）：
    1. 环境变量 RESUME_LIB（显式指定，便于 CI / 多简历库）
    2. 从「当前工作目录」逐级向上查找
    3. 从「本文件所在目录」逐级向上查找
    4. 召回库候选名：简历库 / resume_lib / resume-library / data

用法：
    from resume_generator.paths import find_resume_lib, find_project_root
    lib = find_resume_lib()            # -> Path(.../简历库)
    root = find_project_root()         # -> Path(.../Resume-Agent)
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Optional

# 简历库根目录的候选名称（中文默认 + 英文兼容）
LIB_DIR_NAMES = ("简历库", "resume_lib", "resume-library", "resume_lib_data", "data")

# 产品仓库自身的标志文件（用于定位 project root）
ROOT_MARKERS = ("AGENT.md", "agent_entry.md", "PRD.md")

# 简历库的标志性子目录（用于排除同名误判）
LIB_MARKERS = (
    "00_个人信息",
    "01_教育经历",
    "05_专业技能",
    "99_配置",
    "11_岗位JD",
)

ENV_VAR = "RESUME_LIB"


class ResumeLibNotFound(FileNotFoundError):
    """找不到简历库时抛出，附带可操作的排查提示。"""


def _looks_like_resume_lib(path: Path) -> bool:
    """判断目录是否真的是简历库（至少命中一个标志性子目录）。"""
    if not path.is_dir():
        return False
    return any((path / marker).is_dir() for marker in LIB_MARKERS)


def _ancestors(start: Path) -> Iterable[Path]:
    """从 start 开始逐级向上，产出每一个祖先目录（包含 start 自身）。"""
    current = start.resolve()
    while True:
        yield current
        if current.parent == current:
            return
        current = current.parent


def _search_from(start: Path, names: Iterable[str]) -> Optional[Path]:
    """从 start 向上逐级查找候选目录。"""
    for base in _ancestors(start):
        for name in names:
            candidate = base / name
            if _looks_like_resume_lib(candidate):
                return candidate
    return None


def find_resume_lib(
    start: Optional[Path] = None,
    extra_search_roots: Optional[Iterable[Path]] = None,
) -> Path:
    """定位简历库根目录。

    参数：
        start: 起始目录，默认取当前工作目录
        extra_search_roots: 额外的搜索起点（如脚本所在目录）

    返回：简历库根目录的绝对 Path

    异常：ResumeLibNotFound —— 找不到时给出明确的自救指引
    """
    # 1. 环境变量优先
    env_value = os.environ.get(ENV_VAR)
    if env_value:
        env_path = Path(env_value).expanduser()
        if _looks_like_resume_lib(env_path):
            return env_path.resolve()
        # 环境变量设了但目录结构不对 —— 直接报错，避免静默用错库
        raise ResumeLibNotFound(
            f"环境变量 {ENV_VAR} 指向的目录不是有效的简历库：{env_path}\n"
            f"该目录下应至少包含以下子目录之一：{'、'.join(LIB_MARKERS)}"
        )

    # 2. / 3. 从多个起点向上搜索
    starts = []
    if start is not None:
        starts.append(Path(start))
    starts.append(Path.cwd())
    starts.append(Path(__file__).resolve().parent)
    if extra_search_roots:
        starts.extend(Path(p) for p in extra_search_roots)

    for s in starts:
        found = _search_from(s, LIB_DIR_NAMES)
        if found is not None:
            return found.resolve()

    raise ResumeLibNotFound(_not_found_message(starts))


def _not_found_message(starts: Iterable[Path]) -> str:
    tried = "\n".join(f"  - {s}" for s in dict.fromkeys(str(s) for s in starts))
    return (
        "找不到简历库目录。\n"
        f"已从以下位置向上搜索目录名 {list(LIB_DIR_NAMES)}，均未命中：\n{tried}\n\n"
        "三种修复方式（任选其一）：\n"
        "  1) 把简历库目录放在本仓库的同级或上级目录，并确保命名为「简历库」；\n"
        f"  2) 设置环境变量：{ENV_VAR}=/你的/简历库/绝对路径\n"
        "     Windows PowerShell:  $env:RESUME_LIB='D:\\简历库'\n"
        "     macOS / Linux:       export RESUME_LIB=/Users/you/简历库\n"
        "  3) 用命令行参数显式指定：--lib /你的/简历库/绝对路径\n"
        "     （推荐方式：命令行参数优先级最高，且不污染环境）"
    )


def find_product_root(start: Optional[Path] = None) -> Path:
    """定位 Resume-Agent 产品仓库根目录。

    判定依据：目录内存在 ROOT_MARKERS 中的文件（AGENT.md / agent_entry.md / PRD.md）。
    """
    starts = []
    if start is not None:
        starts.append(Path(start))
    starts.append(Path(__file__).resolve().parent)

    for s in starts:
        for base in _ancestors(s):
            if any((base / m).exists() for m in ROOT_MARKERS):
                return base

    # 兜底：src/resume_generator/paths.py -> 上溯三级 = 仓库根
    return Path(__file__).resolve().parents[2]


def resolve_lib(explicit: Optional[str] = None) -> Path:
    """给 CLI 用的统一入口：命令行参数 > 环境变量 > 自动发现。"""
    if explicit:
        candidate = Path(explicit).expanduser()
        if not candidate.is_dir():
            raise ResumeLibNotFound(f"--lib 指定的目录不存在：{candidate}")
        if not _looks_like_resume_lib(candidate):
            raise ResumeLibNotFound(
                f"--lib 指定的目录不是有效的简历库：{candidate}\n"
                f"该目录下应至少包含以下子目录之一：{'、'.join(LIB_MARKERS)}"
            )
        return candidate.resolve()
    return find_resume_lib()


def describe_paths() -> str:
    """自检用：打印当前路径解析结果，便于用户与 AI 排查。"""
    lines = [f"cwd            : {Path.cwd()}"]
    lines.append(f"product_root   : {find_product_root()}")
    lines.append(f"{ENV_VAR:<15}: {os.environ.get(ENV_VAR, '(未设置)')}")
    try:
        lines.append(f"resume_lib     : {resolve_lib()}")
    except ResumeLibNotFound as exc:
        lines.append(f"resume_lib     : ❌ 未找到\n{exc}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(describe_paths())
