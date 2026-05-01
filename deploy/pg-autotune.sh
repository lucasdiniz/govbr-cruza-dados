#!/usr/bin/env bash
# pg-autotune: ajusta o tuning do PostgreSQL automaticamente com base na RAM detectada.
#
# Roda em duas situacoes:
#   1. Sob demanda durante deploys (chamado pelo workflow apos resize de VM).
#   2. No boot do sistema, via pg-autotune.service (Before=postgresql.service)
#      garantindo que o postgres sobe ja com a config correta apos resize.
#
# Formulas conservadoras (Postgres best-practices):
#   shared_buffers       = 25% RAM
#   effective_cache_size = 75% RAM
#   work_mem             = RAM / 128 (cap min 8MB)
#   maintenance_work_mem = 6% RAM (cap min 64MB, max 1GB)
#
# Settings fixos que nao dependem de RAM ficam no final.

set -euo pipefail

TOTAL_KB=$(awk '/^MemTotal:/ {print $2}' /proc/meminfo 2>/dev/null || echo 0)
TOTAL_MB=$(( TOTAL_KB / 1024 ))

# Defensivo: se deteccao falhou por algum motivo, assume 8GB.
if [ "$TOTAL_MB" -lt 1024 ]; then
    echo "pg-autotune: WARNING memoria detectada=${TOTAL_MB}MB, usando fallback 8192MB"
    TOTAL_MB=8192
fi

SHARED_BUFFERS_MB=$(( TOTAL_MB / 4 ))
EFFECTIVE_CACHE_MB=$(( TOTAL_MB * 3 / 4 ))

WORK_MEM_MB=$(( TOTAL_MB / 128 ))
[ "$WORK_MEM_MB" -lt 8 ] && WORK_MEM_MB=8

MAINT_MB=$(( TOTAL_MB * 6 / 100 ))
[ "$MAINT_MB" -gt 1024 ] && MAINT_MB=1024
[ "$MAINT_MB" -lt 64 ] && MAINT_MB=64

CONF_DIR=/etc/postgresql/16/main/conf.d
TARGET="$CONF_DIR/tuning.conf"

mkdir -p "$CONF_DIR"

cat > "$TARGET" <<EOF
# Auto-gerado por pg-autotune.sh com base na RAM detectada (${TOTAL_MB}MB)
shared_buffers = ${SHARED_BUFFERS_MB}MB
effective_cache_size = ${EFFECTIVE_CACHE_MB}MB
work_mem = ${WORK_MEM_MB}MB
maintenance_work_mem = ${MAINT_MB}MB
max_wal_size = 4GB
checkpoint_completion_target = 0.9
random_page_cost = 1.1
EOF

echo "pg-autotune: tuning aplicado para ${TOTAL_MB}MB de RAM"
echo "  shared_buffers=${SHARED_BUFFERS_MB}MB effective_cache_size=${EFFECTIVE_CACHE_MB}MB"
echo "  work_mem=${WORK_MEM_MB}MB maintenance_work_mem=${MAINT_MB}MB"
