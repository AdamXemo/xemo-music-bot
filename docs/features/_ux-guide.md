# UX guide

Cross-cutting UX decisions for every feature spec. Extends "UX principles" in
[ARCHITECTURE.md](../ARCHITECTURE.md). Feature-specific decisions live in each spec.

## Decisions

| Decision | Choice | Source |
|----------|--------|--------|
| Look and feel | Minimal and calm: little text, few well-chosen emoji, feels like a premium app | Owner, 2026-10-10 |
| Languages | `en`, `uk`, `ru`; English is canonical; mechanics per ADR 0005 | ADR 0005 |
| Form of address | Formal: UK "ви", RU "вы" | Owner, 2026-10-10 |
| Emoji | Only premium custom emoji (the owner has Telegram Premium). No regular Unicode emoji in the UI | Owner, 2026-10-10 |
| Emoji placement | Free: button icons and message text, wherever one genuinely helps. Owner reviews every use | Owner, 2026-10-10 |
| Colored buttons | `style` only on the one key action of a screen; never on lists or paging; never `danger` | Owner, 2026-10-10 (calm look); exact rule assumed default |
| Formatting | HTML parse mode. Bold for at most one thing per message. All provider text is HTML-escaped | Assumed default |
| Voice | Short, plain, friendly; one idea per message; errors say what happened and what to do next | Assumed default |
| Bot speech | Bot may say "I" in present/future tense only; no gendered past tense for the bot or the user | Assumed default |
| Device | Phone first: label budgets are measured on a phone in the longest language | Assumed default |

## Emoji rules

- Emoji are named **slots** (for example `language`, `loading`). Specs reference slots,
  never emoji ids. The ids live in one constants module; the owner picks the actual
  custom emoji later. A slot with no id renders nothing, so every screen works without
  emoji.
- In buttons a slot is `icon_custom_emoji_id`: no Unicode character appears at all.
- In message text a slot is a `custom_emoji` entity. Telegram requires a regular emoji
  under it as the fallback; use the custom emoji's own alt emoji. Users may see that
  fallback in notifications, the chat list, reply quotes and copied text. This is the
  only accepted appearance of a Unicode emoji.
- Places that cannot hold custom emoji get **no emoji**: callback toasts and alerts,
  command descriptions, bot description and short description, audio metadata.
- An emoji never carries meaning alone; the text must make sense without it.
- If the owner's Premium lapses, button icons disappear and message emoji fall back to
  Unicode. Accepted risk.
- Emoji inside track titles are user content, not UI; they are shown as is.

## Typography

- Quotes: EN `“…”`, UK and RU `«…»`.
- Separator between title and duration: ` · `. Duration `m:ss`, or `h:mm:ss` from 1 hour.
- Track display in messages: `Artist - Title` (matches the audio player). On track
  buttons: `Title - Artist · m:ss`, artist cut first, duration always kept. Both use
  cleaned metadata: a title of the form `X - Y` is split into performer `X` and title
  `Y`, and junk like "(Official Audio)" is removed. Rules in the MVP spec.
- Ellipsis is the single character `…`.
- Language names are always in their own language, without flags: English, Українська,
  Русский.

## Glossary

| EN | UK | RU | Note |
|----|----|----|------|
| track | трек | трек | never "song" in UI |
| track name | назва треку | название трека | what the user searches by |
| results | результати | результаты | |
| invite | запрошення | приглашение | |
| language | мова | язык | |
| audio | аудіо | аудио | the delivered message |
| send (user action) | надішліть | пришлите | formal imperative |
| choose | виберіть | выберите | |
| try again | спробуйте ще раз | попробуйте ещё раз | |
