# Feature: MVP search and listen

- **Roadmap item:** Phase 1 - UX interview (covers onboarding, language, search, results,
  delivery, errors for the Phase 1 items that implement them)
- **Status:** Approved

## Goal

An invited friend opens the invite link, sends a track name, taps a track and gets the
track as a Telegram audio message, in English, Ukrainian or Russian.

## User flow

Mockups use `[e:slot]` for an optional custom emoji slot (see the UX guide). `( )` marks a
disabled button. Text in `<b>` is bold.

### 1. Stranger

Any user not in `users` (or `blocked`) who sends `/start` gets one plain line, no keyboard.
Other messages from strangers are ignored.

```
┌──────────────────────────────────────────────┐
│ This bot is private. To join, ask @Xemo999   │
│ for an invite                                │
└──────────────────────────────────────────────┘
```

### 2. Joining with an invite (`/start <code>`)

1. Valid code: the user is created with the language taken from Telegram's
   `language_code` (`uk` -> uk, `ru` -> ru, anything else -> en). The bot sends the
   language picker.
2. Invalid, used up, expired or revoked code: `invite_invalid`, no keyboard, in the
   detected language.
3. Any allowed user (member or admin) who sends `/start`, with or without a code: the
   picker if no language has been picked yet, otherwise the welcome.

**First-run picker.** A new message. The prompt is in the stored language (the detected
one until a pick). The stored language has `style: primary`. Each button is the flag, a
space and the name, so it reads the same whatever the prompt language.

```
┌──────────────────────────────────────────────┐
│ Choose a language                            │
│ [ 🇬🇧 English ] [ 🇺🇦 Українська ] [ 🇷🇺 Русский ] │
└──────────────────────────────────────────────┘
```

Tapping a language saves it and edits the same message into the welcome in that
language (no confirmation line; the welcome in the new language is the confirmation).
The callback is answered without text.

**Welcome.** No keyboard. Sent as a new message on every later `/start`.

```
┌──────────────────────────────────────────────┐
│ [e:hello] Send me a track name and I'll      │
│ find it                                      │
└──────────────────────────────────────────────┘
```

### 3. `/language`

The quiet way to switch later, until a Settings screen absorbs it (later roadmap item,
not this one). Sends the same picker as a new message. Tapping a language saves it and
edits the message to `language_set` (no keyboard), written in the new language.

```
┌──────────────────────────────────────────────┐
│ Language set to English                      │
└──────────────────────────────────────────────┘
```

### 4. `/help`

```
┌──────────────────────────────────────────────┐
│ Send a track name, like daft punk instant    │
│ crush, and tap a track in the list           │
│ /language changes the language               │
└──────────────────────────────────────────────┘
```

### 5. Search

1. The user sends text. The `typing` chat action runs until the reply is sent.
2. The bot sends one new results message: the query in bold as the only text, then one
   full-width button per track (up to 5) and, if there is more than one page, a pager row.
3. Each track button carries the optional `track` emoji slot as its icon and no `style`.
4. Paging edits the same message (text and keyboard). At the ends the arrow is a disabled
   button so the row never shifts. The counter is always disabled.

```
┌──────────────────────────────────────────────┐
│ <b>instant crush</b>                         │
│ [ [e:track] Instant Crush (feat.… · 5:37   ] │
│ [ [e:track] Instant Crush (Live) · 6:02    ] │
│ [ [e:track] Instant Crush (Remix) · 3:41   ] │
│ [ [e:track] Instant Crush - Jenny Kim · 4:12 ]│
│ [ [e:track] Instant Crush - Daft… · 1:02:15 ]│
│ ( ‹ Back ) ( 1 / 4 ) [ Next › ]              │
└──────────────────────────────────────────────┘
```

**Track label.** `Title - Artist · duration` (`result_label`), built from the cleaned
performer and title (see "Clean metadata" below). The whole label is at most 32
characters, not counting the icon; emoji in titles count as 2. Shortening order:

1. The ` · duration` suffix is never cut.
2. If the label is too long, the artist is cut at the end with `…`.
3. If fewer than 5 characters of the artist (including `…`) would remain, the artist and
   its ` - ` are dropped.
4. If still too long, the title is cut at a word boundary with `…` (at a character
   boundary if one word is longer than the space left).

The label is the same in every language; only `track_loading` is translated, and its
longest form (UK, 13 characters) fits the full-width budget.

### 6. Delivery

