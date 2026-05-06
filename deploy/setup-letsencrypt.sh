#!/bin/bash
# Setup idempotente de Let's Encrypt + nginx para transparenciapb.org.
#
# Pode ser executado múltiplas vezes:
#   - Se o cert ainda não existe, instala certbot, copia config bootstrap
#     (HTTP-only com ACME path), emite o cert via webroot e troca pelo
#     config completo (HTTPS).
#   - Se o cert já existe, só reaplica o config completo (idempotente).
#
# Uso (na VM, como root):
#   sudo bash deploy/setup-letsencrypt.sh
#
# Pré-requisitos:
#   - DNS A records de transparenciapb.org e www.transparenciapb.org
#     apontando para o IP público desta VM (52.162.207.186).
#   - Portas TCP 80 e 443 abertas no NSG/firewall.
#
# Variáveis de ambiente opcionais:
#   DOMAIN          - domínio apex (default: transparenciapb.org)
#   ACME_EMAIL      - email de contato Let's Encrypt
#                     (default: lets-encrypt@transparenciapb.org)
#   STAGING         - se "1", usa Let's Encrypt staging (não conta no rate limit;
#                     útil pra debug). Default: 0.
set -euo pipefail

DOMAIN="${DOMAIN:-transparenciapb.org}"
WWW_DOMAIN="www.${DOMAIN}"
ACME_EMAIL="${ACME_EMAIL:-lets-encrypt@${DOMAIN}}"
STAGING="${STAGING:-0}"

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
NGINX_BOOTSTRAP_CONF="${REPO_DIR}/deploy/nginx-cruza-http-only.conf"
NGINX_FULL_CONF="${REPO_DIR}/deploy/nginx-cruza.conf"
SSL_PARAMS_SRC="${REPO_DIR}/deploy/ssl-params.conf"
NGINX_SITE_PATH="/etc/nginx/sites-available/cruza"
SSL_PARAMS_PATH="/etc/nginx/snippets/ssl-params.conf"
WEBROOT="/var/www/certbot"
CERT_PATH="/etc/letsencrypt/live/${DOMAIN}/fullchain.pem"

log() { echo "[setup-letsencrypt] $*"; }

if [[ "${EUID}" -ne 0 ]]; then
    log "ERRO: precisa rodar como root (use sudo)."
    exit 1
fi

# 1) Instalar certbot se ausente
if ! command -v certbot >/dev/null 2>&1; then
    log "Instalando certbot..."
    apt-get update
    apt-get install -y certbot
fi

# 2) Garantir nginx instalado e webroot dir existe
if ! dpkg -s nginx >/dev/null 2>&1; then
    log "Instalando nginx..."
    apt-get update
    apt-get install -y nginx
fi
mkdir -p "${WEBROOT}"
chown -R www-data:www-data "${WEBROOT}" 2>/dev/null || true

# 3) Vendor SSL params snippet (compartilhado entre os server blocks HTTPS)
mkdir -p "$(dirname "${SSL_PARAMS_PATH}")"
install -m 0644 "${SSL_PARAMS_SRC}" "${SSL_PARAMS_PATH}"

# 4) Garantir sites-enabled apontando para o nosso config (não para o default)
ln -sf "${NGINX_SITE_PATH}" /etc/nginx/sites-enabled/cruza
rm -f /etc/nginx/sites-enabled/default

# Helper: copia config atomicamente (evita corrida com renewal-hook reload)
install_nginx_config() {
    local src="$1"
    local label="$2"
    log "Aplicando nginx config (${label}): ${src}"
    local tmp
    tmp=$(mktemp "${NGINX_SITE_PATH}.XXXXXX")
    cp "${src}" "${tmp}"
    chmod 0644 "${tmp}"
    mv -f "${tmp}" "${NGINX_SITE_PATH}"
    if ! nginx -t; then
        log "ERRO: nginx -t falhou após copiar ${label}."
        return 1
    fi
    systemctl reload nginx || systemctl start nginx
    systemctl enable nginx >/dev/null 2>&1 || true
}

