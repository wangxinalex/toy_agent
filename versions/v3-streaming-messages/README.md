# V3 — 流式输出 + 消息结构重构

V3 在 V2 的基础上改了 `llm.py`（重写）和 `agent.py`（微调），引入两个关键改进：

1. **流式输出**：模型边想边打字，不再黑箱等待。
2. **消息结构重构**：从"所有 history 塞进一条 user message"变成标准的 user/assistant 交替对话。

## V2 → V3 改了什么

| 文件 | 改动量 | 改了什么 |
|------|--------|---------|
| `llm.py` | 重写 | 流式 SSE 解析 + 消息结构重构 |
| `agent.py` | 一行 | print 时机微调 |
| `tools.py` | 不变 | — |
| `main.py` | 不变 | — |

## 变化 1：消息结构 — 为什么不能全塞进一条 user message

### V2 的做法

整个 history 序列化成 JSON 字符串，放进一条 user message：

```python
user_message = {
    "role": "user",
    "content": [{"type": "text", "text": json.dumps(history)}]
}
messages = [user_message]  # 整个对话历史是一条消息
```

模型看到的上下文是一个巨大的 JSON 数组：

```
[user]: [{"task": "改 README"}, {"decision": {...}, "result": {...}}, ...]
```

所有东西 —— 任务、模型自己的决策、工具返回的结果 —— 混在一起。模型分不清哪些是自己说过的、哪些是外部输入。

### V3 的做法

history 内部格式不变，但在 `build_model_request()` 里转换成标准的 user/assistant 交替消息：

```python
messages = []
for entry in history:
    if "task" in entry:
        messages.append({"role": "user", "content": entry["task"]})
    elif "decision" in entry:
        messages.append({"role": "assistant", "content": json.dumps(entry["decision"])})
        messages.append({"role": "user", "content": json.dumps(entry["result"])})
```

模型看到的是清晰的对话结构：

```
[user]: 改 README
[assistant]: {"action":"read_file","path":"README.md"}
[user]: {"ok":true,"content":"..."}
[assistant]: {"action":"write_file",...}
[user]: {"ok":true,"bytes_written":2048}
[assistant]: {"action":"finish","summary":"..."}
```

**关键洞察**：`agent.py` 里的 `history` 格式一行没改。转换逻辑只发生在 `build_model_request()` 里。这证明了"内部数据模型"和"API 传输格式"是两个独立的关注点。

## 变化 2：流式输出 — 从黑箱到透明

### V2 的做法

```python
with urllib.request.urlopen(request, timeout=60) as response:
    raw_payload = response.read().decode("utf-8")  # 阻塞等待完整响应
```

用户看到的是：等待 5-30 秒 → 突然蹦出完整 JSON。中间过程完全不可见。

### V3 的做法

请求体加 `"stream": true`，响应变成 SSE（Server-Sent Events）流。逐行读取，实时打印 token：

```python
response = urllib.request.urlopen(request, timeout=120)
with response:
    for line in response:                          # 逐行读 SSE
        event = json.loads(line[6:])               # 去掉 "data: " 前缀
        if event["type"] == "content_block_delta":
            text = event["delta"]["text"]
            sys.stdout.write(text)                 # 边收边打印
            sys.stdout.flush()
            accumulated.append(text)
```

模型一边生成一边输出，就像人在打字。你不需要等到全部完成就能判断方向对不对。

一次 SSE 流的事件序列：

```
data: {"type":"message_start",...}
data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"{"}}
data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"\"action"}}
...
data: {"type":"message_stop"}
```

我们只关心 `content_block_delta` 事件，从中取出 `delta.text` 累积。其他事件忽略。

## 代码导读

如果你已经读过 V2，只需关注这些差异：

### `llm.py`

| 关注点 | 变化说明 |
|--------|---------|
| `build_model_request()` | V2 用单条 user message，V3 用交替 messages + `"stream": true` |
| `call_model()` | V2 用 `response.read()` 一次性读，V3 用 `for line in response` 逐行读 SSE |
| `extract_text_from_response()` | 已删除 — V3 在流式处理中直接累积文本 |

### `agent.py`

| 关注点 | 变化说明 |
|--------|---------|
| `print(f"\n--- Step {step} ---")` | V2 在模型返回后打印完整 decision，V3 在调用前打印步数标题，内容由流式实时展示 |

## 体验一下

```bash
cd versions/v3-streaming-messages
python main.py "read main.py and explain what this project does"
```

观察 token 逐个出现在屏幕上，而不是一次性蹦出来。

## 这个版本仍然不做什么

- **没有持久化**。关掉进程上下文仍丢失（→ V4）。
- **仍然是整文件覆写**。没有补丁编辑（→ V5）。
- **命令执行仍无限制**。`shell=True` 的风险存在（→ V6）。
- **没有历史长度管理**。多轮对话下 messages 数组会一直增长。

## 下一步 → V4

详见 [`docs/TOY_TO_USABLE_ROADMAP.md`](../../docs/TOY_TO_USABLE_ROADMAP.md)。
