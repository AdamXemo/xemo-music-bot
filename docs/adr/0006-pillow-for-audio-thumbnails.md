# 0006. Convert audio covers to Telegram thumbnails with Pillow

- **Status:** Accepted
- **Date:** 2026-10-15

## Context

Every delivered audio must show a cover (MVP spec, "Cover (required)"). `sendAudio`
takes a `thumbnail` only if it is a JPEG under 200 kB with width and height at most 320
px. SoundCloud artwork comes in fixed sizes (usually a 500x500 JPEG, sometimes PNG with
transparency, an odd mode such as CMYK, or a broken file), so the bot has to centre-crop
it to a square, scale it down, convert it to RGB JPEG and re-encode at lower quality
until it fits. A bad image must never fail a delivery; the bot falls back to a default
cover instead.

## Decision

- Add **Pillow** as a runtime dependency (owner approved, 2026-10-15) and do the
  conversion in `providers/covers.py`: a pure function from an image file to thumbnail
  bytes, run through `asyncio.to_thread` because Pillow is synchronous. Pillow's default
  decompression bomb limit stays on.
- yt-dlp fetches the cover into the download's temp dir (`writethumbnail`), so no new
  HTTP client is needed and the cover is removed with the audio.
- The default cover is a static JPEG in the package (`assets/default_cover.jpg`) that
  already meets the rules; `scripts/make_default_cover.py` drew the placeholder.

## Alternatives considered

- **ffmpeg for image conversion** - already installed for audio, so no new Python
  package. But fitting under 200 kB means a quality loop of subprocess runs, the crop and
  scale need a filter expression, and errors come back as exit codes and stderr text.
  Each cover would cost several process starts, and tests would need the binary.
- **No thumbnail** - Telegram shows a generic note icon. Rejected: the spec requires a
  cover on every audio.
- **Upload the image as is** - SoundCloud's 500x500 artwork already breaks the 320 px
  rule, and PNG covers break the JPEG one.

## Consequences

- One more runtime dependency with native code (it ships wheels for Linux, macOS and
  Windows, so the Docker image needs no extra system packages); Dependabot keeps it current.
- Cover handling is plain, testable Python: tests build images in memory, no network.
- Replacing the default cover means swapping one file; a test checks it still meets the
  thumbnail rules.
