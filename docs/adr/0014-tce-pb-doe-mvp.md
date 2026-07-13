# ADR-0014: TCE-PB DOE — empresa citada em processos

- Status: Accepted
- Data: 2026-05-22
- Decisores: Lucas (maintainer)
- Tags: etl, fonte-de-dados, web, mv, frontend, lgpd

## Contexto

O Tribunal de Contas do Estado da Paraiba publica diariamente em
`https://publicacao.tce.pb.gov.br/decisao.php?ano=YYYY` o **Diario Oficial
Eletronico do TCE-PB (DOE-TCE-PB)** com decisoes/acordaos de processos
(PCAs, licitacoes, denuncias, contratos, recursos etc). Cada decisao tem
um hash estavel como ID e um PDF imutavel servido em
`https://publicacao.tce.pb.gov.br/<hash>`.

Nao havia integracao com essa fonte. Empresas fornecedoras de prefeituras
PB que aparecem em processos do TCE-PB (irregulares, com multa, com
debito imputado) eram invisiveis no nosso fluxo de risco/fraude.

## Decisao

Adicionar uma feature MVP em `/empresa/<cnpj>`:

> **"TCE-PB — processos publicados no DOE"** — count + tabela de processos
> em que o CNPJ aparece, com visualizacao embed do PDF da decisao via
> backend proxy (anti-`X-Frame-Options`).

Implementacao em **PR unico** abrangendo:

1. **Schema** (`sql/42_tce_pb_decisao.sql`): tabelas
   `tce_pb_decisao` (PK=`_nk_md5` md5 de NK natural) e
   `tce_pb_decisao_cnpj` (FK CASCADE) — bag de CNPJs por decisao.

2. **ETL classico** (`etl/23_tce_pb_doe.py`): download (4 workers + retry
   exponencial calibrado em 9.935 PDFs) + parse pdfminer.six + UPSERT
   idempotente com gating por `parser_version`. Registrado como **Fase 18**
   em `etl/run_all.py` (antes da Fase 19 Views, para que `mv_empresa_tce_pb`
   ja tenha dados quando criada).

3. **MV L1** `mv_empresa_tce_pb` (em `sql/12_views.sql` +
   `deploy/mv_updates/mv_empresa_tce_pb.sql` para swap atomico):
   agregado por `cnpj_basico` com jsonb embarcado dos top 20 processos
   mais recentes (cada processo agrupa N decisoes).

4. **MV L2** `mv_empresa_pb` ganha 4 colunas `qtd_processos_tce_pb*`
   (badge em listas). O jsonb completo fica em `mv_empresa_tce_pb`,
   consultado separadamente pela rota de empresa (query barata, indexada
   por `cnpj_basico`).

5. **Rota proxy** `/api/tce-pb/decisao/<hash>.pdf` em
   `web/routes/tce_pb.py`: whitelist por `tce_pb_decisao.hash_publicacao`,
   cache local em `/var/cache/cruza-web/tce-pb/<2-prefix>/<hash>.pdf`,
   reescreve `Content-Disposition: inline` (default) ou `attachment`
   (com `?download=1`).

6. **Frontend**: secao colapsavel
   `partials/empresa/_tce_pb_doe.html` + dialog MD3 full-screen com iframe
   apontando pra rota proxy (mobile-first, touch ≥44px).

## Calibracao quantitativa (N=9.935 PDFs, 2024-2026)

Antes de implementar, baixamos uma amostra grande (alvo: 10k decisoes
individuais) e analisamos viabilidade:

| Metrica | Valor |
|---|---|
| PDFs baixados | 9.935 / 10.000 (0,65% bloqueio Cloudflare persistente) |
| Densidade CNPJ por PDF | 6,4% (545 PDFs citam ≥1 CNPJ) |
| **CNPJs distintos no corpus** | **659** |
| CNPJs validos contra base RFB local | 646 / 659 (98%) |
| CNPJs UF=PB | 381 (59%) |
| **CNPJs que sao fornecedores de pelo menos 1 cidade PB** | **459 / 659 (69,7%)** |

