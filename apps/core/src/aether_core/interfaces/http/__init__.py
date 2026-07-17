"""HTTP API (v1): app factory and wiring."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from aether_core import __version__
from aether_core.application.events import EventBus
from aether_core.infrastructure.db import make_engine, make_session_factory, run_migrations
from aether_core.infrastructure.filesystem import FileIconStore, LocalContentFilesystem
from aether_core.infrastructure.processes import LocalProcessSupervisor
from aether_core.infrastructure.registry import EntryPointProviderRegistry
from aether_core.infrastructure.security import load_or_create_secret
from aether_core.infrastructure.settings import AppSettings
from aether_core.interfaces.http.errors import register_error_handlers
from aether_core.interfaces.http.routes import auth, content, instances, meta, power, users
from aether_core.interfaces.http.ws import router as ws_router


def create_app(settings: AppSettings | None = None) -> FastAPI:
    settings = settings or AppSettings()
    settings.ensure_dirs()
    run_migrations(settings.db_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        await app.state.supervisor.shutdown()

    app = FastAPI(
        title="Aether Core",
        version=__version__,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.session_factory = make_session_factory(make_engine(settings.db_url))
    app.state.bus = EventBus()
    app.state.providers = EntryPointProviderRegistry()
    app.state.fs = LocalContentFilesystem()
    app.state.icons = FileIconStore(settings.icons_dir)
    app.state.supervisor = LocalProcessSupervisor(app.state.bus)
    app.state.jwt_secret = load_or_create_secret(settings.data_dir)

    api = APIRouter(prefix="/api/v1")
    api.include_router(meta.router)
    api.include_router(auth.router)
    api.include_router(users.router)
    api.include_router(instances.router)
    api.include_router(content.router)
    api.include_router(power.router)
    app.include_router(api)
    app.include_router(ws_router)

    @app.middleware("http")
    async def audit_middleware(request, call_next):
        response = await call_next(request)
        if (
            request.method in ("POST", "PUT", "PATCH", "DELETE")
            and request.url.path.startswith("/api/")
            and not request.url.path.startswith("/api/v1/auth/")
            and response.status_code < 400
        ):
            from aether_core.infrastructure.repositories import SqlAuditLog

            user = getattr(request.state, "user", None)
            ip = request.client.host if request.client else None
            async with app.state.session_factory() as session:
                await SqlAuditLog(session).add(f"{request.method} {request.url.path}", user, ip)
        return response

    register_error_handlers(app)
    return app
