from __future__ import annotations

import json
import textwrap
from typing import Any

from llm import call_model
from tools import TOOLS

# 截断历史时保留的最大 entry 数（不含开头的 task entry）。
# 选 20 对 decision+result 是经验值：足够保持上下文连贯，又不会让 session 文件过大。
HISTORY_MAX_ENTRIES = 40


def execute_tool(decision: dict[str, Any]) -> dict[str, Any]:
    """根据模型给出的 action 调用本地工具。"""
    action = decision.get("action")
    tool = TOOLS.get(action)
    if tool is None:
        return {"ok": False, "error": f"Unknown action: {action}"}

    args = {key: value for key, value in decision.items() if key != "action"}
    try:
        return tool(**args)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def run_agent(
    task: str,
    *,
    max_steps: int,
    api_key: str,
    base_url: str,
    model: str,
    history: list[dict[str, Any]] | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """最小 agent 主循环。

    V4 变化：
    - 接受可选的 history 参数，用于恢复会话。
    - 返回 (summary, history) 两个值，供外部保存。
    """
    if history is None:
        # 新会话：从零开始
        history = [{"task": task}]
    else:
        # 恢复会话：截断旧历史，追加新任务。
        # 不做截断的话，长时间运行的 session 文件会无限增长。
        history = history[-HISTORY_MAX_ENTRIES:]
        history.append({"task": task})

    for step in range(1, max_steps + 1):
        print(f"\n--- Step {step} ---")
        decision = call_model(
            api_key=api_key,
            base_url=base_url,
            model=model,
            history=history,
        )
        action = decision.get("action")

        if action == "finish":
            summary = decision.get("summary", "No summary provided.")
            print("\nAgent finished:")
            print(summary)
            return summary, history

        result = execute_tool(decision)
        print(
            textwrap.indent(
                json.dumps(result, ensure_ascii=False, indent=2), prefix="  "
            )
        )
        history.append({"decision": decision, "result": result})

    print("\nAgent stopped: reached max steps.")
    return "Agent stopped: reached max steps.", history
