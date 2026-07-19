"""server.properties: codec (comment-preserving) and config schema."""

from pathlib import Path

from aether_sdk import ConfigField, ConfigFieldType, ConfigSchema, ConfigWarning

_BOOL = ConfigFieldType.BOOLEAN
_INT = ConfigFieldType.INTEGER
_ENUM = ConfigFieldType.ENUM
_STR = ConfigFieldType.STRING
_PASS = ConfigFieldType.PASSWORD


class PropertiesCodec:
    """Java .properties-style key=value files.

    ``apply`` rewrites values in place, keeping comments, blank lines and
    key order; unknown keys are appended at the end.
    """

    def parse(self, text: str) -> dict[str, str]:
        values: dict[str, str] = {}
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", "!")):
                continue
            if "=" in stripped:
                key, _, value = stripped.partition("=")
                values[key.strip()] = value.strip()
        return values

    def apply(self, text: str, values: dict[str, str]) -> str:
        remaining = dict(values)
        out: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith(("#", "!")) and "=" in stripped:
                key = stripped.partition("=")[0].strip()
                if key in remaining:
                    out.append(f"{key}={remaining.pop(key)}")
                    continue
            out.append(line)
        out.extend(f"{key}={value}" for key, value in remaining.items())
        return "\n".join(out) + "\n"


def _f(key: str, label: str, **kw) -> ConfigField:
    return ConfigField(key=key, label=label, **kw)


SERVER_PROPERTIES_SCHEMA = ConfigSchema(
    id="server-properties",
    label="server.properties",
    file="server.properties",
    format="properties",
    fields=[
        # ------------------------------------------------------------- Geral
        _f("motd", "MOTD (mensagem do servidor)", type=_STR, section="Geral",
           description="Aparece na lista de servidores do jogo. Aceita cores com §"),
        _f("max-players", "Máximo de jogadores", type=_INT, default="20", section="Geral",
           minimum=1, maximum=2000),
        _f("server-port", "Porta", type=_INT, default="25565", section="Geral",
           minimum=1, maximum=65535),
        _f("enable-status", "Aparecer na lista de servidores", type=_BOOL, default="true",
           section="Geral", advanced=True),
        _f("hide-online-players", "Ocultar lista de jogadores online", type=_BOOL,
           default="false", section="Geral", advanced=True),
        _f("player-idle-timeout", "Expulsar por inatividade (minutos, 0 = nunca)", type=_INT,
           default="0", section="Geral", minimum=0, advanced=True),

        # -------------------------------------------------------------- Jogo
        _f("gamemode", "Modo de jogo", type=_ENUM, default="survival", section="Jogo",
           options=["survival", "creative", "adventure", "spectator"]),
        _f("difficulty", "Dificuldade", type=_ENUM, default="normal", section="Jogo",
           options=["peaceful", "easy", "normal", "hard"]),
        _f("hardcore", "Hardcore", type=_BOOL, default="false", section="Jogo",
           description="Morrer vira modo espectador permanentemente"),
        _f("pvp", "PvP", type=_BOOL, default="true", section="Jogo"),
        _f("allow-flight", "Permitir voo", type=_BOOL, default="false", section="Jogo",
           description="Necessário com mods que dão voo, senão o servidor expulsa o jogador"),
        _f("enable-command-block", "Blocos de comando", type=_BOOL, default="false",
           section="Jogo"),
        _f("force-gamemode", "Forçar modo de jogo ao entrar", type=_BOOL, default="false",
           section="Jogo", advanced=True),
        _f("spawn-monsters", "Gerar monstros", type=_BOOL, default="true", section="Jogo"),
        _f("spawn-animals", "Gerar animais", type=_BOOL, default="true", section="Jogo"),
        _f("spawn-npcs", "Gerar aldeões", type=_BOOL, default="true", section="Jogo"),
        _f("allow-nether", "Permitir o Nether", type=_BOOL, default="true", section="Jogo"),

        # ------------------------------------------------------------- Mundo
        _f("level-name", "Nome da pasta do mundo", type=_STR, default="world", section="Mundo",
           description="Precisa bater com o nome da pasta em disco, senão um mundo novo é criado"),
        _f("level-seed", "Seed", type=_STR, section="Mundo",
           description="Só afeta a geração de um mundo novo"),
        _f("level-type", "Tipo de mundo", type=_ENUM, default="minecraft:normal", section="Mundo",
           options=["minecraft:normal", "minecraft:flat", "minecraft:large_biomes",
                    "minecraft:amplified", "minecraft:single_biome_surface"], advanced=True),
        _f("generate-structures", "Gerar estruturas", type=_BOOL, default="true", section="Mundo"),
        _f("spawn-protection", "Proteção do spawn (blocos)", type=_INT, default="16",
           section="Mundo", minimum=0,
           description="Raio onde só operadores podem construir. 0 desativa"),
        _f("max-world-size", "Tamanho máximo do mundo (blocos)", type=_INT, default="29999984",
           section="Mundo", minimum=1, advanced=True),

        # -------------------------------------------------------- Desempenho
        _f("view-distance", "Distância de visão (chunks)", type=_INT, default="10",
           section="Desempenho", minimum=2, maximum=32,
           description="O que mais pesa no servidor. 8–12 é o comum em servidor modado"),
        _f("simulation-distance", "Distância de simulação (chunks)", type=_INT, default="10",
           section="Desempenho", minimum=2, maximum=32,
           description="Raio onde mobs e redstone rodam. Reduzir ajuda mais que a visão"),
        _f("max-tick-time", "Tempo máximo por tick (ms, -1 desliga o watchdog)", type=_INT,
           default="60000", section="Desempenho", advanced=True,
           description="Com muitos mods, -1 evita o servidor se matar achando que travou"),
        _f("network-compression-threshold", "Limiar de compressão de rede (bytes)", type=_INT,
           default="256", section="Desempenho", advanced=True),
        _f("entity-broadcast-range-percentage", "Alcance de entidades (%)", type=_INT,
           default="100", section="Desempenho", minimum=10, maximum=1000, advanced=True),
        _f("sync-chunk-writes", "Escrita síncrona de chunks", type=_BOOL, default="true",
           section="Desempenho", advanced=True,
           description="Desativar acelera em disco lento, com risco em queda de energia"),

        # -------------------------------------------------- Acesso e segurança
        _f("online-mode", "Online mode (contas originais)", type=_BOOL, default="true",
           section="Acesso",
           description="Desativado, qualquer pessoa entra com qualquer nome — use whitelist"),
        _f("white-list", "Whitelist", type=_BOOL, default="false", section="Acesso",
           description="Só quem está na lista entra. É a proteção quando online-mode está off"),
        _f("enforce-whitelist", "Expulsar quem sair da whitelist", type=_BOOL, default="false",
           section="Acesso"),
        _f("enforce-secure-profile", "Exigir perfil assinado", type=_BOOL, default="true",
           section="Acesso", advanced=True),
        _f("prevent-proxy-connections", "Bloquear conexões via proxy", type=_BOOL,
           default="false", section="Acesso", advanced=True),
        _f("op-permission-level", "Nível de permissão dos operadores", type=_ENUM, default="4",
           options=["1", "2", "3", "4"], section="Acesso", advanced=True),
        _f("broadcast-console-to-ops", "Enviar saída do console aos operadores", type=_BOOL,
           default="true", section="Acesso", advanced=True),

        # ---------------------------------------------------- Pacote de recursos
        _f("resource-pack", "URL do pacote de recursos", type=_STR, section="Pacote de recursos"),
        _f("resource-pack-sha1", "SHA-1 do pacote", type=_STR, section="Pacote de recursos",
           advanced=True, description="Sem isso o jogador rebaixa o pacote a cada entrada"),
        _f("require-resource-pack", "Exigir o pacote", type=_BOOL, default="false",
           section="Pacote de recursos"),
        _f("resource-pack-prompt", "Mensagem ao pedir o pacote", type=_STR,
           section="Pacote de recursos", advanced=True),

        # ------------------------------------------------------ RCON e consulta
        _f("enable-rcon", "Habilitar RCON", type=_BOOL, default="false", section="RCON",
           description="Console remoto. Necessário para métricas de TPS e jogadores"),
        _f("rcon.port", "Porta do RCON", type=_INT, default="25575", section="RCON",
           minimum=1, maximum=65535),
        _f("rcon.password", "Senha do RCON", type=_PASS, section="RCON",
           description="Sem senha forte, qualquer um com acesso à porta controla o servidor"),
        _f("enable-query", "Habilitar consulta (GameSpy4)", type=_BOOL, default="false",
           section="RCON", advanced=True),
        _f("query.port", "Porta da consulta", type=_INT, default="25565", section="RCON",
           minimum=1, maximum=65535, advanced=True),
    ],
)


