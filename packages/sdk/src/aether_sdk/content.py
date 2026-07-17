"""Content contract: how providers describe and analyze instance content.

"Content" is any managed file set of a game instance: mods, plugins,
worlds, resource packs... Each provider declares its own content types and
supplies an analyzer able to extract metadata from a single content file.
"""

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class ContentType(BaseModel):
    """A kind of content a provider knows how to manage (e.g. ``mod``).

    ``default_directory`` is where this content lives relative to the
    instance root (e.g. ``mods``); instances may override it per type.
    """

    id: str
    label: str
    file_patterns: list[str] = Field(default_factory=list)
    default_directory: str = ""


class ContentDependency(BaseModel):
    """A dependency declared by one content item on another."""

    content_id: str
    version_range: str = ""
    mandatory: bool = True


class ContentMetadata(BaseModel):
    """Everything an analyzer could extract from one content file.

    All fields are optional except ``display_name``: analyzers must degrade
    gracefully on malformed files and report problems via ``error`` instead
    of raising.
    """

    content_id: str = ""
    display_name: str
    version: str = ""
    description: str = ""
    authors: str = ""
    license: str = ""
    homepage: str = ""
    game_version: str = ""
    loader: str = ""
    client_only: bool = False
    dependencies: list[ContentDependency] = Field(default_factory=list)
    icon_png: bytes | None = None
    extra: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


@runtime_checkable
class ContentAnalyzer(Protocol):
    """Extracts metadata from a single content file.

    Implementations must be pure with respect to the file system: read the
    given path, never write anywhere. Storage of icons/cache is the Core's
    responsibility.
    """

    content_type: str

    def analyze(self, path: Path) -> ContentMetadata: ...
