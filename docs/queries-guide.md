# Queries guide — adicionando uma Q##

Este guia cobre o ciclo de vida de uma query nova no `govbr-cruza-dados`. Para contexto arquitetural, ver [architecture.md](architecture.md); para registrá-la na UI, ver [web-guide.md](web-guide.md).

## Panorama

- **125 queries ativas** em **17 arquivos** `queries/*.sql`, numeradas globalmente de `Q01` a `Q310` (com gaps históricos).
- Executor: [`etl/run_queries.py`](../etl/run_queries.py) com parser custom `split_sql_statements` que trata aspas simples/duplas (`''` escapado). **Dollar-quoting (`$$...$$`) ainda não é suportado** — issue P0 #9.
- Saída padrão: `resultados/Q##_<titulo>.csv` (uma por query).
- Registro na UI web em [`web/queries/registry.py`](../web/queries/registry.py).

## Ciclo de vida

```mermaid
flowchart TD
    A[Definir tema/objeto da investigação] --> B[Escolher Q## livre<br/>(grep -h '-- Q' queries/*.sql)]
    B --> C[Header obrigatório<br/>-- Q##: Titulo curto]
    C --> D[Escrever SQL<br/>placeholders %(municipio)s, etc.]
    D --> E[EXPLAIN ANALYZE local]
    E --> F{Custo > 30s?}
    F -- não --> G[python -m etl.run_queries --query Q##]
    F -- sim --> H[Adicionar índice em<br/>sql/19_indices_queries.sql]
    H --> I{Ainda lento?}
    I -- sim --> J[Pré-computar via MV<br/>em sql/12_views.sql]
    I -- não --> G
    J --> G
    G --> K{Query da UI?}
    K -- sim --> L[Registrar via _reg em<br/>web/queries/registry.py]
    K -- não --> M[Relatório markdown<br/>opcional em relatorios/]
    L --> M
    M --> N[PR]
```

## Header obrigatório

```sql
-- Q199: Servidores com vínculo CPF→CNPJ em fornecedor pago
WITH ...
```

O regex em `etl/run_queries.py:67` é literalmente `r"(-- Q(\d+): ([^\n]+)\n.*?)(?=-- Q\d+:|$)"`. Sem o header, a query não é detectada e nem o `run_queries.py` nem a UI a encontram.

## Numeração

A numeração é **global** — não reinicia por arquivo. Antes de escolher um número:

```bash
grep -h '^-- Q' queries/*.sql | sort -u
grep -E '"Q[0-9]+"' web/queries/registry.py
```

Gaps existem (queries deprecadas). Pode reaproveitar números livres ou pegar o próximo após o maior em uso.

## Performance

- **Timeout default:** `QueryDef.timeout_sec = 30` ([`web/queries/registry.py:15`](../web/queries/registry.py)). Aplicado como `SET statement_timeout = 30000` em `web/db.py:53`.
- **EXPLAIN ANALYZE obrigatório** antes do PR. Se a query consome MV nova, lembre que `21_views.py` deve ter rodado primeiro.
- **Se passar de 30s:**
  1. **Índice cirúrgico** em [`sql/19_indices_queries.sql`](../sql/19_indices_queries.sql) (separado do schema base em `11_indices.sql` para evitar conflitos durante ETL).
  2. **MV pré-computada** em [`sql/12_views.sql`](../sql/12_views.sql) — útil quando muitas Q## compartilham o mesmo agregado. Ver [mv-guide.md](mv-guide.md).
  3. **Override de timeout** em `_reg(..., timeout=60)` — última opção; só justificado quando a query é raramente acionada na UI. (Note: o argumento é `timeout`, não `timeout_sec` — ver [`web/queries/registry.py:98`](../web/queries/registry.py).)
- **Padrões medidos hoje:** 122/125 queries têm `ORDER BY`, 32/125 usam CTEs, 16/125 têm `LIMIT`. Sempre prefira `LIMIT` quando a UI renderiza só top-N.

## Identidade de fornecedor — caveat crítico

Use **`cpf_cnpj` completo (14 dígitos)**, **NÃO** `cnpj_basico` (8 dígitos):

```sql
-- ❌ ERRADO: cnpj_basico colide com CPFs cujos primeiros 8 dígitos coincidem
SELECT cnpj_basico, SUM(valor)
FROM tce_pb_despesa
GROUP BY cnpj_basico;

-- ✅ CORRETO: cpf_cnpj 14 dígitos + filtro de existência em estabelecimento
SELECT d.cpf_cnpj, SUM(d.valor)
FROM tce_pb_despesa d
WHERE EXISTS (
    SELECT 1 FROM estabelecimento e
    WHERE e.cpf_cnpj = d.cpf_cnpj
)
GROUP BY d.cpf_cnpj;
```

Sem o `EXISTS`, CPFs de pessoa física entram no resultado como se fossem empresas, inflando contagens e gerando falsos positivos em relatórios. Ver convenção em [CONTRIBUTING.md](../CONTRIBUTING.md) e nas instruções do repo.

## TCE-PB quirks

Cruzar `tce_pb_licitacao` com `tce_pb_despesa` exige cuidado:

| Campo | Em `licitacao` | Em `despesa` |
|---|---|---|
| `numero_licitacao` | `'00003/2025'` (com `/`) | `'000032025'` (sem separador) |
| `modalidade_licitacao` | sufixo `LIC` ou similar | sufixo distinto |

