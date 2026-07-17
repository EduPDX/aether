"""Server-side filesystem browser route (admin only)."""

from fastapi import APIRouter

from aether_core.application.browse import browse as browse_fs
from aether_core.interfaces.http.deps import InstancesWrite

router = APIRouter(prefix="/fs", tags=["fs"])


@router.get("/browse")
async def browse(_: InstancesWrite, path: str | None = None) -> dict:
    result = browse_fs(path)
    return {
        "path": result.path,
        "parent": result.parent,
        "separator": result.separator,
        "entries": [{"name": e.name, "path": e.path} for e in result.entries],
    }