A densidade alta de fornecedores ja cadastrados na nossa base justifica
o esforco de ETL + MV + proxy: 459 CNPJs entrarao com sinal qualificado.

### Calibracao de regex

Iteramos sobre o corpus parcial (N=5.491) ate convergir nestes padroes:

- `irregular`: `\bjulgar?\s+irregular|contas?\s+irregulares?|julgou-se\s+irregular`
- `regular_ressalva`: `regular(?:es)?\s+com\s+ressalva|aprova[çc][ãa]o\s+com\s+ressalva`
- `regular` (com lookahead pra nao vazar): `\bjulgar?\s+regular(?!\s+(?:com\s+ressalva|irregular))|\bparecer\s+favor[áa]vel\b`
- `aplicou_multa`: `aplicar?\s+multa|impor?\s+multa`
- `imputou_debito`: `imputa[çc][ãa]o\s+de\s+d[ée]bito|imputar?\s+d[ée]bito|ressarcimento[^\n]{0,40}R\$`

Excluimos `tipo_materia=atos_pessoal` dos agregados (57,9% do volume mas
apenas 0,1% irregular — ruido puro).

### Padrao de download Cloudflare-friendly

Testes empiricos:

| Config | Resultado |
|---|---|
| 12 workers, sem retry | ~70% HTTP 520 |
| **4 workers + retry exponencial {520, 429, 503, timeout}, backoff 2→4→8→16→30s** | **0,65% erro, 3,6 PDFs/s sustentado** |

## Bloqueios e solucoes

### Bloqueio: `X-Frame-Options: SAMEORIGIN` no PDF

TCE-PB serve `https://publicacao.tce.pb.gov.br/<hash>` com cabecalhos:

- `Content-Disposition: attachment` (forca download)
- `X-Frame-Options: SAMEORIGIN` (impede iframe externo)

Embedding direto e impossivel.

**Solucao**: rota proxy `/api/tce-pb/decisao/<hash>.pdf` que:

1. Valida `hash` contra regex `^[a-f0-9]{32}$` (impede path traversal).
2. Valida que `hash` existe em `tce_pb_decisao` (anti-open-proxy — sem
    isso, qualquer hash seria buscado upstream).
3. Cacheia localmente em
    `/var/cache/cruza-web/tce-pb/<2-prefix>/<hash>.pdf`. PDFs sao
    imutaveis por hash (CDN TCE-PB), entao cache "for-ever" e seguro.
4. Reescreve `Content-Disposition` para `inline` (ou `attachment` com
    `?download=1`).
5. `Cache-Control: public, max-age=2592000, immutable` (30 dias).

### LGPD

3% dos PDFs contem CPF cru. NAO persistimos — apenas `cpf_digitos_6`
(prefixo padronizado pelo projeto). Esta camada nao indexa pessoas (v2).

### Parser version

Schema reserva coluna `parser_version SMALLINT`. UPSERT so atualiza row
existente se `EXCLUDED.parser_version > current OR text_sha256 IS
DISTINCT`. Bumpar `PARSER_VERSION` em `etl/23_tce_pb_doe.py` + rodar
`--reprocess-all` reaplica heuristicas sem refazer download.

## Estrategia de deploy

Esta secao reflete as **limitacoes reais** do framework `mv_swap.py` descobertas
em reviews automaticos (Opus 4.7 + GPT 5.5) na evolucao deste PR. Nem todos os
passos sao downtime ZERO estrito; documentamos a janela real de cada passo.

