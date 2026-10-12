"""Russian copy."""

from xemo_music_bot.bot.locales.catalog import Texts

RU = Texts(
    greeting="Привет! Это Xemo Music. Поиск треков уже скоро.",
    private_bot=(
        "Это закрытый бот. Чтобы присоединиться, попросите приглашение "
        # RUF001 mistakes the one-letter Russian preposition for a Latin "y"; it is real copy.
        "у друга, который им пользуется."  # noqa: RUF001
    ),
)
