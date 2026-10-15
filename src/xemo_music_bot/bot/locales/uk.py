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
    results_header="<b>{query}</b>",
    # RUF001 flags the single angle quotes used as pager arrows; they are real copy.
    pager_back="‹ Назад",  # noqa: RUF001
    pager_next="Далі ›",  # noqa: RUF001
    pager_counter="{page} / {pages}",
    no_results=(
        # RUF001 reads Cyrillic look-alike letters as Latin; it is real copy.
        "За запитом «{query}» нічого не знайдено. "  # noqa: RUF001
        "Спробуйте коротший запит або інше написання"  # noqa: RUF001
    ),
    search_failed="SoundCloud не відповідає. Спробуйте ще раз за хвилину",
    query_too_long="Задовгий запит. Спробуйте лише виконавця й назву",
    not_text="Надішліть назву треку текстом",
    link_not_supported="Пошук за посиланнями не працює. Надішліть назву треку",
    unknown_command="Такої команди немає. Спробуйте /help",
    results_expired="Ці результати застаріли. Надішліть назву ще раз",
    cmd_start="Запустити бота",
    cmd_language="Змінити мову",
    bot_short_description="Приватний музичний бот для кола друзів. Лише за запрошенням",
    bot_description=(
        "Надішліть назву треку, виберіть його зі списку й отримайте аудіо просто в чаті"
        "\n\n"
        "Бот приватний: попросіть запрошення в @Xemo999"
    ),
)