def config_warnings(root: Path, values: dict[str, str]) -> list[ConfigWarning]:
    """Problemas que o schema não pega porque o valor é sintaticamente válido.

    O caso que motivou isto: `level-name` aceita qualquer texto, e apontar para
    uma pasta que não existe faz o Minecraft **gerar um mundo novo e vazio** sem
    reclamar. Aconteceu duas vezes neste projeto, e nas duas o sintoma só
    apareceu quando alguém entrou no servidor e viu terreno desconhecido.
    """
    avisos: list[ConfigWarning] = []

    nome = (values.get("level-name") or "").strip()
    if nome and not (root / nome).is_dir():
        candidatos = sorted(
            d.name for d in root.iterdir() if d.is_dir() and (d / "level.dat").is_file()
        )
        sugestao = f" Mundos encontrados na pasta: {', '.join(candidatos)}." if candidatos else ""
        avisos.append(
            ConfigWarning(
                key="level-name",
                level="error",
                message=(
                    f"A pasta “{nome}” não existe. Ao iniciar, o servidor vai gerar um "
                    f"mundo novo e vazio com esse nome em vez de carregar o seu.{sugestao}"
                ),
            )
        )

    if values.get("online-mode") == "false" and values.get("white-list") != "true":
        avisos.append(
            ConfigWarning(
                key="white-list",
                level="warning",
                message=(
                    "Com online-mode desligado e sem whitelist, qualquer pessoa que "
                    "alcance o servidor entra com o nome que quiser — inclusive o de "
                    "um operador."
                ),
            )
        )

    if values.get("enable-rcon") == "true" and not (values.get("rcon.password") or "").strip():
        avisos.append(
            ConfigWarning(
                key="rcon.password",
                level="error",
                message="RCON habilitado sem senha: quem alcançar a porta controla o servidor.",
            )
        )

    return avisos
