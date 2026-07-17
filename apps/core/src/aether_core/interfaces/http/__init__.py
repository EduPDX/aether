"""HTTP API (v1): app factory and wiring."""

from fastapi import APIRouter, FastAPI

from aether_core import __version__
from aether_core.application.events import EventBus
from aether_core.infrastructure.db import make_engine, make_session_factory, run_migrations
from aether_core.infrastructure.filesystem import FileIconStore, LocalContentFilesystem
from aether_core.infrastructure.registry import EntryPointProviderRegistry
from aether_core.infrastructure.settings import AppSettings
from aether_core.interfaces.http.errors import register_error_handlers
from aether_core.interfaces.http.routes import content, instances, meta


def create_app(settings: AppSettings | None = None) -> FastAPI:
    settings = settings or AppSettings()
    settings.ensure_dirs()
    run_migrations(settings.db_path)

    app = FastAPI(
        title="Aether Core",
        version=__version__,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.state.settings = settings
    app.state.session_factory = make_session_factory(make_engine(settings.db_url))
    app.state.bus = EventBus()
    app.state.providers = EntryPointProviderRegistry()
    app.state.fs = LocalContentFilesystem()
    app.state.icons = FileIconStore(settings.icons_dir)

    api = APIRouter(prefix="/api/v1")
    api.include_router(meta.router)
    api.include_router(instances.router)
    api.include_router(content.router)
    app.include_router(api)

    register_error_handlers(app)
    return app