# Verifica se o cert atual cobre exatamente os domínios desejados.
# Retorna 0 se cert presente E SANs == { DOMAIN, WWW_DOMAIN }, 1 caso contrário.
cert_covers_expected_domains() {
    [[ -f "${CERT_PATH}" ]] || return 1
    local sans expected
    sans=$(openssl x509 -in "${CERT_PATH}" -noout -ext subjectAltName 2>/dev/null \
            | grep -oE 'DNS:[^,]+' | sed 's/DNS://g; s/ //g' | sort -u)
    expected=$(printf "%s\n%s\n" "${DOMAIN}" "${WWW_DOMAIN}" | sort -u)
    [[ "${sans}" == "${expected}" ]]
}

# 5) Bootstrap se cert não existe OU não cobre os domínios esperados
if cert_covers_expected_domains; then
    log "Cert presente em ${CERT_PATH} cobrindo ${DOMAIN} e ${WWW_DOMAIN}. Pulando emissão."
else
    if [[ -f "${CERT_PATH}" ]]; then
        log "Cert existe mas SANs não batem. Vou expandir/reemitir."
    else
        log "Cert ainda não emitido. Iniciando bootstrap."
        install_nginx_config "${NGINX_BOOTSTRAP_CONF}" "bootstrap HTTP-only"
    fi

    CERTBOT_ARGS=(
        certonly
        --webroot
        -w "${WEBROOT}"
        --cert-name "${DOMAIN}"
        -d "${DOMAIN}"
        -d "${WWW_DOMAIN}"
        --email "${ACME_EMAIL}"
        --agree-tos
        --no-eff-email
        --non-interactive
        --keep-until-expiring
        --expand
    )
    if [[ "${STAGING}" == "1" ]]; then
        log "Usando ambiente STAGING do Let's Encrypt."
        CERTBOT_ARGS+=(--staging)
    fi

    log "Emitindo/atualizando cert via certbot webroot..."
    certbot "${CERTBOT_ARGS[@]}"
fi

# 6) Aplicar config full (HTTPS) — idempotente
install_nginx_config "${NGINX_FULL_CONF}" "completo (HTTPS)"

# 7) Hook de renovação: reload nginx após renovação automática
HOOK_DIR=/etc/letsencrypt/renewal-hooks/deploy
HOOK_FILE="${HOOK_DIR}/reload-nginx.sh"
mkdir -p "${HOOK_DIR}"
cat > "${HOOK_FILE}" <<'EOF'
#!/bin/bash
# Disparado pelo certbot após renovação bem-sucedida (certbot.timer).
systemctl reload nginx
EOF
chmod +x "${HOOK_FILE}"

# 8) Garantir timer de renovação ativo. O pacote certbot do Debian/Ubuntu
# instala certbot.timer; o snap usa snap.certbot.renew.timer. Procuramos
# pelos nomes conhecidos e falhamos alto se NENHUM existir (caso contrário,
# o cert vai expirar silenciosamente em 90 dias).
RENEW_TIMER=""
for candidate in certbot.timer snap.certbot.renew.timer; do
    if systemctl list-unit-files "${candidate}" 2>/dev/null | grep -q "^${candidate}"; then
        RENEW_TIMER="${candidate}"
        break
    fi
done
if [[ -z "${RENEW_TIMER}" ]]; then
    log "ERRO: nenhum timer de renovação do certbot encontrado (procurei certbot.timer e snap.certbot.renew.timer)."
    log "      O cert vai expirar em ~90 dias sem renovação automática."
    log "      Investigar com: systemctl list-unit-files | grep certbot"
    exit 1
fi
if systemctl is-enabled "${RENEW_TIMER}" 2>/dev/null | grep -q masked; then
    log "ERRO: ${RENEW_TIMER} está MASKED. Rode: sudo systemctl unmask ${RENEW_TIMER}"
    exit 1
fi
systemctl enable --now "${RENEW_TIMER}"
log "Timer de renovação ativo: ${RENEW_TIMER} ($(systemctl is-active "${RENEW_TIMER}"))"

log "Pronto. https://${DOMAIN} deve estar respondendo."
log "Status: $(systemctl is-active nginx) (nginx) | $(systemctl is-active "${RENEW_TIMER}") (${RENEW_TIMER})"
