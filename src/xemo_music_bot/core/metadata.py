"""Clean performer and title from raw provider metadata.

The rules are the "Clean metadata" section of ``docs/features/mvp-search-and-listen.md``.
Uploads often put the artist into the title (``Daft Punk - Instant Crush``) and add
promotional suffixes (``[Free Download]``); the cleaned values are what users see.
"""

import re
from dataclasses import dataclass

_JUNK = (
    "official audio",
    "official video",
    "official music video",
    "lyrics",
    "lyric video",
    "audio",
    "free download",
    "free dl",
    "out now",
)
_JUNK_ALTERNATIVES = "|".join(junk.replace(" ", r"\s+") for junk in _JUNK)
# One junk tag at the very end, in () or [] or after a |.
_JUNK_SUFFIX_RE = re.compile(
    rf"\s*(?:[(\[]\s*(?:{_JUNK_ALTERNATIVES})\s*[)\]]|\|\s*(?:{_JUNK_ALTERNATIVES}))\s*$",
    re.IGNORECASE,
)
# Hyphen, en dash or em dash with whitespace around it, so "Jay-Z" is not split.
_SEPARATOR_RE = re.compile(r"\s+[-\u2013\u2014]\s+")
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")
_WORD_RE = re.compile(r"[^\W_]+")
# Words that only describe a version. When everything after the separator is made of
# them, as in "Intro - Live", it is a version of the title, not a title by an artist
# called "Intro".
_VERSION_WORDS = frozenset(
    [
        "acoustic",
        "bootleg",
        "club",
        "demo",
        "dub",
        "edit",
        "extended",
        "instrumental",
        "live",
        "mix",
        "original",
        "radio",
        "remaster",
        "remastered",
        "remix",
        "rework",
        "single",
        "unplugged",
        "version",
        "vip",
    ]
)


@dataclass(slots=True, frozen=True)
class TrackName:
    """Cleaned performer and title of a track.

    Attributes:
        artist: Performer; empty if neither the title nor the uploader names one.
        title: Track title without the performer and junk suffixes.
    """

    artist: str
    title: str


def clean_track_name(raw_title: str, uploader: str) -> TrackName:
    """Derive the performer and title shown to users from raw upload metadata.

    Args:
        raw_title: Title exactly as the provider returns it.
        uploader: Name of the account that uploaded the track.

    Returns:
        The performer and title. An ``X - Y`` title gives performer ``X`` and title
        ``Y``; otherwise the uploader is the performer. If cleaning leaves no title, the
        raw title (with whitespace collapsed) is kept.
    """
    title = _normalize_space(raw_title)
    uploader = _normalize_space(uploader)
    stripped = _strip_junk(title)
    if not stripped:
        return TrackName(artist=uploader, title=title)

    parts = _SEPARATOR_RE.split(stripped, maxsplit=1)
    if len(parts) == 2 and all(parts) and not _is_version_tag(parts[1]):
        return TrackName(artist=parts[0], title=parts[1])
    return TrackName(artist=uploader, title=stripped)


def _normalize_space(text: str) -> str:
    """Turn control characters into spaces and collapse runs of whitespace."""
    return " ".join(_CONTROL_CHARS_RE.sub(" ", text).split())


def _strip_junk(title: str) -> str:
    """Remove junk tags from the end of ``title``, repeatedly, as they can be stacked."""
    while (stripped := _JUNK_SUFFIX_RE.sub("", title)) != title:
        title = stripped
    return title


def _is_version_tag(text: str) -> bool:
    """Whether ``text`` only names a version, like ``Live`` or ``2011 Remaster``."""
    words = _WORD_RE.findall(text.lower())
    return bool(words) and all(word in _VERSION_WORDS or word.isdigit() for word in words)
