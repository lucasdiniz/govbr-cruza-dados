#!/bin/bash
# Daily traffic digest — gera um resumo do access.log do dia anterior e
# envia por email. Roda via systemd timer (cruza-traffic-digest.timer).
#
# Por que existe:
#   - GoAccess so tem dashboard real-time, sem digest historico
#   - Umami mostra eventos mas nao da o "panorama operacional" diario
#     (top paths, status codes, exploits tentados, IPs novos, anomalias)
#   - Skill local analyze-prod-traffic so roda on-demand via dev console
#
# Output:
#   1. Sempre escreve markdown em /var/log/cruza-traffic-digest/YYYY-MM-DD.md
#   2. Se TRAFFIC_DIGEST_EMAIL_TO estiver setado em /etc/cruza-traffic-digest.env,
#      envia o markdown por email usando msmtp/mailx (admin configura o
#      MTA separadamente — setup-traffic-digest.sh documenta).
#
# Envvars (lidas de /etc/cruza-traffic-digest.env se existir):
#   TRAFFIC_DIGEST_EMAIL_TO   - destinatario(s), separados por virgula
#                               (vazio = so escreve arquivo, nao envia)
#   TRAFFIC_DIGEST_EMAIL_FROM - remetente (default: digest@<hostname>)
#   TRAFFIC_DIGEST_SUBJECT    - assunto (default: [transparenciapb]
#                               Digest de trafego YYYY-MM-DD)

set -euo pipefail

LOG="/var/log/nginx/access.log.1"   # log rotacionado de ontem
if [[ ! -r "${LOG}" ]]; then
    # Fallback pra log atual + filtro por data de ontem (caso logrotate
    # nao tenha rodado ainda quando o timer dispara).
    LOG="/var/log/nginx/access.log"
fi

OUTDIR="/var/log/cruza-traffic-digest"
mkdir -p "${OUTDIR}"
chmod 750 "${OUTDIR}"

YESTERDAY="$(date -u -d 'yesterday' '+%Y-%m-%d')"
YESTERDAY_NGINX="$(date -u -d 'yesterday' '+%d/%b/%Y')"
OUT="${OUTDIR}/${YESTERDAY}.md"

# Load env if present
if [[ -f /etc/cruza-traffic-digest.env ]]; then
    # shellcheck disable=SC1091
    set -a; source /etc/cruza-traffic-digest.env; set +a
fi

# ── Filtra so as linhas de ontem (UTC). Combined log format: o timestamp
#    nginx default vem em [DD/Mon/YYYY:HH:MM:SS +0000]. ──
FILTERED=$(mktemp)
trap "rm -f '${FILTERED}'" EXIT
grep "\[${YESTERDAY_NGINX}:" "${LOG}" > "${FILTERED}" || true

total_hits=$(wc -l < "${FILTERED}" | tr -d ' ')
unique_ips=$(awk '{print $1}' "${FILTERED}" | sort -u | wc -l | tr -d ' ')

# Top paths (excluindo /static/* e /api/*)
top_paths=$(awk '{print $7}' "${FILTERED}" \
    | grep -vE '^/static/|^/api/|^/_traffic/' \
    | sed 's/?.*//' \
    | sort | uniq -c | sort -rn | head -15 \
    | awk '{printf "  - `%s` (%s hits)\n", $2, $1}')

