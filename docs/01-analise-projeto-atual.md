# 01 — Análise do projeto atual (GerenciadorDeMods)

Analisado em 2026-07-16. Código: `server.py` (643 linhas, Python stdlib puro) + `static/index.html` (682 linhas, HTML/CSS/JS vanilla em arquivo único).

## O que ele faz hoje

- Escaneia duas pastas de mods (Servidor / Cliente), extrai metadados de `.jar` (mods.toml Forge/NeoForge, fabric.mod.json), ícones, versão de MC por heurística.
- Interface web local: busca, filtros (loader/status), ordenação, detecção de duplicados, ativar/desativar, lixeira, comparação Cliente × Servidor, cópia entre lados, exportação de lista.
- Cache de metadados por `nome|tamanho|mtime`.

## Pontos fortes (a preservar)

| Ativo | Valor para o Aether |
|---|---|
| **Lógica de extração de metadados de .jar** | É conhecimento de domínio real e testado: parse de mods.toml com fallback regex para TOML malformado, `${file.jarVersion}` via MANIFEST.MF, mapa Forge→MC, heurística de versão por nome de arquivo, extração de ícone com candidatos ordenados. Vira o módulo `content/analyzer` do **Minecraft Provider**. |
| **Comparação Cliente × Servidor** | Feature que Crafty/Pterodactyl não têm. Vira o **Sync Engine** (generalizado por Provider). |
| **Segurança básica correta** | `os.path.basename` contra path traversal, lixeira em vez de exclusão, escrita atômica de cache. Padrões a manter. |
| **UX validada** | Cards com ícone estilo menu do Minecraft, filtros, badges — o usuário já aprovou esse fluxo. Referência de UX para o módulo de mods do Dashboard. |

## Problemas identificados

### Arquiteturais
1. **Monólito de arquivo único** — HTTP, domínio, filesystem e config no mesmo módulo; impossível testar unidades isoladamente.
2. **Acoplado ao Minecraft em todos os níveis** — `FORGE_TO_MC`, "mods", "loader" estão no núcleo, não em um adaptador.
3. **Sem camadas** — handlers HTTP chamam filesystem diretamente; não há domínio separado de infraestrutura.
4. **Estado em arquivos JSON soltos** — `config.json`/`cache.json` sem versionamento de schema, sem migração, cache cresce sem limite.

### Técnicos
5. `http.server` síncrono da stdlib: sem WebSocket, sem streaming, sem autenticação — inviável para console em tempo real e multiusuário.
6. Frontend em arquivo único sem componentes, sem build, estado global manual — não escala para um painel com dock/painéis/editor.
7. Zero testes, zero type hints, zero CI.
8. Específico de Windows (`os.startfile`), caminhos absolutos do usuário embutidos no código (`DEFAULT_CONFIG`).
9. Polling manual (botão Recarregar) em vez de eventos.
10. Sem processo de servidor: só gerencia arquivos; não inicia/para o servidor, não lê console, não mede TPS.

## Oportunidades

- **Nenhum concorrente une painel + launcher + sync.** Crafty/Pterodactyl ignoram o lado do jogador; Prism ignora o lado do servidor. A ponte entre os dois (manifesto de sync assinado pelo servidor, consumido pelo launcher) é o diferencial central do Aether.
- A comparação Cliente × Servidor já provou o conceito em escala real (143 × 146 mods do usuário).
- O conhecimento de parsing de metadados é raro e portável — o mesmo padrão (analisador de conteúdo por Provider) serve para plugins Paper, mods Palworld, workshop do Valheim etc.

## Decisão de migração

**Não evoluir o código atual — extrair e reescrever.** O GerenciadorDeMods continua funcionando intacto como ferramenta do dia a dia até o Aether atingir paridade (v0.1). A lógica de metadados é portada (com testes) para `providers/minecraft/content/`; o resto é reprojetado.

> ⚠️ **Nota operacional:** o repositório do Aether NÃO deve viver dentro do OneDrive (`Documentos`). OneDrive sincroniza `node_modules`, `.git` e artefatos de build, causando lentidão e corrupção de lock files. Recomendação: `C:\Dev\aether`, com backup via Git remoto (GitHub). Esta pasta `Aether\` guarda apenas a documentação de arquitetura até o repositório nascer.
