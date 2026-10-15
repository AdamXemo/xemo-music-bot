"""Russian copy."""

from xemo_music_bot.bot.locales.catalog import Texts

RU = Texts(
    # RUF001 mistakes the one-letter Russian preposition for a Latin "y"; it is real copy.
    private_bot="Это закрытый бот. Чтобы присоединиться, попросите приглашение у @Xemo999",  # noqa: RUF001
    # RUF001 reads the all-look-alike pronoun as Latin letters; it is real copy.
    welcome="Пришлите название трека, и я его найду",  # noqa: RUF001
    language_flag="🇷🇺",
    language_name="Русский",
    language_prompt="Выберите язык",
    language_set="Язык изменён на русский",
    results_header="<b>{query}</b>",
    # RUF001 flags the single angle quotes used as pager arrows; they are real copy.
    pager_back="‹ Назад",  # noqa: RUF001
    pager_next="Далее ›",  # noqa: RUF001
    pager_counter="{page} / {pages}",
    no_results=(
        "По запросу «{query}» ничего не нашлось. Попробуйте запрос покороче или другое написание"
    ),
    search_failed="SoundCloud не отвечает. Попробуйте ещё раз через минуту",
    query_too_long="Слишком длинный запрос. Попробуйте только исполнителя и название",
    not_text="Пришлите название трека текстом",
    link_not_supported="Поиск по ссылкам не работает. Пришлите название трека",
    unknown_command="Такой команды нет. Попробуйте /help",
    results_expired="Эти результаты устарели. Пришлите название ещё раз",
    cmd_start="Запустить бота",
    cmd_language="Сменить язык",
    bot_short_description="Закрытый музыкальный бот для своих. Только по приглашению",
    bot_description=(
        # RUF001 reads the all-look-alike pronoun as Latin letters; it is real copy.
        "Пришлите название трека, выберите его в списке и получите аудио прямо в чате"  # noqa: RUF001
        "\n\n"
        # RUF001 mistakes the one-letter Russian preposition for a Latin "y"; it is real copy.
        "Бот закрытый: попросите приглашение у @Xemo999"  # noqa: RUF001
    ),
)
