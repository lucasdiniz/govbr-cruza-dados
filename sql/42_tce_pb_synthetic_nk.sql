-- Migration: tce_pb_despesa/servidor/licitacao/receita para NK sintetica md5.
-- Framework ETL incremental (P1-P6). Padrao sql/35a-d (pb_extras) e sql/41 (BF).
--
-- Aplicada pelo step "ETL: Incremental" do deploy.yml quando TCE-PB esta no
-- escopo (etl_phase=incremental). Idempotente — pode ser re-aplicada sem dano.
--
-- IMPORTANTE: os UNIQUE INDEX CONCURRENTLY ficam em sql/42z (rodam APOS o
-- populate). Esta migration so tem DDL segura em transacao. Aplicar via
-- `psql -v ON_ERROR_STOP=1 -f` SEM `--single-transaction`.
--
-- ── Por que synthetic md5 e nao NK natural? (ADR-0014) ──────────────────────
--
-- Analise empirica em prod (2026-06):
--
-- 1. tce_pb_despesa (16.2M rows): a NK candidata do spec tem 1037 grupos
--    (2530 rows) com >1 ocorrencia, e ZERO sao duplicatas — todos tem
--    valor_*/cpf_cnpj/nome_credor/historico DISTINTOS (empenhos/parcelas
--    legitimamente diferentes que a NK nao distingue). UNIQUE INDEX na NK
--    seria errado e UPSERT_DO_NOTHING PULARIA novos registros distintos.
--
-- 2. tce_pb_servidor (22.2M rows): a NK natural inclui colunas NULLABLE
--    nao-coalescidas (municipio: 90.047 NULL; nome_servidor: 201 NULL). Em
--    PostgreSQL, UNIQUE INDEX trata NULL como DISTINTO, entao essas 90k+ rows
--    NAO seriam deduplicadas e ON CONFLICT NAO dispararia -> cada re-run do
--    bucket DUPLICARIA essas rows. NK natural e inseguro aqui.
--
-- 3. tce_pb_licitacao / tce_pb_receita: NK natural seria segura hoje
--    (0 NULL nas cols nao-coalescidas), mas usamos md5 por UNIFORMIDADE e
--    para nao depender de auditoria de NULL a cada mudanca de dados upstream.
--
-- Synthetic md5 (hash de TODAS as cols de negocio) so colapsa rows
-- byte-a-byte identicas (true duplicates do ETL classico, que fazia INSERT
-- plano sem dedup). Cobre 100% sem perda e trata NULL uniformemente
-- (coalesce -> '').
--
-- ── Idempotencia cross-boundary (ETL classico -> incremental) ──────────────
--
-- Para que re-inserir um bucket ja carregado NAO duplique, o _nk_md5 de uma
-- row re-inserida (trigger) deve igualar o da row legacy (populate). Garantido
-- porque ambos usam a MESMA funcao de hash (etl_admin.nk_md5_<tabela>_row,
-- single source of truth) e os valores armazenados sao canonicos:
--   * TEXT: ETL classico (etl/19_tce_pb.py) e o framework (build_typed_select)
--     ambos aplicam trim. coalesce(col,'').
--   * DECIMAL(15,2): escala fixa pela coluna -> ::text canonico ('N.NN') em
--     ambos os caminhos (validado: 10.50 armazenado -> '10.50').
--   * DATE: to_char(col,'YYYY-MM-DD').
--   * SMALLINT (ano_arquivo/ano_licitacao/receita.ano): ::text.
-- Cols de NORMALIZACAO sao EXCLUIDAS do hash (ficam NULL em rows recem-
-- inseridas, populadas por fase posterior, e preenchidas em rows legacy ->
-- inclui-las quebraria a idempotencia):
--   * despesa:   cnpj_basico, cpf_digitos, e `ano` (SMALLINT dup de
--                ano_arquivo criada pela normalizacao — o hash usa ano_arquivo).
--   * servidor:  cpf_digitos_6, nome_upper.
--   * licitacao: cnpj_basico_proponente, cpf_digitos_proponente.
-- ATENCAO: `receita.ano` NAO e coluna de normalizacao — e business col do CSV
-- e ESTA incluida no hash de receita.
--
-- Ver ADR-0014 e docs/etl-incremental-guide.md.


-- ============================================================================
-- 0. Pre-flight: a funcao de hash injetiva precisa existir (sql/35a)
-- ============================================================================
-- etl_admin.row_hash_md5() usa array_to_json (injective). NAO redefinimos aqui
-- para evitar drift entre trigger (rows novas) e populate (rows legacy).
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'etl_admin' AND p.proname = 'row_hash_md5'
    ) THEN
        RAISE EXCEPTION
            'etl_admin.row_hash_md5() ausente. Rode sql/35a_pb_extras_synthetic_nk_columns.sql '
            'antes (schema base; aplicado por etl_phase=sql ou ETL completo).';
    END IF;
