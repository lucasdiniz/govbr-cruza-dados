# Analytics & Umami events

> Catálogo dos eventos Umami emitidos pelo frontend. **Fonte autoritativa**:
> o comentário no topo de [`web/static/js/lib/umami-track.js`](../web/static/js/lib/umami-track.js).
> Este documento espelha o catálogo num formato consultável e adiciona contexto
> de UX/produto. Quando adicionar um evento novo, atualize **os dois**.

## Como funciona

- Wrapper: [`web/static/js/lib/umami-track.js`](../web/static/js/lib/umami-track.js)
  expõe `trackEvent(name, props)`. Engole silenciosamente se
  `window.umami` não estiver carregado (DNT ativado, dev sem
  `UMAMI_WEBSITE_ID`, etc.).
- Tracker carrega via snippet em `<head>` de `base.html` quando
  `UMAMI_WEBSITE_ID` está setado. Self-hosted em
  [`/_traffic/analytics/`](https://transparenciapb.org/_traffic/analytics/)
  (admin-only, basic-auth + login Umami).
- Privacidade: sem fingerprinting cross-site, sem Google Analytics, sem
  Facebook Pixel. Detalhes em [`docs/privacidade.md`](privacidade.md).

## Convenções de naming

- **kebab-case**, **sem prefixo de página** (ex: `secao-toggle`, não
  `cidade-secao-toggle`).
- Nome curto e estável — vai virar coluna no painel Umami; renomear quebra
  histórico.
- Props extras viram colunas filtráveis. Valores simples (strings curtas,
  numbers); evite payloads grandes ou JSON aninhado.
- Reuse evento existente quando semântica casar (ex: `secao-toggle` para
  qualquer `<details>` colapsável, não criar um novo evento por seção).

## Catálogo

### Navegação & contexto da página

| Evento | Props | Onde dispara |
|---|---|---|
| `cidade-buscar` | `{via: 'autocomplete'}` | busca de cidade no header |
| `cidade-visita` | `{municipio, uf}` | top-of-funnel da página de cidade |
| `empresa-visita` | `{cnpj, nome, escopo: 'global'\|'municipio', municipio?}` | abertura da página de empresa |
| `pagina-caso-visita` | `{slug}` | abertura de página de caso (`/caso/...`) |
| `nav-clicado` | `{target: 'sobre'\|'glossario'\|'contato', from: 'footer'\|'overflow-menu'}` | auto-track via `data-umami-event` |
| `outbound-click` | `{dominio, href}` | clique em link externo (origin+pathname; sem query/hash) |
| `tour-iniciado` | `{pagina: 'cidade'\|'home'}` | usuário inicia tour guiado |

### Mapa & filtros globais

| Evento | Props | Onde dispara |
|---|---|---|
| `mapa-cidade-click` | `{cidade, metrica}` | clique em município no mapa da home |
| `mapa-metrica-mudou` | `{metrica}` | troca da métrica visualizada no mapa |
| `date-filter-aplicado` | `{preset, de?, ate?, municipio?}` | aplicação de filtro temporal nas páginas de cidade |
| `modo-toggle` | `{to: 'auditor'\|'citizen'}` | toggle dual-mode citizen ↔ auditor |
| `font-size-change` | `{level: 'normal'\|'lg'\|'xl'}` | toggle de tamanho de fonte (a11y) |

### Dialogs (drilldowns)

| Evento | Props | Onde dispara |
|---|---|---|
| `dialog-aberto` | `{tipo, municipio, ...id-fields, drilled_from?}` ¹ | abertura de dialog drilldown |
| `dialog-tab-change` | `{tipo, de, para}` | troca de tab via **click, keyboard ou swipe** ² |
| `dialog-fechado` | `{tipo, dwell_ms, tabs_visitadas, scroll_max_pct, drilled_to?}` ³ | pareado com `dialog-aberto`; mede engagement real |
| `credibilidade-aberto` | — | abertura do dialog "Sobre os dados" |
| `denuncia-info-aberto` | — | abertura do dialog "Como denunciar" |

¹ Id-fields variam por tipo:
- `tipo='empenho'` → `{empenho}`
- `tipo='servidor'` → `{cpf6, nome}`
- `tipo='fornecedor'` → `{cnpj, nome}`
- `tipo='licitacao'` → `{numero, ano, modalidade}`
- `tipo='heatmap'` → `{ano, mes}`
- `drilled_from` aparece quando usuário navegou de um dialog para outro sem fechar (ex: `fornecedor → empenho`).

² Swipe touch também dispara `dialog-tab-change` — handler manual em
[`web/static/js/components/dialog-decorate.js`](../web/static/js/components/dialog-decorate.js)
porque o swipe não passa pelo listener `tabs.change` do `<md-tabs>`.

³ `drilled_to` presente quando o dialog "fechou" porque o usuário navegou
para outro tipo de dialog (chain sem fechar o `md-dialog`) ou clicou voltar.

### Engagement

| Evento | Props | Onde dispara |
|---|---|---|
| `scroll-deep` | `{percent: 50\|75\|100, pagina}` | marcos discretos de scroll |
| `pagina-saida` | `{pagina, tempo_ms, scroll_max_pct}` | uma vez por page load, no `visibilitychange`/`pagehide` (sai da aba) ⁴ |
| `narrative-anchor-click` | `{anchor}` | clique em palavra destacada do resumo da cidade que pula pra seção |
| `finding-card-expand` | `{tipo}` | expand de finding card (collapse não dispara) |
| `secao-toggle` | `{section, action: 'open'\|'close'}` ⁵ | toggle genérico de `<details>` colapsável |
| `termo-tooltip-aberto` | `{termo}` | tap numa palavra do glossário inline (`.term[data-tip]`) em touch device |
| `explainer-aberto` | `{target}` | clique no botão "?" inline que expande "O que isso significa?" |
| `back-to-top-clicado` | `{scroll_pct}` | clique no botão flutuante "voltar ao topo"; `scroll_pct` 0-100 mede a profundidade antes do reset |
| `concentracao-bar-clicado` | `{rank}` | clique numa barra do card "Concentração de fornecedores" (cidade); `rank` 1..N, casa com `dialog-aberto` que dispara em seguida |

⁴ Implementado em
[`web/static/js/lib/page-engagement.js`](../web/static/js/lib/page-engagement.js).
Respeita whitelist de páginas (cidade, empresa, caso, etc.).

⁵ `section` identifica a seção (ex: `'bolsa-familia-regras'`,
`'duplo-vinculo-regras'`, ou auto-derivado do `h4`).

⁶ `tabela` vem de `data-table-id` no shell. Templates conhecidos:
`top-servidores`, `top-fornecedores`, `result-query` (genérico Q##).
Tabelas sem `data-table-id` no shell **não emitem** o evento — opt-in
explícito para evitar ruído de tabelas auxiliares.

⁷ Flags possíveis no chip de fornecedores: `inidoneidade`,
`recebeu_durante_inidoneidade`, `recebeu_durante_sancao_aplicavel`,
`ceis`, `cnep`, `acordo_leniencia`, `inativa_irregular`, `pgfn`, `inativa`.
Semântica OR (union dos filtros ativos).

### Filtros & ordenação de tabelas

| Evento | Props | Onde dispara |
|---|---|---|
| `servidores-filtro-toggle` | `{flag, action: 'on'\|'off', ativos, qtd_ativos, visiveis, total}` | toggle de chip de filtro na tabela de servidores |
| `servidores-filtro-limpar` | `{ativos_anteriores, qtd_ativos_anteriores, visiveis}` | botão "Limpar" dos chips de filtro |
| `fornecedores-filtro-toggle` | `{flag, action: 'on'\|'off', ativos, qtd_ativos, visiveis, total}` | toggle de chip de filtro na tabela de fornecedores ⁷ |
| `fornecedores-filtro-limpar` | `{ativos_anteriores, qtd_ativos_anteriores, visiveis}` | botão "Limpar" dos chips de filtro de fornecedores |
| `tabela-pagina-mudou` | `{tabela, de, para, total_paginas, via: 'prev'\|'next'}` ⁶ | clique em Anterior/Próxima das tabelas paginadas |
| `empenho-table-sort` | `{coluna, direcao: 'asc'\|'desc'}` | clique em header de tabela para ordenar (dialog de empenho) |

### Diversos

| Evento | Props | Onde dispara |
|---|---|---|
| `compartilhar` | `{via: 'share-api'\|'clipboard'\|'fallback'}` | botão compartilhar |
| `contato-enviado` | — | formulário `/contato` submitted com sucesso |
| `api-error` | `{endpoint, status}` | drilldown via `/api/...` falhou; `status=0` = network error |

## Adicionando um evento novo

1. Escolha o nome seguindo as convenções acima (kebab-case, sem prefixo).
2. Verifique se um evento existente cobre o caso. Reuse antes de criar.
3. Disparar via `trackEvent(name, props)`:
   ```js
   if (typeof trackEvent === 'function') {
       trackEvent('meu-evento', { campo1: valor1 });
   }
   ```
4. Atualize **dois lugares**:
   - Bloco de comentário no topo de
     [`web/static/js/lib/umami-track.js`](../web/static/js/lib/umami-track.js).
   - Tabela correspondente neste documento (`docs/analytics.md`).
5. Se o evento for de toggle/expand, use `aria-pressed`/`aria-expanded`
   correspondentes e teste em mobile (ver checklist mobile-first no
   [`AGENTS.md`](../AGENTS.md)).

## Auto-track via `data-umami-event`

Para clicks simples sem lógica condicional, usar atributos HTML:

```html
<a href="/sobre"
   data-umami-event="nav-clicado"
   data-umami-event-target="sobre"
   data-umami-event-from="footer">Sobre</a>
```

Umami captura automaticamente via delegação no `document`. Preferir
`trackEvent()` em JS quando precisar de lógica condicional ou props
computadas em runtime.

## Onde consultar os dados

- Painel: [`/_traffic/analytics/`](https://transparenciapb.org/_traffic/analytics/)
  (admin, basic-auth + login Umami).
- Logs do tracker: `journalctl -u cruza-umami` na VM.
- Detalhes de infra: [`docs/ops.md`](ops.md#runbook-goaccess--umami).
