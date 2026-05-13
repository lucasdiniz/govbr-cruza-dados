// === lib/page-engagement.js ===
// Dispara evento Umami `pagina-saida` UMA UNICA VEZ por page load quando
// a aba fica oculta (visibilitychange -> hidden) ou no pagehide. Mede:
//
//   tempo_ms        - tempo total entre pageshow/load e o disparo, em ms
//                     (apenas enquanto a aba esteve visivel; descontamos
//                     periodos em background quando o usuario alterna
//                     de aba e volta)
//   scroll_max_pct  - profundidade maxima do scroll alcancada (0-100,
//                     arredondado pra inteiro). Usa o mesmo calculo do
//                     scroll-deep mas reportando o valor continuo.
//   pagina          - mesma classificacao do scroll-deep
//                     (cidade|empresa|caso|home|mapa|sobre|glossario|outro)
//
// Por que `pagina-saida` E NAO um proxy de scroll-deep:
//   - scroll-deep dispara em marcos discretos (50/75/100); user que para
//     em 65% nao gera evento. pagina-saida sempre reporta o maximo real.
//   - Sem pagina-saida, "tempo na pagina" tem que ser inferido por
//     diferenca de pageviews — impreciso e nao funciona pra visitas de
//     pagina unica (bounces).
//   - Combinado com scroll-deep + pagina-saida, a tabela Umami fica:
//        bounce real (sem scroll, baixo tempo)
//        leu rapidamente (alto scroll, baixo tempo)
//        leu profundamente (alto scroll, alto tempo)
//        abriu e largou aberto (baixo scroll, alto tempo — distrai)
//
// Entrega:
//   - Usa `pagehide` (fire-and-forget) como caminho primario quando
//     disponivel. visibilitychange -> hidden eh o caminho mais confiavel
//     em mobile (especialmente iOS Safari, que nao garante pagehide
//     consistente quando app vai pro background).
//   - umami.track usa fetch() com keepalive=true no v3, entao envia
//     mesmo durante unload. Sem keepalive, o evento poderia ser
//     cancelado pelo browser ao fechar a aba.
//   - Dedup: depois do primeiro disparo, listeners ficam no-op pra nao
//     dobrar o evento (visibilitychange + pagehide podem ambos fire em
//     sequencia em alguns browsers).
//
// Whitelist: mesma do scroll-deep — paginas onde "tempo na pagina" eh um
// sinal de leitura genuina. Em listings/forms efêmeros (outro), pular.

function _pageEngagementKind() {
    const p = window.location.pathname;
    if (p.startsWith('/cidade/')) return 'cidade';
    if (p.startsWith('/empresa/') && p.split('/').length >= 4) return 'empresa-municipio';
    if (p.startsWith('/empresa/')) return 'empresa';
    if (p.startsWith('/caso/')) return 'caso';
    if (p === '/' || p === '/index') return 'home';
    if (p === '/mapa') return 'mapa';
    if (p === '/sobre') return 'sobre';
    if (p === '/glossario') return 'glossario';
    return 'outro';
}

