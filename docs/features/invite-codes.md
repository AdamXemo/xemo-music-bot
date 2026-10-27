# Feature: Invite codes

- **Roadmap item:** Phase 1 - Invite codes (admin replies for `/invite`; joining with
  `/start <code>`)
- **Status:** Approved

## Goal

An admin sends `/invite`, passes the link to one friend, and that friend opens it and
is in: language picker, then welcome. The admin is told who joined.

## User flow

Joining (picker, welcome, `invite_invalid`) is already specified in
[mvp-search-and-listen.md](mvp-search-and-listen.md) section 2. This spec adds the admin
side and the rules for using a code up. Revoking and banning are out of scope.

### 1. Admin creates an invite

1. Admin sends `/invite`. Any text after the command is ignored. Each call creates a
   new single-use code that works for 7 days.
2. The bot sends one new message. Link preview is off.

```
┌──────────────────────────────────────────────┐
│ One-time invite ready                        │
│ [ Copy ]                      [ Share ]      │
└──────────────────────────────────────────────┘
```

The line is bold. It shows no link and no validity text. The link is only on the buttons.
The labels are plain: the Telegram client draws its own corner icon on each button, so
they carry no symbol prefix and no custom emoji icon (a second icon would double up).

- **Copy** copies `https://t.me/xemo_music_bot?start=Kx7pQ2mZ`. The Telegram app shows
  its own "copied" notice, and the bot gets no callback.
- **Share** opens Telegram's chat picker. After a chat is picked, the input field holds
  the link, a line break and `invite_share_text`, ready to send:

```
┌──────────────────────────────────────────────┐
│ https://t.me/xemo_music_bot?start=Kx7pQ2mZ   │
│ An invite to our music bot                   │
└──────────────────────────────────────────────┘
```

To invite three friends, the admin sends `/invite` three times. Each friend gets their
own link.

### 2. Friend joins

1. The friend opens the link, taps Start, and the bot receives `/start Kx7pQ2mZ`.
2. If the code exists, has not been used, has not expired and has not been revoked, a
   `users` row is created (`invited_by` = the inviting admin, language from Telegram)
   and the code is used up. All of this happens in one step.
3. The friend gets the first-run picker, and picking a language edits it into the
   welcome (MVP spec, unchanged).
4. The inviting admin gets one new message in the admin's own language.

```
┌──────────────────────────────────────────────┐
│ Anna Kovalenko (@anna) joined with your      │
│ invite                                       │
└──────────────────────────────────────────────┘
```

If the friend has no username, the line shows only the name: `Anna joined with your
invite`.

### 3. Code does not work

The friend gets `invite_invalid` (MVP copy) in the language detected from Telegram, with
no keyboard. Nothing is created.

```
┌──────────────────────────────────────────────┐
│ This invite doesn't work anymore. Ask for a  │
│ new one                                      │
└──────────────────────────────────────────────┘
```

## UX decisions

| Decision | Choice | Source |
|----------|--------|--------|
| Uses per invite | Always one. No `/invite N` and no number buttons; one link is one person, so `invited_by` stays exact | Owner, 2026-10-27 |
| Several friends | Send `/invite` again; each call makes a fresh code | Owner, 2026-10-27 |
| Arguments after `/invite` | Ignored; the reply is the normal one, with no error | Owner, 2026-10-27 (the calmer option) |
| Expiry | 7 days from creation | Owner, 2026-10-27 |
| Admin reply | One line, "One-time invite ready", and `[ Copy ] [ Share ]` in one row; no link in the text | Owner, 2026-10-28 |
| Join notice | Only the inviting admin gets one line with the friend's name and @username | Owner, 2026-10-27 |
| Friend's onboarding | Unchanged: picker, then welcome; no "invited by" line | Owner, 2026-10-27 (recommended default) |
| Member or admin opens an invite | Normal `/start`; the code is not used, and no notice is sent | Owner, 2026-10-27 (recommended default) |
| Share text | One short line after the link | Owner, 2026-10-27 (recommended default) |
| Code format | 8 random characters `A-Z a-z 0-9`, case-sensitive | Owner-approved default, 2026-10-27 |
| Validity wording | Not shown; the 7-day expiry stays, a friend with an expired link asks for a new one | Owner, 2026-10-28 |
| When a code is used up | Only when a new `users` row is created | Owner-approved default, 2026-10-27 |
| Blocked user with a valid code | Stays blocked, gets `private_bot`, the code is not used | Owner-approved default, 2026-10-27 |
| Same code opened by two people at once | Checked when the second person joins: the first one in wins, the other gets `invite_invalid` | Owner-approved default, 2026-10-27 |
| Invite list (`/invites`) | None; it belongs with Revocation | Owner-approved default, 2026-10-27 |
| Button style | No `style` on Copy or Share; neither is the single key action | Owner, 2026-10-27 |
| Invite message after use | Not edited; it stays as sent | Owner, 2026-10-27 |
| Inviting admin removed from `ADMIN_IDS` | Their unused invites keep working, and the notice still goes to them | Owner, 2026-10-27 |
| Name in the notice | Telegram first and last name, HTML-escaped, cut to 40 characters with `…`; then ` (@username)` if they have one | Owner, 2026-10-27 |
| `/invite` from a member | `unknown_command`, as for any command they don't have | Owner, 2026-10-27 |

## Copy

