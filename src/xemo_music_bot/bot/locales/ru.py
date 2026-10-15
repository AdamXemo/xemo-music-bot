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
)
