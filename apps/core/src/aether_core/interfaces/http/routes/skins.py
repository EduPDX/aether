"""Skins dos jogadores — armazenamento e serviço para o CustomSkinLoader.

Em modo offline o jogo não conhece skins; o mod CustomSkinLoader busca a skin
por nome de usuário numa URL. Aqui o Core hospeda essas skins: qualquer cliente
com o mod (todos, se estiver no pacote) vê a skin de todos.

- **Servir** é público (o mod acessa sem login).
- **Enviar** exige o código do perfil (prova de ser um cliente legítimo daquele
  servidor) — suficiente para um servidor de amigos.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from aether_core.interfaces.http.deps import SyncServiceDep

router = APIRouter(prefix="/public", tags=["skins"])

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_MAX_SKIN = 512 * 1024  # skins do Minecraft têm poucos KB
_NAME_RE = re.compile(r"^[A-Za-z0-9_]{1,16}$")


def _skins_dir(request: Request) -> Path:
    d = Path(request.app.state.settings.data_dir) / "skins"
    d.mkdir(parents=True, exist_ok=True)
    return d


# Skins mudam quando o jogador troca; não podem ficar presas em cache de borda
# (Cloudflare cacheia .png por padrão). no-store garante que sempre venha fresca.
_NOCACHE = {"Cache-Control": "no-store, max-age=0"}


@router.get("/skins/{username}.png")
async def get_skin(username: str, request: Request) -> FileResponse:
    if not _NAME_RE.match(username):
        raise HTTPException(status_code=404, detail="not found", headers=_NOCACHE)
    # Normaliza para minúsculo: o mod pode pedir o nome com outra caixa.
    path = _skins_dir(request) / f"{username.lower()}.png"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="sem skin", headers=_NOCACHE)
    return FileResponse(path, media_type="image/png", headers=_NOCACHE)


@router.get("/capes/{username}.png")
async def get_cape(username: str) -> FileResponse:
    # Capas ainda não são suportadas; 404 faz o mod simplesmente ignorar.
    raise HTTPException(status_code=404, detail="sem capa", headers=_NOCACHE)


@router.post("/skins/{username}")
async def upload_skin(username: str, request: Request, sync: SyncServiceDep) -> dict:
    if not _NAME_RE.match(username):
        raise HTTPException(status_code=400, detail="nome de usuário inválido")
    # Valida o cliente pelo código do perfil (404 se não existir).
    await sync.get_profile(request.headers.get("x-aether-profile", ""))
    body = await request.body()
    if not body.startswith(_PNG_MAGIC) or len(body) > _MAX_SKIN:
        raise HTTPException(status_code=400, detail="envie um PNG de skin válido")
    dest = _skins_dir(request) / f"{username.lower()}.png"
    tmp = dest.with_name(dest.name + ".part")
    tmp.write_bytes(body)
    tmp.replace(dest)
    return {"ok": True, "username": username}
