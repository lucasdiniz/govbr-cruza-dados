"""Fase 7: Entity Resolution — popula tabela pessoa a partir de sócios, CPGF, emendas, PGFN.

Estratégia:
  1. Extrai nomes + CPF mascarado de cada fonte
  2. Insere na tabela pessoa (sem UNIQUE constraint — aceita possíveis duplicatas)
  3. Cria observações por fonte
  4. Identifica merges de alta confiança (CPF completo ou nome+CPF masked idênticos)
"""

from etl.db import get_conn, table_count


def _cpf_mask_from_digits(expr: str) -> str:
    return f"""
        CASE WHEN LENGTH(REGEXP_REPLACE({expr}, '[^0-9]', '', 'g')) = 6
             THEN REGEXP_REPLACE({expr}, '[^0-9]', '', 'g')
             WHEN LENGTH(REGEXP_REPLACE({expr}, '[^0-9]', '', 'g')) >= 9
             THEN SUBSTRING(REGEXP_REPLACE({expr}, '[^0-9]', '', 'g'), 4, 6)
             ELSE NULL
        END
    """


def _populate_from_socios(conn):
    """Extrai pessoas físicas da tabela de sócios."""
    cpf_mask_expr = _cpf_mask_from_digits("cpf_cnpj_socio")
    with conn.cursor() as cur:
        cur.execute(f"""
            INSERT INTO pessoa (nome_normalizado, cpf_masked)
            SELECT DISTINCT
                UPPER(TRIM(nome)),
                {cpf_mask_expr}
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
    cpf_mask_expr = _cpf_mask_from_digits("cpf_portador")
    with conn.cursor() as cur:
        cur.execute(f"""
            INSERT INTO pessoa (nome_normalizado, cpf_masked)
            SELECT DISTINCT
                UPPER(TRIM(nome_portador)),
                {cpf_mask_expr}
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
                SUBSTRING(REGEXP_REPLACE(cpf_cnpj, '[^0-9]', '', 'g'), 4, 6),
                REGEXP_REPLACE(cpf_cnpj, '[^0-9]', '', 'g')
            FROM pgfn_divida
            WHERE tipo_pessoa ILIKE '%FISICA%'
              AND nome_devedor IS NOT NULL
              AND TRIM(nome_devedor) != ''
              AND LENGTH(REGEXP_REPLACE(cpf_cnpj, '[^0-9]', '', 'g')) = 11
        """)
    conn.commit()
    print(f"    Pessoas de PGFN: inseridas")


def _create_observations(conn):
    """Cria observações linkando cada pessoa à sua fonte."""
    socio_mask_expr = _cpf_mask_from_digits("s.cpf_cnpj_socio")
    cpgf_mask_expr = _cpf_mask_from_digits("c.cpf_portador")

    # Observações de sócios
    with conn.cursor() as cur:
        cur.execute(f"""
            INSERT INTO pessoa_observacao (pessoa_id, fonte, fonte_id, nome_original, cpf_raw)
            SELECT p.id, 'rfb_socios', s.id::TEXT, s.nome, s.cpf_cnpj_socio
            FROM pessoa p
            JOIN socio s ON UPPER(TRIM(s.nome)) = p.nome_normalizado
               AND s.tipo_socio = 2
               AND ({socio_mask_expr}) IS NOT DISTINCT FROM p.cpf_masked
        """)
        cur.execute(f"""
            INSERT INTO pessoa_observacao (pessoa_id, fonte, fonte_id, nome_original, cpf_raw)
            SELECT p.id, 'cpgf', c.id::TEXT, c.nome_portador, c.cpf_portador
            FROM pessoa p
            JOIN cpgf_transacao c ON UPPER(TRIM(c.nome_portador)) = p.nome_normalizado
               AND ({cpgf_mask_expr}) IS NOT DISTINCT FROM p.cpf_masked
            WHERE c.nome_portador IS NOT NULL
              AND TRIM(c.nome_portador) != ''
              AND c.cpf_portador IS NOT NULL
        """)
        cur.execute("""
            INSERT INTO pessoa_observacao (pessoa_id, fonte, fonte_id, nome_original, cpf_raw)
            SELECT p.id, 'pgfn', d.id::TEXT, d.nome_devedor, d.cpf_cnpj
            FROM pessoa p
            JOIN pgfn_divida d ON UPPER(TRIM(d.nome_devedor)) = p.nome_normalizado
               AND REGEXP_REPLACE(d.cpf_cnpj, '[^0-9]', '', 'g') IS NOT DISTINCT FROM p.cpf_completo
            WHERE d.tipo_pessoa ILIKE '%FISICA%'
              AND d.nome_devedor IS NOT NULL
              AND TRIM(d.nome_devedor) != ''
              AND LENGTH(REGEXP_REPLACE(d.cpf_cnpj, '[^0-9]', '', 'g')) = 11
        """)
    conn.commit()
    print(f"    Observações de pessoas criadas")


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
        cur.execute("""
            INSERT INTO pessoa_merge (pessoa_a_id, pessoa_b_id, score, metodo, status)
            SELECT LEAST(p1.id, p2.id), GREATEST(p1.id, p2.id),
                   0.95, 'nome_cpf_masked', 'confirmado'
            FROM pessoa p1
            JOIN pessoa p2 ON p1.nome_normalizado = p2.nome_normalizado
              AND p1.cpf_masked = p2.cpf_masked
              AND p1.id < p2.id
            WHERE p1.cpf_masked IS NOT NULL
              AND p1.cpf_masked != '000000'
            ON CONFLICT DO NOTHING
        """)
    conn.commit()
    print(f"    Merges por CPF completo e nome+CPF mascarado identificados")


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
