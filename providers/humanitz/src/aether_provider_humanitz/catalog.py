"""Ficha do HumanitZ para o catálogo."""

from aether_sdk import (
    GameCatalogEntry,
    LinkUtil,
    PortaDoJogo,
    RamPorJogadores,
    RequisitosDeHardware,
)

from aether_provider_humanitz.server.container import DEFAULT_PORT, DEFAULT_QUERY_PORT

# O app da loja é outro: o 2728330 é o servidor dedicado e não tem página, então
# pedir metadados por ele volta vazio. O 1622560 é o jogo na loja.
STEAM_APP_ID_LOJA = 1622560


def catalog_entry() -> GameCatalogEntry:
    return GameCatalogEntry(
        id="humanitz",
        provider_id="humanitz",
        nome="HumanitZ",
        tagline="Sobrevivência pós-apocalíptica com zumbis, em mundo aberto cooperativo.",
        so_do_servidor=["Linux", "Windows"],
        steam_app_id=STEAM_APP_ID_LOJA,
        requisitos_servidor_minimo=RequisitosDeHardware(
            cpu="2 núcleos",
            ram="4 GB",
            disco="6 GB",
            rede="10 Mbps de upload",
            observacao="Poucos jogadores.",
        ),
        requisitos_servidor_recomendado=RequisitosDeHardware(
            cpu="4 núcleos com bom clock",
            ram="8 GB",
            disco="10 GB em SSD",
            rede="25 Mbps de upload",
            observacao="Servidor cheio, com airdrops e loot respawnando.",
        ),
        ram_por_jogadores=[
            RamPorJogadores(ate_jogadores=8, ram="4 GB", observacao="Configuração padrão."),
            RamPorJogadores(ate_jogadores=16, ram="6–8 GB", observacao="Servidor cheio."),
            RamPorJogadores(
                ate_jogadores=32,
                ram="8 GB+",
                observacao="Acima de 16 jogadores o gargalo tende a ser CPU.",
            ),
        ],
        portas=[
            PortaDoJogo(numero=DEFAULT_PORT, protocolo="udp", descricao="Conexão dos jogadores"),
            PortaDoJogo(
                numero=DEFAULT_QUERY_PORT,
                protocolo="udp",
                descricao="Consulta da Steam — sem ela o servidor não aparece na lista",
            ),
        ],
        observacoes_de_hospedagem=[
            "Nome, senha, PVP e máximo de jogadores ficam no GameServerSettings.ini, "
            "editável na aba Config.",
            'Evite a palavra "Official" no nome do servidor: o jogo pode recusá-lo.',
            "A senha de admin (AdminPass) libera comandos com /adminaccess <senha> no jogo.",
        ],
        links=[
            LinkUtil(titulo="Site oficial", url="https://www.humanitzgame.com/"),
            LinkUtil(
                titulo="Guia de servidor dedicado (Steam)",
                url="https://steamcommunity.com/app/1622560/discussions/",
            ),
        ],
    )
