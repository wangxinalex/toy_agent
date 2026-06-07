# Toy Agent — 一步步搭建一个编程 Agent

这是一个**教学项目**，用最少的代码展示一个 coding agent 是如何从零搭建起来的。

> 接收任务 → 发给 LLM → 模型返回 JSON 动作 → 执行本地工具 → 结果喂回模型 → 循环直到完成

## 学习路径

按版本顺序阅读，**每个版本只引入极少的变化**：

```
V1 (单轮闭环) → V2 (多轮交互) → V3 (流式+消息) → V4 (会话持久化) → V5+ (规划中)
```

| 版本 | 命题 | 改了什么 |
|------|------|---------|
| V1 | 最小闭环：一个 agent 怎么跑起来 | 全部（初始） |
| V2 | 交互模式：怎么保持会话 | 只改 `main.py` |
| V3 | 流式输出 + 消息结构 | 重写 `llm.py`，微调 `agent.py` |
| V4 | 会话持久化：关闭再打开，对话还在 | 重写 `main.py`，微调 `agent.py` |
| V5+ | 补丁编辑 / 命令安全 / 自动验证 | 见[路线图](docs/TOY_TO_USABLE_ROADMAP.md) |

**建议所有学习者从 V1 开始。**

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
                 │ 本地工具  │
                 └──────────┘
                       │
                       ▼
              工具结果追加到历史，下一轮
```

| 模块 | 职责 | 核心问题 |
|------|------|---------|
| `main.py` | 启动、读配置、调度 agent、session 管理 | 用户怎么交互？ |
| `agent.py` | observe → decide → act 循环 | agent 怎么一步步完成任务？ |
| `llm.py` | 构造请求、流式 SSE 解析、提取 JSON | 怎么和 LLM 对话并控制输出？ |
| `tools.py` | 文件读写、文本搜索、命令执行 | agent 能对本地环境做什么？ |

## 项目结构

所有可运行代码在 `versions/` 目录里。根目录只有文档。

```
toy_agent/
├── README.md
├── CLAUDE.md
├── docs/
│   └── TOY_TO_USABLE_ROADMAP.md
└── versions/
    ├── INDEX.md
    ├── v1-single-turn/
    ├── v2-multi-turn/
    ├── v3-streaming-messages/
    └── v4-session-persistence/
```

## 快速开始

```bash
# 1. 设置 API key
export ANTHROPIC_API_KEY=your_deepseek_key

# 2. 进入最新版本
cd versions/v4-session-persistence

# 3. 安装依赖
pip install python-dotenv

# 4. 带任务启动（流式输出，逐 token 实时显示）
python main.py "read main.py and explain what this project does"

# 5. 或交互模式
python main.py
# You> 帮我看看这个项目有哪些文件
# You> exit

# 6. 下次回来恢复上次的对话
python main.py --resume <session-id>
python main.py --list-sessions
```

默认使用 DeepSeek 的 Anthropic 兼容接口。切换模型：

```bash
export ANTHROPIC_BASE_URL="https://api.anthropic.com/v1/messages"
export ANTHROPIC_MODEL="claude-sonnet-4-6"
```

## 设计原则

- **每个版本只改最少代码**。V1 → V2 只动了 `main.py`；V3 主改 `llm.py`；V4 主改 `main.py`。
- **每个版本独立可运行**。`cd` 进去就能跑，互不依赖。
- **代码即文档**。关键函数有注释，变量名刻意直白，结构刻意扁平。
- **版本是目录快照**。横向对比文件用目录，纵向追踪变更用 Git。

## 阅读导航

| 你在找什么 | 去这里 |
|-----------|--------|
| 所有版本一句话概览 | [`versions/INDEX.md`](versions/INDEX.md) |
| V1-V4 每个版本的深度讲解 | `versions/v*/README.md` |
| V5+ 演进计划 | [`docs/TOY_TO_USABLE_ROADMAP.md`](docs/TOY_TO_USABLE_ROADMAP.md) |
| Git 规范 & 项目说明 | [`CLAUDE.md`](CLAUDE.md) |
