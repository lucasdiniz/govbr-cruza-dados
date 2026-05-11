#!/bin/bash
# Setup idempotente do GoAccess real-time dashboard atras de nginx.
#
# Chamado pelo deploy.yml apos setup-letsencrypt.sh + setup-fail2ban.sh.
# Em deploys subsequentes sem mudancas, eh no-op (cmp + reload).
#
# Uso (na VM, como root):
#   sudo bash deploy/setup-goaccess.sh
#   # ou com credenciais explicitas:
#   sudo env GOACCESS_USER=admin GOACCESS_PASSWORD='senha-forte' \
#       bash deploy/setup-goaccess.sh
#
# Variaveis de ambiente (todas opcionais):
#   GOACCESS_USER     - basic-auth username (default: admin)
#   GOACCESS_PASSWORD - basic-auth password. Se vazio E /etc/nginx/.htpasswd-traffic
#                       NAO existe, o setup pula a instalacao do service (no-op).
#                       Se vazio mas o .htpasswd-traffic ja existe, preserva a senha
#                       anterior.
#   GOACCESS_DOMAIN   - dominio publico (default: transparenciapb.org).
#                       Usado no ws-url do goaccess.conf.

set -euo pipefail

GOACCESS_USER="${GOACCESS_USER:-admin}"
GOACCESS_DOMAIN="${GOACCESS_DOMAIN:-transparenciapb.org}"
GOACCESS_PASSWORD="${GOACCESS_PASSWORD:-}"

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CONF_SRC="${REPO_DIR}/deploy/cruza-goaccess.conf"
CONF_DST="/etc/goaccess/cruza-goaccess.conf"
SERVICE_SRC="${REPO_DIR}/deploy/cruza-goaccess.service"
SERVICE_DST="/etc/systemd/system/cruza-goaccess.service"
HTPASSWD="/etc/nginx/.htpasswd-traffic"
OUT_DIR="/var/www/traffic"
DB_DIR="/var/lib/goaccess"

log() { echo "[goaccess] $*"; }

if [[ "${EUID}" -ne 0 ]]; then
    log "ERRO: precisa rodar como root (use sudo)."
    exit 1
fi

# ─── Skip rapido: sem credencial e sem htpasswd previo, nao instala nada ───
# A location /_traffic/ no nginx existe sempre, mas retorna 500 quando o
# htpasswd nao existe — ou seja, e seguro deixar o dashboard "desativado"
# por padrao ate o admin definir uma senha.
if [[ -z "${GOACCESS_PASSWORD}" && ! -f "${HTPASSWD}" ]]; then
    log "Pulando setup: GOACCESS_PASSWORD vazio e ${HTPASSWD} ausente."
    log "Pra ativar, defina o secret GOACCESS_PASSWORD ou rode manualmente:"
    log "  sudo env GOACCESS_PASSWORD='<senha>' bash deploy/setup-goaccess.sh"
    exit 0
fi

# ─── 1. Instalar goaccess (PPA oficial pra versao >=1.7 com anonymize-ip) ───
if ! command -v goaccess >/dev/null 2>&1; then
    log "Instalando goaccess via repo oficial deb.goaccess.io..."
    mkdir -p /usr/share/keyrings
    wget -qO - https://deb.goaccess.io/gnugpg.key \
        | gpg --dearmor -o /usr/share/keyrings/goaccess.gpg
    echo "deb [signed-by=/usr/share/keyrings/goaccess.gpg] https://deb.goaccess.io/ $(lsb_release -cs) main" \
        > /etc/apt/sources.list.d/goaccess.list
    apt-get update -qq
    apt-get install -y goaccess
fi
GOACCESS_VERSION="$(goaccess --version 2>/dev/null | head -1 || echo 'unknown')"
log "Usando ${GOACCESS_VERSION}"

# ─── 2. apache2-utils (htpasswd) ───
if ! command -v htpasswd >/dev/null 2>&1; then
    apt-get install -y apache2-utils
fi

# ─── 3. Diretorios de output + persistencia ───
mkdir -p "${OUT_DIR}" "${DB_DIR}" /etc/goaccess
chown -R www-data:www-data "${OUT_DIR}" "${DB_DIR}"
chmod 755 "${OUT_DIR}" "${DB_DIR}"

# ─── 4. basic-auth ───
# - Se GOACCESS_PASSWORD fornecido: cria/atualiza .htpasswd-traffic com a senha.
# - Senao mas o file ja existe: preserva (idempotente).
if [[ -n "${GOACCESS_PASSWORD}" ]]; then
    htpasswd -bc "${HTPASSWD}" "${GOACCESS_USER}" "${GOACCESS_PASSWORD}"
    chown root:www-data "${HTPASSWD}"
    chmod 640 "${HTPASSWD}"
    log "basic-auth atualizado pra user '${GOACCESS_USER}'."
else
    log "basic-auth preservado (${HTPASSWD} ja existente)."
fi

# ─── 5. Config do goaccess (substitui dominio) ───
tmp_conf="$(mktemp "${CONF_DST}.XXXXXX")"
sed "s|@@GOACCESS_DOMAIN@@|${GOACCESS_DOMAIN}|g" "${CONF_SRC}" > "${tmp_conf}"
chmod 644 "${tmp_conf}"
conf_changed=0
if ! cmp -s "${tmp_conf}" "${CONF_DST}" 2>/dev/null; then
    mv -f "${tmp_conf}" "${CONF_DST}"
    log "  ${CONF_DST} atualizado"
    conf_changed=1
else
    rm -f "${tmp_conf}"
fi

# ─── 6. Systemd unit ───
service_changed=0
if ! cmp -s "${SERVICE_SRC}" "${SERVICE_DST}" 2>/dev/null; then
    install -m 0644 "${SERVICE_SRC}" "${SERVICE_DST}"
    log "  ${SERVICE_DST} atualizado"
    service_changed=1
fi
if [[ "${service_changed}" -eq 1 ]]; then
    systemctl daemon-reload
fi
systemctl enable cruza-goaccess >/dev/null 2>&1 || true

# Restart se: service unit mudou, config mudou, ou nao esta ativo.
if [[ "${service_changed}" -eq 1 || "${conf_changed}" -eq 1 ]] \
   || ! systemctl is-active --quiet cruza-goaccess; then
    systemctl restart cruza-goaccess
    log "cruza-goaccess restart"
fi

# ─── 7. Reload nginx (caso /_traffic/* tenha sido adicionado neste deploy) ───
# nginx-cruza.conf eh aplicado por setup-letsencrypt.sh logo antes, entao
# aqui so reload se realmente necessario. Soft-fail: se nginx -t falhar,
# log e segue (deploy nao deve quebrar por causa do dashboard interno).
if nginx -t >/dev/null 2>&1; then
    systemctl reload nginx
else
    log "AVISO: nginx -t falhou. Pulei o reload. Rode 'sudo nginx -t' pra debug."
fi

# ─── 8. Smoke ───
sleep 2
if systemctl is-active --quiet cruza-goaccess; then
    log "✓ cruza-goaccess ativo."
    log "  Dashboard: https://${GOACCESS_DOMAIN}/_traffic/"
    log "  Logs:      journalctl -u cruza-goaccess -f"
else
    log "ERRO: cruza-goaccess nao subiu. Ultimas linhas:"
    journalctl -u cruza-goaccess --no-pager -n 30 | sed 's/^/  /'
    exit 1
fi
