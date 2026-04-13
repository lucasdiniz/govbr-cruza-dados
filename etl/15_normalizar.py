"""Normaliza identificadores e cria índices otimizados para queries de fraude.

Executa cada statement separadamente para não perder progresso se interromper.
Usa WHERE col IS NULL para ser idempotente (pode retomar de onde parou).
CREATE INDEX CONCURRENTLY requer autocommit.

EXECUTAR APÓS a carga completa (sem INSERTs ativos).
"""

import time

from etl.db import get_conn


def _exec(conn, desc, sql, autocommit=False):
    """Executa um statement com log de progresso."""
    print(f"  {desc}...", end=" ", flush=True)
    t0 = time.time()
    try:
        if autocommit:
            old = conn.autocommit
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.autocommit = old
        else:
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
        elapsed = time.time() - t0
        print(f"OK ({elapsed:.1f}s)")
    except Exception as e:
        if not autocommit:
            conn.rollback()
        err = str(e).strip().split("\n")[0]
        print(f"ERRO: {err}")


def run():
    conn = get_conn()
    try:
        print("  === Fase 1: Colunas desnormalizadas (CPF/CNPJ apenas dígitos) ===")

        # PGFN (40M rows)
        _exec(conn, "pgfn_divida: ADD cpf_cnpj_norm",
              "ALTER TABLE pgfn_divida ADD COLUMN IF NOT EXISTS cpf_cnpj_norm TEXT")
        _exec(conn, "pgfn_divida: UPDATE cpf_cnpj_norm (40M rows, pode demorar)",
              "UPDATE pgfn_divida SET cpf_cnpj_norm = REGEXP_REPLACE(cpf_cnpj, '[^0-9]', '', 'g') WHERE cpf_cnpj_norm IS NULL")

        # Sócio (27M rows)
        _exec(conn, "socio: ADD cpf_cnpj_norm",
              "ALTER TABLE socio ADD COLUMN IF NOT EXISTS cpf_cnpj_norm TEXT")
        _exec(conn, "socio: UPDATE cpf_cnpj_norm (27M rows, pode demorar)",
              "UPDATE socio SET cpf_cnpj_norm = REGEXP_REPLACE(cpf_cnpj_socio, '[^0-9]', '', 'g') WHERE cpf_cnpj_norm IS NULL AND cpf_cnpj_socio IS NOT NULL")

        # Bolsa Família (21M rows)
        _exec(conn, "bolsa_familia: ADD cpf_digitos",
              "ALTER TABLE bolsa_familia ADD COLUMN IF NOT EXISTS cpf_digitos TEXT")
        _exec(conn, "bolsa_familia: UPDATE cpf_digitos (21M rows)",
              "UPDATE bolsa_familia SET cpf_digitos = REGEXP_REPLACE(cpf_favorecido, '[^0-9]', '', 'g') WHERE cpf_digitos IS NULL AND cpf_favorecido IS NOT NULL AND cpf_favorecido != ''")

        # SIAPE (617k rows)
        _exec(conn, "siape_cadastro: ADD cpf_digitos",
              "ALTER TABLE siape_cadastro ADD COLUMN IF NOT EXISTS cpf_digitos TEXT")
        _exec(conn, "siape_cadastro: UPDATE cpf_digitos",
              "UPDATE siape_cadastro SET cpf_digitos = REGEXP_REPLACE(cpf, '[^0-9]', '', 'g') WHERE cpf_digitos IS NULL AND cpf IS NOT NULL")

        # CPGF (725k rows)
        _exec(conn, "cpgf_transacao: ADD cpf_portador_digitos",
              "ALTER TABLE cpgf_transacao ADD COLUMN IF NOT EXISTS cpf_portador_digitos TEXT")
        _exec(conn, "cpgf_transacao: UPDATE cpf_portador_digitos",
              "UPDATE cpgf_transacao SET cpf_portador_digitos = REGEXP_REPLACE(cpf_portador, '[^0-9]', '', 'g') WHERE cpf_portador_digitos IS NULL AND cpf_portador IS NOT NULL AND cpf_portador != ''")

        # Sanções (pequenas)
        for tbl in ["ceis_sancao", "cnep_sancao", "ceaf_expulsao"]:
            _exec(conn, f"{tbl}: ADD cpf_cnpj_norm",
                  f"ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS cpf_cnpj_norm TEXT")
            _exec(conn, f"{tbl}: UPDATE cpf_cnpj_norm",
                  f"UPDATE {tbl} SET cpf_cnpj_norm = REGEXP_REPLACE(cpf_cnpj_sancionado, '[^0-9]', '', 'g') WHERE cpf_cnpj_norm IS NULL")

        # CEIS/CNEP: coluna extra com 6 dígitos centrais do CPF para match com sócio
        # cpf_cnpj_norm preserva CPF completo (11 dig) / CNPJ (14 dig)
        # cpf_digitos_6 extrai apenas os 6 centrais (posição 4-9) de CPFs com 11 dígitos
        for tbl in ["ceis_sancao", "cnep_sancao"]:
            _exec(conn, f"{tbl}: ADD cpf_digitos_6",
                  f"ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS cpf_digitos_6 TEXT")
            _exec(conn, f"{tbl}: UPDATE cpf_digitos_6 (6 centrais do CPF)",
                  f"UPDATE {tbl} SET cpf_digitos_6 = SUBSTRING(cpf_cnpj_norm, 4, 6) WHERE cpf_digitos_6 IS NULL AND LENGTH(cpf_cnpj_norm) = 11")

        _exec(conn, "acordo_leniencia: ADD cnpj_norm",
              "ALTER TABLE acordo_leniencia ADD COLUMN IF NOT EXISTS cnpj_norm TEXT")
        _exec(conn, "acordo_leniencia: UPDATE cnpj_norm",
              "UPDATE acordo_leniencia SET cnpj_norm = REGEXP_REPLACE(cnpj_sancionado, '[^0-9]', '', 'g') WHERE cnpj_norm IS NULL")

        # Viagem (3.9M rows)
        _exec(conn, "viagem: ADD cpf_viajante_digitos",
              "ALTER TABLE viagem ADD COLUMN IF NOT EXISTS cpf_viajante_digitos TEXT")
        _exec(conn, "viagem: UPDATE cpf_viajante_digitos",
              "UPDATE viagem SET cpf_viajante_digitos = REGEXP_REPLACE(cpf_viajante, '[^0-9]', '', 'g') WHERE cpf_viajante_digitos IS NULL AND cpf_viajante IS NOT NULL")

        # PNCP cnpj_basico_fornecedor
        _exec(conn, "pncp_contrato: ADD cnpj_basico_fornecedor",
              "ALTER TABLE pncp_contrato ADD COLUMN IF NOT EXISTS cnpj_basico_fornecedor TEXT")
        _exec(conn, "pncp_contrato: UPDATE cnpj_basico_fornecedor",
              "UPDATE pncp_contrato SET cnpj_basico_fornecedor = LEFT(REGEXP_REPLACE(ni_fornecedor, '[^0-9]', '', 'g'), 8) WHERE cnpj_basico_fornecedor IS NULL AND ni_fornecedor IS NOT NULL AND LENGTH(ni_fornecedor) >= 8")

        # Emenda favorecido cnpj_basico (somente CNPJ puro digitos — PF tem CPF mascarado com */-,  LEFT(8) gera lixo)
        _exec(conn, "emenda_favorecido: ADD cnpj_basico_favorecido",
              "ALTER TABLE emenda_favorecido ADD COLUMN IF NOT EXISTS cnpj_basico_favorecido TEXT")
        _exec(conn, "emenda_favorecido: UPDATE cnpj_basico_favorecido (CNPJ only)",
              "UPDATE emenda_favorecido SET cnpj_basico_favorecido = LEFT(codigo_favorecido, 8) WHERE cnpj_basico_favorecido IS NULL AND codigo_favorecido IS NOT NULL AND codigo_favorecido ~ '^[0-9]+$'")
        _exec(conn, "emenda_favorecido: LIMPAR cnpj_basico_favorecido quebrado (non-CNPJ)",
              "UPDATE emenda_favorecido SET cnpj_basico_favorecido = NULL WHERE codigo_favorecido ~ '[^0-9]' AND cnpj_basico_favorecido IS NOT NULL")

        print("\n  === Fase 2: Índices em colunas desnormalizadas ===")

        _exec(conn, "idx pgfn_norm", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pgfn_norm ON pgfn_divida(cpf_cnpj_norm)", autocommit=True)
        _exec(conn, "idx socio_norm", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_socio_norm ON socio(cpf_cnpj_norm) WHERE cpf_cnpj_norm IS NOT NULL AND cpf_cnpj_norm != '000000'", autocommit=True)
        _exec(conn, "idx bf_cpf_digitos", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_bf_cpf_digitos ON bolsa_familia(cpf_digitos)", autocommit=True)
        _exec(conn, "idx siape_cpf_digitos", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_siape_cpf_digitos ON siape_cadastro(cpf_digitos)", autocommit=True)
        _exec(conn, "idx cpgf_portador_digitos", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cpgf_portador_digitos ON cpgf_transacao(cpf_portador_digitos)", autocommit=True)
        _exec(conn, "idx ceis_norm", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ceis_norm ON ceis_sancao(cpf_cnpj_norm)", autocommit=True)
        _exec(conn, "idx cnep_norm", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cnep_norm ON cnep_sancao(cpf_cnpj_norm)", autocommit=True)
        _exec(conn, "idx ceaf_norm", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ceaf_norm ON ceaf_expulsao(cpf_cnpj_norm)", autocommit=True)
        _exec(conn, "idx ceis_digitos6", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ceis_cpf_digitos_6 ON ceis_sancao(cpf_digitos_6) WHERE cpf_digitos_6 IS NOT NULL", autocommit=True)
        _exec(conn, "idx cnep_digitos6", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cnep_cpf_digitos_6 ON cnep_sancao(cpf_digitos_6) WHERE cpf_digitos_6 IS NOT NULL", autocommit=True)
        _exec(conn, "idx acordo_norm", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_acordo_norm ON acordo_leniencia(cnpj_norm)", autocommit=True)
        _exec(conn, "idx viagem_digitos", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_viagem_cpf_digitos ON viagem(cpf_viajante_digitos)", autocommit=True)
        _exec(conn, "idx pncp_cnpj_basico", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pnpc_contrato_cnpj_basico ON pncp_contrato(cnpj_basico_fornecedor)", autocommit=True)
        _exec(conn, "idx emfav_cnpj_basico", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_emfav_cnpj_basico ON emenda_favorecido(cnpj_basico_favorecido)", autocommit=True)

        # Compostos: cpf_norm + nome (movidos de 11_indices.sql pois dependem de colunas criadas aqui)
        _exec(conn, "idx socio_norm_nome", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_socio_norm_nome ON socio(cpf_cnpj_norm, UPPER(TRIM(nome))) WHERE cpf_cnpj_norm IS NOT NULL AND cpf_cnpj_norm <> '000000'", autocommit=True)
        _exec(conn, "idx bf_cpf_nome", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_bf_cpf_nome ON bolsa_familia(cpf_digitos, UPPER(TRIM(nm_favorecido))) WHERE cpf_digitos IS NOT NULL", autocommit=True)

        print("\n  === Fase 3: Índices funcionais para queries ===")

        _exec(conn, "idx pncp LEFT8", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pncp_contrato_forn_left8 ON pncp_contrato (LEFT(ni_fornecedor, 8))", autocommit=True)
        _exec(conn, "idx emfav LEFT8", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_emfav_favorecido_left8 ON emenda_favorecido (LEFT(codigo_favorecido, 8))", autocommit=True)
        _exec(conn, "idx cpgf fav LEFT8", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cpgf_favorecido_left8 ON cpgf_transacao (LEFT(cnpj_cpf_favorecido, 8))", autocommit=True)
        _exec(conn, "idx bndes LEFT8", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_bndes_cnpj_left8 ON bndes_contrato (LEFT(cnpj, 8))", autocommit=True)
        _exec(conn, "idx pgfn LEFT8", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pgfn_cpf_cnpj_left8 ON pgfn_divida (LEFT(cpf_cnpj, 8))", autocommit=True)
        _exec(conn, "idx pgfn norm LEFT8", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pgfn_norm_left8 ON pgfn_divida (LEFT(cpf_cnpj_norm, 8)) WHERE LENGTH(cpf_cnpj_norm) = 14", autocommit=True)
        _exec(conn, "idx pncp municipio_uf", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pncp_municipio_uf ON pncp_contrato(municipio_nome, uf)", autocommit=True)

        _exec(conn, "idx bf UPPER nome", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_bf_nome_upper ON bolsa_familia (UPPER(TRIM(nm_favorecido)))", autocommit=True)
        _exec(conn, "idx socio UPPER nome", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_socio_nome_upper ON socio (UPPER(TRIM(nome)))", autocommit=True)
        _exec(conn, "idx siape UPPER nome", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_siape_nome_upper ON siape_cadastro (UPPER(TRIM(nome)))", autocommit=True)
        _exec(conn, "idx cpgf UPPER portador", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cpgf_portador_nome_upper ON cpgf_transacao (UPPER(TRIM(nome_portador)))", autocommit=True)

        # Compostos: CPF digitos + nome (para JOINs que usam CPF mascarado 6 dig)
        _exec(conn, "idx cpgf cpf+nome", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cpgf_portador_cpf_nome ON cpgf_transacao(cpf_portador_digitos, UPPER(TRIM(nome_portador))) WHERE cpf_portador_digitos IS NOT NULL AND cpf_portador_digitos != '000000'", autocommit=True)
        _exec(conn, "idx siape cpf+nome", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_siape_cpf_nome ON siape_cadastro(cpf_digitos, UPPER(TRIM(nome))) WHERE cpf_digitos IS NOT NULL AND cpf_digitos != '000000'", autocommit=True)
        _exec(conn, "idx viagem cpf+nome", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_viagem_cpf_nome ON viagem(cpf_viajante_digitos, UPPER(TRIM(nome_viajante))) WHERE cpf_viajante_digitos IS NOT NULL AND cpf_viajante_digitos != '000000'", autocommit=True)

        print("\n  === Fase 4: Índices de datas e compostos ===")

        _exec(conn, "idx pncp dt_assinatura", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pncp_contrato_dt_assinatura ON pncp_contrato (dt_assinatura)", autocommit=True)
        _exec(conn, "idx cpgf dt_transacao", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cpgf_dt_transacao ON cpgf_transacao (dt_transacao)", autocommit=True)
        _exec(conn, "idx viagem dt_inicio", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_viagem_dt_inicio ON viagem (dt_inicio)", autocommit=True)
        _exec(conn, "idx estab matriz ativa", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_estab_matriz_ativa ON estabelecimento (cnpj_basico) WHERE cnpj_ordem = '0001' AND situacao_cadastral = '2'", autocommit=True)

        print("\n  === Fase 5: TCE-PB normalização ===")

        # tce_pb_despesa: cnpj_basico (8 dig) para JOINs
        _exec(conn, "tce_desp: ADD cnpj_basico",
              "ALTER TABLE tce_pb_despesa ADD COLUMN IF NOT EXISTS cnpj_basico VARCHAR(8)")
        _exec(conn, "tce_desp: UPDATE cnpj_basico",
              "UPDATE tce_pb_despesa SET cnpj_basico = LEFT(cpf_cnpj, 8) WHERE cnpj_basico IS NULL AND LENGTH(cpf_cnpj) = 14")
        _exec(conn, "tce_desp: ADD ano",
              "ALTER TABLE tce_pb_despesa ADD COLUMN IF NOT EXISTS ano SMALLINT")
        _exec(conn, "tce_desp: UPDATE ano",
              "UPDATE tce_pb_despesa SET ano = COALESCE(EXTRACT(YEAR FROM data_empenho)::SMALLINT, ano_arquivo) WHERE ano IS NULL")

        # tce_pb_servidor: cpf_digitos_6 (6 centrais do CPF mascarado)
        _exec(conn, "tce_serv: ADD cpf_digitos_6",
              "ALTER TABLE tce_pb_servidor ADD COLUMN IF NOT EXISTS cpf_digitos_6 VARCHAR(6)")
        _exec(conn, "tce_serv: UPDATE cpf_digitos_6",
              "UPDATE tce_pb_servidor SET cpf_digitos_6 = REGEXP_REPLACE(cpf_cnpj, '[^0-9]', '', 'g') WHERE cpf_digitos_6 IS NULL AND cpf_cnpj LIKE '***%'")
        _exec(conn, "tce_serv: ADD nome_upper",
              "ALTER TABLE tce_pb_servidor ADD COLUMN IF NOT EXISTS nome_upper TEXT")
        _exec(conn, "tce_serv: UPDATE nome_upper",
              "UPDATE tce_pb_servidor SET nome_upper = UPPER(TRIM(nome_servidor)) WHERE nome_upper IS NULL AND nome_servidor IS NOT NULL")

        # tce_pb_licitacao: cnpj_basico e cpf_digitos para proponentes
        _exec(conn, "tce_lic: ADD cnpj_basico_proponente",
              "ALTER TABLE tce_pb_licitacao ADD COLUMN IF NOT EXISTS cnpj_basico_proponente VARCHAR(8)")
        _exec(conn, "tce_lic: UPDATE cnpj_basico_proponente",
              "UPDATE tce_pb_licitacao SET cnpj_basico_proponente = LEFT(cpf_cnpj_proponente, 8) WHERE cnpj_basico_proponente IS NULL AND LENGTH(cpf_cnpj_proponente) >= 14")
        _exec(conn, "tce_lic: ADD cpf_digitos_proponente",
              "ALTER TABLE tce_pb_licitacao ADD COLUMN IF NOT EXISTS cpf_digitos_proponente VARCHAR(6)")
        _exec(conn, "tce_lic: UPDATE cpf_digitos_proponente",
              "UPDATE tce_pb_licitacao SET cpf_digitos_proponente = SUBSTRING(cpf_cnpj_proponente, 4, 6) WHERE cpf_digitos_proponente IS NULL AND LENGTH(cpf_cnpj_proponente) = 11")

        print("\n  === Fase 6: TCE-PB índices ===")

        _exec(conn, "idx tce_desp cnpj_basico", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tce_desp_cnpj_basico ON tce_pb_despesa(cnpj_basico)", autocommit=True)
        _exec(conn, "idx tce_desp ano", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tce_desp_ano ON tce_pb_despesa(ano)", autocommit=True)
        _exec(conn, "idx tce_desp modalidade_lic", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tce_desp_modalidade_lic ON tce_pb_despesa(modalidade_licitacao)", autocommit=True)
        _exec(conn, "idx tce_desp funcao", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tce_desp_funcao ON tce_pb_despesa(codigo_funcao)", autocommit=True)
        _exec(conn, "idx tce_desp mun+cnpj", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tce_desp_mun_cnpj ON tce_pb_despesa(municipio, cpf_cnpj)", autocommit=True)
        _exec(conn, "idx tce_serv cpf_dig6", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tce_serv_cpf_dig6 ON tce_pb_servidor(cpf_digitos_6)", autocommit=True)
        _exec(conn, "idx tce_serv nome_upper", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tce_serv_nome_upper ON tce_pb_servidor(nome_upper)", autocommit=True)
        _exec(conn, "idx tce_lic cnpj_basico", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tce_lic_cnpj_basico ON tce_pb_licitacao(cnpj_basico_proponente)", autocommit=True)
        _exec(conn, "idx tce_lic objeto trgm", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tce_lic_objeto_trgm ON tce_pb_licitacao USING gin(objeto_licitacao gin_trgm_ops)", autocommit=True)

        print("\n  === Fase 7: dados.pb.gov.br normalização ===")

        # pb_pagamento: cpfcnpj_credor ja limpo no ETL. Adicionar cnpj_basico e cpf_digitos_6
        _exec(conn, "pb_pag: ADD cnpj_basico",
              "ALTER TABLE pb_pagamento ADD COLUMN IF NOT EXISTS cnpj_basico VARCHAR(8)")
        _exec(conn, "pb_pag: UPDATE cnpj_basico",
              "UPDATE pb_pagamento SET cnpj_basico = LEFT(cpfcnpj_credor, 8) WHERE cnpj_basico IS NULL AND LENGTH(cpfcnpj_credor) = 14")
        _exec(conn, "pb_pag: ADD cpf_digitos_6",
              "ALTER TABLE pb_pagamento ADD COLUMN IF NOT EXISTS cpf_digitos_6 VARCHAR(6)")
        _exec(conn, "pb_pag: UPDATE cpf_digitos_6",
              "UPDATE pb_pagamento SET cpf_digitos_6 = SUBSTRING(cpfcnpj_credor, 4, 6) WHERE cpf_digitos_6 IS NULL AND LENGTH(cpfcnpj_credor) = 11 AND cpfcnpj_credor NOT LIKE '***%'")
        _exec(conn, "pb_pag: ADD nome_upper",
              "ALTER TABLE pb_pagamento ADD COLUMN IF NOT EXISTS nome_upper TEXT")
        _exec(conn, "pb_pag: UPDATE nome_upper",
              "UPDATE pb_pagamento SET nome_upper = UPPER(TRIM(nome_credor)) WHERE nome_upper IS NULL AND nome_credor IS NOT NULL")

        # pb_empenho: cnpj_basico (PJ) — CPF mascarado com *** nao tem digitos uteis
        _exec(conn, "pb_emp: ADD cnpj_basico",
              "ALTER TABLE pb_empenho ADD COLUMN IF NOT EXISTS cnpj_basico VARCHAR(8)")
        _exec(conn, "pb_emp: UPDATE cnpj_basico",
              "UPDATE pb_empenho SET cnpj_basico = LEFT(cpfcnpj_credor, 8) WHERE cnpj_basico IS NULL AND LENGTH(cpfcnpj_credor) = 14 AND cpfcnpj_credor NOT LIKE '***%'")

        # pb_contrato: cnpj_basico
        _exec(conn, "pb_ctr: ADD cnpj_basico",
              "ALTER TABLE pb_contrato ADD COLUMN IF NOT EXISTS cnpj_basico VARCHAR(8)")
        _exec(conn, "pb_ctr: UPDATE cnpj_basico",
              "UPDATE pb_contrato SET cnpj_basico = LEFT(cpfcnpj_contratado, 8) WHERE cnpj_basico IS NULL AND LENGTH(cpfcnpj_contratado) = 14 AND cpfcnpj_contratado NOT LIKE '***%'")

        # pb_saude: cnpj_basico
        _exec(conn, "pb_saude: ADD cnpj_basico",
              "ALTER TABLE pb_saude ADD COLUMN IF NOT EXISTS cnpj_basico VARCHAR(8)")
        _exec(conn, "pb_saude: UPDATE cnpj_basico",
              "UPDATE pb_saude SET cnpj_basico = LEFT(cpfcnpj_credor, 8) WHERE cnpj_basico IS NULL AND LENGTH(cpfcnpj_credor) = 14")

        # pb_convenio: cnpj_basico
        _exec(conn, "pb_conv: ADD cnpj_basico",
              "ALTER TABLE pb_convenio ADD COLUMN IF NOT EXISTS cnpj_basico VARCHAR(8)")
        _exec(conn, "pb_conv: UPDATE cnpj_basico",
              "UPDATE pb_convenio SET cnpj_basico = LEFT(cnpj_convenente, 8) WHERE cnpj_basico IS NULL AND LENGTH(cnpj_convenente) = 14")

        # pb_liquidacao_despesa: cnpj_basico (PJ; CPF pode vir mascarado)
        _exec(conn, "pb_liq_desp: ADD cnpj_basico",
              "ALTER TABLE pb_liquidacao_despesa ADD COLUMN IF NOT EXISTS cnpj_basico VARCHAR(8)")
        _exec(conn, "pb_liq_desp: UPDATE cnpj_basico",
              "UPDATE pb_liquidacao_despesa SET cnpj_basico = LEFT(cpfcnpj_credor, 8) WHERE cnpj_basico IS NULL AND LENGTH(cpfcnpj_credor) = 14 AND cpfcnpj_credor NOT LIKE '***%'")

        # pb_empenho_anulacao: cnpj_basico + nome_upper
        _exec(conn, "pb_emp_anul: ADD cnpj_basico",
              "ALTER TABLE pb_empenho_anulacao ADD COLUMN IF NOT EXISTS cnpj_basico VARCHAR(8)")
        _exec(conn, "pb_emp_anul: UPDATE cnpj_basico",
              "UPDATE pb_empenho_anulacao SET cnpj_basico = LEFT(cpfcnpj_credor, 8) WHERE cnpj_basico IS NULL AND LENGTH(cpfcnpj_credor) = 14 AND cpfcnpj_credor NOT LIKE '***%'")
        _exec(conn, "pb_emp_anul: ADD nome_upper",
              "ALTER TABLE pb_empenho_anulacao ADD COLUMN IF NOT EXISTS nome_upper TEXT")
        _exec(conn, "pb_emp_anul: UPDATE nome_upper",
              "UPDATE pb_empenho_anulacao SET nome_upper = UPPER(TRIM(nome_credor)) WHERE nome_upper IS NULL AND nome_credor IS NOT NULL")

        # pb_empenho_suplementacao: cnpj_basico + nome_upper
        _exec(conn, "pb_emp_supl: ADD cnpj_basico",
              "ALTER TABLE pb_empenho_suplementacao ADD COLUMN IF NOT EXISTS cnpj_basico VARCHAR(8)")
        _exec(conn, "pb_emp_supl: UPDATE cnpj_basico",
              "UPDATE pb_empenho_suplementacao SET cnpj_basico = LEFT(cpfcnpj_credor, 8) WHERE cnpj_basico IS NULL AND LENGTH(cpfcnpj_credor) = 14 AND cpfcnpj_credor NOT LIKE '***%'")
        _exec(conn, "pb_emp_supl: ADD nome_upper",
              "ALTER TABLE pb_empenho_suplementacao ADD COLUMN IF NOT EXISTS nome_upper TEXT")
        _exec(conn, "pb_emp_supl: UPDATE nome_upper",
              "UPDATE pb_empenho_suplementacao SET nome_upper = UPPER(TRIM(nome_credor)) WHERE nome_upper IS NULL AND nome_credor IS NOT NULL")

        # pb_diaria: cnpj_basico + nome_upper
        _exec(conn, "pb_diaria: ADD cnpj_basico",
              "ALTER TABLE pb_diaria ADD COLUMN IF NOT EXISTS cnpj_basico VARCHAR(8)")
        _exec(conn, "pb_diaria: UPDATE cnpj_basico",
              "UPDATE pb_diaria SET cnpj_basico = LEFT(cpfcnpj_credor, 8) WHERE cnpj_basico IS NULL AND LENGTH(cpfcnpj_credor) = 14 AND cpfcnpj_credor NOT LIKE '***%'")
        _exec(conn, "pb_diaria: ADD nome_upper",
              "ALTER TABLE pb_diaria ADD COLUMN IF NOT EXISTS nome_upper TEXT")
        _exec(conn, "pb_diaria: UPDATE nome_upper",
              "UPDATE pb_diaria SET nome_upper = UPPER(TRIM(nome_credor)) WHERE nome_upper IS NULL AND nome_credor IS NOT NULL")

        print("\n  === Fase 8: dados.pb.gov.br índices ===")

        _exec(conn, "idx pb_pag cnpj_basico", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pb_pag_cnpj_basico ON pb_pagamento(cnpj_basico)", autocommit=True)
        _exec(conn, "idx pb_pag cpf_dig6", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pb_pag_cpf_dig6 ON pb_pagamento(cpf_digitos_6)", autocommit=True)
        _exec(conn, "idx pb_pag nome_upper", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pb_pag_nome_upper ON pb_pagamento(nome_upper)", autocommit=True)
        _exec(conn, "idx pb_emp cnpj_basico", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pb_emp_cnpj_basico ON pb_empenho(cnpj_basico)", autocommit=True)
        _exec(conn, "idx pb_ctr cnpj_basico", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pb_ctr_cnpj_basico ON pb_contrato(cnpj_basico)", autocommit=True)
        _exec(conn, "idx pb_saude cnpj_basico", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pb_saude_cnpj_basico ON pb_saude(cnpj_basico)", autocommit=True)
        _exec(conn, "idx pb_conv cnpj_basico", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pb_conv_cnpj_basico ON pb_convenio(cnpj_basico)", autocommit=True)
        _exec(conn, "idx pb_liq_desp cnpj_basico", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pb_liq_desp_cnpj_basico ON pb_liquidacao_despesa(cnpj_basico)", autocommit=True)
        _exec(conn, "idx pb_emp_anul cnpj_basico", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pb_emp_anul_cnpj_basico ON pb_empenho_anulacao(cnpj_basico)", autocommit=True)
        _exec(conn, "idx pb_emp_anul nome_upper", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pb_emp_anul_nome_upper ON pb_empenho_anulacao(nome_upper)", autocommit=True)
        _exec(conn, "idx pb_emp_supl cnpj_basico", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pb_emp_supl_cnpj_basico ON pb_empenho_suplementacao(cnpj_basico)", autocommit=True)
        _exec(conn, "idx pb_emp_supl nome_upper", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pb_emp_supl_nome_upper ON pb_empenho_suplementacao(nome_upper)", autocommit=True)
        _exec(conn, "idx pb_diaria cnpj_basico", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pb_diaria_cnpj_basico ON pb_diaria(cnpj_basico)", autocommit=True)
        _exec(conn, "idx pb_diaria nome_upper", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pb_diaria_nome_upper ON pb_diaria(nome_upper)", autocommit=True)

        print("\n  Normalização e índices concluídos.")

    finally:
        conn.close()


if __name__ == "__main__":
    run()
