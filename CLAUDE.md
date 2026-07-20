# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## O que é

**Aether Platform** — painel de administração de servidores de jogos, alternativa
ao Crafty Controller / Pterodactyl / AMP. Roda hoje num servidor Forge 1.20.1
real com ~143 mods.

O launcher do jogador vive em outro repositório:
[EduPDX/aether-launcher](https://github.com/EduPDX/aether-launcher). A fronteira
entre os dois está documentada em [apps/LAUNCHER.md](apps/LAUNCHER.md).

## Comandos

```bash
uv sync --all-packages          # dependências Python (workspace uv)
uv run pytest                   # suíte inteira
uv run pytest apps/core/tests/test_backups_api.py -q     # um arquivo
uv run pytest -k "cpu"          # por nome
uv run ruff check . --fix
uv run ruff format

pnpm install
pnpm --dir apps/dashboard dev       # dev server na 5173, proxy /api → 127.0.0.1:8600
pnpm --dir apps/dashboard build
# Typecheck. Tem de ser `tsc -b`: o tsconfig.json da raiz é só um mapa de
# referências (`"files": []`), então `tsc --noEmit` passa sempre — sem checar
# arquivo nenhum. Use `--force` para não confiar no cache incremental.
cd apps/dashboard && npx tsc -b --force

# Core local
AETHER_DATA_DIR=/tmp/aether-dev uv run uvicorn \
  --factory aether_core.interfaces.http:create_app --port 8600
```

CI roda ruff, `ruff format --check`, pytest e o build do dashboard.

**Se `uv` não estiver no PATH** — acontece quando o venv foi criado pelo uv mas o
executável não ficou acessível na sessão — use o Python do venv direto, que é o
mesmo ambiente:

```bash
./.venv/Scripts/python.exe -m pytest        # Windows
./.venv/bin/python -m pytest                # Linux
```

Rode sempre a partir da raiz do repositório: `testpaths` no `pyproject.toml` é
relativo a ela, e `cd apps/dashboard` antes de um comando Python faz o pytest
não achar nada.

## Arquitetura

### Camadas (Clean Architecture)

Dentro de `apps/core/src/aether_core/`, as dependências apontam só para dentro:

```
domain/          regras puras, sem I/O — é onde mora a lógica que dá errado em silêncio
application/     casos de uso; define Protocols (portas) do que precisa de fora
infrastructure/  SQLAlchemy, psutil, httpx, Argon2/JWT — implementa as portas
interfaces/http/ FastAPI: rotas finas, sem regra de negócio
```

Testar `domain/` não precisa de banco nem de rede, e é onde estão os testes mais
valiosos (janela de agendamento, retenção de backup, comparação de versões).

### O ponto central: o Core não conhece nenhum jogo

Minecraft é só o primeiro **Provider**. Tudo que é específico de jogo entra por
contratos do SDK (`packages/sdk/`), descobertos por entry point
`aether.providers`:

| Contrato | O provider declara |
|---|---|
| `ContentAnalyzer` / `ContentType` | como ler um mod e onde ele mora |
| `SupportsLaunch` / `ConsoleCodec` | como subir o servidor e ler o console |
| `SupportsConfig` | schema de configuração → o Dashboard gera o formulário |
| `SupportsBackup` | o que entra no backup e como pausar a escrita |
| `ContentSource` | catálogos de mods (Modrinth) |

**Ao adicionar funcionalidade, pergunte primeiro se ela é do jogo ou da
plataforma.** Se for do jogo, o contrato vai no SDK e a implementação no
provider — nunca um `if provider_id == "minecraft"` no Core.

### Frontend

`apps/dashboard/` — React 19 + Vite + Tailwind v4 com CSS variables. Não há
biblioteca de componentes: `components/ui.tsx` tem as primitivas (`Panel`,
`StatTile`, `Button`, `Segmented`, `Modal`). Temas trocam as CSS variables em
tempo de execução (`lib/themes.ts`); gráficos são SVG artesanal em
`components/BarChart.tsx`.

`components/Dialog.tsx` substitui `confirm`/`alert`/`prompt` do navegador com
uma API de promessa (`await dialog.confirm({...})`). **Não use os nativos.**

## Decisões que não são óbvias

Estas custaram depuração. Mudá-las sem entender o motivo reintroduz o bug:

- **Produção roda Python 3.11.** `Path.glob("x/**")` devolve só diretórios até o
  3.12 e passou a incluir arquivos no 3.13. Um dev em Python novo escreve código
  que funciona na máquina dele e falha em silêncio no servidor — foi assim que
  o backup quase saiu vazio. Ver `application/backups.py::collect_files`.
- **`psutil.Process` precisa ser reaproveitado entre coletas.** `cpu_percent()`
  é um delta desde a leitura anterior *daquele objeto*; recriar devolve 0.0 para
  sempre. E o valor é por núcleo: 324% em 10 núcleos são 32% da máquina — por
  isso a API expõe `cpu_percent` e `cpu_percent_total`.
- **Nome de arquivo de backup leva um discriminador.** O carimbo tem resolução
  de segundos; sem ele o backup de segurança do restore sobrescrevia o backup
  que estava sendo restaurado.
- **Downloads grandes vão por link assinado**, não por `fetch` + Blob: o Blob
  materializa o arquivo na memória da aba e morre num mundo de 6 GB. Zip de
  pasta é gerado em fluxo (`files.py::stream_zip`).
- **Troca de senha incrementa `token_epoch`**, gravado no JWT. Sem isso o token
  antigo continuaria valendo 7 dias e a troca daria falsa sensação de segurança.
- **Agendamento ancora no horário, não em intervalo.** "A cada 24h" faz a tarefa
  das 4h deslizar até rodar de tarde. Ver `domain/tasks.py::previous_occurrence`.

## Convenções

- Código, comentários e mensagens de commit em **português**; nomes de símbolo
  em inglês quando já existiam assim.
- Comentário explica **por quê**, não o quê. Se descreve o óbvio, apague.
- Teste tem nome que descreve o comportamento e docstring com o motivo quando o
  caso é sutil.
- Migrações Alembic em `infrastructure/migrations/versions/`, numeradas em
  sequência. Rodam sozinhas no start do Core.

## Deploy

Produção é um LXC no Proxmox (endereço na rede local do dono), código em `/opt/aether`,
serviço systemd `aether-core`. O deploy empacota `git archive` + o `dist/` do
dashboard, envia por `pct push` e reinicia o serviço. O dashboard é servido pelo
próprio Core em `/app`.
