"""Public routes: what launchers/clients consume WITHOUT authentication.

Only explicitly published data is reachable here: the signed manifest,
the files it lists, and coarse instance status. Nothing else.
"""

from pathlib import Path

from aether_sdk import LaunchContext, SupportsContainer
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from aether_core.application.ports_config import descrever
from aether_core.domain.errors import NotFoundError
from aether_core.domain.instances import Instance
from aether_core.interfaces.http.deps import SyncServiceDep

router = APIRouter(prefix="/public", tags=["public"])

# Porta padrão do jogo no container (mesma DEFAULT_PORT do provider Minecraft).
_DEFAULT_GAME_PORT = 25565


async def _instance_for(request: Request, instance_id: str) -> Instance:
    from aether_core.infrastructure.repositories import SqlInstanceRepository

    async with request.app.state.session_factory() as session:
        instance = await SqlInstanceRepository(session).get(instance_id)
    if instance is None:
        raise NotFoundError(f"instance not found: {instance_id}")
    return instance


def _game_port(request: Request, instance: Instance) -> int | None:
    """Porta TCP publicada onde os clientes conectam.

    É informação de conexão (o jogador precisa dela para entrar), por isso pode
    ser pública. Continua agnóstica de jogo: só lê o mapeamento de portas que a
    instância já declara — sem nenhuma lógica específica de Minecraft aqui.
    """
    provider = request.app.state.providers.get(instance.provider_id)
    if not isinstance(provider, SupportsContainer):
        return None
    try:
        spec = provider.container_spec(
            LaunchContext(root_dir=Path(instance.root_dir), provider_data=instance.provider_data)
        )
        portas = descrever(spec, instance.provider_data)
    except Exception:  # noqa: BLE001 - provider quebrado não deve derrubar o status
        return None
    tcp = [p for p in portas if p.get("protocol") == "tcp"]
    if not tcp:
        return None
    for p in tcp:
        if p.get("container_port") == _DEFAULT_GAME_PORT:
            return p.get("host_port")
    return tcp[0].get("host_port")


@router.get("/sync/{profile_id}")
async def get_manifest(profile_id: str, sync: SyncServiceDep) -> dict:
    profile = await sync.get_profile(profile_id)
    return sync.public_payload(profile)


@router.get("/sync/{profile_id}/file")
async def download_file(
    profile_id: str, path: str, request: Request, sync: SyncServiceDep
) -> FileResponse:
    profile = await sync.get_profile(profile_id)
    instance = await _instance_for(request, profile.instance_id)
    full = sync.resolve_manifest_file(instance, profile, path)
    return FileResponse(full, media_type="application/octet-stream", filename=full.name)


@router.get("/instances/{instance_id}/status")
async def public_status(instance_id: str, request: Request) -> dict:
    instance = await _instance_for(request, instance_id)
    return {
        "name": instance.name,
        "state": request.app.state.supervisor.state(instance.id),
        "port": _game_port(request, instance),
    }
