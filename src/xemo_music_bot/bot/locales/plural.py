"""Plural forms for copy with a number in it (ADR 0005)."""

from dataclasses import dataclass

from xemo_music_bot.core.models import Language


@dataclass(slots=True, frozen=True)
class Plural:
    """The forms of one phrase for each kind of number, each with a ``{count}`` placeholder.

    English uses only ``one`` and ``many`` (its "other" form); its ``few`` repeats ``many``.

    Attributes:
        one: 1, and in Ukrainian and Russian also 21, 31, ... but not 11.
        few: Ukrainian and Russian 2-4, 22-24, ... but not 12-14.
        many: Every other number.
    """

    one: str
    few: str
    many: str


def plural(language: Language, count: int, forms: Plural) -> str:
    """Return the form of ``forms`` that fits ``count`` in ``language``, filled in.

    Args:
        language: The language of ``forms``; it decides which numbers take which form.
        count: The number, a non-negative integer.
        forms: The phrase's forms from that language's catalog.
    """
    if language == "en":
        form = forms.one if count == 1 else forms.many
    else:
        units, tens = count % 10, count % 100
        if units == 1 and tens != 11:
            form = forms.one
        elif 2 <= units <= 4 and not 12 <= tens <= 14:
            form = forms.few
        else:
            form = forms.many
    return form.format(count=count)
