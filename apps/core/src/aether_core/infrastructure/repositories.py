"""SQLAlchemy implementations of the persistence ports."""

import json
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from aether_core.application.ports import CachedContent
from aether_core.domain.backups import Backup, BackupKind, BackupPolicy, BackupSchedule
from aether_core.domain.instances import Instance
from aether_core.domain.tasks import ScheduledTask, TaskKind, TaskSchedule
from aether_core.domain.trash import TrashItem, TrashOrigin
from aether_core.domain.users import Role, User
from aether_core.infrastructure.db import (
    AuditLogRow,
    BackupPolicyRow,
    BackupRow,
    ContentCacheRow,
    InstanceRow,
    ProviderVersionsRow,
    ScheduledTaskRow,
    SyncProfileRow,
    TrashItemRow,
    UserRow,
)

_CHUNK = 500  # stay under SQLite's bound-parameter limit


def _row_to_instance(row: InstanceRow) -> Instance:
    return Instance(
        id=row.id,
        name=row.name,
        provider_id=row.provider_id,
        root_dir=row.root_dir,
        runtime=row.runtime or "process",
        content_dirs=json.loads(row.content_dirs or "{}"),
        provider_data=json.loads(row.provider_data or "{}"),
        created_at=datetime.fromisoformat(row.created_at),
    )


class SqlInstanceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, instance: Instance) -> None:
        self._session.add(
            InstanceRow(
                id=instance.id,
                name=instance.name,
                provider_id=instance.provider_id,
                root_dir=instance.root_dir,
                runtime=instance.runtime,
                content_dirs=json.dumps(instance.content_dirs),
                provider_data=json.dumps(instance.provider_data),
                created_at=instance.created_at.isoformat(),
            )
        )
        await self._session.commit()

    async def get(self, instance_id: str) -> Instance | None:
        row = await self._session.get(InstanceRow, instance_id)
        return _row_to_instance(row) if row else None

    async def list_all(self) -> list[Instance]:
        rows = await self._session.scalars(select(InstanceRow).order_by(InstanceRow.created_at))
        return [_row_to_instance(r) for r in rows]

    async def update_provider_data(self, instance_id: str, provider_data: dict) -> None:
        row = await self._session.get(InstanceRow, instance_id)
        if row is None:
            return
        row.provider_data = json.dumps(provider_data)
        await self._session.commit()

    async def delete(self, instance_id: str) -> bool:
        result = await self._session.execute(
            delete(InstanceRow).where(InstanceRow.id == instance_id)
        )
        await self._session.commit()
        return result.rowcount > 0

    async def delete_related(self, instance_id: str) -> dict[str, int]:
        """Apaga o que pendurava na instância: backups, política, tarefas e
        perfis de sync.

        O SQLite aqui não tem chave estrangeira com cascata, então sem isto as
        linhas ficavam órfãs para sempre — invisíveis na interface e
        ressuscitando se um id fosse reaproveitado.
        """
        removidos: dict[str, int] = {}
        for tabela in (BackupRow, BackupPolicyRow, ScheduledTaskRow, SyncProfileRow):
            resultado = await self._session.execute(
                delete(tabela).where(tabela.instance_id == instance_id)
            )
            if resultado.rowcount:
                removidos[tabela.__tablename__] = resultado.rowcount
        await self._session.commit()
        return removidos


class SqlContentCache:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_many(self, keys: list[str]) -> dict[str, CachedContent]:
        out: dict[str, CachedContent] = {}
        for i in range(0, len(keys), _CHUNK):
            chunk = keys[i : i + _CHUNK]
            rows = await self._session.scalars(
                select(ContentCacheRow).where(ContentCacheRow.key.in_(chunk))
            )
            for row in rows:
                out[row.key] = CachedContent(
                    metadata=json.loads(row.metadata_json), icon_file=row.icon_file
                )
        return out

    async def put_many(self, entries: dict[str, CachedContent]) -> None:
        if not entries:
            return
        now = datetime.now(UTC).isoformat()
        values = [
            {
                "key": key,
                "metadata_json": json.dumps(cc.metadata, ensure_ascii=False),
                "icon_file": cc.icon_file,
                "updated_at": now,
            }
            for key, cc in entries.items()
        ]
        for i in range(0, len(values), _CHUNK):
            stmt = sqlite_insert(ContentCacheRow).values(values[i : i + _CHUNK])
            stmt = stmt.on_conflict_do_update(
                index_elements=[ContentCacheRow.key],
                set_={
                    "metadata_json": stmt.excluded.metadata_json,
                    "icon_file": stmt.excluded.icon_file,
                    "updated_at": stmt.excluded.updated_at,
                },
            )
            await self._session.execute(stmt)
        await self._session.commit()


