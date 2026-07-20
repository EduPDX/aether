"""HTTP API (v1): app factory and wiring."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from aether_core import __version__
from aether_core.application.events import EventBus
from aether_core.application.images import ImageService
from aether_core.application.metrics import MetricsService
from aether_core.application.power import SupervisorHub
from aether_core.application.scheduler import BackupScheduler
from aether_core.domain.instances import InstanceRuntime
from aether_core.infrastructure.containers import AiodockerRuntime, DockerContainerSupervisor
from aether_core.infrastructure.db import make_engine, make_session_factory, run_migrations
from aether_core.infrastructure.filesystem import FileIconStore, LocalContentFilesystem
from aether_core.infrastructure.http_client import CatalogHttp, HttpDownloader
from aether_core.infrastructure.processes import LocalProcessSupervisor
from aether_core.infrastructure.registry import EntryPointProviderRegistry
from aether_core.infrastructure.security import (
    load_or_create_secret,
    load_or_create_sync_key,
    public_key_hex,
    sign_payload,
)
from aether_core.infrastructure.settings import AppSettings
from aether_core.interfaces.http.errors import register_error_handlers
from aether_core.interfaces.http.routes import (
    auth,
    backups,
    browse,
    config,
    content,
    files,
    images,
    instances,
    meta,
    metrics,
    power,
    public,
    sources,
    sync,
    tasks,
    trash,
    users,
)
from aether_core.interfaces.http.ws import router as ws_router


class _SyncSigner:
    def __init__(self, key) -> None:
        self._key = key

    def sign(self, payload: bytes) -> str:
        return sign_payload(self._key, payload)

    def public_key(self) -> str:
        return public_key_hex(self._key)


def create_app(settings: AppSettings | None = None) -> FastAPI:
    settings = settings or AppSettings()
    settings.ensure_dirs()
    run_migrations(settings.db_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.backup_scheduler.start()
        await _reconcile_containers(app)
        yield
        await app.state.backup_scheduler.stop()
        await app.state.catalog_http.close()
        await app.state.images.shutdown()
        await app.state.supervisor.shutdown()
        await app.state.container_runtime.close()

    async def _reconcile_containers(app: FastAPI) -> None:
        """Readota containers de instância que ficaram rodando entre restarts."""
        from aether_sdk import SupportsContainer

        from aether_core.infrastructure.repositories import SqlInstanceRepository

        async with app.state.session_factory() as session:
            instances = await SqlInstanceRepository(session).list_all()
        codecs = {}
        for inst in instances:
            if inst.runtime != InstanceRuntime.DOCKER:
                continue
            provider = app.state.providers.all().get(inst.provider_id)
            codecs[inst.id] = (
                provider.console_codec() if isinstance(provider, SupportsContainer) else None
            )
        if codecs:
            await app.state.docker_supervisor.reconcile(codecs)

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
    process_supervisor = LocalProcessSupervisor(app.state.bus)
    app.state.container_runtime = AiodockerRuntime()
    app.state.docker_supervisor = DockerContainerSupervisor(
        app.state.container_runtime, app.state.bus
    )
    # `supervisors` (por runtime) alimenta o PowerService; `supervisor` é o
    # hub para quem só conhece o instance_id (backups, tasks, rotas de leitura).
    app.state.supervisors = {
        InstanceRuntime.PROCESS.value: process_supervisor,
        InstanceRuntime.DOCKER.value: app.state.docker_supervisor,
    }
    app.state.supervisor = SupervisorHub(process_supervisor, app.state.docker_supervisor)
    app.state.metrics = MetricsService(
        app.state.supervisor,
        container_supervisor=app.state.docker_supervisor,
        container_runtime=app.state.container_runtime,
    )
    app.state.images = ImageService(app.state.container_runtime, app.state.providers, app.state.bus)
    app.state.catalog_http = CatalogHttp()
    app.state.downloader = HttpDownloader()
    # Providers que sabem falar com catálogos recebem o transporte aqui: eles
    # não abrem conexão sozinhos, para seguirem testáveis sem rede.
    for provider in app.state.providers.all().values():
        injetar = getattr(provider, "set_http", None)
        if callable(injetar):
            injetar(app.state.catalog_http.get, app.state.catalog_http.post)

    app.state.jwt_secret = load_or_create_secret(settings.data_dir)
    app.state.sync_signer = _SyncSigner(load_or_create_sync_key(settings.data_dir))

    def _backup_service(session):
        from aether_core.application.backups import BackupService
        from aether_core.infrastructure.repositories import SqlBackupRepository

        return BackupService(
            repo=SqlBackupRepository(session),
            providers=app.state.providers,
            supervisor=app.state.supervisor,
            bus=app.state.bus,
            backups_root=settings.backups_dir,
        )

    def _instance_repo(session):
        from aether_core.infrastructure.repositories import SqlInstanceRepository

        return SqlInstanceRepository(session)

    def _task_service(session):
        from aether_core.application.power import PowerService
        from aether_core.application.tasks import TaskService
        from aether_core.infrastructure.repositories import SqlScheduledTaskRepository

        return TaskService(
            repo=SqlScheduledTaskRepository(session),
            supervisor=app.state.supervisor,
            power=PowerService(providers=app.state.providers, supervisors=app.state.supervisors),
            bus=app.state.bus,
        )

    app.state.backup_scheduler = BackupScheduler(
        app.state.session_factory, _backup_service, _instance_repo, _task_service
    )

    if settings.static_dir and settings.static_dir.is_dir():
        from fastapi.staticfiles import StaticFiles

        app.mount("/app", StaticFiles(directory=settings.static_dir, html=True), name="dashboard")

        @app.get("/", include_in_schema=False)
        def index_redirect():
            from fastapi.responses import RedirectResponse

            return RedirectResponse("/app/")

    api = APIRouter(prefix="/api/v1")
    api.include_router(meta.router)
    api.include_router(auth.router)
    api.include_router(users.router)
    api.include_router(instances.router)
    api.include_router(content.router)
    api.include_router(power.router)
    api.include_router(files.router)
    api.include_router(config.router)
    api.include_router(backups.router)
    api.include_router(trash.router)
    api.include_router(sources.router)
    api.include_router(tasks.router)
    api.include_router(sync.router)
    api.include_router(public.router)
    api.include_router(browse.router)
    api.include_router(metrics.router)
    api.include_router(images.router)
    app.include_router(api)
    app.include_router(ws_router)

    @app.middleware("http")
    async def no_cache_html(request, call_next):
        """O index.html nunca pode ficar em cache.

        Os assets têm hash no nome (podem ser cacheados para sempre), mas
        se o navegador guardar o index.html antigo ele continua pedindo o
        bundle antigo — foi assim que uma atualização do painel não
        apareceu para o usuário.
        """
        response = await call_next(request)
        path = request.url.path
        if path.startswith("/app") and (path.endswith("/") or path.endswith(".html")):
            response.headers["Cache-Control"] = "no-cache, must-revalidate"
        elif path.startswith("/app/assets/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

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
