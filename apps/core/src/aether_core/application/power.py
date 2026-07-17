"""Power use cases: start/stop/restart/kill and console interaction."""

from pathlib import Path
from typing import Protocol

from aether_sdk import ConsoleCodec, LaunchContext, LaunchSpec, SupportsLaunch

from aether_core.application.ports import ProviderRegistry
from aether_core.domain.errors import ValidationFailedError
from aether_core.domain.instances import Instance, InstanceState


class ProcessSupervisor(Protocol):
    def state(self, instance_id: str) -> InstanceState: ...

    def logs(self, instance_id: str, tail: int = 200) -> list[str]: ...

    async def start(
        self, instance_id: str, spec: LaunchSpec, codec: ConsoleCodec | None
    ) -> None: ...

    async def stop(self, instance_id: str) -> None: ...

    async def kill(self, instance_id: str) -> None: ...

    async def restart(
        self, instance_id: str, spec: LaunchSpec, codec: ConsoleCodec | None
    ) -> None: ...

    async def send_command(self, instance_id: str, command: str) -> None: ...


class PowerService:
    def __init__(self, providers: ProviderRegistry, supervisor: ProcessSupervisor) -> None:
        self._providers = providers
        self._supervisor = supervisor

    def _launch(self, instance: Instance) -> tuple[LaunchSpec, ConsoleCodec]:
        provider = self._providers.get(instance.provider_id)
        if not isinstance(provider, SupportsLaunch):
            raise ValidationFailedError(
                f"provider {instance.provider_id!r} does not support server processes"
            )
        spec = provider.launch_spec(
            LaunchContext(root_dir=Path(instance.root_dir), provider_data=instance.provider_data)
        )
        if spec is None:
            raise ValidationFailedError(
                "no runnable server found in the instance directory "
                "(expected run script, server jar or provider_data.command)"
            )
        return spec, provider.console_codec()

    async def start(self, instance: Instance) -> InstanceState:
        spec, codec = self._launch(instance)
        await self._supervisor.start(instance.id, spec, codec)
        return self._supervisor.state(instance.id)

    async def stop(self, instance: Instance) -> InstanceState:
        await self._supervisor.stop(instance.id)
        return self._supervisor.state(instance.id)

    async def restart(self, instance: Instance) -> InstanceState:
        spec, codec = self._launch(instance)
        await self._supervisor.restart(instance.id, spec, codec)
        return self._supervisor.state(instance.id)

    async def kill(self, instance: Instance) -> InstanceState:
        await self._supervisor.kill(instance.id)
        return self._supervisor.state(instance.id)

    def state(self, instance: Instance) -> InstanceState:
        return self._supervisor.state(instance.id)

    def logs(self, instance: Instance, tail: int) -> list[str]:
        return self._supervisor.logs(instance.id, tail)

    async def send_command(self, instance: Instance, command: str) -> None:
        command = command.strip()
        if not command:
            raise ValidationFailedError("empty command")
        await self._supervisor.send_command(instance.id, command)
