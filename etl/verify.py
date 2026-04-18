"""Verify database: print row counts for key tables."""

from etl.db import get_conn, table_count

TABLES = [
    "empresa", "estabelecimento", "socio", "simples",
    "pncp_contratacao", "pncp_contrato", "pncp_item",
    "tce_pb_despesa", "tce_pb_servidor", "tce_pb_licitacao", "tce_pb_receita",
    "emenda_tesouro", "emenda_convenio", "emenda_favorecido",
    "cpgf_transacao", "pgfn_divida",
    "bndes_contrato",
    "bolsa_familia", "siape_cadastro", "viagem",
    "ceis_sancao", "cnep_sancao", "ceaf_expulsao",
    "tse_candidato", "tse_receita_candidato",
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
        except Exception as e:
            conn.rollback()
            print(f"  {t}: (not found) [{type(e).__name__}]")
    print(f"  --- TOTAL: {total:,} ---")
    conn.close()


if __name__ == "__main__":
    run()