END $$;


-- ============================================================================
-- 0c. Remover UNIQUE INDEX da NK natural (se existir) — ADR-0014
-- ============================================================================
-- A NK natural foi abandonada (despesa tem 1037 colisoes reais; servidor tem
-- 90k NULLs na NK). Um UNIQUE INDEX natural remanescente (de POCs antigos ou
-- sql/30/sql/31) QUEBRA o upsert synthetic: re-inserir uma row legacy viola o
-- index natural, e o ON CONFLICT (_nk_md5) NAO trata esse conflito ->
-- UniqueViolation aborta o bucket. (Detectado em teste local: o loader falhava
-- com "viola a restricao de unicidade ix_tce_pb_licitacao_nk".) Idempotente.
DROP INDEX IF EXISTS ix_tce_pb_despesa_nk;
DROP INDEX IF EXISTS ix_tce_pb_servidor_nk;
DROP INDEX IF EXISTS ix_tce_pb_licitacao_nk;
DROP INDEX IF EXISTS ix_tce_pb_receita_nk;


-- ============================================================================
-- 0b. Normalizadores de hash (REPLICAM o parser incremental) — ADR-0014
-- ============================================================================
-- O ETL classico (etl/19_tce_pb.py) e o framework incremental armazenam o
-- MESMO valor de CSV de formas diferentes. Para que rows legacy (populate) e
-- re-inseridas (trigger) gerem o MESMO _nk_md5, o hash normaliza cada coluna
-- da forma que o parser incremental normaliza. Aplicado nos DOIS caminhos.
--
-- TEXTO (replica etl/incremental/parser.py:_clean_for_tab + staging trim +
-- sentinelas):
--   \t -> espaco, \r removido, \n -> espaco; depois trim; e
--   '' / 00/00/0000 / 0000-00-00 / NULL  ->  '' (sentinelas viram vazio).
-- Sem caracteres especiais e o no-op de trim — nao muda o hash de dados ja
-- limpos (validado: prod tem 0 rows com \n/\t nas cols de texto).
CREATE OR REPLACE FUNCTION etl_admin.nk_norm_text(v text)
RETURNS text LANGUAGE sql IMMUTABLE AS $$
  SELECT coalesce(
    nullif(nullif(nullif(nullif(
      btrim(translate(replace(v, E'\r', ''), E'\t\n', '  ')),
    ''), '00/00/0000'), '0000-00-00'), 'NULL'),
  '')
$$;

-- NUMERO: o parser incremental nulifica o token cru '0' (parser.py:329
-- `IN ('', '0', 'NULL') -> NULL`), enquanto o ETL classico armazena '0' como
-- 0.00 (DECIMAL(15,2)). Sem normalizacao, a MESMA row hashearia '0.00' (legacy)
-- vs '' (incremental) e duplicaria (91k+ rows com valor_pago='0' so em
-- despesas-2026). coalesce(v,0.00) colapsa NULL e 0.00 para '0.00'; valores
-- nao-nulos ficam identicos ao ::text canonico do DECIMAL(15,2).
CREATE OR REPLACE FUNCTION etl_admin.nk_norm_num(v numeric)
RETURNS text LANGUAGE sql IMMUTABLE AS $$
  SELECT coalesce(v, 0.00)::text
$$;


-- ============================================================================
-- tce_pb_despesa
-- ============================================================================
ALTER TABLE tce_pb_despesa ADD COLUMN IF NOT EXISTS _nk_md5 TEXT;
COMMENT ON COLUMN tce_pb_despesa._nk_md5 IS
    'Hash md5 (injetivo) das 41 cols de negocio. Trigger BEFORE INSERT. '
    'UNIQUE INDEX garante idempotencia sem perder registros distintos que '
    'compartilham a NK natural (1037 grupos de colisao reais). Ver ADR-0014.';

