# ADR-0009: Cleanup de entries órfãs em `web_cache` pós-MV refresh

## Status

Accepted

## Date

2026-05-17

## Context

Após o ETL normalize fix de [ADR-0007](0007-etl-normalize-fix.md) (PR #156),
empresas que existiam em `mv_empresa_pb` apenas por contaminação de CPFs
padded (ex: AVICOLA CHESTER MONGAGUA LTDA, CNPJ `00014020000111`, cujos
8 dígitos `00014020` colidiam com o prefixo de CPFs mascarados
`000.014.020-XX`) foram **removidas** da MV via `REFRESH MATERIALIZED
VIEW CONCURRENTLY`.

Mas o `web_cache` reteve as entries antigas dessas empresas órfãs:

- `EMPRESA_PERFIL` (1 row por CNPJ): ~43.853 entries órfãs
- `EMPRESA_PERFIL_MUN` (1 row por par `<cnpj14>:<slug-municipio>`): ~467.659
  entries órfãs

Total: ~511k rows de cache servindo agregados falsos.

O warm cycle de `web/warm_cache.py` é UPSERT-only e enumera **apenas
empresas qualificadas atuais** (de `mv_empresa_pb`). Empresas que
deixaram de qualificar nunca são tocadas pelo warm — suas entries no
cache permanecem stale indefinidamente.

**Sintoma visível**: páginas `/empresa/<cnpj>/<slug>` órfãs renderizavam
KPIs (R$ 100k, 112 empenhos, "atua em 3+ municípios") do cache stale,
mas a tabela de empenhos (live query no banco) retornava "Nenhum
empenho disponível". Inconsistência clara para o usuário.

### Alternativas consideradas

1. **Zerar agregados no payload (UPDATE JSONB)** — mantém entries no
   cache com `total_tce_pago=0`, `empenhos_total=0`, etc. Preserva
   cadastrais (estabelecimento, sócios, sanções, PGFN) e SEO.
   Vantagem: páginas indexadas pelo Google continuam servindo
   conteúdo "magro" mas válido. Desvantagem: 511k URLs vazias
   continuam consumindo crawl budget, polui qualidade percebida do
   site, e exige mapear ~25 campos do payload para zerar.

2. **Tabela durável `empresa_url_indexada`** — registra cada CNPJ
   emitido em sitemap/cache. Warm enumera UNION (qualifying ∪
   indexada). Sobrevive a `drop_cache`. Vantagem: cobertura ampla.
   Desvantagem: ~200 linhas de código novo + migração + tests; 3
   pontos de falha (warm enum, tabela, `compute_empty` flag);
   mantém 511k URLs vazias no índice.

3. **DELETE entries stale** — hard remove do cache. Sitemap regenera
   natural (só qualifying da MV). URLs órfãs acessadas via cache
   miss → **404 Not Found** (rota mudou de 503 para 404 junto com
   este ADR — ver "Decision" abaixo). Google de-indexa em ~7-30 dias.
   Vantagem: simplicidade, self-healing, qualidade do índice
   melhorada. Desvantagem: ~511k URLs indexadas viram 404 durante
   de-indexação.

4. **Adicionar `allow_empty=True` em `compute_empresa_perfil_dict`** —
   warm processaria empresas órfãs reescrevendo cache com payload
   zerado. Combina com (2) acima.

### Avaliação

URLs com dados falsos prejudicam mais o site do que URLs ausentes.
Manter páginas vazias indexadas confunde usuário ("essa empresa tem
CNPJ válido mas zero empenho? bug?") sem benefício SEO real — essas
são empresas fantasma de outros estados (AVICOLA SP, etc) sem
backlinks externos.

Tabela durável adiciona complexidade arquitetural permanente para um
problema pontual: contaminação por CPF padded foi um bug de longa
data corrigido em PR #156. Novas contaminações podem aparecer mas
serão raras (RFB sync não delista, ETL normalize agora aplica EXISTS
guard).

## Decision

Adotamos **alternativa 3** (DELETE entries stale) com função
**standalone** invocável independentemente do warm cycle, **acompanhada
de mudança no contrato de cache miss da rota `/empresa/<cnpj>` (e
`/empresa/<cnpj>/<slug>`)** de `503 Service Unavailable` para
`404 Not Found`.

### Rota: cache miss = 404 (era 503)

Antes deste ADR, `web/routes/empresa.py` retornava `503` com
`Retry-After: 3600` em cache miss. A intenção original era proteger o
DB em cold start (warm ainda não completou) e dizer ao crawler "volte
depois". Mas com:

- **Warm cycle pós-PR #156** que cobre todas as empresas qualificadas
  em `mv_empresa_pb`,
- **`cleanup_orphan_empresa_cache`** que remove entries de CNPJs não
  mais qualificados,
- **Sitemap gated** (só inclui CNPJs após warm),

um cache miss em `/empresa/<cnpj>` significa essencialmente uma das
três situações:

1. CNPJ inexistente / URL inventada;
2. CNPJ órfão (foi removido do cache pelo cleanup);
3. CNPJ recém-qualificado entre warms (caso raríssimo — crawler só
   descobre via sitemap, que só lista pós-warm).

Em todos os casos, **a URL não representa um recurso válido no
domínio PB**. `404 Not Found` é semanticamente correto e produz
melhor sinal SEO: Google de-indexa URLs 404 em ~7-30 dias, vs
semanas-meses pra 503 transient. Para as ~511k URLs órfãs que estão
sendo limpas, isso acelera materialmente a saída do índice.

Cold start (warm ainda rodando após restart) continua possível mas é
caso transitório e raro — o trade-off pra produção é favorável.

### Implementação do cleanup

`web/warm_cache.py` ganha função `cleanup_orphan_empresa_cache(dry_run,
batch_size, verbose)`:

```python
WITH stale AS (
    SELECT wc.ctid
    FROM web_cache wc
    WHERE wc.query_id = 'EMPRESA_PERFIL'
      AND NOT EXISTS (
          SELECT 1 FROM mv_empresa_pb m
          WHERE m.cnpj_basico = substring(wc.municipio, 1, 8)
      )
    LIMIT 5000
)
DELETE FROM web_cache wc
USING stale s
WHERE wc.ctid = s.ctid;
-- Repete em loop ate rowcount=0; mesmo para EMPRESA_PERFIL_MUN.
```

Por que **batches via `ctid`**:

- `LIMIT` direto em `DELETE` não é suportado pelo Postgres.
- Batches evitam segurar lock longo em `web_cache` (read-heavy pelo
  `cruza-web` servindo páginas).
- Permite log de progresso entre batches.

Por que **`substring(municipio, 1, 8)`** funciona para ambos qids:

- `EMPRESA_PERFIL`: `municipio = cnpj_completo` (14 dígitos). Primeiros
  8 = `cnpj_basico`.
- `EMPRESA_PERFIL_MUN`: `municipio = '<cnpj14>:<slug>'`. Primeiros 8
  = `cnpj_basico` (pois `cnpj14` tem 14 dígitos, slug vem após `:`).

CLI:

```bash
python -m web.warm_cache --cleanup-orphan-empresa            # delete
python -m web.warm_cache --cleanup-orphan-empresa --dry-run  # count only
```

### Deploy workflow

Novo input em `.github/workflows/deploy.yml`:

```yaml
cleanup_orphan_empresa_cache:
  description: 'Roda DELETE em web_cache (EMPRESA_PERFIL + EMPRESA_PERFIL_MUN)
    para entries cujo cnpj_basico nao existe mais em mv_empresa_pb. ...'
  required: false
  type: boolean
  default: false
```

Step novo "Cleanup orphan empresa cache" entre `MV refresh concurrently`
e `Deploy web frontend and cache warmer`. **Não dispara warm cycle**
(standalone) — diferentemente de `rewarm_cache_keys` que roda 3+ horas
de warm.

Sequência típica pós-ETL normalize fix:

```bash
# 1. ETL fix (idempotente)
gh workflow run deploy.yml -f etl_phase=web -f run_normalize_fix=true

# 2. Propagar fix nas MVs L1
gh workflow run deploy.yml -f etl_phase=web \
  -f refresh_mvs=mv_empresa_pb,mv_pessoa_pb,mv_municipio_pb_risco,mv_empresa_governo

# 3. Propagar fix nas MVs L2
gh workflow run deploy.yml -f etl_phase=web \
  -f refresh_mvs=mv_servidor_pb_risco,mv_municipio_pb_kpi_score,mv_municipio_pb_mapa,mv_q67_dated_pb

# 4. CLEANUP cache stale (este ADR) — leve, ~1-5 min
gh workflow run deploy.yml -f etl_phase=web -f cleanup_orphan_empresa_cache=true

# 5. (Opcional) Rewarm cache atualizado pra qualifying remanescentes
gh workflow run deploy.yml -f etl_phase=web \
  -f rewarm_cache_keys=EMPRESA_PERFIL,EMPRESA_PERFIL_MUN,PERFIL,KPI_SUMMARY
```

## Consequences

### Positive

- **Simplicidade arquitetural**: ~30 linhas de código + step no
  deploy. Sem tabela nova, sem flag no compute.
- **Self-healing futuro**: se nova contaminação aparecer (improvável
  pós ADR-0007), basta rerodar `cleanup_orphan_empresa_cache=true`.
  Idempotente.
- **Standalone**: roda em ~1-5 min sem disparar warm de ~3 horas. VM
  permanece em B2 (não dispara auto-resize do preflight).
- **Sitemap regenera natural**: usa `_get_qualifying_empresas` da
  `mv_empresa_pb`. Sem URLs órfãs no sitemap novo.
- **Qualidade do índice melhora**: 511k URLs servindo dados falsos
  saem do Google em ~7-30 dias (vs semanas-meses se rota fosse 503).
- **Semântica HTTP correta**: 404 reflete "URL não existe" para
  CNPJs fora de `mv_empresa_pb`.

### Negative / Trade-offs

- **511k URLs indexadas viram 404 transient**: Google ainda demora
  ~7-30 dias para de-indexar. Período de transição com URLs "Not
  Found" no índice. Mitigação: dados serviam contaminação, perda
  real é zero.
- **Sem rastro histórico de URLs órfãs**: se um dia precisarmos saber
  "quais empresas foram cacheadas antes do fix", a info é perdida.
  Mitigação: git tem o código antigo; Google Search Console mantém
  histórico de URLs descobertas.
- **Cold start mostra 404 em vez de 503**: usuário/crawler acessando
  durante warm ainda rodando vê 404 (era 503 transient). Mitigação:
  cold start é raro (deploys ~mensais), e o caso "novo CNPJ qualificado
  ainda não cacheado" só é descoberto via sitemap (que só lista pós-
  warm).
- **Drop_cache risk**: se `drop_cache=true` rodar, **todas** as URLs
  retornam 404 até o warm reconstruir o cache. Antes era 503 (less
  drastic). Mitigação: `drop_cache=true` é operação rara/manual com
  janela controlada.

### Mitigations

- **Idempotente**: re-run não corrompe.
- **DELETE em batches**: lock curto, permite cancelar limpo.
- **`--dry-run` flag**: conta sem deletar antes de comitar.
- **Pre-flight**: função verifica `to_regclass` de `web_cache` e
  `mv_empresa_pb` antes de tentar DELETE.

## Related

- Code:
  - [`web/warm_cache.py::cleanup_orphan_empresa_cache`](../../web/warm_cache.py)
  - [`web/routes/empresa.py`](../../web/routes/empresa.py) — `empresa_perfil` + `empresa_perfil_municipio` (cache miss = 404).
- Workflow:
  - [`.github/workflows/deploy.yml`](../../.github/workflows/deploy.yml)
    (input `cleanup_orphan_empresa_cache`).
- Other ADRs:
  - [ADR-0007](0007-etl-normalize-fix.md) — ETL normalize fix que
    introduziu a inconsistência cache vs MV.
  - [ADR-0003](0003-shadow-rewarm.md) — shadow rewarm (warm cycle
    completo, alternativa pesada).
- Docs:
  - [`docs/cache.md`](../cache.md) seção "Cleanup de entries órfãs".
- PRs:
  - [#156](https://github.com/lucasdiniz/govbr-cruza-dados/pull/156) —
    ETL normalize fix que motivou este ADR.
