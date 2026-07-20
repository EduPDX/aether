"""Supervisor Docker sobre um runtime falso: ciclo de vida, console e readoção.

O projeto não usa pytest-asyncio; os casos assíncronos rodam via asyncio.run.
O FakeContainerRuntime implementa a porta ContainerRuntime em memória — os
testes exercitam exatamente o contrato que a implementação aiodocker cumpre.
"""

import asyncio
from pathlib import Path

from aether_core.application.events import EventBus
from aether_core.application.ports import ContainerLaunch, ContainerStats, ManagedContainer
from aether_core.domain.errors import ConflictError
from aether_core.domain.instances import InstanceState
from aether_core.infrastructure.containers import DockerContainerSupervisor
from aether_provider_minecraft.server.console import MinecraftConsoleCodec
from aether_sdk import ContainerSpec, PortMapping, VolumeMount

READY = '[00:00:01] [Server thread/INFO]: Done (1.2s)! For help, type "help"'


class FakeContainer:
    def __init__(self, name: str, labels: dict, spec: ContainerSpec, root_dir: Path) -> None:
        self.name = name
        self.labels = labels
        self.spec = spec
        self.root_dir = root_dir
        self.running = False
        self.exit_code: int = 0
        self.stdin: list[str] = []
        self._lines: asyncio.Queue[str | None] = asyncio.Queue()

    def emit(self, line: str) -> None:
        self._lines.put_nowait(line)

    def finish(self, code: int) -> None:
        self.exit_code = code
        self.running = False
        self._lines.put_nowait(None)  # encerra o stream de logs


class FakeContainerRuntime:
    def __init__(self, imagens: set[str] | None = None) -> None:
        self.containers: dict[str, FakeContainer] = {}
        self._seq = 0
        # Por padrão a imagem já está no disco; os testes de pull começam vazios.
        self.imagens = {"itzg/minecraft-server"} if imagens is None else imagens
        self.pulls: list[str] = []

    async def ensure_available(self) -> None:
        pass

    async def create(self, name, labels, spec, root_dir) -> str:
        # Espelha a engine real: create não baixa imagem, ele falha com 404.
        if spec.image not in self.imagens:
            raise RuntimeError(f"[404] No such image: {spec.image}:latest")
        self._seq += 1
        cid = f"cid-{self._seq}"
        self.containers[cid] = FakeContainer(name, labels, spec, root_dir)
        return cid

    async def start(self, container_id) -> None:
        self.containers[container_id].running = True

    async def stop(self, container_id, timeout) -> None:
        c = self.containers[container_id]
        if c.running:
            c.finish(0)

    async def kill(self, container_id) -> None:
        c = self.containers[container_id]
        if c.running:
            c.finish(137)

    async def write_stdin(self, container_id, data) -> None:
        self.containers[container_id].stdin.append(data)

    async def stream_logs(self, container_id):
        c = self.containers[container_id]
        while True:
            line = await c._lines.get()
            if line is None:
                return
            yield line

    async def wait(self, container_id) -> int:
        c = self.containers[container_id]
        while c.running:
            await asyncio.sleep(0.005)
        return c.exit_code

    async def list_managed(self):
        return [
            ManagedContainer(cid, c.labels.get("aether.instance", ""), c.running)
            for cid, c in self.containers.items()
        ]

    async def stats(self, container_id):
        return ContainerStats(cpu_percent=50.0, memory_bytes=1024, memory_limit_bytes=4096)

    async def list_images(self):
        return []

    async def has_image(self, ref) -> bool:
        return ref in self.imagens

    async def pull_image(self, ref):
        self.pulls.append(ref)
        yield {"status": "Pulling from library"}
        yield {"status": "Downloading", "progress": "50%"}
        yield {"status": "Pull complete"}
        self.imagens.add(ref)

    async def remove_image(self, ref) -> None:
        pass


