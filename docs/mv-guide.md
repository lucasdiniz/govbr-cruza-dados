# MV guide — adicionando uma materialized view

Este guia cobre o trabalho prático em [`sql/12_views.sql`](../sql/12_views.sql) (1500+ linhas). Para overview das camadas, ver [architecture.md](architecture.md). Para queries que consomem MVs, ver [queries-guide.md](queries-guide.md).

## Camadas

As MVs são organizadas em **três camadas** com dependências estritas:

```mermaid
flowchart TD
    subgraph base["Tabelas base (ETL phases 1-17)"]
        e[empresa / estabelecimento]
        s[socio]
        tcd[tce_pb_despesa]
        tcl[tce_pb_licitacao]
        srv[tce_pb_servidor]
        pncp[pncp_contrato]
        emenda[emenda_favorecido]
        cpgf[cpgf]
        ceis[ceis / cnep / inidoneo]
        pgfn[pgfn]
    end

    subgraph L1["L1 — MVs independentes"]
        meg[mv_empresa_governo]
        mpb[mv_pessoa_pb]
        mmr[mv_municipio_pb_risco]
        msb[mv_servidor_pb_base]
    end

    subgraph L2["L2 — MVs derivadas"]
        msr[mv_servidor_pb_risco]
        mep[mv_empresa_pb<br/>+ _tmp_* backing]
        mrp[mv_rede_pb]
        mks[mv_municipio_pb_kpi_score]
        mmp[mv_municipio_pb_mapa]
        mq67[mv_q67_dated_pb]
    end

    subgraph L3["L3 — Views planas (sem materialização)"]
        vre[v_risk_score_empresa]
        vrp[v_risk_score_pb]
    end

    e --> meg
    pncp --> meg
    emenda --> meg
    cpgf --> meg
    ceis --> meg
    pgfn --> meg

    s --> mpb
    e --> mpb

    tcd --> mmr
    tcl --> mmr
    srv --> mmr

    srv --> msb

    msb --> msr
    mpb --> msr

    meg --> mep
    mmr --> mep
    s --> mep

    mep --> mrp
    mpb --> mrp

    mmr --> mks
    meg --> mks

    mks --> mmp

    tcd --> mq67
    pgfn --> mq67

    mep --> vre
    mmr --> vrp
    mks --> vrp
```

> **L2 silenciosamente quebra** se uma MV L1 mudar de coluna sem propagar. A fase 18 ([`etl/21_views.py`](../etl/21_views.py)) executa o arquivo inteiro em ordem — um CREATE quebrado aborta o resto.

## Atualizando UMA MV existente (atomic swap zero-downtime)

> 🟢 **Default para qualquer mudança de definição de UMA MV.** Use `mv_swap` em vez de `etl_phase=sql`. A diferença prática é ~1s vs ~1-2h de downtime parcial, e `etl_phase=sql` é não-cancelável uma vez que o `DROP CASCADE` rodou (ver "Quando NÃO usar" abaixo).

`etl/mv_swap.py` permite atualizar a definição de UMA MV (incluindo schema/colunas novas) com **downtime de ~1s**, sem dropar as outras MVs do `sql/12_views.sql`. Reutilizável pra qualquer MV.

**Quando usar:**
- Correção pontual de query/CTE de UMA MV (ex: adicionar EXISTS guard contra CPF padded).
- Mudança de schema: adicionar coluna, alterar tipo, renomear coluna.
- Qualquer mudança onde `REFRESH MATERIALIZED VIEW` não basta porque a definição mudou.

**Quando NÃO usar:**
- Refresh periódico de dados (use `REFRESH MATERIALIZED VIEW CONCURRENTLY`).
- Mudanças em múltiplas MVs simultaneamente que se referenciam (use `etl_phase=sql` — único caso legítimo).

> ⚠️ **`etl_phase=sql` é destrutivo e não-cancelável.** O `etl.21_views` executa `sql/12_views.sql`, cujos primeiros ~12 statements são `DROP MATERIALIZED VIEW ... CASCADE` pra **todas** as MVs. Durante ~1-2h, `pg_matviews` fica vazio; cancelar o deploy nesse intervalo deixa o banco sem MVs e o site quebra em paths que dependem delas. Sempre prefira `mv_swap` pra mudanças pontuais.

**Mecânica** (detalhes em [`../etl/mv_swap.py`](../etl/mv_swap.py)):

