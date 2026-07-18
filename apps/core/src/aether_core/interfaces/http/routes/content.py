"""Content routes: listing, toggle, trash, copy, compare and icons."""

from typing import Annotated

from fastapi import APIRouter, Query, Request
from fastapi.responses import FileResponse

from aether_core.domain.errors import NotFoundError
from aether_core.interfaces.http.deps import (
    ContentRead,
    ContentServiceDep,
    ContentWrite,
    InstanceServiceDep,
)
from aether_core.interfaces.http.schemas import (
    CompareOut,
    ContentFileRequest,
    ContentItemOut,
    CopyContentRequest,
)

router = APIRouter(tags=["content"])

TypeParam = Annotated[str, Query(alias="type")]


@router.get("/instances/{instance_id}/content")
async def list_content(
    instance_id: str,
    type: TypeParam,
    instances: InstanceServiceDep,
    content: ContentServiceDep,
    _: ContentRead,
) -> list[ContentItemOut]:
    instance = await instances.get(instance_id)
    items = await content.list_content(instance, type)
    return [ContentItemOut.from_domain(i) for i in items]


@router.post("/instances/{instance_id}/content/toggle")
async def toggle_content(
    instance_id: str,
    body: ContentFileRequest,
    instances: InstanceServiceDep,
    content: ContentServiceDep,
    _: ContentWrite,
) -> dict:
    instance = await instances.get(instance_id)
    new_name = await content.toggle(instance, body.type, body.file)
    return {"file": new_name}


@router.post("/instances/{instance_id}/content/trash")
async def trash_content(
    instance_id: str,
    body: ContentFileRequest,
    instances: InstanceServiceDep,
    content: ContentServiceDep,
    _: ContentWrite,
) -> dict:
    instance = await instances.get(instance_id)
    moved_to = await content.trash(instance, body.type, body.file)
    return {"moved_to": moved_to}


@router.post("/instances/{instance_id}/content/copy", status_code=204)
async def copy_content(
    instance_id: str,
    body: CopyContentRequest,
    instances: InstanceServiceDep,
    content: ContentServiceDep,
    _: ContentWrite,
) -> None:
    source = await instances.get(instance_id)
    target = await instances.get(body.to_instance_id)
    await content.copy(source, target, body.type, body.file, body.to_type)


@router.get("/instances/{instance_id}/content/compare")
async def compare_content(
    instance_id: str,
    with_instance: Annotated[str, Query(alias="with")],
    type: TypeParam,
    instances: InstanceServiceDep,
    content: ContentServiceDep,
    _: ContentRead,
    with_type: Annotated[str | None, Query(alias="with_type")] = None,
) -> CompareOut:
    a = await instances.get(instance_id)
    b = await instances.get(with_instance)
    result = await content.compare(a, b, type, with_type)
    return CompareOut(
        only_in_a=[ContentItemOut.from_domain(i) for i in result.only_in_a],
        only_in_b=[ContentItemOut.from_domain(i) for i in result.only_in_b],
        version_diffs=result.version_diffs,
    )


@router.get("/icons/{name}", tags=["icons"])
def get_icon(name: str, request: Request) -> FileResponse:
    path = request.app.state.icons.path(name)
    if not path.is_file():
        raise NotFoundError(f"icon not found: {name}")
    return FileResponse(path, media_type="image/png")
