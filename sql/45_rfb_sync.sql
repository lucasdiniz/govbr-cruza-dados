-- =============================================================================
-- sql/45_rfb_sync.sql — suporte ao sync mensal RFB (etl/rfb_sync.py)
-- =============================================================================
-- Idempotente (IF NOT EXISTS). Aplicado pelo proprio etl.rfb_sync no inicio
-- de cada execucao; nao toca nas tabelas RFB existentes.
--
-- rfb_sync_log          : 1 linha por tentativa de sync (auditoria + "ja
--                         sincronizado?" + bloqueio de regressao de mes).
-- socio_historico       : vinculos de socio que sairam da base RFB. O sync
--                         MOVE a linha de `socio` para ca (mesmo id) em vez de
--                         marcar in-place, para que todas as queries existentes
--                         sobre `socio` continuem significando "socio atual".
-- rfb_sync_estab_delta  : estabelecimentos inseridos/removidos no ultimo sync.
--                         Consumido por refresh_post_incremental --source rfb
--                         para re-ligar/anular cnpj_basico nas tabelas PB de
--                         forma direcionada (sem varrer 16M+ linhas inteiras).
-- =============================================================================

CREATE TABLE IF NOT EXISTS rfb_sync_log (
    id              BIGSERIAL PRIMARY KEY,
    rfb_mes         CHAR(7) NOT NULL,              -- 'YYYY-MM' da publicacao RFB
    status          TEXT NOT NULL
                    CHECK (status IN ('running', 'success', 'failed', 'aborted')),
    iniciado_em     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finalizado_em   TIMESTAMPTZ,
    stats           JSONB NOT NULL DEFAULT '{}'::jsonb,
    erro            TEXT
);

CREATE INDEX IF NOT EXISTS idx_rfb_sync_log_mes_status
    ON rfb_sync_log (rfb_mes, status);

CREATE TABLE IF NOT EXISTS socio_historico (
    id                   INTEGER NOT NULL,         -- id original em socio
    cnpj_basico          CHAR(8) NOT NULL,
    tipo_socio           SMALLINT,
    nome                 VARCHAR(500),
    cpf_cnpj_socio       VARCHAR(50),
    qualificacao         VARCHAR(50),
    dt_entrada           DATE,
    pais                 VARCHAR(50),
    cpf_representante    VARCHAR(50),
    nome_representante   VARCHAR(500),
    qualif_representante VARCHAR(50),
    faixa_etaria         SMALLINT,
    cpf_cnpj_norm        TEXT,
    removido_em          DATE NOT NULL,            -- data do sync que detectou a saida
    rfb_mes_removido     CHAR(7) NOT NULL,         -- 1a publicacao RFB sem o vinculo
    PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS idx_socio_hist_cnpj_basico ON socio_historico (cnpj_basico);
CREATE INDEX IF NOT EXISTS idx_socio_hist_cpf_norm
    ON socio_historico (cpf_cnpj_norm) WHERE cpf_cnpj_norm IS NOT NULL;

CREATE TABLE IF NOT EXISTS rfb_sync_estab_delta (
    cnpj_completo   CHAR(14) NOT NULL,
    mudanca         TEXT NOT NULL CHECK (mudanca IN ('inserido', 'removido')),
    rfb_mes         CHAR(7) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_rfb_sync_estab_delta_cnpj
    ON rfb_sync_estab_delta (cnpj_completo);