1. Build paralelo (autocommit): `CREATE MATERIALIZED VIEW <mv>_swap AS …`. Tráfego live continua na MV original.
2. Snapshot recursivo de dependentes via `pg_depend`/`pg_rewrite` + `pg_get_viewdef`.
3. Transação atômica (~1s): `DROP MATERIALIZED VIEW <mv> CASCADE` + `ALTER MV <mv>_swap RENAME TO <mv>` + recreate de dependentes.
4. `REFRESH MATERIALIZED VIEW` em MVs dependentes (fora de tx).

**Passos pra atualizar uma MV:**

1. **Crie `deploy/mv_updates/<mv_name>.sql`** com a nova definição usando sufixo `_swap` em todos os identifiers:

   ```sql
   CREATE MATERIALIZED VIEW mv_empresa_pb_swap AS
   WITH ... SELECT ...;

   CREATE UNIQUE INDEX idx_mv_epb_cnpj_swap ON mv_empresa_pb_swap(cnpj_basico);
   CREATE INDEX idx_mv_epb_inativa_swap ON mv_empresa_pb_swap(...) WHERE ...;
   ```

   O framework remove o sufixo `_swap` dos identifiers após o swap. Todos os indexes da MV original devem ter equivalente `_swap`.

2. **Atualize `sql/12_views.sql`** com a mesma definição. O swap altera a MV em prod imediatamente; o `sql/12_views.sql` garante que o próximo full rebuild reflita o fix.

3. **Teste local**:
   ```bash
   python -m etl.mv_swap mv_empresa_pb deploy/mv_updates/mv_empresa_pb.sql
   ```

4. **Deploy via workflow**:
   ```bash
   gh workflow run deploy.yml --ref main \
     -f etl_phase=web \
     -f mv_swap=mv_empresa_pb \
     -f rewarm_cache_keys=EMPRESA_PERFIL,EMPRESA_PERFIL_MUN
   ```

   `mv_swap` aceita múltiplas MVs em CSV. Roda APÓS ETL phase, ANTES do warm. Pode ser combinado com `etl_phase=web` pra evitar VM resize.

**Limitações:**

- Durante o REFRESH pós-swap, MVs dependentes ficam vazias temporariamente. Pra MVs que alimentam fluxo crítico, prefira aplicar guard no SQL source e rodar `etl_phase=sql` em janela de baixo tráfego.
- A transação swap requer `ACCESS EXCLUSIVE` (vem do `DROP MATERIALIZED VIEW`); se houver query lenta concorrente lendo a MV, o swap aguarda. Considere `lock_timeout` se isso for crítico.

## Convenções do `sql/12_views.sql`

1. **DROP no topo** em ordem reversa de dependência (views planas → L2 → L1).
2. **CREATE por camadas** depois dos DROPs (L1 primeiro, depois L2, depois views).
3. `REFRESH MATERIALIZED VIEW CONCURRENTLY` exige `UNIQUE INDEX` na MV. Sem isso, falha em runtime.
4. **Notas de refresh** no rodapé do arquivo (linhas 1465+) — lista a ordem operacional dos REFRESH em produção.

Exemplo real do topo do arquivo:

```sql
-- Drop em ordem reversa de dependência
DROP VIEW IF EXISTS v_risk_score_pb CASCADE;
DROP VIEW IF EXISTS v_risk_score_empresa CASCADE;
DROP MATERIALIZED VIEW IF EXISTS mv_rede_pb CASCADE;
DROP MATERIALIZED VIEW IF EXISTS mv_empresa_pb CASCADE;
DROP MATERIALIZED VIEW IF EXISTS mv_servidor_pb_risco CASCADE;
DROP MATERIALIZED VIEW IF EXISTS mv_servidor_pb_base CASCADE;
-- ... (L1 por último)
DROP MATERIALIZED VIEW IF EXISTS mv_empresa_governo CASCADE;
```

## Adicionando uma MV nova — checklist

1. **Decida a camada** olhando as deps (L1 se só toca tabelas base; L2 se lê outra MV; view plana se for projeção barata).
2. **Adicione `DROP MATERIALIZED VIEW IF EXISTS <nome> CASCADE`** no bloco de DROPs, **respeitando a ordem reversa** (mais derivada primeiro).
3. **Escreva o `CREATE MATERIALIZED VIEW`** na seção correspondente (L1 / L2 / Views).
4. **Crie `UNIQUE INDEX`** logo após o CREATE se quiser permitir `REFRESH ... CONCURRENTLY`:
   ```sql
   CREATE UNIQUE INDEX mv_minha_nova_pk
       ON mv_minha_nova (cnpj_basico, municipio);
   ```
