"""FastAPI dependency wiring (one service graph per request)."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from aether_core.application.auth import AuthService
from aether_core.application.backups import BackupService
from aether_core.application.config import ConfigService
from aether_core.application.config_raw import RawConfigService
from aether_core.application.content import ContentService
from aether_core.application.files import FilesService
from aether_core.application.icons import ServerIconService
from aether_core.application.instances import InstanceService
from aether_core.application.players import PlayerService
from aether_core.application.power import PowerService
from aether_core.application.sources import SourceService
from aether_core.application.sync import SyncService
from aether_core.application.tasks import TaskService
from aether_core.application.trash import TrashService
from aether_core.domain.errors import AuthenticationError, ForbiddenError
from aether_core.domain.users import User
from aether_core.infrastructure import security
from aether_core.infrastructure.repositories import (
    SqlBackupRepository,
    SqlContentCache,
    SqlInstanceRepository,
    SqlScheduledTaskRepository,
    SqlSyncProfileRepository,
    SqlTrashRepository,
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

    def issue(self, user_id: str, token_type: str, epoch: int = 1) -> str:
        return security.issue_token(self._secret, user_id, token_type, epoch)

    def decode(self, token: str, expected_type: str) -> str:
        return security.decode_token(self._secret, token, expected_type)

    def epoch_of(self, token: str) -> int:
        return security.token_epoch(self._secret, token)


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


async def authenticate_request(request: Request) -> User:
    """Autentica fora do sistema de dependências.

    Serve às rotas que aceitam mais de um esquema — o download, que atende
    tanto o Bearer do dashboard quanto o link assinado de navegação, e por
    isso não pode declarar a permissão como dependência.
    """
    async with request.app.state.session_factory() as session:
        auth = AuthService(
            users=SqlUserRepository(session),
            hasher=_Hasher(),
            tokens=_Tokens(request.app.state.jwt_secret),
        )
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            raise AuthenticationError("missing bearer token")
        return await auth.authenticate(header[len("Bearer ") :])


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
BackupsRead = Annotated[User, Depends(_require("backups.read"))]
BackupsWrite = Annotated[User, Depends(_require("backups.write"))]
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
        instances_dir=state.settings.instances_dir,
    )


def get_trash_service(request: Request, session: SessionDep) -> TrashService:
    state = request.app.state
    return TrashService(
        trash_root=state.settings.trash_dir,
        repo=SqlTrashRepository(session),
        bus=state.bus,
    )


def get_content_service(request: Request, session: SessionDep) -> ContentService:
    state = request.app.state
    return ContentService(
        providers=state.providers,
        fs=state.fs,
        cache=SqlContentCache(session),
        icons=state.icons,
        trash=get_trash_service(request, session),
        bus=state.bus,
    )


def get_power_service(request: Request) -> PowerService:
    state = request.app.state
    return PowerService(providers=state.providers, supervisors=state.supervisors)


def get_player_service(request: Request) -> PlayerService:
    state = request.app.state
    return PlayerService(
        providers=state.providers,
        power=get_power_service(request),
        bus=state.bus,
    )


def get_files_service(request: Request, session: SessionDep) -> FilesService:
    state = request.app.state
    return FilesService(trash=get_trash_service(request, session), bus=state.bus)


def get_backup_service(request: Request, session: SessionDep) -> BackupService:
    state = request.app.state
    return BackupService(
        repo=SqlBackupRepository(session),
        providers=state.providers,
        supervisor=state.supervisor,
        bus=state.bus,
        backups_root=state.settings.backups_dir,
    )


BackupServiceDep = Annotated[BackupService, Depends(get_backup_service)]


def get_source_service(request: Request, session: SessionDep) -> SourceService:
    state = request.app.state
    conteudo = get_content_service(request, session)

    def pasta(instance, ctype_id):
        return conteudo.folder_for(instance, ctype_id)

    return SourceService(
        providers=state.providers,
        downloader=state.downloader,
        bus=state.bus,
        content_dir_of=pasta,
    )


SourceServiceDep = Annotated[SourceService, Depends(get_source_service)]


def get_config_service(request: Request, session: SessionDep) -> ConfigService:
    state = request.app.state
    return ConfigService(
        providers=state.providers,
        files=get_files_service(request, session),
        bus=state.bus,
    )


def get_raw_config_service(request: Request, session: SessionDep) -> RawConfigService:
    state = request.app.state
    return RawConfigService(
        providers=state.providers, files=get_files_service(request, session), bus=state.bus
    )


RawConfigServiceDep = Annotated[RawConfigService, Depends(get_raw_config_service)]


def get_server_icon_service(request: Request) -> ServerIconService:
    return ServerIconService(bus=request.app.state.bus, providers=request.app.state.providers)


ServerIconServiceDep = Annotated[ServerIconService, Depends(get_server_icon_service)]


def get_task_service(request: Request, session: SessionDep) -> TaskService:
    state = request.app.state
    return TaskService(
        repo=SqlScheduledTaskRepository(session),
        supervisor=state.supervisor,
        power=get_power_service(request),
        bus=state.bus,
    )


TaskServiceDep = Annotated[TaskService, Depends(get_task_service)]


def get_sync_service(request: Request, session: SessionDep) -> SyncService:
    state = request.app.state
    return SyncService(
        repo=SqlSyncProfileRepository(session),
        signer=state.sync_signer,
        bus=state.bus,
        providers=state.providers,
    )


InstanceServiceDep = Annotated[InstanceService, Depends(get_instance_service)]
ContentServiceDep = Annotated[ContentService, Depends(get_content_service)]
PowerServiceDep = Annotated[PowerService, Depends(get_power_service)]
FilesServiceDep = Annotated[FilesService, Depends(get_files_service)]
ConfigServiceDep = Annotated[ConfigService, Depends(get_config_service)]
SyncServiceDep = Annotated[SyncService, Depends(get_sync_service)]
TrashServiceDep = Annotated[TrashService, Depends(get_trash_service)]
PlayerServiceDep = Annotated[PlayerService, Depends(get_player_service)]
