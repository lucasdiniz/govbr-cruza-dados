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
`410 Gone` (atualizada de `404 Not Found` em revisão 2026-05-18,
ver seção "Revisão 2026-05-18" abaixo).

### Rota: cache miss = 410 Gone (era 503 → depois 404 → revisado para 410)

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
domínio PB**. Inicialmente adotamos `404 Not Found`. Após observação
em produção (ver "Revisão 2026-05-18"), migramos para `410 Gone`
para acelerar de-indexação.

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
  - [`web/routes/empresa.py`](../../web/routes/empresa.py) — `empresa_perfil` + `empresa_perfil_municipio` (cache miss = 410 Gone, atualizado de 404 em 2026-05-18).
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

---

## Revisão 2026-05-18: cache miss = 410 Gone (era 404)

### Observação em produção

Após o ADR original (2026-05-17), análise de tráfego em 18/May/2026
mostrou Googlebot **persistindo em ~6.7k re-crawls/dia** em URLs órfãs
retornando 404. O comportamento esperado era de-indexação em 7-30
dias, mas Google estava interpretando 404 como "recurso temporariamente
ausente, vale a pena retentar" — mantendo crawl budget alocado em URLs
que nunca mais existirão.

Distribuição de status no dia 18/May/2026 (00:00-18:21 BR):

| Status | Hits | % do total |
|---|---:|---:|
| 200 | 51,348 | 59.2% |
| **404** | **33,743** | **38.9%** |
| 301 | 1,206 | 1.4% |

`66.249.74.38` (Googlebot principal) sozinho gerou 6,726 × 404 — quase
todos em URLs `/empresa/<CNPJ>/<municipio>` órfãs. O mesmo padrão se
repetiu em 17/May (~6.7k) — ou seja, o ritmo de retry não diminuiu
após 24h+.

### Mudança

Substituímos `status_code=404` por `status_code=410` nos dois cache
miss handlers (`empresa_perfil` e `empresa_perfil_municipio`).

**Por que 410 é estritamente melhor para este caso**:

1. **Semântica HTTP precisa**: 410 Gone significa "removido
   permanentemente, não tente novamente". Google documenta que trata
   410 como permanente e remove do índice em dias (vs semanas para 404).
2. **Crawl budget preservado**: Googlebot para de retentar URLs 410,
   liberando budget para crawlar páginas novas qualificadas.
3. **Zero complexidade adicionada**: a mudança é literal de
   `status_code=404` para `status_code=410`. O template `errors/404.html`
   é reutilizado (status code é o que importa pra crawler, conteúdo é
   genérico).
4. **Nenhuma nova query**: avaliamos cachear um existence check em
   `empresa` (RFB) para distinguir "CNPJ nunca existiu" de "CNPJ órfão",
   mas isso adiciona complexidade (LRU cache, day-bucket TTL, thundering
   herd protection) sem benefício prático — 99%+ dos cache misses em
   produção são caso (b) "CNPJ órfão", justificando 410 universal.

### Trade-offs aceitos