def _row_to_user(row: UserRow) -> User:
    return User(
        id=row.id,
        username=row.username,
        password_hash=row.password_hash,
        role=Role(row.role),
        email=row.email or "",
        display_name=row.display_name or "",
        token_epoch=row.token_epoch or 1,
        created_at=datetime.fromisoformat(row.created_at),
    )


class SqlUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, user: User) -> None:
        self._session.add(
            UserRow(
                id=user.id,
                username=user.username,
                password_hash=user.password_hash,
                role=str(user.role),
                email=user.email,
                display_name=user.display_name,
                token_epoch=user.token_epoch,
                created_at=user.created_at.isoformat(),
            )
        )
        await self._session.commit()

    async def save(self, user: User) -> None:
        row = await self._session.get(UserRow, user.id)
        if row is None:
            return
        row.password_hash = user.password_hash
        row.email = user.email
        row.display_name = user.display_name
        row.token_epoch = user.token_epoch
        await self._session.commit()

    async def get(self, user_id: str) -> User | None:
        row = await self._session.get(UserRow, user_id)
        return _row_to_user(row) if row else None

    async def get_by_username(self, username: str) -> User | None:
        row = await self._session.scalar(select(UserRow).where(UserRow.username == username))
        return _row_to_user(row) if row else None

    async def count(self) -> int:
        return (await self._session.scalar(select(func.count()).select_from(UserRow))) or 0

    async def list_all(self) -> list[User]:
        rows = await self._session.scalars(select(UserRow).order_by(UserRow.created_at))
        return [_row_to_user(r) for r in rows]

    async def delete(self, user_id: str) -> bool:
        result = await self._session.execute(delete(UserRow).where(UserRow.id == user_id))
        await self._session.commit()
        return result.rowcount > 0


class SqlAuditLog:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, action: str, user: User | None = None, ip: str | None = None) -> None:
        self._session.add(
            AuditLogRow(
                user_id=user.id if user else None,
                username=user.username if user else None,
                action=action,
                ip=ip,
                created_at=datetime.now(UTC).isoformat(),
            )
        )
        await self._session.commit()

    async def list_recent(self, limit: int = 100) -> list[dict]:
        rows = await self._session.scalars(
            select(AuditLogRow).order_by(AuditLogRow.id.desc()).limit(limit)
        )
        return [
            {
                "id": r.id,
                "username": r.username,
                "action": r.action,
                "ip": r.ip,
                "created_at": r.created_at,
            }
            for r in rows
        ]


def _row_to_profile(row: "SyncProfileRow"):
    from aether_core.application.sync import SyncProfile, SyncRules

    return SyncProfile(
        id=row.id,
        instance_id=row.instance_id,
        name=row.name,
        channel=row.channel,
        rules=SyncRules.model_validate_json(row.rules or "{}"),
        manifest=json.loads(row.manifest) if row.manifest else None,
        signature=row.signature,
        published_at=datetime.fromisoformat(row.published_at) if row.published_at else None,
        created_at=datetime.fromisoformat(row.created_at),
    )


class SqlSyncProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, profile) -> None:
        self._session.add(
            SyncProfileRow(
                id=profile.id,
                instance_id=profile.instance_id,
                name=profile.name,
                channel=profile.channel,
                rules=profile.rules.model_dump_json(),
                created_at=profile.created_at.isoformat(),
            )
        )
        await self._session.commit()

    async def get(self, profile_id: str):
        row = await self._session.get(SyncProfileRow, profile_id)
        return _row_to_profile(row) if row else None

    async def list_for_instance(self, instance_id: str):
        rows = await self._session.scalars(
            select(SyncProfileRow)
            .where(SyncProfileRow.instance_id == instance_id)
            .order_by(SyncProfileRow.created_at)
        )
        return [_row_to_profile(r) for r in rows]

    async def save(self, profile) -> None:
        row = await self._session.get(SyncProfileRow, profile.id)
        if row is None:
            return
        row.name = profile.name
        row.channel = profile.channel
        row.rules = profile.rules.model_dump_json()
        row.manifest = (
            json.dumps(profile.manifest, ensure_ascii=False) if profile.manifest else None
        )
        row.signature = profile.signature
        row.published_at = profile.published_at.isoformat() if profile.published_at else None
        await self._session.commit()

    async def delete(self, profile_id: str) -> bool:
        result = await self._session.execute(
            delete(SyncProfileRow).where(SyncProfileRow.id == profile_id)
        )
        await self._session.commit()
        return result.rowcount > 0


