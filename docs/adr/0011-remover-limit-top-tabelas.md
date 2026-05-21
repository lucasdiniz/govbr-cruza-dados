# ADR-0011: Remover LIMIT 200 / 500 dos top resultados de cidade

## Status

Accepted (parcial) — implementado **apenas para `TOP_SERVIDORES_RISCO` /
`TOP_SERVIDORES_RISCO_DATED`** em 2026-05-20 ([PR #195][pr195]). Demais
LIMITs (queries Q## em `registry.py` e outras top-tabelas em `cidade.py`)
continuam **Proposed** e serão tratados em PRs subsequentes, caso-a-caso.

[pr195]: https://github.com/lucasdiniz/govbr-cruza-dados/pull/195

## Date

2026-05-17 (proposta original)
2026-05-20 (aceitação parcial — servidores)

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

`Proposed` (para os escopos não implementados — Q## em `registry.py` e
outras top-tabelas em `cidade.py`). Ver "Implementação parcial" abaixo
para o que já foi aceito em [PR #195][pr195].

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

## Implementação parcial (2026-05-20) — TOP_SERVIDORES_RISCO

**Escopo aceito**: apenas `TOP_SERVIDORES_RISCO` e `TOP_SERVIDORES_RISCO_DATED`
em `web/queries/cidade.py:805`. Os demais LIMITs listados na tabela acima
**continuam em vigor** e serão tratados em PRs separadas, caso-a-caso,
quando houver demanda concreta de produto.

Entregue em [PR #195 — feat(web): servidores sem LIMIT + filtros][pr195]:

- **LIMIT removido** de `TOP_SERVIDORES_RISCO` em `web/queries/cidade.py`.
  Variante `_DATED` herda automaticamente via `.replace()`.
- **Sizing real** (medido na VM em 2026-05-20, não 13k como estimado):
  - João Pessoa: **51.573 servidores** (~30MB de HTML SSR sem limit).
  - Campina Grande: 32.035; Santa Rita: 12.360; Bayeux: 9.978.
  - Mediana das 223 munis PB: 855 servidores.
  - `mv_servidor_pb_risco` total: 358.651 rows.
- **Decisão "sem LIMIT mesmo assim"**: usuário priorizou completude.
  Paginação client-side existente (`data-table.js`, 10/pag) absorve o volume
  visual; cliente paga em download/parse. Virtual scroll fica como
  follow-up se Lighthouse/mobile reportar regressão.
- **Sort reescrito** (em vez de só `risco_score DESC`):
  1. `flag_ceaf_expulso` (vermelho — expulsão administrativa federal)
  2. `flag_socio_inidoneidade` (vermelho — sócio CEIS Inidoneidade)
  3. `total_pago_durante_vinculo > 0` (vermelho — empresa do servidor
     recebeu durante vínculo)
  4. `flag_bolsa_familia` (amarelo)
  5. `flag_socio_sancionado` (laranja)
  6. `flag_multi_empresa` (amarelo)
  7. `risco_score` (peso composto da MV)
  8. `flag_duplo_vinculo_federal` (apenas tie-breaker — Constituição
     permite acumulação em alguns casos; não é "fraude" por si só).

  Motivação: João Pessoa estava com 20 páginas dominadas por médicos
  com duplo vínculo (saúde + município), enterrando sinais de fraude
  reais (CEAF, sócio sancionado, pagamentos durante vínculo).

- **Filtros por flag** (chips): UI permite ao usuário fatiar livremente.
  Chips disponíveis: CEAF, Inidoneidade, "Empresa recebeu durante vínculo",
  Bolsa Família, Sócio sancionado, Multi-empresa, Salário alto + sócio,
  Vínculo SIAPE. Semantica **OR** dentro do grupo (row visível se
  combina ≥1 chip ativo). Chip `duplo_vinculo_estadual` foi
  explicitamente excluído (decisão de UX: não enfatizar o sinal de
  duplo vínculo, que tem hipóteses constitucionais permitidas).

- **Eventos Umami**: `servidores-filtro-toggle` ({flag, action, ativos,
  qtd_ativos, visiveis, total}) + `servidores-filtro-limpar`. Padrão
  kebab-case sem prefixo de página, alinhado com memory de Umami event
  naming. Permite medir adoção dos filtros e quais flags os usuários
  efetivamente usam.

- **Expandable de regras de acumulação**: servidor-dialog agora renderiza
  `details[data-duplo-vinculo-regras]` quando há vínculo municipal +
  federal SIAPE, com dual-mode citizen/auditor citando CF/88 Art. 37 XI
  e XVI, EC 19/98, EC 34/2001, Lei 8.112/90 Art. 132 e teto do STF (MP
  1.230/2024). Reusa CSS `.bf-regras-info` e padrão de evento Umami
  `secao-toggle` com `section='duplo-vinculo-regras'`.

- **Warm cache impact**: TOP_SERVIDORES_RISCO já era warm; sem LIMIT
  o tamanho do payload por key cresce ~250× em JP. Não foi medido em
  prod ainda — follow-up se warm cycle aumentar significativamente.
  Não muda CACHE_DEPENDENCY_GRAPH.

### Próximos passos (continuam Proposed — não entregues no PR #195)

Nada abaixo foi implementado ainda. PRs futuras devem revisitar este ADR:

- LIMITs em `cidade.py:289`, `:393`, `:512`, `:614` (outras agregações de
  top-tabelas, ainda com `LIMIT 200` hardcoded).
- LIMIT 500 nas ~30 queries Q## em `web/queries/registry.py`
  (linhas 169-849).
- Aplicar o mesmo padrão de chips de filtro + ordenação por sinais reais
  em top-fornecedores e demais top-tables.
- Considerar virtual scroll se mobile Lighthouse regredir > 10% após PR
  #195 estar em produção.
