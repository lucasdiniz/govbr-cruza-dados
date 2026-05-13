#!/bin/bash
# Setup idempotente do digest diario de trafego.
#
# Chamado pelo deploy.yml apos setup-goaccess.sh. Em deploys subsequentes
# sem mudancas, eh no-op (cmp + reload-conditional).
#
# Uso (na VM, como root):
#   sudo bash deploy/setup-traffic-digest.sh
#   # ou com email destinatario:
#   sudo env TRAFFIC_DIGEST_EMAIL_TO=admin@example.com \
#       bash deploy/setup-traffic-digest.sh
#
# Variaveis de ambiente (todas opcionais):
#   TRAFFIC_DIGEST_EMAIL_TO    - destinatario(s) do email diario.
#                                 Se vazio E /etc/cruza-traffic-digest.env
#                                 ja existir, preserva valor anterior.
#   TRAFFIC_DIGEST_EMAIL_FROM  - remetente do email
#   TRAFFIC_DIGEST_SUBJECT     - assunto custom
#
# MTA: o script de digest tenta msmtp -> mail -> sendmail nessa ordem.
# Pra usar msmtp com Gmail/SES SMTP relay:
#   sudo apt-get install msmtp msmtp-mta
#   sudo tee /etc/msmtprc <<'EOF'
#   defaults
#   auth on
#   tls on
#   tls_starttls on
#   tls_trust_file /etc/ssl/certs/ca-certificates.crt
#   logfile /var/log/msmtp.log
#
#   account default
#   host smtp.gmail.com
#   port 587
#   from <seu-email>@gmail.com
#   user <seu-email>@gmail.com
#   password <app-password>
#   EOF
#   sudo chmod 600 /etc/msmtprc

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT_SRC="${REPO_DIR}/deploy/cruza-traffic-digest.sh"
SCRIPT_DST="/usr/local/bin/cruza-traffic-digest.sh"
SERVICE_SRC="${REPO_DIR}/deploy/cruza-traffic-digest.service"
SERVICE_DST="/etc/systemd/system/cruza-traffic-digest.service"
TIMER_SRC="${REPO_DIR}/deploy/cruza-traffic-digest.timer"
TIMER_DST="/etc/systemd/system/cruza-traffic-digest.timer"
ENV_FILE="/etc/cruza-traffic-digest.env"
OUTDIR="/var/log/cruza-traffic-digest"

log() { echo "[traffic-digest] $*"; }

if [[ "${EUID}" -ne 0 ]]; then
    log "ERRO: precisa rodar como root (use sudo)."
    exit 1
fi

# ─── 1. Output dir ───
mkdir -p "${OUTDIR}"
chmod 750 "${OUTDIR}"

# ─── 2. Script principal ───
needs_reload_unit=0
if [[ ! -f "${SCRIPT_DST}" ]] || ! cmp -s "${SCRIPT_SRC}" "${SCRIPT_DST}"; then
    log "Instalando ${SCRIPT_DST}"
    install -m 755 -o root -g root "${SCRIPT_SRC}" "${SCRIPT_DST}"
fi

# ─── 3. Env file ───
# Se ${TRAFFIC_DIGEST_EMAIL_TO} vier do env do deploy, atualiza; senao
# preserva o que ja existir no arquivo. Permite o admin setar o email
# uma vez via secret do GitHub Actions e nao precisar manter na config
# do repo.
EMAIL_TO="${TRAFFIC_DIGEST_EMAIL_TO:-}"
EMAIL_FROM="${TRAFFIC_DIGEST_EMAIL_FROM:-}"
SUBJECT="${TRAFFIC_DIGEST_SUBJECT:-}"
EXISTING_EMAIL_TO=""
EXISTING_EMAIL_FROM=""
EXISTING_SUBJECT=""

# Le valores existentes do env file SEM usar `source` (anti-injection).
# Mesmo parser do cruza-traffic-digest.sh — exige formato KEY="VALUE".
if [[ -f "${ENV_FILE}" ]]; then
    while IFS= read -r _envline; do
        [[ -z "${_envline}" || "${_envline:0:1}" == "#" ]] && continue
        if [[ "${_envline}" =~ ^([A-Z_]+)=\"(.*)\"$ ]]; then
            _k="${BASH_REMATCH[1]}"
            _v="${BASH_REMATCH[2]}"
            _v="${_v//\\\\/\\}"
            _v="${_v//\\\"/\"}"
            case "${_k}" in
                TRAFFIC_DIGEST_EMAIL_TO)   EXISTING_EMAIL_TO="${_v}"   ;;
                TRAFFIC_DIGEST_EMAIL_FROM) EXISTING_EMAIL_FROM="${_v}" ;;
                TRAFFIC_DIGEST_SUBJECT)    EXISTING_SUBJECT="${_v}"    ;;
            esac
        fi
    done < "${ENV_FILE}"
    unset _envline _k _v
