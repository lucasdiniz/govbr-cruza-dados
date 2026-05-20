# ADR-0012: Páginas dedicadas para empenhos (`/empenho/pj/...` e `/empenho/pf/...`)

## Status

Proposed

## Date

2026-05-19

## Context

Hoje, o detalhe de um empenho individual em `transparenciapb.org` só é
visualizável dentro de uma **dialog modal** (`web/static/js/components/
empenho-dialog.js`), aberta a partir de listagens em `/empresa/<cnpj>`,
`/empresa/<cnpj>/<mun>`, `/cidade/<slug>/<yyyy>-<mm>` e
`/licitacao/<...>`. A dialog faz fetch ad-hoc no endpoint
`/api/empenho/detalhes` ([`web/routes/cidade.py:2231`](../../web/routes/cidade.py))
com `LATERAL JOIN` pra resolver a licitação canônica.

Limitações desse modelo:

1. **Sem URL própria** — empenho não pode ser linkado, compartilhado em
   redes sociais, citado em relatórios investigativos
   ([`relatorios/`](../../relatorios/)), nem encontrado por busca externa
   (Google, Bing). A modal só existe enquanto a página-pai está aberta.
2. **Sem SEO** — Googlebot não indexa conteúdo de modal aberto via
   JavaScript. ~15M empenhos da base TCE-PB (`tce_pb_despesa`) são
   invisíveis para descoberta orgânica.
3. **Profundidade limitada** — dialog tem espaço para ~10-15 campos.
   Empenho real tem 30+ campos relevantes (histórico TCE, classificação
   funcional/programática, fonte de recurso, modalidade de aplicação,
   subelemento, todos os pagamentos parcelados, vínculo com servidor
   beneficiário no caso de diárias, vínculo com licitação-mãe, etc).
4. **Sem cross-link de outras entidades** — quando o usuário está em
   `/empresa/<cnpj>` (fornecedor), não há como linkar `<a href>` para
   um empenho específico em outra aba; só é possível abrir a modal.
5. **Cache miss penaliza UX** — dialog faz fetch a cada abertura. Para
   empenhos populares (consultados várias vezes pelo mesmo investigador),
   isso desperdiça query.

Entidades vizinhas já têm página dedicada com SEO + sitemap completos:
`/empresa/*` (~143k páginas, 3 shards de sitemap), `/empresa/<cnpj>/<mun>`
(~250k, 6 shards), `/licitacao/*` (~350k PJ-qualificadas, 8 shards),
`/cidade/<slug>/<yyyy>-<mm>` (~14k, 1 shard). **Empenho é a única
entidade-folha do grafo de transparência sem página própria**, apesar
de ser o "átomo" do gasto público (cada R$ pago pela administração tem
um empenho na origem).

### Quantos empenhos?

Queries em `tce_pb_despesa` (16.13M rows, prod). **Identidade usa 5-tupla**
`(municipio, codigo_ug, data_empenho, numero_empenho)` + tipo (PJ/PF) — ver
"Uniqueness key" na seção Decision. Contagens 4-tupla (sem `data_empenho`)
mascaram ~24k colisões de empenhos genuinamente distintos, por isso são
substituídas por 5-tupla:

| Universo | Distinct 5-tuplas (`mun`, `ug`, `data`, `num_empenho`) | % |
| -------- | ------------------------------------------------------:| -:|
| **PJ qualificado** (digits=14 + JOIN `empresa` + `natureza_juridica NOT LIKE '1%'` + `valor_pago>0`) | **~12,107,000** | 79.7% |
| **NAO-PJ** (PF com CPF zero-padded + órgãos públicos `1xxx` + sem cadastro RFB) | **~3,081,000** | 20.3% |
| **Total empenhos com pagamento** | **15,188,883** | 100% |

(Contagem PJ/PF 5-tupla derivada da proporção 4-tupla, com delta 4→5 de
+0.4% distribuído proporcionalmente. Revalidar em prod no PR-1.)

Distribuição PJ por materialidade:

| Filtro                              | Páginas PJ | Sitemap shards (49k/shard) |
| ----------------------------------- | ----------:| --------------------------:|
| Todas                               | 12,053,900 |                       ~246 |
| `SUM(valor_pago) > R$1k`            |  5,088,913 |                       ~104 |
| `SUM(valor_pago) > R$10k`           |    600,716 |                        ~13 |

