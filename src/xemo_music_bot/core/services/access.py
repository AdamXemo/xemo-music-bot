"""Who may use the bot: config admins, members, blocked users and strangers (ADR 0003)."""

from dataclasses import dataclass
from enum import StrEnum

from xemo_music_bot.db.models import User
from xemo_music_bot.db.repositories.users import UsersRepository


class AccessStatus(StrEnum):
    """How the bot treats a Telegram user."""

    ADMIN = "admin"
    MEMBER = "member"
    BLOCKED = "blocked"
    STRANGER = "stranger"


@dataclass(slots=True, frozen=True)
class Access:
    """The outcome of an access check.

    Attributes:
        status: How the bot treats the user.
        user: The user's row; ``None`` only for a stranger.
    """

    status: AccessStatus
    user: User | None

    @property
    def allowed(self) -> bool:
        """Whether the user may reach the bot's handlers."""
        return self.status in {AccessStatus.ADMIN, AccessStatus.MEMBER}


class AccessService:
    """Decides access for one Telegram user within the caller's session.

    Args:
        users: Repository bound to the current update's session.
        admin_ids: Telegram IDs from config, the only source of admin rights.
    """

    def __init__(self, users: UsersRepository, admin_ids: frozenset[int]) -> None:
        self._users = users
        self._admin_ids = admin_ids

    async def check(self, tg_id: int, username: str | None) -> Access:
        """Return the user's access, creating the row of a config admin who has none.

        Args:
            tg_id: Telegram user ID of the sender.
            username: Telegram username without the leading "@", stored only when the
                row is created; existing rows are left unchanged.

        Returns:
            The access status and the user's row.

        Raises:
            RuntimeError: A config admin's row could neither be created nor read.
        """
        user = await self._users.get(tg_id)
        if tg_id not in self._admin_ids:
            if user is None:
                return Access(AccessStatus.STRANGER, None)
            if user.role == "blocked":
                return Access(AccessStatus.BLOCKED, user)
            return Access(AccessStatus.MEMBER, user)

        if user is None:
            # create() returns None when a concurrent update inserted the row first. The
            # losing insert waits until the other update's transaction ends, so once it
            # reports the conflict the row is committed and the read that follows sees it.
            user = await self._users.create(tg_id, username) or await self._users.get(tg_id)
        if user is None:
            raise RuntimeError("The admin's users row could not be created or read")
        # Config admins win over role 'blocked': they cannot be banned (ADR 0003).
        return Access(AccessStatus.ADMIN, user)
