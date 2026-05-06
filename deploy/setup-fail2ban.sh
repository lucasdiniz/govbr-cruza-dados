#!/bin/bash
# Setup idempotente de fail2ban com jail customizado pra 429s.
#
# Chamado pelo deploy.yml apos setup-letsencrypt.sh. Em deploys subsequentes
# sem mudancas nos arquivos, eh no-op (cmp + reload).
#
# Uso (na VM, como root):
#   sudo bash deploy/setup-fail2ban.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FILTER_SRC="${REPO_DIR}/deploy/fail2ban-transparenciapb-429.filter.conf"
FILTER_DST="/etc/fail2ban/filter.d/transparenciapb-429.conf"
JAIL_SRC="${REPO_DIR}/deploy/fail2ban-transparenciapb-429.jail.conf"
JAIL_DST="/etc/fail2ban/jail.d/transparenciapb-429.conf"

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

# Copiar filter + jail (idempotente — so reload se mudou).
changed=0
for pair in "${FILTER_SRC}:${FILTER_DST}" "${JAIL_SRC}:${JAIL_DST}"; do
    src="${pair%:*}"
    dst="${pair#*:}"
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

# Status do jail
if fail2ban-client status transparenciapb-429 >/dev/null 2>&1; then
    log "Jail transparenciapb-429 ativo:"
    fail2ban-client status transparenciapb-429 | sed 's/^/  /'
else
    log "AVISO: jail transparenciapb-429 nao detectado. Verifique:"
    log "  systemctl status fail2ban"
    log "  journalctl -u fail2ban -n 50"
fi
