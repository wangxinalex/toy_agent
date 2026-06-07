from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

WORKSPACE_ROOT = Path(__file__).resolve().parent


def ensure_workspace_path(relative_path: str) -> Path:
    # 所有文件工具都先过这一层，避免模型读写工作区之外的路径。
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

    这不是最安全的实现，但非常适合教学，因为你能很清楚地看到“模型生成内容 -> 本地落盘”。
    """
    target = ensure_workspace_path(path)
    target.write_text(content)
    return {
        "ok": True,
        "path": path,
        "bytes_written": len(content.encode("utf-8")),
    }


def run_command(command: str) -> dict[str, Any]:
    """工具 4: 运行本地命令。

    对 coding agent 来说，这一步很关键，因为它提供了外部反馈，例如测试是否通过。
    """
    completed = subprocess.run(
        command,
        cwd=WORKSPACE_ROOT,
        shell=True,
        capture_output=True,
        text=True,
    )
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
    "run_command": run_command,
}