// === lib/umami-track.js ===
// Wrapper safe pra window.umami.track. Sem trabalho quando o tracker nao
// esta carregado (UMAMI_SCRIPT_URL/UMAMI_WEBSITE_ID nao setados ou DNT).
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