5. **Índices auxiliares** para joins/filtros frequentes (não-unique).
6. **Atualize o bloco de refresh notes** no rodapé do arquivo (~linha 1465) adicionando a linha:
   ```sql
   --   REFRESH MATERIALIZED VIEW CONCURRENTLY mv_minha_nova;
   ```
7. **Atualize consumidores** em [`web/queries/registry.py`](../web/queries/registry.py) e em `queries/*.sql` que dependerem da MV nova.
8. **Verifique `etl/21_views.py`** — ele executa `sql/12_views.sql` inteiro; nenhuma mudança Python é necessária a menos que você adicione uma _tmp table backing (ver abaixo).
9. **Atualize o diagrama** neste doc + o diagrama de MVs em [architecture.md](architecture.md).

## Performance: REFRESH CONCURRENTLY vs plain

| Modo | Lock | Tempo | Quando usar |
|---|---|---|---|
| `REFRESH ... CONCURRENTLY` | `ShareUpdateExclusive` (não bloqueia leitura) | ~2× (escreve nova cópia + reindex) | Padrão em prod — UI continua servindo |
| `REFRESH ...` (plain) | `AccessExclusive` (bloqueia tudo) | ~1× | Bootstrap inicial; mudança de schema |

`CONCURRENTLY` exige UNIQUE INDEX. Sem ele, escolha está feita: você só pode dar refresh plain (com downtime de leitura).

## Tabelas `_tmp_*` backing

Quando uma MV agrega muitas fontes e o SELECT inicial dá timeout, o padrão é usar tabelas auxiliares **`_tmp_<algo>`** povoadas antes do CREATE da MV. Exemplo em `mv_empresa_pb` (linhas ~664+). Caveat citado no próprio arquivo:

```sql
-- Na próxima execução, o CASCADE no DROP MATERIALIZED VIEW libera as _tmp tables,
-- mas elas precisam ser recriadas/povoadas antes do CREATE MATERIALIZED VIEW.
```

Se adicionar uma _tmp backing, documente no comentário acima do CREATE quem a popula (geralmente uma função em `etl/21_views.py` antes de chamar o `execute_sql_file`).

## Caveats

- **Tamanho do arquivo:** 1500+ linhas. Qualquer mudança exige ler a ordem inteira de DROP/CREATE antes de inserir. Use grep para localizar:
  ```bash
  grep -n 'MATERIALIZED VIEW\|CREATE OR REPLACE VIEW' sql/12_views.sql
  ```
- **Drift Python ↔ SQL:** [`web/kpis/municipio_pb.py:sql_score_expression()`](../web/kpis/municipio_pb.py) define a expressão de score em Python, mas `mv_municipio_pb_risco` materializa essa mesma lógica em SQL inline. Mudanças precisam ser feitas **nos dois lugares** — `TODO.md` registra o drift como dívida técnica.
- **L2 perde dep silenciosamente:** se você renomear coluna em L1 e esquecer L2, fase 18 falha tarde no pipeline. Rode `python -m etl.run_all 23` localmente após qualquer mudança em MV (`23` é a posição 1-based da Fase 18 Views na lista `phases` — ver [deploy.md](deploy.md)). Alternativamente, use `etl_phase=sql` no workflow que executa só índices + normalização + views.
- **`REFRESH CONCURRENTLY` precisa de espaço em disco** equivalente ao tamanho da MV (escreve cópia inteira antes de swap). Em VMs com disk-pressure, plain refresh pode ser preferível.
- **CASCADE** nos DROPs propaga para views planas e índices — saudável, mas exige recriação completa.

## Relacionados

- [architecture.md](architecture.md) — diagrama macro das camadas + ERD.
- [cache.md](cache.md) — `web_cache` lê queries que dependem de MVs; mudança de MV requer rewarm para evitar cache stale.
- [queries-guide.md](queries-guide.md) — quando uma Q## lenta deve virar MV.
- [`etl/21_views.py`](../etl/21_views.py) — phase 18 que aplica `sql/12_views.sql`.
