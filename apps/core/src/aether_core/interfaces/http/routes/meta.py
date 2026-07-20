"""System and provider discovery routes."""

from aether_sdk import (
    SupportsBackup,
    SupportsConfig,
    SupportsContainer,
    SupportsGameMetadata,
    SupportsLaunch,
    SupportsPlayers,
    SupportsProvision,
)
from fastapi import APIRouter, Request

from aether_core import __version__
from aether_core.interfaces.http.deps import CurrentUserDep

router = APIRouter()


@router.get("/health", tags=["system"])
def health() -> dict:
    return {"status": "ok", "version": __version__}


def _capabilities(p) -> dict:
    """O dashboard liga/desliga telas pelo que o provider sabe fazer —
    é isto que evita `if provider == minecraft` espalhado na interface."""
    return {
        "launch": isinstance(p, SupportsLaunch),
        "container": isinstance(p, SupportsContainer),
        "provision": isinstance(p, SupportsProvision),
        "config": isinstance(p, SupportsConfig),
        "backup": isinstance(p, SupportsBackup),
        "players": isinstance(p, SupportsPlayers),
        "sources": bool(getattr(p, "content_sources", None) and p.content_sources()),
        "game_metadata": isinstance(p, SupportsGameMetadata),
    }


@router.get("/providers", tags=["providers"])
def providers(request: Request, _: CurrentUserDep) -> list[dict]:
    result = []
    for p in request.app.state.providers.all().values():
        item = {
            "manifest": p.manifest.model_dump(),
            "content_types": [ct.model_dump() for ct in p.content_types()],
            "capabilities": _capabilities(p),
        }
        if isinstance(p, SupportsProvision):
            item["provision_schema"] = p.provision_schema().model_dump()
        result.append(item)
    return result
