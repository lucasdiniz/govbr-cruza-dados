# ADR-0003: Shadow rewarm com `__pending` swap atômico

## Status

Accepted

## Date

2025-01-20

## Context

A tabela `web_cache` armazena resultados pré-computados das queries em
[`web/queries/registry.py`](../../web/queries/registry.py). Cada linha tem
`(query_id, params_hash) → JSONB`. O warm leva **12–18 horas** para preencher
todas as queries de todos os municípios PB.

Mudanças em `registry.py` (ex.: correção de bug na Q65, nova versão da Q67 com
filtro de data) **invalidam o cache existente** para essas queries. Workflow
ingênuo:

```
DELETE FROM web_cache WHERE query_id = 'Q65';
-- start warm
```

Durante todo o warm (horas) as rotas que dependem de Q65 retornam **cache miss
→ query live (timeout) → 503**. Inaceitável.

Caminhos considerados:

1. **Aceitar downtime durante warm** — descartado, viola SLA do site público.
2. **Warm em outra tabela `web_cache_v2`** e switch via config — exige restart
   do app + manutenção de duas tabelas em paralelo + risco de drift de schema.
3. **Shadow rewarm com sufixo no `query_id`** — manter live + pending na mesma
   tabela, diferenciados por sufixo, swap atômico no fim. Sem restart. Sem
   tabela duplicada.

## Decision

Pattern `rewarm_cache_keys` implementado em
[`web/warm_cache.py`](../../web/warm_cache.py):

### Fluxo

1. Warm escreve em `<qid>__pending` — sufixo aplicado na coluna `query_id`
   (`Q65` → `Q65__pending`).
2. **Live rows continuam servindo** durante o warm (rotas leem `Q65`, ignoram
   `Q65__pending`).
3. Ao final do warm:
   - **Se 100% sucesso (fail == 0)**: swap atômico em transação única:
     ```sql
     DELETE FROM web_cache WHERE query_id = 'Q65';
     UPDATE web_cache SET query_id = 'Q65' WHERE query_id = 'Q65__pending';
     ```
   - **Se qualquer query falhou**: ABORT — descarta todo o `__pending`, mantém
     live antigo intacto.

### Auto-expansão de dependências

Algumas chaves disparam expansão automática para evitar deploys parciais:

- Shadow de prefixos `PERFIL`, `TOP_FORN`, `TOP_SERV` → inclui automaticamente
  `KPI_SUMMARY` (que depende deles).

### Match semantics — **exato de qid ou base**, não substring

Para evitar matches espúrios em chaves compostas:

- `PERFIL` casa: `PERFIL`, `ANO:PERFIL`, `ANO_MES:PERFIL`
- `PERFIL` **NÃO** casa: `EMPRESA_PERFIL`, `PERFILADO`

O matcher quebra o `query_id` em segmentos por `:` e compara o último segmento
contra a chave fornecida (igualdade estrita).

## Consequences

### Positive

- **Zero downtime** em rewarms operacionais.
- **Abort preserva live** — warm parcial nunca corrompe produção.
- **Auto-expansão** evita esquecer dependências (esquecer `KPI_SUMMARY` ao
  reaquecer `PERFIL` daria UI inconsistente).
- Swap é uma única transação curta → janela de inconsistência de milissegundos.

### Negative / Trade-offs

- Durante o warm, `web_cache` **dobra de tamanho** (~30–50 GB extras).
- Complexidade em `warm_cache.py` (~1700 linhas) — matching, expansão, swap,
  abort, retry, logging.
- Política de abort é **estrita demais**: 1 query que falha aborta tudo,
  mesmo quando 999 outras passaram. Pode atrasar deploys quando há flakiness
  em uma única query.
- Operacional: se o cron noturno falha em uma query intermitente, o live
  fica antigo até o próximo run — não há recovery parcial.

### Mitigations

- **Storage Postgres é commodity** no setup atual (disco Azure managed
  expansível); o pico durante o warm é aceitável.
- Warm roda em **janela de baixo tráfego** (cron 03h BR).
- Abort emite **log claro com a query culpada** + count de sucessos —
  diagnosticar e re-rodar é direto.
- O workflow `deploy.yml` aceita `rewarm_cache_keys` como input, permitindo
  rewarm cirúrgico (só `Q65`, por exemplo) sem refazer as 12 h inteiras.

## Related

- Code: [`web/warm_cache.py`](../../web/warm_cache.py)
  (`rewarm_cache_keys`, `_swap_pending_to_live`, `_expand_keys`).
- Other ADRs: [ADR-0002](0002-mv-layered.md) (MVs alimentam o cache).
- Workflow:
  [`.github/workflows/deploy.yml`](../../.github/workflows/deploy.yml) (input
  `rewarm_cache_keys`).
- Docs: `docs/cache.md` (a ser criado) detalha o ciclo de vida do
  `web_cache` e operação do rewarm.
