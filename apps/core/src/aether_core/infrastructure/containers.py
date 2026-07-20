"""Runtime Docker: containers de instância supervisionados pelo Core.

Duas peças com papéis distintos:

- :class:`AiodockerRuntime` — a única classe que fala o dialeto do Docker
  (implementa a porta ``ContainerRuntime``);
- :class:`DockerContainerSupervisor` — o par containerizado do
  ``LocalProcessSupervisor``: mesmo protocolo, mesmos tópicos de evento
  (``instance.{id}.console`` / ``.state``), então console, WebSocket e
  dashboard não distinguem processo de container.

Diferença essencial: container sobrevive ao restart do Core. Por isso todo
container recebe o label ``aether.instance`` e o supervisor readota os que
encontrar rodando no startup (:meth:`DockerContainerSupervisor.reconcile`).
"""

import asyncio
import contextlib
import logging
import os
from collections import deque
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path

from aether_sdk import ConsoleCodec, ContainerSpec

from aether_core.application.events import EventBus
from aether_core.application.ports import (
    ContainerLaunch,
    ContainerStats,
    ImageInfo,
    ManagedContainer,
)
from aether_core.domain.errors import ConflictError, ValidationFailedError
from aether_core.domain.instances import InstanceState

log = logging.getLogger(__name__)

INSTANCE_LABEL = "aether.instance"
HISTORY_LINES = 1000
STOP_GRACE_SECONDS = 30


def _dono_dos_volumes(spec: ContainerSpec, root_dir: Path) -> None:
    """Passa os volumes da instância para o uid que roda dentro do container.

    Recursivo só na criação (a árvore está vazia ou pequena); depois disso os
    arquivos já nascem com o dono certo, escritos pelo próprio servidor.
    """
    uid_gid = spec.run_as.split(":")
    uid = int(uid_gid[0])
    gid = int(uid_gid[1]) if len(uid_gid) > 1 else uid
    for volume in spec.volumes:
        alvo = (root_dir / volume.subdir).resolve()
        if not alvo.is_dir():
            continue
        with contextlib.suppress(OSError):
            os.chown(alvo, uid, gid)
            for caminho in alvo.rglob("*"):
                os.chown(caminho, uid, gid)