**Chave canônica de licitação** no mesmo município: a tripla `(codigo_ug, modalidade_licitacao, numero_licitacao)`. Sem `codigo_ug`, podem existir **7+ licitações distintas com mesmo `numero_licitacao` em um único município** — chave incompleta gera produto cartesiano.

```sql
-- ✅ chave canônica completa
JOIN tce_pb_licitacao l
  ON l.municipio       = d.municipio
 AND l.codigo_ug       = d.codigo_ug
 AND l.modalidade      = d.modalidade_licitacao
 AND REPLACE(l.numero_licitacao, '/', '') = d.numero_licitacao
```

## sql_full vs sql_full_dated

Variante datada aceita 6 placeholders opcionais — a UI passa só os que o filtro ativo definiu:

```sql
-- Q199 (sql_full)
WITH base AS (
  SELECT * FROM tce_pb_despesa
  WHERE municipio = %(municipio)s
)
SELECT ...

-- Q199 (sql_full_dated) — mesma query, com janela temporal
WITH base AS (
  SELECT * FROM tce_pb_despesa
  WHERE municipio = %(municipio)s
    AND data_empenho BETWEEN %(data_inicio)s AND %(data_fim)s
)
SELECT ...
```

Use o conjunto que fizer sentido:

- **Datas exatas:** `%(data_inicio)s`, `%(data_fim)s` (DATE).
- **Por ano:** `%(ano_inicio)s`, `%(ano_fim)s` (INT).
- **Por ano-mês:** `%(ano_mes_inicio)s`, `%(ano_mes_fim)s` (`'YYYY-MM'`).

## Registrando na UI

Há duas formas — prefira `_reg()` (padrão atual do código):

```python
# web/queries/registry.py
# Forma preferida — _reg() é wrapper conveniente
_reg(
    "Q199",                                              # qid
    "Servidores com vínculo CPF→CNPJ em fornecedor pago",  # title
    "Cruza CPF de servidor ativo com sócios de empresas pagas pela prefeitura.",  # desc
    "conflito-interesses",                               # cat
    SQL_Q199,                                            # sql_full
    timeout=30,                                          # default; raise só se justificado
    sql_dated=SQL_Q199_DATED,                            # opcional (variante temporal)
)

# Forma manual — QueryDef direto (raramente necessário)
CIDADE_QUERIES["Q199"] = QueryDef(
    id="Q199",
    title="Servidores com vínculo CPF→CNPJ em fornecedor pago",
    description="Cruza CPF de servidor ativo com sócios de empresas pagas pela prefeitura.",
    category="conflito-interesses",
    sql_count=SQL_Q199_COUNT,    # query de contagem (paginação)
    sql_full=SQL_Q199,
    sql_full_dated=SQL_Q199_DATED,  # opcional
    timeout_sec=30,
)
```

Assinaturas reais em [`web/queries/registry.py:7-18,98`](../web/queries/registry.py).

Categorias atualmente em uso:

- `fornecedores-irregulares`
- `conflito-interesses`
- `politico-eleitoral`
- `licitacao-concorrencia`
- `cruzamento-estado-municipio`
- `orcamento-financeiro`

Traduções leigas (Modo Cidadão) ficam em `_LAY_TEXT` no mesmo arquivo — opcionais.

## Exemplo concreto

```sql
-- Q199: Servidores com vínculo CPF→CNPJ em fornecedor pago
-- EXPLAIN ANALYZE local (joao-pessoa, 2024):
--   Aggregate (cost=1842..1843 rows=1)  actual time=2103 ms
--   → HashAgg em socio (cpf_socio_norm) usa idx_socio_cpf_norm
WITH fornecedores AS (
    SELECT DISTINCT d.cpf_cnpj
    FROM tce_pb_despesa d
    WHERE d.municipio = %(municipio)s
      AND EXISTS (SELECT 1 FROM estabelecimento e WHERE e.cpf_cnpj = d.cpf_cnpj)
)
SELECT s.nome_servidor, s.cpf_digitos, f.cpf_cnpj AS cnpj_fornecedor, soc.nome_socio
FROM fornecedores f
JOIN socio   soc ON soc.cnpj_basico = LEFT(f.cpf_cnpj, 8)
JOIN tce_pb_servidor s ON s.cpf_digitos = soc.cpf_socio_norm
WHERE s.municipio = %(municipio)s
  AND s.situacao = 'ATIVO'
ORDER BY s.nome_servidor;
```

Rodar isolada:

```bash
python -m etl.run_queries --query Q199
ls resultados/Q199_*.csv
```

## Relatório markdown (opcional)

Investigações narradas vão em `relatorios/relatorio_<tema>.md`. Convenções:

- **Mascarar CPFs:** `***.NNN.NNN-**` (apenas dígitos do meio expostos).
- **CNPJs completos:** sempre validados — devem existir em `empresa`/`estabelecimento`.
- **Auditoria automática** antes do PR:

```bash
python scripts/audit_report_identifiers.py --report relatorios/relatorio_meu_tema.md --strict
```

O script valida CNPJs contra o banco local; CPFs são best-effort (a maioria está mascarada nos dados-fonte).

## Relacionados

- [architecture.md](architecture.md) — overview e onde Q## se encaixam no pipeline.
- [mv-guide.md](mv-guide.md) — quando promover query lenta para MV.
- [cache.md](cache.md) — como o resultado é warmed em `web_cache` para a UI.
- [web-guide.md](web-guide.md) — registrar e renderizar a query na rota da cidade.
