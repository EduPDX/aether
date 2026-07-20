# Aether Platform

> Painel de administração de servidores de jogos — alternativa moderna ao Crafty
> Controller, Pterodactyl e AMP, com um launcher próprio para os jogadores.

**Status:** v0.5 concluída, rodando em produção num servidor Forge 1.20.1 com
~143 mods e um mundo de 6,4 GB.

| Repositório | Conteúdo |
|---|---|
| **este** | Core (API), Dashboard, SDK e Providers |
| [aether-launcher](https://github.com/EduPDX/aether-launcher) | Launcher desktop do jogador (Tauri + Rust) |

---

## Instalação rápida

Num servidor Linux com systemd (Debian/Ubuntu, Fedora/RHEL ou Arch), um comando:

```bash
curl -fsSL https://raw.githubusercontent.com/EduPDX/aether/main/install.sh | sudo bash
```

O script instala as dependências (uv com o Python 3.11, Node e Docker), clona o
projeto em `/opt/aether`, compila o painel, cria o serviço `aether-core` e o
habilita para subir junto com a máquina. Ao final ele mostra o endereço do
painel — na primeira vez, ele pede para criar a conta de dono.

Rodar de novo **atualiza** a instalação: o diretório de dados (`/var/lib/aether`)
nunca é tocado, então reinstalar não custa mundos nem backups.

### Opções

```bash
curl -fsSL .../install.sh | sudo bash -s -- --sem-docker --porta 9000
```

| Opção | Para que serve |
|---|---|
| `--sem-docker` | não instala o Docker (só instâncias em processo local funcionam) |
| `--sem-node` | não instala Node/pnpm (o painel web não é compilado) |
| `--dir CAMINHO` | onde instalar o código (padrão `/opt/aether`) |
| `--dados CAMINHO` | onde ficam os dados (padrão `/var/lib/aether`) |
| `--porta NUM` | porta do painel (padrão `8600`) |
| `--branch NOME` | branch a instalar (padrão `main`) |
| `--dry-run` | mostra o que faria, sem alterar nada |

### Atualizar depois

Em **Configurações → Sistema** existe o botão **Atualizar Aether**: ele busca a
versão mais recente da `main`, reinstala dependências, recompila o painel e
reinicia o serviço, copiando o banco de dados antes. Se alguém tiver editado
arquivos direto no servidor, a atualização é recusada e mostra quais são — em
vez de sobrescrever o trabalho em silêncio.

O botão exige que a instalação seja um clone git, que é o que o `install.sh`
deixa pronto.

## O problema

Quem administra um servidor de Minecraft modado vive com três ferramentas que
não conversam: um painel para ligar o servidor, um launcher para o jogador
entrar, e um grupo de WhatsApp para mandar o zip de mods toda vez que algo muda.

O Aether é as três coisas no mesmo lugar — e a ponte entre elas (o manifesto de
sincronização assinado pelo servidor e consumido pelo launcher) é o que nenhum
concorrente faz.

## O que já funciona

**Servidor**
- Ligar, parar, reiniciar e matar o processo, com detecção de crash
- Console em tempo real com histórico e envio de comandos
- 45 opções do `server.properties` em formulário, com as avançadas recolhidas
- Ícone do servidor: envie qualquer imagem e ela vira o PNG 64×64 que o jogo exige
- Métricas de CPU, memória e disco, do host e do processo do servidor

**Mods**
- Listagem com ícone, versão, loader, dependências e detecção de duplicados
- Conjuntos separados para **servidor** e **cliente**, com diff entre os dois —
  é o que responde "por que o jogo crasha ao entrar no mundo?" antes de crashar
- Catálogo Modrinth: navegar por popularidade, filtrar por categoria e loader,
  instalar com **resolução de dependências** e detectar atualizações por hash
- Envio manual de `.jar` por upload

**Operação**
- Gerenciador de arquivos estilo Explorer: ícones grandes, seleção múltipla,
  download de pasta em zip e editor Monaco com realce de sintaxe
- Backups com agendamento, retenção e restauração — pausa a escrita do mundo
  antes de copiar e cria um backup de segurança antes de restaurar
- Tarefas agendadas: reinício com aviso no chat, e comandos por horário
- Usuários com papéis (owner/admin/moderator/viewer) e registro de auditoria

**Jogador**
- Perfil de sincronização publicado pelo servidor, assinado com Ed25519
- O [launcher](https://github.com/EduPDX/aether-launcher) baixa só o que mudou,
  instala Java e Forge, e abre o jogo
- `aether-sync`, um CLI que sincroniza uma pasta pelo terminal, sem o launcher

**Aparência**
- 20 temas (14 escuros, 6 claros) com prévia ao passar o mouse
- 6 pacotes de ícone para o gerenciador de arquivos
- 7 tipos de gráfico, separados por finalidade — série temporal para CPU e
  memória, categoria para contagens

## Arquitetura em uma frase

**O Core não conhece nenhum jogo.** Minecraft é o primeiro Provider; tudo que é
específico de um jogo entra por contratos do SDK.

```
┌────────────┐   REST/WS     ┌──────────────────────────┐
│ Dashboard  │──────────────▶│                          │
└────────────┘               │           CORE           │   entry points
┌────────────┐ REST público  │    FastAPI + SQLite      │◀────────────┐
│  Launcher  │──────────────▶│   (não conhece jogos)    │             │
└────────────┘               └──────────────────────────┘      ┌──────────────┐
                                                               │  Providers   │
                                                               │  (minecraft) │
                                                               └──────────────┘
```

Um Provider declara o que sabe fazer implementando contratos opcionais:

| Contrato | O Provider informa |
|---|---|
| `ContentAnalyzer` | como ler um mod e extrair metadados |
| `SupportsLaunch` | como subir o servidor e ler o console |
| `SupportsConfig` | schema de configuração — o Dashboard gera o formulário |
| `SupportsBackup` | o que entra no backup e como pausar a escrita |
| `ContentSource` | catálogos de mods disponíveis |

Adicionar Palworld ou Factorio é escrever um Provider, não reescrever o sistema.

### Camadas

O Core segue Clean Architecture — as dependências apontam só para dentro:

```
domain/           regras puras, sem I/O
application/      casos de uso; define as portas do que precisa de fora
infrastructure/   SQLAlchemy, psutil, httpx, Argon2/JWT
interfaces/http/  FastAPI — rotas finas, sem regra de negócio
```

## Stack

| Camada | Tecnologia | Por quê |
|---|---|---|
| Core | Python 3.11+, FastAPI, SQLAlchemy 2, SQLite | Ecossistema de parsing de mods; SQLite sem servidor separado |
| Dashboard | React 19, Vite, Tailwind v4, TanStack Query | Temas por CSS variables, sem biblioteca de componentes |
| Launcher | Tauri 2 + Rust | Executável pequeno; sem Electron na máquina do jogador |
| Workspace | uv (Python) + pnpm (Node) | Instalação reprodutível |

## Desenvolvimento

Requisitos: Python 3.11+, [uv](https://docs.astral.sh/uv/), Node 20+, pnpm.

```bash
# Backend
uv sync --all-packages
uv run pytest                        # suíte completa
uv run ruff check .
uv run python -m aether_core         # API em http://127.0.0.1:8600 (docs em /api/docs)

# Dashboard (com o Core rodando)
pnpm install
pnpm --dir apps/dashboard dev        # http://localhost:5173, proxy /api → 8600
```

No primeiro acesso a interface pede para criar a conta de dono da instalação.

O banco fica em `~/.local/share/Aether/` (Linux) ou `%LOCALAPPDATA%\Aether\`
(Windows); mude com `AETHER_DATA_DIR`. As migrações rodam sozinhas no start.

### Estrutura

```
apps/core/            API, orquestração e host de plugins
apps/dashboard/       interface web
apps/cli/             aether-sync: sincroniza uma pasta pelo terminal
packages/sdk/         contratos entre o Core e os Providers
providers/minecraft/  mods, launch, console, config, backup, Modrinth
docs/                 arquitetura, stack, dados, engenharia e roadmap
```

## Documentação

| Documento | Conteúdo |
|---|---|
| [01 — Análise do projeto atual](docs/01-analise-projeto-atual.md) | Origem do projeto e o que foi aproveitado |
| [02 — Arquitetura](docs/02-arquitetura.md) | Módulos, contrato de Provider, comunicação |
| [03 — Stack](docs/03-stack.md) | Tecnologias e alternativas consideradas |
| [04 — Dados e API](docs/04-dados-e-api.md) | Modelo de banco e design da API |
| [05 — Engenharia](docs/05-engenharia.md) | Testes, CI/CD e convenções |
| [06 — Roadmap](docs/06-roadmap.md) | v0.1 → v1.0 com critérios de pronto |
| [CLAUDE.md](CLAUDE.md) | Guia para agentes: decisões não óbvias e armadilhas |
| [apps/LAUNCHER.md](apps/LAUNCHER.md) | A fronteira entre este repositório e o do launcher |

## Princípios inegociáveis

1. **O Core nunca importa um Provider.** A dependência é sempre no sentido inverso.
2. **API-first.** Dashboard e Launcher são apenas clientes da mesma API.
3. **Local-first.** Tudo funciona sem nuvem; a nuvem seria uma camada opcional.
4. **Cada versão entrega algo usável** — nunca meses de infraestrutura sem nada
   na tela.

## O que falta

- **Assinatura de código do launcher** — o Windows Defender o põe em quarentena
  como falso positivo, o que hoje impede distribuir para os jogadores
- **Login Microsoft** no launcher (só modo offline por enquanto)
- **CurseForge** — o contrato está pronto, falta a chave de API
- **Agent remoto**, métricas de TPS via RCON e o segundo Provider (v0.6 → v0.9)

Roadmap completo em [docs/06-roadmap.md](docs/06-roadmap.md).
