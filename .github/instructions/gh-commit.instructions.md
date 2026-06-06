---
description: "Use when creating git commits, pushing to GitHub, opening pull requests, or when users ask to 'commit', 'push', or 'ship'. Enforces safe and consistent commit workflow."
name: "GitHub Commit Workflow"
---
# GitHub Commit Workflow

- This is a repository-level default for this workspace; user explicit instructions always override it.
- Use semantic-release compatible commit messages as the required format: `<type>(optional-scope): <subject>`.
- Allowed commit `type` values should follow conventional commits used by semantic-release (for example: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `perf`, `build`, `ci`, `revert`).
- Keep commit messages short, imperative, and specific to the actual change.
- Never commit or push directly on `main` or `master`.
- If current branch is `main` or `master`, first create and switch to a descriptive branch before any commit or push.
- Branch names must be descriptive and use prefixes such as `feat/<description>`, `fix/<description>`, `chore/<description>`, `docs/<description>`, or `refactor/<description>`.
- Branch `<description>` must use lowercase kebab-case (for example: `add-env-example`, `fix-cli-arg-parse`).
- Branch names may only contain lowercase letters, numbers, and hyphens after the prefix, and must not contain spaces, underscores, uppercase letters, or special symbols.
- Keep full branch names concise and readable; recommended maximum length is 48 characters.
- Before committing, run relevant verification (tests or lint) and summarize failures instead of hiding them.
- Never amend or rewrite history unless the user explicitly asks.
- Never run destructive git commands (for example hard reset or force push) unless the user explicitly approves.
- Prefer pushing to a feature branch instead of `main` unless the user explicitly asks to push `main`.
- When asked to push, confirm target remote and branch before pushing.
- After push, report the branch and what was pushed in one concise summary.
