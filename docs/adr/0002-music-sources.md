# 0002. Source audio from SoundCloud (primary) and YouTube (optional) via yt-dlp

- **Status:** Proposed
- **Date:** 2026-10-06

## Context

The bot needs a large mainstream catalogue with full-length tracks delivered as Telegram
audio. Options researched (Oct 2026):

- **SoundCloud official API** — needs an Artist Pro subscription to register an app.
  Its terms forbid downloading/caching content and uploading it to third-party
  platforms, which is exactly what delivering a Telegram audio message does. OAuth
  ("Connect with SoundCloud") is allowed and supported (OAuth 2.1 + PKCE).
- **yt-dlp** — extracts audio and public profile data (likes, playlists) from
  SoundCloud and YouTube without API keys. Not permitted by either platform's terms.
- **YouTube** — strong anti-bot measures (PO tokens, datacenter IP blocking) make it
  unreliable from typical VPS hosting.
- **Audius / Jamendo** — legitimate but catalogue too limited; rejected by the owner.

No Telegram music bot of note operates under a label licence; they rely on scrapers or
unofficial APIs. A licensed, public version of this project is not realistically possible.

## Decision

- Use **yt-dlp** behind a `MusicProvider` interface.
- **SoundCloud** is the primary provider; **YouTube** is optional behind a feature flag.
- Keep the bot **private and non-commercial** (see ADR 0003).
- Official SoundCloud OAuth stays in the ideas backlog.

## Alternatives considered

- **Official SoundCloud API only** — cannot deliver audio within its terms.
- **Audius / Jamendo** — catalogue too limited.

## Consequences

- yt-dlp breaks when platforms change; pin it and keep it easy to update.
- Provider abstraction lets us swap or add sources without touching handlers.
- README carries a clear disclaimer: personal, non-commercial learning project.
- YouTube may need residential hosting or cookies to work reliably.
