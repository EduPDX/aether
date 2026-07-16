# 03 — Stack tecnológica

Cada escolha lista as alternativas consideradas e o porquê da decisão. Mudanças aqui exigem um ADR.

## Core + Agent — **Python 3.12 + FastAPI**

| Critério | Decisão |
|---|---|
| Framework web | **FastAPI** — async nativo, WebSocket, OpenAPI gerado automaticamente (pilar do API-first), validação com Pydantic |
| ORM / migrações | **SQLAlchemy 2 (async) + Alembic** |
| Validação/serialização | **Pydantic v2** |
| Processos | `asyncio.subprocess` + supervisor próprio no domínio |
| Métricas de sistema | `psutil`; Docker via SDK oficial |
| Empacotamento | **uv** (gerenciador/lock), PyInstaller para distribuir o Agent como .exe |

**Por que Python e não…**
- **Go**: binário único e footprint menor seriam ideais para o Agent, mas dividiria o projeto em duas linguagens de backend desde o dia 1. O Agent começa em Python (reusa domínio e SDK); se o footprint doer, o Agent — e só ele — pode ser reescrito em Go atrás do mesmo protocolo WS (a arquitetura permite exatamente isso).
- **Node/NestJS**: unificaria com o frontend, mas o ecossistema de manipulação de processos/arquivos/binários e o ecossistema de IA (para o módulo futuro) são mais maduros em Python. Além disso o conhecimento de domínio existente (parser de mods) já está em Python.
- Continuidade: o autor do projeto já trabalha em Python — velocidade de evolução importa mais que perfeição teórica.

## Dashboard — **React 18 + TypeScript + Vite**

| Peça | Escolha | Motivo |
|---|---|---|
| UI kit | **Tailwind CSS + shadcn/ui (Radix)** | Componentes acessíveis, copiáveis e tematizáveis por tokens — base do design system em `packages/ui` |
| Dados | **TanStack Query** + cliente gerado do OpenAPI | Cache/refetch automáticos; o cliente TS é gerado do schema — contrato sempre sincronizado |
| Estado local | **Zustand** | Simples, sem boilerplate |
| Console | **xterm.js** | Padrão da indústria (VS Code usa) |
| Editor | **Monaco** | Editor do VS Code; syntax highlight para TOML/YAML/properties |
| Realtime | WebSocket nativo com camada de tópicos própria | Evita lock-in em socket.io |
| Gráficos | **Recharts** (métricas) | Suficiente e leve; troca fácil se precisar |

## Launcher — **Tauri 2 (Rust) + React/TS**

- Binário pequeno (~10 MB), baixo consumo de RAM (webview do sistema), auto-update embutido, assinatura de binários.
- Operações pesadas (download paralelo, SHA256, extração, spawn do jogo) em Rust — exatamente o que Rust faz melhor.
- UI compartilha `packages/ui` com o Dashboard (mesma identidade visual).
- **Alternativa rejeitada**: Electron — 15× maior, mais RAM; para um launcher que jogadores vão manter aberto junto do jogo, footprint importa.

## Banco de dados — **SQLite (padrão) → PostgreSQL (opcional)**

- SQLite (WAL) para instalação de um clique — perfil de 90% dos usuários (mesma decisão do Crafty).
- SQLAlchemy async + Alembic mantêm o mesmo código para PostgreSQL quando houver multiusuário pesado ou multi-node.
- Dados específicos de Provider em colunas JSON (`provider_data`) — Providers não criam tabelas no Core.
- Cache de metadados de conteúdo (o atual `cache.json`) vira tabela com chave `sha256` (não mais nome|mtime) e limpeza por LRU.

## Infra e qualidade

| Área | Ferramenta |
|---|---|
| Monorepo | **pnpm workspaces** (TS) + **uv workspaces** (Python); **Turborepo** para orquestrar builds TS |
| Lint/format | **Ruff** (Python), **ESLint + Prettier** (TS), **rustfmt/clippy** (Rust) |
| Tipos | **mypy --strict** no `domain`/`application`; `tsc --noEmit` no CI |
| Testes | pytest, Vitest, Playwright, cargo test — detalhes em [05-engenharia.md](05-engenharia.md) |
| CI/CD | **GitHub Actions** |
| Container | Dockerfile oficial do Core + docker-compose de referência |
| Docs site | **Astro Starlight** (futuro, v0.8+) |

## Versões mínimas suportadas

- Python 3.11+ (tomllib nativo), Node 20+, Rust stable.
- SO alvo do Core/Agent: Windows 10+, Linux (Ubuntu 22.04+/Debian 12+); launcher: Windows/Linux/macOS.
