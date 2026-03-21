# Plano: Novas Fontes de Dados (Iteracao 2)

## 1. TSE - Candidatos e Financiamento Eleitoral

### Dados
- **Candidatos**: cadastro com CPF, partido, cargo, situacao, patrimonio
- **Bens declarados**: tipo de bem, descricao, valor declarado
- **Prestacao de contas**: receitas (doacoes) e despesas de campanha

### Schema

```sql
CREATE TABLE tse_candidato (
    id                  SERIAL PRIMARY KEY,
    ano_eleicao         SMALLINT,
    sg_uf               TEXT,
    cd_municipio        TEXT,
    nm_municipio        TEXT,
    cd_cargo            TEXT,
    ds_cargo            TEXT,
    sq_candidato        TEXT,       -- chave unica no TSE
    nr_candidato        TEXT,
    nm_candidato        TEXT,
    nm_urna_candidato   TEXT,
    nm_social_candidato TEXT,
    cpf                 TEXT,       -- CPF completo!
    dt_nascimento       DATE,
    nr_titulo_eleitoral TEXT,
    cd_genero           TEXT,
    ds_genero           TEXT,
    cd_grau_instrucao   TEXT,
    ds_grau_instrucao   TEXT,
    cd_estado_civil     TEXT,
    ds_estado_civil     TEXT,
    cd_cor_raca         TEXT,
    ds_cor_raca         TEXT,
    cd_ocupacao         TEXT,
    ds_ocupacao         TEXT,
    nr_partido          TEXT,
    sg_partido          TEXT,
    nm_partido          TEXT,
    cd_sit_tot_turno    TEXT,
    ds_sit_tot_turno    TEXT,       -- ELEITO, NAO ELEITO, etc
    nr_cnpj_campanha    TEXT       -- CNPJ da campanha
);

CREATE TABLE tse_bem_candidato (
    id                  SERIAL PRIMARY KEY,
    ano_eleicao         SMALLINT,
    sq_candidato        TEXT,
    cd_tipo_bem         TEXT,
    ds_tipo_bem         TEXT,
    ds_bem              TEXT,       -- descricao do bem
    valor_bem           NUMERIC    -- valor declarado
);

CREATE TABLE tse_receita_candidato (
    id                  SERIAL PRIMARY KEY,
    ano_eleicao         SMALLINT,
    sq_candidato        TEXT,
    sg_uf               TEXT,
    cpf_cnpj_doador     TEXT,      -- CPF ou CNPJ completo!
    nm_doador           TEXT,
    nm_doador_rfb       TEXT,
    cd_cnae_doador      TEXT,
    ds_cnae_doador      TEXT,
    sg_uf_doador        TEXT,
    dt_receita          DATE,
    ds_receita          TEXT,
    vr_receita          NUMERIC
);

CREATE TABLE tse_despesa_candidato (
    id                  SERIAL PRIMARY KEY,
    ano_eleicao         SMALLINT,
    sq_candidato        TEXT,
    sg_uf               TEXT,
    cpf_cnpj_fornecedor TEXT,      -- CPF ou CNPJ completo!
    nm_fornecedor       TEXT,
    nm_fornecedor_rfb   TEXT,
    cd_cnae_fornecedor  TEXT,
    dt_despesa          DATE,
    ds_despesa          TEXT,
    vr_despesa          NUMERIC
);
```

### Relacionamentos
- `tse_candidato.cpf` -> JOIN com `socio.cpf_cnpj_socio` (6 digitos centrais)
- `tse_candidato.cpf` -> JOIN com `siape_cadastro.cpf` (servidor que e candidato)
- `tse_candidato.nr_cnpj_campanha` -> JOIN com `empresa.cnpj_basico`
- `tse_receita_candidato.cpf_cnpj_doador` -> JOIN com `empresa.cnpj_basico` / `pncp_contrato.ni_fornecedor`
- `tse_despesa_candidato.cpf_cnpj_fornecedor` -> JOIN com `empresa.cnpj_basico`
- `tse_bem_candidato.sq_candidato` -> JOIN com `tse_candidato.sq_candidato`

