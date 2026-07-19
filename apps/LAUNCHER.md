# O launcher mudou de repositório

O Aether Launcher agora vive em **[EduPDX/aether-launcher](https://github.com/EduPDX/aether-launcher)**.

Ele saiu do monorepo porque não compartilha código com ele — é Rust/Tauri, tem
seu próprio ciclo de release (o jogador atualiza o executável, não o servidor) e
acoplava ~10 GB de artefatos de build do Cargo ao repositório de quem só quer
mexer no painel.

## A fronteira entre os dois

O launcher depende de **três endpoints públicos** do Core e de nada mais:

```
GET /api/v1/public/sync/{profile_id}         → manifesto assinado (Ed25519)
GET /api/v1/public/sync/{profile_id}/file    → download de um arquivo do manifesto
GET /api/v1/public/instances/{id}/status     → status do servidor
```

Definidos em `apps/core/src/aether_core/interfaces/http/routes/public.py`, com
o formato do manifesto em `apps/core/src/aether_core/application/sync.py`.

**Mudar o formato desses três quebra launchers já instalados na máquina dos
jogadores**, que não se atualizam sozinhos. Trate como contrato versionado: se
precisar mudar de forma incompatível, adicione ao lado em vez de alterar.
