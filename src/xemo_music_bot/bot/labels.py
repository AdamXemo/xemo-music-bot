"""Track names for buttons and messages (feature spec: "Track label" and "Copy").

The label is ``Title - Artist · m:ss`` and has a fixed budget, so Telegram never cuts a
button on its own and the duration always shows. Titles and artists arrive cleaned
(``core.metadata``), control characters included.
"""

import unicodedata
from typing import Final

from xemo_music_bot.core.models import Track

MAX_WIDTH: Final = 32
# Longest ``Artist - Title`` in a message; the audio player shows about as much.
MAX_NAME_LENGTH: Final = 60
# Fewer visible artist characters than this (the ellipsis included) are not worth showing.
_MIN_ARTIST_WIDTH: Final = 5
_ELLIPSIS: Final = "…"
_ARTIST_SEPARATOR: Final = " - "

_ZWJ: Final = "\u200d"
_EMOJI_PRESENTATION: Final = "\ufe0f"
_SKIN_TONES: Final = range(0x1F3FB, 0x1F400)

# A unit is what the reader sees as one character: its text and its width in the budget.
type _Unit = tuple[str, int]


def result_label(track: Track) -> str:
    """Build the text of a track button.

    Args:
        track: A track with cleaned title and artist.

    Returns:
        ``Title - Artist · duration`` of at most ``MAX_WIDTH`` characters (emoji count as
        2) unless the duration alone is longer. The duration is never cut; the artist is
        shortened first, then dropped, and only then is the title shortened.
    """
    suffix = f" · {format_duration(track.duration)}"
    budget = MAX_WIDTH - len(suffix)
    title = _units(track.title)
    artist = _units(track.artist)
    if not artist:
        return f"{_fit_title(title, budget)}{suffix}"

    # The title keeps its full length while the artist can still show a useful part.
    room = budget - _width(title) - len(_ARTIST_SEPARATOR)
    if room >= _width(artist):
        return f"{track.title}{_ARTIST_SEPARATOR}{track.artist}{suffix}"
    cut_artist = _cut(artist, room)
    if _width(cut_artist) >= _MIN_ARTIST_WIDTH:
        return f"{track.title}{_ARTIST_SEPARATOR}{_text(cut_artist)}{suffix}"
    return f"{_fit_title(title, budget)}{suffix}"


def track_name(track: Track) -> str:
    """Return ``Artist - Title`` for a message, cut to ``MAX_NAME_LENGTH`` with an ellipsis.

    Args:
        track: A track with cleaned title and artist.

    Returns:
        Plain text: the caller escapes it for HTML. Just the title if there is no artist.
    """
    name = f"{track.artist}{_ARTIST_SEPARATOR}{track.title}" if track.artist else track.title
    if len(name) <= MAX_NAME_LENGTH:
        return name
    return name[: MAX_NAME_LENGTH - 1].rstrip() + _ELLIPSIS


def format_duration(seconds: int) -> str:
    """Format as ``m:ss``, or ``h:mm:ss`` from one hour up."""
    minutes, secs = divmod(max(seconds, 0), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _units(text: str) -> list[_Unit]:
    """Split text into visible characters with their width; emoji are 2 wide.

    A variation selector, a joiner (and the character after it) and a skin tone or
    combining mark belong to the character before them, so a cut never splits an emoji.
    Flags and keycaps are not recognised and may be split or miscounted; they are rare in
    titles, which is accepted.
    """
    units: list[_Unit] = []
    joined = False
    for char in text:
        attaches = (
            joined
            or char in (_ZWJ, _EMOJI_PRESENTATION)
            or ord(char) in _SKIN_TONES
            or unicodedata.combining(char) != 0
        )
        if attaches and units:
            previous, width = units[-1]
            if char == _EMOJI_PRESENTATION:
                width = 2
            units[-1] = (previous + char, width)
        else:
            wide = unicodedata.east_asian_width(char) in ("W", "F")
            units.append((char, 2 if wide else 1))
        joined = char == _ZWJ
    return units


def _width(units: list[_Unit]) -> int:
    return sum(width for _, width in units)


def _text(units: list[_Unit]) -> str:
    return "".join(char for char, _ in units)


def _cut(units: list[_Unit], width: int) -> list[_Unit]:
    """Shorten to at most ``width`` with an ellipsis at the end; unchanged if it fits."""
    if _width(units) <= width:
        return units
    return [*_strip_end(units[: _fitting(units, width - 1)]), (_ELLIPSIS, 1)]


def _fitting(units: list[_Unit], width: int) -> int:
    """Count the leading units that fit in ``width``."""
    used = 0
    for count, (_, unit_width) in enumerate(units):
        used += unit_width
        if used > width:
            return count
    return len(units)


def _strip_end(units: list[_Unit]) -> list[_Unit]:
    """Drop whitespace at the end, so no space comes before an ellipsis."""
    end = len(units)
    while end and units[end - 1][0].isspace():
        end -= 1
    return units[:end]


def _fit_title(units: list[_Unit], width: int) -> str:
    """Shorten the title to ``width`` at a word boundary, with an ellipsis."""
    if _width(units) <= width:
        return _text(units)
    room = width - 1
    cut = _fitting(units, room)
    if 0 < cut < len(units) and not units[cut - 1][0].isspace() and not units[cut][0].isspace():
        # The cut lands inside a word: move it back to where the word starts, unless the
        # word could not fit even on its own, in which case it is cut where it stands.
        start = cut
        while start > 0 and not units[start - 1][0].isspace():
            start -= 1
        end = cut
        while end < len(units) and not units[end][0].isspace():
            end += 1
        if start > 0 and _width(units[start:end]) <= room:
            cut = start
    return _text(_strip_end(units[:cut])) + _ELLIPSIS
