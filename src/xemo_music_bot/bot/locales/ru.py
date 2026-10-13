"""Russian copy."""

from xemo_music_bot.bot.locales.catalog import Texts

RU = Texts(
    private_bot=(
        "Это закрытый бот. Чтобы присоединиться, попросите приглашение "
        # RUF001 mistakes the one-letter Russian preposition for a Latin "y"; it is real copy.
        "у друга, который им пользуется."  # noqa: RUF001
    ),
    # RUF001 reads the all-look-alike pronoun as Latin letters; it is real copy.
    welcome="Пришлите название трека, и я его найду.",  # noqa: RUF001
    language_button="Язык: русский",
    language_name="Русский",
    language_prompt="Выберите язык.",
    language_set="Готово, теперь я говорю по-русски.",
)
