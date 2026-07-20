"""Rotas de sistema: estado da instalação e atualização da aplicação."""

from dataclasses import asdict

from fastapi import APIRouter, Request

from aether_core import __version__
from aether_core.interfaces.http.deps import UsersManage

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/update")
def update_status(request: Request, _: UsersManage) -> dict:
    """Se dá para atualizar, em que commit estamos e quanto falta."""
    status = request.app.state.updates.status()
    return {"version": __version__, **asdict(status)}


@router.post("/update", status_code=202)
async def update(request: Request, _: UsersManage) -> dict:
    """Atualiza e reinicia.

    Exige `users.manage` (dono da instalação): trocar o código em execução é a
    operação mais perigosa do painel. A resposta sai antes do reinício — o
    progresso continua pelo tópico `update.progress` do WebSocket.
    """
    return await request.app.state.updates.update()
