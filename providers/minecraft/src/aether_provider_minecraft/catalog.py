"""Ficha do Minecraft para o catálogo.

O Minecraft não está na Steam, então nada aqui vem de enriquecimento externo —
é tudo curado. É justamente o caso que justifica o contrato separar hospedagem
de metadados de loja: sem isso este jogo ficaria com uma página vazia.
"""

from aether_sdk import (
    GameCatalogEntry,
    LinkUtil,
    PortaDoJogo,
    RamPorJogadores,
    RequisitosDeHardware,
)


def catalog_entry() -> GameCatalogEntry:
    return GameCatalogEntry(
        id="minecraft",
        provider_id="minecraft",
        nome="Minecraft (Java Edition)",
        tagline="Mundo aberto de blocos, com mods e modpacks.",
        descricao=(
            "Servidor dedicado do Minecraft Java Edition. O painel suporta o servidor "
            "puro (Vanilla) e os carregadores de mods e plugins mais usados — Forge, "
            "Fabric e Paper —, com catálogo de mods do Modrinth integrado."
        ),
        genero=["Sandbox", "Sobrevivência", "Construção"],
        desenvolvedora="Mojang Studios",
        publicadora="Mojang Studios",
        plataformas_do_cliente=["Windows", "macOS", "Linux"],
        so_do_servidor=["Linux", "Windows", "macOS"],
        # Imagens do Wikimedia Commons, escolhidas pela licença: o logo é domínio
        # público e a arte é CC BY 3.0. Pegar da loja ou do site oficial seria
        # cópia de material proprietário num projeto aberto.
        logo_url="https://upload.wikimedia.org/wikipedia/commons/c/cb/Minecraft_Logo-en.svg",
        banner_url=(
            "https://upload.wikimedia.org/wikipedia/commons/6/6a/Minecraft_Trails_and_Tales_Art.png"
        ),
        atribuicao_da_imagem="Arte: Xbox MENA, CC BY 3.0, via Wikimedia Commons",
        requisitos_servidor_minimo=RequisitosDeHardware(
            cpu="2 núcleos",
            ram="2 GB para a JVM",
            disco="5 GB",
            rede="5 Mbps de upload",
            observacao="Vanilla, poucos jogadores, distância de renderização baixa.",
        ),
        requisitos_servidor_recomendado=RequisitosDeHardware(
            cpu="4+ núcleos com clock alto",
            ram="6–8 GB para a JVM",
            disco="20 GB em SSD",
            rede="25 Mbps de upload",
            observacao=(
                "O servidor é essencialmente de thread única para a lógica do mundo: "
                "clock alto vale mais do que muitos núcleos."
            ),
        ),
        ram_por_jogadores=[
            RamPorJogadores(ate_jogadores=5, ram="2 GB", observacao="Vanilla."),
            RamPorJogadores(ate_jogadores=10, ram="4 GB", observacao="Vanilla ou poucos plugins."),
            RamPorJogadores(
                ate_jogadores=20,
                ram="6–8 GB",
                observacao="Com modpack, comece em 8 GB.",
            ),
            RamPorJogadores(
                ate_jogadores=40,
                ram="10–12 GB",
                observacao="Modpacks grandes pedem mais memória que jogadores.",
            ),
        ],
        portas=[
            PortaDoJogo(numero=25565, protocolo="tcp", descricao="Conexão dos jogadores"),
            PortaDoJogo(
                numero=25565,
                protocolo="udp",
                descricao="Necessária apenas para chat de voz por mod",
                obrigatoria=False,
            ),
            PortaDoJogo(
                numero=25575,
                protocolo="tcp",
                descricao="RCON (opcional; o painel já dá console)",
                obrigatoria=False,
            ),
        ],
        observacoes_de_hospedagem=[
            "Dar RAM demais à JVM piora as pausas de coleta de lixo — subir de 8 para "
            "16 GB sem necessidade costuma deixar o servidor pior, não melhor.",
            "A EULA do Minecraft precisa ser aceita para o servidor iniciar.",
            "Modpack pesado exige que os jogadores tenham os mesmos mods no cliente.",
        ],
        links=[
            LinkUtil(titulo="Site oficial", url="https://www.minecraft.net/"),
            LinkUtil(titulo="Baixar o servidor", url="https://www.minecraft.net/download/server"),
            LinkUtil(
                titulo="Wiki (servidor dedicado)",
                url="https://minecraft.wiki/w/Tutorial:Setting_up_a_server",
            ),
            LinkUtil(titulo="Modrinth (mods)", url="https://modrinth.com/"),
        ],
    )
