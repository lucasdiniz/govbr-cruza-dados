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
//   cidade-buscar         - {via: 'autocomplete'|'enter'|'autocomplete-keyboard'}
//   mapa-cidade-click     - {cidade, metrica}
//   dialog-aberto         - {tipo: 'empenho'|'servidor'|'fornecedor'|'licitacao'|'heatmap'}
//   modo-toggle           - {to: 'auditor'|'citizen'}
//   font-size-change      - {level: 'normal'|'lg'|'xl'}
//   compartilhar          - {via: 'share-api'|'clipboard'|'fallback'}
//   contato-enviado       -
//   tour-iniciado         - {origem: 'restart'|'auto'}
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
