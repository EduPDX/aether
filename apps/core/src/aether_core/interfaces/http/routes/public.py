"""Public routes: what launchers/clients consume WITHOUT authentication.

Only explicitly published data is reachable here: the signed manifest,
the files it lists, and coarse instance status. Nothing else.
"""

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from aether_core.domain.errors import NotFoundError
from aether_core.domain.instances import Instance
from aether_core.interfaces.http.deps import SyncServiceDep

router = APIRouter(prefix="/public", tags=["public"])


async def _instance_for(request: Request, instance_id: str) -> Instance:
    from aether_core.infrastructure.repositories import SqlInstanceRepository

    async with request.app.state.session_factory() as session:
        instance = await SqlInstanceRepository(session).get(instance_id)
    if instance is None:
        raise NotFoundError(f"instance not found: {instance_id}")
    return instance


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
    }
