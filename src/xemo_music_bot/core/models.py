"""Domain models shared by services, providers and repositories."""

from dataclasses import dataclass


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