1. The user taps a track button. The callback is answered without text.
2. **Cached track** (`tg_file_id` known): the audio is sent immediately. The keyboard is
   not touched.
3. **Not cached:** the tapped button is edited into a disabled loading button
   (`[e:loading]` icon, text `track_loading`). `upload_document` chat action repeats
   every 4 s until the audio is sent. Other tracks stay tappable; several may load at once.
4. The audio arrives as a new message: Telegram's native audio player with the cover as
   the round thumbnail under the play button, the performer and title in bold, and the
   duration and file size below. No caption, no buttons. The track button is restored.
5. The results message stays as it is, so more tracks can be picked.

```
┌──────────────────────────────────────────────┐
│ <b>instant crush</b>                         │
│ [ [e:track] Instant Crush (feat.… · 5:37   ] │
│ ( [e:loading] Loading…                     ) │
│ [ [e:track] Instant Crush (Remix) · 3:41   ] │
│ [ [e:track] Instant Crush - Jenny Kim · 4:12 ]│
│ [ [e:track] Instant Crush - Daft… · 1:02:15 ]│
│ ( ‹ Back ) ( 1 / 4 ) [ Next › ]              │
└──────────────────────────────────────────────┘

┌──────────────────────────────────────────────┐
│  ╭─────╮                                     │
│  │cover│  <b>Daft Punk - Instant Crush</b>   │
│  │ (>) │  5:37 · 5.2 MB                      │
│  ╰─────╯                                     │
└──────────────────────────────────────────────┘
```

Telegram draws the bold line from `performer` and `title` with its own separator, and
adds the file size itself.

**Cover (required).** Every audio has a cover. Order: the track's artwork, else the
uploader's avatar, else the bot's default cover (a static image in the repo).

**Clean metadata.** Performer and title are cleaned once, and the same values are used
in the results list, the audio and the `tracks` cache:

- If the title has the form `X - Y` (the separator may also be an en dash or em dash,
  U+2013 or U+2014, with spaces around it), `X` becomes the performer
  and `Y` the title; the uploader name is dropped.
- Otherwise the performer is the uploader name and the title is used as is.
- Junk is removed from the end of the title, case-insensitive, in `()` or `[]` or after
  `|`: official audio, official video, official music video, lyrics, lyric video,
  audio, free download, free dl, out now. Remix, feat., live, edit, version, cover and
  similar stay.
- Whitespace is collapsed. If cleaning would leave an empty title, the raw title is used.

## UX decisions

