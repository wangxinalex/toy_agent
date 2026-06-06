from __future__ import annotations

import json
import textwrap
from typing import Any

from llm import call_model
from tools import TOOLS


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
    task: str, *, max_steps: int, api_key: str, base_url: str, model: str
) -> str:
    """最小 agent 主循环。

    读这一个函数时，可以把它理解成 4 步：
    1. 把当前状态发给模型
    2. 取回一个动作
    3. 执行动作
    4. 把执行结果追加回历史
    """
    history: list[dict[str, Any]] = [{"task": task}]

    for step in range(1, max_steps + 1):
        decision = call_model(
            api_key=api_key,
            base_url=base_url,
            model=model,
            history=history,
        )
        action = decision.get("action")
        print(f"\nStep {step}: {json.dumps(decision, ensure_ascii=False)}")

        if action == "finish":
            summary = decision.get("summary", "No summary provided.")
            print("\nAgent finished:")
            print(summary)
            return summary

        result = execute_tool(decision)
        print(
            textwrap.indent(
                json.dumps(result, ensure_ascii=False, indent=2), prefix="  "
            )
        )
        history.append({"decision": decision, "result": result})

    print("\nAgent stopped: reached max steps.")
    return "Agent stopped: reached max steps."
