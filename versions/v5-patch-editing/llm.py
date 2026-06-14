from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from typing import Any

SYSTEM_PROMPT = """You are a minimal coding agent working inside one repository.

You must respond with exactly one JSON object.
Do not wrap it in markdown fences.
Do not add any explanation, greeting, or preamble outside the JSON object.

Available actions:
- read_file: {"action":"read_file","path":"relative/path.py"}
- search_text: {"action":"search_text","query":"needle"}
- apply_patch: {"action":"apply_patch","path":"relative/path.py","old_snippet":"exact existing text","new_snippet":"replacement text"}
- write_file: {"action":"write_file","path":"relative/path.py","content":"full file contents"}
- run_command: {"action":"run_command","command":"pytest -q"}
- finish: {"action":"finish","summary":"what you changed or learned"}

Rules:
- Operate only inside the workspace.
- Read before writing when possible.
- When editing an existing file, use apply_patch instead of write_file.
- Only use write_file when creating a new file or rewriting an entire file.
- old_snippet must be an exact substring of the file content (including indentation).
- old_snippet must appear exactly once in the file to avoid ambiguity.
- After a write or patch, usually validate with run_command.
- If a command or file result is enough to conclude, use finish.
"""


def extract_json_object(text: str) -> dict[str, Any]:
    """从模型输出中提取第一个完整 JSON 对象。

    有些模型会在 JSON 前面多说一句话，这里就把那部分忽略掉。
    """
    stripped = text.strip()

    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            return parsed
        raise RuntimeError(f"Expected a JSON object, got {type(parsed).__name__}")
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char not in {"{", "["}:
            continue
        try:
            parsed, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
        raise RuntimeError(f"Expected a JSON object, got {type(parsed).__name__}")

    raise RuntimeError("No JSON object found in model output")


def build_model_request(model: str, history: list[dict[str, Any]]) -> dict[str, Any]:
    """构造发给模型的请求体。

    V3 的核心变化：不再把所有历史塞进一条 user message，而是转换为
    标准的 user/assistant 交替消息结构。

    history 内部格式不变，转换逻辑只在这里发生。
    """
    messages: list[dict[str, Any]] = []
    for entry in history:
        if "task" in entry:
            messages.append({"role": "user", "content": entry["task"]})
        elif "decision" in entry:
            messages.append(
                {"role": "assistant", "content": json.dumps(entry["decision"])}
            )
            messages.append({"role": "user", "content": json.dumps(entry["result"])})
    return {
        "model": model,
        "max_tokens": 4096,
        "system": SYSTEM_PROMPT,
        "messages": messages,
        "stream": True,
    }


def call_model(
    *,
    api_key: str,
    base_url: str,
    model: str,
    history: list[dict[str, Any]],
) -> dict[str, Any]:
    """调用大模型，流式输出 token，返回完整 JSON 动作。

    V3 的核心变化：
    1. 请求体加 stream: true
    2. 逐行读取 SSE 事件，边收边打印
    3. 累积完整文本后解析 JSON
    """
    body = build_model_request(model=model, history=history)
    request = urllib.request.Request(
        base_url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        response = urllib.request.urlopen(request, timeout=120)
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Model request failed: HTTP {exc.code} {details}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Model request failed: {exc.reason}") from exc

    # 流式模式下，服务端返回的是 SSE（Server-Sent Events）字节流，而不是一次性 JSON。
    # 直观理解：
    # - 非流式：一次响应里直接拿到完整文本
    # - 流式：完整文本被拆成很多事件（token 或片段）逐步发送
    #
    # 这里采用"双轨处理"：
    # 1) 每收到片段就立刻打印，提供实时反馈（用户体验）
    # 2) 同时把片段累积到内存，最后拼出完整文本再做 JSON 动作解析（程序正确性）
    accumulated: list[str] = []
    with response:
        for line in response:
            # SSE 是"逐行协议"：
            # - 典型业务数据行形如: data: {...json...}
            # - 空行通常代表事件边界
            # - 也可能出现其他前缀（例如 event:, id:）
            # 对于这个教学版实现，我们只解析 data: 行，其他行全部忽略。
            line_str = line.decode("utf-8").strip()
            if not line_str.startswith("data: "):
                continue

            # 去掉 "data: " 前缀后得到事件负载。
            # 在 Anthropic 兼容流式中，这里是一个 JSON 对象，含 type 字段。
            event = json.loads(line_str[6:])
            event_type = event.get("type")

            if event_type == "content_block_delta":
                # 只处理"文本增量"事件，这是真正携带模型输出内容的事件。
                # 其他控制类事件（例如 message_start/message_delta/message_stop）
                # 在本版本里不参与最终动作提取，所以无需进入拼接流程。
                delta = event.get("delta", {})
                text = delta.get("text", "")
                if text:
                    # 路径 A：实时输出到终端，让用户看到 token 正在持续到达。
                    sys.stdout.write(text)
                    sys.stdout.flush()
                    # 路径 B：保存同一份内容，为最终 JSON 解析保留完整上下文。
                    # 注意：这里不能只打印不保存；否则最后无法拿到完整字符串进行结构化解析。
                    accumulated.append(text)

    # 流结束后把所有片段还原为"完整模型文本"，供 extract_json_object 使用。
    full_text = "".join(accumulated).strip()
    print()  # 流式结束后手动补一个换行，避免和后续日志粘在同一行。

    if not full_text:
        raise RuntimeError("Model returned no text in streaming response.")

    try:
        return extract_json_object(full_text)
    except RuntimeError:
        # 模型没有按 system prompt 的要求输出 JSON（例如直接说了自然语言）。
        # 这虽然不该发生，但现实中总会发生。把自然语言输出包装成 finish，
        # 用户已经通过流式打印看到了内容，不会丢失信息。
        if len(full_text) > 500:
            summary = full_text[:500] + "\n...<truncated>"
        else:
            summary = full_text
        return {"action": "finish", "summary": summary}
