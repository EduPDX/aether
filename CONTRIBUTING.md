# Contribuindo

## Preparar o ambiente

Requisitos: Python 3.11+, [uv](https://docs.astral.sh/uv/), Node 20+, pnpm.

```bash
git clone https://github.com/EduPDX/aether.git
cd aether
uv sync --all-packages
pnpm install
```

Suba as duas metades em terminais separados:

```bash
uv run python -m aether_core      # API em http://127.0.0.1:8600
pnpm --dir apps/dashboard dev     # interface em http://localhost:5173
```

Abra `http://localhost:5173` — na primeira vez ele pede para criar a conta de
dono da sua instalação local.

### Você não precisa de um servidor de Minecraft para trabalhar

Quase tudo funciona com uma pasta qualquer no lugar de um servidor real. Crie
uma instância apontando para um diretório de teste:

```bash
mkdir -p /tmp/servidor-teste/mods /tmp/servidor-teste/world/region
printf 'level-name=world\nmax-players=20\n' > /tmp/servidor-teste/server.properties
```

Mods, arquivos, config, backups e catálogo funcionam assim. Só **ligar o
servidor** e o **console** precisam de um servidor de verdade — para isso, um
Forge/Vanilla baixado localmente já basta.

## Rodar os testes

```bash
uv run pytest                                          # tudo
uv run pytest apps/core/tests/test_backups_api.py      # um arquivo
uv run pytest -k "backup"                              # por nome
uv run ruff check . --fix && uv run ruff format
cd apps/dashboard && npx tsc --noEmit                  # typecheck do front
```

Rode sempre da raiz do repositório: `testpaths` é relativo a ela.

O CI roda exatamente isso — se passa local, passa lá.

## Fluxo de trabalho

O `main` está sempre implantável. Trabalhe em branch e abra pull request:

```bash
git checkout -b feat/nome-curto
# ... commits ...
git push -u origin feat/nome-curto
gh pr create
```

Force-push e exclusão do `main` estão bloqueados no GitHub — não por
desconfiança, mas porque um `--force` acidental apaga trabalho de outra pessoa
sem aviso.

### Commits

Mensagens em **português**, no formato `tipo(escopo): resumo`:

```
feat(dashboard): filtro por categoria no catálogo
fix: download de pastas grandes não funcionava
```

O corpo importa mais que o título quando a mudança não é óbvia. Explique **por
que**, especialmente se você tomou uma decisão que parece estranha de fora —
alguém vai reverter daqui a seis meses achando que foi descuido.

## Antes de escrever código

Duas perguntas que evitam retrabalho:

**1. Isso é do jogo ou da plataforma?** O Core não conhece Minecraft. Se a
funcionalidade depende de como o Minecraft faz as coisas, o contrato vai no SDK
(`packages/sdk/`) e a implementação no provider. Um `if provider_id ==
"minecraft"` dentro do Core é sinal de que a modelagem está errada.

**2. Onde essa regra deveria morar?** Lógica pura vai em `domain/` — testável
sem banco nem rede, e é onde estão os erros que passam despercebidos. A rota
HTTP deve ser fina: recebe, delega, devolve.

Leia o [CLAUDE.md](CLAUDE.md) antes de mexer em backup, métricas, download ou
agendamento. Há decisões contraintuitivas ali que já custaram depuração — e o
teste que as protege pode parecer errado até você entender o motivo.

## O que você não vai conseguir fazer (e tudo bem)

O **deploy é manual e sai da máquina do dono do projeto**: ele empacota o código,
envia por SSH para um LXC no Proxmox da rede local dele e reinicia o serviço.
Não há pipeline de deploy automático, e a chave de acesso não está no
repositório.

Na prática: seu trabalho termina no pull request. Depois de aprovado, o deploy
para o servidor real é feito por quem tem a chave.

## Escopo dos repositórios

| Repositório | O que fica aqui |
|---|---|
| [aether](https://github.com/EduPDX/aether) | Core (API), Dashboard, SDK, Providers |
| [aether-launcher](https://github.com/EduPDX/aether-launcher) | Launcher do jogador (Tauri + Rust) |

Os dois se falam por **três endpoints públicos** documentados em
[apps/LAUNCHER.md](apps/LAUNCHER.md). Mudança no formato deles é mudança de
contrato: quebra launchers já instalados na máquina dos jogadores, que não se
atualizam sozinhos. Se precisar mudar, adicione ao lado em vez de alterar.