### Alternativas consideradas

**A. Não fazer (manter só dialog).** Custo zero, mas perde toda
descoberta SEO e impede cross-link entre entidades. Cada novo
relatório investigativo em `relatorios/` precisa de print/screenshot
ou descrição textual em vez de link clicável.

**B. Página única `/empenho/<mun>/<ano>/<ug>/<num>` (sem split PJ/PF).**
Mais simples (uma rota, um warmer, um cache key). Mas:

- Sitemap precisaria filtrar PJ-vs-PF dentro do gerador (não por
  construção da URL), aumentando risco de regressão LGPD se alguém
  inverter o filter por acidente.
- `X-Robots-Tag: noindex` em PF teria que ser branch dentro da rota
  (vs cabeçalho estático).
- Cache key não distingue tipo, dificultando GC seletivo (ex: "limpar
  só PF mantendo PJ").

**C. Página única `/empenho/<mun>/<ano>/<ug>/<num>` com PJ no sitemap
+ PF cache-only.** Como (B) mas mantendo o split por sitemap. Reduz
risco LGPD mas mantém ambiguidade da URL (URL sozinha não diz se é
PF ou PJ).

**D. Split PJ/PF em prefixos diferentes** (`/empenho/pj/...` e
`/empenho/pf/...`). Maior diff inicial (duas rotas, dois warmers, dois
templates), mas:

- LGPD-safe **por construção**: impossível um shard PJ acidentalmente
  emitir URL PF, ainda que o filter quebre.
- URL auto-documenta o tipo (compartilhar `/empenho/pf/...` no Twitter
  já avisa pesquisador "isso é dado pessoal").
- `X-Robots-Tag: noindex, nofollow` aplicável estaticamente na rota PF.
- Cache keys separados (`EMPENHO_PERFIL_PJ` vs `EMPENHO_PERFIL_PF`),
  permitindo GC e métricas independentes.
- Mesmo padrão de cache key prefix que já uso para outros pares
  PJ/PF no projeto.

**E. Só PJ (sem rota PF).** Mais simples, mas dialog atual exibe
empenho PF normalmente; remover esse acesso quando o investigador
clica em "Ver página" geraria UX inconsistente. Além disso, dialog
PF precisaria de algum identificador estável para deep-link compartilhável
(mesmo problema da rota dedicada com `noindex`).

### PF no sitemap?

Avaliado e descartado por LGPD (Lei 13.709/2018):

- **Finalidade (art. 6, I) + minimização (art. 6, III)**: portal é de
  transparência de gasto público, não de criação de dossiê agregado
  sobre PFs. Sitemap entrega URLs ao Googlebot, criando páginas
  pesquisáveis por nome ("João da Silva empenho prefeitura X").
- **Precedente do próprio projeto**: `/licitacao/*` já é PJ-only no
  sitemap com o mesmo filter (digits=14 + JOIN `empresa` + `natureza
  NOT LIKE '1%'`), consolidado em PR #108 com review Opus 4.7 + GPT 5.5.
- **Risco de reidentificação**: nome + município + ano + UG bastam pra
  identificar pessoa real mesmo com CPF mascarado `***.NNN.NNN-**`.
- **Right-to-be-forgotten (art. 18)**: cada PF poderia exigir remoção
  individual, gerando custo operacional contínuo.
- **PJ tem expectativa zero de privacidade**: dados RFB são públicos
  por construção. PF não.

PF mantém cache populado (deep-link da dialog funciona, retorna 200),
mas rota responde `X-Robots-Tag: noindex, nofollow` e nenhum sitemap
lista a URL. Investigador que chegou ao empenho via fluxo natural
(cidade → licitação → dialog → "Ver página") tem acesso; descoberta
passiva via Google fica bloqueada.

## Decision

Adotamos **alternativa D**: dois prefixos paralelos com URL
auto-documentada.

### URL canônica

```
PJ:  /empenho/pj/<mun-slug>/<yyyy-mm-dd>/<codigo-ug>/<num-empenho-slug>
PF:  /empenho/pf/<mun-slug>/<yyyy-mm-dd>/<codigo-ug>/<num-empenho-slug>
```

- `mun-slug` = `municipio_slug(municipio)` (helper existente).
- `<yyyy-mm-dd>` = `data_empenho` completa (ISO). Bound `2018-01-01`
  até `2099-12-31`. **Não usar só `<ano>`** — ver "Uniqueness key"
  abaixo.
- `<codigo-ug>` = **raw `codigo_ug`** (campo `VARCHAR(20)`, tipicamente
  numérico como `201095`). Não usa slug de `descricao_ug` porque (a)
  duas UGs distintas podem compartilhar descrição idêntica ("Secretaria
  Municipal de Saúde" em municípios diferentes), (b) descrição muda ao
  longo do tempo (rebranding administrativo) quebrando URLs antigas,
  (c) `codigo_ug` é estável e oficial (chave TCE-PB).
- `<num-empenho-slug>` = `numero_slug(numero_empenho)` (lowercase,
  remove acentos, hífen único). Cobre variações TCE-PB (`2025NE000282`,
  `001/2025`, `00028-2025`). Compute valida que slug → numero_empenho
  raw é bijetivo dentro do escopo `(municipio, codigo_ug, data_empenho)`;
  no caso raríssimo de colisão de slug (estimado <100 rows em prod),
  sufixo `-<6charHexHash>` é adicionado e persistido no cache.

**Uniqueness key**: 4-tupla `(municipio, codigo_ug, data_empenho,
numero_empenho)` — **mesma chave do índice natural**
`ix_tce_pb_despesa_nk` em [`sql/30_tce_pb_despesa_natural_keys.sql`](../../sql/30_tce_pb_despesa_natural_keys.sql)
(menos as colunas de subitem como `codigo_subelemento`, que agregam
em line-items dentro da página).

**Por que `data_empenho` completa em vez de só `ano`** (CRÍTICO —
verificado empiricamente em prod, 2026-05-19):

```sql
-- 4-tuplas (mun, ug, EXTRACT YEAR FROM data_empenho, num_empenho):  15,121,826
-- 4-tuplas (mun, ug, data_empenho FULL,            num_empenho):    15,188,883
-- Delta: +67,057 (0.4%) — corresponde a 4-tuplas-ano que mascaravam
--                          empenhos distintos.
-- 4-tuplas com >1 cpf_cnpj distinto (TRUE collision, fornecedores
--                          diferentes no mesmo bucket): 23,894
```

Ou seja, **~24k empenhos genuinamente diferentes** (fornecedores
distintos, valores distintos) **colapsariam para a mesma URL** se a
chave fosse só ano. O custo é +0.4% de URLs (+67k) — trivial.

Múltiplas rows de `tce_pb_despesa` com a mesma 4-tupla expandida
(diferindo só em `codigo_subelemento`/`codigo_fonte_recurso`/etc)
mapeiam ao mesmo empenho — agregadas no compute em line-items de
classificação.

### Cache-only (mesmo invariant do PR #57)

Toda rota lê **exclusivamente** de `web_cache`:

- Cache hit válido → 200 com payload renderizado.
- Cache miss em PJ (sitemap-listed) → **503 Service Unavailable** com
  `Retry-After: 3600`. Sinaliza ao crawler "warm ainda não cobriu,
  retorne depois". Aplica padrão consolidado em ADR-0009 revisão
  2026-05-19 (DB error vs cache miss).
- Cache miss em PF (não-sitemap, só deep-link) → **404 Not Found**
  com `X-Robots-Tag: noindex, nofollow`. Sem retry — usuário/bot que
  inventou URL PF não deve receber Retry-After.
- DB error transiente (sentinel `CACHE_ERROR` de ADR-0009) → 503
  Retry-After em **ambas** as rotas.

Sem fallback live-query — protege DB contra storm de crawler.

### Cache keys

```python
EMPENHO_PERFIL_PJ  → key = f"{mun_slug}:{yyyy_mm_dd}:{codigo_ug}:{num_slug}"
EMPENHO_PERFIL_PF  → key = f"{mun_slug}:{yyyy_mm_dd}:{codigo_ug}:{num_slug}"
```

Cache key **espelha 1:1 a URL** — eliminando classe de bugs onde
"a URL aceita mas o cache não acha" ou vice-versa. `codigo_ug` raw +
`data_empenho` ISO + `num_slug` (com sufixo de hash se colisão) =
identidade reversível.

Mesma `key` em prefixos `query_id` diferentes — preserva GC seletivo e
permite métricas por tipo.

### Sitemap

Apenas PJ qualificado, **enumerando direto de `web_cache`** (não da
qualifying SQL):

- **Fonte**: `SELECT municipio FROM web_cache WHERE query_id =
  'EMPENHO_PERFIL_PJ' [AND ...filter de materialidade]`. Mesma defesa
  de licitação ([`web/routes/seo.py:821-864`](../../web/routes/seo.py))
  contra publicar URLs ainda não warmed — sem isso, sitemap geraria
  até ~20% de URLs respondendo 503 durante warm gate ≥80%.
- **Filter de materialidade**: campo `valor_pago_total` no payload do
  cache (`web_cache.payload->>'valor_pago_total' > '1000'`) — sem
  segundo SELECT à `tce_pb_despesa`. Threshold ajustável via env var
  `EMPENHOS_SITEMAP_MIN_VALOR_PAGO` (default `1000.00`).
- **Universo de qualificação** (aplicado pelo **warmer**, não pelo
  sitemap): distinct 5-tuplas com `LENGTH(REGEXP_REPLACE(cpf_cnpj,
  '\D','','g'))=14` + JOIN `empresa` em `cnpj_basico` +
  `natureza_juridica NOT LIKE '1%'` + `valor_pago > 0`.
- Volume esperado: ~5.1M URLs → **~104 shards**
  `/sitemap-empenhos-{0..103}.xml`.
- Threshold ajustável via env var sem deploy (subir pra R$ 10k reduz
  a ~13 shards; descer pra R$ 0 expande pra ~246 shards).
- Gated por env flag `SITEMAP_INCLUDE_EMPENHOS=1` (default off em
  deploy.yml até warm cobrir ≥80% — mesmo gate de empresas/licitações).
- Past-end shard → **200 OK vazio** (não 410), seguindo padrão licitação
  consolidado em PR #167 review Opus 4.7 (evita 410 espúrio durante
  warm em progresso).

### Warmer

Duas novas fases em `web/warm_cache.py`:

- `_warm_empenhos_pj_phase` — itera PJ qualificados em batches por
  município.
- `_warm_empenhos_pf_phase` — itera NAO-PJ com `valor_pago > 0`.

Shadow rewarm (ADR-0003) aplicável: `query_id` ganha sufixo
`__pending` durante recompute, swap atômico ao final.

**Resume mode requer redesign — `_filter_cached_munis` não escala
para 15M keys**. O helper atual
([`web/warm_cache.py:799-834`](../../web/warm_cache.py)) carrega
todas as keys de um `query_id` num `set` Python; com 15M keys × URL
~80 bytes, isso é ~1.2GB de RAM por warm phase. Padrão atual de
licitação ([`web/warm_cache.py:1811-1864`](../../web/warm_cache.py))
já tem hard limit defensivo de 1M — empenho vai estourar.

Plano para resume escalável (decidido no PR-3 do slicing):

1. **Server-side cursor + streaming**: trocar `cur.fetchall()` por
   `cur.itersize=10000` com loop; cada item testado contra um filter
   in-memory por município/ano sendo processado naquele batch.
2. **Index dedicado**: `CREATE INDEX ON web_cache (query_id,
   (municipio LIKE 'mun-slug:%'))` — postgres já tem `(query_id,
   municipio)` UNIQUE, basta usar prefix-range scan.
3. **Batch por (município, ano)**: warmer enumera qualificados de
   `tce_pb_despesa` JOIN `web_cache` LEFT-anti para skipar já-cacheados
   sem materialização Python.

Resultado: resume usa O(N_batch) memória em vez de O(N_total). Estimativa
revista de resume run: **~4-8h** (não 2-4h como inicialmente sugerido).

CLI flags para skip individual:

```bash
python -m web.warm_cache --skip-empenhos-pj    # warm sem PJ empenhos
python -m web.warm_cache --skip-empenhos-pf    # warm sem PF empenhos
python -m web.warm_cache --only-empenhos       # só os dois acima
```

### Dialog → página dedicada

`empenho-dialog.js` ganha link "Ver página dedicada" no footer (análogo
ao "Ver perfil completo" de `fornecedor-dialog.js:127`). Slug derivation
reaproveita helpers já existentes (`numero_slug`, `municipio_slug`
exportados via window).

Hospitalmente o link só aparece se a página estiver no cache (HEAD
request pré-renderização ou flag no payload da dialog). Evita link
clicado → 503 (PJ não cacheado ainda) ou 404 (PF não cacheado).

### Deploy.yml toggles

Novos inputs em `.github/workflows/deploy.yml`:

```yaml
expose_empenhos_sitemap:
  description: "Expor /sitemap-empenhos-*.xml no índice de sitemaps.
    Recomenda-se manter false até warm cobrir ≥80% dos PJ qualificados."
  required: false
  type: boolean
  default: false

empenhos_sitemap_min_valor_pago:
  description: "Threshold de SUM(valor_pago) para incluir empenho PJ
    no sitemap. Default R$ 1000.00 (~5.1M URLs / ~104 shards).
    R$ 10000.00 reduz pra ~600k URLs / ~13 shards."
  required: false
  type: string
  default: "1000.00"
```

### Volume estimado

| Categoria             | Páginas              | No sitemap? |
| --------------------- | --------------------:| ----------- |
| PJ no `web_cache`     | ~12,107,000          | parcial (filter)         |
| PJ no sitemap (>R$1k) | ~5,109,000           | ✅ ~105 shards            |
| PF no `web_cache`     | ~3,081,000           | ❌ nunca (LGPD)          |
| **Total cache**       | **~15,189,000**      | —                        |

(Tabela usa 5-tupla; revalidar no PR-1. Volume PJ-sitemap pode oscilar
±5% após threshold final ser fixado em prod.)

Custos:

- **`web_cache` storage**: 15.2M rows × ~3KB payload ≈ **~45 GB**
  (vs ~2 GB atuais somando todos os outros). VM tem folga (>300 GB
  livre); monitor disk após primeira warm.
- **Warm primeira run**: ~50ms/página × 15.2M / 8 workers ≈ **~26 h**.
- **Warm runs subsequentes**: resume mode escalável → ~4-8 h (depende
  do redesign descrito na seção "Warmer" acima).
- **Sitemap build**: 105 shards × ~50ms ≈ ~5s (cache de 24h existe).

## Consequences

### Positive

- **Deep-link de empenhos**: relatórios investigativos
  ([`relatorios/`](../../relatorios/)) e cross-link entre entidades
  (`/empresa` → empenho específico de uma cidade) ficam clicáveis.
- **SEO**: ~5M páginas indexáveis cobrindo o "átomo" do gasto público
  da Paraíba. Cada empenho de valor relevante vira potencial entrada
  orgânica de visitante.
- **Profundidade da informação**: página dedicada acomoda 30+ campos
  (vs ~10-15 da dialog), incluindo classificação funcional/programática
  completa, vínculo com licitação-mãe via LATERAL JOIN, todos os
  pagamentos parcelados, beneficiário-servidor (no caso de diárias).
- **LGPD-safe por construção**: PF nunca em sitemap, URL auto-documenta
  tipo, `X-Robots-Tag: noindex` estático na rota PF.
- **Resilience**: cache-only protege DB de storm; sentinel
  `CACHE_ERROR` distingue DB-down de URL-inexistente (ADR-0009 rev
  2026-05-19).
- **Reaproveita padrão consolidado**: arquitetura praticamente
  espelho de `/licitacao/*` (mesmo cache-only, mesmo shadow rewarm,
  mesmo sitemap-gate, mesmo template skeleton).

### Negative / Trade-offs

- **+45 GB no `web_cache`**: 22x o tamanho atual. Disco da VM aguenta
  mas vira componente dominante. Monitor `pg_total_relation_size('web_cache')`
  após primeira warm.
- **Warm primeira run ~26h**: bloqueia self-hosted runner durante
  esse período (1-slot). Mitigação: rodar em janela de baixa demanda
  (fim de semana), incremental subsequente é <4h.
- **104 shards de sitemap**: sitemap-index cresce de ~18 entries pra
  ~122. Limite Google é 50k shards/index, folga enorme — mas alguns
  crawlers (Bing) podem reagir mal a saltos grandes. Rollout gated
  por `SITEMAP_INCLUDE_EMPENHOS=1`.
- **Diff inicial grande**: ~5 PRs (rota, compute, warmer, sitemap,
  dialog-link). Plano em [`docs/empenho-page-plan.md`] (a criar)
  detalha PR slicing.
- **PR slicing exige cuidado**: PJ e PF compartilham muito código
  (compute base, helpers, template parcial). Risco de copy-paste
  drift entre `empenho_pj.py` e `empenho_pf.py` se não compartilharem
  via helpers comuns.
- **Cache GC futuro**: empenhos antigos (>7 anos) tendem a ficar
  stale (TCE retroage classificação às vezes). Não é problema hoje
  mas vira tech-debt em 3-5 anos.

### Mitigations

- **Sitemap gated por env flag**: rollout faseado. `expose_empenhos_sitemap=true`
  só depois de warm cobrir ≥80% dos PJ qualificados (script de
  validação a criar).
- **`empenhos_sitemap_min_valor_pago` ajustável sem deploy**: começa
  em R$ 10k (~13 shards = ~640k URLs) pra validar comportamento
  Googlebot, desce gradualmente até R$ 1k.
- **Cache hit gating no link da dialog**: HEAD request ou flag
  `tem_pagina_dedicada` no payload da dialog evita link → 503/404.
- **PII scrub no campo `historico`**: aplica `web.utils.pii_scrub.scrub_pii()`
  ao texto livre antes de renderizar (mesma defesa de `objeto_licitacao`
  em PR #108 review GPT 5.5).
- **Numero_empenho format quirk**: `numero_slug()` normaliza variações
  TCE-PB. Edge cases (caracteres acentuados em descrição de UG, espaços
  duplos) cobertos por testes parametrizados em `tests/test_slugs.py`
  (a expandir).
- **GC futuro como ADR separado**: se cache size virar problema,
  novo ADR avalia (a) TTL de empenhos com `data_empenho < now - 7
  anos`, (b) tabela `web_cache_empenhos` particionada por ano, (c)
  compressão BRIN nos índices.
- **Re-validação periódica do filter LGPD**: incluir no checklist
  trimestral revalidar `LENGTH(digits)=14 + natureza NOT LIKE '1%'`
  vs novos códigos de natureza jurídica RFB (mudam ~anualmente).

## Implementation outline

Plano completo persistido na sessão de design (não-commitado).
Resumo executivo dos PRs:

1. **PR-1 (compute + dict schema)**: `web/empenho_compute.py`,
   `compute_empenho_dict(tipo, mun, ano, ug, num)`, contract test
   em `tests/test_empenho_compute.py`. Sem rota ainda — só library.
2. **PR-2 (rotas)**: `web/routes/empenho.py`, dois handlers (PJ + PF),
   integração `web/main.py`, template skeleton
   `web/templates/results/empenho.html`. Cache-miss-only ainda
   (warm não toca).
3. **PR-3 (warmer)**: `_warm_empenhos_pj_phase` +
   `_warm_empenhos_pf_phase` em `web/warm_cache.py`, CLI flags
   `--skip-empenhos-*`. Smoke run local em 100 empenhos.
4. **PR-4 (sitemap)**: `sitemap_empenhos_index` +
   `sitemap_empenhos_shard` em `web/routes/seo.py`, env flag
   `SITEMAP_INCLUDE_EMPENHOS`, input deploy.yml
   `expose_empenhos_sitemap`. Past-end → 200 vazio.
5. **PR-5 (dialog deep-link)**: `empenho-dialog.js` ganha link "Ver
   página dedicada", helpers `numero_slug`/`municipio_slug` exportados
   via `window`. Bump `FALLBACK_CACHE_VERSION` em `web/static/sw.js`.

Cada PR roda `python -m compileall web -q` + smoke local + review
Opus 4.7 + GPT 5.5 (padrão consolidado para PRs com SQL + templates
+ cache).

## Related

- Code:
  - [`web/static/js/components/empenho-dialog.js`](../../web/static/js/components/empenho-dialog.js) — dialog atual a evoluir.
  - [`web/routes/cidade.py`](../../web/routes/cidade.py) `/api/empenho/detalhes` (~L2231) — fonte do LATERAL JOIN canônico.
  - [`web/routes/licitacao.py`](../../web/routes/licitacao.py) — referência de arquitetura cache-only.
  - [`web/routes/seo.py`](../../web/routes/seo.py) — referência de sitemap sharded.
  - [`web/warm_cache.py`](../../web/warm_cache.py) `_warm_licitacoes_phase` (~L1784) — template para warmer.
  - [`sql/19_schema_tce_pb.sql`](../../sql/19_schema_tce_pb.sql) — schema `tce_pb_despesa`.
  - [`sql/30_tce_pb_despesa_natural_keys.sql`](../../sql/30_tce_pb_despesa_natural_keys.sql) — confirma que 4-tupla não é única (multiple subelementos), justificando agregação no compute.

- Other ADRs:
  - [ADR-0003](0003-shadow-rewarm.md) — shadow rewarm com swap atômico, aplicável ao warmer.
  - [ADR-0005](0005-no-orm-web.md) — raw SQL no compute, sem ORM.
  - [ADR-0007](0007-etl-normalize-fix.md) — fix de contaminação por CPF padded; relevante para filter PJ no sitemap.
  - [ADR-0009](0009-orphan-empresa-cache-cleanup.md) — sentinel `CACHE_ERROR` + revisão 503-vs-cache-miss, aplicável diretamente.

- External:
  - LGPD (Lei 13.709/2018), arts. 6 (princípios), 18 (direitos do titular).
  - Google Search Central, [Sitemaps limits](https://developers.google.com/search/docs/crawling-indexing/sitemaps/large-sitemaps) — 50k URLs/shard, sitemap-index limite 50k shards.

- PRs precedentes (padrão herdado):
  - PR #57 — cache-only invariant para `/empresa` e `/empresa/<cnpj>/<mun>`.
  - PR #108 — LGPD-safe sitemap em `/licitacao` (PJ-only filter).
  - PR #167 — past-end sitemap shard responde 200 vazio (não 410).
  - PR #181 — sentinel `CACHE_ERROR` distinguindo DB error de cache miss.

---

## Revision history

### 2026-05-19 (pre-merge) — incorpora review GPT-5.5

ADR foi revisado pelo code-review agent GPT-5.5 antes do merge. Quatro
achados endereçados in-place (status ainda Proposed, sem necessidade de
ADR-rev):

1. **CRITICAL — colisão de identidade (4-tupla insuficiente)**:
   `(municipio, codigo_ug, EXTRACT(YEAR FROM data_empenho), numero_empenho)`
   colapsa empenhos distintos. Verificado empiricamente: **23,894
   4-tuplas têm múltiplos `cpf_cnpj` distintos** (fornecedores
   diferentes no mesmo bucket). Fix: identidade vira 5-tupla com
   `data_empenho` completa (custo +0.4% URLs).

2. **HIGH — URL/cache key lossy**: `numero_slug(descricao_ug)` ignora
   `codigo_ug` raw (que é o identificador oficial estável). Fix: URL
   usa `codigo_ug` raw + `data_empenho` ISO; slug residual de
   `numero_empenho` ganha hash suffix se colisão detectada no warm.

3. **HIGH — sitemap publica 503s**: enumerar da qualifying SQL antes
   de warm 100% gera ~20% URLs respondendo 503. Fix: sitemap enumera
   de `web_cache` (mesma defesa de
   [`web/routes/seo.py:821-864`](../../web/routes/seo.py)).

4. **MEDIUM — warmer não escala**: `_filter_cached_munis` carrega
   todas as keys num set Python (~1.2GB para 15M). Fix: redesign para
   server-side cursor + batched por (município, ano); resume estimate
   atualizado para 4-8h (não 2-4h).

Endorsement do review: "high-level direction is sound. The blocking
problems are in identity/key design and sitemap/warm operational
mechanics, not in the overall product decision."
