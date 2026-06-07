---
description: "Commit and push changes using gh-commit rules, then create a PR and return the PR URL"
name: "gh-commit-and-pr"
argument-hint: "What changed (PR title will be auto-summarized from this input unless explicitly provided)"
agent: "agent"
---
Execute this release workflow in the current repository.

Required policy:
- Follow [gh-commit rules](../instructions/gh-commit.instructions.md) exactly.
- Absolute prohibition: never push directly on main or master under any circumstance.

Task input:
- {{input}}

Workflow:
1. Inspect git status and current branch.
2. If current branch is main or master, create and switch to a descriptive branch such as feat/<description> or fix/<description> using lowercase kebab-case before any commit or push.
3. Run relevant verification before commit (tests or lint where applicable) and report failures clearly.
4. Create semantic-release compatible commit messages in this format: <type>(optional-scope): <subject>.
5. Push only to a non-main/non-master branch; if target is main/master, stop and require branch switch first.
6. After push succeeds, create a PR with GitHub CLI.
7. Generate the PR title by auto-summarizing the user input; if the user explicitly provides a PR title, use that title.
8. Return the PR URL and a concise summary of what was committed and validated.

Output format:
- Branch: <branch>
- Commit(s): <short hashes and subjects>
- Verification: <passed/failed and command>
- PR: <url>
- Notes: <important assumptions or follow-up>
