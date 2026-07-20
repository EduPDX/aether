#!/usr/bin/env bash
#
# Instalador do Aether para Linux.
#
#   curl -fsSL https://raw.githubusercontent.com/EduPDX/aether/main/install.sh | bash
#
# Reexecutar é seguro: o script atualiza o que já existe em vez de recomeçar, e
# nunca toca no diretório de dados — reinstalar não pode custar os mundos dos
# jogadores.
#
# O clone git não é detalhe de implementação: é ele que permite o botão
# "Atualizar Aether" do painel funcionar depois.

set -euo pipefail

REPO="${AETHER_REPO:-https://github.com/EduPDX/aether.git}"
BRANCH="${AETHER_BRANCH:-main}"
DIR="${AETHER_DIR:-/opt/aether}"
DATA_DIR="${AETHER_DATA_DIR:-/var/lib/aether}"
PORTA="${AETHER_PORT:-8600}"
SERVICO="${AETHER_SERVICE:-aether-core}"
COM_DOCKER=1
COM_NODE=1
DRY_RUN=0

# ------------------------------------------------------------------- saída --
VERMELHO=$'\033[31m'; VERDE=$'\033[32m'; AMARELO=$'\033[33m'; AZUL=$'\033[36m'; FIM=$'\033[0m'
passo()  { printf '%s==>%s %s\n' "$AZUL" "$FIM" "$1"; }
ok()     { printf '%s  ✓%s %s\n' "$VERDE" "$FIM" "$1"; }
aviso()  { printf '%s  !%s %s\n' "$AMARELO" "$FIM" "$1"; }
erro()   { printf '%s  ✗%s %s\n' "$VERMELHO" "$FIM" "$1" >&2; }
morrer() { erro "$1"; exit 1; }

# Em --dry-run nada é executado: serve para revisar e para o teste automatizado
# conferir o plano sem mexer na máquina.
executar() {
  if [ "$DRY_RUN" = "1" ]; then
    printf '    [dry-run] %s\n' "$*"
    return 0
  fi
  "$@"
}

uso() {
  cat <<'AJUDA'
Uso: install.sh [opções]

  --sem-docker      não instala o Docker (instâncias em container ficam indisponíveis)
  --sem-node        não instala Node/pnpm (o painel web não é compilado)
  --dir CAMINHO     onde instalar o código        (padrão: /opt/aether)
  --dados CAMINHO   onde ficam os dados           (padrão: /var/lib/aether)
  --porta NUM       porta do painel               (padrão: 8600)
  --servico NOME    nome da unit do systemd       (padrão: aether-core)
  --branch NOME     branch a instalar             (padrão: main)
  --dry-run         mostra o que faria, sem executar nada
  -h, --help        esta ajuda
AJUDA
}

while [ $# -gt 0 ]; do
  case "$1" in
    --sem-docker) COM_DOCKER=0 ;;
    --sem-node)   COM_NODE=0 ;;
    --dir)        DIR="$2"; shift ;;
    --dados)      DATA_DIR="$2"; shift ;;
    --porta)      PORTA="$2"; shift ;;
    --servico)    SERVICO="$2"; shift ;;
    --branch)     BRANCH="$2"; shift ;;
    --dry-run)    DRY_RUN=1 ;;
    -h|--help)    uso; exit 0 ;;
    *)            erro "opção desconhecida: $1"; uso; exit 1 ;;
  esac
  shift
done

# ------------------------------------------------------------- verificações --
# As verificações de ambiente valem para a instalação de verdade. Em dry-run
# nada é executado, e poder revisar o plano de qualquer máquina é justamente o
# que torna o script testável.
if [ "$DRY_RUN" = "0" ]; then
  [ "$(uname -s)" = "Linux" ] || morrer "este instalador é para Linux (systemd)."
  [ "$(id -u)" = "0" ] \
    || morrer "rode como root (sudo): o script cria uma unit do systemd e escreve em $DIR."
  command -v systemctl >/dev/null 2>&1 \
    || morrer "systemd não encontrado — o Aether é instalado como serviço do systemd."
