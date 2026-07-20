"""Power use cases: start/stop/restart/kill and console interaction.

O serviço não sabe *como* um servidor roda: ele resolve o spec pelo contrato
do provider (``SupportsLaunch`` ou ``SupportsContainer``) e despacha para o
supervisor do runtime da instância. Adicionar um runtime novo é registrar
mais um supervisor — nada aqui muda.
"""

from pathlib import Path
from typing import Any, Protocol

from aether_sdk import (
    ConsoleCodec,
    LaunchContext,
    SupportsContainer,
    SupportsInstall,
    SupportsLaunch,
)

from aether_core.application.ports import ContainerLaunch, ProviderRegistry
from aether_core.application.ports_config import aplicar_portas
from aether_core.domain.errors import ValidationFailedError
from aether_core.domain.instances import Instance, InstanceRuntime, InstanceState


class ProcessSupervisor(Protocol):
    """Supervisor de um runtime; o tipo do spec depende do runtime
    (``LaunchSpec`` para processo, ``ContainerLaunch`` para container)."""

    def state(self, instance_id: str) -> InstanceState: ...

    def logs(self, instance_id: str, tail: int = 200) -> list[str]: ...

    async def start(self, instance_id: str, spec: Any, codec: ConsoleCodec | None) -> None: ...

    async def stop(self, instance_id: str) -> None: ...

    async def kill(self, instance_id: str) -> None: ...

    async def restart(self, instance_id: str, spec: Any, codec: ConsoleCodec | None) -> None: ...

    async def send_command(self, instance_id: str, command: str) -> None: ...


class SupervisorHub:
    """Fachada única para quem só tem o ``instance_id`` na mão.

    Backups, tarefas agendadas e rotas de leitura consultam estado e mandam
    comandos sem saber o runtime da instância; o hub encaminha para o
    supervisor que a estiver rastreando (container primeiro — o processo
    local responde ``STOPPED`` para qualquer id desconhecido).
    """

    def __init__(self, process: ProcessSupervisor, docker: ProcessSupervisor | None) -> None:
        self._process = process
        self._docker = docker

    def _owner(self, instance_id: str) -> ProcessSupervisor:
        if self._docker is not None and getattr(self._docker, "tracks", lambda _: False)(
            instance_id
        ):
            return self._docker
        return self._process

    def state(self, instance_id: str) -> InstanceState:
        return self._owner(instance_id).state(instance_id)

    def logs(self, instance_id: str, tail: int = 200) -> list[str]:
        return self._owner(instance_id).logs(instance_id, tail)

    async def send_command(self, instance_id: str, command: str) -> None:
        await self._owner(instance_id).send_command(instance_id, command)

    def pid_of(self, instance_id: str) -> int | None:
        pid_of = getattr(self._owner(instance_id), "pid_of", None)
        return pid_of(instance_id) if pid_of else None

    def container_id_of(self, instance_id: str) -> str | None:
        if self._docker is None:
            return None
        return self._docker.container_id_of(instance_id)

    async def shutdown(self) -> None:
        await self._process.shutdown()
        if self._docker is not None:
            await self._docker.shutdown()


class PowerService:
    def __init__(
        self, providers: ProviderRegistry, supervisors: dict[str, ProcessSupervisor]
    ) -> None:
        self._providers = providers
        self._supervisors = supervisors

    def _supervisor(self, instance: Instance) -> ProcessSupervisor:
        supervisor = self._supervisors.get(instance.runtime)
        if supervisor is None:
            raise ValidationFailedError(f"unknown runtime {instance.runtime!r}")
        return supervisor

    def _launch(self, instance: Instance) -> tuple[Any, ConsoleCodec]:
        provider = self._providers.get(instance.provider_id)
        ctx = LaunchContext(root_dir=Path(instance.root_dir), provider_data=instance.provider_data)

        if instance.runtime == InstanceRuntime.DOCKER:
            if not isinstance(provider, SupportsContainer):
                raise ValidationFailedError(
                    f"provider {instance.provider_id!r} does not support containers"
                )
            container = provider.container_spec(ctx)
            if container is None:
                raise ValidationFailedError(self._porque_sem_container(instance, provider))
            container = aplicar_portas(container, instance.provider_data)
            return (
                ContainerLaunch(spec=container, root_dir=Path(instance.root_dir)),
                provider.console_codec(),
            )

        if not isinstance(provider, SupportsLaunch):
            raise ValidationFailedError(
                f"provider {instance.provider_id!r} does not support server processes"
            )
        spec = provider.launch_spec(ctx)
        if spec is None:
            raise ValidationFailedError(
                "no runnable server found in the instance directory "
                "(expected run script, server jar or provider_data.command)"
            )
        return spec, provider.console_codec()

    @staticmethod
    def _porque_sem_container(instance: Instance, provider: Any) -> str:
        """O provider devolveu ``None``; a interface precisa de um porquê.

        O caso comum de longe é servidor sem os arquivos do jogo — instalação
        que nunca rodou, foi interrompida ou falhou. Dizer 'não consegui montar
        o container' manda o usuário procurar defeito no lugar errado.
        """
        if isinstance(provider, SupportsInstall) and not provider.installed_version(
            Path(instance.root_dir)
        ):
            erro = (instance.provider_data.get("install") or {}).get("error")
            if erro:
                return f"os arquivos do servidor não foram instalados: {erro}"
            return (
                "os arquivos do servidor ainda não foram instalados. "
                "Instale a versão do servidor antes de iniciar."
            )
        return (
            f"o provider {instance.provider_id!r} não conseguiu montar um container "
            f"para esta instância"
        )

    async def start(self, instance: Instance) -> InstanceState:
        spec, codec = self._launch(instance)
        supervisor = self._supervisor(instance)
        await supervisor.start(instance.id, spec, codec)
        return supervisor.state(instance.id)

    async def stop(self, instance: Instance) -> InstanceState:
        supervisor = self._supervisor(instance)
        await supervisor.stop(instance.id)
        return supervisor.state(instance.id)

    async def restart(self, instance: Instance) -> InstanceState:
        spec, codec = self._launch(instance)
        supervisor = self._supervisor(instance)
        await supervisor.restart(instance.id, spec, codec)
        return supervisor.state(instance.id)

    async def kill(self, instance: Instance) -> InstanceState:
        supervisor = self._supervisor(instance)
        await supervisor.kill(instance.id)
        return supervisor.state(instance.id)

    def state(self, instance: Instance) -> InstanceState:
        return self._supervisor(instance).state(instance.id)

    def logs(self, instance: Instance, tail: int) -> list[str]:
        return self._supervisor(instance).logs(instance.id, tail)

    async def send_command(self, instance: Instance, command: str) -> None:
        command = command.strip()
        if not command:
            raise ValidationFailedError("empty command")
        await self._supervisor(instance).send_command(instance.id, command)
