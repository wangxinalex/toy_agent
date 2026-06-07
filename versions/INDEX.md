# 版本索引

这个文档是各版本的快速导航。如果你想系统学习，建议按 V1 → V2 → V3+ 的顺序阅读。

## 版本总览

| 版本 | 目录 | 核心命题 | 改了哪些文件 |
|------|------|---------|-------------|
| V1 | [`v1-single-turn/`](v1-single-turn/) | 最小闭环：一个 agent 怎么跑起来 | 全部（初始版本） |
| V2 | [`v2-multi-turn/`](v2-multi-turn/) | 交互模式：怎么保持会话不断开 | 只改了 `main.py` |
| V3+ | 待实现 | 见[路线图](../docs/TOY_TO_USABLE_ROADMAP.md) | — |

## V1 — 单轮对话

**路径**：[`versions/v1-single-turn/`](v1-single-turn/)

**一句话**：接收一个任务，完成它，退出。这是 coding agent 的"最小可运行单元"。

**适合谁**：第一次接触 coding agent 概念。

**怎么跑**：
```bash
cd versions/v1-single-turn
python main.py "read main.py and explain what this project does"
```

## V2 — 多轮交互

**路径**：[`versions/v2-multi-turn/`](v2-multi-turn/)

**一句话**：在 V1 基础上只改 `main.py`，把一次性执行变成持续对话。

**适合谁**：已经理解 V1 的数据流，想了解 CLI 交互层怎么设计。

**怎么跑**：
```bash
cd versions/v2-multi-turn
python main.py
# 然后输入: 看看这个项目有哪些文件
# 然后输入: exit
```

## 学习建议

1. **先跑起来**。每个版本都花 5 分钟实际跑一次，看看终端输出长什么样。
2. **先读 README，再读代码**。README 解释"为什么"，代码解释"怎么做"。
3. **对比着读**。V1 和 V2 的 `main.py` 并列打开，三处差异一目了然。
4. **问自己问题**。每个版本都在"为什么不直接做 X？"和"现有写法有什么局限？"这两个方向上留了思考空间。
