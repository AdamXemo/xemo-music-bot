# 0003. Restrict access with an allowlist and invite codes

- **Status:** Accepted
- **Date:** 2026-10-06

## Context

The bot is built for a small circle of friends and sits in a legal grey zone
(ADR 0002). Open access would invite abuse, load, and attention.

## Decision

- An access middleware rejects any Telegram user not in `users`.
- Admins (Telegram IDs from config) generate invite codes with `/invite`. Config is the
  only source of admin rights. Config admins need no invite: their `users` row is created
  on their first update, and they cannot be banned.
- New users join via deep link `t.me/<bot>?start=<code>`; codes can expire and have a
  use limit.
- Strangers receive one short "this bot is private" reply and nothing else.
- Admins can revoke access: `/revoke <code>` kills an invite, `/ban <user>` sets the
  user's role to `blocked`, which the middleware rejects.

## Alternatives considered

- **Open to everyone** - more exposure and risk, no benefit for the target audience.
- **Hard-coded ID list in config** - no self-service onboarding; redeploy per friend.

## Consequences

- Needs `users` and `invites` tables from Phase 1.
- Middleware runs on every update, so the user lookup must be cheap (Redis cache later).
