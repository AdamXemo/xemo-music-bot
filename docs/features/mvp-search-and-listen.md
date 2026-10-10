# Feature: MVP search and listen

- **Roadmap item:** Phase 1 - UX interview (covers onboarding, language, search, results,
  delivery, errors for the Phase 1 items that implement them)
- **Status:** Draft

## Goal

An invited friend opens the invite link, sends a track name, picks a number and gets the
track as a Telegram audio message, in English, Ukrainian or Russian.

## User flow

Mockups use `[e:slot]` for an optional custom emoji slot (see the UX guide). `( )` marks a
disabled button. Text in `<b>` is bold.

### 1. Stranger

Any user not in `users` (or `blocked`) who sends `/start` gets one plain line, no keyboard.
Other messages from strangers are ignored.

```
┌──────────────────────────────────────────────┐
│ This bot is private. To join, ask a friend   │
│ who uses it for an invite.                   │
└──────────────────────────────────────────────┘
```

### 2. Joining with an invite (`/start <code>`)

1. Valid code: the user is created with the language taken from Telegram's
   `language_code` (`uk` -> uk, `ru` -> ru, anything else -> en). The bot sends the welcome.
2. Invalid, used up, expired or revoked code: `invite_invalid`, no keyboard, in the
   detected language.
3. A member who sends `/start` (with or without a code) gets the welcome again.

```
┌──────────────────────────────────────────────┐
│ [e:hello] Send me a track name and I'll      │
│ find it.                                     │
│ [ [e:language] Language: English           ] │
└──────────────────────────────────────────────┘
```

Tapping the language button edits the same message into the picker. The current language
has `style: primary`.

```
┌──────────────────────────────────────────────┐
│ Choose a language.                           │
│ [ English ]  [ Українська ]  [ Русский ]     │
└──────────────────────────────────────────────┘
```

Tapping a language saves it and edits the message back to the welcome in that language.
The callback is answered without text.

### 3. `/language`

Sends the picker above as a new message. Tapping a language saves it and edits the
message to `language_set` (no keyboard), written in the new language.

```
┌──────────────────────────────────────────────┐
│ Done, I speak English now.                   │
└──────────────────────────────────────────────┘
```

### 4. `/help`

```
┌──────────────────────────────────────────────┐
│ Send a track name, like daft punk instant    │
│ crush, and pick a number from the list.      │
│ /language changes the language.              │
└──────────────────────────────────────────────┘
```

### 5. Search

1. The user sends text. The `typing` chat action runs until the reply is sent.
2. The bot sends one new results message: the query in bold, then up to 5 numbered
   lines, then a row of number buttons and, if there is more than one page, a pager row.
3. Numbering continues across pages (page 2 shows 6-10), so buttons match the lines.
4. Paging edits the same message (text and keyboard). At the ends the arrow is a disabled
   button so the row never shifts. The counter is always disabled.

```
┌──────────────────────────────────────────────┐
│ <b>instant crush</b>                         │
│                                              │
│ 1. Daft Punk - Instant Crush (feat. Julian   │
│    Casablancas) · 5:37                       │
│ 2. Daft Punk - Instant Crush (Live) · 6:02   │
│ 3. Hauzer - Instant Crush (Remix) · 3:41     │
│ 4. Jenny Kim - Instant Crush cover · 4:12    │
│ 5. Daft Punk - Instant Crush · 1:02:15       │
│ [ 1 ] [ 2 ] [ 3 ] [ 4 ] [ 5 ]                │
│ ( ‹ Back ) ( 1 / 4 ) [ Next › ]              │
└──────────────────────────────────────────────┘
```

Each line is `{index}. Artist - Title · duration`, built from the same cleaned performer
and title as the audio (see "Clean metadata" below), cut at a word boundary with `…` so
the `Artist - Title` part is at most 90 characters; the duration is never cut.

### 6. Delivery

1. The user taps a number. The callback is answered without text.
2. **Cached track** (`tg_file_id` known): the audio is sent immediately. The keyboard is
   not touched.
3. **Not cached:** the tapped button is edited into a disabled loading button
   (`[e:loading]` icon, text `…`). `upload_document` chat action repeats every 4 s until
   the audio is sent. Other numbers stay tappable; several tracks may load at once.
4. The audio arrives as a new message: Telegram's native audio player with the cover as
   the round thumbnail under the play button, the performer and title in bold, and the
   duration and file size below. No caption, no buttons. The number button is restored.
5. The results message stays as it is, so more tracks can be picked.