### Queries de fraude

**Q33: Doador de campanha que ganha contrato publico apos eleicao**
```sql
SELECT tc.nm_candidato, tc.sg_partido, tc.ds_cargo,
       tr.nm_doador, tr.cpf_cnpj_doador, tr.vr_receita,
       pc.objeto, pc.valor_global, pc.dt_assinatura
FROM tse_receita_candidato tr
JOIN tse_candidato tc ON tc.sq_candidato = tr.sq_candidato AND tc.ano_eleicao = tr.ano_eleicao
JOIN pncp_contrato pc ON pc.ni_fornecedor = tr.cpf_cnpj_doador
WHERE tc.ds_sit_tot_turno ILIKE '%ELEITO%'
  AND pc.dt_assinatura > make_date(tr.ano_eleicao, 1, 1)
  AND tr.vr_receita > 10000
ORDER BY tr.vr_receita DESC;
```

**Q34: Candidato eleito cuja empresa recebe contratos**
```sql
SELECT tc.nm_candidato, tc.cpf, tc.sg_partido, tc.ds_cargo,
       s.cnpj_basico, e.razao_social,
       pc.objeto, pc.valor_global
FROM tse_candidato tc
JOIN socio s ON SUBSTRING(tc.cpf, 4, 6) = SUBSTRING(s.cpf_cnpj_socio, 4, 6)
  AND s.tipo_socio = 2
JOIN empresa e ON e.cnpj_basico = s.cnpj_basico
JOIN pncp_contrato pc ON LEFT(pc.ni_fornecedor, 8) = s.cnpj_basico
WHERE tc.ds_sit_tot_turno ILIKE '%ELEITO%'
ORDER BY pc.valor_global DESC;
```

**Q35: Patrimonio declarado vs. contratos recebidos**
```sql
SELECT tc.nm_candidato, tc.sg_partido, tc.ds_cargo, tc.ano_eleicao,
       SUM(tb.valor_bem) AS patrimonio_declarado,
       contratos.total_contratos
FROM tse_candidato tc
JOIN tse_bem_candidato tb ON tb.sq_candidato = tc.sq_candidato AND tb.ano_eleicao = tc.ano_eleicao
JOIN socio s ON SUBSTRING(tc.cpf, 4, 6) = SUBSTRING(s.cpf_cnpj_socio, 4, 6)
JOIN (
    SELECT LEFT(ni_fornecedor, 8) AS cnpj8, SUM(valor_global) AS total_contratos
    FROM pncp_contrato GROUP BY 1
) contratos ON contratos.cnpj8 = s.cnpj_basico
GROUP BY tc.nm_candidato, tc.sg_partido, tc.ds_cargo, tc.ano_eleicao, contratos.total_contratos
HAVING contratos.total_contratos > 10 * SUM(tb.valor_bem)
ORDER BY contratos.total_contratos DESC;
```

---

## 2. Pessoas Expostas Politicamente (PEP)

### Dados
Lista de agentes publicos em cargos relevantes nos ultimos 5 anos.

### Schema
```sql
CREATE TABLE pep (
    id                  SERIAL PRIMARY KEY,
    cpf                 TEXT,
    nome                TEXT,
    sigla_funcao        TEXT,
    descricao_funcao    TEXT,
    nivel_funcao        TEXT,
    nome_orgao          TEXT,
    dt_inicio           DATE,
    dt_fim              DATE,
    dt_carencia         DATE       -- ate quando e considerado PEP
);
```

### Queries de fraude

**Q36: PEP que e socio de empresa fornecedora**
```sql
SELECT p.nome, p.cpf, p.descricao_funcao, p.nome_orgao,
       s.cnpj_basico, e.razao_social,
       pc.valor_global, pc.objeto
FROM pep p
JOIN socio s ON SUBSTRING(REGEXP_REPLACE(p.cpf,'[^0-9]','','g'), 4, 6)
              = SUBSTRING(s.cpf_cnpj_norm, 1, 6)
JOIN empresa e ON e.cnpj_basico = s.cnpj_basico
JOIN pncp_contrato pc ON pc.cnpj_basico_fornecedor = s.cnpj_basico
WHERE s.tipo_socio = 2
ORDER BY pc.valor_global DESC;
```

