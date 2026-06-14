from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

WORKSPACE_ROOT = Path(__file__).resolve().parent

# ── V6: 命令安全 ──────────────────────────────────────────────
# 安全命令白名单：命令必须以这些前缀之一开头（忽略大小写），否则拒绝执行。
# 每个 pattern 是一个正则，匹配命令字符串的开头。
COMMAND_WHITELIST = [
    # Python 相关
    r"^python3?\s",              # python / python3
    r"^python3?\s+-m\s",         # python -m pytest / python -m ruff 等
    r"^pytest",                   # 测试
    r"^ruff\s",                  # 代码检查
    r"^mypy\s",                  # 类型检查
    # Git 只读 / 安全操作
    r"^git\s+status",
    r"^git\s+diff",
    r"^git\s+log",
    r"^git\s+add\s",
    r"^git\s+commit\s",
    # 文件查看（只读）
    r"^ls\b",                    # 列出文件
    r"^cat\s",                   # 查看内容
    r"^head\s",                  # 查看文件头
    r"^tail\s",                  # 查看文件尾
    r"^wc\s",                    # 统计行数
    r"^find\s",                  # 搜索文件
    r"^grep\s",                  # 文本搜索
    r"^echo\s",                  # 输出文本
    # 包管理（只读）
    r"^pip\s+list",
    r"^pip\s+show",
]

# 危险模式：即使命令通过了白名单，命中这些模式也拒绝执行。
# 这是第二道防线：防止白名单内的命令被组合利用。
DANGEROUS_PATTERNS = [
    r"\brm\s+-(?:rf?|fr)\b",      # rm -rf / rm -r / rm -f
    r"\brm\s+.*\*",               # rm 含通配符
    r">\s*/dev/",                 # 写入设备文件
    r"\bcurl\b",                  # 网络下载
    r"\bwget\b",                  # 网络下载
    r"\bsudo\b",                  # 权限升级
    r"\bchmod\s+[0-7]*7",         # chmod 包含写/执行权限全开
    r"\bchown\b",                 # 所有权变更
    r"fork\s*bomb",               # fork 炸弹关键词
    r":\(\)\s*\{",                # fork 炸弹语法
    r"\bgit\s+push\b",            # 禁止推送
    r"\bgit\s+reset\s+--hard",    # 危险重置
    r"\bshutdown\b",              # 关机
    r"\breboot\b",                # 重启
    r"\bkill\s+-9",               # 强制杀进程
    r"\bdd\s+if=",                # 磁盘直接读写
    r"\bmkfs\.",                  # 格式化文件系统
]

COMMAND_TIMEOUT = 30  # 秒
# ───────────────────────────────────────────────────────────────


def validate_command(command: str) -> str | None:
    """V6 新增：检查命令是否安全。

    两层检查：
    1. 命令必须以白名单中的某个前缀开头
    2. 命令不能命中任何危险模式

    返回 None 表示通过，否则返回错误描述字符串。
    """
    cmd_stripped = command.strip()
    if not cmd_stripped:
        return "Empty command"

    # 第一层：白名单检查（不区分大小写）
    allowed = False
    for pattern in COMMAND_WHITELIST:
        if re.search(pattern, cmd_stripped, re.IGNORECASE):
            allowed = True
            break

    if not allowed:
        return (
            f"Command not in whitelist: {cmd_stripped[:80]}\n"
            f"Allowed prefixes: python, pytest, ruff, git status/diff/log/add/commit, "
            f"ls, cat, head, tail, wc, find, grep, echo, pip list/show"
        )

    # 第二层：危险模式检查
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, cmd_stripped, re.IGNORECASE):
            return (
                f"Dangerous pattern detected in command: {cmd_stripped[:80]}\n"
                f"Matched: {pattern}"
            )

    return None  # 通过


def ensure_workspace_path(relative_path: str) -> Path:
    """所有文件工具都先过这一层，避免模型读写工作区之外的路径。"""
    candidate = (WORKSPACE_ROOT / relative_path).resolve()
    if WORKSPACE_ROOT not in candidate.parents and candidate != WORKSPACE_ROOT:
        raise ValueError(f"Path escapes workspace: {relative_path}")
    return candidate


