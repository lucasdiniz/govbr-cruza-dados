# ADR-0015: Replace por bucket para os snapshots anuais do TCE-PB

## Status

Accepted

## Date

2026-10-21

Complementa (não substitui) [ADR-0014](0014-tce-pb-incremental-nk.md): o
`_nk_md5` continua sendo a chave de conflito; o que muda é o que acontece com
as linhas do ano que **não** estão mais no arquivo.

## Context

Os arquivos `despesas-YYYY` e `receitas-YYYY` do TCE-PB são **snapshots
anuais**: o TCE-PB regenera o arquivo do ano corrente todo dia (e o do ano
anterior até ~fevereiro). Entre duas publicações, registros existentes mudam:
`valor_pago` avança conforme o empenho é pago, descrições são corrigidas
(`"Recursos não vinculados"` → `"Recursos não Vinculados"`), `co`/`descricao_co`
e `codigo_subelemento_exibicao` são recodificados.

ADR-0014 tornou o upsert idempotente com `_nk_md5` = hash de **todas** as
colunas de negócio + `UPSERT_DO_NOTHING`. Consequência não prevista: qualquer
edição upstream gera um hash novo → a versão nova é inserida e a antiga
**nunca sai**. Medição read-only em produção (issue #211, 16/10/2026):

| ano_arquivo | linhas | empenhos distintos |
|---|---|---|
| 2020 | 3,22M | 1,62M |
| 2022 | 3,99M | 2,09M |
| 2025 | 4,14M | 2,39M |
| 2026 | 4,12M | 1,84M |

~40–50% das linhas de 2020–2026 eram versões velhas; todos os totais
municipais do site (pago, empenhado, nº de empenhos, receita 2026) estavam
~2× inflados. 2018–2019 (arquivos que não mudam mais) estavam limpos; o arquivo
`receitas-2025` tem exatamente o nº de linhas lógicas medido no banco
(163.252), confirmando o diagnóstico.

## Decision

Para specs cujo arquivo é o snapshot completo do bucket, o loader passa a
**substituir** o bucket: após o upsert, na **mesma transação do arquivo**, as
linhas do ano cujo `_nk_md5` não está no arquivo são removidas.

- `LoaderSpec.bucket_replace = BucketReplace(...)` habilita o modo
  (`tce_pb_despesa`, `tce_pb_receita`). Exige `nk_synthetic_md5`,
  `UPSERT_DO_NOTHING`, `YEAR_WINDOW` e 1 arquivo por bucket.
- `etl/incremental/replace.py` recalcula o `_nk_md5` de cada linha do arquivo
  com a **mesma projeção do upsert** (`build_target_projection`) e a **mesma
  função do trigger** (`etl_admin.nk_md5_<tabela>_row`), montando
  `ROW(...)::<tabela>` com cada coluna convertida para o tipo+typmod do target
  (ex.: `DECIMAL(15,2)`) — mesmo arredondamento do `INSERT`. (Versão com
  `jsonb_populate_record` dava o mesmo hash mas levava ~30 min para 2M linhas;
  `ROW` leva ~2 min.)
- A remoção é feita **só** por `etl_admin.tce_pb_replace_bucket` (SECURITY
  DEFINER, [`sql/46`](../../sql/46_tce_pb_bucket_replace.sql)). O role
  `etl_incremental` continua **sem `DELETE`** nas tabelas alvo (P1). A função
  tem allowlist de tabelas (coluna de escopo e chave "gêmeo" fixas no código)
  e guardas:
  - **G1 escopo**: toda linha do arquivo pertence ao bucket
    (`despesa.ano_arquivo` / `receita.ano`).
  - **G2 paridade**: todo hash do arquivo existe no target após o upsert —
    prova que hash calculado == hash do trigger. Se divergir, o replace
    apagaria linhas válidas; aborta.
  - **G3 órfãos**: linhas removidas **sem gêmeo** (mesmo empenho
    `municipio+codigo_ug+numero_empenho+data_empenho` / mesma receita
    `municipio+codigo_ug+mes_ano+codigo_receita` ainda presente) ≤
    `max(2000, 1% do bucket)`. Pega arquivo truncado/errado. O conjunto de
    gêmeos vem das linhas **mantidas** do target, não do chamador.
  - **G4**: arquivo sem linhas nunca remove nada — e, em spec com replace,
    arquivo vazio/placeholder HTML/só cabeçalho é **falha**, não "sucesso sem
    linhas".
  - **G5** (loader): replace exige o arquivo completo. Specs com replace **não**
    desviam linhas com NK declarativa NULL para a DLQ (o `ON CONFLICT` usa só o
    `_nk_md5`, que tolera NULL): `despesas-2023` tem ~7k linhas com
    `municipio`/UG vazios e `receitas` tem `valor='0'` (vira NULL) — desviadas,
    as cópias delas no banco seriam removidas.
  - Os hashes do arquivo entram na função como **dado** (`TEXT[]`,
    materializado pelo chamador no próprio contexto), nunca como relação:
    qualquer relação do chamador lida dentro da função SECURITY DEFINER (view,
    policy, `CHECK`/índice parcial com função do chamador) executaria código
    dele com os privilégios do dono.
- Toda linha removida vai inteira para `<tabela>_removido` (com
  `removido_run_id`, `removido_bucket`, `removido_motivo` =
  `versao_substituida` | `ausente_no_arquivo`). Restauração:
  [ops.md](../ops.md#runbook-restaurar-linhas-removidas-pelo-replace-tce-pb).
- Replace roda só com arquivo **recém-baixado**: specs com replace sempre
  re-baixam (sem 304) e, se o download falha, o bucket é pulado (nunca
  substitui a partir de cache possivelmente velho).
- Bucket com replace que não aplica (guarda, download falho, dry-run, sucesso
  sem `replace_stats`) faz o runner sair com erro. O `deploy.yml` guarda o
  código, refresca as MVs **e aquece o cache** dos buckets que comitaram, e só
  falha o job no último step ("Propagar falha do incremental") — MVs e cache
  ficam consistentes com as tabelas base.
- `ETL_REPLACE_DRY_RUN=1` calcula as estatísticas e faz rollback (uso manual).

`tce_pb_servidor` e `tce_pb_licitacao` continuam acumulativos: excesso medido
≈ 0 (servidor) e 124 linhas em 2026 (licitação) — follow-up se crescer.

## Consequences

### Positivas

- Totais do site deixam de ser inflados e passam a acompanhar a publicação
  vigente do TCE-PB (pagamentos que avançam, correções).
- Idempotente: re-rodar o mesmo arquivo é no-op; o primeiro run em cada ano
  também limpa o legado do ETL clássico + reprocessamento de 07/2026.
- Reversível: backup completo por run.
- Viabiliza o agendamento automático (`incremental-schedule.yml`) sem
  reacumular duplicatas a cada ciclo.

### Negativas / custos

- `_nk_md5`/`id` das linhas editadas mudam a cada publicação (o `id` não é
  exposto em URL pública — ADR-0012 ainda é Proposed).
- Backup cresce ~versões substituídas por ciclo. Limpeza inicial: ~12,5M
  linhas (~17 GB) em `tce_pb_despesa_removido`. Pode ser podado após 90 dias
  (`DELETE … WHERE removido_em < now() - interval '90 days'`).
- Bucket processado inteiro a cada execução (download forçado + scan do ano).
  ~40 min por ano de despesa no B4.

### Validação

- 19 testes (`tests/incremental/test_tce_pb_bucket_replace.py`, Postgres 16
  real com `sql/19`+`42`+`46`).
- E2E local com o runner real e `despesas-2026` publicado (1.984.953 linhas):
  carga inicial e re-run idêntico com G2 OK e 0 remoções; com 93.177 versões
  antigas + 521 empenhos inexistentes injetados, removeu exatamente esses
  (`versao_substituida`/`ausente_no_arquivo`) e não tocou 2025; download
  corrompido ("not a zip") → bucket pulado, runner com erro, nada alterado.
- Revisão: 3 agentes em 3 rodadas; achados (NK NULL, relação do chamador lida
  em SECURITY DEFINER, buraco de mês BF, warm após falha parcial, arquivo
  vazio) corrigidos.

## Alternatives considered

- **Hash só de chave lógica + `UPSERT_DO_UPDATE`**: rejeitada — ADR-0014
  mostrou que não há NK lógica única (1037 colisões reais em despesa); usar uma
  chave "quase única" perderia registros distintos.
- **`TRUNCATE`/`DELETE` do ano + reload**: rejeitada — janela em que o ano
  fica vazio ou com contagem parcial para o site (MVCC esconde dentro da
  transação, mas reescreve 100% das linhas e índices a cada ciclo, inclusive as
  que não mudaram); sem guarda natural contra arquivo truncado.
- **Dedupe periódico por SQL** (manter a versão de maior `id` por empenho):
  rejeitada — não distingue versão velha de registro legítimo distinto (mesmo
  problema da NK natural) e trata o sintoma, não a causa.

## References

- Issue #211 (medição), ADR-0004, ADR-0014
- `sql/46_tce_pb_bucket_replace.sql`, `etl/incremental/replace.py`
- `tests/incremental/test_tce_pb_bucket_replace.py`
- `.github/workflows/incremental-schedule.yml`
