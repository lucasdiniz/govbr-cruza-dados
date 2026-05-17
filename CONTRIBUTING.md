# Contribuindo com o govbr-cruza-dados

Obrigado por considerar contribuir. Este projeto cruza ~350M registros de ~18 fontes públicas brasileiras para detectar indícios de fraude em licitações, emendas parlamentares, sanções e folha de pagamento, e alimenta o portal público [transparenciapb.org](https://transparenciapb.org). Toda contribuição é bem-vinda — desde correções de typo em relatório até queries novas, melhorias de UI e migrações de novas fontes para o ETL incremental.

Este documento descreve o que precisa para contribuir. Para entender a arquitetura, comece pelo [README.md](README.md).

## Sumário

- [Idioma](#idioma)
- [Tipos de contribuição](#tipos-de-contribuição)
- [Setup local](#setup-local)
- [Convenções do código](#convenções-do-código)
- [Convenções de SQL e queries Q##](#convenções-de-sql-e-queries-q)
- [Convenções de relatórios](#convenções-de-relatórios)
- [Convenções de commits e PRs](#convenções-de-commits-e-prs)
- [Checklist de PR](#checklist-de-pr)
- [Contribuindo com agentes de IA](#contribuindo-com-agentes-de-ia)
- [O que você pode tocar / pode não tocar](#o-que-você-pode-tocar--pode-não-tocar)
- [Onde pedir ajuda](#onde-pedir-ajuda)

## Idioma

O idioma de trabalho é **português brasileiro**: identificadores, comentários, SQL, títulos de queries, nomes de relatórios, mensagens de commit, descrições de PR e issues. Mantenha esse padrão para preservar consistência.

Mensagens de erro internas e logs também são em PT-BR. Strings voltadas ao usuário final (frontend `web/`) seguem a mesma regra — a UI inteira é PT-BR e não há infraestrutura de i18n no momento.

## Tipos de contribuição

Três caminhos principais, em ordem de complexidade crescente:

### A. Documentação, glossário, novos relatórios markdown

Mexe apenas em `README.md`, `docs/`, `relatorios/`, comentários inline. Geralmente **não exige rodar Postgres nem o ETL**.

- Se o relatório novo cita CNPJs ou CPFs reais, rode o validador antes de abrir o PR:
  ```bash
  python scripts/audit_report_identifiers.py --strict       # offline — checa só CPFs não-mascarados
  ```
  Em modo `--strict` o script roda sem banco de dados e retorna exit 1 se encontrar qualquer CPF formatado completo (`NNN.NNN.NNN-NN`) sem máscara. O padrão canônico do projeto é `***.NNN.NNN-**` (mantém só os 6 dígitos centrais, igual ao `cpf_digitos_6` das MVs).
- Para validar CNPJs contra a base RFB local (requer Postgres com `empresa` + `estabelecimento` carregados, ~58GB de RFB), rode sem `--strict`:
  ```bash
  python scripts/audit_report_identifiers.py --report relatorios/seu_relatorio.md
  ```

### B. Queries SQL (Q##), MVs, índices

Mexe em `queries/*.sql`, `sql/12_views.sql`, `sql/19_indices_queries.sql`, eventualmente `web/queries/registry.py` para expor no frontend. **Exige Postgres com schema carregado** — não necessariamente todos os ~210GB de dados, mas pelo menos os schemas das tabelas relevantes (`tce_pb_*`, `pb_*`, `empresa`, `socio`, etc.).

Não há ainda um caminho 100% "schema-only sem dados" pronto (P0 da nossa lista de melhorias) — por ora a forma mais simples é rodar o ETL para o subset de fontes que sua query usa, ou pedir um snapshot reduzido nos comentários do issue.

### C. ETL, infraestrutura, deploy, frontend completo

Mexe em `etl/`, `etl/incremental/`, `web/` em mais profundidade, `sql/` schemas novos, `deploy/`. Em geral exige toda a stack rodando: Postgres 16, ETL completo (ou parcial via `etl_phase=N`), e potencialmente acesso à VM de produção para `deploy/`.

Contribuições em `deploy/`, `.github/workflows/` e scripts `setup-*.sh` só podem ser validadas pelo mantenedor (precisa do runner self-hosted Azure). Sinta-se à vontade para abrir PR mesmo assim — só esteja ciente de que o teste real só acontece no merge.

## Setup local

```bash
# 1. Clone e instale
git clone https://github.com/lucasdiniz/govbr-cruza-dados
cd govbr-cruza-dados

# 2. Python 3.10+ com extras dev (pytest) e web (FastAPI, uvicorn, jinja2, pillow, markdown)
pip install -e .[web,dev]

# 3. Node.js >= 20 para o build pipeline de assets do frontend
npm ci

# 4. Variáveis de ambiente
cp .env.example .env
# Edite com credenciais do PostgreSQL e DATA_DIR

# 5. Postgres 16 — instalação direta é o padrão do projeto (a VM de produção
#    também roda Postgres direto, sem Docker). Em desenvolvimento, instale via
#    apt / Homebrew / instalador Windows e crie o banco:
sudo -u postgres psql -c "CREATE USER govbr WITH PASSWORD 'govbr_dev';"
sudo -u postgres psql -c "CREATE DATABASE govbr OWNER govbr;"

# Extensões obrigatórias — habilitar uma vez por banco:
sudo -u postgres psql -d govbr -c \
    "CREATE EXTENSION IF NOT EXISTS pg_trgm; CREATE EXTENSION IF NOT EXISTS unaccent;"

# Alternativa via Docker (se preferir não instalar Postgres direto):
#   docker run --name govbr-pg -e POSTGRES_PASSWORD=govbr_dev -e POSTGRES_USER=govbr \
#              -e POSTGRES_DB=govbr -p 5432:5432 -d postgres:16
#   docker exec -i govbr-pg psql -U govbr -d govbr -c \
#       "CREATE EXTENSION IF NOT EXISTS pg_trgm; CREATE EXTENSION IF NOT EXISTS unaccent;"

# 6. Smoke (não roda o ETL, só compila):
python -m compileall etl web scripts -q

# 7. Testes do framework incremental (precisam de Postgres com migrations 22-29+32+34+35
#    e roles etl_admin/etl_incremental; a maioria faz pytest.skip se schemas ausentes):
pytest tests/incremental/test_framework_smoke.py     # subset offline
pytest tests/incremental                              # suite completa (precisa Postgres)

# 8. Build do frontend (concat + minify + content-hash → manifest.json):
npm run build

# 9. Rodar o frontend (precisa de cache populado ou MVs criadas — ver caminho B/C acima):
python -m uvicorn web.main:app --port 8000
```

**Caveat conhecido**: o caminho ideal "schema-only sem dados" + `docker-compose.yml` + sample data de 1 município está em desenvolvimento (issues abertos com label `good-first-issue`). Por enquanto, o setup mais leve para mexer em `web/` exige rodar pelo menos parte do ETL.

## Convenções do código

### Python (`etl/`, `web/`, `scripts/`)

- **Sem pandas.** ETL processa dados em streaming linha-a-linha e carrega via `COPY FROM STDIN` (helpers em `etl/db.py`: `copy_from_stream`, `copy_csv_streaming`, `batch_insert`). A máquina-alvo é uma VM Azure B4as_v2 (16GB RAM); DataFrames de centenas de milhões de linhas não cabem.
- **Parsers BR-específicos** em `etl/utils.py` (`parse_date_br`, `parse_decimal_br`, `clean_cpf`, `clean_cnpj`, `extract_cpf_masked`, `normalize_name`). Reuse em vez de reimplementar — cada fonte usa formato diferente e os parsers já cobrem os cantos.
- **Encoding por fonte**:
  - RFB é **latin-1** (use `latin1_lines` em vez de `open(...)`)
  - dados.pb.gov.br é **utf-8** mas com fallback para latin-1 em alguns CSVs
  - Restante das fontes é utf-8
- **Normalização de CPF/CNPJ** acontece na fase 17 (`etl/15_normalizar.py`), criando colunas `cpf_digitos` e `cpf_cnpj_norm` indexadas. Qualquer JOIN cross-source novo deve usar essas colunas (igualdade direta), não LIKE/regex.
- **Identidade de fornecedores**: para queries que cruzam empresa com sócio/fornecedor, use `cpf_cnpj` completo (14 dígitos) em vez de `cnpj_basico` (8 dígitos), e filtre com `EXISTS (SELECT 1 FROM estabelecimento WHERE cpf_cnpj = ...)` para excluir falsos positivos de CPFs que coincidem com o prefixo de algum CNPJ.

### Estilo

Não há linter configurado ainda (P1 da lista de melhorias). Siga PEP 8 leve, mantendo o estilo dos arquivos vizinhos. Quando o `ruff` for adotado, será gradual e não-bloqueante para PRs pré-existentes.

## Convenções de SQL e queries Q##

### Header obrigatório

Toda query em `queries/*.sql` começa com:

```sql
-- Q##: Título curto descrevendo a investigação
```

O parser custom em `etl/run_queries.py:split_sql_statements` usa esse header para separar queries dentro de um mesmo arquivo. **Sem o header, a query não é detectada nem executada.**

Numeração Q## é **global** (não por arquivo). Antes de escolher o próximo número, consulte o inventário em `web/queries/registry.py` e os arquivos `queries/*.sql` — a numeração tem gaps históricos que ficam disponíveis para reuso.

### Performance

- Queries do frontend têm timeout default de **30s** (`QueryDef.timeout_sec` em `web/queries/registry.py`). Se a sua query precisa de mais, ajuste no `_reg(... timeout=45/90)`, mas considere antes:
  - Adicionar índice em `sql/19_indices_queries.sql`
  - Pré-computar via materialized view em `sql/12_views.sql`
- Rode `EXPLAIN ANALYZE` localmente antes do PR. Se demorar > 30s no banco completo, vai dar timeout em produção.

### Registro no frontend

Se sua query deve aparecer na UI (`/cidade/<slug>`), registre-a em `web/queries/registry.py` com `_reg(...)`:

```python
_reg(
    qid="Q199",
    titulo="Título exibido na UI",
    categoria="conflito",         # ver categorias existentes
    sql_full=Q199_SQL,            # versão all-time
    sql_full_dated=Q199_DATED,    # versão filtrável (opcional)
    timeout_sec=30,
)
```

Variantes datadas aceitam os placeholders nomeados `%(data_inicio)s`, `%(data_fim)s`, `%(ano_inicio)s`, `%(ano_fim)s`, `%(ano_mes_inicio)s`, `%(ano_mes_fim)s`.

### Materialized views

`sql/12_views.sql` segue uma arquitetura em camadas:

```
L1 (independentes)          L2 (derivadas)                 L3 (views planas)
mv_empresa_governo  ──┐
mv_pessoa_pb        ──┼─► mv_servidor_pb_risco       ─► v_risk_score_pb
mv_municipio_pb_risco ┼─► mv_empresa_pb              ─► v_risk_score_empresa
mv_servidor_pb_base ──┘    mv_rede_pb
                           mv_municipio_pb_kpi_score
                           mv_municipio_pb_mapa
                           mv_q67_dated_pb
```

Lista parcial — antes de mexer em `sql/12_views.sql`, consulte o arquivo completo (drops em ordem reversa no topo, notas de refresh no rodapé).

Ao adicionar/alterar MV:

1. Adicionar `DROP MATERIALIZED VIEW IF EXISTS` no **topo do arquivo**, em ordem reversa de criação (L3 → L2 → L1).
2. Criar a MV no bloco correspondente à sua camada.
3. Se quiser `REFRESH CONCURRENTLY`, crie UNIQUE INDEX.
4. Atualizar o bloco de notas de refresh no rodapé do arquivo.

## Convenções de relatórios

Relatórios em `relatorios/*.md` documentam casos reais detectados pelas queries.

- **Sempre mascarar CPFs** com `***.NNN.NNN-**`. CNPJs ficam completos (são públicos na base aberta da RFB).
- Citar fontes (qual query gerou o achado).
- Para casos de pessoa física, usar nomes oficiais — mas só quando o caso é de interesse público (servidor público, candidato, sancionado) e o dado já está em portal de transparência.
- Rodar `python scripts/audit_report_identifiers.py --strict` antes do PR para checar mascaramento.
- Validar identificadores contra a base RFB (`--report relatorios/seu_relatorio.md` sem `--strict`) se você tem o banco carregado.

## Convenções de commits e PRs

### Trailer Copilot

Toda mensagem de commit deve incluir o trailer:

```
Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
```

Isso documenta o uso de assistentes de IA na geração do código (Github Copilot, Claude Code, Codex). Ferramentas internas do projeto dependem desse trailer.

### Mensagem de commit

Use prefixos convencionais em PT-BR ou EN:

- `feat(escopo):` — feature nova
- `fix(escopo):` — correção de bug
- `docs(escopo):` — só documentação
- `refactor(escopo):` — refactor sem mudança de comportamento
- `perf(escopo):` — melhoria de performance
- `test(escopo):` — testes
- `chore(escopo):` — manutenção

Escopo é livre (`web`, `etl`, `deploy`, `queries`, `seguranca`, etc.).

### Pull request

- **Título** segue o padrão de commit.
- **Body** descreve o "porquê" da mudança, não o "o quê" (esse fica no diff).
- Liste tabelas de Antes/Depois quando aplicável.
- **Nunca cole secrets ou metadata sensível** no body do PR — ele é público mesmo em repos privados se viram públicos. Use placeholders genéricos.
- Marque o PR como "draft" se ainda está em iteração.

### Tamanho do PR

PRs menores são preferíveis. Se a mudança naturalmente quebra em fases (ex: refactor + feature), separe em PRs encadeados (`base: feat/parte-1`).

## Checklist de PR

Antes de abrir ou mergear um PR, **sempre revise estes pontos** — mudanças
não-óbvias na arquitetura ou na superfície pública do projeto exigem
documentação acompanhada:

- [ ] **README** — a mudança introduz uma feature nova, comando, env var, ou
  conceito fundamental que o `README.md` precisa mencionar? Atualize a seção
  apropriada (quick start, features, ou "Documentação adicional").
- [ ] **`docs/`** — o guia de área correto está atualizado?
  - `etl-guide.md` / `etl-incremental-guide.md` — mudou pipeline ETL
  - `web-guide.md` — mudou rota, template, componente MD3
  - `queries-guide.md` — adicionou Q##
  - `mv-guide.md` — mexeu em MV
  - `cache.md` — mexeu em `web_cache` ou shadow rewarm
  - `deploy.md` / `ops.md` — mudou deploy ou runbook
  - Atualize ou adicione diagramas Mermaid se o fluxo/topologia mudou.
- [ ] **ADR** — a mudança é uma decisão arquitetural não-óbvia (afeta múltiplos
  módulos, tem trade-offs não-triviais, alguém razoável poderia ter escolhido
  diferente)? Se sim, **crie `docs/adr/NNNN-titulo.md`** seguindo o template em
  [`docs/adr/README.md`](docs/adr/README.md). ADRs são **imutáveis** uma vez
  `Accepted` — para revisar uma decisão, crie um ADR novo que supersede o
  antigo.
- [ ] **Glossário** — termo novo do domínio que merece entrada em
  [`docs/glossario.md`](docs/glossario.md)?
- [ ] **Testes** — `tests/incremental/` cobre o framework incremental;
  para mudanças one-off, `python -m compileall etl -q` é o baseline mínimo.
- [ ] **Audit scripts** — mexeu em `relatorios/` ou identificadores? Rode
  `python scripts/audit_report_identifiers.py --strict` (offline) antes do PR.
- [ ] **Trailer Copilot** em todo commit:
  `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`.

Esse checklist é a versão "humana" do que o [`AGENTS.md`](AGENTS.md) também
exige para agentes de IA — fica consistente entre as duas audiências.

## Contribuindo com agentes de IA

O projeto foi escrito majoritariamente com auxílio de assistentes de IA
(GitHub Copilot, Claude Code, Codex) e está estruturado para que novos
contributors usem seus próprios agentes com baixa fricção.

A fonte canônica de instruções para agentes vive em
[`AGENTS.md`](AGENTS.md) na raiz do repositório. Ela é lida automaticamente
por:

- **GitHub Copilot CLI** — também lê `.github/copilot-instructions.md`
- **Claude Code** — também lê `CLAUDE.md`
- **Cursor**, **Aider**, **Codex CLI**, **Continue.dev** — leem `AGENTS.md`
  diretamente

`CLAUDE.md` e `.github/copilot-instructions.md` são arquivos-ponteiro curtos
que apontam para `AGENTS.md`. **Edite só o `AGENTS.md`** — os outros dois
ficam quase imutáveis. Justificativa em
[ADR-0008](docs/adr/0008-agents-md-canonical.md).

O `AGENTS.md` cobre:

- Mapa de leitura dos `docs/` em ordem de prioridade
- Comandos críticos de setup
- Arquitetura essencial (com pointers para detalhes)
- Convenções (no-pandas, no-ORM, RFB latin-1, etc.)
- **Quirks descobertos pelos agentes** — gotchas em MD3, Jinja, MV, Mermaid,
  cache typing, deploy. Internalize antes de mexer na área correspondente.
- Checklist de PR (mesma versão acima, para consumo do agente)
- Trailer obrigatório

Se você adicionar uma convenção nova ou descobrir um quirk não-óbvio durante
sua contribuição, **atualize o `AGENTS.md`** no mesmo PR — esse arquivo é o
contrato de conhecimento institucional.

## O que você pode tocar / pode não tocar

| Diretório | Status para PRs externos | Notas |
|---|---|---|
| `README.md`, `docs/`, `relatorios/` | ✅ Livre | Lembre do audit script em relatórios |
| `queries/` | ✅ Livre | Cuide do timeout 30s e índices |
| `sql/12_views.sql`, `sql/19_indices_queries.sql` | ✅ Com cuidado | MV layers; teste localmente |
| `etl/` | ✅ Com revisão profunda | Idempotência + cleanup `_CSV_DIRS`/`_SHARED_DIRS` |
| `etl/incremental/` | ✅ Com revisão profunda | Princípios P1-P6 inegociáveis (ver `etl/incremental/README.md`) |
| `web/` | ✅ Com revisão profunda | XSS / SQL injection / cache invalidation |
| `scripts/audit_report_identifiers.py` | ✅ Com revisão | Tem versão `--strict` que roda offline |
| `deploy/` | ⚠️ Owner-validated | Mantenedor precisa testar contra runner Azure |
| `.github/workflows/` | ⚠️ Owner-validated | Idem |
| `data/static/` | ⚠️ Owner | Snapshots binários referenciados pelo ETL |

## Onde pedir ajuda

- **Issues** — bugs, propostas de feature, ideias de query, dados públicos inconsistentes.
- **Discussions** — perguntas mais abertas, brainstorm de novas fontes.
- **Security** — vulnerabilidades, exposições de PII/LGPD. Use [GitHub Security Advisory](https://github.com/lucasdiniz/govbr-cruza-dados/security/advisories). Política `SECURITY.md` em desenvolvimento.
- **Contato direto** — [contato@transparenciapb.org](mailto:contato@transparenciapb.org).

---

Para um vislumbre da história do projeto, mecânicas do deploy e da arquitetura interna, comece pelo [README.md](README.md). Para o framework ETL incremental (princípios P1-P6, watermark, DLQ, shadow rewarm), veja [etl/incremental/README.md](etl/incremental/README.md).
