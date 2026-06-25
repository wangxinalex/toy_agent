from __future__ import annotations

import json
import textwrap
from typing import Any

from llm import call_model
from tools import TOOLS

# 截断历史时保留的最大 entry 数（不含开头的 task entry）。
# 选 20 对 decision+result 是经验值：足够保持上下文连贯，又不会让 session 文件过大。
HISTORY_MAX_ENTRIES = 40

# V8：同一操作（action + path）连续失败的上限。达到后注入跳过提示。
MAX_CONSECUTIVE_FAILURES = 3

# V8：达到重试上限时注入的提示消息。
RETRY_LIMIT_MSG = (
    "This action has failed {n} consecutive times on '{target}'. "
    "You must try a completely different approach. "
    "Do not retry the same action on the same file."
)

# V7 新增：当模型尝试 finish 但尚未验证时，注入这条提示。
# 这不是给用户看的，而是作为一条 user message 发回模型，迫使它继续工作。
VERIFY_REQUIRED_MSG = (
    "Verification required: you have not run a verification command yet. "
    "Run at least one verification command (e.g. python -m compileall, pytest, "
    "ruff check, mypy) before calling finish."
)


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

    V7 变化：
    - 增加 verified 标记：只有 run_command 成功后才置为 True。
    - 模型调用 finish 时，如果 verified 为 False，注入提示消息并继续循环。
    """
    if history is None:
        # 新会话：从零开始
        history = [{"task": task}]
    else:
        # 恢复会话：截断旧历史，追加新任务。
        # 不做截断的话，长时间运行的 session 文件会无限增长。
        history = history[-HISTORY_MAX_ENTRIES:]
        history.append({"task": task})

    # V7：追踪当前修改是否还没验证。
    # 新任务默认不需要验证；只有写文件后才进入“必须验证”状态。
    needs_verification = False

    # V8：追踪每个 (action, path) 的连续失败次数。
    # 成功时删除 key，失败时 +1，达到上限时注入跳过提示并清零。
    failure_counts: dict[tuple[str, str], int] = {}

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
            # V7：拦截有未验证修改的 finish，强制模型回去验证。
            if needs_verification:
                print(f"\n  [V7] {VERIFY_REQUIRED_MSG}")
                history.append({"decision": decision, "result": {"ok": False, "error": VERIFY_REQUIRED_MSG}})
                continue

            summary = decision.get("summary", "No summary provided.")
            print("\nAgent finished:")
            print(summary)
            return summary, history

        result = execute_tool(decision)

        # V8：追踪连续失败，达到上限时注入跳过提示。
        action_key = (action, decision.get("path", "") or decision.get("command", ""))
        if not result.get("ok"):
            failure_counts[action_key] = failure_counts.get(action_key, 0) + 1
            if failure_counts[action_key] >= MAX_CONSECUTIVE_FAILURES:
                msg = RETRY_LIMIT_MSG.format(n=failure_counts[action_key], target=action_key[1])
                print(f"\n  [V8] Action '{action}' on '{action_key[1]}' failed {failure_counts[action_key]} times. Skipping.")
                history.append({"decision": decision, "result": {"ok": False, "error": msg}})
                del failure_counts[action_key]
                continue
        else:
            failure_counts.pop(action_key, None)

        print(
            textwrap.indent(
                json.dumps(result, ensure_ascii=False, indent=2), prefix="  "
            )
        )
        history.append({"decision": decision, "result": result})

        # V7：写文件会让当前工作进入“未验证”状态；成功的 run_command 会清除它。
        # 局限性：任何成功的 run_command（包括 ls、git status）都会清除 needs_verification，
        # 不区分是否为真正的验证命令（如 pytest、compileall）。
        # 这是有意简化——判断"什么命令算验证"在教学版本中不值得增加复杂度，
        # 真实产品会用更精细的逻辑（如限定命令前缀、要求 returncode 前检查写操作等）。
        if action in {"write_file", "apply_patch"} and result.get("ok"):
            needs_verification = True
        elif action == "run_command" and result.get("ok"):
            needs_verification = False

    print("\nAgent stopped: reached max steps.")
    return "Agent stopped: reached max steps.", history
