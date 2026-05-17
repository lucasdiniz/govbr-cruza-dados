// === components/collapsible.js ===
// Hook leve pras secoes colapsaveis (<details>/<summary>) renderizadas
// pelo macro partials/_collapsible.html.
//
// Duas responsabilidades:
//   1. URL hash sync no toggle: quando o user abre uma secao, atualiza
//      o hash via history.replaceState. Quando fecha a secao corrente,
//      limpa o hash. Permite copiar/compartilhar o link da secao aberta
//      sem mentir sobre o estado da pagina.
//   2. Tracking Umami opcional: dispara `secao-toggle` com
//      {section, action} quando user interage. Util pra entender quais
//      secoes investigativas mais geram engajamento.
//   3. Print: abre todas as secoes em beforeprint, restaura em afterprint
//      (CSS sozinho nao consegue forcar <details> a mostrar conteudo —
//      eh user-agent shadow DOM). Toggles programaticos sao suprimidos
//      pelo _printing flag.
//
// "Abrir secao quando URL bate em hash" eh delegado pro stack
// existente: anchor-auto-expand.js intercepta clicks em <a href="#id">
// + hashchange events, chama expandReportContext() em lib/expand-context.js,
// que sabe abrir details.collapsible-details. Single source of truth pra
// scroll + flash. NAO duplicar essa logica aqui.
//
// Sem JS, o <details> nativo funciona normal (toggle por click, foco com
// Tab, ativacao com Space/Enter). Este helper apenas adiciona conveniencias
// de URL/analytics/print.

(function () {
    'use strict';

    // Flag pra suprimir hash sync + tracking durante print (beforeprint
    // forca abrir tudo, gerando N toggle events programaticos). Sem
    // isso, cada print poluiria o Umami com 6+ events espurios e
    // poderia deixar o hash apontando pra ultima secao aberta.
    // IMPORTANTE: o evento 'toggle' do <details> eh assincrono (fired
    // em task seguinte). Por isso, no afterprint, limpamos a flag via
    // setTimeout(0) — caso contrario os toggle events do restore
    // veriam _printing=false e vazariam pro tracking.
    let _printing = false;

    function _allDetails() {
        return Array.from(document.querySelectorAll('.collapsible-details[data-collapsible-id]'));
    }

    function _attachToggleHandlers() {
        _allDetails().forEach((d) => {
            const id = d.getAttribute('data-collapsible-id') || '';
            if (!id) return;
            // O 'toggle' event do <details> fire em qualquer mudanca de
            // open. Sem precisar de click handler manual no summary.
            d.addEventListener('toggle', () => {
                if (_printing) return; // toggles programaticos do print: ignora
                const action = d.open ? 'open' : 'close';
                // Umami tracking (silencioso se trackEvent ausente).
                if (typeof trackEvent === 'function') {
                    trackEvent('secao-toggle', {
                        section: id,
                        action,
                    });
                }
                // URL hash sync: replace (nao push) pra nao adicionar
                // entrada no history a cada click. Hash representa o
                // ULTIMO toggle do user — comportamento previsivel pra
                // copiar/compartilhar link.
                try {
                    const url = new URL(window.location.href);
                    if (action === 'open') {
                        url.hash = id;
                        window.history.replaceState(window.history.state, '', url);
                    } else if (action === 'close' && url.hash === '#' + id) {
                        // Fechar a secao que estava no hash: limpa o hash
                        // pra URL nao mentir sobre o estado da pagina.
                        // Usa pathname+search pra evitar '#' residual que
                        // alguns browsers deixam ao setar url.hash=''.
                        const cleanUrl = url.pathname + url.search;
                        window.history.replaceState(window.history.state, '', cleanUrl);
                    }
                } catch (_) { /* IE legacy / sandbox: ignora */ }
            });
        });
    }

    function initCollapsibles() {
        if (typeof document === 'undefined') return;
        _attachToggleHandlers();

        // Print: forca abrir tudo antes do navegador serializar a pagina,
        // restaura ao acabar. _printing flag impede que os toggles
        // programaticos disparem tracking ou alterem o hash.
        const _printSnapshot = new WeakMap();
        window.addEventListener('beforeprint', () => {
            _printing = true;
            _allDetails().forEach((d) => {
                _printSnapshot.set(d, d.open);
                d.open = true;
            });
        });
        window.addEventListener('afterprint', () => {
            _allDetails().forEach((d) => {
                if (_printSnapshot.has(d)) {
                    d.open = _printSnapshot.get(d);
                }
            });
            // O evento 'toggle' de <details> eh fired async (queue task,
            // nao sincrono), entao os toggles do restore acima ainda
            // estao pendentes neste ponto. Adiar o clear pra proxima
            // task garante que os handlers vejam _printing=true e
            // suprimam o tracking + hash sync espurio.
            setTimeout(() => { _printing = false; }, 0);
        });
    }

    window.initCollapsibles = initCollapsibles;
})();