| Caso | Status correto ideal | Status produzido | Impacto |
|---|---|---|---|
| (a) URL inventada `/empresa/99999999999999/x` | 404 | 410 | Mínimo — Google de-indexa essa URL "inventada" mais rápido (não é problema; era irrelevante de qualquer forma) |
| (b) CNPJ órfão (PR #156 cleanup) | **410** | 410 ✅ | Resolve o problema raiz |
| (c) Cold start / CNPJ novo entre warms | 503 / 404 transient | 410 transient | Pior caso teórico. Mitigação: warm cycle dura ~3h após deploy mensal; janela de exposição é curta. Crawler descobre URL nova via sitemap (que só lista pós-warm), tornando race improvável |

### Por que não query+cache pra distinguir (a) de (b)/(c)

Considerei (e descartei) cachear `SELECT 1 FROM empresa WHERE
cnpj_basico = $1` com `lru_cache + day_bucket` para retornar 410
apenas quando CNPJ existe na RFB (caso b) e 404 quando não (caso a).

Razões contra:

- **Complexidade não justificada**: ~30 linhas de código + LRU cache
  + day bucket + risco de thundering herd em cold deploy. Para
  distinguir um caso raro (URL inventada) de um caso dominante
  (URL órfã do cleanup), sem ganho prático.
- **Não há cliente para essa distinção**: humanos digitando URLs
  inventadas são <1% do tráfego em rotas `/empresa/<CNPJ>/<slug>`.
  Para esses, ver "Página gone" no lugar de "Página não encontrada"
  não muda nada (template é o mesmo).
- **Yagni**: se um dia precisarmos distinguir, adicionamos. Por
  enquanto, 410 universal é simples e correto para >99% dos casos.

### Consequences (adicionais ao decision original)

#### Positive

- **Crawl budget liberado**: 6.7k retries/dia esperados parar em
  ~3-7 dias após Google internalizar 410.
- **De-index acelerado**: ~511k URLs órfãs saem do Google em dias
  (vs semanas com 404).
- **Sinal mais limpo no Search Console**: URLs com 410 aparecem em
  relatório "Removed" (intencional) em vez de "Not found" (warning).

#### Negative

- **Reversão demora mais**: se uma empresa órfã voltar a qualificar
  (improvável), Google leva mais tempo pra re-indexar URL marcada
  como 410 vs 404. Mitigação: cleanup é idempotente; quando empresa
  re-qualifica, warm cycle popula cache e próximo crawl retorna 200.
  Google reverte 410→200 quando recebe 200 em re-crawl.
- **URLs digitadas inventadas (caso a) recebem 410**: semanticamente
  impreciso ("removido" vs "nunca existiu"), mas inconsequente —
  esses são <1% dos misses e usuário vê mesmo template.

### Reverso da mudança (se necessário)

Se por algum motivo precisarmos voltar para 404 (ex: Google muda
comportamento de tratamento de 410), basta inverter `status_code=410`
para `status_code=404` nos dois handlers. Sem mudança de template,
schema, ou dependências.

---

## Revisão 2026-05-19: DB error distinto de cache miss (503 vs 410)

### Observação em review paralelo do PR #181

Review paralelo Opus 4.7-high + GPT-5.5 do PR #181 (revisão 2026-05-18)
identificou bug HIGH **convergente em ambos os modelos**:

`read_web_cache()` em `web/db.py` usava `try: ... except Exception: pass;
return None`, tornando **DB errors indistinguiveis de cache miss**.
Cenários afetados:

1. **Pool exhaustion** (`POOL_MAX=16`) sob carga de crawler — exatamente
   o padrão que motivou o PR #57.
2. **DB restart / failover / network blip** durante o crawl.
3. **`statement_timeout`** durante `cleanup_orphan_empresa_cache`
   rodando `DELETE` em batches contra `web_cache`.
4. **Cold start** com `_pool` não inicializado raising `RuntimeError`.
5. **JSON corrompido** no payload do cache.

Pré-PR #181, todos esses cenários retornavam `404 Not Found` — bug
recoverable (Google retentava por semanas). **Pós-PR #181 retornavam
`410 Gone`** — Google de-indexava permanente em dias. Uma janela de
5 minutos de pool starvation durante crawl podia marcar páginas
legítimas como removidas.

### Mudança

`web/db.py`:
- Novo sentinel `CACHE_ERROR` (singleton de classe `_CacheError`)
  retornado quando `read_web_cache()` falha por erro de DB/conexão.
- Bare `except Exception: pass` substituído por log de WARNING
  (visível em journalctl) — antes era silencioso, dificultando diagnóstico.
- Tipo de retorno expandido: `tuple[cols, rows] | _CacheError | None`.

`web/routes/empresa.py` (ambos `empresa_perfil` e `empresa_perfil_municipio`):
- Branch novo: `if cached is CACHE_ERROR: return 503 com Retry-After`.
- Comportamento atual mantido para `None` (cache miss permanente) e
  hit válido.

### Por que esse fix é mínimo

Considerei (e descartei) abordagens mais elaboradas:

- **Existence check em `mv_empresa_pb`** antes de decidir 410 vs 503:
  ~30 linhas + LRU cache + day_bucket TTL + thundering herd protection.
  Yagni para distinguir "URL nunca existiu" de "URL órfã" — >99% dos
  misses são caso (b) órfão.
- **Sentinel value no cache** marcando "qualifying mas rewarming":
  exige mudança no warmer, no schema do `web_cache` e na lógica de
  cleanup. Trade-off ruim.
- **Feature flag pra rollout gradual**: 503 é universalmente seguro
  (não causa de-indexação como 410), então rollout direto está OK.

A mudança atual:
- ~15 linhas em `web/db.py` (sentinel + log)
- ~10 linhas por handler em `empresa.py` (verificar `is CACHE_ERROR`)
- Total ~35 linhas

### Trade-offs (após esta revisão)

| Caso | Comportamento atual |
|---|---|
| (a) URL inventada `/empresa/99999999999999/x` | 410 Gone |
| (b) CNPJ órfão (PR #156 cleanup) | 410 Gone ✅ |
| (c) Cold start / CNPJ novo entre warms | 410 transient (raro — sitemap gated em deploy.yml exige cache coverage ≥80%) |
| (d) **DB error transiente** (NOVO) | **503 Retry-After** ✅ |
| (e) JSON corrompido no cache | 410 (cache hit mas dict vazio) — aceitável, cleanup re-popula |

### Reversibilidade

Se uma URL legítima ainda assim receber 410 (caso c muito raro), reverter
para 200 leva 1 crawl pós-warm (Google atualiza status em re-crawl).
Mas com sitemap gated + cache coverage 80%, esse caso é estatisticamente
desprezível (vs ~6.7k retries/dia de URLs verdadeiramente órfãs).

### Observabilidade

`logging.getLogger("transparencia.db").warning(...)` em `read_web_cache`
torna DB errors visíveis em `journalctl -u cruza-web` — antes eram
silenciosos. Padrão de erro para alertar:

```
read_web_cache DB error for EMPRESA_PERFIL:00012345678901 — PoolError: connection pool exhausted
```

Monitorar pico desses warnings após deploy correlaciona com hits 503.

