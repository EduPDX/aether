"""Detects which Minecraft build (version + mod loader) a server dir runs.

Detection order:

1. Explicit ``provider_data["game"]`` (admin override).
2. Forge/NeoForge library layout: ``libraries/net/minecraftforge/forge/
   <mc>-<forge>/`` (created by the Forge installer).
3. Version pattern in server jar names.
"""

import re
from pathlib import Path

_FORGE_DIR = re.compile(r"^([\d.]+)-([\d.]+)")
_JAR_VERSION = re.compile(r"(?:minecraft_server[._-]?|server[._-]?)?(1\.\d{1,2}(?:\.\d{1,2})?)")


def detect_game_metadata(root: Path, provider_data: dict) -> dict | None:
    explicit = provider_data.get("game")
    if isinstance(explicit, dict) and explicit.get("minecraft"):
        return explicit

    # A versão-alvo (instância provisionada) desempata quando o volume tem sobra
    # de outra versão: trocar de versão deixa a instalação antiga no disco, e
    # pegar a "maior por nome" apontaria para a errada — ex.: um 1.20.1 que virou
    # 26.2 e voltou continuaria detectando 26.2.
    alvo = (provider_data.get("container") or {}).get("version") or ""

    for loader, maven_path in (
        ("forge", "libraries/net/minecraftforge/forge"),
        ("neoforge", "libraries/net/neoforged/neoforge"),
    ):
        base = root / maven_path
        if not base.is_dir():
            continue
        filhos = sorted(base.iterdir(), reverse=True)
        # O da versão-alvo primeiro; sem alvo (ou pasta adotada), o mais novo.
        if alvo:
            filhos.sort(key=lambda c: not c.name.startswith(f"{alvo}-"))
        for child in filhos:
            m = _FORGE_DIR.match(child.name)
            if m:
                if loader == "neoforge":
                    # NeoForge dirs são só a versão do loader (ex.: 20.4.x)
                    return {"loader": "neoforge", "loader_version": child.name}
                return {
                    "minecraft": m.group(1),
                    "loader": loader,
                    "loader_version": m.group(2),
                }

    for jar in root.glob("*.jar"):
        m = _JAR_VERSION.search(jar.name.lower())
        if m and m.group(1).startswith("1."):
            return {"minecraft": m.group(1), "loader": "vanilla"}
    return None


# O formulário de criação usa os rótulos do jogo (FORGE, FABRIC…); o Modrinth
# usa os nomes do loader em minúsculo. VANILLA não tem loader de mods e PAPER
# usa plugins — mas ambos ganham o mapeamento mais próximo para o filtro por
# versão continuar valendo.
_TYPE_TO_LOADER = {
    "FORGE": "forge",
    "NEOFORGE": "neoforge",
    "FABRIC": "fabric",
    "QUILT": "quilt",
    "PAPER": "paper",
    # VANILLA: ausente de propósito — sem loader, o catálogo não filtra por ele.
}


def catalog_context(provider_data: dict) -> tuple[str | None, str | None]:
    """Versão do jogo e loader para filtrar o catálogo de mods.

    Uma instância nasce de dois jeitos e guarda essa informação em lugares
    diferentes — é a origem do bug que fazia o catálogo baixar mod de qualquer
    versão:

    - **provisionada** (servidor criado do zero): versão e tipo vivem no bloco
      ``container``, e o tipo vem em maiúsculo do formulário;
    - **adotada** (pasta existente): vêm da detecção dos arquivos, no bloco
      ``game``, já no formato do loader.

    Devolve ``(None, None)`` quando não dá para saber — melhor não filtrar do
    que filtrar por um valor inválido e não achar nada.
    """
    dados = provider_data or {}

    container = dados.get("container") or {}
    version = container.get("version")
    loader = _TYPE_TO_LOADER.get(str(container.get("type") or "").upper())

    game = dados.get("game") or {}
    version = version or game.get("minecraft")
    loader = loader or game.get("loader")

    # LATEST não é uma versão concreta (só se resolve quando o servidor sobe);
    # vanilla não carrega jar de mod. Nos dois casos, some com o filtro daquele
    # eixo em vez de travar a busca inteira.
    if version and str(version).upper() == "LATEST":
        version = None
    if loader in (None, "", "vanilla"):
        loader = None
    return version, loader