fi

FINAL_EMAIL_TO="${EMAIL_TO:-${EXISTING_EMAIL_TO:-}}"
FINAL_EMAIL_FROM="${EMAIL_FROM:-${EXISTING_EMAIL_FROM:-}}"
FINAL_SUBJECT="${SUBJECT:-${EXISTING_SUBJECT:-}}"

if [[ -z "${EMAIL_TO}" && -z "${EMAIL_FROM}" && -z "${SUBJECT}" && -f "${ENV_FILE}" ]]; then
    log "TRAFFIC_DIGEST_EMAIL_TO vazio no env do deploy — preservando ${ENV_FILE} existente."
else
    # Anti header-injection: rejeita newlines/CR (\n, \r) nos valores.
    # Esses chars sao perigosos em headers de email (From/To/Subject).
    for _val in "${FINAL_EMAIL_TO}" "${FINAL_EMAIL_FROM}" "${FINAL_SUBJECT}"; do
        if [[ "${_val}" == *$'\n'* || "${_val}" == *$'\r'* ]]; then
            log "ERRO: valor de email contem newline/CR — rejeitado por seguranca."
            exit 1
        fi
    done
    unset _val

    # Escapa \\ e \" pra formato KEY="VALUE" parseavel pelo digest.
    _quote_env() {
        local v="$1"
        v="${v//\\/\\\\}"
        v="${v//\"/\\\"}"
        printf '"%s"' "$v"
    }

    log "Escrevendo ${ENV_FILE}"
    {
        echo "# MANAGED BY deploy/setup-traffic-digest.sh"
        echo "# Formato: KEY=\"valor\" (sempre quoted; backslash e aspas duplas"
        echo "# internas precisam estar escaped). Newlines/CR sao rejeitados."
        echo "# Edicoes manuais podem ser sobrescritas no proximo deploy."
        if [[ -n "${FINAL_EMAIL_TO}" ]]; then echo "TRAFFIC_DIGEST_EMAIL_TO=$(_quote_env "${FINAL_EMAIL_TO}")"; fi
        if [[ -n "${FINAL_EMAIL_FROM}" ]]; then echo "TRAFFIC_DIGEST_EMAIL_FROM=$(_quote_env "${FINAL_EMAIL_FROM}")"; fi
        if [[ -n "${FINAL_SUBJECT}" ]]; then echo "TRAFFIC_DIGEST_SUBJECT=$(_quote_env "${FINAL_SUBJECT}")"; fi
    } > "${ENV_FILE}"
    chmod 640 "${ENV_FILE}"
    chown root:root "${ENV_FILE}"
fi

# ─── 4. Systemd units ───
if [[ ! -f "${SERVICE_DST}" ]] || ! cmp -s "${SERVICE_SRC}" "${SERVICE_DST}"; then
    log "Instalando ${SERVICE_DST}"
    install -m 644 -o root -g root "${SERVICE_SRC}" "${SERVICE_DST}"
    needs_reload_unit=1
fi
if [[ ! -f "${TIMER_DST}" ]] || ! cmp -s "${TIMER_SRC}" "${TIMER_DST}"; then
    log "Instalando ${TIMER_DST}"
    install -m 644 -o root -g root "${TIMER_SRC}" "${TIMER_DST}"
    needs_reload_unit=1
fi

if [[ "${needs_reload_unit}" -eq 1 ]]; then
    systemctl daemon-reload
fi

systemctl enable --now cruza-traffic-digest.timer >/dev/null 2>&1 || true
log "Timer status:"
systemctl list-timers cruza-traffic-digest.timer --no-pager 2>/dev/null || true

if [[ -n "${FINAL_EMAIL_TO}" ]]; then
    log "Email destinatario: ${FINAL_EMAIL_TO}"
    if ! command -v msmtp >/dev/null 2>&1 && ! command -v mail >/dev/null 2>&1 && ! command -v sendmail >/dev/null 2>&1; then
        log "AVISO: nenhum MTA encontrado (msmtp/mail/sendmail). Instale um deles + configure SMTP."
        log "       Sugestao: sudo apt-get install msmtp msmtp-mta + /etc/msmtprc com SMTP relay."
    fi
else
    log "TRAFFIC_DIGEST_EMAIL_TO vazio. Digest sera gerado em ${OUTDIR}/YYYY-MM-DD.md mas nao enviado."
fi

log "Setup completo."
