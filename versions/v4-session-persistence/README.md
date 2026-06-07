# V4 — 会话持久化

> V3 关掉进程历史全丢。V4 让对话可以保存到文件、下次启动恢复，就像一个真正的助手。

**改动速览**：`agent.py` 微调（history 参数 + 返回 history），`main.py` 重写（session 管理）。`llm.py` 和 `tools.py` 不变。

---

## 1. 上一个版本哪里不够好

V3 在一个 session 内可以多轮对话，但关掉进程后一切清零。重启时模型完全不记得你之前做过什么、讨论过什么、修改过什么。

**所有主流 agent 都支持持久化**：Claude Code 的对话历史在侧边栏里随时可恢复；ChatGPT 的对话列表跨设备同步；Cursor 的 chat history 在项目里持久保存。没有持久化的 agent 只能做"一次性任务"，不能做"持续项目协作"。

V4 要填的就是这个坑——让 session 在进程退出后还能活过来。

## 2. 涉及哪些新概念

| 需要知道 | 一句话解释 |
|---------|-----------|
| JSON 序列化 | Python 的 dict/list 可以直接 `json.dumps()` 写到文件，`json.loads()` 读回来 |
| 文件 I/O | `Path.write_text()` / `Path.read_text()` — 比 `open()` 更简洁 |
| `datetime` / UTC 时间戳 | 用 UTC 时间做 session ID，避免时区问题 |
| History 截断 | 保留最近 N 条记录，丢弃最早的内容，防止文件无限增长 |

**不需要知道**：数据库（SQLite 等）、ORM、文件锁、并发安全。V4 就是单进程、单文件、同步读写。

## 3. 怎么落地到代码

### 3.1 变化一：agent.py — 接受 history，返回 history

```python
# V3: 只返回 summary 字符串
def run_agent(task, ...) -> str:
    history = [{"task": task}]
    # ... loop ...
    return summary

# V4: 接受可选的 history，返回 (summary, history)
def run_agent(task, ..., history=None) -> tuple[str, list]:
    if history is None:
        history = [{"task": task}]        # 新会话
    else:
        history = history[-40:]           # 截断旧历史
        history.append({"task": task})    # 追加新任务
    # ... loop 不变 ...
    return summary, history
```

**为什么截断 40 条**：40 = 20 轮 decision-result 对。经验上足够保持多轮对话的上下文连贯性，同时控制文件在几十 KB 以内。

### 3.2 变化二：main.py — session 管理四件套

新增四个辅助函数，全部围绕 `sessions/` 目录操作：

```python
generate_session_id()   → "20260607-131200"   # UTC 时间戳
save_session(id, history) → Path              # 写 sessions/<id>.json
load_session(id)          → history           # 读 sessions/<id>.json
list_sessions()           → [Path, ...]       # 列出所有 session 文件
```

新增三个 CLI 参数：

```bash
python main.py                           # 新会话（自动生成 ID）
python main.py --session my-experiment   # 新会话（自定义名称）
python main.py --resume 20260607-131200  # 恢复旧会话
python main.py --list-sessions           # 列出所有已保存的会话
```

### 3.3 保存时机

每次 `run_agent()` 完成后立即保存——不等到进程退出。如果 agent 执行过程中崩溃，至少前面的对话已经落盘了。

```python
summary, history = run_agent(pending_task, ..., history=history)
save_session(session_id, history)  # 立即保存
print(f"[Session saved: sessions/{session_id}.json]")
```

### 3.4 文件结构

```
versions/v4-session-persistence/
├── agent.py            ← 微调：history 参数 + 返回值
├── main.py             ← 重写：session 管理
├── llm.py              ← 不变
├── tools.py            ← 不变
└── sessions/           ← 自动生成
    ├── 20260607-131200.json
    └── 20260607-141530.json
```

### 3.5 和 V3 的关键差异

```
                    V3                          V4
run_agent 签名      (task) -> str               (task, history=None) -> (str, list)
history 生命周期    函数内部创建，函数结束即丢弃   外部传入，函数返回，外部保存到文件
session 管理       无                           CLI 参数 + sessions/ 目录
退出后             历史消失                     历史保留在文件中
```

## 4. 为什么这样做而不是那样

**问：为什么用 JSON 文件而不是 SQLite？**

JSON 文件是人类可直接阅读的。`cat sessions/20260607-131200.json` 就能看到完整对话历史，不需要任何查询工具。V4 的 session 量级（几十个文件、每个几十 KB）也不需要数据库的查询能力。SQLite 留给真正需要它的场景。

**问：为什么保存时机选在每次 run_agent 后，而不是进程退出时？**

防御性设计。如果 agent 崩溃或被 Ctrl+C 强制终止，退出时的保存逻辑可能来不及执行。每次都保存虽然多写几次磁盘，但对话历史比几 KB 的磁盘 IO 贵得多。

**问：为什么 session 文件放在版本目录内（`v4/sessions/`）而不是项目根目录？**

每个版本是独立的教学单元。如果 V4 的 session 写到项目根目录，V5 怎么处理？每个版本管理自己的 session，互不干扰，也方便清理。

## 5. 跑起来看看

```bash
cd versions/v4-session-persistence
export ANTHROPIC_API_KEY=your_key

# 1) 新会话：执行一个任务后退出
python main.py "read main.py and explain the project"
# 观察：终端打印 [Session saved: sessions/20260607-NNNNNN.json]

# 2) 恢复会话：模型记得刚才的事
python main.py --resume 20260607-NNNNNN
# You> 根据刚才读到的内容，写一个简短总结
# 观察：模型引用之前的上下文

# 3) 列表查看
python main.py --list-sessions
# 观察：打印所有已保存的 session 及其包含的任务数

# 4) 自定义会话名
python main.py --session learn-v4 "帮我理解 agent.py 的主循环"
```

**体验改进**：进程重启不再等于"失忆"。Agent 从一个"一次性工具"变成了一个"有记忆的协作伙伴"。

**仍然不够**：整文件覆写（→ V5 补丁编辑）；命令无限制（→ V6 安全）；无自动验证（→ V7 验证闭环）。

---

[下一版本：V5 补丁式编辑 → 路线图](../../docs/TOY_TO_USABLE_ROADMAP.md)