def spec(stop_command: str | None = "stop") -> ContainerSpec:
    return ContainerSpec(
        image="itzg/minecraft-server",
        env={"EULA": "TRUE"},
        ports=[PortMapping(container_port=25565, host_port=25565)],
        volumes=[VolumeMount(container_path="/data", subdir=".")],
        stop_command=stop_command,
    )


def launch(tmp_path: Path, stop_command: str | None = "stop") -> ContainerLaunch:
    return ContainerLaunch(spec=spec(stop_command), root_dir=tmp_path)


async def wait_for(condition, timeout: float = 2.0) -> None:
    async with asyncio.timeout(timeout):
        while not condition():
            await asyncio.sleep(0.005)


def test_start_fica_running_na_linha_de_ready(tmp_path):
    async def caso():
        runtime = FakeContainerRuntime()
        sup = DockerContainerSupervisor(runtime, EventBus())
        await sup.start("i1", launch(tmp_path), MinecraftConsoleCodec())
        assert sup.state("i1") is InstanceState.STARTING

        await wait_for(lambda: "cid-1" in runtime.containers)
        runtime.containers["cid-1"].emit(READY)
        await wait_for(lambda: sup.state("i1") is InstanceState.RUNNING)
        assert sup.logs("i1") == [READY]
        assert sup.container_id_of("i1") == "cid-1"
        # Imagem já estava no disco: nada de pull.
        assert runtime.pulls == []

    asyncio.run(caso())


def test_stop_gracioso_escreve_stop_no_stdin(tmp_path):
    async def caso():
        runtime = FakeContainerRuntime()
        sup = DockerContainerSupervisor(runtime, EventBus())
        await sup.start("i1", launch(tmp_path), None)
        await wait_for(lambda: "cid-1" in runtime.containers)

        # O servidor obedece o comando: encerra sozinho com código 0.
        async def obedecer():
            await wait_for(lambda: runtime.containers["cid-1"].stdin)
            runtime.containers["cid-1"].finish(0)

        tarefa = asyncio.create_task(obedecer())
        await sup.stop("i1")
        await tarefa
        assert runtime.containers["cid-1"].stdin == ["stop\n"]
        await wait_for(lambda: sup.state("i1") is InstanceState.STOPPED)

    asyncio.run(caso())


def test_saida_inesperada_vira_crashed(tmp_path):
    async def caso():
        runtime = FakeContainerRuntime()
        sup = DockerContainerSupervisor(runtime, EventBus())
        await sup.start("i1", launch(tmp_path), None)
        await wait_for(lambda: "cid-1" in runtime.containers)
        runtime.containers["cid-1"].finish(3)
        await wait_for(lambda: sup.state("i1") is InstanceState.CRASHED)

    asyncio.run(caso())


def test_start_duplicado_conflita(tmp_path):
    async def caso():
        runtime = FakeContainerRuntime()
        sup = DockerContainerSupervisor(runtime, EventBus())
        await sup.start("i1", launch(tmp_path), None)
        try:
            await sup.start("i1", launch(tmp_path), None)
            raise AssertionError("segunda partida deveria conflitar")
        except ConflictError:
            pass

    asyncio.run(caso())


def test_imagem_ausente_e_baixada_antes_de_criar(tmp_path):
    """O create da engine não baixa imagem — ele falha com 404 "No such image".

    Sem o pull automático, o primeiro start de toda instância nova morria e o
    usuário tinha que descobrir sozinho a tela de imagens.
    """

    async def caso():
        runtime = FakeContainerRuntime(imagens=set())
        sup = DockerContainerSupervisor(runtime, EventBus())
        await sup.start("i1", launch(tmp_path), MinecraftConsoleCodec())

        await wait_for(lambda: "cid-1" in runtime.containers, timeout=3.0)
        runtime.containers["cid-1"].emit(READY)
        await wait_for(lambda: sup.state("i1") is InstanceState.RUNNING, timeout=3.0)

        assert runtime.pulls == ["itzg/minecraft-server"]
        # O progresso aparece no console para o usuário entender a demora.
        console = "\n".join(sup.logs("i1"))
        assert "baixando a imagem itzg/minecraft-server" in console
        assert "pronta" in console

    asyncio.run(caso())


