-- Decisoes individuais do TCE-PB extraidas do DOE eletronico.
-- Fonte: https://publicacao.tce.pb.gov.br/decisao.php?ano=YYYY
-- Cada PDF e uma decisao individual (acordao, decisao_singular, resolucao etc).
-- Um processo (NNNNN/AA) agrupa 1..N decisoes ao longo do tempo.
--
-- Estrategia de parsing: ver etl/23_tce_pb_doe.py.
-- ADR-0014 documenta a feature "Empresa citada em processos do TCE-PB".

CREATE TABLE IF NOT EXISTS tce_pb_decisao (
    _nk_md5            CHAR(32) PRIMARY KEY,
    hash_publicacao    CHAR(32) NOT NULL UNIQUE,
    num_processo       VARCHAR(10) NOT NULL,
    ano_processo       SMALLINT    NOT NULL,
    tipo_decisao       VARCHAR(40),
    orgao_julgador     VARCHAR(10),
    num_decisao        VARCHAR(10),
    ano_decisao        SMALLINT,
    fase               VARCHAR(60),
    data_sessao        DATE,
    tipo_materia       VARCHAR(20) NOT NULL,
    resultado          VARCHAR(20),
    aplicou_multa      BOOLEAN NOT NULL DEFAULT false,
    imputou_debito     BOOLEAN NOT NULL DEFAULT false,
    valor_multa_rs     NUMERIC(14,2),
    valor_debito_rs    NUMERIC(14,2),
    municipio_inferido VARCHAR(120),
    text_sha256        CHAR(64),
    parser_version     SMALLINT NOT NULL DEFAULT 1,
    ingerido_em        TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE  tce_pb_decisao IS 'Decisoes individuais do TCE-PB extraidas do DOE. Uma linha = um PDF de publicacao.tce.pb.gov.br. ADR-0014.';
COMMENT ON COLUMN tce_pb_decisao._nk_md5 IS 'md5(num_processo||ano_processo||tipo_decisao||num_decisao||ano_decisao||fase). NK estavel; permite reprocess sem mudar PK.';
COMMENT ON COLUMN tce_pb_decisao.hash_publicacao IS 'Hash de 32 chars que o TCE-PB usa como URL publica (publicacao.tce.pb.gov.br/<hash>). Imutavel por decisao.';
COMMENT ON COLUMN tce_pb_decisao.tipo_materia IS 'Classificacao por dominio: pca, licitacao, denuncia, contrato, representacao, recurso, embargos, tce_especial, atos_pessoal (excluido de agregados), indef.';
COMMENT ON COLUMN tce_pb_decisao.resultado IS 'Output do classificador: irregular | regular_ressalva | regular | indef. Calibrado em 9.935 PDFs (ver ADR-0014).';
COMMENT ON COLUMN tce_pb_decisao.parser_version IS 'Versao do parser que produziu esta linha. Bump = reprocess sem refazer download.';

CREATE INDEX IF NOT EXISTS ix_tce_pb_decisao_proc       ON tce_pb_decisao (num_processo, ano_processo);
CREATE INDEX IF NOT EXISTS ix_tce_pb_decisao_data       ON tce_pb_decisao (data_sessao DESC);
CREATE INDEX IF NOT EXISTS ix_tce_pb_decisao_municipio  ON tce_pb_decisao (lower(municipio_inferido));
CREATE INDEX IF NOT EXISTS ix_tce_pb_decisao_tipo_mat   ON tce_pb_decisao (tipo_materia) WHERE tipo_materia <> 'atos_pessoal';

-- ── CNPJs citados em cada decisao ────────────────────────────────────────────
-- 1 decisao → N CNPJs. Modelo append-only (CASCADE no delete da decisao garante coerencia).
CREATE TABLE IF NOT EXISTS tce_pb_decisao_cnpj (
    decisao_md5  CHAR(32) NOT NULL REFERENCES tce_pb_decisao(_nk_md5) ON DELETE CASCADE,
    cnpj         CHAR(14) NOT NULL,
    PRIMARY KEY (decisao_md5, cnpj)
);

COMMENT ON TABLE tce_pb_decisao_cnpj IS 'Bag de CNPJs (14 digitos) citados em cada decisao do TCE-PB. ADR-0014.';

CREATE INDEX IF NOT EXISTS ix_tce_pb_decisao_cnpj_cnpj ON tce_pb_decisao_cnpj (cnpj);

-- LGPD: NAO persistimos CPF cru (3% dos PDFs tem CPF completo). Para v2 (feature de pessoa)
-- persistir apenas cpf_digitos_6 (padrao do projeto, conforme docs/privacidade.md).

-- ─────────────────────────────────────────────────────────────────────────────
-- mv_empresa_tce_pb (bootstrap idempotente)
-- ─────────────────────────────────────────────────────────────────────────────
-- A definicao "viva" desta MV mora em sql/12_views.sql:476 (re-criada por
-- etl.21_views). Aqui replicamos com IF NOT EXISTS so para o BOOTSTRAP inicial
-- antes de mv_swap ou refresh ETL (etl/mv_swap.py:236-238 aborta se a MV nao
-- existe). Em deploy "incremental" / "web", este bloco cria MV VAZIA na 1a vez
-- e e no-op nas demais. ATENCAO: ao alterar a SELECT, alterar tambem
-- sql/12_views.sql (drift checado em PR review).
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_empresa_tce_pb AS
WITH base AS (
    SELECT
        LEFT(dc.cnpj, 8)              AS cnpj_basico,
        d._nk_md5,
        d.hash_publicacao,
        d.num_processo,
        d.ano_processo,
        d.tipo_decisao,
        d.orgao_julgador,
        d.fase,
        d.data_sessao,
        d.tipo_materia,
        d.resultado,
        d.aplicou_multa,
        d.imputou_debito,
        COALESCE(d.valor_multa_rs, 0)  AS valor_multa_rs,
        COALESCE(d.valor_debito_rs, 0) AS valor_debito_rs,
        d.municipio_inferido
    FROM tce_pb_decisao d
    JOIN tce_pb_decisao_cnpj dc ON dc.decisao_md5 = d._nk_md5
    WHERE d.tipo_materia <> 'atos_pessoal'
      AND EXISTS (
          SELECT 1 FROM estabelecimento e
          WHERE e.cnpj_basico = LEFT(dc.cnpj, 8)
      )
),
processos AS (
    SELECT
        cnpj_basico,
        num_processo,
        ano_processo,
        MAX(tipo_materia)               AS tipo_materia,
        MAX(orgao_julgador)             AS orgao,
        MAX(municipio_inferido)         AS municipio,
        MAX(data_sessao)                AS ultima_sessao,
        COUNT(*)                        AS qtd_decisoes,
        MIN(CASE resultado
              WHEN 'irregular'        THEN 1
              WHEN 'regular_ressalva' THEN 2
              WHEN 'regular'          THEN 3
              ELSE 4
            END)                        AS pior_resultado_rank,
        bool_or(aplicou_multa)          AS tem_multa,
        bool_or(imputou_debito)         AS tem_debito,
        SUM(valor_multa_rs)             AS multa_total_rs,
        SUM(valor_debito_rs)            AS debito_total_rs,
        jsonb_agg(
            jsonb_build_object(
                'hash',   hash_publicacao,
                'fase',   fase,
                'data',   data_sessao,
                'result', resultado
            )
            ORDER BY data_sessao DESC NULLS LAST
        )                               AS decisoes_json
    FROM base
    GROUP BY cnpj_basico, num_processo, ano_processo
)
SELECT
    p.cnpj_basico,
    COUNT(*)::int                                                  AS qtd_processos,
    SUM(p.qtd_decisoes)::int                                       AS qtd_decisoes,
    COUNT(*) FILTER (WHERE p.pior_resultado_rank = 1)::int         AS qtd_processos_irregular,
    COUNT(*) FILTER (WHERE p.tem_multa)::int                       AS qtd_processos_multa,
    COUNT(*) FILTER (WHERE p.tem_debito)::int                      AS qtd_processos_debito,
    COALESCE(SUM(p.multa_total_rs), 0)::numeric(14,2)              AS multa_total_rs,
    COALESCE(SUM(p.debito_total_rs), 0)::numeric(14,2)             AS debito_total_rs,
    MAX(p.ultima_sessao)                                           AS ultima_decisao_em,
    (
        SELECT jsonb_agg(row_to_json(top20)::jsonb)
        FROM (
            SELECT
                p2.num_processo,
                p2.ano_processo,
                p2.tipo_materia,
                p2.orgao,
                p2.municipio,
                p2.ultima_sessao,
                p2.qtd_decisoes,
                CASE p2.pior_resultado_rank
                    WHEN 1 THEN 'irregular'
                    WHEN 2 THEN 'regular_ressalva'
                    WHEN 3 THEN 'regular'
                    ELSE        'indef'
                END                        AS pior_resultado,
                p2.tem_multa,
                p2.tem_debito,
                p2.decisoes_json           AS decisoes
            FROM processos p2
            WHERE p2.cnpj_basico = p.cnpj_basico
            ORDER BY p2.ultima_sessao DESC NULLS LAST,
                     p2.ano_processo DESC,
                     p2.num_processo DESC
            LIMIT 20
        ) top20
    )                                                              AS processos_json
FROM processos p
GROUP BY p.cnpj_basico;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_empresa_tce_pb_cnpj      ON mv_empresa_tce_pb(cnpj_basico);
CREATE INDEX        IF NOT EXISTS idx_mv_empresa_tce_pb_irregular ON mv_empresa_tce_pb(cnpj_basico)
    WHERE qtd_processos_irregular > 0;
CREATE INDEX        IF NOT EXISTS idx_mv_empresa_tce_pb_multa     ON mv_empresa_tce_pb(cnpj_basico)
    WHERE qtd_processos_multa > 0 OR qtd_processos_debito > 0;