| Decision | Choice | Source |
|----------|--------|--------|
| Results layout | One full-width button per track; message text is only the query (replaces the numbered list) | Owner, 2026-10-10 |
| Track label | `Title - Artist · m:ss`; artist cut first, duration always kept | Owner, 2026-10-10 |
| Rich message cards | Not in the MVP; a spike on real devices decides a later switch | Owner, 2026-10-10 |
| Page size | 5 tracks per page | Owner, 2026-10-10 |
| After the audio is sent | Results message stays as is | Owner, 2026-10-10 |
| Progress | Tapped track button becomes a disabled loading button, plus chat action | Owner, 2026-10-10 |
| Label budget | 32 characters, artist kept only if 5+ characters of it fit | Assumed default |
| Loading button text | "Loading…" with the `loading` icon, instead of the track label | Assumed default |
| Onboarding | First `/start`: language picker, then the welcome in the chosen language. Later `/start`: welcome only | Owner, 2026-10-15 (replaces 2026-10-10) |
| Welcome keyboard | None; the "Language: ..." button is removed | Owner, 2026-10-15 |
| First-run pick | Edits the picker message into the welcome; no `language_set` line | Assumed default, 2026-10-15 |
| First-run prompt | `language_prompt` in the detected language, one line | Assumed default, 2026-10-15 |
| Until a language is picked | Every `/start` sends the picker again; search and other commands work in the detected language | Assumed default, 2026-10-15 |
| `/language` | Stays as the quiet way to switch; a later Settings screen absorbs it | Owner, 2026-10-15 |
| Too-long tracks | Shown normally; a tap shows a short alert | Owner, 2026-10-10 |
| Results header | Only the query, in bold; no "Results for" | Assumed default |
| Welcome text | One line | Assumed default |
| Audio message | Native player: cover thumbnail, bold performer and title, duration (file size shown by Telegram) | Owner, 2026-10-10 |
| Cover | Required on every audio; fallback chain ends in a default cover | Owner, 2026-10-10 |
| Caption and buttons on audio | None | Owner, 2026-10-10 |
| Clean performer and title | No duplicated artist in the title | Owner, 2026-10-10 |
| Cover fallback order | Track artwork, uploader avatar, default cover | Assumed default |
| Default cover design | Owner provides the image; until then a plain dark square with the bot's name | Assumed default |
| Title splitting and junk list | Rules under "Clean metadata" | Assumed default |
| Pager | `‹ Back` · disabled counter · `Next ›`; disabled arrows at the ends | Assumed default |
| Search trigger | Any plain text message (not a command) | Assumed default |
| Commands | `/start`, `/help`, `/language`; admins also see `/invite`, `/revoke`, `/ban` | Assumed default |
| Strangers | Only `/start` gets a reply; everything else is ignored | Assumed default |
| Stranger reply | `private_bot` and `bot_description` name the owner, @Xemo999, as the person to ask for an invite | Owner, 2026-10-15 |
| Unrecognised buttons | One catch-all: answered without text, keyboard removed, nothing saved | Owner, 2026-10-15 |
| Language picker | `🇬🇧 English`, `🇺🇦 Українська`, `🇷🇺 Русский` (flag, space, name) in one row; stored one `primary` | Owner, 2026-10-15 (flags); `primary` assumed default |
| Picker row too wide | If a phone cuts a label, the three buttons stack one per row | Assumed default, 2026-10-15 |
| Download failure | Short new message, the track button is restored; tapping it retries | Assumed default |
| Go+ tracks (preview or DRM only) | Refused, never send the 30 s clip | Owner, 2026-10-15 |
| Go+ refusal UX | New message `track_unavailable` (no retry hint, suggests another version); the button is restored as normal | Assumed default, 2026-10-15 |
| Query length | Over 100 characters is rejected with a hint | Assumed default |
| Picking the current language | Same as a change: the first-run picker edits into the welcome; the `/language` picker shows `language_set`. No toast, no special copy | Owner-approved default, 2026-10-12 |
| Language callbacks | Stateless (language code and origin: first run or `/language`); work on any old message, no expiry | Owner-approved default, 2026-10-12 |
| Language source | Allowed updates use `users.language`; strangers and blocked users get Telegram's `language_code` | Owner-approved default, 2026-10-12 |
| Denied callbacks | Taps from strangers, blocked users or groups are answered without text; nothing is edited | Assumed default, 2026-10-13 |
| Picker prompt language | `language_prompt` in the stored language (the detected one until a pick) | Assumed default, 2026-10-13 |
| Welcome before Search UX ships | Uses the final `welcome` copy; only the admin sees it before invites exist | Owner, 2026-10-12 |

## Copy

No string in this spec needs plural forms. `{query}` and `{track}` are HTML-escaped.
`{track}` in messages is the display form `Artist - Title`, cut to 60 characters (it
matches the audio player); track buttons use `result_label` instead.

