"""Verify database: print row counts for key tables."""

from etl.db import get_conn, table_count

TABLES = [
    "empresa", "estabelecimento", "socio", "simples",
    "pncp_contratacao", "pncp_contrato",
    "tce_pb_despesa", "tce_pb_servidor", "tce_pb_licitacao", "tce_pb_receita",
    "emenda_parlamentar", "cpgf_transacao", "pgfn_inscricao",
    "bndes_contrato", "comprasnet_contrato",
    "bolsa_familia", "siape_cadastro", "viagem",
]


def run():
    conn = get_conn()
    print("=== Database Status ===")
    total = 0
    for t in TABLES:
        try:
            n = table_count(conn, t)
            total += n
            print(f"  {t}: {n:,}")
        except Exception:
            print(f"  {t}: (not found)")
    print(f"  --- TOTAL: {total:,} ---")
    conn.close()


if __name__ == "__main__":
    run()
