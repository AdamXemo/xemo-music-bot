---
name: tooling-gotchas
description: Bash hook blocks some read-only shell combos; .env.example missing despite docs mentioning it
metadata:
  type: project
---

- A PreToolUse Bash hook ("the main session owns git and PRs") also blocked read-only
  compound commands (a `for ... cat` loop over files, `git diff` with a `':!uv.lock'`
  pathspec, `cat .github/...`). **How to apply:** read files with the Read tool and keep
  git commands simple (`git status --short`, `git diff --stat`).
- As of 2026-10-10 `.env.example` is not in the repo even though `config.py` and CHANGELOG
  reference it; check before telling the owner to copy it.
