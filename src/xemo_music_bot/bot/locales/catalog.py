"""The shape every language catalog must fill (ADR 0005)."""

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class Texts:
    """All user-facing copy for one language.

    Every field is required, so mypy rejects a catalog that misses a key. Message fields
    are HTML (escape ``&``, ``<`` and ``>``); button-label fields are plain text.

    Attributes:
        private_bot: Reply to `/start` from a stranger or a blocked user.
        welcome: Reply to `/start` from a member or an admin who has picked a language.
        language_flag: The language's flag, before its name on picker buttons; the only
            Unicode emoji allowed in the copy (UX guide, "Language flags").
        language_name: The language's own name, after the flag on its picker button.
        language_prompt: Text of the language picker.
        language_set: Confirmation after picking a language from `/language`.
        results_header: Text of the results message; ``{query}`` is the HTML-escaped query.
        pager_back: Label of the button to the previous page.
        pager_next: Label of the button to the next page.
        pager_counter: Label of the disabled page counter; ``{page}`` and ``{pages}``.
        no_results: Reply when nothing matched; ``{query}`` is the HTML-escaped query.
        search_failed: Reply when the music source fails.
        query_too_long: Reply to a query over the length limit.
        not_text: Reply to a message that is not text.
        link_not_supported: Reply to text with a link in it.
        unknown_command: Reply to a command the bot does not have.
        results_expired: Toast on a tap on results that are gone from the cache.
        cmd_start: Description of `/start` in the command menu.
        cmd_language: Description of `/language` in the command menu.
        bot_short_description: Short description on the bot's profile (Telegram limit 120).
        bot_description: Description shown in an empty chat with the bot (Telegram limit 512).
    """

    private_bot: str
    welcome: str
    language_flag: str
    language_name: str
    language_prompt: str
    language_set: str
    results_header: str
    pager_back: str
    pager_next: str
    pager_counter: str
    no_results: str
    search_failed: str
    query_too_long: str
    not_text: str
    link_not_supported: str
    unknown_command: str
    results_expired: str
    cmd_start: str
    cmd_language: str
    bot_short_description: str
    bot_description: str