| Etapa | Input deploy.yml | Tempo | Degradacao real |
|---|---|---|---|
| 1. Schema + web + bootstrap MV vazia | `etl_phase=web` (aplica `sql/42_*.sql`) | ~5 min | ~2s janela 502s no restart cruza-web (uvicorn single-process; limitacao conhecida) |
| 2. Bootstrap ETL + REFRESH CONCURRENTLY da MV L1 | `etl_phase=only:23` (roda APENAS a Fase TCE-PB DOE) | ~3-4h | 0 (ETL em background; REFRESH CONCURRENTLY nao bloqueia leitores) |
| 3. mv_swap da L2 (`mv_empresa_pb` ganha 4 colunas) | `etl_phase=web` + `mv_swap=mv_empresa_pb` | ~10-30 min | janela curta com **apenas `v_risk_score_pb`** (view normal, recriada via DDL instantaneamente). `mv_municipio_pb_kpi_score`, `mv_municipio_pb_mapa`, `mv_q67_dated_pb`, `v_risk_score_empresa` **nao** dependem de `mv_empresa_pb` (verificado em `sql/12_views.sql` apos review v3). Impacto trafego real: marginal |
| 4. Shadow rewarm | `etl_phase=web` + `rewarm_cache_keys=EMPRESA_PERFIL,EMPRESA_PERFIL_MUN` | ~30-60 min | 0 (shadow pattern; live rows servem trafego ate swap atomico). Custo extra do warm devido a lookup `EMPRESA_TCE_PB_DOE_BY_BASICO` em 143k empresas: **~5-7 min** (lookup PK em MV indexada) |

**CRITICO — passo 2 usa `only:23`, nao `23` nem `only:18`:** `etl/run_all.py` interpreta
arg numerico como **start_phase** (roda da Fase N ate o fim). `etl_phase=23`
rodaria Fase TCE-PB DOE + Fase Views (`etl.21_views`), que faz `DROP ... CASCADE` de
TODAS as MVs no topo de `sql/12_views.sql` — anula a estrategia e causa 1-2h
de downtime. PR #202 adicionou modo `--only N` em `run_all.py` e formato
`only:N` em `deploy.yml` para o caso cirurgico.

**Importante — N e o INDICE 1-based na lista `PHASES` de `etl/run_all.py`, NAO o label "Fase X"
do tuple.** O label "Fase 18: TCE-PB DOE" e historico (preservado pra nao
renumerar labels antigos); o indice real do tuple `etl.23_tce_pb_doe` na
lista e **23** (item 23 contando a partir de 1). Para confirmar antes de
qualquer deploy `only:`:
```bash
python -c "from etl.run_all import PHASES; [print(i+1, m) for i,(_,m) in enumerate(PHASES)]"
```

**Por que NAO swap conjunto da L1 + L2 (correcao do "swap conjunto" v1/v2):**
`etl/mv_swap.py` itera CSV uma MV por vez, com COMMIT entre swaps — nao e
transacional multi-MV. Mais grave: swap de `mv_empresa_tce_pb` (L1) faria
`DROP CASCADE` que derrubaria `mv_empresa_pb` (L2) entre os dois swaps. Por isso
a estrategia evita swapar L1: usa `REFRESH CONCURRENTLY` (zero-downtime) para a
L1 e reserva `mv_swap` apenas para a L2 que **muda de schema** neste PR.

**Bootstrap da L1 (BLOCKER-1 dos reviews):** `mv_swap` aborta se a MV nao
existir. `sql/42_tce_pb_decisao.sql` cria `mv_empresa_tce_pb` como vazia via
`CREATE MATERIALIZED VIEW IF NOT EXISTS` no passo 1, garantindo que o
REFRESH CONCURRENTLY do passo 2 e qualquer mv_swap futuro funcionem.

**Rollback honesto (BLOCKER-3 corrigido):** `mv_swap.py:283` faz
`DROP CASCADE`, NAO mantem `<mv>_old` — rollback exige re-swap com SQL
pre-mudanca (`deploy/mv_updates/mv_empresa_pb.sql` da branch anterior) +
REFRESH em cadeia. Plano: **antes do merge**, tagear o commit pre-PR (HEAD
de `main` no momento) como `pre-tce-pb-doe`; usar `git checkout pre-tce-pb-doe
-- deploy/mv_updates/mv_empresa_pb.sql sql/12_views.sql` para extrair o SQL
de rollback se necessario.

