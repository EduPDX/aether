"""Config contract (v0.3): schema-driven configuration files.

Providers declare *schemas* (typed fields mapped to a config file) and a
*codec* able to parse/apply values while preserving the file's comments
and layout. The Dashboard renders forms from the schema — providers never
ship UI.
"""

from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field


class ConfigFieldType(StrEnum):
    STRING = "string"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    ENUM = "enum"


class ConfigField(BaseModel):
    key: str
    label: str
    type: ConfigFieldType = ConfigFieldType.STRING
    description: str = ""
    default: str = ""
    options: list[str] = Field(default_factory=list)
    section: str = ""


class ConfigSchema(BaseModel):
    id: str
    label: str
    file: str
    """Path of the config file, relative to the instance root."""
    format: str = "properties"
    fields: list[ConfigField] = Field(default_factory=list)


@runtime_checkable
class ConfigCodec(Protocol):
    """Parses and updates a config file without destroying comments."""

    def parse(self, text: str) -> dict[str, str]: ...

    def apply(self, text: str, values: dict[str, str]) -> str: ...


@runtime_checkable
class SupportsConfig(Protocol):
    """Optional provider capability: schema-driven config files."""

    def config_schemas(self) -> list[ConfigSchema]: ...

    def config_codec(self, format: str) -> ConfigCodec: ...
