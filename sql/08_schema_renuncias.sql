-- Tabelas de Renúncias Fiscais
-- Fonte: 20XX_RenunciasFiscais.csv, 20XX_EmpresasHabilitadas.csv,
--        20XX_EmpresasImunesOuIsentas.csv, 20XX_RenunciasFiscaisPorBeneficiario.csv

DROP TABLE IF EXISTS renuncia_fiscal CASCADE;
DROP TABLE IF EXISTS empresa_habilitada CASCADE;
DROP TABLE IF EXISTS empresa_imune CASCADE;
DROP TABLE IF EXISTS renuncia_beneficiario CASCADE;

CREATE TABLE renuncia_fiscal (
    id               SERIAL PRIMARY KEY,
    ano_calendario   SMALLINT,
    cnpj             VARCHAR(14),
    razao_social     VARCHAR(200),
    nome_fantasia    VARCHAR(200),
    cnae_codigo      VARCHAR(10),
    cnae_descricao   VARCHAR(200),
    municipio        VARCHAR(100),
    uf               CHAR(2),
    tipo_renuncia    VARCHAR(100),
    beneficio_fiscal VARCHAR(200),
    fundamento_legal TEXT,
    descricao        TEXT,
    tributo          VARCHAR(100),
    forma_tributacao VARCHAR(100),
    valor_renuncia   DECIMAL(15,2)
);

CREATE TABLE empresa_habilitada (
    id               SERIAL PRIMARY KEY,
    cnpj             VARCHAR(14),
    razao_social     VARCHAR(200),
    nome_fantasia    VARCHAR(200),
    cnae_codigo      VARCHAR(10),
    cnae_descricao   VARCHAR(200),
    municipio        VARCHAR(100),
    uf               CHAR(2),
    beneficio_fiscal VARCHAR(200),
    base_legal       TEXT,
    descricao        TEXT,
    dt_inicio        DATE,
    dt_fim           DATE
);

CREATE TABLE empresa_imune (
    id               SERIAL PRIMARY KEY,
    ano_calendario   SMALLINT,
    cnpj             VARCHAR(14),
    razao_social     VARCHAR(200),
    nome_fantasia    VARCHAR(200),
    cnae_codigo      VARCHAR(10),
    cnae_descricao   VARCHAR(200),
    municipio        VARCHAR(100),
    uf               CHAR(2),
    tipo_entidade    VARCHAR(100),
    beneficio_fiscal VARCHAR(200)
);

CREATE TABLE renuncia_beneficiario (
    id             SERIAL PRIMARY KEY,
    ano_calendario SMALLINT,
    cnpj           VARCHAR(14),
    razao_social   VARCHAR(200),
    nome_fantasia  VARCHAR(200),
    cnae_codigo    VARCHAR(10),
    cnae_descricao VARCHAR(200),
    municipio      VARCHAR(100),
    uf             CHAR(2),
    valor_renuncia DECIMAL(15,2)
);