-- Single source of truth do hash (trigger E populate chamam esta funcao).
CREATE OR REPLACE FUNCTION etl_admin.nk_md5_tce_pb_despesa_row(r tce_pb_despesa)
RETURNS text AS $func$
  SELECT etl_admin.row_hash_md5(
    etl_admin.nk_norm_text(r.municipio), etl_admin.nk_norm_text(r.codigo_ug),
    etl_admin.nk_norm_text(r.descricao_ug), etl_admin.nk_norm_text(r.numero_empenho),
    to_char(r.data_empenho, 'YYYY-MM-DD'), etl_admin.nk_norm_text(r.mes),
    etl_admin.nk_norm_text(r.cpf_cnpj), etl_admin.nk_norm_text(r.nome_credor),
    etl_admin.nk_norm_num(r.valor_empenhado), etl_admin.nk_norm_num(r.valor_liquidado),
    etl_admin.nk_norm_num(r.valor_pago), etl_admin.nk_norm_text(r.codigo_unidade_orcamentaria),
    etl_admin.nk_norm_text(r.descricao_unidade_orcamentaria), etl_admin.nk_norm_text(r.codigo_funcao),
    etl_admin.nk_norm_text(r.funcao), etl_admin.nk_norm_text(r.codigo_subfuncao),
    etl_admin.nk_norm_text(r.subfuncao), etl_admin.nk_norm_text(r.codigo_programa),
    etl_admin.nk_norm_text(r.programa), etl_admin.nk_norm_text(r.codigo_acao),
    etl_admin.nk_norm_text(r.acao), etl_admin.nk_norm_text(r.codigo_categoria_economica),
    etl_admin.nk_norm_text(r.categoria_economica), etl_admin.nk_norm_text(r.codigo_natureza),
    etl_admin.nk_norm_text(r.grupo_natureza_despesa), etl_admin.nk_norm_text(r.codigo_modalidade_aplicacao),
    etl_admin.nk_norm_text(r.modalidade_aplicacao), etl_admin.nk_norm_text(r.codigo_elemento_despesa),
    etl_admin.nk_norm_text(r.elemento_despesa), etl_admin.nk_norm_text(r.codigo_subelemento),
    etl_admin.nk_norm_text(r.codigo_subelemento_exibicao), etl_admin.nk_norm_text(r.numero_licitacao),
    etl_admin.nk_norm_text(r.modalidade_licitacao), etl_admin.nk_norm_text(r.numero_obra),
    etl_admin.nk_norm_text(r.historico), etl_admin.nk_norm_text(r.codigo_fonte_recurso),
    etl_admin.nk_norm_text(r.descricao_fonte_recurso), etl_admin.nk_norm_text(r.ano_fonte),
    etl_admin.nk_norm_text(r.co), etl_admin.nk_norm_text(r.descricao_co),
    coalesce(r.ano_arquivo::text, '')
  )
$func$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION etl_admin.compute_nk_md5_tce_pb_despesa()
RETURNS trigger AS $func$
BEGIN
  IF NEW._nk_md5 IS NULL THEN
    NEW._nk_md5 := etl_admin.nk_md5_tce_pb_despesa_row(NEW);
  END IF;
  RETURN NEW;
END
$func$ LANGUAGE plpgsql SET search_path = pg_catalog, public;

DROP TRIGGER IF EXISTS trg_compute_nk_md5 ON tce_pb_despesa;
CREATE TRIGGER trg_compute_nk_md5 BEFORE INSERT ON tce_pb_despesa
FOR EACH ROW EXECUTE FUNCTION etl_admin.compute_nk_md5_tce_pb_despesa();


-- ============================================================================
-- tce_pb_servidor
-- ============================================================================
ALTER TABLE tce_pb_servidor ADD COLUMN IF NOT EXISTS _nk_md5 TEXT;
COMMENT ON COLUMN tce_pb_servidor._nk_md5 IS
    'Hash md5 (injetivo) das 11 cols de negocio. Trigger BEFORE INSERT. '
    'NK natural inviavel: municipio/nome_servidor tem NULLs e UNIQUE trata '
    'NULL como distinto -> double-load. Ver ADR-0014.';

CREATE OR REPLACE FUNCTION etl_admin.nk_md5_tce_pb_servidor_row(r tce_pb_servidor)
RETURNS text AS $func$
  SELECT etl_admin.row_hash_md5(
    etl_admin.nk_norm_text(r.municipio), etl_admin.nk_norm_text(r.codigo_ug),
    etl_admin.nk_norm_text(r.descricao_ug), etl_admin.nk_norm_text(r.cpf_cnpj),
    etl_admin.nk_norm_text(r.nome_servidor), etl_admin.nk_norm_text(r.tipo_cargo),
    etl_admin.nk_norm_text(r.descricao_cargo), etl_admin.nk_norm_num(r.valor_vantagem),
    to_char(r.data_admissao, 'YYYY-MM-DD'), etl_admin.nk_norm_text(r.matricula),
    etl_admin.nk_norm_text(r.ano_mes)
  )
$func$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION etl_admin.compute_nk_md5_tce_pb_servidor()
RETURNS trigger AS $func$
BEGIN
  IF NEW._nk_md5 IS NULL THEN
    NEW._nk_md5 := etl_admin.nk_md5_tce_pb_servidor_row(NEW);
  END IF;
  RETURN NEW;
END
$func$ LANGUAGE plpgsql SET search_path = pg_catalog, public;

DROP TRIGGER IF EXISTS trg_compute_nk_md5 ON tce_pb_servidor;
CREATE TRIGGER trg_compute_nk_md5 BEFORE INSERT ON tce_pb_servidor
FOR EACH ROW EXECUTE FUNCTION etl_admin.compute_nk_md5_tce_pb_servidor();