function initPageEngagement() {
    const pagina = _pageEngagementKind();
    if (pagina === 'outro') return;

    let maxScrollPct = 0;
    let visibleSinceMs = performance.now();
    let totalVisibleMs = 0;
    // True apos visibilitychange->hidden (o trecho visivel desde visibleSinceMs
    // ja foi somado a totalVisibleMs). False apos visibilitychange->visible ou
    // apos reset de bfcache. Impede double-counting quando fire() eh chamado
    // logo apos o visibilitychange handler — inclui o caso de pagehide sem
    // visibilitychange anterior (bug documentado em iOS Safari).
    let visibleTimeAccounted = false;
    let fired = false;
    let scrollTicking = false;
    let hiddenFireTimer = null;

    const updateScroll = () => {
        scrollTicking = false;
        const doc = document.documentElement;
        const total = Math.max(doc.scrollHeight, doc.offsetHeight, 1);
        if (total <= window.innerHeight) {
            // Pagina cabe na viewport — define scroll_max_pct como 100
            // (o usuario "viu tudo" sem precisar rolar).
            maxScrollPct = 100;
            return;
        }
        const scrolled = (window.scrollY || window.pageYOffset || 0) + window.innerHeight;
        const pct = Math.min(100, Math.round((scrolled / total) * 100));
        if (pct > maxScrollPct) maxScrollPct = pct;
    };

    const onScroll = () => {
        if (scrollTicking) return;
        scrollTicking = true;
        requestAnimationFrame(updateScroll);
    };

    // Captura o scroll maximo inicial (caso a pagina abra no meio via
    // anchor ou deep-link com scroll preservado).
    updateScroll();

    window.addEventListener('scroll', onScroll, { passive: true });

    // Visibility tracking: descontamos periodos em background do tempo
    // total. Quando aba volta a visible, retomamos o relogio.
    document.addEventListener('visibilitychange', () => {
        if (fired) return;
        if (document.visibilityState === 'hidden') {
            totalVisibleMs += performance.now() - visibleSinceMs;
            visibleTimeAccounted = true;
            // Em mobile/iOS Safari, hidden pode ocorrer em transicoes
            // temporarias (share sheet, app switch curto). Atrasamos um
            // pouco e cancelamos se a aba voltar a visible.
            if (hiddenFireTimer) clearTimeout(hiddenFireTimer);
            hiddenFireTimer = setTimeout(() => {
                hiddenFireTimer = null;
                if (!fired && document.visibilityState === 'hidden') fire();
            }, 300);
        } else {
            if (hiddenFireTimer) {
                clearTimeout(hiddenFireTimer);
                hiddenFireTimer = null;
            }
            visibleSinceMs = performance.now();
            visibleTimeAccounted = false;
        }
    });

    // pagehide eh o fallback quando visibilitychange nao dispara antes do
    // unload (bug documentado em alguns cenarios iOS Safari). Recebe o
    // evento pra detectar bfcache (e.persisted=true).
    window.addEventListener('pagehide', (e) => {
        if (hiddenFireTimer) {
            clearTimeout(hiddenFireTimer);
            hiddenFireTimer = null;
        }
        if (!fired) fire();
        // Se a pagina entra no bfcache (e.persisted=true), pode ser restaurada
        // pelo botao Voltar. Reiniciamos o estado pra medir a proxima sessao
        // de engajamento sem carregar os acumuladores da sessao anterior.
        if (e.persisted) resetEngagementState();
    });

    // Restauracao do bfcache (iOS Safari/Chrome back-forward): reinicia o
    // tracking pra medir a sessao de re-visita corretamente.
    window.addEventListener('pageshow', (e) => {
        if (e.persisted) resetEngagementState();
    });

    function resetEngagementState() {
        if (hiddenFireTimer) {
            clearTimeout(hiddenFireTimer);
            hiddenFireTimer = null;
        }
        fired = false;
        maxScrollPct = 0;
        totalVisibleMs = 0;
        visibleTimeAccounted = false;
        visibleSinceMs = performance.now();
        updateScroll();
    }

    function fire() {
        if (fired) return;
        fired = true;
        if (hiddenFireTimer) {
            clearTimeout(hiddenFireTimer);
            hiddenFireTimer = null;
        }
        // Se fire() eh chamado pelo pagehide sem visibilitychange anterior
        // (bug iOS Safari em alguns cenarios de unload), o trecho visivel
        // desde visibleSinceMs ainda nao foi acumulado em totalVisibleMs.
        if (!visibleTimeAccounted) {
            totalVisibleMs += performance.now() - visibleSinceMs;
        }
        // Refresh scroll max uma ultima vez (caso scroll handler ainda
        // estivesse pendente em requestAnimationFrame).
        updateScroll();
        if (typeof trackEvent === 'function') {
            trackEvent('pagina-saida', {
                pagina,
                tempo_ms: Math.round(totalVisibleMs),
                scroll_max_pct: maxScrollPct,
            });
        }
    }
}
