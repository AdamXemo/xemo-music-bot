---
name: agent-design-lessons
description: Repo-specific lessons for designing subagents in xemo-music-bot (settled decisions in ADRs, read-only vs editing tooling, git-blocking hooks, orchestrator team model, interview-first relay pattern, roster/changelog habits)
metadata:
  type: project
---

- Settled decisions live only in Accepted ADRs (`docs/adr/`) plus the AGENTS.md "Never" list. Owner decided 2026-10-10 that agents must rely on ADRs alone - do not restate decisions in agent prompts; point at the ADRs.
  **Why:** restated copies go stale; "search by track name only" was moved into ADR 0002 for this reason.
  **How to apply:** if a needed decision isn't in an ADR, recommend adding it to one instead of copying it into the agent.
- Read-only agents here get no Bash: frontmatter cannot restrict Bash to specific commands (a `Bash(...)` specifier in disallowedTools removes Bash entirely), and `memory` silently grants Write/Edit, so read-only agents must not use `memory`.
  **How to apply:** for staleness checks, use Glob/Grep over files instead of git commands.
- Editing agents that need Bash but must not touch git: block commands with frontmatter `hooks.PreToolUse` entries using `if: "Bash(git push *)"` + `exit 2` (one rule per `if`; best-effort, backs up the prompt). Used in `python-engineer`.
- `isolation: worktree` branches from the default branch, not the caller's HEAD, so it is wrong for agents that work on a feature branch the main session prepared; leave it per-invocation.
- Team model since 2026-10-10: main session = orchestrator (item, branch, git, PRs); `python-engineer` implements; owner wants one specialised agent per big task type, roles must not overlap (CI/Docker has no owner yet).
- Writing-style rule bites agent files too: no literal em/en dashes even inside grep patterns; use `\x{2013}|\x{2014}`.
- Owner wants interview-first agents (asked for `ux-designer`, 2026-10-10). Subagents never get `AskUserQuestion` (stripped even if listed), so the pattern is: agent returns questions formatted 1:1 for `AskUserQuestion` (batches of 4, 2-4 options, recommended first, header <= 12 chars), main session relays, then resumes the agent via `SendMessage` or re-runs it with answers. Listing `AskUserQuestion` in `tools` is harmless and makes `claude --agent <name>` live interviews work. Cap rounds (2) and record answers in versioned docs, not agent memory.
- Background subagents (default in interactive sessions) keep Read/Grep/Glob/Edit/Write/WebFetch/WebSearch, so doc-editing agents work in the background.
- Convention requested 2026-10-10: agent edit + one `### Changed` line in CHANGELOG `Unreleased`; roster row in AGENTS.md updated only if the role meaning changes. Related: [[plan-reviewer-design]]
