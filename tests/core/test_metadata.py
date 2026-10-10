"""Spec for clean_track_name: each group is one rule, each id reads as one example.

Titles follow real SoundCloud uploads in English, Russian and Ukrainian.
"""

import pytest

from xemo_music_bot.core.metadata import TrackName, clean_track_name

EM = "\u2014"
EN = "\u2013"


def case(case_id: str, raw_title: str, uploader: str, artist: str, title: str) -> object:
    """One example: raw title and uploader in, cleaned performer and title out."""
    return pytest.param(raw_title, uploader, TrackName(artist=artist, title=title), id=case_id)


def check(raw_title: str, uploader: str, expected: TrackName) -> None:
    actual = clean_track_name(raw_title, uploader)
    assert actual == expected, (
        f"\n  input:    {raw_title!r} uploaded by {uploader!r}"
        f"\n  expected: {expected}\n  actual:   {actual}"
    )


PARAMS = ("raw_title", "uploader", "expected")

SPLITS_PERFORMER_FROM_TITLE = [
    case("en: hyphen", "Daft Punk - Instant Crush", "Aaron Gardea", "Daft Punk", "Instant Crush"),
    case("en: en dash", f"Daft Punk {EN} Instant Crush", "dp", "Daft Punk", "Instant Crush"),
    case("ru: em dash", f"Баста {EM} Сансара", "basta_fan", "Баста", "Сансара"),
    case("uk: hyphen", "Океан Ельзи - Обійми", "Okean Elzy", "Океан Ельзи", "Обійми"),
    case("uk: latin artist, en dash", f"Kalush {EN} Стефанія", "kalush", "Kalush", "Стефанія"),
    case("ru: latin artist", "MONA - Пачка сигарет", "mona", "MONA", "Пачка сигарет"),
    case("ru: all caps kept", "СКРИПТОНИТ - ПОЛОЖЕНИЕ", "x", "СКРИПТОНИТ", "ПОЛОЖЕНИЕ"),
    case(
        "ru: feat. stays with artist",
        "Тимати feat. Егор Крид - Гучи",
        "blackstar",
        "Тимати feat. Егор Крид",
        "Гучи",
    ),
    case("en: hyphen inside a name", "Jay-Z - 99 Problems", "rapfan", "Jay-Z", "99 Problems"),
    case("ru: hyphen inside a name", "Би-2 - Варвара", "bi2", "Би-2", "Варвара"),
    case("en: number as artist", "311 - Amber", "fan", "311", "Amber"),
    case(
        "en: only the first dash splits",
        "Artist - Song - Radio Edit",
        "label",
        "Artist",
        "Song - Radio Edit",
    ),
    case(
        "en: title starting with a version word",
        "Oasis - Live Forever",
        "fan",
        "Oasis",
        "Live Forever",
    ),
]

KEEPS_TITLE_WHOLE_WHEN_DASH_INTRODUCES_A_VERSION = [
    case("en: live", "Intro - Live", "The xx", "The xx", "Intro - Live"),
    case("en: radio edit", "Song - Radio Edit", "Artist", "Artist", "Song - Radio Edit"),
    case(
        "en: year and remaster",
        f"Song {EN} 2011 Remastered Version",
        "Artist",
        "Artist",
        f"Song {EN} 2011 Remastered Version",
    ),
    case("ru: remix", "Сансара - Ремикс", "Баста", "Баста", "Сансара - Ремикс"),
    case(
        "ru: cover",
        f"Кукушка {EM} кавер",
        "Полина Гагарина",
        "Полина Гагарина",
        f"Кукушка {EM} кавер",
    ),
    case("uk: remix", "Обійми - Ремікс", "Океан Ельзи", "Океан Ельзи", "Обійми - Ремікс"),
    case("uk: live", "Обійми - Live", "Океан Ельзи", "Океан Ельзи", "Обійми - Live"),
]

