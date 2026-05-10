"""Fase 19: MV dedicada pro sitemap empresa-municipio.

Cria/recria mv_empresa_municipio_pagantes a partir de
sql/12b_mv_empresa_municipio_pagantes.sql. Standalone — pode ser rodado
independentemente do 21_views (que recria TODAS as MVs e demora 1-2h).

Uso:
    python -m etl.22_mv_sitemap

Depois disso, queries em web/queries/empresa.py
(EMPRESAS_MUNICIPIOS_QUALIFICADAS_*) usam a MV. COUNT vira O(1) e
PAGINATED fica < 100ms vs. ~30s+ do GROUP BY anterior em ~16M rows do
tce_pb_despesa.

Resolve o problema do GSC reportando "Couldn't fetch" nos sitemaps
empresa pos-restart do cruza-web (cache em memoria limpo).
"""

import time

from etl.config import SQL_DIR
from etl.db import get_conn


def run() -> None:
    path = SQL_DIR / "12b_mv_empresa_municipio_pagantes.sql"
    sql = path.read_text(encoding="utf-8")

    print(f"  Executando {path.name}...", flush=True)
    t0 = time.time()
    conn = get_conn()
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
    finally:
        conn.close()
    elapsed = time.time() - t0
    print(f"  OK ({elapsed:.0f}s).", flush=True)

    # Sanity: count rows
    conn2 = get_conn()
    conn2.autocommit = True
    try:
        with conn2.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM mv_empresa_municipio_pagantes")
            row = cur.fetchone()
            n = int(row[0]) if row else 0
            print(f"  mv_empresa_municipio_pagantes tem {n:,} pares.", flush=True)
    finally:
        conn2.close()


if __name__ == "__main__":
    run()
