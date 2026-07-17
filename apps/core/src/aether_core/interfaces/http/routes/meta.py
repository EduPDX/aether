"""System and provider discovery routes."""

from fastapi import APIRouter, Request

from aether_core import __version__
from aether_core.interfaces.http.deps import CurrentUserDep

router = APIRouter()


@router.get("/health", tags=["system"])
def health() -> dict:
    return {"status": "ok", "version": __version__}


@router.get("/providers", tags=["providers"])
def providers(request: Request, _: CurrentUserDep) -> list[dict]:
    return [
        {
            "manifest": p.manifest.model_dump(),
            "content_types": [ct.model_dump() for ct in p.content_types()],
        }
        for p in request.app.state.providers.all().values()
    ]
