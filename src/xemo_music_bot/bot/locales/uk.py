"""Ukrainian copy."""

from xemo_music_bot.bot.locales.catalog import Texts

UK = Texts(
    private_bot="Це приватний бот. Щоб приєднатися, попросіть запрошення в @Xemo999",
    # RUF001 mistakes the one-letter Ukrainian conjunction for a Latin "i"; it is real copy.
    welcome="Надішліть назву треку, і я його знайду",  # noqa: RUF001
    language_flag="🇺🇦",
    language_name="Українська",
    language_prompt="Виберіть мову",
    language_set="Мову змінено на українську",
    cmd_start="Запустити бота",
    cmd_language="Змінити мову",
    bot_short_description="Приватний музичний бот для кола друзів. Лише за запрошенням",
    bot_description=(
        "Надішліть назву треку, виберіть його зі списку й отримайте аудіо просто в чаті"
        "\n\n"
        "Бот приватний: попросіть запрошення в @Xemo999"
    ),
)
