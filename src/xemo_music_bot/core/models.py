"""Domain models shared by services, providers and repositories."""

from dataclasses import dataclass
from typing import Final, Literal

# The languages the bot speaks (ADR 0005). A plain assignment, not a PEP 695 `type`
# alias, so `typing.get_args` and the ORM's `Mapped[Language]` read the Literal directly.
Language = Literal["en", "uk", "ru"]

DEFAULT_LANGUAGE: Final[Language] = "en"


@dataclass(slots=True, frozen=True)
class Track:
    """A playable track found by a music provider.

    ``artist`` and ``title`` are already cleaned (see ``core.metadata``), so the results
    list, the delivered audio and the ``tracks`` cache all show the same values.

    Attributes:
        provider: Name of the provider that found the track, for example ``soundcloud``.
        provider_track_id: The track's ID within that provider.
        title: Cleaned track title, never empty.
        artist: Cleaned performer; empty if the source has no usable name.
        duration: Length in whole seconds.
        artwork_url: Cover image URL, or ``None`` if the source has none.
        page_url: Public page of the track, used later to download it.
    """

    provider: str
    provider_track_id: str
    title: str
    artist: str
    duration: int
    artwork_url: str | None
    page_url: str


@dataclass(slots=True, frozen=True)
class SearchSession:
    """One user's search: what they asked, what was found and which page they are on.

    Attributes:
        id: Short random id; the only part of the session that goes into callback data.
        owner_id: Telegram ID of the user who searched.
        query: The search text.
        tracks: All results in display order; a result's index counts across pages.
        page: The page the results message shows, counting from 0.
    """

    id: str
    owner_id: int
    query: str
    tracks: tuple[Track, ...]
    page: int
