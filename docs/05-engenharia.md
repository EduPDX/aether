# 05 — Engenharia: testes, CI/CD, convenções e documentação

## Estratégia de testes (pirâmide)

| Nível | Ferramenta | Escopo | Meta |
|---|---|---|---|
| **Unitário** | pytest / Vitest / cargo test | `domain` e `application` puros (sem IO); parsers de metadados com fixtures de .jar reais | ≥ 90 % no domain |
| **Contrato de Provider** | pytest + suíte do SDK | O SDK publica uma bateria genérica: qualquer Provider deve passar (`installer instala`, `console_codec parseia`, `sync_rules gera manifesto válido`) — é o que garante que providers de terceiros funcionem | 100 % do contrato |
| **Integração** | pytest + httpx + banco efêmero | Rotas da API contra SQLite em memória; ciclo start/stop com um processo fake | Fluxos críticos |
| **E2E** | Playwright | Dashboard: login → criar instance → console → sync. Launcher: aplicar manifesto contra Core em Docker | Smoke por release |
| **Snapshot de API** | schemathesis + diff do OpenAPI no CI | Toda mudança de contrato aparece no PR explicitamente | Sempre |

Regra de ouro: **a lógica portada do GerenciadorDeMods entra com testes antes** — os .jar reais do usuário (Forge/Fabric/NeoForge, TOML malformado, `${file.jarVersion}`) viram fixtures permanentes.

## CI/CD (GitHub Actions)

**Em todo PR** (paralelo, com cache): Ruff + mypy + pytest (core/sdk/providers) · ESLint + tsc + Vitest (dashboard/packages) · clippy + cargo test (launcher) · geração do OpenAPI + diff de contrato · build de todos os artefatos.

**Release** (por tag, ex.: `core-v0.3.0`):
1. Testes completos + E2E smoke.
2. Build: imagem Docker do Core (ghcr.io), wheels Python, instalador do Launcher (NSIS/msi + AppImage + dmg) via Tauri com assinatura e auto-update.
3. Changelog automático (Conventional Commits → release notes).
4. Canais `stable` e `beta` (o Launcher escolhe o canal de update).

**Branching**: trunk-based — `main` sempre verde, features em branches curtas, release por tag. Sem GitFlow.

## Convenções

- **Conventional Commits** (`feat(core): …`, `fix(launcher): …`) — alimenta changelog e semver.
- **SemVer** por app/pacote; o contrato do SDK tem versão própria e política de depreciação (mín. 2 minors de aviso).
- Código, identificadores e docstrings **em inglês**; documentação de usuário **em português** (público inicial) com estrutura pronta para i18n.
- UI: i18n desde o primeiro componente (pt-BR e en).
- PRs pequenos; todo merge com CI verde; sem commit direto na `main`.

## Documentação contínua

| Tipo | Onde | Quando |
|---|---|---|
| **ADR** (Architecture Decision Record) | `docs/adr/NNNN-titulo.md` | Toda decisão estrutural (banco, protocolo, lib central). Formato: contexto → decisão → consequências |
| Referência de API | Gerada do OpenAPI (Redoc/Scalar) | Automática por build |
| Guia do SDK / "escreva um Provider" | `docs/sdk/` | Junto com a v0.8 |
| Guias de usuário (instalar, criar servidor, configurar sync) | Site Starlight | A partir da v0.4 (quando houver launcher para jogador leigo) |
| README por pacote | Cada `apps/*`, `packages/*`, `providers/*` | Sempre |

## Definição de Pronto (DoD) — vale para toda feature

1. Testes cobrindo o caso feliz e os erros esperados.
2. Endpoint documentado no OpenAPI (docstrings/response models corretos).
3. Auditoria + evento emitido quando a ação altera estado.
4. Permissão RBAC definida para a ação.
5. Sem warning de lint/tipos.
6. Changelog (Conventional Commit correto).
