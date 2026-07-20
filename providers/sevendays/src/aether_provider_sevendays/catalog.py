"""Ficha do 7 Days to Die para o catálogo.

Os números aqui vêm de rodar o servidor, não de página de loja: o jogo simula
um mundo inteiro com zumbis, e a memória cresce com o mundo explorado, não só
com o número de jogadores.
"""

from aether_sdk import (
    GameCatalogEntry,
    LinkUtil,
    PortaDoJogo,
    RamPorJogadores,
    RequisitosDeHardware,
)

from aether_provider_sevendays.server.container import DEFAULT_PORT

# O app da loja é outro: o 294420 é a ferramenta de servidor dedicado e não tem
# página, então pedir metadados por ele volta vazio.
STEAM_APP_ID_LOJA = 251570


def catalog_entry() -> GameCatalogEntry:
    return GameCatalogEntry(
        id="sevendays",
        provider_id="sevendays",
        nome="7 Days to Die",
        tagline="Sobrevivência com construção, mundo destrutível e hordas a cada 7 dias.",
        so_do_servidor=["Linux", "Windows"],
        steam_app_id=STEAM_APP_ID_LOJA,
        requisitos_servidor_minimo=RequisitosDeHardware(
            cpu="4 núcleos",
            ram="6 GB",
            disco="20 GB (o jogo sozinho ocupa ~17 GB)",
            rede="10 Mbps de upload",
            observacao="Suficiente para poucos jogadores num mapa pequeno.",
        ),
        requisitos_servidor_recomendado=RequisitosDeHardware(
            cpu="6+ núcleos com bom desempenho por núcleo",
            ram="12 GB ou mais",
            disco="40 GB em SSD",
            rede="50 Mbps de upload",
            observacao=(
                "A geração de mundo e as hordas são pesadas em CPU de núcleo único: "
                "clock alto ajuda mais do que muitos núcleos."
            ),
        ),
        ram_por_jogadores=[
            RamPorJogadores(ate_jogadores=4, ram="6 GB", observacao="Mapa 6144, sem mods."),
            RamPorJogadores(ate_jogadores=8, ram="8–10 GB", observacao="Configuração padrão."),
            RamPorJogadores(
                ate_jogadores=16,
                ram="12–16 GB",
                observacao="Mapa 8192 ou maior consome bem mais.",
            ),
            RamPorJogadores(
                ate_jogadores=32,
                ram="16 GB+",
                observacao="Acima disso o gargalo costuma ser CPU, não memória.",
            ),
        ],
        portas=[
            PortaDoJogo(numero=DEFAULT_PORT, protocolo="tcp", descricao="Conexão dos jogadores"),
            PortaDoJogo(numero=DEFAULT_PORT, protocolo="udp", descricao="Conexão dos jogadores"),
            PortaDoJogo(
                numero=DEFAULT_PORT + 1,
                protocolo="udp",
                descricao="Steam networking — sem ela o servidor não aparece na lista",
            ),
            PortaDoJogo(
                numero=DEFAULT_PORT + 2,
                protocolo="udp",
                descricao="Steam networking",
            ),
            PortaDoJogo(
                numero=8081,
                protocolo="tcp",
                descricao="Telnet (opcional; o painel já dá console)",
                obrigatoria=False,
            ),
        ],
        observacoes_de_hospedagem=[
            "A instalação baixa ~17 GB pela Steam; a primeira subida é demorada.",
            "Gerar um mundo aleatório (RWG) leva vários minutos antes de o servidor abrir.",
            "Da versão 3.0 em diante a dificuldade e as regras vêm num código de sandbox, "
            "gerado na tela de novo jogo do próprio jogo.",
            "EasyAntiCheat precisa ficar desligado para mods que trocam DLLs.",
        ],
        links=[
            LinkUtil(titulo="Site oficial", url="https://7daystodie.com/"),
            LinkUtil(
                titulo="Wiki (hospedagem de servidor)",
                url="https://7daystodie.fandom.com/wiki/Server",
            ),
            LinkUtil(
                titulo="Notas da versão 3.0",
                url="https://7daystodie.com/v3-0-dead-hot-summer-release-notes/",
            ),
        ],
    )
