# ADR-0011: Remover LIMIT 200 / 500 dos top resultados de cidade

## Status

Proposed

## Date

2026-05-17

## Context

Várias queries do frontend (`web/queries/cidade.py`, `web/queries/registry.py`)
truncam resultados com `LIMIT N`:

| Local | Limit | Comentário inferido |
|-------|------:|---------------------|
| `web/queries/cidade.py:289` | 200 | Top servidores PB / agregação |
| `web/queries/cidade.py:393` | 200 | Idem |
| `web/queries/cidade.py:512` | 200 | Idem |
| `web/queries/cidade.py:614` | 200 | Idem |
| `web/queries/cidade.py:805` | 200 | **TOP_SERVIDORES_PB — alvo principal** |
| `web/queries/registry.py:169-849` | 500 | ~30 queries Q## (fornecedores sancionados, vínculos, etc) |

Motivações históricas (inferidas):

1. **Performance early-stage**: queries pesadas (Q##) sem MVs específicas
   timeoutavam com cidades grandes (João Pessoa, Campina Grande). LIMIT
   conteve dano.
2. **Warm cache scale**: `web/warm_cache.py` precisava cachear N munícipios
   × M queries. Com LIMIT, o universo cacheado é controlável.
3. **UX tabela paginada inexistente**: frontend renderiza tudo em uma
   página. Sem virtual scroll / paginação real, 5000+ rows quebraria UX.

**Limitação atual**: a intenção do produto é **listar todos os servidores
PB de uma cidade**, não apenas top 200. Cidades pequenas (~700 munícipios
do estado têm <200 servidores TCE-PB cadastrados) já são cobertas
completamente; mas João Pessoa (~13k servidores) só mostra 200 no UI.

## Decision (proposed)

Remover progressivamente os LIMITs hardcoded, começando por
`web/queries/cidade.py:805` (TOP_SERVIDORES_PB) como caso piloto.

### Plano de execução (PR futura)

1. **Caso piloto**: `web/queries/cidade.py:805`
   - Substituir `LIMIT 200` por LIMIT configurável via `web/config.py`
     (`SERVIDORES_PB_LIMIT`, default = `None` = sem limit).
   - Validar performance: rodar query sem limit contra João Pessoa,
     Campina Grande, Santa Rita (top 3 PB por volume). Medir P95.
   - Se P95 > 30s, criar MV específica `mv_servidores_pb_cidade` agregando
     o necessário com índices apropriados.

2. **Frontend**: implementar paginação real ou virtual scroll
   (`web/templates/results/cidade.html` na seção de servidores).
   Sem isso, response de 5000+ rows quebra layout.

3. **Warm cache strategy** — DEPENDÊNCIA CRÍTICA:
   - Hoje, `web/warm_cache.py` cacheia top-200 servidores por cidade.
   - Removendo LIMIT, cachear todos os 13k servidores × ~70 cidades
     ativas = ~900k keys. Tempo de warm cresceria proporcionalmente.
   - **Alternativas a avaliar**:
     - **Lazy warm**: só cachear servidor quando hit no endpoint
       (`/api/servidor/detalhes`). Cache miss = compute on-demand. ADR-0010
       já adota essa estratégia para o sub-bloco BF.
     - **Top-N warm**: continuar warm dos top-200 (cobertura "popular"),
       cache miss em outros = compute on-demand.
     - **Full warm seletivo**: warm só de servidores em cidades > N
       habitantes, lazy nas pequenas.

4. **Endpoint `/api/servidor/detalhes` BF cache** (interage com ADR-0010):
   - ADR-0010 implementou cache **in-memory** justamente porque o
     universo dependeria de LIMIT futuro. Quando este ADR for executado,
     revisitar:
     - Se ficar lazy warm: ok, in-memory já casa.
     - Se ficar full warm: migrar para `web_cache` persistente via
       padrão `_upsert` (igual `EMPRESA_PERFIL`).

5. **Queries Q## em `registry.py`** (LIMIT 500):
   - Avaliar caso-a-caso. Algumas queries (Q65, Q77) já estouraram
     timeout em cidades grandes (memória do CLI). Remover LIMIT pode
     reintroduzir 504.
   - Prioridade: queries onde "ver mais" é semanticamente útil
     (fornecedores sancionados, sócios laranjas).

## Status

`Proposed` — depende de decisão arquitetural sobre warm cache strategy
e implementação de paginação real no frontend. Não bloqueia o ETL
incremental BF (ADR-0010).

## Quando implementar

Quando alguma das condições se materializar:

1. Reclamação concreta de usuário sobre "não vejo todos os servidores".
2. Auditoria/relatório pede top-N > 200 (já aconteceu informalmente:
   investigação em João Pessoa precisava top-1000 servidores por
   suspeita de fraude em folha).
3. Tempo de warm cache cair muito (>3h) e justificar refator geral
   da estratégia.

## Trade-offs

### Pro (remover LIMIT)
- **Completude**: todos os servidores listados, sem perder cauda longa.
- **Auditoria**: relatórios podem citar todos os ~13k servidores de JP
  sem ter que rodar query ad-hoc.
- **Consistência**: cidades pequenas e grandes têm comportamento idêntico
  no UI (hoje JP "esconde" rows; Santa Rita mostra tudo).

### Contra
- **Warm cache cresce N×**: estratégia precisa ser repensada.
- **Frontend precisa paginação real**: virtual scroll ou infinite scroll.
  Sem isso, payload de ~5000 rows quebra mobile.
- **Queries pesadas precisam revisão de índices/MVs**: Q## específicas
  podem reintroduzir 504. Cuidadoso testing por cidade.

## References

- ADR-0010 — depende da estratégia de warm cache definida aqui.
- `web/queries/cidade.py:805` — primeiro alvo, caso piloto.
- Memória sessão 2026-05-17: usuário pediu "incluir nessa plano um ADR
  para uma proxima PR para tirar esse LIMIT de servidores e possivelmente
  de outras tabelas tambem".
