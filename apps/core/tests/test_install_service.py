"""Instalação e atualização: ordem das etapas e o que acontece quando falham.

O projeto não usa pytest-asyncio; os casos assíncronos rodam via asyncio.run.
"""

import asyncio
from pathlib import Path

import pytest
from aether_core.application.events import EventBus
from aether_core.application.install import InstallService
from aether_core.domain.errors import ConflictError, ValidationFailedError
from aether_core.domain.instances import Instance, InstanceState
from aether_sdk import ContainerSpec, VersionInfo


class FakeProvider:
    """Provider que registra a ordem em que foi chamado."""

    def __init__(self, chamadas: list[str], instalado: str = "") -> None:
        self.chamadas = chamadas
        self._instalado = instalado

    def install_spec(self, ctx, version: str) -> ContainerSpec:
        return ContainerSpec(image="steamcmd", command=["bash", "-c", f"install {version}"])

    def versions_spec(self) -> ContainerSpec:
        return ContainerSpec(image="steamcmd", command=["bash", "-c", "info"])

    def parse_versions(self, stdout: str) -> list[VersionInfo]:
        if "sem rede" in stdout:
            return []
        return [VersionInfo(id="public", label="Mais recente (estável)")]

    def installed_version(self, root_dir) -> str:
        return self._instalado

    def after_install(self, root_dir, provider_data: dict) -> dict:
        self.chamadas.append("after_install")
        return {"install": {"config_seeded": True, "new_properties": ["SandboxCode"]}}


class FakeRegistry:
    def __init__(self, provider) -> None:
        self._provider = provider

    def get(self, provider_id: str):
        return self._provider

    def all(self) -> dict:
        return {"sevendays": self._provider}


class FakeRuntime:
    def __init__(self, chamadas: list[str], exit_code: int = 0, saida: str = "ok") -> None:
        self.chamadas = chamadas
        self.exit_code = exit_code
        self.saida = saida

    async def run_once(self, spec, root_dir, on_line=None):
        self.chamadas.append("run_once")
        if on_line is not None:
            await on_line("Update state (0x61) downloading, progress: 42.02")
        return self.exit_code, self.saida


class FakeSupervisor:
    def __init__(self, state: InstanceState = InstanceState.STOPPED) -> None:
        self._state = state

    def state(self, instance_id: str) -> InstanceState:
        return self._state


class FakeBackups:
    def __init__(self, chamadas: list[str], falha: bool = False) -> None:
        self.chamadas = chamadas
        self.falha = falha

    async def create(self, instance, kind=None, note: str = ""):
        self.chamadas.append("backup")
        if self.falha:
            raise OSError("disco cheio")
        return type("Backup", (), {"file_name": "backup-antes.zip"})()


def _instancia(tmp_path: Path) -> Instance:
    return Instance.new("7DTD", "sevendays", str(tmp_path), runtime="docker")


def _servico(chamadas, *, instalado="", exit_code=0, state=InstanceState.STOPPED):
    provider = FakeProvider(chamadas, instalado=instalado)
    return InstallService(
        FakeRuntime(chamadas, exit_code=exit_code),
        FakeRegistry(provider),
        FakeSupervisor(state),
        EventBus(),
    )


def test_atualizacao_faz_backup_antes_de_tocar_nos_arquivos(tmp_path):
    """A ordem não é negociável: backup, depois instalação. Invertida, um
    download que corrompe a instalação deixa o usuário sem rede de segurança."""

    async def caso():
        chamadas: list[str] = []
        svc = _servico(chamadas, instalado="23906567")
        backups = FakeBackups(chamadas)

        await svc.install(_instancia(tmp_path), "v3.0.1", backup_service=backups)

        assert chamadas == ["backup", "run_once", "after_install"]

    asyncio.run(caso())


def test_backup_que_falha_cancela_a_atualizacao(tmp_path):
    """Sem backup não se atualiza. Melhor não atualizar do que atualizar sem
    poder voltar atrás."""

    async def caso():
        chamadas: list[str] = []
        svc = _servico(chamadas, instalado="23906567")
        backups = FakeBackups(chamadas, falha=True)

        with pytest.raises(ValidationFailedError, match="backup"):
            await svc.install(_instancia(tmp_path), "v3.0.1", backup_service=backups)

        assert "run_once" not in chamadas  # nada foi baixado

    asyncio.run(caso())


