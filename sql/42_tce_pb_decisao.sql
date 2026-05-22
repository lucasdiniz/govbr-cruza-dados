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
