# V7 — 自动验证闭环

> V6 的 agent 修改代码后直接调用 finish，不会自动验证修改是否正确。V7 在 prompt 层和代码层双保险：强制 agent 修改代码后必须运行验证命令，验证失败则修正再验证，通过后才能 finish。

**改动速览**：`llm.py` 更新 system prompt（新增验证规则），`agent.py` 新增 `verified` 状态标记和 finish 拦截逻辑。`main.py` 和 `tools.py` 不变。

---

## 1. 上一个版本哪里不够好

V6 的 agent 主循环中，只要模型返回 `action: "finish"` 就直接退出：

```python
# V6: finish 无条件执行
if action == "finish":
    summary = decision.get("summary", "No summary provided.")
    print("\nAgent finished:")
    print(summary)
    return summary, history
```

问题：
- **不验证**：模型修改了代码，但不运行测试就声称"完成"。
- **不可信**：summary 是模型自己写的，可能有误（"代码已正确修改"但实际上语法错误）。
- **无闭环**：验证失败后不会自动修正——模型根本不知道验证失败了，因为它没跑验证命令。

**所有成熟的 coding agent 都有验证闭环**：Claude Code 修改文件后自动运行 lint/test；Cursor 的 apply 后会提示用户检查；Aider 支持 auto-test 模式。V7 引入最简版本。

## 2. 涉及哪些新概念

| 需要知道 | 一句话解释 |
|---------|-----------|
| 验证闭环（verify loop） | 修改 → 验证 → 失败则修正 → 再验证，循环直至通过 |
| 状态标记（state flag） | 用一个布尔变量 `verified` 追踪是否已经执行过验证命令 |
| finish 拦截 | 模型想 finish 时，检查 `verified` 标记，未验证则拒绝并注入提示消息 |

**不需要知道**：CI/CD pipeline、test harness、代码覆盖率、AST 静态分析。V7 用 `run_command` 的成功返回作为"验证通过"信号，足够讲清闭环思想。

## 3. 怎么落地到代码

### 3.1 变化一：agent.py — 新增 verified 状态和 finish 拦截

**核心思路**：在主循环中用一个布尔变量 `verified` 追踪是否执行过成功的验证命令。当模型调用 `finish` 时检查这个标记。

```python
# V7：追踪是否执行过验证命令
verified = False

for step in range(1, max_steps + 1):
    decision = call_model(...)
    action = decision.get("action")

    if action == "finish":
        # V7：拦截未验证的 finish
        if not verified:
            print(f"\n  [V7] {VERIFY_REQUIRED_MSG}")
            history.append({"decision": decision, "result": {"ok": False, "error": VERIFY_REQUIRED_MSG}})
            continue  # 不退出，继续循环

        summary = decision.get("summary", "No summary provided.")
        return summary, history

    result = execute_tool(decision)
    history.append({"decision": decision, "result": result})

    # V7：成功的 run_command 视为一次验证
    if action == "run_command" and result.get("ok"):
        verified = True
```

**关键设计**：
- 拦截时不是简单忽略，而是把 finish 决策和错误消息追加到 history。模型在下一轮能看到"你的 finish 被拒绝了，因为还没验证"——这是闭环的关键。
- 成功的 `run_command`（`returncode == 0`）即视为验证通过。不要求特定命令——模型自己判断跑 `compileall` 还是 `pytest`。

### 3.2 变化二：llm.py — 更新 system prompt

旧规则（V6）：
```
- After a write or patch, usually validate with run_command.
```

新规则（V7）：
```
- After any write_file or apply_patch, you MUST run at least one verification command
  (e.g. python -m compileall, pytest, ruff check, mypy) before finishing.
- If verification fails, fix the code and re-verify. Repeat until verification passes.
- Only call finish after at least one successful verification command has been run.
- In your finish summary, include which verification you ran and its result.
```

关键词从 `usually`（建议）变成了 `MUST`（强制）。同时要求模型在 summary 中报告验证结果——方便用户确认。

### 3.3 不变的部分

- **tools.py**：工具实现不变。`run_command` 的安全检查和超时仍由 V6 层负责。
- **main.py**：CLI 和 session 管理不变。

### 3.4 文件结构

```
versions/v7-verify-loop/
├── agent.py            ← 新增 verified 标记 + finish 拦截
├── main.py             ← 不变
├── llm.py              ← 更新 system prompt（验证规则）
├── tools.py            ← 不变
└── sessions/           ← 自动生成
```

### 3.5 和 V6 的关键差异

```
                    V6                          V7
finish 条件        无条件执行                  必须 verified == True
验证追踪            无                          verified 布尔标记
拦截行为            无                          注入错误消息，继续循环
system prompt      "usually validate"          "MUST run verification"
summary            不含验证信息                 要求包含验证结果
```

## 4. 为什么这样做而不是那样

**问：为什么用 `verified` 标记而不是在代码层面强制"最后一次操作必须是 run_command"？**

教学优先。`verified` 标记是最直观的状态机——一个布尔变量，一看就懂。如果改成检查"history 最后一条"，逻辑更复杂（还要排除 history 为空、task entry 干扰等边界情况），但核心思想是一样的。

**问：为什么不用独立的 `verify` action，而复用 `run_command`？**

不引入新 action。模型已经知道 `run_command` 可以跑 `pytest`、`compileall` 等命令，这就是验证。新增 `verify` action 会让 Available actions 变多、system prompt 变长，但教学上没有带来新东西。

**问：如果模型改了代码但跑了一个无关的命令（如 `ls`），算验证通过吗？**

算。`verified = True` 只检查命令是否成功执行，不检查命令内容。这是一个有意的简化——判断"什么命令算验证"是一个难题（`ls` 不算，`compilefile` 算？`pytest -k 无关的测试` 算？），在教学版本中不值得为此增加复杂度。真实产品会用更精细的逻辑。

**问：prompt 层的 MUST 规则和代码层的 verified 拦截，为什么两个都要？**

双保险。prompt 引导模型主动验证（好的行为），代码拦截防止模型跳过验证（兜底）。如果只靠 prompt，stronger models 通常会遵守，但 weaker models 或 edge case 仍可能忽略。如果只靠代码拦截，模型不知道为什么被拦，可能陷入死循环。两者配合最稳。

## 5. 跑起来看看

```bash
cd versions/v7-verify-loop
export ANTHROPIC_API_KEY=your_key

# 1) 让 agent 创建一个 Python 文件并验证它
python main.py "create hello.py with print('hello'), then verify it runs correctly"
# 观察：agent 应该 write_file → run_command python hello.py → finish
# 注意 summary 中应包含验证结果

# 2) 让 agent 修改代码——看它是否先验证再 finish
python main.py "in hello.py, change the print to say 'world', then verify"
# 观察：apply_patch → run_command python hello.py → finish

# 3) 对比 V6 的行为
cd ../v6-command-safety
python main.py "create hello.py with print('hello')"
# 观察：模型可能直接 write_file → finish，不运行验证
```

**体验改进**：agent 不再"改完就跑"，而是"改完 → 验证 → 通过才结束"。从"裸改"到"改验一体"。

**仍然不够**：没有文件级 diff 展示（→ V8？）；没有错误重试上限（→ V8？）；验证命令只是"成功执行"而非语义正确。

---

[路线图 → docs/TOY_TO_USABLE_ROADMAP.md](../../docs/TOY_TO_USABLE_ROADMAP.md)