fi

# ------------------------------------------------- gerenciador de pacotes --
if command -v apt-get >/dev/null 2>&1; then
  GERENCIADOR=apt
elif command -v dnf >/dev/null 2>&1; then
  GERENCIADOR=dnf
elif command -v pacman >/dev/null 2>&1; then
  GERENCIADOR=pacman
elif [ "$DRY_RUN" = "1" ]; then
  GERENCIADOR=apt  # dry-run fora de Linux: assume o mais comum só para exibir o plano
else
  morrer "distribuição não suportada: nenhum apt, dnf ou pacman encontrado.
  Instale git, curl e Python 3.11+ manualmente e rode este script de novo."
fi

instalar_pacotes() {
  case "$GERENCIADOR" in
    apt)    executar apt-get update -qq
            executar env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "$@" ;;
    dnf)    executar dnf install -y -q "$@" ;;
    pacman) executar pacman -Sy --noconfirm --needed "$@" ;;
  esac
}

printf '\n  %sAether%s — instalador\n\n' "$AZUL" "$FIM"
printf '  código:  %s\n  dados:   %s\n  porta:   %s\n  serviço: %s\n\n' \
  "$DIR" "$DATA_DIR" "$PORTA" "$SERVICO"
[ "$DRY_RUN" = "1" ] && aviso "modo dry-run: nada será alterado."

# ------------------------------------------------------------ dependências --
passo "Dependências básicas ($GERENCIADOR)"
instalar_pacotes git curl ca-certificates
ok "git e curl prontos"

passo "uv (gerencia o Python 3.11 que a aplicação exige)"
if command -v uv >/dev/null 2>&1; then
  ok "uv já instalado"
else
  executar bash -c 'curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null'
  ok "uv instalado"
fi
export PATH="$HOME/.local/bin:$PATH"

# O link é criado SEMPRE, não só quando instalamos o uv agora: o instalador do
# uv escreve em ~/.local/bin, que não está no PATH do systemd. Sem o link, a
# atualização pelo painel falha com "No such file or directory" numa máquina
# onde o uv já existia.
if [ "$DRY_RUN" = "0" ]; then
  UV_BIN="$(command -v uv 2>/dev/null || true)"
  if [ -n "$UV_BIN" ] && [ "$UV_BIN" != "/usr/local/bin/uv" ]; then
    ln -sf "$UV_BIN" /usr/local/bin/uv
    ok "uv acessível em /usr/local/bin (PATH do systemd)"
  fi
else
  printf '    [dry-run] ln -sf $(command -v uv) /usr/local/bin/uv\n'
fi

if [ "$COM_NODE" = "1" ]; then
  passo "Node 22 (compila o painel web)"
  if command -v node >/dev/null 2>&1 && [ "$(node -v 2>/dev/null | cut -c2-3)" -ge 20 ] 2>/dev/null; then
    ok "Node $(node -v) já instalado"
  else
    case "$GERENCIADOR" in
      apt)    executar bash -c 'curl -fsSL https://deb.nodesource.com/setup_22.x | bash - >/dev/null'
              instalar_pacotes nodejs ;;
      dnf)    executar bash -c 'curl -fsSL https://rpm.nodesource.com/setup_22.x | bash - >/dev/null'
              instalar_pacotes nodejs ;;
      pacman) instalar_pacotes nodejs npm ;;
    esac
    ok "Node instalado"
  fi
  executar corepack enable
else
  aviso "Node ignorado (--sem-node): o painel web não será compilado."
fi

if [ "$COM_DOCKER" = "1" ]; then
  passo "Docker (servidores em container)"
  if command -v docker >/dev/null 2>&1; then
    ok "Docker já instalado"
  else
    executar bash -c 'curl -fsSL https://get.docker.com | sh >/dev/null'
    ok "Docker instalado"
  fi
  executar systemctl enable --now docker
