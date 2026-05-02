#!/bin/bash
# Setup dos services systemd na VM
# Executar como root: sudo bash deploy/setup.sh

set -e

cp deploy/cruza-web.service /etc/systemd/system/
cp deploy/cruza-warm-cache.service /etc/systemd/system/

systemctl daemon-reload

# cruza-web roda como daemon continuo (Type=simple). Habilita e inicia.
systemctl enable cruza-web
systemctl start cruza-web

# cruza-warm-cache eh oneshot (NAO tem [Install] section). Nao auto-inicia
# nem eh enabled. Disparado on-demand via:
#   sudo systemctl start cruza-warm-cache
# Tipicamente eh disparado pelo workflow deploy.yml apos ETL.

echo "Services instalados:"
systemctl status cruza-web --no-pager -l
echo ""
echo "cruza-warm-cache: instalado mas NAO iniciado (oneshot, on-demand)."
