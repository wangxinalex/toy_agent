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
- write_file: {"action":"write_file","path":"relative/path.py","content":"full file contents"}
- run_command: {"action":"run_command","command":"pytest -q"}
- finish: {"action":"finish","summary":"what you changed or learned"}

Rules:
- Operate only inside the workspace.
- Read before writing when possible.
- Prefer small, local edits.
- When editing, prefer the smallest possible change instead of rewriting an entire file.
- After a write, usually validate with run_command.
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
            messages.append(
                {"role": "user", "content": json.dumps(entry["result"])}
            )
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

    accumulated: list[str] = []
    with response:
        for line in response:
            line_str = line.decode("utf-8").strip()
            if not line_str.startswith("data: "):
                continue

            event = json.loads(line_str[6:])
            event_type = event.get("type")

            if event_type == "content_block_delta":
                delta = event.get("delta", {})
                text = delta.get("text", "")
                if text:
                    sys.stdout.write(text)
                    sys.stdout.flush()
                    accumulated.append(text)

    full_text = "".join(accumulated).strip()
    print()  # 流式结束后换行

    if not full_text:
        raise RuntimeError("Model returned no text in streaming response.")

    try:
        return extract_json_object(full_text)
    except RuntimeError as exc:
        raise RuntimeError(f"Model did not return valid JSON: {full_text}") from exc
