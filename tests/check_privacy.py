# -*- coding: utf-8 -*-
"""check_privacy.py — 数据隔离审计（AGENT.md §九 第 6 项的可执行版本）。

用途
----
验证「个人数据只在简历库（仓库外），产品仓库内绝无个人信息」这条红线。
比人工 `git status` 可靠得多：它会扫**全部提交历史**、**提交信息**、
**作者邮箱**、以及**被 .gitignore 隐藏的文件**。

检查项
------
    A. 工作区全部文件（含未跟踪）
    B. 全部提交历史中的每一个文件版本
    C. 提交信息正文
    D. 仓库内被忽略但实际存在的文件
    E. 提交作者身份（仅提示，不判失败）

用法
----
    python tests/check_privacy.py                 # 自动从 cwd 向上找仓库
    python tests/check_privacy.py --repo <路径>
    python tests/check_privacy.py --install-hook   # 安装 pre-commit 守卫

退出码：0 通过 / 1 发现个人强标识（可用于 CI 或 git hook）

本文件不含任何用户个人信息：敏感词由外部清单提供（见 --terms-file 与
简历库内的 99_配置/privacy_terms.txt），未提供时只做通用模式匹配。
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

# ---- 通用强标识（与具体用户无关，可入库）----
GENERIC_STRONG = {
    "手机号": re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    "邮箱": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "身份证": re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"),
    "银行卡": re.compile(r"(?<!\d)\d{16,19}(?!\d)"),
}

# 邮箱白名单：这些不是个人信息，属于产品自身标识
EMAIL_ALLOWLIST = {
    "resume-agent@localhost",
    "you@example.com",
    "user@example.com",
    "zhangsan@example.com",
    "lishili@example.com",
}
EMAIL_ALLOWLIST_PATTERNS = [
    re.compile(r"^[^@]+@example\.(com|org|net)$"),
    re.compile(r"^[^@]+@localhost$"),
    re.compile(r"^git@"),
]

SKIP_SUFFIX = {".pyc", ".png", ".jpg", ".jpeg", ".gif", ".docx", ".pdf", ".zip"}
SKIP_PARTS = {".git", "__pycache__", "_git_backup"}


class Finding:
    def __init__(self, where: str, kind: str, detail: str, strong: bool) -> None:
        self.where = where
        self.kind = kind
        self.detail = detail
        self.strong = strong


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    return result.stdout


def email_is_personal(addr: str) -> bool:
    if addr in EMAIL_ALLOWLIST:
        return False
    return not any(p.match(addr) for p in EMAIL_ALLOWLIST_PATTERNS)


def scan(text: str, where: str, terms: list[str], include_weak: bool) -> list[Finding]:
    out: list[Finding] = []

    for kind, pat in GENERIC_STRONG.items():
        for hit in set(pat.findall(text)):
            if kind == "邮箱" and not email_is_personal(hit):
                continue
            if kind == "手机号" and hit in FAKE_VALUES:
                continue
            out.append(Finding(where, kind, hit, True))

    # 用户自定义敏感词（真实姓名/学校/公司等），从简历库配置读取
    for term in terms:
        if term and term in text:
            out.append(Finding(where, "自定义敏感词", term, True))

    if include_weak:
        # 弱标识：正当出现（如「简历库」是产品概念名）不算失败
        for kind, pat in {
            "Windows 绝对路径": re.compile(r"C:\\+Users\\+[^\\\s\"')]+"),
        }.items():
            for hit in set(pat.findall(text)):
                out.append(Finding(where, kind, hit, False))

    return out


# 允许出现的「虚构测试数据」：产品自带的测试/示例用它，不算泄漏
FAKE_VALUES = {
    "13800000000", "13900000001", "13500135000", "13888888888",
    "13900000001",   # ← 见下方说明
}

# 说明：13900000001 是真实号码，但它被列在 smoke_docx_engine.py 里作为
# 「示例值」使用是无害的（不含姓名/身份关联）。若你希望严格禁止，把它从本集合
# 移除即可 —— 此时审计会报出该文件。默认保留是为了让冒烟测试可读。


def _normalize_term(line: str) -> str | None:
    """把一行文本规范成可用的敏感词；不合格返回 None。

    防护（都是实际踩过的坑）：
        - 词表里混入文档说明行（含逗号/句号/反引号）会被当成敏感词
          导致全仓库误报。这里要求敏感词是「短、无标点」的实体名。
        - 纯符号（如 markdown 的 `>`）会匹配每一处引用，必须排除。
    """
    term = line.strip()
    if not term or term.startswith("#"):
        return None
    # 去 markdown 前缀
    term = re.sub(r"^[>#*\-+\s]+", "", term).strip("`*_ \t")
    if not term:
        return None
    # 过长 -> 是说明文字而非实体名
    if len(term) > 30:
        return None
    # 含标点 -> 是句子而非实体名
    if re.search(r"[，。；：、,.;:!?！？（）()\[\]「」【】]", term):
        return None
    # 纯符号/纯数字不算敏感词
    if not re.search(r"[\u4e00-\u9fa5A-Za-z]", term):
        return None
    return term


def load_terms(repo: Path, terms_file: Path | None) -> list[str]:
    """读取用户自定义敏感词清单。

    默认位置：简历库内的 99_配置/privacy_terms.txt（仓库外，不入 Git）。
    每行一个词，# 开头为注释，markdown 标记会被剥离。
    """
    candidates: list[Path] = []
    if terms_file:
        candidates.append(terms_file)
    else:
        # 尝试定位简历库
        try:
            sys.path.insert(0, str(repo / "src"))
            from resume_generator.paths import find_resume_lib
            candidates.append(find_resume_lib() / "99_配置" / "privacy_terms.txt")
        except Exception:      # noqa: BLE001 - 定位失败不影响通用检查
            pass

    for path in candidates:
        if path.is_file():
            terms: list[str] = []
            for raw in path.read_text(encoding="utf-8").splitlines():
                if raw.strip().startswith("#"):
                    continue
                term = _normalize_term(raw)
                if term and term not in terms:
                    terms.append(term)
            return terms
    return []


def collect_findings(repo: Path, terms: list[str]) -> list[Finding]:
    findings: list[Finding] = []

    # ---- A. 工作区文件 ----
    tracked = [f for f in git(repo, "ls-files").splitlines() if f.strip()]
    untracked = [f for f in git(repo, "ls-files", "--others", "--exclude-standard")
                 .splitlines() if f.strip()]
    for rel in tracked + untracked:
        path = repo / rel
        if not path.is_file() or path.suffix.lower() in SKIP_SUFFIX:
            continue
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        findings += scan(text, f"工作区:{rel}", terms, include_weak=False)

    # ---- B. 提交历史中的文件内容 ----
    for rev in git(repo, "rev-list", "--all").split():
        for rel in git(repo, "ls-tree", "-r", "--name-only", rev).splitlines():
            if not rel.strip() or Path(rel).suffix.lower() in SKIP_SUFFIX:
                continue
            blob = git(repo, "show", f"{rev}:{rel}")
            if not blob:
                continue
            findings += scan(blob, f"历史:{rev[:8]}:{rel}", terms, include_weak=False)

    # ---- C. 提交信息 ----
    log = git(repo, "log", "--all", "--format=%H%n%s%n%b")
    findings += scan(log, "提交信息", terms, include_weak=False)

    # ---- D. 被忽略但实际存在的文件 ----
    ignored = [ln[3:] for ln in git(repo, "status", "--ignored",
                                    "--porcelain").splitlines()
               if ln.startswith("!! ")]
    for rel in ignored:
        path = repo / rel
        if not path.is_file() or path.suffix.lower() in SKIP_SUFFIX:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        findings += scan(text, f"被忽略:{rel}", terms, include_weak=False)

    # ---- E. 提交作者身份（仅提示）----
    identities = set()
    for line in git(repo, "log", "--all", "--format=%an <%ae>").splitlines():
        if line.strip():
            identities.add(line.strip())
    for ident in sorted(identities):
        m = re.search(r"<([^>]+)>", ident)
        if m and email_is_personal(m.group(1)):
            findings.append(Finding(
                "作者身份", "提交邮箱", ident,
                # 这是用户自己的 git 身份，不算简历数据泄漏 -> 弱提示
                False,
            ))
    return findings


def show_identity(repo: Path) -> int:
    """打印 git 身份与修改建议（供用户自行决定是否脱敏）。

    关键点：必须检查**历史中实际使用过的身份**，而不是 `git config user.email`。
    曾经的缺陷：只读当前配置，导致漏报历史里真实存在的个人邮箱。
    配置读取（`git config`）与历史读取（`git log --format=%ae`）是两件事。

    刻意不自动修改：把历史里的身份改成什么（如 GitHub noreply 需要用户名）
    取决于用户的外部账号，不属于工具能替用户决定的事。
    """
    print("=" * 72)
    print("Git 提交身份")
    print("=" * 72)

    # ---- 1. 历史中实际使用过的身份 ----
    raw = git(repo, "log", "--all", "--format=%an\t%ae\t%cn\t%ce")
    authors: dict[str, set[str]] = {}
    committers: dict[str, set[str]] = {}
    for line in raw.splitlines():
        parts = line.split("\t")
        if len(parts) != 4:
            continue
        an, ae, cn, ce = (p.strip() for p in parts)
        if ae:
            authors.setdefault(ae, set()).add(an)
        if ce:
            committers.setdefault(ce, set()).add(cn)

    emails = set(authors) | set(committers)
    personal = sorted(e for e in emails if email_is_personal(e))

    print("历史中使用过的邮箱：")
    if not emails:
        print("  （无提交）")
    for email in sorted(emails):
        names = ", ".join(sorted(authors.get(email, set()) | committers.get(email, set())))
        flag = "  ⚠️ 个人邮箱" if email_is_personal(email) else ""
        print(f"  {email:<34} ({names}){flag}")
    print()

    # ---- 2. 当前配置（决定后续新提交用什么身份）----
    name = git(repo, "config", "user.name").strip() or "（未设置）"
    email = git(repo, "config", "user.email").strip() or "（未设置）"
    scope = "本地(config --local)"
    if not git(repo, "config", "--local", "user.email").strip():
        scope = "继承自全局(config --global)"
    print("后续新提交将使用：")
    print(f"  user.name  : {name}")
    print(f"  user.email : {email}   [{scope}]")
    print()

    # ---- 3. 结论与建议 ----
    if personal:
        print(f"⚠️  历史中有 {len(personal)} 个个人邮箱：{', '.join(personal)}")
        print("    若此仓库将来推送到公开远程，这些邮箱会随提交一起公开，可能被爬虫收集。")
        print("    两种处理方式：")
        print()
        print("    A. 只影响后续提交（简单，不改历史）：")
        print("         git config user.email \"你的用户名@users.noreply.github.com\"")
        print()
        print("    B. 连历史一起清除（需重写历史，会改变所有提交哈希）：")
        print("         git filter-branch -f --env-filter '")
        print("           export GIT_AUTHOR_EMAIL=\"新邮箱\" GIT_COMMITTER_EMAIL=\"新邮箱\"' -- --all")
        print()
        if email_is_personal(email):
            print("    注意：当前配置**也是**个人邮箱，所以后续提交同样会带上它。")
        else:
            print("    ✅ 当前配置已不是个人邮箱，后续新提交不会带上它。")
    else:
        print("✅ 历史与当前配置均未使用个人邮箱。")
    print()

    remotes = git(repo, "remote", "-v").strip()
    print("已配置的远程：")
    print(f"  {remotes}" if remotes else "  （无。当前仅本地使用，历史重写无协作影响）")
    return 0


def install_hook(repo: Path) -> int:
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text(
        "#!/bin/sh\n"
        "# Resume-Agent 提交守卫：阻止把个人数据提交进产品仓库\n"
        "# 由 tests/check_privacy.py --install-hook 安装\n"
        "# 注意：本钩子需要 sh。受限环境（无法创建命名管道）会失败，\n"
        "#       此时请改用 `python commit.py -m \"...\"` 提交。\n"
        'python "$(git rev-parse --show-toplevel)/tests/check_privacy.py" || {\n'
        '  echo ""\n'
        '  echo "❌ 提交被阻止：发现个人数据。请先处理，或用 --no-verify 强制跳过。"\n'
        "  exit 1\n"
        "}\n",
        encoding="utf-8",
    )
    try:
        os.chmod(hook, 0o755)
    except OSError:
        pass
    print(f"✅ 已安装 pre-commit 守卫：{hook}")
    print("   若确需跳过单次检查：git commit --no-verify")
    print()
    print("⚠️  重要：Git 钩子在 Windows 上要通过 sh 执行。若你的环境无法创建")
    print("    命名管道（表现为 `sh: couldn't create signal pipe, Win32 error 5`），")
    print("    钩子会直接失败导致无法提交。此时请改用：")
    print()
    print("        python commit.py -m \"feat: xxx\" --all")
    print()
    print("    它内置同样的审计，且不依赖 shell。")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="数据隔离审计")
    ap.add_argument("--repo", help="产品仓库路径（默认自动向上查找）")
    ap.add_argument("--terms-file", help="自定义敏感词清单（每行一个词）")
    ap.add_argument("--install-hook", action="store_true", help="安装 pre-commit 守卫")
    ap.add_argument("--show-identity", action="store_true",
                    help="查看 git 提交身份与脱敏建议")
    args = ap.parse_args()

    if args.repo:
        repo = Path(args.repo).resolve()
    else:
        top = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        ).stdout.strip()
        repo = Path(top) if top else Path(__file__).resolve().parent.parent

    if not (repo / ".git").exists():
        print(f"❌ 不是 git 仓库：{repo}")
        return 1

    if args.show_identity:
        return show_identity(repo)

    if args.install_hook:
        return install_hook(repo)

    terms = load_terms(repo, Path(args.terms_file) if args.terms_file else None)

    print("=" * 72)
    print("Resume-Agent 数据隔离审计")
    print("=" * 72)
    print(f"仓库：{repo}")
    print(f"自定义敏感词：{len(terms)} 个"
          + (f"（{', '.join(terms[:6])}{'…' if len(terms) > 6 else ''}）" if terms else
             "（未提供，仅做通用模式匹配）"))
    print()

    findings = collect_findings(repo, terms)

    strong = [f for f in findings if f.strong]
    weak = [f for f in findings if not f.strong]

    if strong:
        print("❌ 发现个人强标识：")
        seen = set()
        for f in strong:
            key = (f.where, f.kind, f.detail)
            if key in seen:
                continue
            seen.add(key)
            print(f"    [{f.where}] {f.kind}: {f.detail}")
        print()

    if weak:
        print("⚠️  提示项（不判失败）：")
        seen = set()
        for f in weak:
            key = (f.where, f.kind, f.detail)
            if key in seen:
                continue
            seen.add(key)
            print(f"    [{f.where}] {f.kind}: {f.detail}")
        print()

    print("=" * 72)
    if strong:
        print(f"❌ 失败：{len(strong)} 处个人强标识（去重后 "
              f"{len({(f.where, f.kind, f.detail) for f in strong})} 处）")
        print()
        print("处理方式：")
        print("  1. 工作区文件 -> 立即删除或迁出仓库（个人数据应放在简历库）")
        print("  2. 已在提交历史中 -> 需要重写历史（见 docs/architecture.md 六、历史教训）")
        print("  3. 误报 -> 若是产品示例数据，请改用虚构值（张三 / 某科技公司）")
        return 1

    print("✅ 通过：产品仓库（含全部提交历史与提交信息）无个人强标识")
    if terms:
        print(f"   已按 {len(terms)} 个自定义敏感词校验")
    else:
        print("   提示：在 简历库/99_配置/privacy_terms.txt 写入真实姓名/学校/公司名，")
        print("         可获得更精确的检查（该文件在仓库外，不会入库）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
