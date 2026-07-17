"""FastAPI dependency wiring (one service graph per request)."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from aether_core.application.content import ContentService
from aether_core.application.instances import InstanceService
from aether_core.infrastructure.repositories import SqlContentCache, SqlInstanceRepository


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.session_factory() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


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


InstanceServiceDep = Annotated[InstanceService, Depends(get_instance_service)]
ContentServiceDep = Annotated[ContentService, Depends(get_content_service)]
