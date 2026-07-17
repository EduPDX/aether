"""Instance: a game server (or content folder set) managed by the Core.

In roadmap v0.1 instances are "folders-only": they point at existing
directories and gain process management in v0.2.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from aether_sdk import ContentType


class InstanceState(StrEnum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    CRASHED = "crashed"


@dataclass(frozen=True)
class Instance:
    id: str
    name: str
    provider_id: str
    root_dir: str
    content_dirs: dict[str, str] = field(default_factory=dict)
    provider_data: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @staticmethod
    def new(
        name: str,
        provider_id: str,
        root_dir: str,
        content_dirs: dict[str, str] | None = None,
        provider_data: dict | None = None,
    ) -> "Instance":
        return Instance(
            id=uuid.uuid4().hex,
            name=name,
            provider_id=provider_id,
            root_dir=root_dir,
            content_dirs=dict(content_dirs or {}),
            provider_data=dict(provider_data or {}),
        )

    def resolve_content_dir(self, content_type: ContentType) -> Path:
        """Directory holding this content type: per-instance override wins,
        otherwise the provider's default, resolved against the root."""
        override = self.content_dirs.get(content_type.id)
        rel = override if override is not None else content_type.default_directory
        p = Path(rel)
        return p if p.is_absolute() else Path(self.root_dir) / p