`{friend}` is `invite_friend` (or just `{name}` when there is no username). `{name}` is
HTML-escaped.

| key | EN | UK | RU | notes |
|-----|----|----|----|-------|
| invite_created | `<b>`One-time invite ready`</b>` | `<b>`Одноразове запрошення готове`</b>` | `<b>`Одноразовое приглашение готово`</b>` | message, no format args; owner, 2026-10-28; UK and RU: proofread |
| invite_copy | Copy | Скопіювати | Копировать | button, `copy_text`; max 12 chars; no prefix symbol, the client draws its own icon |
| invite_share | Share | Поділитися | Поделиться | button, URL; max 12 chars; no prefix symbol, as for Copy |
| invite_share_text | An invite to our music bot | Запрошення до нашого бота | Приглашение в наш бот | sent by the admin, after the link; UK and RU: plain "бот", owner, 2026-10-27 |
| invite_friend | {name} (@{username}) | {name} (@{username}) | {name} (@{username}) | same in all three |
| invite_joined | {friend} joined with your invite | Ваше запрошення прийнято: {friend} | Ваше приглашение принято: {friend} | message to the inviting admin; UK and RU avoid the gendered past tense ("приєдналася"), so they don't mirror EN; proofread |
| invite_invalid | This invite doesn't work anymore. Ask for a new one | Це запрошення вже не діє. Попросіть нове | Это приглашение больше не действует. Попросите новое | unchanged, from the MVP spec |
| cmd_invite | Create an invite | Створити запрошення | Создать приглашение | unchanged, from the MVP spec; admin menus only |

## Edge cases & errors

- **Unknown code, or a malformed payload** (wrong length or characters): `invite_invalid`.
  A malformed payload is rejected without a database query. A stranger with any payload
  now gets `invite_invalid` instead of `private_bot`; `/start` with no payload still gets
  `private_bot`.
- **Used, expired or revoked code:** `invite_invalid`, and nothing is created.
- **Two people open the same code:** the first join wins and the other person gets
  `invite_invalid`.
- **The friend taps Start twice quickly:** the first update joins them. The second one
  finds a member and runs a normal `/start`, which sends the picker again (MVP rule:
  `/start` repeats the picker until a pick). The code is not used twice. Accepted.
- **Member or admin opens any invite link, including their own:** normal `/start`. The
  code is not used and no notice is sent.
- **Blocked user, valid or invalid code:** `private_bot`. The code is not used, and the
  reply says nothing about whether the code was valid.
- **`/invite some text`:** the text is ignored and the normal reply is sent.
- **Notice can't be delivered** (for example, the admin blocked the bot): log a warning.
  The friend's join is not affected.
- **Long or emoji-heavy names:** cut to 40 characters with `…`. Emoji count as 2
  characters and are kept. Newlines become spaces.
- **Copy button on a client without `copy_text` support:** use Share.
- **Old invite message after its code is used or has expired:** Copy and Share still
  work on a dead link, and the friend who opens it gets `invite_invalid`. The message is
  not edited.
- **Not in this flow:** search inputs, provider failures, downloads, cached tracks and
  expired results. There are no provider calls here; the MVP spec covers those.

## Technical notes

- Link: `https://t.me/<bot_username>?start=<code>`, with the username from `getMe`
  (fetched once). A deep-link start parameter is at most 64 base64url characters
  (checked 2026-10-27, core.telegram.org/api/links). 8 base62 characters fit, and `_`
  and `-` are never generated, so the code can't be misread.
- `/invite` reply: a new message with HTML parse mode and
  `link_preview_options.is_disabled = true`. It is never edited. One row of two buttons:
  - `copy_text: CopyTextButton(text=<https link>)`. The limit is 1-256 characters
    (checked 2026-10-27). No callback, so there is nothing to answer.
  - `url: https://t.me/share/url?url=<urlencoded link>&text=<urlencoded invite_share_text>`.
    The client puts the URL first, then a newline, then the text (core.telegram.org/api/links).
- Join: check the code, use it up, and create the user with `invited_by =
  invites.created_by` in one transaction. Under a race at most one join may succeed.
  Send the notice only after the join is committed; never announce a join that was
  rolled back.
- Notice: a new message to `invites.created_by`, in that user's `users.language`. The
  name comes from the joining update's `from_user` (`first_name`, `last_name`,
  `username`), so no new column is needed (`users.username` already exists).
- The access middleware has to let a stranger's `/start <payload>` through to the invite
  check. Today it answers it with `private_bot`.
- `cmd_invite` joins the admin chat-scope command menu.
- Ops note for the owner: friends who are config admins today already have a `users`
  row. Removing their id from `ADMIN_IDS` (then a restart) makes them members, so they
  need no invite.

## Open questions

- **Can members invite their own friends?** Left open by the owner. This design is
  admin-only (ADR 0003) but keeps the door open: `invited_by` is a `users` reference, and
  the notice goes to whoever created the code.
- **Closed, 2026-10-28: the `↗` prefix.** It rendered as a colour emoji on Android, so
  both prefixes are dropped and the labels are plain. The client draws its own corner icon
  on each button. Custom emoji icons should not go on these buttons, because they would
  double up with that icon.

## Out of scope

- `/revoke`, `/ban`, unban, invite and member lists (Revocation item).
- Choosing a number of uses or an expiry per invite.
- Members creating invites (see Open questions).
