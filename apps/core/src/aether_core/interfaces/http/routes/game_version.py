"""Troca de versão de jogos sem instalador (o Minecraft via itzg).

Diferente de ``install`` (que roda um instalador e é assíncrono), aqui a versão
é um campo do ``provider_data`` e a troca é imediata: valida, faz backup, grava.
O download da versão nova acontece quando o servidor sobe — o container é
recriado com a env nova pelo próprio fluxo de start.
"""

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from aether_core.domain.backups import BackupKind
from aether_core.domain.errors import ConflictError, ValidationFailedError
from aether_core.domain.instances import InstanceState
from aether_core.interfaces.http.deps import (
    BackupServiceDep,
    InstanceServiceDep,
    InstancesRead,
    InstancesWrite,
    PowerServiceDep,
)

router = APIRouter(tags=["versions"])


class SetVersionRequest(BaseModel):
    version: str = Field(min_length=1, max_length=40)
    skip_backup: bool = False
    """Pular o backup é decisão explícita de quem sabe o que está fazendo."""


def _provider(request: Request, instance):
    p = request.app.state.providers.get(instance.provider_id)
    if not callable(getattr(p, "pin_game_version", None)):
        raise ValidationFailedError(
            f"o provider {instance.provider_id!r} não troca de versão pelo painel"
        )
    return p


@router.get("/instances/{instance_id}/game-version")
async def game_version(
    request: Request,
    instance_id: str,
    instances: InstanceServiceDep,
    power: PowerServiceDep,
    _: InstancesRead,
) -> dict:
    instance = await instances.get(instance_id)
    provider = _provider(request, instance)
    disponiveis = await provider.game_versions()
    return {
        "current": provider.current_game_version(instance.provider_data),
        "modded": provider.game_version_is_modded(instance.provider_data),
        "running": power.state(instance) is not InstanceState.STOPPED,
        "available": [v.model_dump() for v in disponiveis],
    }


@router.post("/instances/{instance_id}/game-version")
async def set_game_version(
    request: Request,
    instance_id: str,
    body: SetVersionRequest,
    instances: InstanceServiceDep,
    backups: BackupServiceDep,
    power: PowerServiceDep,
    user: InstancesWrite,
) -> dict:
    """Fixa a versão. Vale na próxima subida do servidor (o itzg baixa então)."""
    instance = await instances.get(instance_id)
    provider = _provider(request, instance)

    # Parado por dois motivos: recriar o container exige, e o backup de um
    # servidor no ar sai inconsistente.
    if power.state(instance) is not InstanceState.STOPPED:
        raise ConflictError("pare o servidor antes de trocar a versão")

    mudancas = provider.pin_game_version(instance.provider_data, body.version)

    fez_backup = False
    if not body.skip_backup and provider.current_game_version(instance.provider_data):
        # Atualizar é a operação mais destrutiva: backup antes de gravar. Só
        # quando já há versão — numa instância recém-criada não há o que salvar.
        try:
            await backups.create(
                instance, kind=BackupKind.MANUAL, note=f"antes de trocar para {body.version}"
            )
            fez_backup = True
        except Exception as exc:  # noqa: BLE001
            raise ValidationFailedError(
                f"a troca foi cancelada porque o backup falhou: {exc}"
            ) from exc

    await instances.merge_provider_data(instance_id, mudancas)
    await _audit(request, f"game_version instance={instance.name} version={body.version}", user)
    return {"version": body.version, "backed_up": fez_backup}


async def _audit(request: Request, action: str, user) -> None:
    from aether_core.infrastructure.repositories import SqlAuditLog

    async with request.app.state.session_factory() as session:
        ip = request.client.host if request.client else None
        await SqlAuditLog(session).add(action, user, ip)
