# 版本索引

这个文档是各版本的快速导航。建议按 V1 → V2 → V3 → V4 → V5 → V6 → V7 → V8 的顺序阅读。

## 版本总览

| 版本 | 目录 | 核心命题 | 改了哪些文件 |
|------|------|---------|-------------|
| V1 | [`v1-single-turn/`](v1-single-turn/) | 最小闭环：一个 agent 怎么跑起来 | 全部（初始版本） |
| V2 | [`v2-multi-turn/`](v2-multi-turn/) | 交互模式：怎么保持会话不断开 | 只改了 `main.py` |
| V3 | [`v3-streaming-messages/`](v3-streaming-messages/) | 流式输出 + 消息结构 | 改了 `llm.py` 和 `agent.py` |
| V4 | [`v4-session-persistence/`](v4-session-persistence/) | 会话持久化：关闭再打开，对话还在 | 改了 `main.py` 和 `agent.py` |
| V5 | [`v5-patch-editing/`](v5-patch-editing/) | 补丁式编辑：精确替换，不重写整个文件 | 改了 `tools.py` 和 `llm.py` |
| V6 | [`v6-command-safety/`](v6-command-safety/) | 命令安全：白名单 + 危险模式拦截 + 超时 | 改了 `tools.py` 和 `llm.py` |
| V7 | [`v7-verify-loop/`](v7-verify-loop/) | 自动验证闭环：修改代码后必须验证通过才能 finish | 改了 `agent.py` 和 `llm.py` |
| V8 | [`v8-error-recovery/`](v8-error-recovery/) | 错误恢复：连续失败自动跳过 | 改了 `agent.py` |

## V1 — 单轮对话

**路径**：[`versions/v1-single-turn/`](v1-single-turn/)

**一句话**：接收一个任务，完成它，退出。这是 coding agent 的"最小可运行单元"。

**怎么跑**：
```bash
cd versions/v1-single-turn
python main.py "read main.py and explain what this project does"
```

## V2 — 多轮交互

**路径**：[`versions/v2-multi-turn/`](v2-multi-turn/)

**一句话**：在 V1 基础上只改 `main.py`，把一次性执行变成持续对话。

**怎么跑**：
```bash
cd versions/v2-multi-turn
python main.py
# You> 看看这个项目有哪些文件
# You> exit
```

## V3 — 流式输出 + 消息结构

**路径**：[`versions/v3-streaming-messages/`](v3-streaming-messages/)

**一句话**：模型边想边输出；消息结构从"全塞进一条 user message"改为 user/assistant 交替。

**怎么跑**：
```bash
cd versions/v3-streaming-messages
python main.py "read main.py and explain what this project does"
```

## V4 — 会话持久化

**路径**：[`versions/v4-session-persistence/`](v4-session-persistence/)

**一句话**：对话历史保存到 `sessions/` 目录，下次启动 `--resume` 恢复。

**怎么跑**：
```bash
cd versions/v4-session-persistence
python main.py "read main.py"                      # 新会话，自动保存
python main.py --resume 20260607-NNNNNN            # 恢复旧会话
python main.py --list-sessions                     # 列出所有会话
```

## V5 — 补丁式编辑

**路径**：[`versions/v5-patch-editing/`](v5-patch-editing/)

**一句话**：新增 `apply_patch` 工具，编辑文件时只替换局部片段，不再重写整个文件。

**怎么跑**：
```bash
cd versions/v5-patch-editing
python main.py "in tools.py, change the truncate_output default limit from 4000 to 8000"
```

## V6 — 命令安全

**路径**：[`versions/v6-command-safety/`](v6-command-safety/)

**一句话**：白名单只允许安全命令，危险模式拦截 `rm -rf`/`curl`/`sudo`，加 30 秒超时。

**怎么跑**：
```bash
cd versions/v6-command-safety
python main.py "run pytest and tell me the result"
```

## V7 — 自动验证闭环

**路径**：[`versions/v7-verify-loop/`](v7-verify-loop/)

**一句话**：修改代码后必须运行验证命令，验证失败则修正再验证，循环直至通过才能 finish。

**怎么跑**：
```bash
cd versions/v7-verify-loop
python main.py "create hello.py with print('hello'), then verify it runs correctly"
```

## V8 — 错误恢复

**路径**：[`versions/v8-error-recovery/`](v8-error-recovery/)

**一句话**：同一操作连续失败 3 次后自动跳过，避免 agent 陷入死循环。

**怎么跑**：
```bash
cd versions/v8-error-recovery
python main.py "read main.py and explain what this project does"
```

## 学习建议

1. **先跑起来**。每个版本都花 5 分钟实际跑一次，感受差异。
2. **先读 README，再读代码**。README 解释"为什么"，代码解释"怎么做"。
3. **对比着读**。把相邻版本的改动文件并列打开（`diff v3/agent.py v4/agent.py`），差异一目了然。
4. **问自己问题**。每个版本都在"为什么不直接做 X？"和"现有写法有什么局限？"上留了思考空间。
