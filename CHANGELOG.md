# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) ·
Versioning: [SemVer](https://semver.org/).

## [Unreleased]

### Added
- Project planning docs: AGENTS.md, roadmap, architecture, contributing guide, ADRs 0001-0004.
- Repo conventions: PR and issue templates, `.gitignore`, `.editorconfig`, MIT license.
- `plan-reviewer` subagent and agent team roster.
- `agent-engineer` subagent for designing and auditing the other agents.
- Project skeleton: `uv` package on Python 3.13, typed settings via pydantic-settings,
  logging setup, `python -m xemo_music_bot` entrypoint, `.env.example`.
- Tooling: ruff (format + lint), mypy strict with the pydantic plugin, pytest with
  asyncio and coverage, pre-commit hooks; first tests for settings.
- `python-engineer` subagent for implementing roadmap items; the main session becomes
  the orchestrator that delegates and owns git and PRs.
- `ux-designer` subagent with an interview-first workflow.
- ADR 0005 (proposed): English, Ukrainian and Russian via typed in-code catalogs.
- Hello-world bot: aiogram long polling via `python -m xemo_music_bot`, `/start` greeting
  in English, Ukrainian or Russian picked from the Telegram language (English fallback).

### Changed
- `plan-reviewer` subagent: settled decisions sourced from Accepted ADRs only, severity labels (must fix / should fix / consider), evidence-based stale-doc and plan-vs-code drift checks, and rules for verifying external facts.
- Roadmap reworked after plan review: branch protection after CI, Redis before search UX,
  DB layer and delivery split into reviewable PRs, revocation, Dependabot and smoke tests.
- ADRs 0001-0004 accepted; ADR 0002 records search-by-name-only and the Deno need for YouTube.
