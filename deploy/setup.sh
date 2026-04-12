#!/bin/bash
# Setup dos services systemd na VM
# Executar como root: sudo bash deploy/setup.sh

set -e

cp deploy/cruza-web.service /etc/systemd/system/
cp deploy/cruza-warm-cache.service /etc/systemd/system/

systemctl daemon-reload
systemctl enable cruza-web cruza-warm-cache
systemctl start cruza-web cruza-warm-cache

echo "Services instalados e iniciados:"
systemctl status cruza-web --no-pager -l
systemctl status cruza-warm-cache --no-pager -l
