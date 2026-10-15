from unicodedata import east_asian_width

import pytest

from xemo_music_bot.bot.labels import MAX_WIDTH, result_label
from xemo_music_bot.core.models import Track

FAMILY = "\U0001f468\u200d\U0001f469\u200d\U0001f467"  # one emoji made of three joined ones
HEART = "\u2764\ufe0f"  # a 1-wide symbol turned into an emoji by a variation selector
HEADPHONES = "\U0001f3a7"


def make_track(title: str, artist: str = "", duration: int = 200) -> Track:
    return Track("soundcloud", "1", title, artist, duration, None, "https://sc/1")


@pytest.mark.parametrize(
    ("seconds", "shown"),
    [
        pytest.param(0, "0:00", id="zero"),
        pytest.param(5, "0:05", id="seconds-are-padded"),
        pytest.param(61, "1:01", id="minutes-are-not-padded"),
        pytest.param(337, "5:37", id="minutes-and-seconds"),
        pytest.param(3599, "59:59", id="last-second-before-an-hour"),
        pytest.param(3600, "1:00:00", id="an-hour-gets-hours"),
        pytest.param(3735, "1:02:15", id="hours-minutes-seconds"),
        pytest.param(37230, "10:20:30", id="two-digit-hours"),
        pytest.param(-4, "0:00", id="negative-is-zero"),
    ],
)
def test_duration_is_shown_as_minutes_or_hours(seconds: int, shown: str) -> None:
    assert result_label(make_track("Song", "Artist", seconds)) == f"Song - Artist · {shown}"


def test_label_without_artist_has_no_separator() -> None:
    assert result_label(make_track("Instant Crush", "", 337)) == "Instant Crush · 5:37"


def test_label_that_exactly_fills_the_budget_is_kept_whole() -> None:
    # 10 + 3 + 12 + len(" · 3:20") = 32.
    assert result_label(make_track("T" * 10, "A" * 12)) == f"{'T' * 10} - {'A' * 12} · 3:20"


def test_artist_is_cut_with_an_ellipsis_by_the_missing_characters() -> None:
    label = result_label(make_track("T" * 10, "A" * 13))

    assert label == f"{'T' * 10} - {'A' * 11}… · 3:20"
    assert len(label) == MAX_WIDTH


def test_artist_keeps_five_characters_including_the_ellipsis() -> None:
    # Room for the artist is exactly 5: "AAAA…".
    assert result_label(make_track("T" * 17, "A" * 30)) == f"{'T' * 17} - AAAA… · 3:20"


def test_artist_is_dropped_when_fewer_than_five_characters_would_remain() -> None:
    # Room for the artist is 4, so the artist and its " - " go and the title stays whole.
    assert result_label(make_track("T" * 18, "A" * 30)) == f"{'T' * 18} · 3:20"


def test_artist_cut_does_not_leave_a_space_before_the_ellipsis() -> None:
    label = result_label(make_track("Instant Crush", "Daft Punk", 4500))

    assert label == "Instant Crush - Daft… · 1:15:00"


def test_artist_is_dropped_when_the_cut_leaves_under_five_characters_after_trimming() -> None:
    # Room is 5, but "Abc " loses its space before the ellipsis and "Abc…" is only 4.
    assert result_label(make_track("T" * 17, "Abc defgh")) == f"{'T' * 17} · 3:20"


def test_title_is_cut_at_a_word_boundary_once_the_artist_is_dropped() -> None:
    label = result_label(make_track("Instant Crush (feat. Jenny Kim)", "Daft Punk", 337))

    assert label == "Instant Crush (feat.… · 5:37"


def test_title_cut_that_falls_between_words_keeps_the_whole_words() -> None:
    # Room for the title and ellipsis is 24 and the cut falls right after the second word.
    assert result_label(make_track("a" * 11 + " " + "b" * 12 + " cc")) == (
        f"{'a' * 11} {'b' * 12}… · 3:20"
    )


def test_one_long_word_is_cut_at_a_character_boundary() -> None:
    assert result_label(make_track("A" * 40, "Artist")) == f"{'A' * 24}… · 3:20"


def test_word_longer_than_the_space_is_cut_inside_instead_of_dropped() -> None:
    assert result_label(make_track("A " + "B" * 40)) == f"A {'B' * 22}… · 3:20"


def test_emoji_in_the_artist_count_as_two_when_cutting_it() -> None:
    label = result_label(make_track("T" * 10, HEADPHONES * 8))

    # Room is 12: five emoji (10) and the ellipsis fit, a sixth does not.
    assert label == f"{'T' * 10} - {HEADPHONES * 5}… · 3:20"


def test_combining_marks_add_no_width() -> None:
    title = "é" * 25  # 25 visible characters, 50 code points

    assert result_label(make_track(title)) == f"{title} · 3:20"


@pytest.mark.parametrize(
    ("glyph", "kept"),
    [
        pytest.param(HEADPHONES, 12, id="emoji"),
        pytest.param(FAMILY, 12, id="joined-emoji"),
        pytest.param(HEART, 12, id="symbol-with-emoji-presentation"),
        pytest.param("\u65e5", 12, id="wide-character"),
    ],
)
def test_wide_glyphs_count_as_two_and_are_never_split(glyph: str, kept: int) -> None:
    # 24 wide is the most that fits next to " · 3:20" with the title alone.
    assert result_label(make_track(glyph * kept, "Artist")) == f"{glyph * kept} · 3:20"
    assert result_label(make_track(glyph * (kept + 1), "Artist")) == f"{glyph * kept}… · 3:20"


def test_glyph_that_does_not_fit_is_dropped_whole() -> None:
    assert result_label(make_track("A" * 24 + HEADPHONES)) == f"{'A' * 24}… · 3:20"


def _display_width(text: str) -> int:
    """Width as a reader sees it: wide characters count 2, joiners and selectors 0."""
    return sum(
        0 if char in ("\u200d", "\ufe0f") else 2 if east_asian_width(char) == "W" else 1
        for char in text
    )


@pytest.mark.parametrize("glyph", ["x", HEADPHONES], ids=["ascii", "emoji"])
def test_duration_is_never_cut_and_the_label_stays_in_budget(glyph: str) -> None:
    for title_length in range(1, 41):
        for artist_length in range(0, 41, 4):
            title = " ".join([glyph * 2] * title_length)[: title_length * 2]
            label = result_label(make_track(title, glyph * artist_length, 3735))

            assert label.endswith(" · 1:02:15"), (title, artist_length, label)
            assert _display_width(label) <= MAX_WIDTH, (title, artist_length, label)
