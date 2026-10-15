"""The shape every language catalog must fill (ADR 0005)."""

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class Texts:
    """All user-facing copy for one language.

    Every field is required, so mypy rejects a catalog that misses a key. Message fields
    are HTML (escape ``&``, ``<`` and ``>``); button-label fields are plain text.

    Attributes:
        private_bot: Reply to `/start` from a stranger or a blocked user.
        welcome: Reply to `/start` from a member or an admin who has picked a language.
        language_flag: The language's flag, before its name on picker buttons; the only
            Unicode emoji allowed in the copy (UX guide, "Language flags").
        language_name: The language's own name, after the flag on its picker button.
        language_prompt: Text of the language picker.
        language_set: Confirmation after picking a language from `/language`.
    """

    private_bot: str
    welcome: str
    language_flag: str
    language_name: str
    language_prompt: str
    language_set: str
