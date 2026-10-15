"""English copy, the canonical source for the other languages."""

from xemo_music_bot.bot.locales.catalog import Texts

EN = Texts(
    private_bot="This bot is private. To join, ask @Xemo999 for an invite",
    welcome="Send me a track name and I'll find it",
    language_flag="🇬🇧",
    language_name="English",
    language_prompt="Choose a language",
    language_set="Language set to English",
    cmd_start="Start the bot",
    cmd_language="Change language",
    bot_short_description="Private music bot for a circle of friends. Invite only",
    bot_description=(
        "Send a track name, pick it from the list and get the audio right in the chat"
        "\n\n"
        "This bot is private: ask @Xemo999 for an invite"
    ),
)
