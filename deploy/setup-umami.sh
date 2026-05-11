#!/bin/bash
# Setup idempotente do Umami analytics (self-hosted) em /opt/umami.
#
# O que faz:
#   - Cria system user `umami` e diretorio /opt/umami
#   - Instala Node 22 (NodeSource) + pnpm se ausentes
#   - Cria DB+role `umami` no Postgres local (senha aleatoria persistida)
#   - Gera APP_SECRET + HASH_SALT (uma vez, persistidos em /etc/umami.*)
#   - Escreve /etc/umami.env (root:umami 0640) com DATABASE_URL, secrets,
#     BASE_PATH=/_traffic/analytics, PORT=3001, HOSTNAME=127.0.0.1
#   - Faz git clone --depth 1 do umami-software/umami no tag UMAMI_VERSION
#   - pnpm install --frozen-lockfile + pnpm run build (com BASE_PATH baked in;
#     skip se ja built no mesmo tag+BASE_PATH)
#   - pnpm run update-db (prisma migrate deploy)
#   - Instala cruza-umami.service e (re)inicia
#
# Pos-deploy (manual, uma vez):
#   1. Acessar https://transparenciapb.org/_traffic/analytics/login.
#      Primeiro o nginx pede basic-auth (.htpasswd-traffic, mesmo de
#      /_traffic/). Depois o Umami pede login (admin / umami).
#   2. Profile -> Change password.
#   3. Settings -> Websites -> Add -> nome=TransparenciaPB,
#      domain=transparenciapb.org -> salvar.
#   4. Copiar o Website ID gerado pro secret UMAMI_WEBSITE_ID no ENV_FILE
#      do GitHub Actions e re-deploy do web frontend.
#
# Variaveis de ambiente opcionais:
#   UMAMI_VERSION    tag do repo umami-software/umami (default: v3.1.0)
#   UMAMI_DIR        diretorio de instalacao (default: /opt/umami)
#   UMAMI_USER       system user que roda o servico (default: umami)
#   UMAMI_DB         nome do DB (default: umami)
#   UMAMI_DB_USER    role Postgres (default: umami)
#   UMAMI_BASE_PATH  path prefix HTTP (default: /_traffic/analytics).
#                    Trocar exige rebuild (BASE_PATH eh baked in pelo
#                    Next.js no `pnpm run build`).
#
# Uso (na VM, como root):
#   sudo bash deploy/setup-umami.sh

set -euo pipefail

UMAMI_VERSION="${UMAMI_VERSION:-v3.1.0}"
UMAMI_DIR="${UMAMI_DIR:-/opt/umami}"
UMAMI_USER="${UMAMI_USER:-umami}"
UMAMI_DB="${UMAMI_DB:-umami}"
UMAMI_DB_USER="${UMAMI_DB_USER:-umami}"
UMAMI_BASE_PATH="${UMAMI_BASE_PATH:-/_traffic/analytics}"

UMAMI_ENV_FILE="/etc/umami.env"
DB_PASS_FILE="/etc/umami.db-password"
APP_SECRET_FILE="/etc/umami.app-secret"
HASH_SALT_FILE="/etc/umami.hash-salt"
BUILD_MARKER="${UMAMI_DIR}/.next/.cruza-build-marker"
SYSTEMD_UNIT_PATH="/etc/systemd/system/cruza-umami.service"

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SERVICE_SRC="${REPO_DIR}/deploy/cruza-umami.service"

log() { echo "[setup-umami] $*"; }

if [[ "${EUID}" -ne 0 ]]; then
    log "ERRO: precisa rodar como root (use sudo)."
    exit 1
fi

# ─── 1) system user ──────────────────────────────────────────────────────────
if ! id -u "${UMAMI_USER}" >/dev/null 2>&1; then
    log "Criando system user ${UMAMI_USER} com home=${UMAMI_DIR}..."
    useradd --system --create-home --home-dir "${UMAMI_DIR}" \
            --shell /usr/sbin/nologin "${UMAMI_USER}"
else
    # Garante o diretorio mesmo que o user ja exista mas /opt/umami nao
    mkdir -p "${UMAMI_DIR}"
    chown "${UMAMI_USER}:${UMAMI_USER}" "${UMAMI_DIR}"
fi

# ─── 2) Node 22 + pnpm ───────────────────────────────────────────────────────
NEED_NODE=1
if command -v node >/dev/null 2>&1; then
    NODE_MAJOR=$(node -v | sed -E 's/^v([0-9]+).*/\1/')
    if [[ "${NODE_MAJOR}" -ge 20 ]]; then NEED_NODE=0; fi
fi
if [[ "${NEED_NODE}" -eq 1 ]]; then
    log "Instalando Node 22 via NodeSource..."
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
    apt-get install -y nodejs
else
    log "Node $(node -v) ja instalado, ok."
fi

if ! command -v pnpm >/dev/null 2>&1; then
    log "Instalando pnpm globalmente..."
    npm install -g pnpm
