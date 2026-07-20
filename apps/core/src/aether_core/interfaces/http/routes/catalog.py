"""Catálogo de jogos: o que dá para hospedar e o que cada jogo exige."""

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from aether_core.interfaces.http.deps import InstancesRead

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("")
async def listar(request: Request, _: InstancesRead) -> list[dict]:
    return await request.app.state.catalog.list()


@router.get("/{game_id}")
async def detalhe(
    request: Request, game_id: str, _: InstancesRead, atualizar: bool = False
) -> dict:
    return await request.app.state.catalog.get(game_id, atualizar=atualizar)


@router.get("/{game_id}/media/{arquivo}")
async def media(request: Request, game_id: str, arquivo: str) -> FileResponse:
    """Imagens baixadas pelo Core.

    Servi-las daqui é o que faz o catálogo funcionar em rede fechada e evita
    que o navegador de cada usuário vá até a CDN da loja.

    Sem autenticação de propósito: uma tag ``<img>`` não manda cabeçalho, e o
    conteúdo é capa de jogo publicada pela própria loja — exigir token aqui só
    quebraria a imagem sem proteger nada.
    """
    caminho = request.app.state.catalog.media_path(game_id, arquivo)
    return FileResponse(caminho, media_type="image/jpeg")
