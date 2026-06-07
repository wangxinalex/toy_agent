# Toy Agent — 一步步搭建一个编程 Agent

这是一个**教学项目**，用最少的代码展示一个 coding agent 是如何从零搭建起来的。

整个项目只有 4 个模块、约 200 行核心逻辑，但它演示了 coding agent 的关键机制：

> 接收任务 → 发给 LLM → 模型返回 JSON 动作 → 执行本地工具 → 结果喂回模型 → 循环直到完成

## 学习路径

这个项目按版本演进，**每个版本只引入极少的变化**，方便对比和理解每一次改动的原因。

```
V1 (单轮对话)  →  V2 (多轮交互)  →  V3 (会话持久化, 规划中)  →  ...
```

**建议所有学习者从 V1 开始**，理解最小闭环之后再往上看：

| 你要学什么 | 去哪里 |
|-----------|--------|
| agent 的完整数据流和核心机制 | [`versions/v1-single-turn/`](versions/v1-single-turn/) |
| V1 → V2 改了什么、为什么改 | [`versions/v2-multi-turn/`](versions/v2-multi-turn/) |
| 所有版本的快速定位 | [`versions/INDEX.md`](versions/INDEX.md) |
| 未来的演进计划 | [`docs/TOY_TO_USABLE_ROADMAP.md`](docs/TOY_TO_USABLE_ROADMAP.md) |

每个版本目录里都有独立的 README，解释**这个版本做了什么、为什么这样改、关键代码在哪、还有哪些局限**。

## 架构：4 个模块，各司其职

```
用户输入 (task)
    │
    ▼
┌──────────┐     ┌──────────┐     ┌──────────┐
│  main.py │ ──▶ │ agent.py │ ──▶ │  llm.py  │
│ CLI 入口 │     │ 主循环    │     │ API 通信  │
└──────────┘     └──────────┘     └──────────┘
                       │                │
                       ▼                │
                 ┌──────────┐           │
                 │ tools.py │ ◀─────────┘
                 │ 本地工具  │    (模型返回 JSON action)
                 └──────────┘
                       │
                       ▼
                工具执行结果追加到历史，进入下一轮
```

| 模块 | 职责 | 回答的核心问题 |
|------|------|--------------|
| `main.py` | 启动、读配置、调度 agent | 用户怎么与 agent 交互？ |
| `agent.py` | observe → decide → act 循环 | agent 怎么一步步完成任务？ |
| `llm.py` | 构造请求、解析响应、提取 JSON 动作 | 怎么和 LLM 对话并控制输出格式？ |
| `tools.py` | 提供文件读写、搜索、命令执行 | agent 能对本地环境做什么？ |

**建议阅读顺序**：`llm.py` → `tools.py` → `agent.py` → `main.py`

先理解 LLM 怎么交互、工具有哪些，再看 agent 怎么把两者串起来，最后看 CLI 怎么启动整个流程。

## 项目结构

这个仓库本身不包含源码——所有可运行代码都在 `versions/` 目录里。根目录只有教学文档。

```
toy_agent/
├── README.md                  ← 你正在读的课程大纲
├── docs/
│   └── TOY_TO_USABLE_ROADMAP.md
└── versions/
    ├── INDEX.md               ← 版本快速导航
    ├── v1-single-turn/        ← V1 完整代码（含 pyproject.toml）
    └── v2-multi-turn/         ← V2 完整代码（含 pyproject.toml）
```

## 快速开始

```bash
# 1. 设置 API key（需要 DeepSeek 账号）
export ANTHROPIC_API_KEY=your_deepseek_key

# 2. 进入最新版本目录
cd versions/v2-multi-turn

# 3. 安装依赖
pip install python-dotenv

# 4. 带着第一个任务启动
python main.py "read main.py and explain what this project does"

# 5. 或者进入交互模式，自由探索
python main.py
# You> 帮我看看这个项目有哪些文件
# You> exit
```

默认使用 DeepSeek 的 Anthropic 兼容接口。如果你想用真正的 Anthropic API，设置：

```bash
export ANTHROPIC_BASE_URL="https://api.anthropic.com/v1/messages"
export ANTHROPIC_MODEL="claude-sonnet-4-6"
```

## 设计原则

- **每个版本只改最少代码**。V1 → V2 只动了 `main.py` 一个文件，其余模块一行未改。
- **每个版本独立可运行**。`versions/` 下每个目录都是完整快照，可以直接 `cd` 进去跑。
- **代码即文档**。关键函数有注释，变量名和结构刻意保持直白，避免过度抽象。
- **版本是目录，Git 是补充**。目录快照方便横向对比文件，Git 历史方便追踪每次 commit。
