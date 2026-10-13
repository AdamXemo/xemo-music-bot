"""The shape every language catalog must fill (ADR 0005)."""

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class Texts:
    """All user-facing copy for one language.

    Every field is required, so mypy rejects a catalog that misses a key. Message fields
    are HTML (escape ``&``, ``<`` and ``>``); button-label fields are plain text.

    Attributes:
        private_bot: Reply to `/start` from a stranger or a blocked user.
        welcome: Reply to `/start` from a member or an admin.
        language_button: The welcome's button that opens the language picker.
        language_name: The language's own name, used as its picker button.
        language_prompt: Text of the language picker.
        language_set: Confirmation after picking a language from `/language`.
    """

    private_bot: str
    welcome: str
    language_button: str
    language_name: str
    language_prompt: str
    language_set: str
