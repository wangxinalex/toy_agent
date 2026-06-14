# V5 — 补丁式编辑

> V4 的 `write_file` 每次修改都要输出完整文件内容。V5 新增 `apply_patch` 工具，只替换一小段文本，省 token 也更安全。

**改动速览**：`tools.py` 新增 `apply_patch` 函数，`llm.py` 更新 system prompt。`agent.py` 和 `main.py` 不变。

---

## 1. 上一个版本哪里不够好

V4 的 `write_file` 是"整文件覆写"：模型想改一行代码，必须把整个文件重新输出一遍。

问题：
- **浪费 token**：一个 200 行的文件改 1 行，模型要输出 200 行内容。
- **容易出错**：模型可能在重新输出时遗漏某些行、改错缩进、或引入无关改动。
- **上下文膨胀**：完整的文件内容塞进 history，后续每一轮都要重新发送。

**所有成熟的 coding agent 都用补丁/差异编辑**：Claude Code 的 Edit 工具用 old_string/new_string；Cursor 用 diff-based 编辑；Aider 用 search/replace blocks。V5 引入同样的思路。

## 2. 涉及哪些新概念

| 需要知道 | 一句话解释 |
|---------|-----------|
| `str.count()` | 统计子串出现次数，用来检测 old_snippet 是否唯一 |
| `str.replace(old, new, 1)` | 只替换第一次出现，避免歧义 |
| 精确匹配 | old_snippet 必须和文件内容完全一致（包括缩进、换行） |

**不需要知道**：diff 算法、AST 解析、正则表达式。V5 用的就是最朴素的字符串替换。

## 3. 怎么落地到代码

### 3.1 变化一：tools.py — 新增 apply_patch

```python
def apply_patch(path: str, old_snippet: str, new_snippet: str) -> dict[str, Any]:
    target = ensure_workspace_path(path)
    if not target.exists():
        return {"ok": False, "error": f"File not found: {path}"}

    content = target.read_text()
    count = content.count(old_snippet)

    if count == 0:
        return {"ok": False, "error": "old_snippet not found in file"}
    if count > 1:
        return {"ok": False, "error": f"old_snippet appears {count} times, expected 1"}

    new_content = content.replace(old_snippet, new_snippet, 1)
    target.write_text(new_content)
    return {"ok": True, "path": path, "bytes_written": len(new_content.encode("utf-8"))}
```

**三个错误分支**：
1. `old_snippet` 不存在 → 模型可能引用了错误的内容
2. `old_snippet` 出现多次 → 替换哪一处有歧义，拒绝操作
3. 恰好 1 次 → 安全替换

### 3.2 变化二：llm.py — 更新 system prompt

在 Available actions 中添加：
```
- apply_patch: {"action":"apply_patch","path":"relative/path.py","old_snippet":"exact existing text","new_snippet":"replacement text"}
```

更新 Rules：
```
- When editing an existing file, use apply_patch instead of write_file.
- Only use write_file when creating a new file or rewriting an entire file.
- old_snippet must be an exact substring of the file content (including indentation).
- old_snippet must appear exactly once in the file to avoid ambiguity.
```

### 3.3 不变的部分

- **agent.py**：`execute_tool` 从 `TOOLS` 字典分发，新增的 `apply_patch` 自动注册，无需改动。
- **main.py**：CLI 和 session 管理逻辑与编辑方式无关，无需改动。

### 3.4 文件结构

```
versions/v5-patch-editing/
├── agent.py            ← 不变
├── main.py             ← 不变
├── llm.py              ← 更新 system prompt
├── tools.py            ← 新增 apply_patch
└── sessions/           ← 自动生成
```

### 3.5 和 V4 的关键差异

```
                    V4                          V5
编辑方式            write_file 覆写整个文件      apply_patch 替换局部片段
token 消耗          高（输出完整文件）           低（只输出新旧片段）
出错风险            高（重写可能遗漏/改错）      低（精确匹配再替换）
system prompt       4 个 action                 5 个 action
tools.py            4 个工具                    5 个工具
```

## 4. 为什么这样做而不是那样

**问：为什么用简单的 `str.replace` 而不是 diff/patch 算法？**

教学优先。`str.replace` 一行代码就能表达核心思想：找到旧文本、替换成新文本。diff 算法（unified diff、Myers 算法）更强大，但引入的复杂度和教学目标不符。等到了"真正可用"的阶段再考虑。

**问：为什么限制 old_snippet 只能出现 1 次？**

安全兜底。如果 old_snippet 在文件中出现 3 次，模型没有指明替换哪一处，`str.replace` 会全部替换——这几乎不是用户想要的。返回错误让模型提供更精确的片段，比静默替换更安全。

**问：为什么不顺便删掉 write_file？**

`write_file` 仍有用武之地：创建新文件、或需要完全重写一个文件时。V5 的规则是"编辑用 apply_patch，新建用 write_file"，两者共存。

## 5. 跑起来看看

```bash
cd versions/v5-patch-editing
export ANTHROPIC_API_KEY=your_key

# 1) 让 agent 用 apply_patch 修改一个文件
python main.py "in tools.py, change the truncate_output default limit from 4000 to 8000"
# 观察：模型应该读取文件 → 用 apply_patch 精确替换 → run_command 验证

# 2) 对比 V4 的行为
cd ../v4-session-persistence
python main.py "in tools.py, change the truncate_output default limit from 4000 to 8000"
# 观察：模型用 write_file 重写整个文件
```

**体验改进**：编辑操作更快、更精确、消耗更少的 token。Agent 从"整文件打印机"进化为"精确外科医生"。

**仍然不够**：命令无限制（→ V6 安全）；无自动验证（→ V7 验证闭环）。

---

[下一版本：V6 命令安全 → 路线图](../../docs/TOY_TO_USABLE_ROADMAP.md)
