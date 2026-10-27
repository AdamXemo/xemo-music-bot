"""The shape every language catalog must fill (ADR 0005)."""

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class Texts:
    """All user-facing copy for one language.

    Every field is required, so mypy rejects a catalog that misses a key. Message fields
    are HTML (escape ``&``, ``<`` and ``>``); button-label fields are plain text.

    Attributes:
        private_bot: Reply to `/start` from a stranger or a blocked user.
        invite_invalid: Reply to a stranger's `/start` with a code that does not work.
        invite_created: Reply to `/invite`: one bold line; the link is on its buttons.
        invite_copy: Label of the button that copies the invite link.
        invite_share: Label of the button that shares the invite link.
        invite_share_text: Line Telegram puts after the link when it is shared.
        invite_friend: A friend with a username in ``invite_joined``; ``{name}`` is
            HTML-escaped, ``{username}`` has no "@".
        invite_joined: Notice to the inviting user; ``{friend}`` is ``invite_friend``,
            or just the escaped name for a friend without a username.
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
        track_loading: Label of the disabled button a track becomes while it downloads.
        no_results: Reply when nothing matched; ``{query}`` is the HTML-escaped query.
        search_failed: Reply when the music source fails.
        query_too_long: Reply to a query over the length limit.
        not_text: Reply to a message that is not text.
        link_not_supported: Reply to text with a link in it.
        unknown_command: Reply to a command the bot does not have.
        too_long: Alert on a track too long to send; ``{duration}`` is its length.
        too_large: Reply when the file is over Telegram's limit; ``{track}`` is the
            HTML-escaped ``Artist - Title``.
        download_failed: Reply when the download or upload failed; ``{track}`` as above.
        track_unavailable: Reply when the source refuses the track (Go+ preview or DRM);
            ``{track}`` as above.
        already_loading: Toast on a tap on a track that is already downloading.
        results_expired: Toast on a tap on results that are gone from the cache.
        cmd_start: Description of `/start` in the command menu.
        cmd_language: Description of `/language` in the command menu.
        cmd_invite: Description of `/invite` in the admins' command menu.
        bot_short_description: Short description on the bot's profile (Telegram limit 120).
        bot_description: Description shown in an empty chat with the bot (Telegram limit 512).
    """

    private_bot: str
    invite_invalid: str
    invite_created: str
    invite_copy: str
    invite_share: str
    invite_share_text: str
    invite_friend: str
    invite_joined: str
    welcome: str
    language_flag: str
    language_name: str
    language_prompt: str
    language_set: str
    results_header: str
    pager_back: str
    pager_next: str
    pager_counter: str
    track_loading: str
    no_results: str
    search_failed: str
    query_too_long: str
    not_text: str
    link_not_supported: str
    unknown_command: str
    too_long: str
    too_large: str
    download_failed: str
    track_unavailable: str
    already_loading: str
    results_expired: str
    cmd_start: str
    cmd_language: str
    cmd_invite: str
    bot_short_description: str
    bot_description: str
