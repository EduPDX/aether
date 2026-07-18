"""Local process supervisor: spawns and babysits game server processes.

One supervisor per Core process. Each running instance gets an asyncio
subprocess with a reader task that parses console lines through the
provider codec, keeps a ring buffer for history and publishes events:

- ``instance.{id}.console`` — every line ``{line, level, ready}``
- ``instance.{id}.state``   — state transitions ``{state, exit_code?}``
"""

import asyncio
import contextlib
import logging
import os
from collections import deque
from dataclasses import dataclass, field

from aether_sdk import ConsoleCodec, LaunchSpec

from aether_core.application.events import EventBus
from aether_core.domain.errors import ConflictError, ValidationFailedError
from aether_core.domain.instances import InstanceState

log = logging.getLogger(__name__)

HISTORY_LINES = 1000
STOP_GRACE_SECONDS = 30
TERMINATE_GRACE_SECONDS = 10


@dataclass
class _Running:
    process: asyncio.subprocess.Process
    spec: LaunchSpec
    state: InstanceState = InstanceState.STARTING
    logs: deque[str] = field(default_factory=lambda: deque(maxlen=HISTORY_LINES))
    stop_requested: bool = False
    reader: asyncio.Task | None = None


class LocalProcessSupervisor:
    def __init__(self, bus: EventBus) -> None:
        self._bus = bus
        self._procs: dict[str, _Running] = {}

    # -------------------------------------------------------------- queries --
    def state(self, instance_id: str) -> InstanceState:
        rp = self._procs.get(instance_id)
        return rp.state if rp else InstanceState.STOPPED

    def pid_of(self, instance_id: str) -> int | None:
        rp = self._procs.get(instance_id)
        if rp and rp.process.returncode is None:
            return rp.process.pid
        return None

    def logs(self, instance_id: str, tail: int = 200) -> list[str]:
        rp = self._procs.get(instance_id)
        if not rp:
            return []
        lines = list(rp.logs)
        return lines[-tail:] if tail > 0 else lines

    # ------------------------------------------------------------- commands --
    async def start(self, instance_id: str, spec: LaunchSpec, codec: ConsoleCodec | None) -> None:
        current = self.state(instance_id)
        if current in (InstanceState.STARTING, InstanceState.RUNNING, InstanceState.STOPPING):
            raise ConflictError(f"instance is already {current}")

        try:
            process = await asyncio.create_subprocess_exec(
                *spec.command,
                cwd=str(spec.cwd) if spec.cwd else None,
                env={**os.environ, **spec.env},
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
        except OSError as exc:
            raise ValidationFailedError(f"failed to spawn process: {exc}") from exc

        rp = _Running(process=process, spec=spec)
        self._procs[instance_id] = rp
        await self._set_state(instance_id, rp, InstanceState.STARTING)
        rp.reader = asyncio.create_task(self._read_output(instance_id, rp, codec))

    async def stop(self, instance_id: str) -> None:
        rp = self._procs.get(instance_id)
        if not rp or rp.state in (InstanceState.STOPPED, InstanceState.CRASHED):
            raise ConflictError("instance is not running")
        rp.stop_requested = True
        await self._set_state(instance_id, rp, InstanceState.STOPPING)

        if rp.spec.stop_command and rp.process.stdin:
            with contextlib.suppress(Exception):
                rp.process.stdin.write((rp.spec.stop_command + "\n").encode())
                await rp.process.stdin.drain()
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(rp.process.wait(), STOP_GRACE_SECONDS)

        if rp.process.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                rp.process.terminate()
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(rp.process.wait(), TERMINATE_GRACE_SECONDS)

        if rp.process.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                rp.process.kill()
            await rp.process.wait()

    async def kill(self, instance_id: str) -> None:
        rp = self._procs.get(instance_id)
        if not rp or rp.process.returncode is not None:
            raise ConflictError("instance is not running")
        rp.stop_requested = True
        with contextlib.suppress(ProcessLookupError):
            rp.process.kill()
        await rp.process.wait()

    async def restart(self, instance_id: str, spec: LaunchSpec, codec: ConsoleCodec | None) -> None:
        if self.state(instance_id) not in (InstanceState.STOPPED, InstanceState.CRASHED):
            await self.stop(instance_id)
            rp = self._procs.get(instance_id)
            if rp and rp.reader:
                await rp.reader
        await self.start(instance_id, spec, codec)

    async def send_command(self, instance_id: str, command: str) -> None:
        rp = self._procs.get(instance_id)
        if not rp or rp.process.returncode is not None or not rp.process.stdin:
            raise ConflictError("instance is not running")
        rp.process.stdin.write((command + "\n").encode())
        await rp.process.stdin.drain()
        rp.logs.append(f"> {command}")
        await self._bus.publish(
            f"instance.{instance_id}.console",
            {"line": f"> {command}", "level": "CMD", "ready": False},
        )

    async def shutdown(self) -> None:
        """Stop every managed process (Core shutdown)."""
        for instance_id, rp in list(self._procs.items()):
            if rp.process.returncode is None:
                with contextlib.suppress(Exception):
                    await self.stop(instance_id)

    # -------------------------------------------------------------- internal --
    async def _set_state(
        self, instance_id: str, rp: _Running, state: InstanceState, **extra
    ) -> None:
        rp.state = state
        await self._bus.publish(f"instance.{instance_id}.state", {"state": state, **extra})

    async def _read_output(
        self, instance_id: str, rp: _Running, codec: ConsoleCodec | None
    ) -> None:
        assert rp.process.stdout is not None
        try:
            while True:
                chunk = await rp.process.stdout.readline()
                if not chunk:
                    break
                raw = chunk.decode("utf-8", "replace").rstrip("\r\n")
                if not raw:
                    continue
                parsed = codec.parse(raw) if codec else None
                rp.logs.append(raw)
                await self._bus.publish(
                    f"instance.{instance_id}.console",
                    {
                        "line": raw,
                        "level": parsed.level if parsed else "",
                        "ready": bool(parsed and parsed.ready),
                    },
                )
                if parsed and parsed.ready and rp.state == InstanceState.STARTING:
                    await self._set_state(instance_id, rp, InstanceState.RUNNING)
        except Exception:  # noqa: BLE001
            log.exception("console reader failed for instance %s", instance_id)
        finally:
            code = await rp.process.wait()
            final = (
                InstanceState.STOPPED if rp.stop_requested or code == 0 else InstanceState.CRASHED
            )
            await self._set_state(instance_id, rp, final, exit_code=code)