else
    log "pnpm $(pnpm -v) ja instalado, ok."
fi

# ─── 3) Postgres: DB + role ─────────────────────────────────────────────────
if [[ ! -f "${DB_PASS_FILE}" ]]; then
    log "Gerando senha aleatoria pro role ${UMAMI_DB_USER}..."
    (umask 077; openssl rand -hex 24 > "${DB_PASS_FILE}")
    chown root:root "${DB_PASS_FILE}"
    chmod 0600 "${DB_PASS_FILE}"
fi
DB_PASS=$(cat "${DB_PASS_FILE}")

if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='${UMAMI_DB_USER}'" | grep -q 1; then
    log "Criando role ${UMAMI_DB_USER}..."
    sudo -u postgres psql -c "CREATE ROLE ${UMAMI_DB_USER} WITH LOGIN PASSWORD '${DB_PASS}';"
else
    # Re-ALTER toda vez pra garantir que a senha persistida em
    # /etc/umami.db-password bate com a senha do role (caso alguem tenha
    # rodado manual). NAO gera nova senha — usa a que ja esta no arquivo.
    sudo -u postgres psql -c "ALTER ROLE ${UMAMI_DB_USER} WITH LOGIN PASSWORD '${DB_PASS}';" >/dev/null
fi

if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${UMAMI_DB}'" | grep -q 1; then
    log "Criando database ${UMAMI_DB} (owner=${UMAMI_DB_USER})..."
    sudo -u postgres createdb -O "${UMAMI_DB_USER}" "${UMAMI_DB}"
fi

# ─── 4) Secrets (gerar uma vez, persistir) ──────────────────────────────────
# CUIDADO: trocar HASH_SALT depois invalida a continuidade dos visitantes
# (cada IP eh hasheado com o salt; sessoes ficam fragmentadas). APP_SECRET
# tambem nao deve mudar — JWTs assinados ficam invalidos.
for f in "${APP_SECRET_FILE}" "${HASH_SALT_FILE}"; do
    if [[ ! -f "${f}" ]]; then
        log "Gerando $(basename "${f}")..."
        (umask 077; openssl rand -hex 32 > "${f}")
        chown root:root "${f}"
        chmod 0600 "${f}"
    fi
done
APP_SECRET=$(cat "${APP_SECRET_FILE}")
HASH_SALT=$(cat "${HASH_SALT_FILE}")

# ─── 5) /etc/umami.env ──────────────────────────────────────────────────────
# Re-escrito a cada deploy (atomico via mv) — reflete sempre os arquivos
# de senha/secret atuais + UMAMI_BASE_PATH desta execucao.
log "Escrevendo ${UMAMI_ENV_FILE} (BASE_PATH=${UMAMI_BASE_PATH})..."
ENV_TMP=$(mktemp /etc/umami.env.XXXXXX)
cat > "${ENV_TMP}" <<EOF
# Generated by deploy/setup-umami.sh — DO NOT EDIT.
# Os valores vem de /etc/umami.db-password, /etc/umami.app-secret e
# /etc/umami.hash-salt. Pra rotacionar: troque o arquivo de origem e
# rode este script novamente.
DATABASE_URL=postgresql://${UMAMI_DB_USER}:${DB_PASS}@127.0.0.1:5432/${UMAMI_DB}
DATABASE_TYPE=postgresql
APP_SECRET=${APP_SECRET}
HASH_SALT=${HASH_SALT}
PORT=3001
HOSTNAME=127.0.0.1
NODE_ENV=production
# BASE_PATH e baked in pelo Next.js no momento do `pnpm run build` (ver passo
# 7 abaixo). Mantemos ele tambem em runtime pra qualquer codigo server-side
# que leia process.env.BASE_PATH.
BASE_PATH=${UMAMI_BASE_PATH}
# Telemetria do Next.js — desabilitada.
NEXT_TELEMETRY_DISABLED=1
EOF
chown "root:${UMAMI_USER}" "${ENV_TMP}"
chmod 0640 "${ENV_TMP}"
mv -f "${ENV_TMP}" "${UMAMI_ENV_FILE}"

# ─── 6) Clone / checkout do Umami ───────────────────────────────────────────
if [[ ! -d "${UMAMI_DIR}/.git" ]]; then
    log "Clonando umami-software/umami @ ${UMAMI_VERSION} em ${UMAMI_DIR}..."
    # Garante diretorio vazio (sem apagar /opt/umami como root caso ja exista
    # com home do user — preserva o ponto de montagem).
    find "${UMAMI_DIR}" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
    sudo -u "${UMAMI_USER}" git clone --depth 1 --branch "${UMAMI_VERSION}" \
        https://github.com/umami-software/umami.git "${UMAMI_DIR}"
