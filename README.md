# Aether Platform

> Plataforma modular e extensível para administração de servidores de jogos, launchers e sincronização — pensada para durar anos.

**Status:** fase de arquitetura (nenhum código de produção escrito ainda).

## O que é

Um ecossistema único que substitui, para o administrador de servidores de jogos:

| Ferramenta atual | Módulo do Aether |
|---|---|
| Crafty Controller / Pterodactyl / AMP | **Dashboard + Core + Agent** |
| Prism Launcher / TLauncher / SKLauncher | **Aether Launcher** |
| Scripts manuais de sync de mods | **Sync Engine** (manifesto + hash diferencial) |
| Nada (inexistente no mercado) | Comparação Cliente × Servidor, análise por IA |

O Minecraft é apenas o **primeiro Provider**. O Core não conhece nenhum jogo — Palworld, Terraria, Valheim, Rust, Factorio etc. entram como Providers sem reescrever o sistema.

## Documentação

| Documento | Conteúdo |
|---|---|
| [01 — Análise do projeto atual](docs/01-analise-projeto-atual.md) | O que o GerenciadorDeMods tem de bom, problemas e o que aproveitar |
| [02 — Arquitetura](docs/02-arquitetura.md) | Princípios, módulos, contrato de Provider, comunicação, estrutura de pastas |
| [03 — Stack tecnológica](docs/03-stack.md) | Tecnologias escolhidas e por quê (com alternativas consideradas) |
| [04 — Dados e API](docs/04-dados-e-api.md) | Modelo de banco de dados e design da API REST/WebSocket |
| [05 — Engenharia](docs/05-engenharia.md) | Testes, CI/CD, convenções, documentação contínua |
| [06 — Roadmap](docs/06-roadmap.md) | Versões v0.1 → v1.0 com critérios de pronto |

## Princípios inegociáveis

1. **O Core nunca importa um Provider.** Providers dependem do Core, nunca o contrário.
2. **API-first.** Toda funcionalidade nasce como API; Dashboard e Launcher são apenas clientes.
3. **Local-first.** Tudo funciona sem nuvem; a nuvem é uma camada opcional futura.
4. **Cada versão do roadmap entrega valor usável** — nunca seis meses de infraestrutura sem nada na tela.
5. **Decisões registradas.** Toda decisão arquitetural relevante vira um ADR em `docs/adr/`.
