"""Authentication use cases: first-run setup, login, refresh, identity."""

from typing import Protocol

from aether_core.domain.errors import AuthenticationError, ConflictError, ValidationFailedError
from aether_core.domain.users import Role, User


class UserRepository(Protocol):
    async def add(self, user: User) -> None: ...

    async def get(self, user_id: str) -> User | None: ...

    async def get_by_username(self, username: str) -> User | None: ...

    async def count(self) -> int: ...

    async def list_all(self) -> list[User]: ...

    async def delete(self, user_id: str) -> bool: ...


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, password_hash: str, password: str) -> bool: ...


class TokenIssuer(Protocol):
    def issue(self, user_id: str, token_type: str) -> str: ...

    def decode(self, token: str, expected_type: str) -> str: ...


MIN_PASSWORD_LENGTH = 8


class AuthService:
    def __init__(self, users: UserRepository, hasher: PasswordHasher, tokens: TokenIssuer) -> None:
        self._users = users
        self._hasher = hasher
        self._tokens = tokens

    async def setup_required(self) -> bool:
        return await self._users.count() == 0

    async def setup_owner(self, username: str, password: str) -> User:
        """Creates the first user (owner). Only allowed on an empty install."""
        if not await self.setup_required():
            raise ConflictError("setup already completed")
        self._validate_credentials(username, password)
        user = User.new(username, self._hasher.hash(password), Role.OWNER)
        await self._users.add(user)
        return user

    async def login(self, username: str, password: str) -> tuple[str, str, User]:
        user = await self._users.get_by_username(username)
        if user is None or not self._hasher.verify(user.password_hash, password):
            raise AuthenticationError("invalid username or password")
        return (
            self._tokens.issue(user.id, "access"),
            self._tokens.issue(user.id, "refresh"),
            user,
        )

    async def refresh(self, refresh_token: str) -> str:
        user_id = self._tokens.decode(refresh_token, "refresh")
        user = await self._users.get(user_id)
        if user is None:
            raise AuthenticationError("user no longer exists")
        return self._tokens.issue(user.id, "access")

    async def authenticate(self, access_token: str) -> User:
        user_id = self._tokens.decode(access_token, "access")
        user = await self._users.get(user_id)
        if user is None:
            raise AuthenticationError("user no longer exists")
        return user

    # ------------------------------------------------------ user management --
    async def create_user(self, username: str, password: str, role: Role) -> User:
        if role == Role.OWNER:
            raise ValidationFailedError("there is only one owner (created at setup)")
        self._validate_credentials(username, password)
        if await self._users.get_by_username(username) is not None:
            raise ConflictError(f"username already exists: {username}")
        user = User.new(username, self._hasher.hash(password), role)
        await self._users.add(user)
        return user

    async def list_users(self) -> list[User]:
        return await self._users.list_all()

    async def delete_user(self, user_id: str, acting_user: User) -> None:
        if user_id == acting_user.id:
            raise ValidationFailedError("you cannot delete your own account")
        target = await self._users.get(user_id)
        if target is None:
            raise ValidationFailedError(f"user not found: {user_id}")
        if target.role == Role.OWNER:
            raise ValidationFailedError("the owner account cannot be deleted")
        await self._users.delete(user_id)

    @staticmethod
    def _validate_credentials(username: str, password: str) -> None:
        if not username or len(username) < 3:
            raise ValidationFailedError("username must have at least 3 characters")
        if len(password) < MIN_PASSWORD_LENGTH:
            raise ValidationFailedError(
                f"password must have at least {MIN_PASSWORD_LENGTH} characters"
            )
