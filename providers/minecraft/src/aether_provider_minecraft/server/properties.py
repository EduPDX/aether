"""server.properties: codec (comment-preserving) and config schema."""

from aether_sdk import ConfigField, ConfigFieldType, ConfigSchema

_BOOL = ConfigFieldType.BOOLEAN
_INT = ConfigFieldType.INTEGER
_ENUM = ConfigFieldType.ENUM
_STR = ConfigFieldType.STRING


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


SERVER_PROPERTIES_SCHEMA = ConfigSchema(
    id="server-properties",
    label="server.properties",
    file="server.properties",
    format="properties",
    fields=[
        ConfigField(key="motd", label="MOTD (mensagem do servidor)", type=_STR, section="Geral"),
        ConfigField(
            key="max-players",
            label="Máximo de jogadores",
            type=_INT,
            default="20",
            section="Geral",
        ),
        ConfigField(
            key="gamemode",
            label="Modo de jogo",
            type=_ENUM,
            default="survival",
            options=["survival", "creative", "adventure", "spectator"],
            section="Jogo",
        ),
        ConfigField(
            key="difficulty",
            label="Dificuldade",
            type=_ENUM,
            default="normal",
            options=["peaceful", "easy", "normal", "hard"],
            section="Jogo",
        ),
        ConfigField(key="hardcore", label="Hardcore", type=_BOOL, default="false", section="Jogo"),
        ConfigField(key="pvp", label="PvP", type=_BOOL, default="true", section="Jogo"),
        ConfigField(
            key="allow-flight",
            label="Permitir voo (anti-kick de mods)",
            type=_BOOL,
            default="false",
            section="Jogo",
        ),
        ConfigField(
            key="enable-command-block",
            label="Blocos de comando",
            type=_BOOL,
            default="false",
            section="Jogo",
        ),
        ConfigField(
            key="level-name", label="Nome do mundo", type=_STR, default="world", section="Mundo"
        ),
        ConfigField(key="level-seed", label="Seed", type=_STR, section="Mundo"),
        ConfigField(
            key="view-distance",
            label="Distância de visão (chunks)",
            type=_INT,
            default="10",
            section="Desempenho",
        ),
        ConfigField(
            key="simulation-distance",
            label="Distância de simulação (chunks)",
            type=_INT,
            default="10",
            section="Desempenho",
        ),
        ConfigField(
            key="spawn-protection",
            label="Proteção do spawn (blocos)",
            type=_INT,
            default="16",
            section="Mundo",
        ),
        ConfigField(key="server-port", label="Porta", type=_INT, default="25565", section="Rede"),
        ConfigField(
            key="online-mode",
            label="Online mode (contas originais)",
            type=_BOOL,
            default="true",
            description="Desativar permite contas não-originais e remove a autenticação da Mojang",
            section="Rede",
        ),
        ConfigField(
            key="white-list", label="Whitelist", type=_BOOL, default="false", section="Rede"
        ),
    ],
)