STRIPS_JUNK_SUFFIX = [
    case(
        "en: (Official Audio)",
        "Daft Punk - Instant Crush (Official Audio)",
        "x",
        "Daft Punk",
        "Instant Crush",
    ),
    case(
        "en: all caps [OFFICIAL MUSIC VIDEO]",
        "Song [OFFICIAL MUSIC VIDEO]",
        "Artist",
        "Artist",
        "Song",
    ),
    case("en: (Lyric Video)", "Song (Lyric Video)", "Artist", "Artist", "Song"),
    case("en: | Free Download", "Song | Free Download", "Artist", "Artist", "Song"),
    case("en: stacked (Out Now) [FREE DL]", "Song (Out Now) [FREE DL]", "Artist", "Artist", "Song"),
    case("en: loose spacing in brackets", "Song ( official   audio )", "Artist", "Artist", "Song"),
    case("ru: official audio", "Баста - Сансара (Официальное аудио)", "x", "Баста", "Сансара"),
    case(
        "ru: official clip in caps",
        "MONA - Пачка сигарет [ОФИЦИАЛЬНЫЙ КЛИП]",
        "x",
        "MONA",
        "Пачка сигарет",
    ),
    case(
        "ru: clip premiere",
        "Artik & Asti - Под гипнозом (Премьера клипа)",
        "x",
        "Artik & Asti",
        "Под гипнозом",
    ),
    case(
        "ru: track premiere",
        "Скриптонит - Положение [Премьера трека]",
        "x",
        "Скриптонит",
        "Положение",
    ),
    case("ru: song lyrics", "Би-2 - Варвара [Текст песни]", "x", "Би-2", "Варвара"),
    case(
        "ru: russian and english tags stacked",
        "Скриптонит - Положение (Премьера) [Lyrics]",
        "x",
        "Скриптонит",
        "Положение",
    ),
    case(
        "uk: official audio", "Океан Ельзи - Обійми (Офіційне аудіо)", "x", "Океан Ельзи", "Обійми"
    ),
    case("uk: official clip", "Kalush - Стефанія (Офіційний кліп)", "x", "Kalush", "Стефанія"),
    case("uk: track premiere", "Kalush - Стефанія (Прем'єра треку)", "x", "Kalush", "Стефанія"),
    case(
        "uk: premiere with typographic apostrophe",
        "Kalush - Стефанія (Прем\u2019єра)",
        "x",
        "Kalush",
        "Стефанія",
    ),
    case(
        "uk: song lyrics after |",
        "Океан Ельзи - Обійми | Текст пісні",
        "x",
        "Океан Ельзи",
        "Обійми",
    ),
]

KEEPS_CREDITS_AND_VERSION_TAGS = [
    case(
        "en: remix in brackets",
        "Daft Punk - Instant Crush (David Mackay Remix) [Free Download]",
        "David Mackay",
        "Daft Punk",
        "Instant Crush (David Mackay Remix)",
    ),
    case(
        "en: feat. in brackets",
        "Instant Crush (feat. Julian Casablancas)",
        "Daft Punk",
        "Daft Punk",
        "Instant Crush (feat. Julian Casablancas)",
    ),
    case(
        "en: ft. and (Official) are not junk",
        "Daft Punk - Instant Crush ft. Julian Casablancas (Official)",
        "x",
        "Daft Punk",
        "Instant Crush ft. Julian Casablancas (Official)",
    ),
    case(
        "ru: prod. credit",
        "MONA - Пачка сигарет (prod. by Palagin)",
        "x",
        "MONA",
        "Пачка сигарет (prod. by Palagin)",
    ),
    case(
        "en: (Live) (Extended Edit) [Cover]",
        "Song (Live) (Extended Edit) [Cover]",
        "Artist",
        "Artist",
        "Song (Live) (Extended Edit) [Cover]",
    ),
    case(
        "en: junk not at the end",
        "Song (Official Audio) Remix",
        "Artist",
        "Artist",
        "Song (Official Audio) Remix",
    ),
    case("en: bare word audio", "Audio", "Artist", "Artist", "Audio"),
    case(
        "ru: remix credit in brackets",
        "Баста - Сансара (DJ Smash ремикс)",
        "x",
        "Баста",
        "Сансара (DJ Smash ремикс)",
    ),
    case(
        "ru: pri uch. (with) credit",
        "Каста - Вокруг шум (при уч. Хамиль)",
        "x",
        "Каста",
        "Вокруг шум (при уч. Хамиль)",
    ),
    case("uk: remix in brackets", "Kalush - Стефанія (ремікс)", "x", "Kalush", "Стефанія (ремікс)"),
    case(
        "ru: emoji kept",
        "Ягода малинка \U0001f353\U0001f525",
        "Хабиб",
        "Хабиб",
        "Ягода малинка \U0001f353\U0001f525",
    ),
]