**Rollback do ETL apos passo 3:** `TRUNCATE tce_pb_decisao*` por si so deixa
MVs apontando para decisoes inexistentes (MV e snapshot, nao segue TRUNCATE).
Apos rollback de dados, requer `REFRESH MATERIALIZED VIEW CONCURRENTLY mv_empresa_tce_pb`
+ `REFRESH MATERIALIZED VIEW mv_empresa_pb` + cadeia L2.

**O que NAO fazer:** `etl_phase=sql` neste PR. Dispara `etl.21_views` que
executa `DROP MATERIALIZED VIEW ... CASCADE` de TODAS as MVs no topo de
`sql/12_views.sql` — 1-2h de downtime com paginas quebradas.

Cache keys afetadas: prefixos `EMPRESA_PERFIL:<cnpj>` e
`EMPRESA_PERFIL_MUN:<cnpj>:<slug>`. Match exato (NAO substring) em
`rewarm_cache_keys` — usar ambos literais.

## Provisionamento do diretorio de cache

`/var/cache/cruza-web/tce-pb/` precisa existir e ser writable pelo
usuario do servico `cruza-web`. Adicionar step ao `deploy.yml` ou
documentar em `docs/ops.md` como pre-requisito do PR.

## Consequencias

### Positivas

- 459 CNPJs com sinal qualificado de TCE-PB direto na pagina de empresa.
- PDFs embedded na nossa origem (UX > sair pro portal externo).
- Fundacao reutilizavel pra v2 (servidores/pessoas, cidades).
- Schema versionado (`parser_version`) permite iterar regex sem
  refazer download.

### Negativas / debt

- Spec do framework incremental P1-P6 **nao** existe ainda (framework e
  CSV-only — PDFs nao se encaixam). Atualizacao diaria roda via Fase 20
  com `--only-recent N`. Documentado como limitacao conhecida.
- Cache do proxy pode crescer. Stub atual nao tem eviction. ~5GB max
  esperado pra 10k PDFs. Adicionar LRU em v2 se necessario.
- Regex de parsing tem `~5%` taxa de `resultado=indef` — ok pro MVP,
  mas alvo pra calibracao continua.

## Alternativas consideradas

1. **Embed do iframe direto na origem do TCE-PB**: impossivel
   (`X-Frame-Options: SAMEORIGIN`).
2. **Renderizar PDFs em imagens**: caro (pdf2image + storage de
   thumbnails) e perde UX nativa (busca, zoom).
3. **Apenas link externo "ver no TCE-PB"**: perde a feature de
   "ver decisao sem sair do site" — questao central que motivou a
   feature.
4. **JSONB completo em `mv_empresa_pb`**: dobra o tamanho da MV
   (~70k empresas × ~5KB jsonb medio = ~350MB) e atrasa refresh.
   Manter jsonb em MV separada (`mv_empresa_tce_pb`) e consultar
   sob demanda e mais barato.

## Referencias

- `etl/23_tce_pb_doe.py` — ETL phase (Fase 20 em `etl/run_all.py`)
- `sql/42_tce_pb_decisao.sql` — schema
- `sql/12_views.sql` — `mv_empresa_tce_pb` + coluna em `mv_empresa_pb`
- `deploy/mv_updates/mv_empresa_tce_pb.sql` — swap atomico
- `deploy/mv_updates/mv_empresa_pb.sql` — swap atomico (atualizado)
- `web/routes/tce_pb.py` — rota proxy
- `web/templates/partials/empresa/_tce_pb_doe.html` — secao colapsavel
- `web/static/js/components/tce-pdf-viewer.js` — dialog viewer
- `web/static/css/components/tce-pdf-viewer.css` — estilo mobile-first
- ADR-0006 — mv_swap atomico (mecanismo reutilizado)
- ADR-0013 — zero-downtime web (estrategia herdada)