class AiodockerRuntime:
    """Implementação da porta ``ContainerRuntime`` sobre a API do Docker."""

    def __init__(self) -> None:
        # Conexão preguiçosa: o Core precisa subir normalmente numa máquina
        # sem Docker — só o uso do runtime docker exige a engine.
        self._docker = None

    async def _client(self):
        if self._docker is None:
            import aiodocker

            self._docker = aiodocker.Docker()
        return self._docker

    async def ensure_available(self) -> None:
        try:
            docker = await self._client()
            await docker.version()
        except Exception as exc:  # noqa: BLE001 - qualquer falha vira o mesmo aviso
            raise ValidationFailedError(
                "Docker indisponível nesta máquina — instale/inicie o Docker "
                f"para usar instâncias containerizadas ({exc})"
            ) from exc

    async def close(self) -> None:
        if self._docker is not None:
            await self._docker.close()
            self._docker = None

    # ------------------------------------------------------------ containers --
    async def create(
        self, name: str, labels: dict[str, str], spec: ContainerSpec, root_dir: Path
    ) -> str:
        docker = await self._client()
        exposed: dict[str, dict] = {}
        bindings: dict[str, list[dict]] = {}
        for p in spec.ports:
            key = f"{p.container_port}/{p.protocol}"
            exposed[key] = {}
            # Sem host_port o provider quer a mesma porta fora e dentro:
            # previsível para port-forward manual, diferente do aleatório do Docker.
            bindings[key] = [{"HostPort": str(p.host_port or p.container_port)}]

        binds = [
            f"{(root_dir / v.subdir).resolve().as_posix()}:{v.container_path}" for v in spec.volumes
        ]

        config = {
            "Image": spec.image,
            "Env": [f"{k}={v}" for k, v in spec.env.items()],
            "OpenStdin": True,  # send_command escreve no stdin do servidor
            "Tty": False,
            "StopSignal": spec.stop_signal,
            "Labels": labels,
            "ExposedPorts": exposed,
            "HostConfig": {"Binds": binds, "PortBindings": bindings},
        }
        if spec.command:
            config["Cmd"] = spec.command
        if spec.run_as:
            config["User"] = spec.run_as
            # O diretório da instância nasce do Core (root); sem ajustar o dono
            # o servidor sobe sem poder escrever no próprio volume.
            _dono_dos_volumes(spec, root_dir)

        container = await docker.containers.create_or_replace(name=name, config=config)
        return container.id

    async def start(self, container_id: str) -> None:
        docker = await self._client()
        await (await docker.containers.get(container_id)).start()

    async def stop(self, container_id: str, timeout: int) -> None:
        docker = await self._client()
        await (await docker.containers.get(container_id)).stop(t=timeout)

    async def kill(self, container_id: str) -> None:
        docker = await self._client()
        await (await docker.containers.get(container_id)).kill()

    async def write_stdin(self, container_id: str, data: str) -> None:
        docker = await self._client()
        container = await docker.containers.get(container_id)
        async with container.attach(stdin=True, stdout=False, stderr=False) as stream:
            await stream.write_in(data.encode())

    async def stream_logs(self, container_id: str) -> AsyncIterator[str]:
        docker = await self._client()
        container = await docker.containers.get(container_id)
        async for chunk in container.log(stdout=True, stderr=True, follow=True):
            yield chunk

    async def wait(self, container_id: str) -> int:
        docker = await self._client()
        result = await (await docker.containers.get(container_id)).wait()
        return int(result.get("StatusCode", -1))

    async def list_managed(self) -> list[ManagedContainer]:
        docker = await self._client()
        containers = await docker.containers.list(all=True, filters={"label": [INSTANCE_LABEL]})
        managed = []
        for c in containers:
            info = c._container  # payload da listagem; evita um inspect por container
            managed.append(
                ManagedContainer(
                    container_id=c.id,
                    instance_id=info.get("Labels", {}).get(INSTANCE_LABEL, ""),
                    running=info.get("State") == "running",
                )
            )
        return managed

    async def stats(self, container_id: str) -> ContainerStats | None:
        docker = await self._client()
        container = await docker.containers.get(container_id)
        raw = await container.stats(stream=False)
        data = raw[0] if isinstance(raw, list) else raw
        try:
            cpu = data["cpu_stats"]
            pre = data["precpu_stats"]
            cpu_delta = cpu["cpu_usage"]["total_usage"] - pre["cpu_usage"]["total_usage"]
            sys_delta = cpu["system_cpu_usage"] - pre.get("system_cpu_usage", 0)
            ncpus = cpu.get("online_cpus") or len(cpu["cpu_usage"].get("percpu_usage") or [1])
            percent = (cpu_delta / sys_delta) * ncpus * 100.0 if sys_delta > 0 else 0.0
            mem = data.get("memory_stats", {})
            return ContainerStats(
                cpu_percent=round(percent, 1),
                memory_bytes=int(mem.get("usage", 0)),
                memory_limit_bytes=int(mem.get("limit", 0)),
            )
        except (KeyError, TypeError, ZeroDivisionError):
            # Container recém-criado ainda não tem duas amostras de CPU.
            return None

    # -------------------------------------------------------------- imagens --
    async def list_images(self) -> list[ImageInfo]:
        docker = await self._client()
        images = await docker.images.list()
        return [
            ImageInfo(
                id=img.get("Id", ""),
                tags=[t for t in (img.get("RepoTags") or []) if t != "<none>:<none>"],
                size_bytes=int(img.get("Size", 0)),
            )
            for img in images
        ]

    async def has_image(self, ref: str) -> bool:
        docker = await self._client()
        try:
            await docker.images.inspect(ref)
            return True
        except Exception:  # noqa: BLE001 - 404 da engine = não tem
            return False

    async def pull_image(self, ref: str) -> AsyncIterator[dict]:
        docker = await self._client()
        name, _, tag = ref.partition(":")
        async for event in docker.images.pull(from_image=name, tag=tag or "latest", stream=True):
            yield event

    async def remove_image(self, ref: str) -> None:
        docker = await self._client()
        await docker.images.delete(ref)


@dataclass
class _RunningContainer:
    container_id: str
    spec: ContainerSpec | None
    state: InstanceState = InstanceState.STARTING
    logs: deque[str] = field(default_factory=lambda: deque(maxlen=HISTORY_LINES))
    stop_requested: bool = False
    reader: asyncio.Task | None = None


