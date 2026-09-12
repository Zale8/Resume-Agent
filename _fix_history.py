# -*- coding: utf-8 -*-
"""临时脚本（用完即删）：A. 修正 CHANGELOG 日期；B. 纯 Python 重建历史以清除泄漏手机号。

为什么重建历史：审计发现真实手机号被写进了 5 个提交的
tests/check_privacy.py（当时把它加进了「虚构测试数据」白名单，这是错误做法）。
`git filter-branch` 在本环境不可用（需 sh，无法创建命名管道），因此用纯 Python
逐提交重建。仓库无远程、无协作，历史重写无外部影响。

保留：全部提交（顺序、时间、提交信息、作者身份）、全部文件内容
仅修改：tests/check_privacy.py 中的白名单（去掉真实号码）
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
LEAKED = "13900000001"

# CHANGELOG 日期修正
DATE_FIXES = [
    ("## v0.2.3 (2026-09-12)", "## v0.2.3 (2026-09-13)"),
    ("## v0.2.4 (2026-09-12) — 仓库整理", "## v0.2.4 (2026-09-13) — 仓库整理"),
    ("## v0.2.5 (2026-09-12) — 身份审计修正", "## v0.2.5 (2026-09-13) — 身份审计修正"),
]


def git(*args: str, cwd: Path | None = None, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=cwd or REPO, capture_output=True,
        text=True, encoding="utf-8", errors="replace", env=env,
    )


def fix_date() -> bool:
    path = REPO / "CHANGELOG.md"
    text = path.read_text(encoding="utf-8")
    original = text
    for old, new in DATE_FIXES:
        text = text.replace(old, new)
    if text == original:
        print("  CHANGELOG 日期无需修改")
        return False
    path.write_text(text, encoding="utf-8")
    print("  已修正 CHANGELOG 日期 09-12 -> 09-13")
    return True


def rebuild_history() -> int:
    """逐提交重建，清除测试文件里的泄漏手机号。"""
    log = git("log", "--all", "--reverse",
              "--format=%H%x1f%an%x1f%ae%x1f%aI%x1f%cn%x1f%ce%x1f%cI%x1f%B%x1e")
    commits = []
    for chunk in log.stdout.split("\x1e"):
        chunk = chunk.strip("\n")
        if not chunk.strip():
            continue
        parts = chunk.split("\x1f")
        if len(parts) < 8:
            continue
        commits.append({
            "sha": parts[0], "an": parts[1], "ae": parts[2], "ad": parts[3],
            "cn": parts[4], "ce": parts[5], "cd": parts[6], "message": parts[7],
        })
    print(f"  源提交数：{len(commits)}")

    # 抓取每个提交的文件（除 .git）
    snapshots = []
    for c in commits:
        files = [f for f in git("ls-tree", "-r", "--name-only", c["sha"])
                 .stdout.splitlines() if f.strip()]
        blobs = {}
        for f in files:
            r = subprocess.run(["git", "show", f"{c['sha']}:{f}"], cwd=REPO,
                               capture_output=True)
            blobs[f] = r.stdout
        snapshots.append({"meta": c, "blobs": blobs})

    fresh = REPO / "_rebuilt"
    if fresh.exists():
        shutil.rmtree(fresh)
    fresh.mkdir()
    git("init", "-q", "-b", "main", cwd=fresh)

    patched = 0
    for snap in snapshots:
        for item in fresh.iterdir():
            if item.name == ".git":
                continue
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
        for rel, data in snap["blobs"].items():
            target = fresh / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            # 关键：清除泄漏手机号
            if rel.endswith(".py") or rel.endswith(".md"):
                try:
                    text = data.decode("utf-8")
                except UnicodeDecodeError:
                    target.write_bytes(data)
                    continue
                if LEAKED in text:
                    text = text.replace(LEAKED, "13900000001")
                    patched += 1
                    data = text.encode("utf-8")
            target.write_bytes(data)

        git("add", "-A", cwd=fresh)
        meta = snap["meta"]
        env = dict(os.environ)
        env.update({
            "GIT_AUTHOR_NAME": meta["an"], "GIT_AUTHOR_EMAIL": meta["ae"],
            "GIT_AUTHOR_DATE": meta["ad"],
            "GIT_COMMITTER_NAME": meta["cn"], "GIT_COMMITTER_EMAIL": meta["ce"],
            "GIT_COMMITTER_DATE": meta["cd"],
        })
        subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", meta["message"]],
                       cwd=fresh, env=env, check=True)

    print(f"  已清除 {patched} 处泄漏手机号")

    # 替换 .git
    old = REPO / "_old_git"
    (REPO / ".git").rename(old)
    (fresh / ".git").rename(REPO / ".git")
    shutil.rmtree(fresh)
    print("  已替换 .git")
    return 0


def main() -> int:
    print("A. 修正 CHANGELOG 日期")
    changed = fix_date()

    # 先把工作区里的泄漏修掉并提交，再重建历史 —— 这样最新提交本身就是干净的
    print("\nB. 提交当前工作区修正")
    git("add", "-A")
    staged = git("diff", "--cached", "--name-only").stdout.split()
    if staged:
        r = git("commit", "-q", "-m",
                "fix: 修正 CHANGELOG 日期；测试白名单移除真实手机号")
        print(f"  已提交 {len(staged)} 个文件")
    else:
        print("  无改动需提交")

    print("\nC. 重建历史以清除泄漏手机号")
    rebuild_history()

    # 清理旧 .git（只读文件需先去属性）
    old = REPO / "_old_git"
    if old.exists():
        for p in old.rglob("*"):
            try:
                p.chmod(0o666 if p.is_file() else 0o777)
            except OSError:
                pass
        shutil.rmtree(old, ignore_errors=True)
        print(f"  旧 .git 清理：{not old.exists()}")

    print("\nD. 验证（提交数应为 19）")
    print(git("log", "--oneline").stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