| key | EN | UK | RU | notes |
|-----|----|----|----|-------|
| private_bot | This bot is private. To join, ask @Xemo999 for an invite | Це приватний бот. Щоб приєднатися, попросіть запрошення в @Xemo999 | Это закрытый бот. Чтобы присоединиться, попросите приглашение у @Xemo999 | owner copy, 2026-10-15 |
| invite_invalid | This invite doesn't work anymore. Ask for a new one | Це запрошення вже не діє. Попросіть нове | Это приглашение больше не действует. Попросите новое | |
| welcome | Send me a track name and I'll find it | Надішліть назву треку, і я його знайду | Пришлите название трека, и я его найду | slot `hello` may prefix; owner copy, 2026-10-15 |
| language_flag | 🇬🇧 | 🇺🇦 | 🇷🇺 | Unicode, the guide's one exception; picker only |
| language_name | English | Українська | Русский | picker button label is `language_flag`, a space, `language_name`; max 13 chars |
| language_prompt | Choose a language | Виберіть мову | Выберите язык | first-run picker and `/language`; owner copy, 2026-10-15 |
| language_set | Language set to English | Мову змінено на українську | Язык изменён на русский | `/language` only; owner copy, 2026-10-15 |
| help | Send a track name, like `<i>daft punk instant crush</i>`, and tap a track in the list`\n`/language changes the language | Надішліть назву треку, наприклад `<i>daft punk instant crush</i>`, і натисніть потрібний трек у списку`\n`/language змінює мову | Пришлите название трека, например `<i>daft punk instant crush</i>`, и нажмите нужный трек в списке`\n`/language меняет язык | no period at a line end (guide) |
| results_header | `<b>{query}</b>` | `<b>{query}</b>` | `<b>{query}</b>` | |
| result_label | `{label} · {duration}` | `{label} · {duration}` | `{label} · {duration}` | track button; `{label}` is `Title - Artist` or `Title`, shortened per "Track label"; plain text, not escaped (buttons have no parse mode) |
| pager_back | ‹ Back | ‹ Назад | ‹ Назад | button |
| pager_next | Next › | Далі › | Далее › | button |
| pager_counter | `{page} / {pages}` | `{page} / {pages}` | `{page} / {pages}` | disabled button |
| track_loading | Loading… | Завантаження… | Загрузка… | disabled button, slot `loading` icon |
| no_results | Nothing found for “{query}”. Try fewer words or another spelling | За запитом «{query}» нічого не знайдено. Спробуйте коротший запит або інше написання | По запросу «{query}» ничего не нашлось. Попробуйте запрос покороче или другое написание | |
| search_failed | SoundCloud isn't responding. Try again in a minute | SoundCloud не відповідає. Спробуйте ще раз за хвилину | SoundCloud не отвечает. Попробуйте ещё раз через минуту | slot `error` may prefix |
| query_too_long | That's too long for a search. Try just the artist and title | Задовгий запит. Спробуйте лише виконавця й назву | Слишком длинный запрос. Попробуйте только исполнителя и название | |
| not_text | Send the track name as text | Надішліть назву треку текстом | Пришлите название трека текстом | |
| link_not_supported | Search doesn't work with links. Send the track name instead | Пошук за посиланнями не працює. Надішліть назву треку | Поиск по ссылкам не работает. Пришлите название трека | ADR 0002 |
| unknown_command | There's no such command. Try /help | Такої команди немає. Спробуйте /help | Такой команды нет. Попробуйте /help | |
| too_long | This track is too long for Telegram ({duration}). Try a shorter version | Цей трек задовгий для Telegram ({duration}). Спробуйте коротшу версію | Этот трек слишком длинный для Telegram ({duration}). Попробуйте версию покороче | alert, under 200 chars |
| too_large | “{track}” is too large for Telegram. Try a shorter version | Трек «{track}» завеликий для Telegram. Спробуйте коротшу версію | Трек «{track}» слишком большой для Telegram. Попробуйте версию покороче | message |
| download_failed | Couldn't get “{track}”. Tap it again to retry, or pick another one | Не вдалося завантажити «{track}». Натисніть на нього ще раз або виберіть інший | Не получилось загрузить «{track}». Нажмите на него ещё раз или выберите другой | slot `error` may prefix |
| track_unavailable | SoundCloud doesn't allow downloading “{track}”. Try another version | SoundCloud не дозволяє завантажити трек «{track}». Спробуйте іншу версію | SoundCloud не даёт загрузить трек «{track}». Попробуйте другую версию | message; Go+ preview or DRM; no retry hint, a retry never helps; slot `error` may prefix; UK and RU: proofread |
| already_loading | Already on its way | Уже завантажується | Уже загружается | toast |
| results_expired | These results have expired. Send the name again | Ці результати застаріли. Надішліть назву ще раз | Эти результаты устарели. Пришлите название ещё раз | toast |
| cmd_start | Start the bot | Запустити бота | Запустить бота | command description |
| cmd_help | How it works | Як користуватися | Как пользоваться | command description |
| cmd_language | Change language | Змінити мову | Сменить язык | command description |
| cmd_invite | Create an invite | Створити запрошення | Создать приглашение | admin only |
| cmd_revoke | Revoke an invite | Скасувати запрошення | Отозвать приглашение | admin only |
| cmd_ban | Block a user | Заблокувати користувача | Заблокировать пользователя | admin only |
| bot_short_description | Private music bot for a circle of friends. Invite only | Приватний музичний бот для кола друзів. Лише за запрошенням | Закрытый музыкальный бот для своих. Только по приглашению | `setMyShortDescription`, max 120 |
| bot_description | Send a track name, pick it from the list and get the audio right in the chat`\n\n`This bot is private: ask @Xemo999 for an invite | Надішліть назву треку, виберіть його зі списку й отримайте аудіо просто в чаті`\n\n`Бот приватний: попросіть запрошення в @Xemo999 | Пришлите название трека, выберите его в списке и получите аудио прямо в чате`\n\n`Бот закрытый: попросите приглашение у @Xemo999 | `setMyDescription`, max 512; names the owner like `private_bot` (Owner, 2026-10-15) |

