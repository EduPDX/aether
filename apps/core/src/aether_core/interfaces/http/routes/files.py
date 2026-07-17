"""File explorer routes (sandboxed to the instance root)."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from aether_core.interfaces.http.deps import (
    FilesRead,
    FilesServiceDep,
    FilesWrite,
    InstanceServiceDep,
)

router = APIRouter(prefix="/instances/{instance_id}/files", tags=["files"])


class WriteFileRequest(BaseModel):
    path: str
    content: str


class FileOpRequest(BaseModel):
    op: Literal["mkdir", "rename", "delete"]
    path: str
    new_name: str | None = None


@router.get("")
async def list_dir(
    instance_id: str,
    instances: InstanceServiceDep,
    files: FilesServiceDep,
    _: FilesRead,
    path: str = "",
) -> list[dict]:
    instance = await instances.get(instance_id)
    entries = await files.list_dir(instance, path)
    return [e.__dict__ for e in entries]


@router.get("/content")
async def read_file(
    instance_id: str,
    path: str,
    instances: InstanceServiceDep,
    files: FilesServiceDep,
    _: FilesRead,
) -> dict:
    instance = await instances.get(instance_id)
    return {"path": path, "content": await files.read_text(instance, path)}


@router.put("/content", status_code=204)
async def write_file(
    instance_id: str,
    body: WriteFileRequest,
    instances: InstanceServiceDep,
    files: FilesServiceDep,
    _: FilesWrite,
) -> None:
    instance = await instances.get(instance_id)
    await files.write_text(instance, body.path, body.content)


@router.post("/op")
async def file_op(
    instance_id: str,
    body: FileOpRequest,
    instances: InstanceServiceDep,
    files: FilesServiceDep,
    _: FilesWrite,
) -> dict:
    instance = await instances.get(instance_id)
    if body.op == "mkdir":
        await files.mkdir(instance, body.path)
    elif body.op == "rename":
        await files.rename(instance, body.path, body.new_name or "")
    elif body.op == "delete":
        moved_to = await files.delete(instance, body.path)
        return {"ok": True, "moved_to": moved_to}
    return {"ok": True}
