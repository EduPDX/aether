"""Launch contract (v0.2): how a provider tells the Core to run a server.

Providers translate an instance's root directory + configuration into a
:class:`LaunchSpec`; the Core owns the actual process lifecycle. Console
output flows back through the provider's :class:`ConsoleCodec` so the Core
can extract levels and readiness without knowing the game's log format.
"""

from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field


class LaunchContext(BaseModel):
    """Everything a provider may consider when building a launch spec."""

    root_dir: Path
    provider_data: dict = Field(default_factory=dict)


class LaunchSpec(BaseModel):
    """A concrete, ready-to-spawn server process."""

    command: list[str]
    cwd: Path | None = None
    env: dict[str, str] = Field(default_factory=dict)
    stop_command: str | None = None
    """Text written to stdin for a graceful stop (e.g. ``stop``); ``None``
    means the process only stops via signals."""


class ConsoleLine(BaseModel):
    """One parsed console line."""

    raw: str
    message: str = ""
    level: str = ""
    ready: bool = False
    """True when this line signals the server finished starting."""


@runtime_checkable
class ConsoleCodec(Protocol):
    """Parses raw console output into structured lines."""

    def parse(self, raw: str) -> ConsoleLine: ...


@runtime_checkable
class SupportsLaunch(Protocol):
    """Optional provider capability: managed server processes.

    ``launch_spec`` returns ``None`` when no runnable server is found in
    the instance directory.
    """

    def launch_spec(self, ctx: LaunchContext) -> LaunchSpec | None: ...

    def console_codec(self) -> ConsoleCodec: ...
