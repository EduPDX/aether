"""Authentication use cases: first-run setup, login, refresh, identity."""

import re
from typing import Protocol

from aether_core.domain.errors import AuthenticationError, ConflictError, ValidationFailedError
from aether_core.domain.users import Role, User


class UserRepository(Protocol):
    async def add(self, user: User) -> None: ...

    async def save(self, user: User) -> None: ...

    async def get(self, user_id: str) -> User | None: ...

    async def get_by_username(self, username: str) -> User | None: ...

    async def count(self) -> int: ...

    async def list_all(self) -> list[User]: ...

    async def delete(self, user_id: str) -> bool: ...


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, password_hash: str, password: str) -> bool: ...


class TokenIssuer(Protocol):
    def issue(self, user_id: str, token_type: str, epoch: int = 1) -> str: ...

    def decode(self, token: str, expected_type: str) -> str: ...

    def epoch_of(self, token: str) -> int: ...


MIN_PASSWORD_LENGTH = 8

# Validação deliberadamente frouxa: o e-mail aqui é contato do administrador,
# não credencial nem canal de recuperação. Recusar endereço válido por causa de
# um regex esperto custa mais do que aceitar um errado que ninguém usa.
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_email(email: str) -> str:
    limpo = (email or "").strip()
    if not limpo:
        return ""
    if len(limpo) > 200 or not _EMAIL.match(limpo):
        raise ValidationFailedError(f"e-mail inválido: {limpo}")
    return limpo


class AuthService:
    def __init__(self, users: UserRepository, hasher: PasswordHasher, tokens: TokenIssuer) -> None:
        self._users = users
        self._hasher = hasher
        self._tokens = tokens

    async def setup_required(self) -> bool:
        return await self._users.count() == 0

    async def setup_owner(
        self, username: str, password: str, email: str = "", display_name: str = ""
    ) -> User:
        """Creates the first user (owner). Only allowed on an empty install."""
        if not await self.setup_required():
            raise ConflictError("setup already completed")
        self._validate_credentials(username, password)
        user = User.new(
            username,
            self._hasher.hash(password),
            Role.OWNER,
            email=validate_email(email),
            display_name=display_name.strip()[:100],
        )
        await self._users.add(user)
        return user

    async def login(self, username: str, password: str) -> tuple[str, str, User]:
        user = await self._users.get_by_username(username)
        if user is None or not self._hasher.verify(user.password_hash, password):
            raise AuthenticationError("invalid username or password")
        return (
            self._tokens.issue(user.id, "access", user.token_epoch),
            self._tokens.issue(user.id, "refresh", user.token_epoch),
            user,
        )

    async def refresh(self, refresh_token: str) -> str:
        user_id = self._tokens.decode(refresh_token, "refresh")
        user = await self._users.get(user_id)
        if user is None:
            raise AuthenticationError("user no longer exists")
        self._check_epoch(user, refresh_token)
        return self._tokens.issue(user.id, "access", user.token_epoch)

    async def authenticate(self, access_token: str) -> User:
        user_id = self._tokens.decode(access_token, "access")
        user = await self._users.get(user_id)
        if user is None:
            raise AuthenticationError("user no longer exists")
        self._check_epoch(user, access_token)
        return user

    def _check_epoch(self, user: User, token: str) -> None:
        """Recusa token emitido antes da última troca de senha."""
        if self._tokens.epoch_of(token) != user.token_epoch:
            raise AuthenticationError("sessão encerrada: a senha foi alterada")

    # ------------------------------------------------------------- perfil --
    async def change_password(self, user: User, current: str, new: str) -> tuple[str, str]:
        """Troca a senha e derruba as outras sessões.

        Exige a senha atual: sem isso, quem alcançasse uma sessão já aberta —
        uma aba esquecida num computador compartilhado — trocaria a senha e
        tomaria a conta. Devolve tokens novos para quem trocou não cair fora.
        """
        if not self._hasher.verify(user.password_hash, current):
            raise AuthenticationError("a senha atual não confere")
        if len(new) < MIN_PASSWORD_LENGTH:
            raise ValidationFailedError(
                f"a nova senha precisa de pelo menos {MIN_PASSWORD_LENGTH} caracteres"
            )
        if new == current:
            raise ValidationFailedError("a nova senha é igual à atual")

        atualizado = User(
            **{
                **user.__dict__,
                "password_hash": self._hasher.hash(new),
                "token_epoch": user.token_epoch + 1,
            }
        )
        await self._users.save(atualizado)
        return (
            self._tokens.issue(atualizado.id, "access", atualizado.token_epoch),
            self._tokens.issue(atualizado.id, "refresh", atualizado.token_epoch),
        )

    async def update_profile(self, user: User, email: str, display_name: str) -> User:
        atualizado = User(
            **{
                **user.__dict__,
                "email": validate_email(email),
                "display_name": display_name.strip()[:100],
            }
        )
        await self._users.save(atualizado)
        return atualizado

    # ------------------------------------------------------ user management --
    async def create_user(
        self,
        username: str,
        password: str,
        role: Role,
        email: str = "",
        display_name: str = "",
    ) -> User:
        if role == Role.OWNER:
            raise ValidationFailedError("there is only one owner (created at setup)")
        self._validate_credentials(username, password)
        if await self._users.get_by_username(username) is not None:
            raise ConflictError(f"username already exists: {username}")
        user = User.new(
            username,
            self._hasher.hash(password),
            role,
            email=validate_email(email),
            display_name=display_name.strip()[:100],
        )
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

    async def reset_password(self, user_id: str, new_password: str, acting_user: User) -> None:
        """O dono redefine a senha de outro usuário, sem saber a atual.

        É o substituto de "esqueci minha senha": como o Aether não manda
        e-mail, quem recupera acesso é o dono da instalação.
        """
        if acting_user.role != Role.OWNER:
            raise ValidationFailedError("apenas o dono pode redefinir a senha de outro usuário")
        target = await self._users.get(user_id)
        if target is None:
            raise ValidationFailedError(f"user not found: {user_id}")
        if len(new_password) < MIN_PASSWORD_LENGTH:
            raise ValidationFailedError(
                f"a senha precisa de pelo menos {MIN_PASSWORD_LENGTH} caracteres"
            )
        await self._users.save(
            User(
                **{
                    **target.__dict__,
                    "password_hash": self._hasher.hash(new_password),
                    "token_epoch": target.token_epoch + 1,
                }
            )
        )

    @staticmethod
    def _validate_credentials(username: str, password: str) -> None:
        if not username or len(username) < 3:
            raise ValidationFailedError("username must have at least 3 characters")
        if len(password) < MIN_PASSWORD_LENGTH:
            raise ValidationFailedError(
                f"password must have at least {MIN_PASSWORD_LENGTH} characters"
            )
