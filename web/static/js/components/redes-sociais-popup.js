// === components/redes-sociais-popup.js ===
// Popup once-per-user pra convidar a seguir as redes sociais
// (@transparencia_pb no Instagram + @transparenci_pb no X). Tambem
// captura clicks nos CTAs estaticos do footer e da pagina /caso/<slug>
// pra emitir o mesmo evento `redes-clique` com origem distinta.
//
// Por que existe:
//   - Newsletters/feeds RSS sao baixa-fricao mas tem baixa taxa de
//     descoberta. Botoes estaticos no footer atingem 100% das paginas
//     mas convertem ~1% por discoverability ambiental.
//   - Um popup once-per-user calibrado pra trigger DEPOIS de engagement
//     real (30s OU scroll 50%) eleva conversao sem ser intrusivo
//     porque so aparece pra quem ja demonstrou interesse no conteudo.
//
// Trigger:
//   - Pelo menos um dos: (a) 30s na pagina E aba visivel, (b) scroll
//     50% da pagina. O que vier primeiro.
//   - Skip em paginas administrativas/informativas (/contato, /sobre,
//     /glossario) — sao tipicamente paginas de saida/forms.
//   - Skip se o user ja viu/fechou o popup (localStorage dedup).
//   - Skip se ha dialog stack aberta (#empresa-dialog open) — nao
//     interromper exploracao.
//
// Eventos Umami emitidos:
//   redes-popup-mostrado    - {trigger: 'tempo'|'scroll'}
//   redes-popup-dispensado  - {via: 'fechar'|'mais-tarde'|'nao-mostrar'}
//   redes-clique            - {rede: 'instagram'|'x', origem: 'popup'|'footer'|'caso'}
//
// Dedup:
//   - localStorage['tpb.redes_popup'] = 'shown' | 'dismissed' apos
//     qualquer interacao do user com o popup. 'shown' eh setado no
//     dispatch pra evitar re-aparecer se user navegar antes de fechar.
//   - sessionStorage fallback pra browsers em modo privado onde
//     localStorage eh efemero (ou indisponivel).
//
// Implementacao: nao usa <md-dialog> dedicado pra evitar carregar mais
// 1 componente MWC. O HTML do popup eh injetado on-demand no body
// com classe .redes-popup-overlay (CSS gerencia visibility). Funciona
// sem upgrade do bundle MWC — usavel em fallback path tambem.