## Emoji slots

| slot | where | kind |
|------|-------|------|
| `hello` | start of `welcome` | message entity |
| `track` | every track button | button icon |
| `loading` | loading track button | button icon (an animated one suits it) |
| `error` | start of `search_failed`, `download_failed`, `track_unavailable` | message entity |

## Edge cases & errors

- **No results:** the reply is `no_results` instead of a results message. No keyboard.
- **Provider failure during search:** `search_failed`, no keyboard.
- **Track too long** (duration known before download, over the size guard): the tap is
  answered with `too_long` as `show_alert`. Nothing is edited.
- **Too large after download** (the file turns out over 50 MB): the button is restored,
  and `too_large` is sent as a new message.
- **Download failure or timeout** (assumed 3 min): the button is restored, and
  `download_failed` is sent as a new message. Tapping the track again retries.
- **SoundCloud Go+ track** (only a 30 s preview or a DRM stream is offered; Owner,
  2026-10-15: refuse, never send the clip): search cannot spot them, so they look normal
  in the list. The tap starts as usual (callback answered without text, loading button);
  when the provider refuses, the button is restored as normal and `track_unavailable` is
  sent as a new message (not an alert: the callback is already answered). A later tap
  repeats the same refusal; nothing is remembered (assumed default, 2026-10-15).
- **No artwork, or the cover fails to download or convert:** fall through to the
  uploader avatar, then the default cover. The user sees no difference in flow.
- **Slow download:** the loading button stays, and the chat action keeps repeating. No
  extra messages.
- **Cached track:** instant send, no loading button, no chat action.
- **Double tap on a loading track:** answered with toast `already_loading`. A second
  download never starts.
- **Paging while a track loads:** the page is re-rendered with that track's button still
  loading if it is on the shown page.
- **Expired results** (cache TTL gone): any tap is answered with toast `results_expired`,
  and the message's keyboard is removed so no dead buttons are left.
- **Long or emoji-heavy titles:** shortened per "Track label" before Telegram can cut
  them, so the duration always shows. Emoji in titles are kept as user content and count
  as 2 characters. Newlines and control characters in titles become spaces.
- **Two labels on a page end up identical** (same title, artist dropped, same duration):
  accepted for the MVP; the cover and performer in the delivered audio tell them apart.
- **Query over 100 characters:** `query_too_long`.
- **Link** (text with a URL): `link_not_supported`.
- **Sticker, voice, photo, file or other non-text:** `not_text`.
- **Unknown command:** `unknown_command`.
- **Message deleted by the user while a track loads:** the audio is still sent; the
  button restore is skipped silently.
- **Picking the language already set** (owner-approved default, 2026-10-12): handled
  like a change. The first-run picker edits into the welcome; the `/language` picker
  shows `language_set`. No toast.
- **Language buttons on an old message** (owner-approved default, 2026-10-12): they
  keep working. A first-run picker tapped after a language was already picked (for
  example a second one from a repeated `/start`) saves the tapped language and edits
  that message into the welcome in it, like the first time. An old `/language` picker
  saves and shows `language_set`. No expiry toast. Other old messages are not updated
  after a change (assumed default, 2026-10-13).
- **First-run picker ignored** (assumed default, 2026-10-15): the user can search right
  away; everything is in the detected language and nothing counts as a pick. The next
  `/start` sends the picker again.
- **Old welcome with the removed "Language" button** (assumed default, 2026-10-15; only
  the admin has one): the tap is answered without text and the message's keyboard is
  removed.
- **Any other button no handler recognises** (outdated or unparseable callback data, for
  example a picker sent before the current data format; Owner, 2026-10-15; one catch-all
  handler):
  same as the old "Language" button. Answered without text, keyboard removed, nothing
  saved.
- **Button tap from a stranger, a blocked user or a group** (assumed default,
  2026-10-13): the callback is answered without text; nothing is edited or sent.
- **Double tap or "message is not modified" on a language edit** (owner-approved
  default, 2026-10-12): the callback is answered without text and the error is ignored
  silently.

## Technical notes

- Parse mode HTML for every message. Custom emoji go in as `<tg-emoji emoji-id="…">`
  with the slot's alt emoji inside. Toasts, alerts and command texts carry no emoji.
- Every callback is answered: without text for tracks, pages and languages; with a
  toast or alert only where this spec says.
