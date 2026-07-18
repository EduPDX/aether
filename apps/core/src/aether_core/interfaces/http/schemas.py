"""Request/response models for the v1 API."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from aether_core.domain.content import ContentItem
from aether_core.domain.instances import Instance


class CreateInstanceRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    provider_id: str
    root_dir: str
    content_dirs: dict[str, str] = Field(default_factory=dict)
    provider_data: dict[str, Any] = Field(default_factory=dict)


class InstanceOut(BaseModel):
    id: str
    name: str
    provider_id: str
    root_dir: str
    content_dirs: dict[str, str]
    provider_data: dict[str, Any]
    created_at: datetime
    state: str = "stopped"

    @staticmethod
    def from_domain(instance: Instance, state: str = "stopped") -> "InstanceOut":
        return InstanceOut(**instance.__dict__, state=state)


class ContentFileRequest(BaseModel):
    type: str
    file: str


class CopyContentRequest(ContentFileRequest):
    to_instance_id: str
    """Tipo de destino; ausente = mesmo tipo da origem.

    Difere ao levar um mod do servidor para o perfil de cliente da instância.
    """
    to_type: str | None = None


class ContentItemOut(BaseModel):
    file: str
    enabled: bool
    size_bytes: int
    mtime: int
    duplicate: bool
    icon_url: str | None
    metadata: dict[str, Any]

    @staticmethod
    def from_domain(item: ContentItem) -> "ContentItemOut":
        return ContentItemOut(
            file=item.file,
            enabled=item.enabled,
            size_bytes=item.size_bytes,
            mtime=item.mtime,
            duplicate=item.duplicate,
            icon_url=f"/api/v1/icons/{item.icon_file}" if item.icon_file else None,
            metadata=item.metadata.model_dump(exclude={"icon_png"}),
        )


class CompareOut(BaseModel):
    only_in_a: list[ContentItemOut]
    only_in_b: list[ContentItemOut]
    version_diffs: list[dict[str, Any]]
