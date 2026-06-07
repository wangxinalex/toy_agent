# V1 — 单轮对话 · 最小闭环

这是整个项目的**起点**。V1 演示了一个 coding agent 能跑起来的最简结构 —— 只做一件事，做完就退出。

## 这个版本教你什么

1. **coding agent 本质上是什么**：一个循环，每轮把"当前状态"发给 LLM，取回一个 JSON 动作，执行，把结果追加到历史里。
2. **LLM 怎么被约束成 agent**：通过 system prompt 告诉模型"你只能输出 JSON 对象"，从而把开放式对话变成一个可控的决策系统。
3. **工具层怎么抽象**：所有工具返回统一的 `{"ok": ..., ...}` 结构，主循环不用关心每个工具的内部细节。

## 执行流程

一次典型运行的长这样：

```
用户: python main.py "把 README 里的 claude 改成 Claude"

   main.py                agent.py              llm.py             tools.py
      │                       │                    │                   │
      ├─ task ───────────────▶│                    │                   │
      │                       ├─ history ─────────▶│                   │
      │                       │                    ├─ POST /messages   │
      │                       │                    │   (system prompt  │
      │                       │                    │   + task as JSON) │
      │                       │                    │                   │
      │                       │                    │◀─ {"action":      │
      │                       │                    │    "read_file",   │
      │                       │                    │    "path":"..."}  │
      │                       │                    │                   │
      │                       │                    │                   │
      │                       ├─── read_file() ──────────────────────▶│
      │                       │◀── {"ok":true,"content":"..."} ──────│
      │                       │                    │                   │
      │                       ├─ (再次调 LLM，history 里多了          │
      │                       │    上一步的决策和结果)                  │
      │                       │                    │                   │
      │                       │                    ├─ {"action":       │
      │                       │                    │    "write_file",  │
      │                       │                    │    ...}           │
      │                       │                    │                   │
      │                       ├─── write_file() ─────────────────────▶│
      │                       │◀── {"ok":true,"bytes_written":...} ──│
      │                       │                    │                   │
      │                       │                    ├─ {"action":       │
      │                       │                    │    "finish",      │
      │                       │                    │    "summary":"..."}│
      │                       │                    │                   │
      │◀── "Agent finished" ──│                    │                   │
```

### 流程中的关键点

**System prompt 是 agent 的"宪法"**（`llm.py:8-28`）。它规定了模型只能输出 JSON、只能从 5 种 action 中选一种、遵循哪些规则。没有这个 prompt，模型会自由发挥，无法驱动工具执行。

**历史是 agent 的"短期记忆"**（`agent.py:36`）。history 列表里装了 task + 每一轮的 decision + result。整个列表序列化成 JSON 塞进 user message。模型通过这个列表了解"任务是什么、我之前做了什么、结果是什么、下一步该做什么"。

**工具返回统一结构**（`tools.py`）。无论哪个工具，都返回 `ok` 字段表示成败。这让主循环的 `execute_tool()` 不需要 if-else 分支处理不同类型的结果。

## 代码导读

建议按这个顺序读，这个顺序也是依赖链条的反方向：

### 1. `llm.py` — LLM 边界

| 关注点 | 行号 | 为什么重要 |
|--------|------|-----------|
| `SYSTEM_PROMPT` | 8-28 | 这是唯一约束模型行为的地方。试想删掉它会怎样？ |
| `extract_json_object()` | 47-74 | JSON 解析的鲁棒性：先尝试直解，失败则从头扫描 `{` 或 `[`。为什么要两次？ |
| `build_model_request()` | 77-95 | 整个 history 序列化成 JSON 作为一条 user message。注意没有 assistant 角色 —— 这是故意的简化。 |
| `call_model()` | 99-138 | 用的是标准库 `urllib`，没有框架依赖。如果你要换 `httpx` 或 `requests`，改这里就行。 |

### 2. `tools.py` — 工具层

| 关注点 | 行号 | 为什么重要 |
|--------|------|-----------|
| `ensure_workspace_path()` | 10-15 | 安全边界：所有路径操作都先检查是否在工作区内。 |
| `truncate_output()` | 18-22 | 防上下文爆炸：超过 4000 字符的结果会被截断。 |
| `TOOLS` 字典 | 100-104 | 这是 agent 的"能力注册表"。新增工具只需在这里加一行。 |
| `run_command()` | 79-97 | 使用 `shell=True`，教学便利但危险 —— V5 会处理这个问题。 |

### 3. `agent.py` — 主循环

| 关注点 | 行号 | 为什么重要 |
|--------|------|-----------|
| `run_agent()` | 25-63 | 整个 agent 的核心。函数体只有 30 行，但表达了完整的 observe-decide-act 循环。 |
| `execute_tool()` | 11-22 | 从 decision 里拆出 action 和参数，分发给对应工具。 |

### 4. `main.py` — CLI 入口

| 关注点 | 行号 | 为什么重要 |
|--------|------|-----------|
| `parse_args()` | 19-25 | `task` 是必传的位置参数。这是 V1 的标志性特征：一次只能跑一个任务。 |
| `main()` | 39-52 | 只调用一次 `run_agent()` 就结束，没有交互循环。 |

## 这个版本刻意不做什么

理解这些"不做"和"做了什么"同样重要：

- **没有多轮交互**。一次任务一次进程，做完就退出。如果你想继续，得重新启动。
- **没有持久化**。关闭进程后，对话历史全部丢失。
- **整文件覆写**。`write_file` 替换整个文件内容，而不是做 diff 编辑。
- **没有安全检查**。`run_command` 使用 `shell=True`，信任所有命令。
- **没有流式输出**。等模型完全返回后才解析。

每个"不做"都是一个学习点，会在后续版本中逐步解决。

## 跑一下试试

```bash
cd versions/v1-single-turn
export ANTHROPIC_API_KEY=your_key
python main.py "read main.py and explain what this project does"
```

观察输出：你会看到每一步的 decision（模型想干什么）和 result（工具返回了什么），直到 `action: finish`。

## 下一步 → V2

V1 跑完一次就退出了，每次都要重新启动进程。V2 解决了这个问题：只改 `main.py` 一个文件，把一次性执行变成持续交互。去看 [`versions/v2-multi-turn/README.md`](../v2-multi-turn/README.md)。
