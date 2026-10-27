import pytest

from xemo_music_bot.bot.locales.plural import Plural, plural
from xemo_music_bot.core.models import Language

# Each form names itself, so a failure shows which form was picked.
FORMS = Plural(one="{count} one", few="{count} few", many="{count} many")


@pytest.mark.parametrize(
    ("language", "count", "expected"),
    [
        pytest.param("en", 1, "1 one", id="en:1-is-one"),
        pytest.param("en", 0, "0 many", id="en:0-is-other"),
        pytest.param("en", 3, "3 many", id="en:3-is-other"),
        pytest.param("en", 21, "21 many", id="en:21-is-other"),
        pytest.param("uk", 1, "1 one", id="uk:1-is-one"),
        pytest.param("uk", 21, "21 one", id="uk:21-is-one"),
        pytest.param("uk", 11, "11 many", id="uk:11-is-many"),
        pytest.param("uk", 3, "3 few", id="uk:3-is-few"),
        pytest.param("uk", 24, "24 few", id="uk:24-is-few"),
        pytest.param("uk", 12, "12 many", id="uk:12-is-many"),
        pytest.param("uk", 7, "7 many", id="uk:7-is-many"),
        pytest.param("ru", 0, "0 many", id="ru:0-is-many"),
        pytest.param("ru", 101, "101 one", id="ru:101-is-one"),
        pytest.param("ru", 111, "111 many", id="ru:111-is-many"),
        pytest.param("ru", 112, "112 many", id="ru:112-is-many"),
        pytest.param("ru", 122, "122 few", id="ru:122-is-few"),
    ],
)
def test_plural_picks_the_form_for_the_number(
    language: Language, count: int, expected: str
) -> None:
    actual = plural(language, count, FORMS)
    assert actual == expected, f"{language} {count}: expected {expected!r}, got {actual!r}"
