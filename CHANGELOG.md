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

### Changed
- `plan-reviewer` subagent: settled decisions sourced from Accepted ADRs only, severity labels (must fix / should fix / consider), evidence-based stale-doc and plan-vs-code drift checks, and rules for verifying external facts.
- Roadmap reworked after plan review: branch protection after CI, Redis before search UX,
  DB layer and delivery split into reviewable PRs, revocation, Dependabot and smoke tests.
- ADRs 0001-0004 accepted; ADR 0002 records search-by-name-only and the Deno need for YouTube.
