"""Mapa-mundi via BlueMap CLI, como sidecar (container à parte).

Ver ADR 0001: o render do mapa não pode disputar CPU nem heap com o servidor do
jogo, então o BlueMap roda no seu próprio container, lendo o mundo por um volume
**só-leitura**. Aqui mora só a tradução instância → :class:`MapPlan`; quem grava
a config, sobe o container e publica a porta é o Core.

A imagem oficial já resolve os caminhos relativos (``world``/``web``/``data``)
sobre o ``WorkingDir`` ``/app``, que é onde o Core monta os volumes — por isso a
config padrão do BlueMap já aponta para o lugar certo, e só precisamos ligar o
``accept-download`` e conter o render.
"""

from aether_sdk import (
    ContainerSpec,
    LaunchContext,
    MapPlan,
    MapSeedFile,
    PortMapping,
    VolumeMount,
)

#: Imagem oficial do BlueMap CLI, **fixada por digest** — reprodutibilidade
#: acima de novidade (os mesmos bits daqui a anos > pegar a última). O registry
#: não publica tag por versão; este digest é a 5.22 (conferido com `-V`).
#: Para atualizar: `docker pull ...:latest`, `docker inspect` o novo digest.
BLUEMAP_IMAGE = (
    "ghcr.io/bluemap-minecraft/bluemap"
    "@sha256:b0f0f36a083e77890f8e0168b00fb3e97a610addb89f3b5adfd785dc2b1cb9db"
)

#: Porta interna onde o webserver do BlueMap serve a UI (padrão do produto).
WEB_PORT = 8100

#: Threads de render + teto de CPU (:attr:`ContainerSpec.cpus`). Balanceado: o
#: render inicial de um mundo grande anda bem, mas o cap isola o jogo — mesmo
#: usando estes núcleos, o container do jogo (à parte) nunca é sufocado. Custo
#: único: depois do primeiro render o sidecar só atualiza o que muda.
#: (TODO: tornar isto ajustável por instância / adaptativo aos núcleos do host.)
RENDER_THREADS = 4

#: ``core.conf`` completo — partimos do padrão do BlueMap e mudamos só o
#: essencial, mantendo todas as chaves para não depender de merge de defaults:
#:  - ``accept-download: true`` → aceite explícito do EULA da Mojang para baixar
#:    os recursos do cliente que texturizam o mapa (opt-in do dono do servidor);
#:  - ``render-thread-count`` → limita o paralelismo do render;
#:  - ``metrics: false`` → nada de telemetria anônima saindo por padrão.
#: O resto (``webserver.conf`` na 8100, ``webapp.conf``, os ``maps/`` das três
#: dimensões) o BlueMap gera sozinho no primeiro boot, já apontando para os
#: volumes montados.
_CORE_CONF = f"""\
# Gerado pelo Aether — mapa-mundi (BlueMap sidecar). Ver ADR 0001.
# Ligar 'accept-download' indica que você aceitou o EULA da Mojang:
# https://account.mojang.com/documents/minecraft_eula
accept-download: true
data: "data"
render-thread-count: {RENDER_THREADS}
update-cooldown: 60
full-update-interval: 1440
scan-for-mod-resources: true
metrics: false
log: {{
  file: "data/logs/debug.log"
  append: false
}}
"""


def map_plan(ctx: LaunchContext) -> MapPlan | None:
    """Plano do sidecar de mapa para uma instância Minecraft.

    Devolve ``None`` enquanto não há mundo para renderizar — sem isso o BlueMap
    sobe, não acha o save e serve um mapa vazio, confundindo o dono.
    """
    world = ctx.root_dir / "world"
    if not world.is_dir():
        return None

    container = ContainerSpec(
        image=BLUEMAP_IMAGE,
        # -r renderiza uma vez, -u segue observando o mundo e atualizando o
        # mapa quando algo muda, -w serve a UI. A config vem de ./config
        # (= /app/config) sem precisar de -c.
        command=["-r", "-u", "-w"],
        volumes=[
            # O mundo do jogo, SÓ-LEITURA: o mapa jamais pode escrever no save.
            VolumeMount(container_path="/app/world", subdir="world", read_only=True),
            # Dados do próprio mapa vivem dentro da instância — assim backup,
            # files e a remoção da instância os enxergam junto com o resto.
            VolumeMount(container_path="/app/config", subdir="aether-map/config"),
            VolumeMount(container_path="/app/web", subdir="aether-map/web"),
            VolumeMount(container_path="/app/data", subdir="aether-map/data"),
        ],
        ports=[PortMapping(container_port=WEB_PORT, protocol="tcp", host_port=WEB_PORT)],
        # Java 25 respeita o cgroup, mas fixamos o heap para caber com folga no
        # teto de memória e não arriscar OOM-kill no meio de um render grande.
        env={"JAVA_TOOL_OPTIONS": "-Xmx1536m"},
        # Isolamento de recursos — o coração do porquê "sidecar" (ADR 0001):
        # o render fica preso a estes núcleos e a 2 GB, o jogo nunca sente.
        cpus=4.0,
        memory="2g",
    )

    return MapPlan(
        container=container,
        web_port=WEB_PORT,
        url_path="/",
        seed_files=(
            MapSeedFile(
                path="aether-map/config/core.conf",
                content=_CORE_CONF,
                keep_existing=True,
            ),
        ),
    )