else
  aviso "Docker ignorado (--sem-docker): só instâncias em processo local funcionarão."
fi

# ------------------------------------------------------------------ código --
if [ -d "$DIR/.git" ]; then
  passo "Atualizando o código em $DIR"
  executar git -C "$DIR" fetch --quiet origin "$BRANCH"
  executar git -C "$DIR" checkout --quiet "$BRANCH"
  # --ff-only: se alguém editou direto no servidor, é melhor falhar aqui e
  # avisar do que sobrescrever o trabalho da pessoa em silêncio.
  executar git -C "$DIR" pull --quiet --ff-only origin "$BRANCH"
  ok "código atualizado"
elif [ -d "$DIR" ] && [ -n "$(ls -A "$DIR" 2>/dev/null || true)" ]; then
  morrer "$DIR existe e não é um clone git.
  Mova ou remova o diretório e rode de novo (os dados em $DATA_DIR não são afetados)."
else
  passo "Clonando o Aether em $DIR"
  executar git clone --quiet --branch "$BRANCH" "$REPO" "$DIR"
  ok "código clonado"
fi

passo "Dependências Python"
executar bash -c "cd '$DIR' && uv sync --all-packages --python 3.11 >/dev/null"
ok "ambiente Python pronto"

if [ "$COM_NODE" = "1" ]; then
  passo "Compilando o painel"
  executar bash -c "cd '$DIR' && corepack pnpm install --silent"
  executar bash -c "cd '$DIR' && corepack pnpm --dir apps/dashboard build >/dev/null"
  ok "painel compilado"
fi

executar mkdir -p "$DATA_DIR"

# ------------------------------------------------------------------ serviço --
passo "Serviço do systemd ($SERVICO)"
UNIT="/etc/systemd/system/$SERVICO.service"
if [ "$DRY_RUN" = "1" ]; then
  printf '    [dry-run] escreveria %s\n' "$UNIT"
else
  cat > "$UNIT" <<UNITFILE
[Unit]
Description=Aether Core — painel de servidores de jogos
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$DIR
Environment=AETHER_DATA_DIR=$DATA_DIR
# O PATH do systemd é enxuto e não inclui ~/.local/bin, onde o uv se instala.
# A atualização pelo painel chama uv e corepack, então eles precisam estar aqui.
Environment=PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$HOME/.local/bin
# Sem AETHER_STATIC_DIR o Core sobe, mas /app responde 404: é esta variável que
# diz onde está o painel compilado.
Environment=AETHER_STATIC_DIR=$DIR/apps/dashboard/dist
ExecStart=$DIR/.venv/bin/uvicorn --factory aether_core.interfaces.http:create_app --host 0.0.0.0 --port $PORTA
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
UNITFILE
fi
executar systemctl daemon-reload
executar systemctl enable --quiet "$SERVICO"
executar systemctl restart "$SERVICO"
ok "serviço habilitado no boot e iniciado"

# ------------------------------------------------------------------ pronto --
if [ "$DRY_RUN" = "0" ]; then
  passo "Aguardando o painel responder"
  for _ in $(seq 1 30); do
    if curl -fsS "http://127.0.0.1:$PORTA/api/v1/health" >/dev/null 2>&1; then
      ok "no ar"
      break
    fi
    sleep 1
  done
fi

IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "127.0.0.1")
printf '\n  %sPronto.%s Acesse o painel em %shttp://%s:%s/app/%s\n' "$VERDE" "$FIM" "$AZUL" "$IP" "$PORTA" "$FIM"
printf '  Na primeira vez ele pede para criar a conta de dono.\n\n'
printf '  Comandos úteis:\n'
printf '    systemctl status %s\n' "$SERVICO"
printf '    journalctl -u %s -f\n\n' "$SERVICO"