-- ============================================================================
-- tce_pb_licitacao
-- ============================================================================
ALTER TABLE tce_pb_licitacao ADD COLUMN IF NOT EXISTS _nk_md5 TEXT;
COMMENT ON COLUMN tce_pb_licitacao._nk_md5 IS
    'Hash md5 (injetivo) das 13 cols de negocio. Trigger BEFORE INSERT. '
    'Synthetic NK por uniformidade com despesa/servidor. Ver ADR-0014.';

CREATE OR REPLACE FUNCTION etl_admin.nk_md5_tce_pb_licitacao_row(r tce_pb_licitacao)
RETURNS text AS $func$
  SELECT etl_admin.row_hash_md5(
    etl_admin.nk_norm_text(r.municipio), etl_admin.nk_norm_text(r.codigo_ug),
    etl_admin.nk_norm_text(r.descricao_ug), etl_admin.nk_norm_text(r.numero_licitacao),
    etl_admin.nk_norm_text(r.numero_protocolo_tce), coalesce(r.ano_licitacao::text, ''),
    etl_admin.nk_norm_text(r.modalidade), etl_admin.nk_norm_text(r.objeto_licitacao),
    to_char(r.data_homologacao, 'YYYY-MM-DD'), etl_admin.nk_norm_text(r.nome_proponente),
    etl_admin.nk_norm_text(r.cpf_cnpj_proponente), etl_admin.nk_norm_num(r.valor_ofertado),
    etl_admin.nk_norm_text(r.situacao_proposta)
  )
$func$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION etl_admin.compute_nk_md5_tce_pb_licitacao()
RETURNS trigger AS $func$
BEGIN
  IF NEW._nk_md5 IS NULL THEN
    NEW._nk_md5 := etl_admin.nk_md5_tce_pb_licitacao_row(NEW);
  END IF;
  RETURN NEW;
END
$func$ LANGUAGE plpgsql SET search_path = pg_catalog, public;

DROP TRIGGER IF EXISTS trg_compute_nk_md5 ON tce_pb_licitacao;
CREATE TRIGGER trg_compute_nk_md5 BEFORE INSERT ON tce_pb_licitacao
FOR EACH ROW EXECUTE FUNCTION etl_admin.compute_nk_md5_tce_pb_licitacao();


-- ============================================================================
-- tce_pb_receita
-- ============================================================================
ALTER TABLE tce_pb_receita ADD COLUMN IF NOT EXISTS _nk_md5 TEXT;
COMMENT ON COLUMN tce_pb_receita._nk_md5 IS
    'Hash md5 (injetivo) das 13 cols de negocio. Trigger BEFORE INSERT. '
    'Synthetic NK por uniformidade com despesa/servidor. Ver ADR-0014.';

CREATE OR REPLACE FUNCTION etl_admin.nk_md5_tce_pb_receita_row(r tce_pb_receita)
RETURNS text AS $func$
  SELECT etl_admin.row_hash_md5(
    etl_admin.nk_norm_text(r.municipio), etl_admin.nk_norm_text(r.codigo_ug),
    etl_admin.nk_norm_text(r.descricao_ug), etl_admin.nk_norm_text(r.mes_ano),
    coalesce(r.ano::text, ''), etl_admin.nk_norm_text(r.codigo_receita),
    etl_admin.nk_norm_text(r.descricao_receita), etl_admin.nk_norm_text(r.tipo_atualizacao_receita),
    etl_admin.nk_norm_num(r.valor), etl_admin.nk_norm_text(r.codigo_fonte_recurso),
    etl_admin.nk_norm_text(r.descricao_fonte_recurso), etl_admin.nk_norm_text(r.co),
    etl_admin.nk_norm_text(r.descricao_co)
  )
$func$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION etl_admin.compute_nk_md5_tce_pb_receita()
RETURNS trigger AS $func$
BEGIN
  IF NEW._nk_md5 IS NULL THEN
    NEW._nk_md5 := etl_admin.nk_md5_tce_pb_receita_row(NEW);
  END IF;
  RETURN NEW;
END
$func$ LANGUAGE plpgsql SET search_path = pg_catalog, public;

DROP TRIGGER IF EXISTS trg_compute_nk_md5 ON tce_pb_receita;
CREATE TRIGGER trg_compute_nk_md5 BEFORE INSERT ON tce_pb_receita
FOR EACH ROW EXECUTE FUNCTION etl_admin.compute_nk_md5_tce_pb_receita();


-- Populate de _nk_md5 nas rows legacy: feito via Python autocommit (batched +
-- partial index), reusando as funcoes nk_md5_<tabela>_row acima:
--   python -m etl.refresh_post_incremental --source tce_pb --populate-only
-- Em seguida, sql/42z faz dedupe + UNIQUE INDEX. Ver ADR-0014.
