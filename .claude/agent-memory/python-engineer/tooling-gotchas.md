---
name: tooling-gotchas
description: Bash hook blocks some read-only shell combos and heredocs; dash escapes get turned into literal dashes; ruff SIM905
metadata:
  type: project
---

- A PreToolUse Bash hook ("the main session owns git and PRs") also blocked read-only
  compound commands (a `for ... cat` loop over files, `git diff` with a `':!uv.lock'`
  pathspec, `cat .github/...`, a `cat > file <<EOF` heredoc). **How to apply:** read files
  with the Read tool, write scratch scripts with Write, keep git commands simple.
- `–` / `—` escapes written into Python files came out as literal en/em dashes
  (ruff RUF001 caught it). **How to apply:** after writing code or tests that mention
  dashes, grep for `[\x{2013}\x{2014}]` and fix with
  `sed -i 's/\xe2\x80\x93/\\u2013/g; s/\xe2\x80\x94/\\u2014/g'`.
- `ruff check --fix` (SIM905) rewrites `"a b c".split()` into a list literal, which
  `ruff format` then explodes one item per line; just write the set/list directly.
