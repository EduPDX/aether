"""Resource metrics routes (host + per-instance process)."""

from dataclasses import asdict

from fastapi import APIRouter, Request

from aether_core.interfaces.http.deps import InstancesRead

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("")
async def metrics(request: Request, _: InstancesRead) -> dict:
    """Snapshot atual do host + processos das instâncias + histórico curto."""
    from aether_core.infrastructure.repositories import SqlInstanceRepository

    svc = request.app.state.metrics
    svc.sample()

    async with request.app.state.session_factory() as session:
        instances = await SqlInstanceRepository(session).list_all()

    return {
        "host": asdict(svc.host()),
        "instances": [asdict(await svc.instance_metrics(i)) | {"name": i.name} for i in instances],
        "history": svc.history(),
    }
