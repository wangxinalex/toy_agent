# V8 设计：错误恢复（重试上限）

日期：2026-06-25

## 背景

V7 的 agent 主循环中，工具调用失败后模型只收到一个 `{"ok": false, "error": "..."}` 然后继续下一步。模型可以无限重试同一个失败操作，浪费 token，直到 `max_steps` 耗尽。

## 目标

在 `agent.py` 中增加重试上限机制：同一操作连续失败 N 次后，注入跳过提示，agent 继续运行。

## 设计决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 功能范围 | 仅重试上限（不含错误反馈增强） | 最小增量，符合项目原则 |
| 达到上限后行为 | 跳过并继续 | 符合"恢复"理念，不浪费后续步骤 |
| "同一操作"判定 | action + path 匹配 | 比全参数匹配更实用，比仅 action 匹配更精确 |
| 最大重试次数 | 3 次 | 经验值：足够给模型调整空间，又不会浪费太多 token |

## 改动范围

仅改 `versions/v8-error-recovery/agent.py`，约 20 行新增代码。

## 具体设计

### 新增常量

```python
MAX_CONSECUTIVE_FAILURES = 3
```

### 新增状态变量

在 `run_agent` 函数的循环外：

```python
failure_counts: dict[tuple[str, str], int] = {}
```

key 为 `(action, path)` 元组，value 为连续失败次数。

### 循环内逻辑

在 `execute_tool()` 调用之后、`history.append()` 之前：

1. 提取 key：
   - `action` = `decision.get("action")`
   - `path` = `decision.get("path", "")`（`run_command` 用 `decision.get("command", "")` 替代）
2. 如果 result 失败（`result.get("ok")` 为 False）：
   - 该 key 计数 +1
   - 如果计数 >= `MAX_CONSECUTIVE_FAILURES`：
     - 打印提示：`[V8] Action '{action}' on '{path}' failed {N} times. Skipping.`
     - 注入一条 history entry：`{"decision": decision, "result": {"ok": False, "error": RETRY_LIMIT_MSG}}`（与 V7 的 VERIFY_REQUIRED_MSG 格式一致，模型看到 `ok: False` 会尝试调整策略）
     - 清零该 key 的计数
3. 如果 result 成功：
   - 删除该 key（重置计数）

### 跳过提示消息

```python
RETRY_LIMIT_MSG = (
    "This action has failed {n} consecutive times. "
    "You must try a completely different approach. "
    "Do not retry the same action on the same file."
)
```

### 与 V7 的交互

V7 的 `needs_verification` 逻辑不变。错误恢复和验证闭环是两个独立关注点，互不干扰。

### 边界情况

| 场景 | 行为 |
|------|------|
| 模型换参数重试同一 action+path | 计数器继续累加 |
| 模型先 `read_file` 再 `apply_patch` | 两个 key 独立计数 |
| 达到上限后模型又犯同样的错 | 计数器重新开始（已清零） |
| `run_command` 失败 | `command` 字段作为 path 的替代键 |
| 历史截断（`HISTORY_MAX_ENTRIES`） | 计数器不受影响，它独立于 history |

## 测试计划

新增 `test_error_recovery.py`，覆盖：

1. 同一操作连续失败 3 次后注入跳过提示
2. 失败后成功重置计数器
3. 不同 path 的同一 action 独立计数
4. 达到上限后计数器清零，可以重新开始

## 版本目录

新建 `versions/v8-error-recovery/`，从 V7 复制基础代码，只改 `agent.py`。
