# 06 — Roadmap

Princípios do roadmap:
- **Toda versão termina com algo que você usa no seu servidor real** (Forge 1.20.1, 143 mods). Seu servidor é o ambiente de validação contínua.
- O GerenciadorDeMods atual continua em uso até a v0.1 atingir paridade.
- Estimativas são de **escopo relativo**, não datas — projeto de longo prazo com dedicação variável.

---

## v0.1 — Fundação + paridade de mods `[escopo: M]`
> "O GerenciadorDeMods renasce dentro da arquitetura definitiva."

- Monorepo, CI, lint, testes, uv/pnpm workspaces.
- Core mínimo: FastAPI, SQLite + Alembic, config em banco, OpenAPI, barramento de eventos interno.
- SDK v0: contrato `ContentAnalyzer` + `ContentType` + suíte de contrato.
- **Minecraft Provider v0**: analisador de conteúdo portado (mods.toml/NeoForge/fabric.mod.json, ícones, heurísticas) **com testes usando seus .jar reais**.
- Instance "somente pastas" (sem processo ainda): registra as pastas Servidor/Cliente como duas instances.
- Dashboard shell: layout dock/sidebar, tema escuro com tokens, command palette, módulo **Conteúdo** (paridade total: busca, filtros, toggle, lixeira, duplicados, comparação, cópia, export).
- ✅ **Pronto quando:** você desliga o GerenciadorDeMods e não sente falta de nada.

## v0.2 — Processos e console `[M]`
> "O Aether liga e desliga o servidor."

- Supervisor de processos no Core (Agent embutido): start/stop/restart/kill, crash detect + auto-restart com backoff.
- `LaunchSpec` + `ConsoleCodec` no SDK; flavors Forge e Vanilla no Provider (instalação manual apontando dir existente).
- Console em tempo real no Dashboard (xterm.js + WS), histórico de log, envio de comandos.
- Estados de instance + eventos (`instance.started`, `instance.crashed`…).
- ✅ Você administra o servidor Forge de verdade pelo Aether (subir, console, parar).

## v0.3 — Usuários, arquivos e configuração `[M]`
- Auth completa (Argon2, JWT+refresh, setup do owner), RBAC granular, auditoria, tokens de API.
- Explorador de arquivos (sandbox por instance) + editor Monaco com highlight (properties/TOML/YAML/JSON).
- `ConfigSchema` no SDK + forms gerados; `server.properties` do Minecraft como primeiro schema.
- Rate limit, problem+json, hardening da API.
- ✅ Você cria um usuário "moderador" que só vê console, e edita configs pelo painel.

## v0.4 — Sync Engine + Launcher MVP `[G — o diferencial]`
- `SyncRules`/manifesto assinado (Ed25519) no Core; publicação por canal (stable/beta); CDN local de arquivos.
- **Launcher Tauri MVP**: perfil do servidor, download diferencial paralelo com SHA256 e retomada, instalação automática de Java (Adoptium), instalação do Forge, launch do jogo, MSA login (+ modo offline), reparo de instalação.
- Endpoints públicos: status do servidor, manifesto, notícias.
- ✅ **Um jogador do seu servidor instala o launcher, clica "Entrar" e o jogo abre sincronizado.** (Adeus TLauncher + mandar zip de mods.)

## v0.5 — Conteúdo inteligente `[M]`
- `ContentSource`: busca/instalação Modrinth + CurseForge (API key), resolução de dependências, detecção de updates de mods, incompatibilidades conhecidas.
- Backups: manual + retenção, restore, porta `StorageBackend` (local).
- Scheduler (cron): restart, backup, comando.
- ✅ Você atualiza os 143 mods com relatório de dependências, e o servidor faz backup sozinho às 4h.

## v0.6 — Monitoramento e Agent remoto `[M]`
- Métricas de node (CPU/RAM/disco/rede, psutil) e de instance (TPS/jogadores via `MetricsExtractor` + RCON/query).
- Dashboards de métricas (Recharts), retenção com downsampling, alertas básicos (evento → notificação).
- **Agent standalone**: mesmo código, WS outbound, registro por token — administra servidor em outra máquina/VPS. Suporte Docker (instance containerizada).
- ✅ Gráfico de TPS do seu servidor com alerta de queda; possibilidade de mover o servidor para uma VPS.

## v0.7 — Mundos, desempenho e primeira IA `[M]`
- Gerenciador de mundos (backup/troca/upload, pre-generation via provider).
- Análise de crash: parser de crash-report do Minecraft + **`AIAnalyzer`** (análise de log/crash com LLM, diagnóstico e sugestão de correção — primeiro caso de uso de IA).
- Perfil de desempenho (integração spark quando presente).
- ✅ O servidor crashou → o Aether diz qual mod provavelmente causou e o que fazer.

## v0.8 — Extensibilidade pública `[G]`
- SDK 1.0-beta publicado (PyPI) + guia "escreva um Provider"; loader de plugins com sandbox de permissões declaradas.
- Widgets de dashboard registráveis por plugins; temas por tokens; webhooks (Discord etc.).
- Flavors restantes do Minecraft: Paper, Purpur, Spigot, Bukkit, Velocity, Waterfall, BungeeCord (proxies com visão de rede multi-instance).
- ✅ Um terceiro consegue criar um provider/plugin sem tocar no repositório.

## v0.9 — Segundo Provider (prova da tese) `[M]`
- Implementar **Terraria** ou **Palworld** usando apenas o SDK público. Cada limitação encontrada gera correção no contrato **antes** do 1.0 congelar.
- Auditoria de segurança, testes de carga, migrações de upgrade testadas, i18n en completa.
- ✅ Dois jogos rodando lado a lado no mesmo painel.

## v1.0 — Release público `[G]`
- Site + docs de usuário, instaladores polidos (one-click Windows, Docker, systemd), auto-update em todos os apps, canal beta, telemetria opt-in anônima.
- Congelamento do contrato SDK 1.0 e da API v1.
- ✅ Qualquer administrador instala sem sua ajuda.

---

## Pós-1.0 (visão)
Marketplace (registro de extensões assinadas) → Mobile (API já pronta; push via eventos) → Cloud (login, backup remoto, sync entre máquinas) → Chat launcher↔servidor → mais Providers (Valheim, Rust, ARK, Factorio, Zomboid, CS2, Satisfactory).

## Riscos conhecidos (postura de CTO)

| Risco | Mitigação |
|---|---|
| Escopo gigantesco / burnout | Versões pequenas com valor real; nunca duas frentes G simultâneas; o seu servidor como cliente nº 1 mantém o foco |
| Abstração de Provider errada (descoberta tarde) | v0.9 existe exatamente para isso: segundo jogo antes de congelar contrato |
| CurseForge ToS / API key | Só via API oficial; Modrinth como fonte preferencial |
| Distribuição do client Minecraft | Launcher baixa somente de fontes oficiais; manifesto nunca embute binários da Mojang |
| Jogadores com conta pirata (TLauncher) hoje | Launcher suporta MSA (caminho correto) e modo offline; decisão de política é do admin do servidor |
| OneDrive corromper repo | Repo em `C:\Dev\aether` + GitHub desde o commit 1 |