class DockerContainerSupervisor:
    """Supervisor de instâncias containerizadas (protocolo ``ProcessSupervisor``).

    ``start`` recria o container do zero a cada subida: o estado durável da
    instância mora nos volumes, então recriar garante que mudanças de spec
    (imagem, env, portas) sempre valem na próxima partida.
    """

    def __init__(self, runtime, bus: EventBus) -> None:
        self._runtime = runtime
        self._bus = bus
        self._containers: dict[str, _RunningContainer] = {}

    @staticmethod
    def container_name(instance_id: str) -> str:
        return f"aether-{instance_id}"

    # -------------------------------------------------------------- queries --
    def tracks(self, instance_id: str) -> bool:
        """O hub usa isto para saber a quem uma instância pertence."""
        return instance_id in self._containers

    def state(self, instance_id: str) -> InstanceState:
        rc = self._containers.get(instance_id)
        return rc.state if rc else InstanceState.STOPPED

    def container_id_of(self, instance_id: str) -> str | None:
        rc = self._containers.get(instance_id)
        if rc and rc.state in (InstanceState.STARTING, InstanceState.RUNNING):
            return rc.container_id
        return None

    def logs(self, instance_id: str, tail: int = 200) -> list[str]:
        rc = self._containers.get(instance_id)
        if not rc:
            return []
        lines = list(rc.logs)
        return lines[-tail:] if tail > 0 else lines

    # ------------------------------------------------------------- commands --
    async def start(
        self, instance_id: str, launch: ContainerLaunch, codec: ConsoleCodec | None
    ) -> None:
        """Coloca a instância em STARTING e faz o resto em segundo plano.

        Baixar a imagem pode levar minutos; prender a request HTTP nisso a
        faria estourar por timeout e o usuário não veria progresso nenhum. O
        boot roda como task e conversa pelo console, como o servidor faria.
        """
        current = self.state(instance_id)
        if current in (InstanceState.STARTING, InstanceState.RUNNING, InstanceState.STOPPING):
            raise ConflictError(f"instance is already {current}")
        await self._runtime.ensure_available()

        rc = _RunningContainer(container_id="", spec=launch.spec)
        self._containers[instance_id] = rc
        await self._set_state(instance_id, rc, InstanceState.STARTING)
        rc.reader = asyncio.create_task(self._boot(instance_id, rc, launch, codec))

    async def _boot(
        self,
        instance_id: str,
        rc: _RunningContainer,
        launch: ContainerLaunch,
        codec: ConsoleCodec | None,
    ) -> None:
        try:
            await self._ensure_image(instance_id, rc, launch.spec.image)
            rc.container_id = await self._runtime.create(
                name=self.container_name(instance_id),
                labels={INSTANCE_LABEL: instance_id},
                spec=launch.spec,
                root_dir=Path(launch.root_dir),
            )
            await self._runtime.start(rc.container_id)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - a falha vira console + CRASHED
            log.warning("boot da instância %s falhou: %s", instance_id, exc)
            await self._console(instance_id, rc, f"[aether] falha ao iniciar: {exc}", "ERROR")
            await self._set_state(instance_id, rc, InstanceState.CRASHED, exit_code=-1)
            return
        await self._read_output(instance_id, rc, codec)

    async def _ensure_image(self, instance_id: str, rc: _RunningContainer, image: str) -> None:
        """Garante a imagem no disco antes de criar o container.

        O ``create`` da engine falha com 404 em vez de baixar; sem isto o
        primeiro start de toda instância nova morria com "No such image".
        """
        if await self._runtime.has_image(image):
            return
        await self._console(instance_id, rc, f"[aether] baixando a imagem {image}…")
        ultimo = ""
        async for evento in self._runtime.pull_image(image):
            status = str(evento.get("status") or "")
            # Só as mudanças de fase: o progresso por camada são milhares de
            # eventos e inundaria o console.
            if status and status != ultimo and "Downloading" not in status:
                ultimo = status
                await self._console(instance_id, rc, f"[aether] {status}")
        await self._console(instance_id, rc, f"[aether] imagem {image} pronta.")

    async def _console(
        self, instance_id: str, rc: _RunningContainer, linha: str, level: str = "INFO"
    ) -> None:
        rc.logs.append(linha)
        await self._bus.publish(
            f"instance.{instance_id}.console", {"line": linha, "level": level, "ready": False}
        )

    async def stop(self, instance_id: str) -> None:
        rc = self._containers.get(instance_id)
        if not rc or rc.state in (InstanceState.STOPPED, InstanceState.CRASHED):
            raise ConflictError("instance is not running")
        rc.stop_requested = True
        await self._set_state(instance_id, rc, InstanceState.STOPPING)

        # Ainda sem container: o boot está baixando a imagem. Cancelar a task
        # é a única forma de parar — não há processo a quem mandar sinal.
        if not rc.container_id:
            await self._cancelar_boot(rc)
            await self._console(instance_id, rc, "[aether] início cancelado.")
            await self._set_state(instance_id, rc, InstanceState.STOPPED, exit_code=0)
            return

        if rc.spec and rc.spec.stop_command:
            with contextlib.suppress(Exception):
                await self._runtime.write_stdin(rc.container_id, rc.spec.stop_command + "\n")
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._runtime.wait(rc.container_id), STOP_GRACE_SECONDS)

        # `docker stop`: manda o StopSignal do container e mata após o timeout —
        # cobre tanto o caso sem stop_command quanto o servidor que o ignorou.
        with contextlib.suppress(Exception):
            await self._runtime.stop(rc.container_id, timeout=STOP_GRACE_SECONDS)

    async def kill(self, instance_id: str) -> None:
        rc = self._containers.get(instance_id)
        if not rc or rc.state in (InstanceState.STOPPED, InstanceState.CRASHED):
            raise ConflictError("instance is not running")
        rc.stop_requested = True
        if not rc.container_id:
            await self._cancelar_boot(rc)
            await self._set_state(instance_id, rc, InstanceState.STOPPED, exit_code=0)
            return
        with contextlib.suppress(Exception):
            await self._runtime.kill(rc.container_id)

    @staticmethod
    async def _cancelar_boot(rc: _RunningContainer) -> None:
        if rc.reader:
            rc.reader.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await rc.reader
            rc.reader = None

    async def restart(
        self, instance_id: str, launch: ContainerLaunch, codec: ConsoleCodec | None
    ) -> None:
        if self.state(instance_id) not in (InstanceState.STOPPED, InstanceState.CRASHED):
            await self.stop(instance_id)
            rc = self._containers.get(instance_id)
            if rc and rc.reader:
                await rc.reader
        await self.start(instance_id, launch, codec)

    async def send_command(self, instance_id: str, command: str) -> None:
        rc = self._containers.get(instance_id)
        if not rc or rc.state not in (InstanceState.STARTING, InstanceState.RUNNING):
            raise ConflictError("instance is not running")
        if not rc.container_id:
            raise ConflictError("the server is still starting up")
        await self._runtime.write_stdin(rc.container_id, command + "\n")
        rc.logs.append(f"> {command}")
        await self._bus.publish(
            f"instance.{instance_id}.console",
            {"line": f"> {command}", "level": "CMD", "ready": False},
        )

    async def reconcile(self, codecs: dict[str, ConsoleCodec | None]) -> None:
        """Readota containers que sobreviveram a um restart do Core.

        ``codecs`` mapeia instance_id → codec do provider da instância; um
        container rodando sem instância conhecida fica intocado (pode ser de
        outro Core apontando para a mesma engine).
        """
        try:
            managed = await self._runtime.list_managed()
        except Exception:  # noqa: BLE001 - sem Docker não há o que readotar
            return
        for mc in managed:
            if not mc.running or mc.instance_id not in codecs:
                continue
            rc = _RunningContainer(
                container_id=mc.container_id,
                spec=None,  # spec original se foi com o Core; stop cai no `docker stop`
                state=InstanceState.RUNNING,
            )
            self._containers[mc.instance_id] = rc
            await self._set_state(mc.instance_id, rc, InstanceState.RUNNING)
            rc.reader = asyncio.create_task(
                self._read_output(mc.instance_id, rc, codecs[mc.instance_id])
            )
            log.info("readotado container %s da instância %s", mc.container_id, mc.instance_id)

    async def shutdown(self) -> None:
        """No desligamento do Core os containers ficam rodando de propósito:
        o jogo não precisa cair junto com o painel. Só paramos os leitores."""
        for rc in self._containers.values():
            if rc.reader:
                rc.reader.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await rc.reader

    # -------------------------------------------------------------- internal --
    async def _set_state(
        self, instance_id: str, rc: _RunningContainer, state: InstanceState, **extra
    ) -> None:
        rc.state = state
        await self._bus.publish(f"instance.{instance_id}.state", {"state": state, **extra})

    async def _read_output(
        self, instance_id: str, rc: _RunningContainer, codec: ConsoleCodec | None
    ) -> None:
        try:
            async for raw_chunk in self._runtime.stream_logs(rc.container_id):
                raw = raw_chunk.rstrip("\r\n")
                if not raw:
                    continue
                parsed = codec.parse(raw) if codec else None
                rc.logs.append(raw)
                await self._bus.publish(
                    f"instance.{instance_id}.console",
                    {
                        "line": raw,
                        "level": parsed.level if parsed else "",
                        "ready": bool(parsed and parsed.ready),
                    },
                )
                if parsed and parsed.ready and rc.state == InstanceState.STARTING:
                    await self._set_state(instance_id, rc, InstanceState.RUNNING)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.exception("leitor de console falhou para a instância %s", instance_id)
        code = -1
        with contextlib.suppress(Exception):
            code = await self._runtime.wait(rc.container_id)
        final = InstanceState.STOPPED if rc.stop_requested or code == 0 else InstanceState.CRASHED
        await self._set_state(instance_id, rc, final, exit_code=code)
