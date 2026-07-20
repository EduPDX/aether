"""Config contract (v0.3): schema-driven configuration files.

Providers declare *schemas* (typed fields mapped to a config file) and a
*codec* able to parse/apply values while preserving the file's comments
and layout. The Dashboard renders forms from the schema — providers never
ship UI.
"""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field


class ConfigFieldType(StrEnum):
    STRING = "string"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    ENUM = "enum"
    """Renderizado mascarado; sem isso uma senha de RCON apareceria na tela."""
    PASSWORD = "password"


class ConfigField(BaseModel):
    key: str
    label: str
    type: ConfigFieldType = ConfigFieldType.STRING
    description: str = ""
    default: str = ""
    options: list[str] = Field(default_factory=list)
    section: str = ""
    """Fora do essencial: a interface esconde atrás de "mostrar avançadas"."""
    advanced: bool = False
    """Limites de um campo numérico, quando o jogo os define."""
    minimum: int | None = None
    maximum: int | None = None
    depends_on: dict[str, str] = Field(default_factory=dict)
    """Só faz sentido quando outro campo tem certo valor — a semente e o
    tamanho do mundo, por exemplo, só existem em mapa gerado. A interface
    esconde o campo enquanto a condição não bate."""


class ConfigSchema(BaseModel):
    id: str
    label: str
    file: str
    """Path of the config file, relative to the instance root."""
    format: str = "properties"
    fields: list[ConfigField] = Field(default_factory=list)
    fields_from_file: bool = False
    """O arquivo distribuído pelo jogo é que define quais campos existem.

    Com isto ligado o Core esconde os campos ausentes do arquivo, em vez de
    oferecer uma configuração que aquela versão ignora — o 7 Days to Die
    trocou o conjunto de propriedades entre versões mais de uma vez. Fica
    desligado para formatos onde chave ausente significa "usar o padrão"
    (o ``server.properties`` do Minecraft)."""


@runtime_checkable
class ConfigCodec(Protocol):
    """Parses and updates a config file without destroying comments."""

    def parse(self, text: str) -> dict[str, str]: ...

    def apply(self, text: str, values: dict[str, str]) -> str: ...


@dataclass(frozen=True)
class ConfigWarning:
    """Aviso sobre um valor que é válido sintaticamente mas errado na prática.

    Existe porque a configuração de um jogo tem armadilhas que o schema não
    expressa: um campo pode aceitar qualquer texto e ainda assim apontar para
    algo que não existe. O provider conhece essas armadilhas; o Core não.
    """

    key: str
    message: str
    """"error" impede o servidor de funcionar como esperado; "warning" é suspeita."""
    level: str = "warning"


@runtime_checkable
class SupportsConfig(Protocol):
    """Optional provider capability: schema-driven config files."""

    def config_schemas(self) -> list[ConfigSchema]: ...

    def config_codec(self, format: str) -> ConfigCodec: ...

    def config_warnings(self, root: Path, values: dict[str, str]) -> list[ConfigWarning]:
        """Problemas detectáveis nos valores atuais. Vazio = nada a apontar."""
        ...
