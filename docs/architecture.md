# Arquitetura

Visão geral arquitetural do `govbr-cruza-dados` — pensada como ponto único de entrada para contributors externos entenderem como as peças se encaixam. Este documento é a **landing page**; cada componente tem doc dedicado que aprofunda. Para vocabulário do domínio público brasileiro (empenho, UG, CEIS, etc.), veja [`glossario.md`](glossario.md).

## TL;DR

O projeto faz ETL de ~350M registros de ~18 fontes públicas brasileiras para PostgreSQL 16, normaliza identidades por CPF/CNPJ, materializa scores de risco em camadas, e serve o resultado via FastAPI no portal público [transparenciapb.org](https://transparenciapb.org). Tudo orquestrado por GitHub Actions sobre um self-hosted runner em Azure VM.

```mermaid
flowchart LR
    SOURCES[18+ fontes<br/>públicas BR] --> ETL[ETL<br/>24 fases]
    ETL --> DB[(PostgreSQL 16<br/>~248GB)]
    DB --> MVS[(MVs<br/>L1 → L2 → views)]
    MVS --> CACHE[(web_cache<br/>pré-computado)]
    DB --> QUERIES[Queries Q##<br/>fraud detection]
    CACHE --> WEB[FastAPI<br/>transparenciapb.org]
    QUERIES --> REPORTS[40+ relatórios<br/>investigativos]

    classDef src fill:#e8f5e9,stroke:#2e7d32
    classDef store fill:#e3f2fd,stroke:#1565c0
    classDef compute fill:#fff3e0,stroke:#e65100
    class SOURCES src
    class DB,MVS,CACHE store
    class ETL,QUERIES,WEB compute
```

## Camadas

1. **Ingestão de dados brutos** — 18 fontes públicas baixadas como CSVs/JSONs em `$DATA_DIR`. Owner: `etl/00_download.py`.
2. **ETL clássico** — 24 fases (full reload, TRUNCATE+rebuild) carregando do raw para tabelas físicas. Owner: `etl/run_all.py`.
3. **ETL incremental** — framework dedicado em `etl/incremental/` para fontes append-only (TCE-PB, dados.pb hoje). Princípios não-negociáveis P1-P6. Owner: [`etl/incremental/README.md`](../etl/incremental/README.md).
4. **Schema** — DDL numerada em `sql/00_*.sql` a `sql/35d_*.sql`, executada pelo `etl.db.execute_sql_file`.
5. **Materialized Views em camadas** — `sql/12_views.sql`. L1 (independentes) → L2 (derivadas) → views planas. Detalhes em [`mv-guide.md`](mv-guide.md).
6. **Entity Resolution** — fase 17 (`etl/15_normalizar.py`) cria colunas `cpf_digitos` e `cpf_cnpj_norm` que permitem JOINs cross-source por igualdade direta.
7. **Queries Q##** — `queries/*.sql` com 125+ queries de fraude, numeradas globalmente Q01-Q310. Executadas por `etl/run_queries.py`. Detalhes em [`queries-guide.md`](queries-guide.md).
8. **Web frontend** — FastAPI + Jinja2 servindo cache pré-computado, com *shadow rewarm* zero-downtime. Detalhes em [`web-guide.md`](web-guide.md) e [`cache.md`](cache.md).
9. **Deploy** — workflow GitHub Actions com auto-resize de VM Azure. Detalhes em [`deploy.md`](deploy.md).
10. **Observabilidade** — Umami self-hosted + GoAccess + traffic-digest + pg-autotune. Detalhes em [`ops.md`](ops.md).

## Data flow ETL

```mermaid
flowchart TB
    subgraph SOURCES[18+ fontes públicas]
        direction LR
        S1[RFB CNPJ ~58GB]
        S2[PNCP ~30GB]
        S3[TCE-PB ~20GB]
        S4[dados.pb ~10GB]
        S5[TSE ~12GB]
        S6[PGFN ~11GB]
        S7[+ 12 outras]
    end

    SOURCES -->|HTTPS<br/>etl.00_download| RAW[(DATA_DIR<br/>CSV / JSON / ZIP)]

    subgraph CLASSIC[ETL clássico — 24 fases — full reload]
        direction TB
        P1[1. Schema base<br/>etl.01_schema]
        P2[2-14. Cargas<br/>RFB, PNCP, Emendas,<br/>CPGF, PGFN, BNDES]
        P3[15-18. Sanções,<br/>Viagens, TSE,<br/>Bolsa Família]
        P4[19-20. TCE-PB +<br/>dados.pb]
        P5[17. Normalização<br/>CPF/CNPJ]
        P6[18. MVs L1/L2/L3<br/>etl.21_views]
        P7[19. MV sitemap<br/>etl.22_mv_sitemap]

        P1 --> P2 --> P3 --> P4 --> P5 --> P6 --> P7
    end

    RAW --> CLASSIC

    subgraph INCREMENTAL[ETL incremental — append-only]
        direction TB
        I1[etl.incremental.runner]
        I2[Conditional GET<br/>HEAD probe + ETag]
        I3[staging RAW<br/>staging typed]
        I4[INSERT target<br/>ON CONFLICT DO NOTHING]
        I5[DLQ: rows rejeitadas]

        I1 --> I2 --> I3 --> I4
        I3 -.->|NK NULL| I5
    end

    SOURCES -.->|TCE-PB +<br/>dados.pb| INCREMENTAL

    CLASSIC --> DB[(PostgreSQL 16<br/>~248GB)]
    INCREMENTAL --> DB

    DB --> CONSUMERS[Queries Q## + web + relatórios]
```

ETL clássico e incremental coexistem para fontes diferentes — o incremental cobre TCE-PB e dados.pb (20 specs, ~40M rows); o clássico cobre todas as outras. Quando uma fonte clássica migra para incremental, ela sai da lista de `etl/run_all.py` e ganha `LoaderSpec` em `etl/incremental/specs/`.

## Entity Resolution (CPF/CNPJ)

CPFs aparecem mascarados em formatos diferentes por fonte. JOINs cross-source não funcionariam com `LIKE` / regex em 350M linhas. Solução: normalização na fase 17.

```mermaid
flowchart LR
    subgraph FONTES[CPF em 7 formatos diferentes]
        direction TB
        F1["Bolsa Família / SIAPE / CPGF<br/><code>***.456.789-**</code><br/>6 dígitos centrais"]
        F2["Sócio RFB<br/><code>***456789**</code><br/>sem pontuação"]
        F3["PGFN<br/><code>XXX456.789XX</code><br/>formato próprio"]
        F4["CEIS / CNEP<br/><code>12345678901</code><br/>completo (raro)"]
        F5["TCE-PB servidor<br/><code>***.456.789-**</code>"]
        F6["dados.pb pagamento<br/><code>00045678901</code><br/>completo!"]
        F7["dados.pb empenho PF<br/><code>***456***</code><br/>3 dígitos centrais"]
    end

    FONTES -->|Phase 17<br/>etl.15_normalizar| NORM[Funções utilitárias<br/><code>clean_cpf, clean_cnpj,<br/>extract_cpf_masked</code>]

    NORM --> COL1[("<b>cpf_digitos</b><br/>6 dígitos centrais<br/>indexed"]
    NORM --> COL2[("<b>cpf_cnpj_norm</b><br/>11 ou 14 dígitos<br/>indexed")]

    COL1 --> MATCH[JOIN por igualdade<br/>direta + nome normalizado]
    COL2 --> MATCH
```

**Caveat importante**: ao identificar fornecedores em queries, use **`cpf_cnpj` completo (14 dígitos)** — não `cnpj_basico` (8 dígitos), que sofre colisão com CPFs cujos primeiros 8 dígitos coincidem com algum CNPJ. Filtre com `EXISTS (SELECT 1 FROM estabelecimento WHERE cpf_cnpj = ...)` para excluir falsos positivos. Detalhes em [`queries-guide.md`](queries-guide.md).

## ERD principal

Visão simplificada das entidades centrais. Tabelas auxiliares (`dom_*`, `etl_*` audit, `pb_extras_*`) omitidas para clareza.

```mermaid
erDiagram
    empresa ||--o{ estabelecimento : "1 matriz : N filiais"
    empresa ||--o{ socio : "1 empresa : N sócios"
    empresa {
        text cnpj_basico PK
        text razao_social
        text porte
        text natureza_juridica
        numeric capital_social
    }
    estabelecimento {
        text cnpj_basico FK
        text cpf_cnpj
        text nome_fantasia
        int situacao_cadastral
        text municipio
        text uf
    }
    socio {
        text cnpj_basico FK
        text nome_socio
        text cpf_digitos
    }
    tce_pb_despesa }o--|| estabelecimento : "fornecedor via cpf_cnpj"
    tce_pb_despesa {
        text municipio
        text nome_municipio
        text cpf_cnpj
        text modalidade_licitacao
        text numero_licitacao
        date data_empenho
        numeric valor_empenhado
        numeric valor_pago
    }
    pb_pagamento }o--|| estabelecimento : "credor via cpf_cnpj_norm"
    pb_pagamento {
        text exercicio
        text ug
        text empenho
        text cpf_cnpj_norm
        date data_pagamento
        numeric valor
    }
    ceis_sancao }o--|| estabelecimento : "sancionado"
    ceis_sancao {
        text cpf_cnpj_sancionado
        date data_inicio_sancao
        date data_final_sancao
        text tipo_sancao
        text abrangencia
    }
    tce_pb_servidor }o--|| socio : "match por nome + cpf_digitos"
    tce_pb_servidor {
        text municipio
        text cpf_digitos
        text nome
        text cargo
        numeric salario
    }
    bolsa_familia }o--|| tce_pb_servidor : "match servidor → beneficiário"
    bolsa_familia {
        text municipio
        text cpf_digitos
        text nome
        numeric valor
        text competencia
    }
```

Relacionamentos não-mostrados por simplicidade:

- `pncp_*` (contratacao/contrato/item) → `estabelecimento` via `cpf_cnpj`
- `pb_empenho`, `pb_contrato`, `pb_liquidacao_*` → `pb_pagamento` por `(exercicio, ug, empenho)`
- `siape`, `cpgf`, `viagem` → `estabelecimento` / `socio` via `cpf_digitos` + nome
- `tse_*` (candidato, doador, patrimônio) → `socio` via `cpf_digitos` + nome
- `cnep_sancao`, `ceaf_expulsao`, `acordo_*` → similar a `ceis_sancao`

Para o catálogo completo de colunas das tabelas TCE-PB e dados.pb, veja [`dicionario_dados_pb.md`](dicionario_dados_pb.md).

## Materialized Views em camadas

```mermaid
flowchart TB
    subgraph L0[Tabelas físicas]
        T_TCE[tce_pb_*]
        T_PB[pb_*]
        T_EMP[empresa,<br/>estabelecimento,<br/>socio]
        T_BF[bolsa_familia,<br/>siape, cpgf]
        T_SAN[ceis_sancao,<br/>cnep_sancao,<br/>ceaf_expulsao]
    end

    subgraph L1[L1 - MVs independentes]
        L1A[mv_empresa_governo]
        L1B[mv_pessoa_pb]
        L1C[mv_municipio_pb_risco]
        L1D[mv_servidor_pb_base]
        L1E[mv_empresa_municipio_pagantes]
    end

    subgraph L2[L2 - MVs derivadas]
        L2A[mv_servidor_pb_risco]
        L2B[mv_empresa_pb]
        L2C[mv_rede_pb]
        L2D[mv_municipio_pb_kpi_score]
        L2E[mv_municipio_pb_mapa]
        L2F[mv_q67_dated_pb]
    end

    subgraph L3[L3 - Views planas]
        V1[v_risk_score_pb]
        V2[v_risk_score_empresa]
    end

    L0 --> L1
    L1A & L1B & L1C & L1D --> L2A
    L1A & L1C --> L2B
    L1A & L1B --> L2C
    L2A & L1C --> L2D
    L2D & L1C --> L2E
    L1C --> L2F

    L2A & L2B & L2C --> V1
    L2B --> V2
```

Convenções estritas em `sql/12_views.sql`:

1. **DROP no topo do arquivo, em ordem reversa** — views planas primeiro, L2 depois, L1 por último
2. **Criação por camada** — L1 → L2 → views planas, na sequência
3. **`REFRESH MATERIALIZED VIEW CONCURRENTLY`** exige UNIQUE INDEX na MV
4. **Notas de refresh** no rodapé do arquivo documentam ordem em produção

Detalhes operacionais em [`mv-guide.md`](mv-guide.md).

## Web cache e shadow rewarm

A tabela `web_cache` armazena resultados pré-computados de queries pesadas. FastAPI lê dela diretamente em request time. Três modos de atualização:

```mermaid
sequenceDiagram
    participant Op as Owner / Workflow
    participant Warm as warm_cache.py
    participant Cache as web_cache (live)
    participant Pending as web_cache (__pending)
    participant Web as FastAPI

    Note over Cache,Web: Estado: live serve todos os usuários

    Op->>Warm: rewarm_cache_keys=Q65
    Warm->>Pending: INSERT INTO Q65__pending<br/>(execução completa)

    par Live continua servindo
        Web->>Cache: SELECT Q65 (live)
        Cache-->>Web: rows existentes
    and Warm escreve em shadow
        Warm->>Pending: queries calmas, 12-18h
    end

    alt Todas as queries Q65 succeeded (fail==0)
        Warm->>Cache: SWAP ATÔMICO<br/>RENAME Q65__pending → Q65
        Note over Cache: Nova versão visível
    else Qualquer query Q65 falhou (fail>0)
        Warm->>Pending: ABORT — descarta __pending
        Note over Cache: Live mantido intacto
    end
```

**Outros modos**:

- **`drop_cache`** — TRUNCATE total. Causa 12-18h de cache miss em todas as queries. Só use em mudança de schema.
- **`invalidate_cache_keys`** — DELETE cirúrgico por prefixo de qid. Causa cache miss até warm rebuildar. Use só quando dados live estão *broken*.
- **`rewarm_cache_keys`** — shadow rewarm (acima). **Default recomendado**. Auto-expansão: `PERFIL` propaga para `KPI_SUMMARY` (mesmo prefixo).

Detalhes em [`cache.md`](cache.md). Documentação dos inputs do `deploy.yml` em [`deploy.md`](deploy.md).

## Deploy pipeline (resumo)

```mermaid
flowchart LR
    DISPATCH[workflow_dispatch<br/>com 14 inputs]
    DISPATCH --> PRE[Preflight<br/>github-hosted]
    PRE -->|"resize VM B2→B4 +<br/>disk Standard→Premium"| AZ[Azure ARM]
    PRE --> DEPLOY[Deploy<br/>self-hosted runner na VM]
    DEPLOY -->|"ETL / SQL / web / incremental /<br/>warm cache / IndexNow"| POST[Postflight<br/>github-hosted]
    POST -->|"resize VM B4→B2 +<br/>disk Premium→Standard"| AZ
```

3 jobs encadeados com `concurrency.group` único para evitar dois deploys simultâneos quebrarem o banco. Custo médio mensal ~$104 (web base + 1 ETL + 1 warm/mês), prorateado por hora. Detalhes em [`deploy.md`](deploy.md).

## Componentes operacionais (transparenciapb.org)

| Serviço | Systemd unit | Função |
|---|---|---|
| Frontend FastAPI | `cruza-web` | Uvicorn :8000 |
| Warm cache | `cruza-warm-cache` | Type=oneshot, dispara via workflow |
| Umami analytics | `cruza-umami` | `/_traffic/analytics/` (basic-auth + login) |
| GoAccess | `cruza-goaccess` | Dashboard `/_traffic/goaccess/` |
| Traffic tail | `cruza-traffic-tail` | últimas N linhas raw |
| Traffic digest | `cruza-traffic-digest.{service,timer}` | cron diário |
| PG auto-tune | `pg-autotune` | recalcula `shared_buffers` etc. por RAM da VM |

Detalhes operacionais (runbooks de rollback, restore, troubleshoot warm, fail2ban) em [`ops.md`](ops.md).

## SEO

Camada de descobribilidade tratada como produto, com sitemap-index shardado, ~550k URLs cobertas, IndexNow, OG image dinâmica. README contém a seção dedicada `## SEO` com os detalhes técnicos.

## Convenções não-negociáveis

Cada uma com fundo arquitetural — quebrá-las introduz regressões silenciosas. Documentadas em [`../CONTRIBUTING.md`](../CONTRIBUTING.md):

1. **PT-BR em todo o projeto** — identificadores, comentários, SQL, commits
2. **Sem pandas** — RAM budget 16GB sobre 350M rows. Streaming line-by-line + `COPY FROM STDIN` (helpers em `etl/db.py`). ADR-001.
3. **MVs em camadas L1→L2→views planas** — DROP reverso, REFRESH CONCURRENTLY. ADR-002.
4. **Shadow rewarm** como padrão de atualização de cache. ADR-003.
5. **Framework incremental dedicado** para fontes append-only, com role `etl_incremental` sem privilégios destrutivos. ADR-004.
6. **Header `-- Q##:` obrigatório** em `queries/*.sql` — sem ele o parser custom de `etl/run_queries.py` não detecta a query.
7. **`cpf_cnpj` (14 dígitos) para fornecedores**, não `cnpj_basico` (8) — colisão CPF/CNPJ.
8. **RFB usa latin-1**, outras fontes utf-8 — usar `latin1_lines` para RFB.

ADRs em [`adr/`](adr/) detalham o "porquê" de cada decisão arquitetural inegociável.

## Hardest-to-onboard files

Para contributor novo, os 5 arquivos com maior densidade conceitual:

| Arquivo | Linhas | Por que difícil |
|---|---|---|
| `sql/12_views.sql` | 1500+ | MVs em 3 camadas, DROP reverso no topo, dependências implícitas |
| `etl/run_all.py` | 800+ | 24 fases hardcoded, `_CSV_DIRS` vs `_SHARED_DIRS` cleanup automático |
| `web/routes/cidade.py` | 2100+ | SSR + APIs + cache + dialogs em um arquivo |
| `web/warm_cache.py` | 1700+ | Shadow rewarm, swap atômico, abort conditions, contextual rebuild |
| `etl/run_queries.py:split_sql_statements` | ~60 | Parser custom de SQL (quotes + dollar-quoting), processa 125+ Q## |

Os guias temáticos (`etl-guide.md`, `web-guide.md`, `mv-guide.md`, `queries-guide.md`, `cache.md`) destrincham cada um.

## Documentação adicional

| Doc | Para quem |
|---|---|
| [`../README.md`](../README.md) | Primeira leitura — quickstart + overview de features |
| [`../CONTRIBUTING.md`](../CONTRIBUTING.md) | Convenções + 3 caminhos de contribuição + setup local |
| [`glossario.md`](glossario.md) | Vocabulário do domínio (CEIS, empenho, UG, etc.) |
| [`onboarding.md`](onboarding.md) | Walk-through 15min clone → `uvicorn` |
| [`etl-guide.md`](etl-guide.md) | Adicionar fase ETL clássica |
| [`etl-incremental-guide.md`](etl-incremental-guide.md) | Adicionar spec incremental (P1-P6) |
| [`web-guide.md`](web-guide.md) | Adicionar query/rota/template/MD3 |
| [`queries-guide.md`](queries-guide.md) | Adicionar Q## (header, EXPLAIN, índice) |
| [`mv-guide.md`](mv-guide.md) | Adicionar MV (layered) |
| [`cache.md`](cache.md) | `web_cache` + shadow rewarm |
| [`deploy.md`](deploy.md) | 14 inputs `deploy.yml` + OIDC setup |
| [`ops.md`](ops.md) | Runbooks operacionais |
| [`privacidade.md`](privacidade.md) | Política LGPD pública |
| [`dicionario_dados_pb.md`](dicionario_dados_pb.md) | Catálogo de colunas TCE-PB e dados.pb |
| [`plano_novas_fontes.md`](plano_novas_fontes.md) | Roadmap de fontes (TSE histórico, etc.) |
| [`adr/`](adr/) | Decision records arquiteturais |
| [`../etl/incremental/README.md`](../etl/incremental/README.md) | Framework incremental detalhado |
| [`../DATA-LICENSE.md`](../DATA-LICENSE.md) | Licenciamento de dados + LGPD |
