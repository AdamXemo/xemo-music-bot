"""Single-use invite codes: creating them and joining with one (ADR 0003)."""

import re
import secrets
import string
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from typing import Final

from xemo_music_bot.core.models import Language
from xemo_music_bot.db.models import Invite
from xemo_music_bot.db.repositories.invites import InvitesRepository
from xemo_music_bot.db.repositories.users import UsersRepository

CODE_LENGTH: Final = 8
INVITE_TTL: Final = timedelta(days=7)
# Base62 only: a deep-link payload allows `_` and `-` too, but they are easy to misread.
_ALPHABET: Final = string.ascii_letters + string.digits
# The same shape as the CHECK constraint on `invites.code`.
_CODE_PATTERN: Final = re.compile(rf"[A-Za-z0-9]{{{CODE_LENGTH}}}")
# 62**8 codes make a collision very unlikely; three tries make giving up practically never.
_CREATE_ATTEMPTS: Final = 3


def generate_code() -> str:
    """Return a new random code of ``CODE_LENGTH`` base62 characters."""
    return "".join(secrets.choice(_ALPHABET) for _ in range(CODE_LENGTH))


def is_code_format(text: str) -> bool:
    """Whether ``text`` has the shape of a code, so malformed input never reaches a query."""
    return _CODE_PATTERN.fullmatch(text) is not None


class JoinStatus(StrEnum):
    """The outcome of joining with a code."""

    JOINED = "joined"
    ALREADY_MEMBER = "already_member"
    INVALID = "invalid"


@dataclass(slots=True, frozen=True)
class JoinResult:
    """What happened when someone joined with a code.

    Attributes:
        status: The outcome.
        inviter_id: Telegram ID of the code's creator, set only when the user joined.
    """

    status: JoinStatus
    inviter_id: int | None


class InviteService:
    """Creates codes and lets strangers join with them, within the caller's session.

    Args:
        invites: Repository bound to the current session.
        users: Repository bound to the same session.
        generate: Makes a new code; replaceable so tests can force a collision.
    """

    def __init__(
        self,
        invites: InvitesRepository,
        users: UsersRepository,
        generate: Callable[[], str] = generate_code,
    ) -> None:
        self._invites = invites
        self._users = users
        self._generate = generate

    async def create(self, created_by: int) -> Invite:
        """Create a single-use code that works for ``INVITE_TTL``.

        Args:
            created_by: Telegram ID of the creating user, who must have a row.

        Raises:
            RuntimeError: Every generated code was already taken.
        """
        for _ in range(_CREATE_ATTEMPTS):
            invite = await self._invites.create(self._generate(), created_by, INVITE_TTL)
            if invite is not None:
                return invite
        raise RuntimeError("No free invite code after several attempts")

    async def join(
        self, code: str, tg_id: int, username: str | None, language: Language
    ) -> JoinResult:
        """Use up the code and create the user's row, all in the caller's transaction.

        The code's row stays locked until the caller commits, so of two people racing
        for one code only the first joins. The caller must commit before announcing the
        join, so a rolled-back join is never announced.

        Args:
            code: The payload of the user's `/start`, in any shape.
            tg_id: Telegram user ID of the person joining.
            username: Telegram username without the leading "@", if any.
            language: The language detected from Telegram, stored with the new row.

        Returns:
            ``JOINED`` with the inviter; ``ALREADY_MEMBER`` if the user has a row (the
            code is left unused); otherwise ``INVALID``.
        """
        if not is_code_format(code):
            return JoinResult(JoinStatus.INVALID, None)
        inviter_id = await self._invites.lock_usable(code)
        if inviter_id is None:
            # Someone tapping Start twice loses the race to their own first tap: by now
            # they are a member, and the code is used by them.
            if await self._users.get(tg_id) is None:
                return JoinResult(JoinStatus.INVALID, None)
            return JoinResult(JoinStatus.ALREADY_MEMBER, None)
        if await self._users.create(tg_id, username, language, invited_by=inviter_id) is None:
            # The row appeared since the caller's access check; the code stays unused.
            return JoinResult(JoinStatus.ALREADY_MEMBER, None)
        await self._invites.mark_used(code, tg_id)
        return JoinResult(JoinStatus.JOINED, inviter_id)