def test_primeira_instalacao_nao_exige_backup(tmp_path):
    """Instância nova está vazia: exigir backup do nada só cria atrito."""

    async def caso():
        chamadas: list[str] = []
        svc = _servico(chamadas, instalado="")
        await svc.install(_instancia(tmp_path), "public", backup_service=FakeBackups(chamadas))

        assert chamadas == ["run_once", "after_install"]

    asyncio.run(caso())


def test_servidor_rodando_recusa_instalacao(tmp_path):
    async def caso():
        chamadas: list[str] = []
        svc = _servico(chamadas, instalado="1", state=InstanceState.RUNNING)

        with pytest.raises(ConflictError, match="pare o servidor"):
            await svc.install(_instancia(tmp_path), "public", backup_service=FakeBackups(chamadas))

        assert chamadas == []

    asyncio.run(caso())


def test_instalacao_que_falha_nao_prepara_config(tmp_path):
    """Código de saída diferente de zero significa instalação incompleta:
    preparar a config em cima disso mascararia o problema."""

    async def caso():
        chamadas: list[str] = []
        svc = _servico(chamadas, exit_code=8)

        with pytest.raises(ValidationFailedError, match="código 8"):
            await svc.install(_instancia(tmp_path), "public")

        assert "after_install" not in chamadas

    asyncio.run(caso())


def test_progresso_do_download_chega_ao_console(tmp_path):
    async def caso():
        chamadas: list[str] = []
        bus = EventBus()
        provider = FakeProvider(chamadas)
        svc = InstallService(FakeRuntime(chamadas), FakeRegistry(provider), FakeSupervisor(), bus)

        instance = _instancia(tmp_path)
        recebidas: list[str] = []
        bus.subscribe(
            f"instance.{instance.id}.console",
            lambda topic, payload: recebidas.append(payload["line"]),
        )

        await svc.install(instance, "public")

        assert any("downloading" in linha for linha in recebidas)
        assert any("instalação concluída" in linha for linha in recebidas)

    asyncio.run(caso())


def test_start_devolve_na_hora_e_instala_em_segundo_plano(tmp_path):
    """Baixar 17 GB não cabe numa request HTTP: ela morreria de timeout e o
    usuário não veria progresso nenhum."""

    async def caso():
        chamadas: list[str] = []
        guardados: list[dict] = []

        async def persistir(_instance_id: str, resultado: dict) -> None:
            guardados.append(resultado)

        provider = FakeProvider(chamadas)
        svc = InstallService(
            FakeRuntime(chamadas),
            FakeRegistry(provider),
            FakeSupervisor(),
            EventBus(),
            persistir=persistir,
        )

        instance = _instancia(tmp_path)
        await svc.start(instance, "public")
        assert svc.rodando(instance.id) is True

        # Deixa a tarefa de fundo terminar.
        await asyncio.sleep(0.05)
        assert chamadas == ["run_once", "after_install"]
        assert svc.rodando(instance.id) is False
        assert guardados and guardados[0]["version"] == "public"

    asyncio.run(caso())


def test_start_recusa_segunda_instalacao_simultanea(tmp_path):
    async def caso():
        chamadas: list[str] = []
        svc = _servico(chamadas)
        instance = _instancia(tmp_path)

        await svc.start(instance, "public")
        with pytest.raises(ConflictError, match="já existe"):
            await svc.start(instance, "v2.6")

        await asyncio.sleep(0.05)

    asyncio.run(caso())


def test_origem_fora_do_ar_devolve_lista_vazia():
    """A tela de criação precisa abrir mesmo sem a Steam responder."""

    async def caso():
        chamadas: list[str] = []
        provider = FakeProvider(chamadas)

        class RuntimeQuebrado(FakeRuntime):
            async def run_once(self, spec, root_dir, on_line=None):
                raise OSError("sem rede")

        svc = InstallService(
            RuntimeQuebrado(chamadas), FakeRegistry(provider), FakeSupervisor(), EventBus()
        )
        assert await svc.versions("sevendays") == []

    asyncio.run(caso())