def _row_to_backup(row: BackupRow) -> Backup:
    return Backup(
        id=row.id,
        instance_id=row.instance_id,
        file_name=row.file_name,
        size_bytes=row.size_bytes,
        kind=BackupKind(row.kind),
        note=row.note or "",
        created_at=datetime.fromisoformat(row.created_at),
    )


class SqlBackupRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, backup: Backup) -> None:
        self._session.add(
            BackupRow(
                id=backup.id,
                instance_id=backup.instance_id,
                file_name=backup.file_name,
                size_bytes=backup.size_bytes,
                kind=str(backup.kind),
                note=backup.note,
                created_at=backup.created_at.isoformat(),
            )
        )
        await self._session.commit()

    async def list_for(self, instance_id: str) -> list[Backup]:
        rows = await self._session.scalars(
            select(BackupRow)
            .where(BackupRow.instance_id == instance_id)
            .order_by(BackupRow.created_at.desc())
        )
        return [_row_to_backup(r) for r in rows]

    async def get(self, backup_id: str) -> Backup | None:
        row = await self._session.get(BackupRow, backup_id)
        return _row_to_backup(row) if row else None

    async def delete(self, backup_id: str) -> bool:
        result = await self._session.execute(delete(BackupRow).where(BackupRow.id == backup_id))
        await self._session.commit()
        return result.rowcount > 0

    async def get_policy(self, instance_id: str) -> BackupPolicy:
        row = await self._session.get(BackupPolicyRow, instance_id)
        if row is None:
            return BackupPolicy()
        return BackupPolicy(schedule=BackupSchedule(row.schedule), keep=row.keep)

    async def set_policy(self, instance_id: str, policy: BackupPolicy) -> None:
        row = await self._session.get(BackupPolicyRow, instance_id)
        if row is None:
            row = BackupPolicyRow(instance_id=instance_id)
            self._session.add(row)
        row.schedule = str(policy.schedule)
        row.keep = policy.keep
        await self._session.commit()

    async def last_run(self, instance_id: str) -> datetime | None:
        row = await self._session.get(BackupPolicyRow, instance_id)
        if row is None or not row.last_run:
            return None
        return datetime.fromisoformat(row.last_run)

    async def mark_run(self, instance_id: str, when: datetime) -> None:
        row = await self._session.get(BackupPolicyRow, instance_id)
        if row is None:
            row = BackupPolicyRow(instance_id=instance_id)
            self._session.add(row)
        row.last_run = when.isoformat()
        await self._session.commit()


def _row_to_task(row: ScheduledTaskRow) -> ScheduledTask:
    return ScheduledTask(
        id=row.id,
        instance_id=row.instance_id,
        kind=TaskKind(row.kind),
        schedule=TaskSchedule(row.schedule),
        at_hour=row.at_hour,
        at_minute=row.at_minute,
        weekday=row.weekday,
        enabled=bool(row.enabled),
        command=row.command or "",
        warn_minutes=row.warn_minutes,
        last_run=datetime.fromisoformat(row.last_run) if row.last_run else None,
        created_at=datetime.fromisoformat(row.created_at),
    )


class SqlScheduledTaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, task: ScheduledTask) -> None:
        self._session.add(
            ScheduledTaskRow(
                id=task.id,
                instance_id=task.instance_id,
                kind=str(task.kind),
                schedule=str(task.schedule),
                at_hour=task.at_hour,
                at_minute=task.at_minute,
                weekday=task.weekday,
                enabled=task.enabled,
                command=task.command,
                warn_minutes=task.warn_minutes,
                last_run=task.last_run.isoformat() if task.last_run else None,
                created_at=task.created_at.isoformat(),
            )
        )
        await self._session.commit()

    async def list_for(self, instance_id: str) -> list[ScheduledTask]:
        rows = await self._session.scalars(
            select(ScheduledTaskRow)
            .where(ScheduledTaskRow.instance_id == instance_id)
            .order_by(ScheduledTaskRow.created_at)
        )
        return [_row_to_task(r) for r in rows]

    async def list_all(self) -> list[ScheduledTask]:
        rows = await self._session.scalars(select(ScheduledTaskRow))
        return [_row_to_task(r) for r in rows]

    async def get(self, task_id: str) -> ScheduledTask | None:
        row = await self._session.get(ScheduledTaskRow, task_id)
        return _row_to_task(row) if row else None

    async def save(self, task: ScheduledTask) -> None:
        row = await self._session.get(ScheduledTaskRow, task.id)
        if row is None:
            return
        row.schedule = str(task.schedule)
        row.at_hour = task.at_hour
        row.at_minute = task.at_minute
        row.weekday = task.weekday
        row.enabled = task.enabled
        row.command = task.command
        row.warn_minutes = task.warn_minutes
        row.last_run = task.last_run.isoformat() if task.last_run else None
        await self._session.commit()

    async def delete(self, task_id: str) -> bool:
        result = await self._session.execute(
            delete(ScheduledTaskRow).where(ScheduledTaskRow.id == task_id)
        )
        await self._session.commit()
        return result.rowcount > 0


def _row_to_trash(row: TrashItemRow) -> TrashItem:
    return TrashItem(
        id=row.id,
        instance_id=row.instance_id,
        original_path=row.original_path,
        stored_name=row.stored_name,
        is_dir=bool(row.is_dir),
        size_bytes=row.size_bytes,
        origin=TrashOrigin(row.origin),
        content_type=row.content_type,
        trashed_at=datetime.fromisoformat(row.trashed_at),
    )


class SqlTrashRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, item: TrashItem) -> None:
        self._session.add(
            TrashItemRow(
                id=item.id,
                instance_id=item.instance_id,
                original_path=item.original_path,
                stored_name=item.stored_name,
                is_dir=item.is_dir,
                size_bytes=item.size_bytes,
                origin=str(item.origin),
                content_type=item.content_type,
                trashed_at=item.trashed_at.isoformat(),
            )
        )
        await self._session.commit()

    async def list_for(self, instance_id: str) -> list[TrashItem]:
        rows = await self._session.scalars(
            select(TrashItemRow)
            .where(TrashItemRow.instance_id == instance_id)
            .order_by(TrashItemRow.trashed_at.desc())
        )
        return [_row_to_trash(r) for r in rows]

    async def get(self, item_id: str) -> TrashItem | None:
        row = await self._session.get(TrashItemRow, item_id)
        return _row_to_trash(row) if row else None

    async def delete(self, item_id: str) -> bool:
        result = await self._session.execute(delete(TrashItemRow).where(TrashItemRow.id == item_id))
        await self._session.commit()
        return result.rowcount > 0


class SqlProviderVersionsRepository:
    """Cache das versões oferecidas pela origem do jogo.

    Fica no banco, e não em memória, porque reiniciar o Core não pode custar
    outra rodada de containers falando com a Steam — e porque assim a lista
    sobrevive à origem estar fora do ar.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, provider_id: str) -> tuple[list[dict], datetime] | None:
        row = await self._session.get(ProviderVersionsRow, provider_id)
        if row is None:
            return None
        try:
            return json.loads(row.payload), datetime.fromisoformat(row.fetched_at)
        except (ValueError, json.JSONDecodeError):
            return None

    async def put(self, provider_id: str, versoes: list[dict]) -> None:
        stmt = sqlite_insert(ProviderVersionsRow).values(
            provider_id=provider_id,
            payload=json.dumps(versoes, ensure_ascii=False),
            fetched_at=datetime.now(UTC).isoformat(),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[ProviderVersionsRow.provider_id],
            set_={"payload": stmt.excluded.payload, "fetched_at": stmt.excluded.fetched_at},
        )
        await self._session.execute(stmt)
        await self._session.commit()
