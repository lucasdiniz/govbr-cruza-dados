"""Fase 7: Entity Resolution — popula tabela pessoa a partir de sócios, CPGF, emendas, PGFN.

Estratégia:
  1. Extrai nomes + CPF mascarado de cada fonte
  2. Insere na tabela pessoa (sem UNIQUE constraint — aceita possíveis duplicatas)
  3. Cria observações por fonte
  4. Identifica merges de alta confiança (CPF completo ou nome+CPF masked idênticos)
"""

from etl.db import get_conn, table_count


def _populate_from_socios(conn):
    """Extrai pessoas físicas da tabela de sócios."""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO pessoa (nome_normalizado, cpf_masked)
            SELECT DISTINCT
                UPPER(TRIM(nome)),
                CASE WHEN LENGTH(REGEXP_REPLACE(cpf_cnpj_socio, '[^0-9]', '', 'g')) = 6
                     THEN REGEXP_REPLACE(cpf_cnpj_socio, '[^0-9]', '', 'g')
                     WHEN LENGTH(REGEXP_REPLACE(cpf_cnpj_socio, '[^0-9]', '', 'g')) >= 9
                     THEN SUBSTRING(REGEXP_REPLACE(cpf_cnpj_socio, '[^0-9]', '', 'g'), 4, 6)
                     ELSE NULL
                END
            FROM socio
            WHERE tipo_socio = 2
              AND nome IS NOT NULL
              AND TRIM(nome) != ''
              AND cpf_cnpj_socio NOT IN ('***000000**', '')
        """)
    conn.commit()
    print(f"    Pessoas de sócios: inseridas")


def _populate_from_cpgf(conn):
    """Extrai portadores do CPGF."""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO pessoa (nome_normalizado, cpf_masked)
            SELECT DISTINCT
                UPPER(TRIM(nome_portador)),
                CASE WHEN LENGTH(REGEXP_REPLACE(cpf_portador, '[^0-9]', '', 'g')) >= 9
                     THEN SUBSTRING(REGEXP_REPLACE(cpf_portador, '[^0-9]', '', 'g'), 4, 6)
                     WHEN LENGTH(REGEXP_REPLACE(cpf_portador, '[^0-9]', '', 'g')) = 6
                     THEN REGEXP_REPLACE(cpf_portador, '[^0-9]', '', 'g')
                     ELSE NULL
                END
            FROM cpgf_transacao
            WHERE nome_portador IS NOT NULL
              AND TRIM(nome_portador) != ''
              AND cpf_portador IS NOT NULL
        """)
    conn.commit()
    print(f"    Pessoas de CPGF: inseridas")


def _populate_from_pgfn(conn):
    """Extrai devedores PF da PGFN (tem CPF completo)."""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO pessoa (nome_normalizado, cpf_masked, cpf_completo)
            SELECT DISTINCT
                UPPER(TRIM(nome_devedor)),
                SUBSTRING(cpf_cnpj, 4, 6),
                cpf_cnpj
            FROM pgfn_divida
            WHERE tipo_pessoa ILIKE '%FISICA%'
              AND nome_devedor IS NOT NULL
              AND TRIM(nome_devedor) != ''
              AND LENGTH(cpf_cnpj) = 11
        """)
    conn.commit()
    print(f"    Pessoas de PGFN: inseridas")


def _create_observations(conn):
    """Cria observações linkando cada pessoa à sua fonte."""
    # Observações de sócios
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO pessoa_observacao (pessoa_id, fonte, fonte_id, nome_original, cpf_raw)
            SELECT p.id, 'rfb_socios', s.id::TEXT, s.nome, s.cpf_cnpj_socio
            FROM pessoa p
            JOIN socio s ON UPPER(TRIM(s.nome)) = p.nome_normalizado
              AND s.tipo_socio = 2
            LIMIT 1000000
        """)
    conn.commit()
    print(f"    Observações de sócios criadas (limitado a 1M)")


def _identify_merges(conn):
    """Identifica merges de alta confiança baseado em CPF completo."""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO pessoa_merge (pessoa_a_id, pessoa_b_id, score, metodo, status)
            SELECT LEAST(p1.id, p2.id), GREATEST(p1.id, p2.id),
                   1.0, 'cpf_completo', 'confirmado'
            FROM pessoa p1
            JOIN pessoa p2 ON p1.cpf_completo = p2.cpf_completo
              AND p1.id < p2.id
            WHERE p1.cpf_completo IS NOT NULL
            ON CONFLICT DO NOTHING
        """)
    conn.commit()
    print(f"    Merges por CPF completo identificados")


def run():
    conn = get_conn()
    try:
        print("  Populando tabela pessoa...")
        _populate_from_socios(conn)
        _populate_from_cpgf(conn)
        _populate_from_pgfn(conn)
        print(f"    pessoa: {table_count(conn, 'pessoa')} registros")

        print("  Criando observações...")
        _create_observations(conn)
        print(f"    pessoa_observacao: {table_count(conn, 'pessoa_observacao')} registros")

        print("  Identificando merges...")
        _identify_merges(conn)
        print(f"    pessoa_merge: {table_count(conn, 'pessoa_merge')} registros")
    finally:
        conn.close()


if __name__ == "__main__":
    run()
