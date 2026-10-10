---
name: yt-dlp-quirks
description: Verified yt-dlp 2026.8.19 facts for SoundCloud search - flat entry shape, latency, typing, Go+ previews
metadata:
  type: reference
---

Verified on yt-dlp 2026.8.19, 2026-10-10:

- No `py.typed`; pyproject has a mypy override (`ignore_missing_imports`) for `yt_dlp.*`.
  `ydl.extract_info` returns Any, so annotate the variable to satisfy `warn_return_any`.
- `scsearchN:q` with `extract_flat="in_playlist"` makes one API call and returns entries
  with `id` (str), `title`, `uploader`, `duration` (float s), `webpage_url`, `thumbnails`
  (ids `t500x500`, `original`, ...). Full extraction adds several requests per track.
- Flat search still does one HEAD per entry (the `original` thumbnail check in
  `_extract_thumbnails`): about 1.5 s for 10 results, 3.5 s for 20. No option skips it.
- `thumbnails` already falls back to the uploader avatar when artwork is missing; the raw
  `artwork_url` / `avatar_url` are not exposed separately in flat entries.
- SoundCloud Go+ tracks come back as 30.0 s previews (`duration` is the snippet); the
  `policy: SNIP` field is not in flat entries. Expect several per popular query.
- Errors surface as `yt_dlp.utils.DownloadError` (subclass of `YoutubeDLError`).
- `logger` option takes a stdlib `logging.Logger`; info and debug both go to `.debug`.