```
┌──────────────────────────────────────────────┐
│ ...results text unchanged...                 │
│ [ 1 ] ( [e:loading] … ) [ 3 ] [ 4 ] [ 5 ]    │
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
| Results layout | Numbered text list with full titles, compact number buttons below | Owner, 2026-10-10 |
| Page size | 5 per page, one row of number buttons | Owner, 2026-10-10 |
| After the audio is sent | Results message stays as is | Owner, 2026-10-10 |
| Progress | Tapped number becomes a disabled loading button, plus chat action | Owner, 2026-10-10 |
| Onboarding | Welcome in the detected language with a language button; no extra step | Owner, 2026-10-10 |
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
| Language picker | Names in their own language, no flags; current one `primary` | Assumed default |
| Download failure | Short new message, the number is restored; tapping it retries | Assumed default |
| Query length | Over 100 characters is rejected with a hint | Assumed default |

## Copy

No string in this spec needs plural forms. `{query}` and `{track}` are HTML-escaped.
`{track}` is the display form `Artist - Title`, cut to 60 characters.

| key | EN | UK | RU | notes |
|-----|----|----|----|-------|
| private_bot | This bot is private. To join, ask a friend who uses it for an invite. | Це приватний бот. Щоб приєднатися, попросіть запрошення в друга, який ним користується. | Это закрытый бот. Чтобы присоединиться, попросите приглашение у друга, который им пользуется. | |
| invite_invalid | This invite doesn't work anymore. Ask for a new one. | Це запрошення вже не діє. Попросіть нове. | Это приглашение больше не действует. Попросите новое. | |
| welcome | Send me a track name and I'll find it. | Надішліть назву треку, і я його знайду. | Пришлите название трека, и я его найду. | slot `hello` may prefix |
| language_button | Language: English | Мова: українська | Язык: русский | button, slot `language` icon; max 16 chars |
| language_name | English | Українська | Русский | picker button label |
| language_prompt | Choose a language. | Виберіть мову. | Выберите язык. | |
| language_set | Done, I speak English now. | Готово, тепер я говорю українською. | Готово, теперь я говорю по-русски. | proofread UK/RU |
| help | Send a track name, like `<i>daft punk instant crush</i>`, and pick a number from the list.`\n`/language changes the language. | Надішліть назву треку, наприклад `<i>daft punk instant crush</i>`, і виберіть номер у списку.`\n`/language змінює мову. | Пришлите название трека, например `<i>daft punk instant crush</i>`, и выберите номер в списке.`\n`/language меняет язык. | |
| results_header | `<b>{query}</b>` | `<b>{query}</b>` | `<b>{query}</b>` | |
| result_line | `{index}. {track} · {duration}` | `{index}. {track} · {duration}` | `{index}. {track} · {duration}` | here `{track}` is cut to 90 chars |
| pager_back | ‹ Back | ‹ Назад | ‹ Назад | button |
| pager_next | Next › | Далі › | Далее › | button |
| pager_counter | `{page} / {pages}` | `{page} / {pages}` | `{page} / {pages}` | disabled button |
| track_loading | … | … | … | disabled button, slot `loading` icon |
| no_results | Nothing found for “{query}”. Try fewer words or another spelling. | За запитом «{query}» нічого не знайдено. Спробуйте коротший запит або інше написання. | По запросу «{query}» ничего не нашлось. Попробуйте запрос покороче или другое написание. | |
| search_failed | SoundCloud isn't responding. Try again in a minute. | SoundCloud не відповідає. Спробуйте ще раз за хвилину. | SoundCloud не отвечает. Попробуйте ещё раз через минуту. | slot `error` may prefix |
| query_too_long | That's too long for a search. Try just the artist and title. | Задовгий запит. Спробуйте лише виконавця й назву. | Слишком длинный запрос. Попробуйте только исполнителя и название. | |
| not_text | Send the track name as text. | Надішліть назву треку текстом. | Пришлите название трека текстом. | |
| link_not_supported | Search doesn't work with links. Send the track name instead. | Пошук за посиланнями не працює. Надішліть назву треку. | Поиск по ссылкам не работает. Пришлите название трека. | ADR 0002 |
| unknown_command | There's no such command. Try /help. | Такої команди немає. Спробуйте /help. | Такой команды нет. Попробуйте /help. | |
| too_long | This track is too long for Telegram ({duration}). Try a shorter version. | Цей трек задовгий для Telegram ({duration}). Спробуйте коротшу версію. | Этот трек слишком длинный для Telegram ({duration}). Попробуйте версию покороче. | alert, under 200 chars |
| too_large | “{track}” is too large for Telegram. Try a shorter version. | Трек «{track}» завеликий для Telegram. Спробуйте коротшу версію. | Трек «{track}» слишком большой для Telegram. Попробуйте версию покороче. | message |
| download_failed | Couldn't get “{track}”. Tap its number to try again, or pick another one. | Не вдалося завантажити «{track}». Натисніть його номер, щоб спробувати ще раз, або виберіть інший. | Не получилось загрузить «{track}». Нажмите его номер, чтобы попробовать ещё раз, или выберите другой. | slot `error` may prefix |
| already_loading | Already on its way. | Уже завантажується. | Уже загружается. | toast |
| results_expired | These results have expired. Send the name again. | Ці результати застаріли. Надішліть назву ще раз. | Эти результаты устарели. Пришлите название ещё раз. | toast |
| cmd_start | Start the bot | Запустити бота | Запустить бота | command description |
| cmd_help | How it works | Як користуватися | Как пользоваться | command description |
| cmd_language | Change language | Змінити мову | Сменить язык | command description |
| cmd_invite | Create an invite | Створити запрошення | Создать приглашение | admin only |
| cmd_revoke | Revoke an invite | Скасувати запрошення | Отозвать приглашение | admin only |
| cmd_ban | Block a user | Заблокувати користувача | Заблокировать пользователя | admin only |
| bot_short_description | Private music bot for a circle of friends. Invite only. | Приватний музичний бот для кола друзів. Лише за запрошенням. | Закрытый музыкальный бот для своих. Только по приглашению. | `setMyShortDescription`, max 120 |
| bot_description | Send a track name, pick it from the list and get the audio right in the chat.`\n\n`This bot is private: you need an invite from a friend. | Надішліть назву треку, виберіть його зі списку й отримайте аудіо просто в чаті.`\n\n`Бот приватний: потрібне запрошення від друга. | Пришлите название трека, выберите его в списке и получите аудио прямо в чате.`\n\n`Бот закрытый: нужно приглашение от друга. | `setMyDescription`, max 512 |

## Emoji slots

| slot | where | kind |
|------|-------|------|
| `hello` | start of `welcome` | message entity |
| `language` | `language_button` | button icon |
| `loading` | loading number button | button icon (an animated one suits it) |
| `error` | start of `search_failed`, `download_failed` | message entity |

## Edge cases & errors

- **No results:** the reply is `no_results` instead of a results message. No keyboard.
- **Provider failure during search:** `search_failed`, no keyboard.
- **Track too long** (duration known before download, over the size guard): the tap is
  answered with `too_long` as `show_alert`. Nothing is edited.
- **Too large after download** (the file turns out over 50 MB): the button is restored,
  and `too_large` is sent as a new message.
- **Download failure or timeout** (assumed 3 min): the button is restored, and
  `download_failed` is sent as a new message. Tapping the number again retries.
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
- **Long or emoji-heavy titles:** HTML-escaped, cut per the rules above. Emoji in titles
  are kept as user content. Lines wrap in the message; buttons are numbers only, so
  nothing truncates.
- **Query over 100 characters:** `query_too_long`.
- **Link** (text with a URL): `link_not_supported`.
- **Sticker, voice, photo, file or other non-text:** `not_text`.
- **Unknown command:** `unknown_command`.
- **Message deleted by the user while a track loads:** the audio is still sent; the
  button restore is skipped silently.

## Technical notes

- Parse mode HTML for every message. Custom emoji go in as `<tg-emoji emoji-id="…">`
  with the slot's alt emoji inside. Toasts, alerts and command texts carry no emoji.
- Every callback is answered: without text for numbers, pages and languages; with a
  toast or alert only where this spec says.
- Edited, never re-sent: the language picker inside the welcome, the `/language` picker,
  pages of the results message, and the loading state of a number button.
- New messages: welcome, `/help`, results, errors, audio.
- Chat actions: `typing` during search; `upload_document` every 4 s during a download
  (there is no audio chat action).
- Button state that needs storage: per results message, the search session (query,
  results, current page) and the set of tracks loading in it. Both go in Redis next to
  the search session; no new tables.
- Commands: `setMyCommands` per `language_code` (en, uk, ru) for the default scope. When
  a user changes language, also set that user's chat-scope commands in the chosen
  language. For admins the chat scope includes the admin commands. Bot description and
  short description are set per language at startup.
- Language detection: any `language_code` starting with `uk` or `ru` maps to it; else `en`.
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

## Out of scope

- Admin replies for `/invite`, `/revoke`, `/ban` (short spec with the invite PR).
- Rich messages, inline mode, favourites, history, YouTube.
- Reactions: in private chats they would be regular emoji, which the guide forbids.
- Later idea: a caption on delivered audio with a link to the bot, so friends who
  receive a forwarded track can find it. Not wanted for now (Owner, 2026-10-10).
