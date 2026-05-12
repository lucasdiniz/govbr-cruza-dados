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
//   mapa-cidade-click     - {cidade, metrica}
//   mapa-metrica-mudou    - {metrica}
//   dialog-aberto         - {tipo, municipio, ...id-fields conforme tipo}:
//                             tipo=empenho     -> {empenho}
//                             tipo=servidor    -> {cpf6, nome}
//                             tipo=fornecedor  -> {cnpj, nome}
//                             tipo=licitacao   -> {numero, ano, modalidade}
//                             tipo=heatmap     -> {ano, mes}
//   empresa-visita        - {cnpj, nome, escopo: 'global'|'municipio', municipio?}
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
// A identidade fica em localStorage ('umami.identity') e eh re-aplicada
// automaticamente em cada pageview / navegacao. No painel Umami, sessoes
// com identity setada aparecem com o id atrelado (visivel em
// Sessions > Detalhes).
//
// O umami tracker carrega assincrono, entao fazemos poll ate window.umami
// existir antes de chamar identify(). Limite 5s pra desistir.
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
(function _applyIdentityWhenReady() {
    let me;
    try { me = localStorage.getItem('umami.identity'); } catch (_) { return; }
    if (!me) return;
    let tries = 0;
    const tick = () => {
        if (window.umami && typeof window.umami.identify === 'function') {
            try { window.umami.identify(me); } catch (_) {}
            return;
        }
        if (++tries > 50) return;
        setTimeout(tick, 100);
    };
    tick();
})();
