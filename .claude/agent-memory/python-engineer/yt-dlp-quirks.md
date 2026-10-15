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
- Download (verified 2026-10-15): most tracks only have HLS AAC (`hls_aac_160k`), converted to
  MP3 by `FFmpegExtractAudio`; `info["requested_downloads"][0]["filepath"]` is the final
  `.mp3`. Go+ tracks are either previews (only format `http_mp3_1_0_preview`, info duration
  30.0, format_id ends with `preview`) or raise `DownloadError` "This video is DRM protected"
  (flat search shows the full duration for these). A progress hook raising
  `DownloadCancelled` stops a running download from another thread's event.
- Covers (verified 2026-10-15, real download): full extraction exposes no separate
  avatar; `thumbnails` is artwork else avatar. `writethumbnail` tries the LAST (best,
  `original` has preference 10) first, falls back on fetch errors, and sets
  `thumb["filepath"]` on the top-level `info["thumbnails"]` entry. To narrow sizes:
  `extract_info(url, download=False, process=False)`, edit `thumbnails`, then
  `process_ie_result(info, download=True)` (processing errors then arrive unwrapped,
  e.g. raw ExtractorError, still YoutubeDLError).
- Pillow 12.3 has py.typed; `getpixel` returns a union (narrow with isinstance);
  `Image.new("I;16")` PNG converts to RGB fine; ruff S311 flags `random.Random` in tests.
- Errors surface as `yt_dlp.utils.DownloadError` (subclass of `YoutubeDLError`).
- `logger` option takes a stdlib `logging.Logger`; info and debug both go to `.debug`.
