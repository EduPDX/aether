"""Analyzer de mods do 7 Days to Die.

Um mod é uma *pasta* dentro de ``Mods/`` com um ``ModInfo.xml`` — diferente
do jar único do Minecraft. O analyzer também aceita o ``.zip`` como baixado
do Nexus, porque é o formato em que o mod chega antes de ser extraído.

Dois dialetos de ModInfo convivem: o antigo (``<ModInfo>`` com ``<Name>``)
e o V2 (raiz ``<xml>`` com ``DisplayName``). Ambos são lidos.
"""

import zipfile
from pathlib import Path
from xml.etree import ElementTree

from aether_sdk import ContentMetadata

_CAMPOS = {
    "Name": "content_id",
    "DisplayName": "display_name",
    "Version": "version",
    "Description": "description",
    "Author": "authors",
    "Website": "homepage",
}


def _parse_modinfo(texto: str) -> dict[str, str]:
    raiz = ElementTree.fromstring(texto)
    # No formato antigo os campos ficam sob <ModInfo>; no V2, direto na raiz.
    origem = raiz.find("ModInfo") if raiz.find("ModInfo") is not None else raiz
    valores: dict[str, str] = {}
    for el in origem:
        destino = _CAMPOS.get(el.tag)
        if destino:
            valores[destino] = el.get("value", "") or ""
    return valores


def _modinfo_de_zip(path: Path) -> str | None:
    with zipfile.ZipFile(path) as zf:
        candidatos = [n for n in zf.namelist() if n.endswith("ModInfo.xml")]
        if not candidatos:
            return None
        # O mais raso é o do mod; os demais podem ser de mods embutidos.
        candidatos.sort(key=lambda n: n.count("/"))
        return zf.read(candidatos[0]).decode("utf-8", "replace")


class ModInfoAnalyzer:
    def __init__(self, content_type: str) -> None:
        self.content_type = content_type

    def analyze(self, path: Path) -> ContentMetadata:
        nome = path.name.removesuffix(".disabled")
        try:
            if path.is_dir():
                arquivo = path / "ModInfo.xml"
                texto = (
                    arquivo.read_text(encoding="utf-8", errors="replace")
                    if arquivo.is_file()
                    else None
                )
            elif zipfile.is_zipfile(path):
                texto = _modinfo_de_zip(path)
            else:
                texto = None
            if texto is None:
                return ContentMetadata(display_name=nome, error="ModInfo.xml não encontrado no mod")
            valores = _parse_modinfo(texto)
        except (OSError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
            return ContentMetadata(display_name=nome, error=f"ModInfo.xml ilegível: {exc}")

        display = valores.pop("display_name", "") or valores.get("content_id") or nome
        return ContentMetadata(display_name=display, **valores)
