"""File explorer routes (sandboxed to the instance root)."""

from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from aether_core.domain.errors import ForbiddenError
from aether_core.infrastructure.security import decode_download_token, issue_download_token
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


@router.post("/download-token")
async def download_token(
    instance_id: str,
    path: str,
    request: Request,
    instances: InstanceServiceDep,
    user: FilesRead,
) -> dict:
    """Emite um link curto para o navegador baixar sem cabeçalho.

    Download nativo é uma navegação, e navegação não carrega o Bearer. Com o
    link assinado o navegador grava direto em disco, com barra de progresso e
    sem materializar o arquivo na memória da aba.
    """
    await instances.get(instance_id)
    token = issue_download_token(request.app.state.jwt_secret, user.id, instance_id, path)
    return {"token": token}


@router.get("/download")
async def download(
    instance_id: str,
    path: str,
    request: Request,
    instances: InstanceServiceDep,
    files: FilesServiceDep,
    token: str | None = None,
):
    """Baixa um arquivo; se for pasta, transmite um zip gerado em fluxo."""
    # Aceita Bearer (chamadas do dashboard) ou o token curto de navegação.
    if token:
        decode_download_token(request.app.state.jwt_secret, token, instance_id, path)
    else:
        await _require_files_read(request)

    instance = await instances.get(instance_id)
    target, is_dir = await files.resolve_download(instance, path)

    if not is_dir:
        return FileResponse(target, filename=target.name, media_type="application/octet-stream")

    nome = f"{target.name or instance.name}.zip"
    return StreamingResponse(
        files.stream_zip(instance, path),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{nome}"',
            # Sem tamanho conhecido de antemão: o zip é gerado enquanto envia.
            "Cache-Control": "no-store",
        },
    )


async def _require_files_read(request: Request) -> None:
    """Autenticação manual: a rota aceita dois esquemas, então a permissão
    não pode vir por dependência declarada."""
    from aether_core.interfaces.http.deps import authenticate_request

    user = await authenticate_request(request)
    if not user.has_permission("files.read"):
        raise ForbiddenError("missing permission: files.read")


@router.post("/upload")
async def upload_files(
    instance_id: str,
    instances: InstanceServiceDep,
    files: FilesServiceDep,
    _: FilesWrite,
    uploads: Annotated[list[UploadFile], File()],
    path: Annotated[str, Form()] = "",
    overwrite: Annotated[bool, Form()] = False,
) -> dict:
    """Uploads one or more files into ``path`` (relative to the instance)."""
    instance = await instances.get(instance_id)

    async def chunks(upload: UploadFile):
        while data := await upload.read(1024 * 1024):
            yield data

    saved = []
    for upload in uploads:
        saved.append(
            await files.save_upload(
                instance,
                path,
                upload.filename or "arquivo",
                chunks(upload),
                overwrite=overwrite,
            )
        )
    return {"saved": saved}


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
        # O id serve para a interface oferecer "desfazer" logo depois. Antes
        # daqui saía o caminho absoluto no servidor, que não ajudava ninguém.
        item_id = await files.delete(instance, body.path)
        return {"ok": True, "trash_item_id": item_id}
    return {"ok": True}
