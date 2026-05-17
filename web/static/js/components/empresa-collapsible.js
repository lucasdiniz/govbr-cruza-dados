// === components/empresa-collapsible.js ===
// Hook leve pras secoes colapsaveis (<details>) das paginas /empresa.
//
// Tres responsabilidades:
//   1. Deep-link via hash: se URL bate em /empresa/...#pgfn, abre a secao
//      correspondente automaticamente + scroll into view.
//      OBS: clicks em <a href="#pgfn"> dentro da pagina sao tratados por
//      anchor-auto-expand.js (que faz preventDefault e nao dispara
//      hashchange). A integracao com <details> esta em
//      lib/expand-context.js — qualquer atualizacao na convencao
//      "abrir details via deep-link" precisa tocar tambem aquele arquivo.
//   2. Atualiza hash da URL quando o user abre/fecha uma secao (history
//      replace, nao push — nao polui o stack do back-button). Fechar a
//      secao corrente limpa o hash pra URL nao mentir sobre o estado.
//   3. Tracking Umami opcional: dispara `empresa-secao-toggle` com
//      {section, action} quando user interage. Util pra entender quais
//      secoes investigativas mais geram interesse. Toggles programaticos
//      (print) sao suprimidos pela flag _printing.
//
// Sem JS, o <details> nativo ja funciona normal (toggle por click no
// summary, foco com Tab, ativacao com Space/Enter). Este helper apenas
// adiciona conveniencias de URL/analytics.

(function () {
    'use strict';

    // Flag pra suprimir hash sync + tracking durante print (beforeprint
    // forca abrir tudo, gerando N toggle events programaticos). Sem
    // isso, cada print poluiria o Umami com 6+ events espurios e
    // poderia deixar o hash apontando pra ultima secao aberta.
    let _printing = false;

    function _allDetails() {
        return Array.from(document.querySelectorAll('.empresa-collapsible-details[data-collapsible-id]'));
    }

    function _openFromHash() {
        const hash = (window.location.hash || '').replace(/^#/, '');
        if (!hash) return;
        const target = document.querySelector(
            '.empresa-collapsible-details[data-collapsible-id="' + CSS.escape(hash) + '"]'
        );
        if (!target) return;
        if (!target.open) target.open = true;
        // Scroll suave pra section pos open (sem ser instantaneo). Aguarda
        // 1 raf pro layout do conteudo expandido estabilizar antes de
        // calcular o offset.
        requestAnimationFrame(() => {
            const section = target.closest('section.empresa-section');
            if (section && typeof section.scrollIntoView === 'function') {
                section.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        });
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
                    trackEvent('empresa-secao-toggle', {
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
                        // Sem isso, refresh reabriria a secao que o user
                        // explicitamente fechou (e share-link reabriria
                        // pro destinatario).
                        url.hash = '';
                        // history.replaceState com URL sem hash mantem o
                        // '#' no final em alguns browsers; usar pathname+
                        // search explicito pra remover totalmente.
                        const cleanUrl = url.pathname + url.search;
                        window.history.replaceState(window.history.state, '', cleanUrl);
                    }
                } catch (_) { /* IE legacy / sandbox: ignora */ }
            });
        });
    }

    function initEmpresaCollapsibles() {
        if (typeof document === 'undefined') return;
        _attachToggleHandlers();
        // hashchange durante navegacao SPA-like ou click em <a href="#id">.
        window.addEventListener('hashchange', _openFromHash);
        // Estado inicial: se a URL ja tem #id, abre.
        _openFromHash();

        // Print: forca abrir tudo antes do navegador serializar a pagina,
        // restaura ao acabar. CSS sozinho nao consegue forcar <details>
        // colapsada a mostrar conteudo (eh user-agent shadow DOM).
        // _printing flag impede que os toggles programaticos disparem
        // tracking ou alterem o hash.
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
            // Limpar flag DEPOIS do restore pra que os toggles do restore
            // tambem sejam suprimidos.
            _printing = false;
        });
    }

    window.initEmpresaCollapsibles = initEmpresaCollapsibles;
})();