NORMALIZES_SPACING_QUOTES_AND_TRACK_NUMBERS = [
    case(
        "en: tabs, newlines, extra spaces",
        "  Daft   Punk -\tInstant\nCrush  ",
        " Up\u00a0loader ",
        "Daft Punk",
        "Instant Crush",
    ),
    case("en: control character", "Song\x00Title", "Artist", "Artist", "Song Title"),
    case("ru: extra spaces around em dash", f"Баста   {EM}   Сансара", "x", "Баста", "Сансара"),
    case("ru: uploader spacing", "Сансара", "  Баста  ", "Баста", "Сансара"),
    case("ru: title in guillemets", "Баста - \u00abСансара\u00bb", "x", "Баста", "Сансара"),
    case("ru: title in low-high quotes", "Би-2 - \u201eВарвара\u201c", "x", "Би-2", "Варвара"),
    case(
        "uk: whole title in curly quotes",
        "\u201cОбійми\u201d",
        "Океан Ельзи",
        "Океан Ельзи",
        "Обійми",
    ),
    case(
        "en: title in straight quotes",
        'Daft Punk - "Instant Crush"',
        "x",
        "Daft Punk",
        "Instant Crush",
    ),
    case(
        "en: quotes inside the title kept",
        'The "Real" Slim Shady',
        "Eminem",
        "Eminem",
        'The "Real" Slim Shady',
    ),
    case("ru: track number", "01. Сансара", "Баста", "Баста", "Сансара"),
    case("ru: track number before artist", "01. Баста - Сансара", "x", "Баста", "Сансара"),
    case("uk: track number after dash", "Океан Ельзи - 03. Обійми", "x", "Океан Ельзи", "Обійми"),
    case("en: track number with bracket", "1) Intro", "The xx", "The xx", "Intro"),
    case("en: number that belongs to the title", "99 Problems", "Jay-Z", "Jay-Z", "99 Problems"),
]

FALLS_BACK = [
    case("en: no dash, uploader is artist", "Jay-Z", "uploader", "uploader", "Jay-Z"),
    case("ru: no dash, uploader is artist", "Сансара", "Баста", "Баста", "Сансара"),
    case(
        "en: dash without space after",
        "Daft Punk -Instant Crush",
        "dp",
        "dp",
        "Daft Punk -Instant Crush",
    ),
    case("en: leading dash", "- Instant Crush", "dp", "dp", "- Instant Crush"),
    case(
        "en: only junk keeps raw title", "(Official Audio)", "Artist", "Artist", "(Official Audio)"
    ),
    case(
        "en: only stacked junk",
        "[Free Download] | Out Now",
        "Artist",
        "Artist",
        "[Free Download] | Out Now",
    ),
    case("ru: only junk keeps raw title", "(Премьера клипа)", "Баста", "Баста", "(Премьера клипа)"),
    case("en: no uploader name", "Song", "", "", "Song"),
]

KNOWN_LIMITATIONS = [
    case(
        "en: title starting with the track name splits",
        "Intro - Renaissance Tour Live",
        "BEYONCÉ",
        "Intro",
        "Renaissance Tour Live",
    ),
    case(
        "ru: em dash without spaces is not split",
        f"Баста{EM}Сансара",
        "basta_fan",
        "basta_fan",
        f"Баста{EM}Сансара",
    ),
    case(
        "ru: artist and title in guillemets without dash",
        "Баста \u00abСансара\u00bb",
        "basta_fan",
        "basta_fan",
        "Баста \u00abСансара\u00bb",
    ),
    case(
        "ru: junk tag with extra words stays",
        "Баста - Сансара (Премьера клипа, 2024)",
        "x",
        "Баста",
        "Сансара (Премьера клипа, 2024)",
    ),
    case(
        "ru: track number before a dash reads as artist", "01 - Сансара", "Баста", "01", "Сансара"
    ),
]


@pytest.mark.parametrize(PARAMS, SPLITS_PERFORMER_FROM_TITLE)
def test_splits_performer_from_title(raw_title: str, uploader: str, expected: TrackName) -> None:
    check(raw_title, uploader, expected)


@pytest.mark.parametrize(PARAMS, KEEPS_TITLE_WHOLE_WHEN_DASH_INTRODUCES_A_VERSION)
def test_keeps_title_whole_when_dash_introduces_a_version(
    raw_title: str, uploader: str, expected: TrackName
) -> None:
    check(raw_title, uploader, expected)


@pytest.mark.parametrize(PARAMS, STRIPS_JUNK_SUFFIX)
def test_strips_junk_suffix(raw_title: str, uploader: str, expected: TrackName) -> None:
    check(raw_title, uploader, expected)


@pytest.mark.parametrize(PARAMS, KEEPS_CREDITS_AND_VERSION_TAGS)
def test_keeps_credits_and_version_tags(raw_title: str, uploader: str, expected: TrackName) -> None:
    check(raw_title, uploader, expected)


@pytest.mark.parametrize(PARAMS, NORMALIZES_SPACING_QUOTES_AND_TRACK_NUMBERS)
def test_normalizes_spacing_quotes_and_track_numbers(
    raw_title: str, uploader: str, expected: TrackName
) -> None:
    check(raw_title, uploader, expected)


@pytest.mark.parametrize(PARAMS, FALLS_BACK)
def test_falls_back_to_uploader_or_raw_title(
    raw_title: str, uploader: str, expected: TrackName
) -> None:
    check(raw_title, uploader, expected)


@pytest.mark.parametrize(PARAMS, KNOWN_LIMITATIONS)
def test_known_limitation(raw_title: str, uploader: str, expected: TrackName) -> None:
    """Imperfect results we accept for now; a fix should flip these into real rules."""
    check(raw_title, uploader, expected)
