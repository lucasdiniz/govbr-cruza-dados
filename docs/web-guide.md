# Web guide — adicionando query, rota, template ou componente MD3

Este guia complementa [architecture.md](architecture.md) e o [glossario.md](glossario.md) com os fluxos práticos do frontend.

## Stack

- **Backend:** FastAPI + Uvicorn (`web/main.py`), pool de conexões `psycopg2` em [`web/db.py`](../web/db.py).
- **Templates:** Jinja2 SSR — sem React, sem SPA. Cada rota retorna HTML completo.
- **JS:** scripts clássicos (não-módulos) carregados em ordem fixa por `JS_FILES` em [`web/main.py`](../web/main.py) (linhas ~363-439). Funções compartilhadas via globais.
- **CSS:** Material Design 3 tokens + camadas (layers), zero Tailwind.
- **Mapa:** Leaflet em `web/static/js/components/mapa.js`.
- **Build de assets:** esbuild (`scripts/build-assets.mjs`) gera bundles com content-hash em `web/static/dist/manifest.json`.
- **SQL:** raw, sem ORM. Toda query passa por `cached_query()`, `read_web_cache()` ou `execute_query()` de [`web/db.py`](../web/db.py).

## Fluxo de um request

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser
    participant N as Nginx (rate limit)
    participant R as FastAPI route
    participant D as web/db.py
    participant PG as PostgreSQL
    participant T as Jinja2

    B->>N: GET /cidade/joao-pessoa
    N->>R: proxy (host allowed, RPS ok)
    R->>D: read_web_cache(qid="KPI_SUMMARY", municipio="João Pessoa")
    alt cache hit
        D-->>R: (cols, rows)
        R->>T: render(cidade.html, ctx)
        T-->>B: HTML SSR
    else cache miss em rota cache-only
        D-->>R: None
        R-->>B: 503 (warm pendente)
    else live fallback (rotas leves: perfil, autocomplete)
        R->>D: execute_query(sql, timeout=TIMEOUT_PROFILE=3s)
        D->>PG: SET statement_timeout=3000; SELECT ...
        PG-->>D: rows ou timeout
        D-->>R: (cols, rows)
        R->>T: render
        T-->>B: HTML
    end
```

> **Cache-only by design:** rotas pesadas (`/api/cidade/q/*`) só leem `web_cache`; nunca tocam Postgres em request quente. Quem popula o cache é [`web/warm_cache.py`](../web/warm_cache.py). Detalhes em [cache.md](cache.md).

## 1. Adicionando uma query nova ao registry

As Q## do modo deep-dive são registradas em [`web/queries/registry.py`](../web/queries/registry.py) via `QueryDef`:

```python
_reg(
    qid="Q199",
    titulo="Servidores com vínculo CPF→CNPJ em fornecedor pago",
    categoria="conflito-interesses",  # ver categorias existentes
    sql_full=SQL_Q199,
    sql_full_dated=SQL_Q199_DATED,    # opcional
    timeout_sec=30,                   # default; raise só se justificado
)
```

Placeholders nomeados aceitos:

| Placeholder | Quando aparece | Origem |
|---|---|---|
| `%(municipio)s` | sempre (filtro principal) | path param |
| `%(data_inicio)s`, `%(data_fim)s` | variante `_dated` (datas exatas) | UI date filter |
| `%(ano_inicio)s`, `%(ano_fim)s` | variante `_dated` por ano | UI date filter |
| `%(ano_mes_inicio)s`, `%(ano_mes_fim)s` | variante `_dated` por ano-mês | UI date filter |

**Checklist:**

1. Cabeçalho `-- Q##: Titulo` no `.sql` (parser de `etl/run_queries.py` depende dele — ver [queries-guide.md](queries-guide.md)).
2. Rodar `EXPLAIN ANALYZE` localmente.
3. Se passar de 30s ou tiver `Seq Scan` em tabelões: adicionar índice em [`sql/19_indices_queries.sql`](../sql/19_indices_queries.sql).
4. Categoria existente: `fornecedores-irregulares`, `conflito-interesses`, `politico-eleitoral`, `licitacao-concorrencia`, `cruzamento-estado-municipio`, `orcamento-financeiro`.
5. Criar índice/MV se a query for cache-eligible — o warmer só consegue popular se rodar dentro do timeout em produção.

Detalhes completos em [queries-guide.md](queries-guide.md).

## 2. Adicionando uma rota nova

Crie um módulo em `web/routes/<feature>.py`:

```python
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from web import db
from web.main import templates  # ou injete via dependency

router = APIRouter()


@router.get("/feature/{municipio}", response_class=HTMLResponse)
async def feature_page(request: Request, municipio: str):
    cache = db.read_web_cache("FEATURE_KEY", municipio)
    if cache is None:
        # 503 cache-only; warm.py é quem popula
        return templates.TemplateResponse("503_warm.html", {"request": request}, status_code=503)
    cols, rows = cache
    return templates.TemplateResponse(
        "feature.html",
        {"request": request, "cols": cols, "rows": rows, "municipio": municipio},
    )
```

Registre em `web/main.py`:

```python
from web.routes.feature import router as feature_router
app.include_router(feature_router)
```

**Regras de ouro:**

- **Sem ORM.** Toda SQL é raw, parametrizada via `%(name)s` (psycopg2). f-strings em SQL só com whitelist hardcoded (ver caveat em `web/routes/cidade.py` nas funções que montam `IN (...)` por concatenação).
- **Use `read_web_cache()` para queries pesadas** — request quente nunca espera Postgres mais que `TIMEOUT_PROFILE=3s`.
- **Para queries leves** (autocomplete, perfil simples), use `cached_query()` com `timeout_sec=TIMEOUT_AUTOCOMPLETE` (2s) ou `TIMEOUT_PROFILE` (3s) de [`web/config.py`](../web/config.py).
- **POST em `/api/*`** passa pelo Origin guard de [`web/main.py:99-118`](../web/main.py) — só hosts em `_ALLOWED_API_HOSTS` (`transparenciapb.org`, `localhost`...).

## 3. Adicionando um template novo

Estenda `base.html` e preencha os blocks SEO:

```html
{% extends "base.html" %}

{% block title %}Minha feature — {{ municipio }} | transparenciapb.org{% endblock %}
{% block meta_description %}Resumo curto, 140-160 chars, para SERP.{% endblock %}
{% block og_title %}{{ self.title() }}{% endblock %}
{% block og_image %}{{ asset_url('og-default.png') }}{% endblock %}

{% block content %}
  <link rel="stylesheet" href="{{ asset_url('feature.css') }}">
  <article>
    <h1>{{ municipio }}</h1>
    <!-- ... -->
  </article>
{% endblock %}
```

- `asset_url('feature.css')` resolve via manifest (`web/static/dist/manifest.json`) com hash de conteúdo; em dev sem build, devolve o arquivo cru com `?v=ASSET_VERSION`.
- `canonical_url(request)` é Jinja global (`web/main.py:589`) — use em `<link rel="canonical">`.
- Não use `i18n`: o projeto é **PT-BR hardcoded** (decisão de produto, não roadmap).

## 4. Adicionando um componente Material Design 3

Os tags `<md-*>` são custom elements do `@material/web` carregados via importmap em `base.html:115-134` (módulo deferido em `web/static/js/md3/imports.js`).

**Race condition real:** os custom elements fazem upgrade async. Qualquer JS clássico que toque propriedades de um `<md-*>` (ex: `.value`, `.selected`, `.open`) **deve** esperar o helper de [`web/static/js/lib/md3-ready.js`](../web/static/js/lib/md3-ready.js):

```html
<md-filled-select id="filtro-ano">
  <md-select-option value="2024">2024</md-select-option>
  <md-select-option value="2025">2025</md-select-option>
</md-filled-select>

<script>
  window.whenMD3Ready(() => {
    const sel = document.getElementById("filtro-ano");
    sel.value = "2025";              // safe — upgrade já aconteceu
    sel.addEventListener("change", e => { /* ... */ });
  });