def truncate_output(text: str, limit: int = 4000) -> str:
    """截断过长输出，避免把太多文本再次塞回模型上下文。"""
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...<truncated>"


def read_file(path: str) -> dict[str, Any]:
    """工具 1: 读取文件内容。

    返回统一的 dict 结构，这样主循环不用关心每个工具的细节差异。
    """
    target = ensure_workspace_path(path)
    if not target.exists():
        return {"ok": False, "error": f"File not found: {path}"}
    return {"ok": True, "path": path, "content": truncate_output(target.read_text())}


def search_text(query: str) -> dict[str, Any]:
    """工具 2: 在工作区做最朴素的文本搜索。

    这里不用索引或 AST，就是为了把原理压到最小：模型先搜，再决定读哪个文件。
    """
    matches: list[dict[str, Any]] = []
    for file_path in WORKSPACE_ROOT.rglob("*"):
        if not file_path.is_file() or file_path.name.startswith("."):
            continue
        if ".venv" in file_path.parts:
            continue
        try:
            content = file_path.read_text()
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(content.splitlines(), start=1):
            if query.lower() in line.lower():
                matches.append(
                    {
                        "path": str(file_path.relative_to(WORKSPACE_ROOT)),
                        "line": line_number,
                        "text": line.strip(),
                    }
                )
            if len(matches) >= 20:
                return {"ok": True, "query": query, "matches": matches}
    return {"ok": True, "query": query, "matches": matches}


def write_file(path: str, content: str) -> dict[str, Any]:
    """工具 3: 直接覆盖写文件。

    这不是最安全的实现，但非常适合教学，因为你能很清楚地看到"模型生成内容 -> 本地落盘"。
    """
    target = ensure_workspace_path(path)
    target.write_text(content)
    return {
        "ok": True,
        "path": path,
        "bytes_written": len(content.encode("utf-8")),
    }


def apply_patch(path: str, old_snippet: str, new_snippet: str) -> dict[str, Any]:
    """工具 5: 精确文本替换。

    V5 新增：不再覆盖整个文件，只替换 old_snippet 出现的那一小段。
    比 write_file 省 token，也更安全——改错位置的概率更低。

    约束：
    - old_snippet 必须在文件中恰好出现 1 次，否则返回错误（避免歧义）。
    - old_snippet 和 new_snippet 必须完全匹配，包括缩进和换行。
    """
    target = ensure_workspace_path(path)
    if not target.exists():
        return {"ok": False, "error": f"File not found: {path}"}

    content = target.read_text()
    count = content.count(old_snippet)

    if count == 0:
        return {"ok": False, "error": "old_snippet not found in file"}
    if count > 1:
        return {
            "ok": False,
            "error": f"old_snippet appears {count} times, expected 1",
        }

    new_content = content.replace(old_snippet, new_snippet, 1)
    target.write_text(new_content)
    return {
        "ok": True,
        "path": path,
        "bytes_written": len(new_content.encode("utf-8")),
    }


def run_command(command: str) -> dict[str, Any]:
    """工具 4: 运行本地命令。

    V6 变化：执行前先过 validate_command() 安全检查，加 30 秒超时。
    白名单允许只读/安全的开发命令（pytest、ruff、git status 等），
    危险模式拦截删除、下载、权限升级等操作。
    """
    error = validate_command(command)
    if error is not None:
        return {"ok": False, "command": command, "error": error}

    try:
        completed = subprocess.run(
            command,
            cwd=WORKSPACE_ROOT,
            shell=True,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "command": command,
            "error": f"Command timed out after {COMMAND_TIMEOUT}s",
        }

    return {
        "ok": completed.returncode == 0,
        "command": command,
        "returncode": completed.returncode,
        "stdout": truncate_output(completed.stdout),
        "stderr": truncate_output(completed.stderr),
    }


TOOLS = {
    "read_file": read_file,
    "search_text": search_text,
    "write_file": write_file,
    "apply_patch": apply_patch,
    "run_command": run_command,
}
