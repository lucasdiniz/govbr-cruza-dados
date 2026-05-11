#!/bin/bash
# Setup idempotente de fail2ban com jails customizados.
#
# Jails instalados:
#   - transparenciapb-429: bana IPs que excedem rate limit (10x 429 em 5min)
#   - transparenciapb-exploit-paths: bana IPs que pedem /.env, /.git, /wp-*,
#     /phpunit, /cgi-bin/.%2e, etc. (3 hits em 10min = ban 24h)
#
# Chamado pelo deploy.yml apos setup-letsencrypt.sh. Em deploys subsequentes
# sem mudancas nos arquivos, eh no-op (cmp + reload).
#
# Uso (na VM, como root):
#   sudo bash deploy/setup-fail2ban.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Jail 1: 429 rate limit
F429_FILTER_SRC="${REPO_DIR}/deploy/fail2ban-transparenciapb-429.filter.conf"
F429_FILTER_DST="/etc/fail2ban/filter.d/transparenciapb-429.conf"
F429_JAIL_SRC="${REPO_DIR}/deploy/fail2ban-transparenciapb-429.jail.conf"
F429_JAIL_DST="/etc/fail2ban/jail.d/transparenciapb-429.conf"

# Jail 2: exploit paths
FEXP_FILTER_SRC="${REPO_DIR}/deploy/fail2ban-transparenciapb-exploit-paths.filter.conf"
FEXP_FILTER_DST="/etc/fail2ban/filter.d/transparenciapb-exploit-paths.conf"
FEXP_JAIL_SRC="${REPO_DIR}/deploy/fail2ban-transparenciapb-exploit-paths.jail.conf"
FEXP_JAIL_DST="/etc/fail2ban/jail.d/transparenciapb-exploit-paths.conf"

log() { echo "[fail2ban] $*"; }

if [[ "${EUID}" -ne 0 ]]; then
    log "ERRO: precisa rodar como root (use sudo)."
    exit 1
fi

# Instalar fail2ban se ausente
if ! command -v fail2ban-client >/dev/null 2>&1; then
    log "Instalando fail2ban..."
    apt-get update
    apt-get install -y fail2ban
fi

# Copiar filters + jails (idempotente — so reload se mudou).
changed=0
for pair in \
    "${F429_FILTER_SRC}:${F429_FILTER_DST}" \
    "${F429_JAIL_SRC}:${F429_JAIL_DST}" \
    "${FEXP_FILTER_SRC}:${FEXP_FILTER_DST}" \
    "${FEXP_JAIL_SRC}:${FEXP_JAIL_DST}"; do
    src="${pair%:*}"
    dst="${pair#*:}"
    if [[ ! -f "${src}" ]]; then
        log "AVISO: source ${src} nao existe — pulando."
        continue
    fi
    if ! cmp -s "${src}" "${dst}" 2>/dev/null; then
        install -m 0644 "${src}" "${dst}"
        log "  ${dst} atualizado"
        changed=1
    fi
done

# Garantir fail2ban habilitado + ativo
systemctl enable fail2ban >/dev/null 2>&1 || true
if ! systemctl is-active --quiet fail2ban; then
    systemctl start fail2ban
    log "fail2ban iniciado"
elif [[ "${changed}" -eq 1 ]]; then
    systemctl reload fail2ban
    log "fail2ban reload (config mudou)"
fi

# Status dos jails
for jail in transparenciapb-429 transparenciapb-exploit-paths; do
    if fail2ban-client status "${jail}" >/dev/null 2>&1; then
        log "Jail ${jail} ativo:"
        fail2ban-client status "${jail}" | sed 's/^/  /'
    else
        log "AVISO: jail ${jail} nao detectado."
    fi
done

