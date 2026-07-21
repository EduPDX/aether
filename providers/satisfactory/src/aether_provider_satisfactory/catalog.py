"""Ficha do Satisfactory para o catálogo.

Os requisitos de hospedagem vêm da experiência de rodar o servidor: o gargalo é
memória, que cresce com o tamanho da fábrica, não com o número de jogadores (o
jogo é cooperativo, com poucos jogadores num mundo enorme).
"""

from aether_sdk import (
    GameCatalogEntry,
    LinkUtil,
    PortaDoJogo,
    RamPorJogadores,
    RequisitosDeHardware,
)

from aether_provider_satisfactory.server.container import DEFAULT_PORT

# O app da loja é outro: o 1690800 é o servidor dedicado e não tem página, então
# pedir metadados por ele volta vazio. O 526870 é o jogo na loja.
STEAM_APP_ID_LOJA = 526870


def catalog_entry() -> GameCatalogEntry:
    return GameCatalogEntry(
        id="satisfactory",
        provider_id="satisfactory",
        nome="Satisfactory",
        tagline="Construção de fábricas em mundo aberto, cooperativo para poucos jogadores.",
        so_do_servidor=["Linux", "Windows"],
        steam_app_id=STEAM_APP_ID_LOJA,
        requisitos_servidor_minimo=RequisitosDeHardware(
            cpu="4 núcleos",
            ram="6 GB",
            disco="10 GB",
            rede="Boa latência importa mais que banda; o jogo troca pouco tráfego.",
            observacao="Fábrica pequena, poucas horas de jogo.",
        ),
        requisitos_servidor_recomendado=RequisitosDeHardware(
            cpu="4+ núcleos com bom desempenho por núcleo",
            ram="12–16 GB",
            disco="15 GB em SSD",
            rede="A simulação é local ao servidor; upload modesto basta.",
            observacao=(
                "Fábrica de fim de jogo é pesada em memória e em CPU de núcleo único: "
                "clock alto ajuda mais que muitos núcleos."
            ),
        ),
        ram_por_jogadores=[
            RamPorJogadores(
                ate_jogadores=4,
                ram="8–12 GB",
                observacao="O consumo cresce com o tamanho da fábrica, não com jogadores.",
            ),
            RamPorJogadores(
                ate_jogadores=8,
                ram="12–16 GB",
                observacao="Fábricas grandes no fim do jogo pedem mais memória.",
            ),
        ],
        portas=[
            PortaDoJogo(numero=DEFAULT_PORT, protocolo="udp", descricao="Conexão dos jogadores"),
            PortaDoJogo(numero=DEFAULT_PORT, protocolo="tcp", descricao="Conexão dos jogadores"),
        ],
        observacoes_de_hospedagem=[
            "O servidor não tem arquivo de configuração: nome, senha e regras são "
            "definidos dentro do jogo depois de reivindicar o servidor pelo cliente.",
            "Ao subir pela primeira vez o servidor fica 'não reivindicado' — conecte-se "
            "pelo cliente (Servidores → Adicionar servidor pelo IP) para reivindicá-lo.",
            "Desde a 1.0 basta a porta 7777 (UDP e TCP); as antigas de beacon/query saíram.",
        ],
        links=[
            LinkUtil(titulo="Site oficial", url="https://www.satisfactorygame.com/"),
            LinkUtil(
                titulo="Wiki (servidor dedicado)",
                url="https://satisfactory.wiki.gg/wiki/Dedicated_servers",
            ),
        ],
    )