(function () {
    'use strict';

    const STORAGE_KEY = 'tpb.redes_popup';
    const TIMER_MS = 30000;
    const SCROLL_PCT = 50;

    // Whitelist: paginas onde o popup eh apropriado mostrar.
    // Conteudo investigativo + descoberta de cidades — onde user
    // chegou via SEO/share e pode valorar follow.
    function _popupAllowedOnPath(path) {
        return (
            path === '/' ||
            path === '/index' ||
            path === '/mapa' ||
            path.startsWith('/cidade/') ||
            path.startsWith('/empresa/') ||
            path.startsWith('/caso/')
        );
    }

    function _alreadyShown() {
        try {
            if (localStorage.getItem(STORAGE_KEY)) return true;
        } catch (_) { /* private mode */ }
        try {
            if (sessionStorage.getItem(STORAGE_KEY)) return true;
        } catch (_) { /* fallback also unavailable */ }
        return false;
    }

    function _markShown(state) {
        // state: 'shown' (apareceu mas nao dispensou explicito) ou
        // 'dismissed' (user fechou). Em ambos os casos nao aparece de
        // novo. Mantemos a distincao pra futuras analises de funnel.
        try { localStorage.setItem(STORAGE_KEY, String(state || 'shown')); } catch (_) {}
        try { sessionStorage.setItem(STORAGE_KEY, String(state || 'shown')); } catch (_) {}
    }

    function _dialogStackOpen() {
        const d = document.getElementById('empresa-dialog');
        return !!(d && d.hasAttribute('open'));
    }

    // Track click em qualquer CTA de rede social (footer, popup, /caso/).
    // Usado via delegacao no document — captura cliques em links com
    // [data-rede-social] sem precisar attach handler em cada elemento.
    //
    // Mobile deep-linking: a href fica HTTPS (acessivel pra right-click,
    // copy-link, share, SEO crawlers, leitores de tela). No mobile,
    // interceptamos o click e tentamos abrir o app via URL scheme
    // (instagram://, twitter://) com fallback automatico pra HTTPS apos
    // 1.5s caso o app nao esteja instalado. Detectamos "app abriu" via
    // visibilitychange -> hidden (a aba perdeu foco porque o SO trocou
    // pro app). Se nao houver visibilitychange em 1.5s, assumimos que o
    // scheme falhou e abrimos a URL web em nova aba.
    const SCHEME_FALLBACK_MS = 1500;

    function _isMobileUA() {
        return /Android|iPhone|iPad|iPod/.test(navigator.userAgent || '');
    }

    function _schemeFor(rede) {
        // Schemes oficiais reconhecidos pelos apps. Instagram aceita
        // `instagram://user?username=X`. X (rebrand do Twitter) ainda
        // honra o scheme `twitter://user?screen_name=X` na versao
        // mobile pra back-compat.
        if (rede === 'instagram') return 'instagram://user?username=transparencia_pb';
        if (rede === 'x') return 'twitter://user?screen_name=transparenci_pb';
        return null;
    }

    function _tryOpenAppThenFallback(rede, webUrl) {
        const scheme = _schemeFor(rede);
        if (!scheme) {
            // Sem scheme conhecido — segue navegacao web default.
            window.open(webUrl, '_blank', 'noopener');
            return;
        }

        let fallbackFired = false;
        const tStart = Date.now();

        function onVisHidden() {
            if (document.visibilityState === 'hidden') {
                // App abriu (browser perdeu foco). Cancela fallback e
                // remove listener pra nao re-disparar em alt-tab depois.
                fallbackFired = true;
                clearTimeout(fallbackTimer);
                document.removeEventListener('visibilitychange', onVisHidden);
            }
        }

        const fallbackTimer = setTimeout(() => {
            if (fallbackFired) return;
            // Verifica se passou tempo suficiente — se o user backgrounded
            // a aba manualmente (mensagem, push), tStart->now ficaria
            // baixo e poderiamos falsamente assumir que foi tudo certo.
            // Aqui ja se passou ~SCHEME_FALLBACK_MS entao OK assumir
            // que o scheme falhou e abrir fallback.
            if (Date.now() - tStart >= SCHEME_FALLBACK_MS - 100) {
                document.removeEventListener('visibilitychange', onVisHidden);
                window.open(webUrl, '_blank', 'noopener');
            }
        }, SCHEME_FALLBACK_MS);

        document.addEventListener('visibilitychange', onVisHidden);

        // Dispara o scheme. Em iOS Safari sem app, exibe alerta "Cannot
        // open page" — tentamos minimizar via timeout curto + abrir
        // fallback rapido. Em Android Chrome sem app, scheme falha
        // silenciosamente e o fallback dispara.
        try {
            window.location.href = scheme;
        } catch (_) {
            clearTimeout(fallbackTimer);
            window.open(webUrl, '_blank', 'noopener');
        }
    }

    function _attachClickTracking() {
        document.addEventListener('click', (e) => {
            const link = e.target.closest('[data-rede-social]');
            if (!link) return;
            const rede = link.getAttribute('data-rede-social');
            const origem = link.getAttribute('data-rede-origem') || 'desconhecido';
            if (typeof trackEvent === 'function') {
                trackEvent('redes-clique', { rede, origem });
            }
            // Se for click do popup, marca como dismissed (user converteu).
            if (origem === 'popup') {
                _markShown('dismissed');
                _hidePopup();
            }
            // No mobile, intercepta pra tentar abrir o app nativo. No
            // desktop, deixa o click default acontecer (target=_blank no
            // <a> abre HTTPS em nova aba).
            if (_isMobileUA()) {
                const webUrl = link.getAttribute('href');
                if (webUrl) {
                    e.preventDefault();
                    _tryOpenAppThenFallback(rede, webUrl);
                }
            }
        }, true); // capture phase pra rodar antes de outros handlers
    }

    // Markup do popup. Inline SVG icons (Instagram + X) — sem dependencia
    // externa, ~250 bytes cada gzippeed. SVG embebido tambem evita FOUC.
    function _popupHTML() {
        return [
            '<div class="redes-popup-backdrop" data-redes-popup-backdrop aria-hidden="true"></div>',
            '<div class="redes-popup" role="dialog" aria-modal="true" aria-labelledby="redes-popup-title" tabindex="-1">',
            '  <button type="button" class="redes-popup-close" aria-label="Fechar" data-redes-popup-close>',
            '    <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" fill="currentColor">',
            '      <path d="M6.4 5L5 6.4 10.6 12 5 17.6 6.4 19 12 13.4 17.6 19 19 17.6 13.4 12 19 6.4 17.6 5 12 10.6z"/>',
            '    </svg>',
            '  </button>',
            '  <h3 class="redes-popup-title" id="redes-popup-title">Acompanhe novos casos</h3>',
            '  <p class="redes-popup-text">Investigacoes, novos relatorios e cruzamentos de dados publicos da Paraiba. Sem spam.</p>',
            '  <div class="redes-popup-buttons">',
            '    <a class="redes-btn redes-btn-ig" href="https://instagram.com/transparencia_pb" target="_blank" rel="noopener" data-rede-social="instagram" data-rede-origem="popup">',
            '      <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" fill="currentColor">',
            '        <path d="M12 2.16c3.2 0 3.58.01 4.85.07 1.17.05 1.8.25 2.23.41.56.22.96.48 1.38.9.42.42.68.82.9 1.38.16.42.36 1.06.41 2.23.06 1.27.07 1.64.07 4.85s-.01 3.58-.07 4.85c-.05 1.17-.25 1.8-.41 2.23-.22.56-.48.96-.9 1.38-.42.42-.82.68-1.38.9-.42.16-1.06.36-2.23.41-1.27.06-1.64.07-4.85.07s-3.58-.01-4.85-.07c-1.17-.05-1.8-.25-2.23-.41-.56-.22-.96-.48-1.38-.9-.42-.42-.68-.82-.9-1.38-.16-.42-.36-1.06-.41-2.23C2.17 15.58 2.16 15.21 2.16 12s.01-3.58.07-4.85c.05-1.17.25-1.8.41-2.23.22-.56.48-.96.9-1.38.42-.42.82-.68 1.38-.9.42-.16 1.06-.36 2.23-.41C8.42 2.17 8.79 2.16 12 2.16zm0 1.95c-3.15 0-3.5.01-4.72.07-1.14.05-1.76.24-2.18.4-.55.21-.94.47-1.35.88-.41.41-.67.8-.88 1.35-.16.42-.35 1.04-.4 2.18-.06 1.22-.07 1.57-.07 4.72s.01 3.5.07 4.72c.05 1.14.24 1.76.4 2.18.21.55.47.94.88 1.35.41.41.8.67 1.35.88.42.16 1.04.35 2.18.4 1.22.06 1.57.07 4.72.07s3.5-.01 4.72-.07c1.14-.05 1.76-.24 2.18-.4.55-.21.94-.47 1.35-.88.41-.41.67-.8.88-1.35.16-.42.35-1.04.4-2.18.06-1.22.07-1.57.07-4.72s-.01-3.5-.07-4.72c-.05-1.14-.24-1.76-.4-2.18-.21-.55-.47-.94-.88-1.35-.41-.41-.8-.67-1.35-.88-.42-.16-1.04-.35-2.18-.4-1.22-.06-1.57-.07-4.72-.07zM12 7.38a4.62 4.62 0 1 1 0 9.24 4.62 4.62 0 0 1 0-9.24zm0 1.95a2.67 2.67 0 1 0 0 5.34 2.67 2.67 0 0 0 0-5.34zm5.86-2.16a1.08 1.08 0 1 1-2.16 0 1.08 1.08 0 0 1 2.16 0z"/>',
            '      </svg>',
            '      <span>Instagram</span>',
            '    </a>',
            '    <a class="redes-btn redes-btn-x" href="https://x.com/transparenci_pb" target="_blank" rel="noopener" data-rede-social="x" data-rede-origem="popup">',
            '      <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" fill="currentColor">',
            '        <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24h-6.66l-5.214-6.817-5.967 6.817H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>',
            '      </svg>',
            '      <span>X (Twitter)</span>',
            '    </a>',
            '  </div>',
            '  <div class="redes-popup-actions">',
            '    <button type="button" class="redes-popup-dismiss" data-redes-popup-dismiss="nao-mostrar">Nao mostrar mais</button>',
            '  </div>',
            '</div>',
        ].join('');
    }

    let _wrapper = null;

    function _ensureWrapper() {
        if (_wrapper && document.body.contains(_wrapper)) return _wrapper;
        _wrapper = document.createElement('div');
        _wrapper.className = 'redes-popup-overlay';
        _wrapper.setAttribute('hidden', '');
        _wrapper.innerHTML = _popupHTML();
        document.body.appendChild(_wrapper);

        const close = () => _dismissPopup('fechar');
        _wrapper.querySelector('[data-redes-popup-close]').addEventListener('click', close);
        _wrapper.querySelector('[data-redes-popup-backdrop]').addEventListener('click', close);
        _wrapper.querySelector('[data-redes-popup-dismiss]').addEventListener('click', () => {
            _dismissPopup('nao-mostrar');
        });
        // Escape pra fechar
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && !_wrapper.hasAttribute('hidden')) {
                _dismissPopup('fechar');
            }
        });
        return _wrapper;
    }

    function _hidePopup() {
        if (!_wrapper) return;
        _wrapper.setAttribute('hidden', '');
        document.body.classList.remove('redes-popup-open');
    }

    function _dismissPopup(via) {
        _markShown('dismissed');
        _hidePopup();
        if (typeof trackEvent === 'function') {
            trackEvent('redes-popup-dispensado', { via: String(via || 'fechar') });
        }
    }

    let _shown = false;

    function _showPopup(trigger) {
        if (_shown) return;
        if (_dialogStackOpen()) return; // nao interromper exploracao
        _shown = true;
        _markShown('shown');
        const w = _ensureWrapper();
        w.removeAttribute('hidden');
        document.body.classList.add('redes-popup-open');
        // Foca no dialog pra acessibilidade
        try { w.querySelector('.redes-popup').focus(); } catch (_) {}
        if (typeof trackEvent === 'function') {
            trackEvent('redes-popup-mostrado', { trigger: String(trigger || 'desconhecido') });
        }
    }

    function _initPopupTriggers() {
        if (_alreadyShown()) return;
        if (!_popupAllowedOnPath(window.location.pathname)) return;

        // Tempo: 30s de pagina visivel. Desconta tempo em background.
        let visibleSinceMs = performance.now();
        let visibleAccumulatedMs = 0;
        let timerHandle = null;

        function startTimer() {
            if (timerHandle) clearTimeout(timerHandle);
            const remaining = Math.max(0, TIMER_MS - visibleAccumulatedMs);
            timerHandle = setTimeout(() => {
                _showPopup('tempo');
            }, remaining);
        }

        function pauseTimer() {
            if (timerHandle) {
                clearTimeout(timerHandle);
                timerHandle = null;
            }
            visibleAccumulatedMs += performance.now() - visibleSinceMs;
        }

        document.addEventListener('visibilitychange', () => {
            if (_shown) return;
            if (document.visibilityState === 'hidden') {
                pauseTimer();
            } else {
                visibleSinceMs = performance.now();
                startTimer();
            }
        });

        if (document.visibilityState === 'visible') startTimer();
        else pauseTimer();

        // Scroll 50%
        let scrollTicking = false;
        function onScroll() {
            if (_shown || scrollTicking) return;
            scrollTicking = true;
            requestAnimationFrame(() => {
                scrollTicking = false;
                const doc = document.documentElement;
                const total = Math.max(doc.scrollHeight, doc.offsetHeight, 1);
                if (total <= window.innerHeight * 1.2) return; // pagina pequena, scroll trivial
                const scrolled = (window.scrollY || window.pageYOffset || 0) + window.innerHeight;
                const pct = (scrolled / total) * 100;
                if (pct >= SCROLL_PCT) {
                    pauseTimer();
                    _showPopup('scroll');
                }
            });
        }
        window.addEventListener('scroll', onScroll, { passive: true });
    }

    function initRedesSociaisPopup() {
        _attachClickTracking();
        _initPopupTriggers();
    }

    window.initRedesSociaisPopup = initRedesSociaisPopup;
})();
