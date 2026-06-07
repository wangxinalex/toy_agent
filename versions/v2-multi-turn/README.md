# V2 — 多轮交互 · 保持会话

V2 在 V1 的基础上只改了一个文件（`main.py`），把"一次任务一次进程"变成了"持续对话直到你主动退出"。

## V1 → V2 改了什么

**只有 `main.py` 变了。** `agent.py`、`llm.py`、`tools.py` 和 V1 完全一致，一行未改。

### 为什么改 main.py

V1 的问题不是 agent 循环本身有问题，而是 **CLI 的交互模式太原始**：每执行一个任务就要重启进程、重新加载模型、丢失上下文。这体验很差，也不像真实的 coding assistant。

解决思路很简单：在 `main()` 里加一个 `while True`，首轮任务执行完后不要退出，继续等待下一个输入。

### 三处变化

```python
# 变化 1: task 从必传 → 可选
# V1:
parser.add_argument("task", help="What the agent should do.")
# V2:
parser.add_argument("task", nargs="?", help="Optional first task to run.")

# 变化 2: main() 加了交互循环
# V1:
args = parse_args()
api_key = require_api_key()
run_agent(args.task, ...)          # 执行一次即退出

# V2:
args = parse_args()
api_key = require_api_key()
pending_task = args.task           # 可能是 None

while True:
    if pending_task is None:
        user_input = input("\nYou> ").strip()
        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit", "q"}:
            print("Bye.")
            break
        pending_task = user_input

    run_agent(pending_task, ...)
    pending_task = None             # 重置，下一轮等待输入
```

### 为什么要用 `pending_task` 这个变量

它是"待处理任务"的缓冲区。两种来源：

1. **命令行参数**：`python main.py "review agent.py"`，启动时 `args.task` 有值，先执行这个。
2. **交互输入**：首轮结束后 `pending_task = None`，`while` 循环进入等待状态，用户输入下一轮任务。

这个设计让 **"首次任务"和"后续任务"走同一条执行路径**（都经过 `run_agent()`），而不是写两套逻辑。

## 哪些没变，为什么这很重要

`agent.py`、`llm.py`、`tools.py` 和 V1 逐行完全一致。

这说明：**从单轮到多轮，agent 的核心机制不需要任何改动。** agent 的"观察-决策-执行"循环天然支持继续工作——你只要继续喂 task 给它就行。V1 做不了多轮纯粹是 CLI 代码没给机会，不是 agent 没这个能力。

这也是模块化设计的好处：交互方式（`main.py`）和 agent 循环（`agent.py`）是独立的关注点，改一个不影响另一个。

## 代码导读

如果你已经读过 V1，只需要关注 `main.py` 的变化：

| 关注点 | 行号 | 思考题 |
|--------|------|--------|
| `nargs="?"` | 24 | 为什么用 `?` 而不是 `*`？两者的行为差异是什么？ |
| `while True` | 46 | 这个循环为什么放在 `main()` 而不是 `run_agent()` 里？ |
| `pending_task = None` | 63 | 如果忘了这一行，会发生什么 bug？ |

## 体验一下

```bash
cd versions/v2-multi-turn
export ANTHROPIC_API_KEY=your_key
python main.py
# You> 看看这个项目有哪些文件
# You> 在 tools.py 里写清楚每个函数的用途
# You> exit
```

和 V1 对比着跑一遍：先跑 V1 做两个任务（需要启动两次），再跑 V2 做同样的两个任务（一次启动搞定）。感受一下 CLI 交互的差异。

## 这个版本仍然不做什么

V2 只解决了交互模式，这些限制还在：

- **重启丢失上下文**。虽然一个 session 内可以多轮对话，但关掉进程历史就没了。
- **仍然是整文件覆写**。没有补丁级编辑。
- **命令执行仍无限制**。`shell=True` 的风险和 V1 一样。
- **没有历史长度控制**。多轮对话下 history 会一直增长直到超出模型上下文窗口。

## 下一步 → V3

V2 让你可以持续对话了，但关掉进程一切清零。V3 要解决的是**会话持久化**：把对话历史保存到文件，下次启动时恢复。详见 [`docs/TOY_TO_USABLE_ROADMAP.md`](../../docs/TOY_TO_USABLE_ROADMAP.md)。
