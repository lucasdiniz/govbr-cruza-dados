// === lib/umami-track.js ===
// Wrapper safe pra window.umami.track. Sem trabalho quando o tracker nao
// esta carregado (UMAMI_SCRIPT_URL/UMAMI_WEBSITE_ID nao setados ou DNT).
//
// >>> CATALOGO COMPLETO: ../../../docs/analytics.md <<<
//
// O snippet do Umami injeta `window.umami` quando o script eh carregado e
// data-website-id eh valido. Em dev/preview sem essas vars, `window.umami`
// nao existe — o wrapper engole silenciosamente em vez de quebrar a UI
// com TypeError.
//
// Convencao de nomes (kebab-case):
//   * Vai aparecer no painel Umami -> Events. Use nomes curtos e estaveis.
//   * Props extras viram colunas filtraveis. Mantenha valores simples
//     (strings curtas, numbers); evite payloads grandes.
//   * Sem prefixo de pagina (ex: 'secao-toggle', nao 'cidade-secao-toggle').
//
// IMPORTANTE: ao adicionar/renomear evento, atualizar OS DOIS:
//   1. Bloco de comentario abaixo (fonte autoritativa pra agentes/devs).
//   2. docs/analytics.md (formato consultavel + contexto de UX).
//
// Eventos atuais (ver tambem README dos componentes):
//   cidade-buscar         - {via: 'autocomplete'}
//   cidade-visita         - {municipio, uf}  (top-of-funnel da cidade)
//   mapa-cidade-click     - {cidade, metrica}
//   mapa-metrica-mudou    - {metrica}
//   dialog-aberto         - {tipo, municipio, ...id-fields conforme tipo,
//                            drilled_from? (tipo do dialog anterior quando
//                            usuario navegou de um dialog pra outro sem
//                            fechar — ex: fornecedor->empenho)}:
//                             tipo=empenho     -> {empenho}
//                             tipo=servidor    -> {cpf6, nome}
//                             tipo=fornecedor  -> {cnpj, nome}
//                             tipo=licitacao   -> {numero, ano, modalidade}
//                             tipo=heatmap     -> {ano, mes}
//   dialog-tab-change     - {tipo, de, para}  (label das tabs do dialog
//                            quando user troca via click/keyboard/swipe)
//   empresa-visita        - {cnpj, nome, escopo: 'global'|'municipio', municipio?}
//   pagina-caso-visita    - {slug}
//   date-filter-aplicado  - {preset, de?, ate?, municipio?}
//   outbound-click        - {dominio, href}  (origem+pathname; sem query/hash)
//   modo-toggle           - {to: 'auditor'|'citizen'}
//   font-size-change      - {level: 'normal'|'lg'|'xl'}
//   compartilhar          - {via: 'share-api'|'clipboard'|'fallback'}
//   contato-enviado       -
//   tour-iniciado         - {pagina: 'cidade'|'home'}
//   nav-clicado           - {target, from}  (auto-track via data-umami-event;
//                            target ∈ sobre|glossario|contato; from ∈
//                            footer|overflow-menu)
//   credibilidade-aberto  -
//   denuncia-info-aberto  -
//   scroll-deep           - {percent: 50|75|100, pagina}
//                           (engagement: leu 50/75/100% do scroll)
//   narrative-anchor-click - {anchor}  (palavra destacada do resumo da
//                            cidade que pula pra secao relacionada)
//   finding-card-expand   - {tipo}  (expand de finding card; collapse nao)
//   empenho-table-sort    - {coluna, direcao: 'asc'|'desc'}
//   api-error             - {endpoint, status}  (drilldown falhou;
//                            status=0 = network error)
//   pagina-saida          - {pagina, tempo_ms, scroll_max_pct}
//                           Disparado UMA UNICA VEZ por page load quando
//                           a aba fica oculta (visibilitychange) ou no
//                           pagehide. Mede tempo real de engajamento
//                           (vs scroll-deep que so dispara em marcos
//                           discretos) e profundidade maxima do scroll.
//                           Implementado em lib/page-engagement.js;
//                           respeita o mesmo whitelist de paginas do
//                           scroll-deep (cidade, empresa, caso, etc).
//   dialog-fechado        - {tipo, dwell_ms, tabs_visitadas, scroll_max_pct,
//                            drilled_to?}
//                           Pareado com dialog-aberto. Mede engagement
//                           real por dialog: quanto tempo o user ficou,
//                           quantas tabs DISTINTAS explorou, quanto do
//                           conteudo rolou. `drilled_to` so presente
//                           quando o dialog "fechou" porque o user
//                           navegou pra outro tipo de dialog (chain sem
//                           fechar o md-dialog), ou clicou voltar e
//                           restaurou o nivel anterior
//                           (`drilled_to='back-<tipo>'`). Implementado
//                           em lib/dialog-engagement.js.
//   dialog-restored       - {tipo} Disparado quando o user clica
//                           "voltar" do dialog stack e o conteudo de um
//                           dialog anterior eh re-renderizado.
//                           tipo = nivel restaurado. Permite distinguir
//                           "abri novo" (dialog-aberto) de "voltei"
//                           (dialog-restored). dialog-engagement usa pra
//                           flushar a sessao do nivel atual marcando
//                           drilled_to='back-<tipo>' e comecar nova
//                           sessao com o tipo restaurado.
//   servidores-filtro-toggle - {flag, action: 'on'|'off', ativos,
//                            qtd_ativos, visiveis, total}
//                           Toggle de chip de filtro na tabela de
//                           servidores (PR #195 / ADR-0011). `ativos`
//                           eh CSV ordenado de flags ativos pos-toggle.
//   servidores-filtro-limpar - {ativos_anteriores, qtd_ativos_anteriores,
//                            visiveis}
//                           Botao "Limpar" dos chips de filtro.
//   fornecedores-filtro-toggle - {flag, action: 'on'|'off', ativos,
//                            qtd_ativos, visiveis, total}
//                           Toggle de chip de filtro na tabela de
//                           fornecedores. Flags: inidoneidade,
//                           recebeu_durante_inidoneidade,
//                           recebeu_durante_sancao_aplicavel, ceis, cnep,
//                           acordo_leniencia, inativa_irregular, pgfn,
//                           inativa.
//   fornecedores-filtro-limpar - {ativos_anteriores, qtd_ativos_anteriores,
//                            visiveis}
//                           Botao "Limpar" dos chips de filtro de
//                           fornecedores.
//   secao-toggle          - {section, action: 'open'|'close'}
//                           Toggle generico de <details> colapsavel.
//                           `section` identifica a secao (ex:
//                           'bolsa-familia-regras',
//                           'duplo-vinculo-regras' do servidor-dialog).
//   tabela-pagina-mudou   - {tabela, de, para, total_paginas, via:
//                            'prev'|'next'}
//                           Click em Anterior/Proxima das tabelas
//                           paginadas. `tabela` vem de data-table-id no
//                           shell (opt-in por template; tabelas sem
//                           data-table-id NAO emitem o evento). Permite
//                           medir profundidade de exploracao por tipo
//                           de tabela (top-servidores, top-fornecedores,
//                           result-query).
//   tabela-hidratada      - {tabela, total, initial, ms_to_hydrate,
//                            forced: true|false}
//                           Tabelas top-servidores/top-fornecedores com
//                           > 100 rows usam progressive loading (PR #199):
//                           SSR emite as primeiras `initial` rows em
//                           <tbody> + o resto em
//                           <script type="text/html" data-rest-rows>.
//                           Evento dispara no momento em que o tail e
//                           hidratado (via requestIdleCallback ou ao
//                           primeiro user input). `forced=true` quando
//                           usuario interagiu antes do RIC disparar.
//                           Permite monitorar TTI real em mid-tier mobile.
//   termo-tooltip-aberto  - {termo} Tap em palavra do glossario inline
//                           (`.term[data-tip]`) em touch device. Mede
//                           quais termos confundem leitores.
//   explainer-aberto      - {target} Click no botao "?" inline
//                           (`.explainer-btn[data-explainer-target]`).
//                           `target` eh o id do panel expandido.
//   back-to-top-clicado   - {scroll_pct} Click no botao flutuante de
//                           voltar ao topo. `scroll_pct` (0-100) mede
//                           profundidade real antes do reset.
//   concentracao-bar-clicado - {rank} Click numa barra do card
//                           "Concentracao de fornecedores" da pagina
//                           cidade. `rank` eh 1..N (posicao do top).
//                           Casa com `dialog-aberto` que dispara em
//                           seguida.
window.trackEvent = function trackEvent(name, props) {
    try {
        if (typeof window.umami !== 'undefined' && typeof window.umami.track === 'function') {
            if (props && typeof props === 'object') {
                window.umami.track(name, props);
            } else {
                window.umami.track(name);
            }
        }
    } catch (_) {
        // noop: analytics nunca pode quebrar a pagina
    }
    // Dispatch CustomEvent espelhando o track. Permite que listeners
    // internos (dialog-engagement, futuros agregadores) reajam a eventos
    // SEM precisar ser invocados explicitamente por cada call-site. O
    // dispatch acontece mesmo em dev sem Umami carregado — desacopla
    // analytics do estado do tracker.
    try {
        document.dispatchEvent(new CustomEvent('tpb:tracked', {
            detail: { name: String(name), props: (props && typeof props === 'object') ? props : null },
        }));
    } catch (_) {
        // CustomEvent nao suportado / document indisponivel — ignora.
    }
};

