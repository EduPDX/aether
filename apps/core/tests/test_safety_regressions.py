"""Regressões de perda de dados, fronteiras de arquivos e sessão de eventos."""

import asyncio
import io
import zipfile
from types import SimpleNamespace

import pytest
from aether_core.application.backups import BackupService, collect_files
from aether_core.application.events import EventBus
from aether_core.application.files import FilesService
from aether_core.application.sync import SyncRules
from aether_core.domain.errors import ConflictError, ValidationFailedError
from aether_core.domain.instances import InstanceState
from aether_sdk import BackupSpec, QuiescePlan
from starlette.websockets import WebSocketDisconnect


def test_zip_nao_exporta_link_para_arquivo_externo(tmp_path):
    root = tmp_path / "instance"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("privado")
    (root / "link.txt").symlink_to(outside)
    (root / "public.txt").write_text("permitido")
    archive = b"".join(
        FilesService(None, EventBus()).stream_zip(SimpleNamespace(root_dir=str(root)), "")
    )
    with zipfile.ZipFile(io.BytesIO(archive)) as zf:
        assert zf.namelist() == ["public.txt"]
        assert zf.read("public.txt") == b"permitido"
    with pytest.raises(ValidationFailedError):
        collect_files(root, BackupSpec(include=("*",)))


def test_zip_suporta_membro_que_excede_limite_zip64(tmp_path, monkeypatch):
    (tmp_path / "file.bin").write_bytes(b"x" * 2048)
    monkeypatch.setattr(zipfile, "ZIP64_LIMIT", 1024)
    archive = b"".join(
        FilesService(None, EventBus()).stream_zip(SimpleNamespace(root_dir=str(tmp_path)), "")
    )
    with zipfile.ZipFile(io.BytesIO(archive)) as zf:
        assert zf.read("file.bin") == b"x" * 2048


@pytest.mark.parametrize("path", ["../outside", "/absolute", "C:/root", "..\\outside", "mods/../x"])
def test_sync_recusa_destino_fora_da_raiz(path):
    with pytest.raises(ValueError):
        SyncRules.model_validate({"rules": [{"dir": "mods", "target": path}]})


@pytest.mark.parametrize("cancel", [False, True])
def test_backup_aborta_e_retoma_gravacao_em_falha_ou_cancelamento(tmp_path, cancel):
    async def case():
        commands, records = [], []
        paused = asyncio.Event()

        class Supervisor:
            def state(self, _):
                return InstanceState.RUNNING

            async def send_command(self, _, command):
                commands.append(command)
                if command == "save-off":
                    paused.set()
                    if not cancel:
                        raise RuntimeError("falha simulada")

        class Repo:
            async def add(self, backup):
                records.append(backup)

        (tmp_path / "world.dat").write_bytes(b"mundo")
        service = BackupService(Repo(), None, Supervisor(), EventBus(), tmp_path / "backups")
        service._spec = lambda _: BackupSpec(include=("world.dat",))
        service._quiesce = lambda _: QuiescePlan(
            before=("save-off",), after=("save-on",), settle_seconds=60
        )
        instance = SimpleNamespace(root_dir=str(tmp_path), id="demo", name="Demo")
        task = asyncio.create_task(service.create(instance))
        await asyncio.wait_for(paused.wait(), timeout=2)
        if cancel:
            other = BackupService(Repo(), None, Supervisor(), service._bus, tmp_path / "backups")
            with pytest.raises(ConflictError, match="em andamento"):
                await other.create(instance)
            task.cancel()
        with pytest.raises(asyncio.CancelledError if cancel else RuntimeError):
            await task
        assert commands == ["save-off", "save-on"]
        assert not records
        assert not list((tmp_path / "backups").rglob("*.zip"))

    asyncio.run(case())


def test_websocket_recusa_token_revogado(client):
    token = client.headers["Authorization"].removeprefix("Bearer ")
    result = client.post(
        "/api/v1/auth/password",
        json={"current_password": "senha-forte-123", "new_password": "nova-senha-123"},
    )
    assert result.status_code == 200
    with client.websocket_connect(f"/ws?token={token}") as ws:
        with pytest.raises(WebSocketDisconnect) as error:
            ws.receive_json()
        assert error.value.code == 4401


@pytest.mark.parametrize("topic", ["update.progress", "images.pull", "files", "unknown"])
def test_viewer_nao_assina_eventos_privilegiados(client, topic):
    assert (
        client.post(
            "/api/v1/users",
            json={"username": "viewer", "password": "viewer-pass-123", "role": "viewer"},
        ).status_code
        == 201
    )
    token = client.post(
        "/api/v1/auth/login", json={"username": "viewer", "password": "viewer-pass-123"}
    ).json()["access_token"]
    with client.websocket_connect(f"/ws?token={token}") as ws:
        ws.send_json({"op": "subscribe", "topic": topic})
        with pytest.raises(WebSocketDisconnect) as error:
            ws.receive_json()
        assert error.value.code == 4403


def test_websocket_aberto_para_de_entregar_apos_revogacao(client):
    token = client.headers["Authorization"].removeprefix("Bearer ")

    async def publish():
        await asyncio.sleep(0.05)
        await client.app.state.bus.publish("update.progress", {"etapa": "teste"})

    with client.websocket_connect(f"/ws?token={token}") as ws:
        ws.send_json({"op": "subscribe", "topic": "update.progress"})
        client.portal.call(publish)
        assert ws.receive_json()["payload"]["etapa"] == "teste"
        assert (
            client.post(
                "/api/v1/auth/password",
                json={"current_password": "senha-forte-123", "new_password": "nova-senha-123"},
            ).status_code
            == 200
        )
        client.portal.call(publish)
        with pytest.raises(WebSocketDisconnect) as error:
            ws.receive_json()
        assert error.value.code == 4401