def test_falha_no_boot_vira_crashed_com_motivo_no_console(tmp_path):
    """Imagem inexistente no registry: o erro precisa chegar ao usuário, não
    sumir num traceback do servidor."""

    async def caso():
        runtime = FakeContainerRuntime(imagens=set())

        async def pull_quebrado(ref):
            raise RuntimeError("manifest unknown")
            yield  # pragma: no cover - torna a função um gerador assíncrono

        runtime.pull_image = pull_quebrado
        sup = DockerContainerSupervisor(runtime, EventBus())
        await sup.start("i1", launch(tmp_path), None)

        await wait_for(lambda: sup.state("i1") is InstanceState.CRASHED, timeout=3.0)
        assert "manifest unknown" in "\n".join(sup.logs("i1"))

    asyncio.run(caso())


def test_parar_durante_o_download_cancela_o_boot(tmp_path):
    """Sem container ainda não há sinal a mandar: parar precisa cancelar a task."""

    async def caso():
        runtime = FakeContainerRuntime(imagens=set())

        async def pull_lento(ref):
            await asyncio.sleep(30)
            yield {"status": "nunca chega"}  # pragma: no cover

        runtime.pull_image = pull_lento
        sup = DockerContainerSupervisor(runtime, EventBus())
        await sup.start("i1", launch(tmp_path), None)
        await asyncio.sleep(0.05)
        assert sup.state("i1") is InstanceState.STARTING

        await sup.stop("i1")
        assert sup.state("i1") is InstanceState.STOPPED
        assert runtime.containers == {}

    asyncio.run(caso())


def test_run_as_ajusta_o_dono_do_volume(tmp_path, monkeypatch):
    """Com run_as, o volume precisa passar para o uid do container.

    A raiz da instância nasce do Core (root); sem o chown o servidor sobe sem
    conseguir escrever no próprio volume — falha silenciosa e confusa.
    """
    from aether_core.infrastructure import containers as mod

    chowns: list[tuple[str, int, int]] = []
    monkeypatch.setattr(mod.os, "chown", lambda p, uid, gid: chowns.append((str(p), uid, gid)))

    (tmp_path / "UserData").mkdir()
    spec = ContainerSpec(
        image="cm2network/steamcmd:root",
        volumes=[VolumeMount(container_path="/data", subdir=".")],
        run_as="1000:1000",
    )
    mod._dono_dos_volumes(spec, tmp_path)

    alvos = {c[0] for c in chowns}
    assert str(tmp_path.resolve()) in alvos
    assert str((tmp_path / "UserData").resolve()) in alvos
    assert all(c[1:] == (1000, 1000) for c in chowns)


def test_reconcile_readota_container_vivo(tmp_path):
    """Containers sobrevivem ao restart do Core; o supervisor novo precisa
    readotá-los para estado e console voltarem sem reiniciar o jogo."""

    async def caso():
        runtime = FakeContainerRuntime()
        cid = await runtime.create("aether-i1", {"aether.instance": "i1"}, spec(), tmp_path)
        await runtime.start(cid)

        sup = DockerContainerSupervisor(runtime, EventBus())
        assert sup.state("i1") is InstanceState.STOPPED
        await sup.reconcile({"i1": MinecraftConsoleCodec()})
        assert sup.state("i1") is InstanceState.RUNNING
        assert sup.tracks("i1")

        runtime.containers[cid].emit(READY)
        await wait_for(lambda: sup.logs("i1") == [READY])

    asyncio.run(caso())


def test_reconcile_ignora_container_de_instancia_desconhecida(tmp_path):
    async def caso():
        runtime = FakeContainerRuntime()
        cid = await runtime.create("aether-x", {"aether.instance": "x"}, spec(), tmp_path)
        await runtime.start(cid)
        sup = DockerContainerSupervisor(runtime, EventBus())
        await sup.reconcile({"i1": None})
        assert not sup.tracks("x")

    asyncio.run(caso())