// ─── Self-identify pra debug/marcacao manual ────────────────────────────────
// Permite marcar SEU proprio browser nas listas de visitantes do painel Umami
// pra distinguir sessoes de teste/equipe do trafego real.
//
// Uso (uma vez por browser, no DevTools Console):
//   setUmamiIdentity('lucas')          -> tagga todos eventos com id='lucas'
//   clearUmamiIdentity()               -> remove a tag
//
// A identidade fica em localStorage ('umami.identity') e eh re-injetada
// em CADA payload via o hook data-before-send do tracker (ver base.html).
// Esse hook intercepta todos os sends — incluindo o pageview inicial do
// init() — antes do fetch acontecer, eliminando race condition entre o
// tracker dispatchar pageview ANTES de identify() rodar.
//
// O alternativo seria poll de window.umami + chamar identify(), mas isso
// tem race: o init() do tracker dispara track() (pageview inicial) ANTES
// do nosso poll chamar identify, entao a sessao anonima eh criada e
// pageviews ficam la em vez de na sessao identificada.
//
// Mantemos tambem a chamada explicita a umami.identify() no setUmamiIdentity,
// pra que quando o user roda no DevTools imediatamente uma session record
// com distinct_id seja criada no DB (alem dos payloads subsequentes).

// Hook before-send: intercepta TODO payload (event/identify/performance) e
// injeta payload.id do localStorage se setado. Roda ANTES do fetch pro
// /api/send, entao mesmo o pageview inicial (que o init() dispara
// sincronamente) vai com id atrelado.
window.umamiBeforeSend = function umamiBeforeSend(_type, payload) {
    try {
        const me = localStorage.getItem('umami.identity');
        if (me && payload && typeof payload === 'object') {
            payload.id = me;
        }
    } catch (_) {
        // localStorage indisponivel (private mode etc) — payload segue inalterado
    }
    return payload;
};

window.setUmamiIdentity = function setUmamiIdentity(name) {
    try { localStorage.setItem('umami.identity', String(name)); } catch (_) {}
    try {
        if (window.umami && typeof window.umami.identify === 'function') {
            window.umami.identify(String(name));
        }
    } catch (_) {}
};
window.clearUmamiIdentity = function clearUmamiIdentity() {
    try { localStorage.removeItem('umami.identity'); } catch (_) {}
};
