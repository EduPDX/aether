"""O que compõe um backup de um servidor Minecraft."""

from pathlib import Path

from aether_sdk import BackupSpec, QuiescePlan

# Arquivos de estado que não são o mundo mas doem de perder: listas de acesso,
# permissões e a configuração do servidor.
ARQUIVOS_DE_ESTADO = (
    "server.properties",
    "ops.json",
    "whitelist.json",
    "banned-players.json",
    "banned-ips.json",
    "permissions.yml",
    "bukkit.yml",
    "spigot.yml",
    "paper.yml",
    "usercache.json",
)

# Volumosos e reproduzíveis: jars baixáveis de novo, logs e caches. Mantê-los
# multiplicaria o tamanho do backup sem proteger nada insubstituível.
EXCLUSOES = (
    "libraries/**",
    "cache/**",
    "logs/**",
    "crash-reports/**",
    "versions/**",
    "*.jar",
    "**/*.log",
    "**/*.log.gz",
)

DEFAULT_LEVEL = "world"


def level_name(root: Path) -> str:
    """Nome do mundo conforme `level-name` em server.properties.

    Sem isso o backup erraria o alvo em qualquer servidor que não use o nome
    padrão — e servidor com mundo renomeado é comum.
    """
    props = root / "server.properties"
    try:
        for linha in props.read_text(encoding="utf-8", errors="replace").splitlines():
            linha = linha.strip()
            if linha.startswith("#") or "=" not in linha:
                continue
            chave, _, valor = linha.partition("=")
            if chave.strip() == "level-name":
                nome = valor.strip()
                return nome or DEFAULT_LEVEL
    except OSError:
        pass
    return DEFAULT_LEVEL


def backup_spec(root: Path) -> BackupSpec:
    nivel = level_name(root)
    # O Nether e o End ficam em pastas irmãs sufixadas — no formato de mundo
    # único (Bukkit/Spigot) elas existem separadas; no Vanilla ficam dentro
    # da pasta do mundo e o glob da própria pasta já as cobre.
    mundos = (f"{nivel}/**", f"{nivel}_nether/**", f"{nivel}_the_end/**")
    return BackupSpec(
        include=(*mundos, "config/**", *ARQUIVOS_DE_ESTADO),
        exclude=EXCLUSOES,
        summary=(
            f"Mundo “{nivel}” (com Nether e End), a pasta config/ e os arquivos de "
            "estado do servidor. Não inclui os mods nem as bibliotecas: são grandes "
            "e podem ser baixados de novo."
        ),
    )


def quiesce_plan() -> QuiescePlan:
    """Pausa a gravação do mundo enquanto o backup lê.

    `save-all flush` força o que está em memória para o disco e `save-off`
    impede novas escritas; sem isso, um servidor em uso grava no meio da
    cópia e o backup sai com região corrompida.
    """
    return QuiescePlan(
        before=("save-all flush", "save-off"),
        after=("save-on",),
        settle_seconds=3.0,
    )
