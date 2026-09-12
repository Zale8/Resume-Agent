#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""commit.py — 带数据隔离守卫的提交入口。

为什么不用 .git/hooks/pre-commit：
    Git 钩子在 Windows 上要通过 `sh` 执行，在受限环境里会因无法创建命名管道
    而失败（实测 `sh: couldn't create signal pipe, Win32 error 5`）。
    Python 入口不依赖 shell，Windows / macOS / Linux 行为一致。

作用
----
    1. 先跑数据隔离审计（tests/check_privacy.py）
    2. 审计通过才执行 git add + git commit
    3. 审计失败则拒绝提交，并打印处理方式

用法
----
    python commit.py -m "feat: 新增 xxx"            # 只提交已暂存的改动
    python commit.py -m "docs: 更新说明" --all      # 先 add -A 再提交
    python commit.py -m "..." --force              # 跳过审计（仅在确认无个人数据时）

本文件不含任何用户个人信息。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AUDIT = HERE / "tests" / "check_privacy.py"


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )


def main() -> int:
    ap = argparse.ArgumentParser(
        description="带数据隔离守卫的 git 提交入口",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("-m", "--message", required=True, help="提交信息")
    ap.add_argument("--all", action="store_true", help="提交前先 git add -A")
    ap.add_argument("--force", action="store_true", help="跳过数据隔离审计")
    args = ap.parse_args()

    repo = HERE

    if args.all:
        added = run(["git", "add", "-A"], repo)
        if added.returncode != 0:
            print(f"❌ git add 失败：{added.stderr.strip()}")
            return 1
        print("已执行 git add -A")

    # 没有暂存内容时给出明确提示，避免误以为提交成功
    staged = run(["git", "diff", "--cached", "--name-only"], repo)
    staged_files = [f for f in staged.stdout.splitlines() if f.strip()]
    if not staged_files:
        print("❌ 暂存区为空，没有可提交的内容。")
        print("   如需提交全部改动，加 --all")
        return 1
    print(f"暂存文件：{len(staged_files)} 个")

    if not args.force:
        print()
        if not AUDIT.is_file():
            print(f"⚠️  未找到审计脚本 {AUDIT}，跳过守卫")
        else:
            proc = subprocess.run(
                [sys.executable, str(AUDIT), "--repo", str(repo)],
                cwd=repo, text=True, encoding="utf-8", errors="replace",
            )
            if proc.returncode != 0:
                print()
                print("=" * 68)
                print("❌ 提交被拒绝：数据隔离审计未通过")
                print("=" * 68)
                print("请按上面的提示处理个人数据后重试。")
                print("若确认是误报，可加 --force 跳过（风险自负）。")
                return 1
    else:
        print("⚠️  已跳过数据隔离审计（--force）")

    print()
    commit = run(["git", "commit", "-m", args.message], repo)
    if commit.returncode != 0:
        print(f"❌ 提交失败：\n{commit.stdout.strip()}\n{commit.stderr.strip()}")
        return 1

    print(commit.stdout.strip())
    print("\n✅ 提交完成，且已通过数据隔离审计")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