- Edited, never re-sent: the first-run picker into the welcome (text and keyboard; the
  welcome has no keyboard), the `/language` picker into `language_set`, pages of the
  results message, and the loading state of a track button (only the keyboard is edited
  for loading and restore).
- Language picker buttons: text is `language_flag`, a space and `language_name`, each
  from its own language's catalog; plain Unicode flags, no `icon_custom_emoji_id`.
- "Has the user picked a language yet" is the one new piece of state (yes or no; any
  pick from any picker sets it). Storage is db-architect's. UX has no preference for
  users who existed before this change: not asking them again is fine.
- Any pick, the first one included, sets that user's chat-scope commands (below; landed
  with i18n 2/2).
- Track buttons: one per row, callback data `<session_id>:<index>` as in ARCHITECTURE,
  `icon_custom_emoji_id` from the `track` slot when set, no `style`.
- New messages: the first-run picker, the welcome on a later `/start`, the `/language`
  picker, `/help`, results, errors, audio.
- Chat actions: `typing` during search; `upload_document` every 4 s during a download
  (there is no audio chat action).
- Button state that needs storage: per results message, the search session (query,
  results, current page) and the set of tracks loading in it. Both go in Redis next to
  the search session; no new tables.
- Commands: `setMyCommands` per `language_code` (en, uk, ru) for the default scope. When
  a user changes language, also set that user's chat-scope commands in the chosen
  language. For admins the chat scope includes the admin commands (each admin command
  is added by the item that builds it; until then every menu is the same). Bot
  description and short description are set per language at startup.
- Language detection: a `language_code` whose primary subtag is `uk` or `ru` maps to it
  (`uk-UA` -> uk); else `en`.
- `sendAudio` on a cache miss: `performer` and `title` (cleaned), `duration` in seconds,
  `thumbnail`, no `caption`, no `reply_markup`. Bot API (checked 2026-10-10): the
  thumbnail must be JPEG, under 200 kB, width and height at most 320; it is only used when
  the audio itself is uploaded as multipart, and it can't be reused by `file_id`, so it is
  uploaded with the audio each time. Convert the chosen cover to a centre-cropped square
  JPEG, at most 320x320, re-encoding at lower quality until it is under 200 kB. Audio is
  at most 50 MB.
- Cache hit: send by `file_id` only. Telegram keeps the thumbnail, performer, title and
  duration from the first upload, so the cached audio looks identical.
- If no cover can be fetched or converted, use the default cover; never send without one.
- Store the cleaned performer and title in `tracks` (`artist`, `title`), so the cached
  and the results-list forms always match.

## Rich cards spike

Owner decision 2026-10-10, moved to after Delivery (owner decision 2026-10-15): a
throwaway script (not merged, no handlers) tests rich-message track cards on real devices.
The result decides whether cards replace the track buttons in a later PR; callbacks and
the search session stay the same either way.

What the script sends to the owner and two or three friends:

1. One `sendRichMessage` with the query as a heading and 5 cards. Each card is a
   paragraph (`<tg-emoji>` slot, bold title, then `Artist · m:ss`) and a right-aligned
   buttons block with one callback button; plus a pager row as `reply_markup`. Use one
   real long title (60+ characters) and one with emoji.
2. The same cards with the title itself as an inline `<tg-button style="link">`.
3. On a tap: `editMessageText` with `rich_message`, swapping that card's button to a
   disabled "Loading…" one, then back after 3 s; and one page change.

What the owner checks, on iPhone, Android, Telegram Desktop, Web (K and A) and any
third-party client a friend uses:

- Does it render at all, and what does a client without support show?
- How it looks next to the plain button version: spacing, long titles, alignment.
- The notification text and the chat-list preview, and whether any Unicode fallback
  emoji leak into them.
- Tap targets: easy to hit with a thumb, no mis-taps between cards.
- Edits: does the message jump, flicker or scroll when one button changes or a page turns?
- Callback answers arrive as with normal inline buttons.

## Out of scope

- Admin replies for `/invite`, `/revoke`, `/ban` (short spec with the invite PR).
- Rich message cards (see the spike above), inline mode, favourites, history, YouTube.
- A Settings screen that absorbs `/language` (later roadmap item).
- Reactions: in private chats they would be regular emoji, which the guide forbids.
- Later idea: a caption on delivered audio with a link to the bot, so friends who
  receive a forwarded track can find it. Not wanted for now (Owner, 2026-10-10).
