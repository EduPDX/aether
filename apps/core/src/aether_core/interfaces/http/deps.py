"""FastAPI dependency wiring (one service graph per request)."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from aether_core.application.auth import AuthService
from aether_core.application.config import ConfigService
from aether_core.application.content import ContentService
from aether_core.application.files import FilesService
from aether_core.application.instances import InstanceService
from aether_core.application.power import PowerService
from aether_core.application.sync import SyncService
from aether_core.domain.errors import AuthenticationError, ForbiddenError
from aether_core.domain.users import User
from aether_core.infrastructure import security
from aether_core.infrastructure.repositories import (
    SqlContentCache,
    SqlInstanceRepository,
    SqlSyncProfileRepository,
    SqlUserRepository,
)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.session_factory() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


class _Hasher:
    def hash(self, password: str) -> str:
        return security.hash_password(password)

    def verify(self, password_hash: str, password: str) -> bool:
        return security.verify_password(password_hash, password)


class _Tokens:
    def __init__(self, secret: str) -> None:
        self._secret = secret

    def issue(self, user_id: str, token_type: str) -> str:
        return security.issue_token(self._secret, user_id, token_type)

    def decode(self, token: str, expected_type: str) -> str:
        return security.decode_token(self._secret, token, expected_type)


def get_auth_service(request: Request, session: SessionDep) -> AuthService:
    return AuthService(
        users=SqlUserRepository(session),
        hasher=_Hasher(),
        tokens=_Tokens(request.app.state.jwt_secret),
    )


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


async def get_current_user(request: Request, auth: AuthServiceDep) -> User:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise AuthenticationError("missing bearer token")
    user = await auth.authenticate(header[len("Bearer ") :])
    request.state.user = user
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


def _require(permission: str):
    async def dep(user: CurrentUserDep) -> User:
        if not user.has_permission(permission):
            raise ForbiddenError(f"missing permission: {permission}")
        return user

    return dep


InstancesRead = Annotated[User, Depends(_require("instances.read"))]
InstancesWrite = Annotated[User, Depends(_require("instances.write"))]
ContentRead = Annotated[User, Depends(_require("content.read"))]
ContentWrite = Annotated[User, Depends(_require("content.write"))]
PowerUse = Annotated[User, Depends(_require("power.use"))]
ConsoleUse = Annotated[User, Depends(_require("console.use"))]
AuditRead = Annotated[User, Depends(_require("audit.read"))]
UsersManage = Annotated[User, Depends(_require("users.manage"))]
FilesRead = Annotated[User, Depends(_require("files.read"))]
FilesWrite = Annotated[User, Depends(_require("files.write"))]
ConfigRead = Annotated[User, Depends(_require("config.read"))]
ConfigWrite = Annotated[User, Depends(_require("config.write"))]
SyncRead = Annotated[User, Depends(_require("sync.read"))]
SyncWrite = Annotated[User, Depends(_require("sync.write"))]


def get_instance_service(request: Request, session: SessionDep) -> InstanceService:
    state = request.app.state
    return InstanceService(
        repo=SqlInstanceRepository(session),
        providers=state.providers,
        fs=state.fs,
        bus=state.bus,
    )


def get_content_service(request: Request, session: SessionDep) -> ContentService:
    state = request.app.state
    return ContentService(
        providers=state.providers,
        fs=state.fs,
        cache=SqlContentCache(session),
        icons=state.icons,
        trash_root=state.settings.trash_dir,
        bus=state.bus,
    )


def get_power_service(request: Request) -> PowerService:
    state = request.app.state
    return PowerService(providers=state.providers, supervisor=state.supervisor)


def get_files_service(request: Request) -> FilesService:
    state = request.app.state
    return FilesService(trash_root=state.settings.trash_dir, bus=state.bus)


def get_config_service(request: Request) -> ConfigService:
    state = request.app.state
    return ConfigService(
        providers=state.providers,
        files=get_files_service(request),
        bus=state.bus,
    )


def get_sync_service(request: Request, session: SessionDep) -> SyncService:
    state = request.app.state
    return SyncService(
        repo=SqlSyncProfileRepository(session),
        signer=state.sync_signer,
        bus=state.bus,
    )


InstanceServiceDep = Annotated[InstanceService, Depends(get_instance_service)]
ContentServiceDep = Annotated[ContentService, Depends(get_content_service)]
PowerServiceDep = Annotated[PowerService, Depends(get_power_service)]
FilesServiceDep = Annotated[FilesService, Depends(get_files_service)]
ConfigServiceDep = Annotated[ConfigService, Depends(get_config_service)]
SyncServiceDep = Annotated[SyncService, Depends(get_sync_service)]
