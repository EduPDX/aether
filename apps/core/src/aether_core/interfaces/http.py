"""HTTP API (v1). Every route lives under ``/api/v1``."""

from fastapi import APIRouter, FastAPI

from aether_core import __version__
from aether_core.infrastructure.plugins import discover_providers


def create_app() -> FastAPI:
    app = FastAPI(
        title="Aether Core",
        version=__version__,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.include_router(_api_v1())
    return app


def _api_v1() -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.get("/health", tags=["system"])
    def health() -> dict:
        return {"status": "ok", "version": __version__}

    @router.get("/providers", tags=["providers"])
    def providers() -> list[dict]:
        return [
            {
                "manifest": p.manifest.model_dump(),
                "contentTypes": [ct.model_dump() for ct in p.content_types()],
            }
            for p in discover_providers().values()
        ]

    return router