</script>
```

Sem `whenMD3Ready`, em mobile e em conexões lentas o setter executa antes do upgrade — set vira no-op, listener pode ficar órfão.

**Adicione o JS** ao final do array `JS_FILES` em `web/main.py:363-439`, respeitando dependências (helpers como `lib/format.js` precisam vir antes dos componentes que os usam).

## Build pipeline

```bash
npm install                # uma vez
npm run build              # esbuild concat + minify + sourcemap → web/static/dist/
npm run build:check        # smoke usado no CI
```

- Lista de entradas é lida por `scripts/build-assets.mjs:75-105` a partir de `JS_FILES` em `web/main.py`.
- Output: `web/static/dist/<nome>.<hash>.min.js` + `manifest.json` mapeando nome lógico → URL com hash.
- `asset_url('cidade.js')` busca no manifest em runtime; com `ASSETS_STRICT=1` ausência de bundle falha (prod), sem strict cai pro arquivo cru (dev).

## Caveats reais

- **f-strings em SQL com lista `IN`:** `web/routes/cidade.py` (várias funções de detalhes) monta `IN (...)` por concatenação. Há issue aberta para helper central; até lá, **nunca interpolar input do usuário** — só constantes whitelisted.
- **Templates com `|safe`:** `web/templates/results/cidade.html` injeta HTML com `|safe` para rich snippets (linhas em torno de `202`, `215-216`, `433`). Política: autoescape ligado por padrão (Jinja default) + `|safe` só em strings montadas no servidor com whitelist.
- **`/api/cache/invalidate`** exige header `X-Admin-Token` (PR #118). Fail-closed: se `CACHE_INVALIDATE_TOKEN` não estiver no `.env`, endpoint responde 503. Ver `web/routes/cidade.py:1406-1430`.
- **Service Worker:** `web/static/sw.js` faz stale-while-revalidate para assets estáticos. Bump `ASSET_VERSION` (atualmente `"112"` em `web/main.py:441`) quando publicar mudança que precise invalidar SW.
- **Origin guard** bloqueia `POST /api/*` sem Origin/Referer válido. Bots casuais (curl, scrapy default) são filtrados; é defesa em profundidade, não autenticação.
- **Acessibilidade:** skip link + ARIA estão em `base.html` e templates principais. Auditoria automatizada (axe/lighthouse no CI) é issue #131, ainda aberta.

## Testando localmente

```bash
pip install -e .[web]
# Postgres rodando com schema + cache populado:
python -m web.warm_cache --pb           # popula web_cache para 223 munis PB
python -m uvicorn web.main:app --port 8000 --reload
# smoke estático:
python -m compileall web -q
```

Para `web.warm_cache` e cache em geral, ver [cache.md](cache.md).
Para mudanças em queries Q##, ver [queries-guide.md](queries-guide.md).
Para mudanças em MVs, ver [mv-guide.md](mv-guide.md).
