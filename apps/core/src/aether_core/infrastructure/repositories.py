"""SQLAlchemy implementations of the persistence ports."""

import json
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from aether_core.application.ports import CachedContent
from aether_core.domain.instances import Instance
from aether_core.domain.users import Role, User
from aether_core.infrastructure.db import (
    AuditLogRow,
    ContentCacheRow,
    InstanceRow,
    SyncProfileRow,
    UserRow,
)

_CHUNK = 500  # stay under SQLite's bound-parameter limit


def _row_to_instance(row: InstanceRow) -> Instance:
    return Instance(
        id=row.id,
        name=row.name,
        provider_id=row.provider_id,
        root_dir=row.root_dir,
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

    async def delete(self, instance_id: str) -> bool:
        result = await self._session.execute(
            delete(InstanceRow).where(InstanceRow.id == instance_id)
        )
        await self._session.commit()
        return result.rowcount > 0


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
                created_at=user.created_at.isoformat(),
            )
        )
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
