"""Provider manifest: how a provider identifies itself to the Core."""

import re

from pydantic import BaseModel, field_validator

SDK_VERSION = "0.1.0.dev0"

_SLUG = re.compile(r"^[a-z][a-z0-9-]{1,40}$")


class ProviderManifest(BaseModel):
    """Static identity of a provider package.

    ``id`` is a stable slug (never changes across versions); ``sdk_version``
    is the contract version the provider was built against, used by the Core
    to reject or adapt incompatible providers.
    """

    id: str
    name: str
    version: str
    sdk_version: str = SDK_VERSION
    games: list[str] = []

    @field_validator("id")
    @classmethod
    def _validate_slug(cls, v: str) -> str:
        if not _SLUG.fullmatch(v):
            raise ValueError(f"provider id must be a slug (got {v!r})")
        return v
