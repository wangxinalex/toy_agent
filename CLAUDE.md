# Toy Agent 项目说明

这是一个教学项目，用最少的代码展示 coding agent 如何从零搭建。所有可运行代码在 `versions/` 目录下，按 V1 → V2 → V3 版本演进。

- 每个版本目录独立可运行，只引入最少的变化。
- 版本对照见 `versions/INDEX.md`，演进计划见 `docs/TOY_TO_USABLE_ROADMAP.md`。
- 代码注释使用中文，文档使用中文。

## Git 规范

### Commit 格式

使用 conventional commits：`<type>(<scope>): <subject>`

允许的 type：`feat` `fix` `docs` `chore` `refactor` `test` `perf` `build` `ci` `revert`

示例：
- `feat(v3): add streaming SSE parsing to llm.py`
- `docs(v1): rewrite README with code reading guide`
- `refactor(tools): extract ensure_workspace_path helper`

### 分支规范

- 禁止在 `main` 或 `master` 上直接 commit/push。
- 当前分支如果是 `main`/`master`，先切到新分支再提交。
- 分支名格式：`<type>/<kebab-case-description>`
  - 如 `feat/v3-streaming`, `docs/add-version-index`, `fix/cli-arg-parse`
- 只允许小写字母、数字、连字符。建议不超过 48 字符。

### 提交流程

1. commit 前运行 `python -m compileall .` 验证代码至少能通过语法检查。
2. 不跳过 git hooks（不用 `--no-verify`、`--no-gpg-sign`）。
3. 不 amend 已发布的 commit，除非明确要求。
4. push 到 feature 分支（非 main/master）。
5. push 成功后用 `gh pr create` 创建 PR。
