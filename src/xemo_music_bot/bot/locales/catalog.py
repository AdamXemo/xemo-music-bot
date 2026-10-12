"""The shape every language catalog must fill (ADR 0005)."""

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class Texts:
    """All user-facing copy for one language.

    Every field is required, so mypy rejects a catalog that misses a key.

    Attributes:
        greeting: Reply to `/start`.
        private_bot: Reply to `/start` from a stranger or a blocked user.
    """

    greeting: str
    private_bot: str
