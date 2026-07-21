"""Troca de versão do Minecraft.

Diferente do 7DTD, o Minecraft não roda um instalador: a versão é a variável
``VERSION`` do container ``itzg``. Trocar de versão é editar o ``provider_data``
e recriar o container — o itzg baixa a versão nova no próximo boot. Por isso o
Minecraft não implementa ``SupportsInstall`` (feito para jogos com instalador),
e sim esta capacidade própria, mais leve.

A lista de versões vem do manifesto oficial da Mojang, então nunca envelhece.
"""

from pathlib import Path
from typing import Any

from aether_sdk import VersionInfo

# Manifesto oficial: todas as versões lançadas, com a marca de release/snapshot.
MANIFEST_URL = "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"

# O itzg entende o id da versão direto (release "1.20.1", snapshot "23w31a"),
# então o id do manifesto é o que vai para a variável VERSION sem tradução.


async def fetch_versions(http_get) -> list[VersionInfo]:
    """Lê o manifesto da Mojang e devolve as versões instaláveis.

    Degrada para lista vazia em vez de levantar: origem fora do ar não pode
    quebrar a tela de versão.
    """
    if http_get is None:
        return []
    try:
        corpo: Any = await http_get(MANIFEST_URL)
    except Exception:  # noqa: BLE001 - origem fora do ar não é erro nosso
        return []
    if not isinstance(corpo, dict):
        return []

    out: list[VersionInfo] = []
    for v in corpo.get("versions") or []:
        vid = str(v.get("id") or "")
        if not vid:
            continue
        tipo = str(v.get("type") or "")
        estavel = tipo == "release"
        out.append(
            VersionInfo(
                id=vid,
                label=vid,
                description="" if estavel else tipo,  # snapshot, old_beta, old_alpha
                stable=estavel,
            )
        )
    return out


def current_version(provider_data: dict) -> str:
    """Versão fixada hoje na instância (o que está no bloco container)."""
    container = (provider_data or {}).get("container") or {}
    return str(container.get("version") or "")


# Mods do servidor e o perfil do cliente — os dois lugares onde um .jar preso à
# versão pode existir.
_PASTAS_MOD = ("mods", "aether-client/mods")


def is_modded(root: Path) -> bool:
    """A instância tem mods de verdade instalados?

    O aviso da troca de versão é sobre isto: mod é preso à versão e quebra ao
    atualizar. Mas o que importa é haver mod, não o tipo do servidor — um Forge
    sem nenhum mod atualiza sem problema. Por isso conta arquivos, não o loader.

    Só conta ``.jar`` habilitados: um ``.jar.disabled`` não carrega, então não
    quebra o boot.
    """
    for sub in _PASTAS_MOD:
        pasta = root / sub
        if pasta.is_dir() and any(p.is_file() and p.suffix == ".jar" for p in pasta.iterdir()):
            return True
    return False


def pin_version(provider_data: dict, version: str) -> dict:
    """Mudanças a mesclar no provider_data para fixar `version`.

    Não recria o container aqui: o Core faz o backup e reinicia. Na próxima
    subida, o container_spec lê esta versão e o itzg baixa o que faltar.
    """
    version = version.strip()
    if not version:
        raise ValueError("informe a versão")
    container = dict((provider_data or {}).get("container") or {})
    container["version"] = version
    return {"container": container}
