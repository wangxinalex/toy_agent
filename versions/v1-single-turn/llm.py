from __future__ import annotations

import json
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


def extract_text_from_response(payload: dict[str, Any]) -> str:
    """从 Anthropic 风格响应中提取纯文本内容。"""
    content = payload.get("content", [])
    chunks = [item.get("text", "") for item in content if item.get("type") == "text"]
    if chunks:
        return "\n".join(chunks).strip()

    # 兼容少数非标准返回：有些服务会把正文放在别的字段里。
    if isinstance(payload.get("text"), str):
        return payload["text"].strip()
    if isinstance(payload.get("completion"), str):
        return payload["completion"].strip()

    return "\n".join(chunks).strip()


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

    这里把“状态如何喂给模型”单独拆出来，便于你观察 agent 的输入到底是什么。
    """
    user_message = {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": json.dumps(history, ensure_ascii=False, indent=2),
            }
        ],
    }
    return {
        "model": model,
        "max_tokens": 4096,
        "system": SYSTEM_PROMPT,
        "messages": [user_message],
    }


def call_model(
    *,
    api_key: str,
    base_url: str,
    model: str,
    history: list[dict[str, Any]],
) -> dict[str, Any]:
    """调用大模型，并强制把返回结果解释成一个 JSON 动作。"""
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
        with urllib.request.urlopen(request, timeout=60) as response:
            raw_payload = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Model request failed: HTTP {exc.code} {details}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Model request failed: {exc.reason}") from exc

    payload = json.loads(raw_payload)
    text = extract_text_from_response(payload)
    if not text:
        raise RuntimeError(
            "Model returned no text blocks. "
            f"payload_keys={list(payload.keys())}, "
            f"content={payload.get('content')!r}"
        )
    try:
        return extract_json_object(text)
    except RuntimeError as exc:
        raise RuntimeError(f"Model did not return valid JSON: {text}") from exc
