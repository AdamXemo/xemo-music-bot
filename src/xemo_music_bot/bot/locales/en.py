"""English copy, the canonical source for the other languages."""

from xemo_music_bot.bot.locales.catalog import Texts
from xemo_music_bot.bot.locales.plural import Plural

EN = Texts(
    private_bot="This bot is private. To join, ask @Xemo999 for an invite",
    invite_invalid="This invite doesn't work anymore. Ask for a new one",
    invite_created="Invite link:\n{link}\nFor one person, works for {days}",
    invite_days=Plural(one="{count} day", few="{count} days", many="{count} days"),
    invite_copy="⧉ Copy",
    invite_share="↗ Share",
    invite_share_text="An invite to our music bot",
    invite_friend="{name} (@{username})",
    invite_joined="{friend} joined with your invite",
    welcome="Send me a track name and I'll find it",
    language_flag="🇬🇧",
    language_name="English",
    language_prompt="Choose a language",
    language_set="Language set to English",
    results_header="<b>{query}</b>",
    # RUF001 flags the single angle quotes used as pager arrows; they are real copy.
    pager_back="‹ Back",  # noqa: RUF001
    pager_next="Next ›",  # noqa: RUF001
    pager_counter="{page} / {pages}",
    track_loading="Loading…",
    no_results="Nothing found for “{query}”. Try fewer words or another spelling",
    search_failed="SoundCloud isn't responding. Try again in a minute",
    query_too_long="That's too long for a search. Try just the artist and title",
    not_text="Send the track name as text",
    link_not_supported="Search doesn't work with links. Send the track name instead",
    unknown_command="There's no such command. Try /help",
    too_long="This track is too long for Telegram ({duration}). Try a shorter version",
    too_large="“{track}” is too large for Telegram. Try a shorter version",
    download_failed="Couldn't get “{track}”. Tap it again to retry, or pick another one",
    track_unavailable="SoundCloud doesn't allow downloading “{track}”. Try another version",
    already_loading="Already on its way",
    results_expired="These results have expired. Send the name again",
    cmd_start="Start the bot",
    cmd_language="Change language",
    cmd_invite="Create an invite",
    bot_short_description="Private music bot for a circle of friends. Invite only",
    bot_description=(
        "Send a track name, pick it from the list and get the audio right in the chat"
        "\n\n"
        "This bot is private: ask @Xemo999 for an invite"
    ),
)
