"""Ukrainian copy."""

from xemo_music_bot.bot.locales.catalog import Texts

UK = Texts(
    private_bot=(
        "Це приватний бот. Щоб приєднатися, попросіть запрошення в друга, який ним користується."
    ),
    # RUF001 mistakes the one-letter Ukrainian conjunction for a Latin "i"; it is real copy.
    welcome="Надішліть назву треку, і я його знайду.",  # noqa: RUF001
    language_button="Мова: українська",
    language_name="Українська",
    language_prompt="Виберіть мову.",
    language_set="Готово, тепер я говорю українською.",
)
