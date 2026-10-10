import pytest

from xemo_music_bot.core.metadata import TrackName, clean_track_name

# (raw title, uploader, expected artist, expected title); titles are real SoundCloud ones.
CASES = [
    # Splitting "X - Y"
    ("Daft Punk - Instant Crush", "Aaron Gardea", "Daft Punk", "Instant Crush"),
    ("Daft Punk \u2013 Instant Crush", "someone", "Daft Punk", "Instant Crush"),
    ("Daft Punk \u2014 Instant Crush", "someone", "Daft Punk", "Instant Crush"),
    ("Jay-Z - 99 Problems", "rapfan", "Jay-Z", "99 Problems"),
    ("Artist - Song - Radio Edit", "label", "Artist", "Song - Radio Edit"),
    ("Daft Punk -Instant Crush", "someone", "someone", "Daft Punk -Instant Crush"),
    ("- Instant Crush", "someone", "someone", "- Instant Crush"),
    # No separator: the uploader is the artist
    (
        "Instant Crush (feat. Julian Casablancas)",
        "Daft Punk",
        "Daft Punk",
        "Instant Crush (feat. Julian Casablancas)",
    ),
    ("Jay-Z", "uploader", "uploader", "Jay-Z"),
    # A version tag after the separator is not a title
    ("Intro - Live", "The xx", "The xx", "Intro - Live"),
    ("Song - Radio Edit", "Artist", "Artist", "Song - Radio Edit"),
    (
        "Song \u2013 2011 Remastered Version",
        "Artist",
        "Artist",
        "Song \u2013 2011 Remastered Version",
    ),
    ("Oasis - Live Forever", "fan", "Oasis", "Live Forever"),
    # Known misses: an upload title that starts with the track name is still split.
    ("Intro - Renaissance Tour Live", "BEYONCÉ", "Intro", "Renaissance Tour Live"),
    # Junk suffixes
    ("Daft Punk - Instant Crush (Official Audio)", "x", "Daft Punk", "Instant Crush"),
    ("Song [OFFICIAL MUSIC VIDEO]", "Artist", "Artist", "Song"),
    ("Song (Lyric Video)", "Artist", "Artist", "Song"),
    ("Song [Lyrics]", "Artist", "Artist", "Song"),
    ("Song | Free Download", "Artist", "Artist", "Song"),
    ("Song (Out Now) [FREE DL]", "Artist", "Artist", "Song"),
    ("Song ( official   audio )", "Artist", "Artist", "Song"),
    (
        "Daft Punk - Instant Crush (David Mackay Remix) [Free Download]",
        "David Mackay",
        "Daft Punk",
        "Instant Crush (David Mackay Remix)",
    ),
    # Not junk: kept as is
    ("Song (Official Audio) Remix", "Artist", "Artist", "Song (Official Audio) Remix"),
    ("Audio", "Artist", "Artist", "Audio"),
    ("Intro (Live)", "Dalvin La Melodia", "Dalvin La Melodia", "Intro (Live)"),
    ("Song (Extended Edit) [Cover]", "Artist", "Artist", "Song (Extended Edit) [Cover]"),
    # Whitespace and control characters
    ("  Daft   Punk -\tInstant\nCrush  ", " Up\u00a0loader ", "Daft Punk", "Instant Crush"),
    ("Song\x00Title", "Artist", "Artist", "Song Title"),
    # Cleaning would leave nothing: keep the raw title
    ("(Official Audio)", "Artist", "Artist", "(Official Audio)"),
    ("[Free Download] | Out Now", "Artist", "Artist", "[Free Download] | Out Now"),
    # No uploader name
    ("Song", "", "", "Song"),
]


@pytest.mark.parametrize(("raw_title", "uploader", "artist", "title"), CASES)
def test_clean_track_name(raw_title: str, uploader: str, artist: str, title: str) -> None:
    assert clean_track_name(raw_title, uploader) == TrackName(artist=artist, title=title)
