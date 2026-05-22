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
   idempotente com gating por `parser_version`. Registrado como **Fase 20**
   em `etl/run_all.py`.

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

## Estrategia de deploy (zero-downtime)

| Etapa | Input deploy.yml | Tempo | Downtime |
|---|---|---|---|
| 1. Schema (CREATE TABLE IF NOT EXISTS) | `etl_phase=sql` | ~30s | 0 |
| 2. Bootstrap ETL (download + parse + load) | `etl_phase=20` ou via `etl_phase=incremental` futura | ~3-4h | 0 (background) |
| 3. Provisionar cache dir na VM | manual ou via deploy step | <1s | 0 |
| 4. MV L1 nova | `mv_swap=mv_empresa_tce_pb` | ~1s bloqueio | ~1s |
| 5. MV L2 atualizada | `mv_swap=mv_empresa_pb` | ~1s bloqueio | ~1s |
| 6. Frontend | `etl_phase=web` + `rewarm_cache_keys=EMPRESA_PERFIL,EMPRESA_PERFIL_MUN` | ~30min warm | 0 |

Cache keys afetadas: prefixos `EMPRESA_PERFIL:<cnpj>` e
`EMPRESA_PERFIL_MUN:<cnpj>:<slug>` — populadas pelo `web/warm_cache.py`.
Shadow rewarm seletivo via `rewarm_cache_keys` (memoria zero-downtime).

Rollback: `mv_swap` mantem versao anterior renomeada com sufixo
(`<mv>_old`), instantaneo (~1s).

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