---

## 3. Bolsa Familia / Novo Bolsa Familia

### Dados
Pagamentos mensais a beneficiarios (CPF, valor, municipio).

### Schema
```sql
CREATE TABLE bolsa_familia (
    id                  SERIAL PRIMARY KEY,
    ano_mes             TEXT,
    uf                  TEXT,
    cd_municipio        TEXT,
    nm_municipio        TEXT,
    cpf_beneficiario    TEXT,
    nis_beneficiario    TEXT,
    nm_beneficiario     TEXT,
    valor_parcela       NUMERIC
);
```

### Queries de fraude

**Q37: Servidor federal que recebe Bolsa Familia**
```sql
SELECT sc.nome, sc.cpf, sc.descricao_cargo, sc.org_exercicio,
       sr.remuneracao_apos_deducoes,
       bf.nm_beneficiario, bf.valor_parcela
FROM siape_cadastro sc
JOIN siape_remuneracao sr ON sr.id_servidor_portal = sc.id_servidor_portal
JOIN bolsa_familia bf ON SUBSTRING(REGEXP_REPLACE(sc.cpf,'[^0-9]','','g'), 1, 6)
                        = SUBSTRING(REGEXP_REPLACE(bf.cpf_beneficiario,'[^0-9]','','g'), 4, 6)
WHERE sr.remuneracao_apos_deducoes > 3000  -- ganha mais que o limite do BF
ORDER BY sr.remuneracao_apos_deducoes DESC;
```

**Q38: Socio de empresa fornecedora que recebe Bolsa Familia**
```sql
SELECT bf.nm_beneficiario, bf.cpf_beneficiario, bf.valor_parcela,
       s.cnpj_basico, e.razao_social, e.capital_social
FROM bolsa_familia bf
JOIN socio s ON SUBSTRING(REGEXP_REPLACE(bf.cpf_beneficiario,'[^0-9]','','g'), 4, 6)
              = SUBSTRING(s.cpf_cnpj_norm, 1, 6)
  AND s.tipo_socio = 2
JOIN empresa e ON e.cnpj_basico = s.cnpj_basico
WHERE e.capital_social > 100000
ORDER BY e.capital_social DESC;
```

---

## Indices para novas tabelas

```sql
-- TSE
CREATE INDEX idx_tse_cand_cpf ON tse_candidato(cpf);
CREATE INDEX idx_tse_cand_partido ON tse_candidato(sg_partido);
CREATE INDEX idx_tse_cand_cargo ON tse_candidato(cd_cargo);
CREATE INDEX idx_tse_cand_cnpj ON tse_candidato(nr_cnpj_campanha);
CREATE INDEX idx_tse_cand_sq ON tse_candidato(sq_candidato, ano_eleicao);
CREATE INDEX idx_tse_bem_sq ON tse_bem_candidato(sq_candidato, ano_eleicao);
CREATE INDEX idx_tse_receita_doador ON tse_receita_candidato(cpf_cnpj_doador);
CREATE INDEX idx_tse_receita_sq ON tse_receita_candidato(sq_candidato);
CREATE INDEX idx_tse_despesa_forn ON tse_despesa_candidato(cpf_cnpj_fornecedor);

-- PEP
CREATE INDEX idx_pep_cpf ON pep(cpf);
CREATE INDEX idx_pep_nome ON pep USING gin(nome gin_trgm_ops);

-- Bolsa Familia
CREATE INDEX idx_bf_cpf ON bolsa_familia(cpf_beneficiario);
CREATE INDEX idx_bf_municipio ON bolsa_familia(cd_municipio);
```

## Prioridade de implementacao

1. **TSE Candidatos + Bens** — CPF completo permite match exato (mais valioso)
2. **PEP** — lista pequena, carga rapida, alto impacto
3. **TSE Prestacao de Contas** — 1.2GB, mais complexo mas muito valioso
4. **Bolsa Familia** — volume enorme, usar amostra primeiro
