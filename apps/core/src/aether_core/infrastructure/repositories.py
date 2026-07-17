"""SQLAlchemy implementations of the persistence ports."""

import json
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from aether_core.application.ports import CachedContent
from aether_core.domain.instances import Instance
from aether_core.infrastructure.db import ContentCacheRow, InstanceRow

_CHUNK = 500  # stay under SQLite's bound-parameter limit


def _row_to_instance(row: InstanceRow) -> Instance:
    return Instance(
        id=row.id,
        name=row.name,
        provider_id=row.provider_id,
        root_dir=row.root_dir,
        content_dirs=json.loads(row.content_dirs or "{}"),
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
