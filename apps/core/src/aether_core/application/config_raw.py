"""Edição direta do arquivo de configuração (modo avançado).

O formulário só cobre o que o painel conhece e traduziu; o modo avançado dá
acesso ao arquivo inteiro, para quem precisa de uma opção que a versão do jogo
tem mas o painel ainda não mapeou.

Poder editar o arquivo cru significa poder impedir o servidor de subir, então
o serviço compensa com três garantias:

- valida antes de gravar, apontando linha e coluna do erro;
- guarda a versão anterior a cada gravação, e sabe restaurá-la;
- nunca grava um arquivo que não passou na validação.
"""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

from aether_core.application.events import EventBus
from aether_core.application.files import FilesService
from aether_core.application.ports import ProviderRegistry
from aether_core.domain.errors import NotFoundError, ValidationFailedError
from aether_core.domain.instances import Instance

SUFIXO_ANTERIOR = ".anterior"
"""A cópia fica ao lado do arquivo: quem olhar a pasta entende o que é."""


@dataclass
class ErroDeSintaxe:
    message: str
    line: int
    column: int


def validar_xml(texto: str) -> ErroDeSintaxe | None:
    """``None`` quando o XML está bem formado.

    A posição vem do próprio parser; sem ela o usuário fica caçando o erro num
    arquivo de 100 linhas.
    """
    try:
        ElementTree.fromstring(texto)
    except ElementTree.ParseError as exc:
        linha, coluna = getattr(exc, "position", (0, 0))
        # O parser conta coluna a partir de zero; editores contam de um.
        return ErroDeSintaxe(message=str(exc).split(":")[0], line=linha, column=coluna + 1)
    return None


VALIDADORES = {"xml": validar_xml}


class RawConfigService:
    def __init__(self, providers: ProviderRegistry, files: FilesService, bus: EventBus) -> None:
        self._providers = providers
        self._files = files
        self._bus = bus

    def schema_de(self, instance: Instance, schema_id: str):
        """Exposto para a rota de validação, que valida sem ler o arquivo."""
        return self._schema(instance, schema_id)

    def _schema(self, instance: Instance, schema_id: str):
        provider = self._providers.get(instance.provider_id)
        schemas = getattr(provider, "config_schemas", None)
        if schemas is None:
            raise ValidationFailedError(f"provider {instance.provider_id!r} has no config schemas")
        schema = next((s for s in schemas() if s.id == schema_id), None)
        if schema is None:
            raise NotFoundError(f"unknown config schema: {schema_id}")
        return schema

    async def read(self, instance: Instance, schema_id: str) -> dict:
        schema = self._schema(instance, schema_id)
        try:
            texto = await self._files.read_text(instance, schema.file)
        except NotFoundError:
            texto = ""
        anterior = Path(instance.root_dir) / (schema.file + SUFIXO_ANTERIOR)
        return {
            "file": schema.file,
            "format": schema.format,
            "content": texto,
            "has_previous": anterior.is_file(),
        }

    async def write(self, instance: Instance, schema_id: str, content: str) -> dict:
        """Valida, guarda a versão atual e só então grava a nova."""
        schema = self._schema(instance, schema_id)
        validador = VALIDADORES.get(schema.format)
        if validador is not None:
            erro = validador(content)
            if erro is not None:
                raise ValidationFailedError(
                    f"{erro.message} (linha {erro.line}, coluna {erro.column})"
                )

        await self._guardar_anterior(instance, schema.file)
        await self._files.write_text(instance, schema.file, content)
        await self._bus.publish(
            "config.updated", {"instance_id": instance.id, "schema": schema_id, "raw": True}
        )
        return {"file": schema.file, "has_previous": True}

    async def restore(self, instance: Instance, schema_id: str) -> dict:
        """Volta para a última versão salva antes da alteração mais recente."""
        schema = self._schema(instance, schema_id)
        anterior = Path(instance.root_dir) / (schema.file + SUFIXO_ANTERIOR)
        if not anterior.is_file():
            raise NotFoundError("não há versão anterior guardada deste arquivo")

        texto = await asyncio.to_thread(anterior.read_text, encoding="utf-8", errors="replace")
        # A restauração também é uma alteração: guarda o que está lá antes de
        # sobrescrever, senão restaurar por engano não teria volta.
        await self._guardar_anterior(instance, schema.file)
        await self._files.write_text(instance, schema.file, texto)
        await self._bus.publish(
            "config.updated", {"instance_id": instance.id, "schema": schema_id, "restored": True}
        )
        return {"file": schema.file, "content": texto}

    async def _guardar_anterior(self, instance: Instance, rel_path: str) -> None:
        atual = Path(instance.root_dir) / rel_path
        if not atual.is_file():
            return

        def _copiar() -> None:
            destino = atual.with_name(atual.name + SUFIXO_ANTERIOR)
            destino.write_bytes(atual.read_bytes())

        await asyncio.to_thread(_copiar)