else
    cd "${UMAMI_DIR}"
    CUR_VER=$(sudo -u "${UMAMI_USER}" git describe --tags --exact-match 2>/dev/null || echo "unknown")
    if [[ "${CUR_VER}" != "${UMAMI_VERSION}" ]]; then
        log "Atualizando Umami: ${CUR_VER} -> ${UMAMI_VERSION}..."
        sudo -u "${UMAMI_USER}" git fetch --tags --depth 1 origin \
            "refs/tags/${UMAMI_VERSION}:refs/tags/${UMAMI_VERSION}"
        sudo -u "${UMAMI_USER}" git checkout "${UMAMI_VERSION}"
    else
        log "Umami ja em ${UMAMI_VERSION}, pulando checkout."
    fi
fi
chown -R "${UMAMI_USER}:${UMAMI_USER}" "${UMAMI_DIR}"

# ─── 7) Build (skip se marker == versao+base-path atual) ────────────────────
# BASE_PATH eh baked in pelo Next.js durante `pnpm run build` (next.config.js
# usa process.env.BASE_PATH). Trocar UMAMI_BASE_PATH exige rebuild — por
# isso o marker carrega versao+base-path.
NEED_BUILD=1
BUILD_KEY="${UMAMI_VERSION}|${UMAMI_BASE_PATH}"
if [[ -f "${BUILD_MARKER}" ]]; then
    if [[ "$(cat "${BUILD_MARKER}")" == "${BUILD_KEY}" ]]; then
        NEED_BUILD=0
    fi
fi

if [[ "${NEED_BUILD}" -eq 1 ]]; then
    log "Buildando Umami ${UMAMI_VERSION} com BASE_PATH=${UMAMI_BASE_PATH} (pode levar ~3min)..."
    # Build precisa de DATABASE_URL (prisma generate puxa schema do DB).
    # `set -a; source ...; set +a` carrega todas as vars do env file pro
    # subshell — mais robusto que `export $(cat | xargs)` frente a valores
    # com caracteres especiais.
    sudo -u "${UMAMI_USER}" env "HOME=${UMAMI_DIR}" bash -c "
        cd '${UMAMI_DIR}' && \
        set -a && source '${UMAMI_ENV_FILE}' && set +a && \
        pnpm install --frozen-lockfile && \
        pnpm run build
    "
    sudo -u "${UMAMI_USER}" mkdir -p "$(dirname "${BUILD_MARKER}")"
    echo -n "${BUILD_KEY}" | sudo -u "${UMAMI_USER}" tee "${BUILD_MARKER}" >/dev/null
else
    log "Build ja existe pro tag ${UMAMI_VERSION} + BASE_PATH ${UMAMI_BASE_PATH}, pulando."
fi

# ─── 8) Migrations ──────────────────────────────────────────────────────────
log "Aplicando Prisma migrations..."
sudo -u "${UMAMI_USER}" env "HOME=${UMAMI_DIR}" bash -c "
    cd '${UMAMI_DIR}' && \
    set -a && source '${UMAMI_ENV_FILE}' && set +a && \
    pnpm run update-db
"

# ─── 9) systemd unit ────────────────────────────────────────────────────────
log "Instalando cruza-umami.service..."
install -m 0644 "${SERVICE_SRC}" "${SYSTEMD_UNIT_PATH}"
systemctl daemon-reload
systemctl enable cruza-umami >/dev/null
systemctl restart cruza-umami

# Espera o servico ficar healthy (max 30s). Umami v3 leva alguns segundos
# pra subir Next + abrir socket; testa via /api/heartbeat dentro do
# BASE_PATH (com BASE_PATH=/_traffic/analytics, vira /_traffic/analytics/api/heartbeat).
log "Aguardando cruza-umami responder em 127.0.0.1:3001${UMAMI_BASE_PATH}/api/heartbeat..."
for i in $(seq 1 30); do
    if curl -fsS -o /dev/null --max-time 2 "http://127.0.0.1:3001${UMAMI_BASE_PATH}/api/heartbeat" 2>/dev/null; then
        log "OK: Umami healthy apos ${i}s."
        break
    fi
    sleep 1
    if [[ "${i}" -eq 30 ]]; then
        log "ERRO: Umami nao respondeu em 30s. Veja journalctl -u cruza-umami -n 50"
        systemctl status cruza-umami --no-pager -l || true
        exit 1
    fi
done

log "Setup concluido."
log "  - Painel:    https://transparenciapb.org${UMAMI_BASE_PATH}/ (apos basic-auth + login)"
log "  - Tracker:   https://transparenciapb.org${UMAMI_BASE_PATH}/script.js (publico)"
log "  - Bind:      127.0.0.1:3001 (proxy via nginx + .htpasswd-traffic)"
log "  - Logs:      journalctl -u cruza-umami -f"
log "  - Versao:    ${UMAMI_VERSION}"
log "  - BASE_PATH: ${UMAMI_BASE_PATH}"
log ""
log "Proximo passo: criar website no painel e copiar Website ID pro"
log "secret UMAMI_WEBSITE_ID (variavel ENV_FILE do GitHub Actions)."