# Top referers (excluindo own domain + empty)
top_refs=$(awk -F\" '{print $4}' "${FILTERED}" \
    | grep -vE '^$|^-$|transparenciapb\.org' \
    | sort | uniq -c | sort -rn | head -10 \
    | awk '{$1=$1; sub(/^[0-9]+ /, ""); print "  - " $0}' \
    | head -10)

# Status code breakdown
status_breakdown=$(awk '{print $9}' "${FILTERED}" \
    | sort | uniq -c | sort -rn \
    | awk '{printf "  - HTTP %s: %s\n", $2, $1}')

# Top IPs (potencial bot/scanner)
top_ips=$(awk '{print $1}' "${FILTERED}" \
    | sort | uniq -c | sort -rn | head -10 \
    | awk '{printf "  - %s (%s hits)\n", $2, $1}')

# 4xx/5xx errors — quais paths bombam?
top_errors=$(awk '$9 ~ /^[45][0-9][0-9]$/ {print $9, $7}' "${FILTERED}" \
    | sed 's/?.*//' \
    | sort | uniq -c | sort -rn | head -10 \
    | awk '{printf "  - HTTP %s `%s` (%s vezes)\n", $2, $3, $1}')

# Exploit attempts (paths suspeitos — mesmas heuristicas do fail2ban
# transparenciapb-exploit-paths.filter)
exploits=$(awk '{print $1, $7}' "${FILTERED}" \
    | grep -iE '\.env|\.git|wp-admin|wp-login|/admin|/phpmyadmin|/php\.ini|/web-console|/saml|/vpn|/v[12345]/api|/actuator|/manager/html' \
    | sort | uniq -c | sort -rn | head -10 \
    | awk '{printf "  - %s -> `%s` (%s)\n", $2, $3, $1}')

# IPs identificados (>100 hits + sao usuarios reais provaveis pelo UA)
# Heuristica simples — Mozilla + nao-bot UA
real_users=$(awk -F\" '$6 ~ /Mozilla/ && $6 !~ /[Bb]ot|[Cc]rawler|[Ss]craper|[Ss]pider/' "${FILTERED}" \
    | awk '{print $1}' | sort | uniq -c | sort -rn | head -10 \
    | awk '{printf "  - %s (%s hits)\n", $2, $1}')

# Compose markdown
cat > "${OUT}" <<EOF
# Digest de trafego — ${YESTERDAY}

> Resumo do access.log do dia anterior. Gerado por cruza-traffic-digest.

## Resumo numerico

- **Hits totais:** ${total_hits}
- **IPs unicos:** ${unique_ips}

## Top paths (excluindo /static, /api, /_traffic)

${top_paths:-_nenhum dado_}

## Top referers (externos)

${top_refs:-_nenhum dado_}

## Distribuicao de status codes

${status_breakdown:-_nenhum dado_}

## Top IPs (volume)

${top_ips:-_nenhum dado_}

## Top paginas com erro 4xx/5xx

${top_errors:-_nenhum dado_}

## Tentativas de exploit (paths suspeitos)

${exploits:-_nenhum dado_}

## Usuarios reais provaveis (top 10 por hits)

${real_users:-_nenhum dado_}

---

_Gerado automaticamente em $(date -u '+%Y-%m-%d %H:%M:%S UTC'). Para forcar regerar: \`sudo systemctl start cruza-traffic-digest.service\`._
EOF

chmod 640 "${OUT}"
echo "[digest] Escrito: ${OUT}"

# Envia por email se configurado
if [[ -n "${TRAFFIC_DIGEST_EMAIL_TO:-}" ]]; then
    SUBJECT="${TRAFFIC_DIGEST_SUBJECT:-[transparenciapb] Digest de trafego ${YESTERDAY}}"
    FROM="${TRAFFIC_DIGEST_EMAIL_FROM:-digest@$(hostname -f 2>/dev/null || hostname)}"

    if command -v msmtp >/dev/null 2>&1; then
        {
            echo "From: ${FROM}"
            echo "To: ${TRAFFIC_DIGEST_EMAIL_TO}"
            echo "Subject: ${SUBJECT}"
            echo "Content-Type: text/plain; charset=UTF-8"
            echo
            cat "${OUT}"
        } | msmtp --read-recipients
        echo "[digest] Enviado por msmtp para ${TRAFFIC_DIGEST_EMAIL_TO}"
    elif command -v mail >/dev/null 2>&1; then
        mail -s "${SUBJECT}" -a "From: ${FROM}" "${TRAFFIC_DIGEST_EMAIL_TO}" < "${OUT}"
        echo "[digest] Enviado por mail(1) para ${TRAFFIC_DIGEST_EMAIL_TO}"
    elif command -v sendmail >/dev/null 2>&1; then
        {
            echo "From: ${FROM}"
            echo "To: ${TRAFFIC_DIGEST_EMAIL_TO}"
            echo "Subject: ${SUBJECT}"
            echo "Content-Type: text/plain; charset=UTF-8"
            echo
            cat "${OUT}"
        } | sendmail -t
        echo "[digest] Enviado por sendmail para ${TRAFFIC_DIGEST_EMAIL_TO}"
    else
        echo "[digest] AVISO: TRAFFIC_DIGEST_EMAIL_TO setado mas nenhum MTA encontrado (msmtp/mail/sendmail). Arquivo gravado em ${OUT}, sem envio."
    fi
else
    echo "[digest] TRAFFIC_DIGEST_EMAIL_TO vazio em /etc/cruza-traffic-digest.env — arquivo gravado mas nao enviado."
fi

# Retencao: mantem 60 dias
find "${OUTDIR}" -name '*.md' -mtime +60 -delete 2>/dev/null || true
