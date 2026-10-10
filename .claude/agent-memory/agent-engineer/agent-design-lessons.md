---
name: agent-design-lessons
description: Repo-specific lessons for designing subagents in xemo-music-bot (settled decisions outside ADRs, read-only tooling, roster/changelog habits)
metadata:
  type: project
---

- Settled decisions live only in Accepted ADRs (`docs/adr/`) plus the AGENTS.md "Never" list. Owner decided 2026-10-10 that agents must rely on ADRs alone - do not restate decisions in agent prompts; point at the ADRs.
  **Why:** restated copies go stale; "search by track name only" was moved into ADR 0002 for this reason.
  **How to apply:** if a needed decision isn't in an ADR, recommend adding it to one instead of copying it into the agent.
- Read-only agents here get no Bash: frontmatter cannot restrict Bash to specific commands (a `Bash(...)` specifier in disallowedTools removes Bash entirely), and `memory` silently grants Write/Edit, so read-only agents must not use `memory`.
  **How to apply:** for staleness checks, use Glob/Grep over files instead of git commands.
- Convention requested 2026-10-10: agent edit + one `### Changed` line in CHANGELOG `Unreleased`; roster row in AGENTS.md updated only if the role meaning changes. Related: [[plan-reviewer-design]]
