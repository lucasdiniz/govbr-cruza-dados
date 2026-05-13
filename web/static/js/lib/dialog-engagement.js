// === lib/dialog-engagement.js ===
// Dispara evento `dialog-fechado` pareado com `dialog-aberto`, medindo
// engagement REAL por dialog: dwell time, tabs exploradas, profundidade
// do scroll. Sem este evento, so sabemos "abriu" — nao "leu/explorou".
//
// Como funciona:
//   1. Hook em document `tpb:tracked` (dispatchado pelo trackEvent em
//      lib/umami-track.js).
//   2. Quando vem `dialog-aberto` com props.tipo, comecamos a sessao:
//        { tipo, t0, tabsCount, maxScrollPct }
//      Se ja havia sessao ativa (drilldown — usuario abriu outro tipo
//      de dialog SEM fechar o md-dialog), fechamos a sessao anterior
//      com `drilled_to = props.tipo` e iniciamos nova.
//   3. Quando vem `dialog-tab-change`, incrementamos tabsCount. Nao
//      armazenamos os nomes das tabs (privacidade + payload menor);
//      apenas a quantidade DISTINTA de tabs visitadas alem da inicial.
//   4. Scroll listener no #empresa-dialog .dialog-body atualiza
//      maxScrollPct. A dialog-body eh reutilizada entre drilldowns —
//      resetamos maxScrollPct a cada novo dialog-aberto.
//   5. Quando o md-dialog fecha de verdade (event `closed`), emitimos
//      o evento final SEM drilled_to.
//
// Notas:
//   - tabs_visitadas comeca em 1 (tab inicial) e aumenta com cada
//     dialog-tab-change. Se o usuario nunca trocar de tab, sai 1.
//   - dwell_ms eh tempo absoluto desde o open ate o close/drilldown.
//     Diferente do pagina-saida, NAO descontamos visibility — dialogs
//     sao sessoes interativas curtas e descontar background piora a
//     leitura (e dialog raramente fica aberto com aba inativa).
//   - scroll_max_pct soma o scroll DA DIALOG-BODY apenas. Scroll da
//     pagina por baixo eh medido em pagina-saida separadamente.
//   - O dialog #empresa-dialog hospeda 5 tipos diferentes (fornecedor,
//     servidor, empenho, licitacao, heatmap). Usamos o tipo capturado
//     no dialog-aberto, nao o id do md-dialog.

(function () {
    let active = null;   // { tipo, t0, tabsVisited:Set, maxScrolledPx, initialTabLabel? }
    let scrollEl = null;
    let scrollTicking = false;
    let _inited = false;

    function readScrolledPx() {
        if (!scrollEl) return 0;
        return scrollEl.scrollTop + scrollEl.clientHeight;
    }

    function updateMaxScroll() {
        scrollTicking = false;
        if (!active || !scrollEl) return;
        const px = readScrolledPx();
        if (px > active.maxScrolledPx) active.maxScrolledPx = px;
    }

    function onDialogScroll() {
        if (scrollTicking) return;
        scrollTicking = true;
        requestAnimationFrame(updateMaxScroll);
    }

    // Computa scroll_max_pct SO no flush(), nao no start(). Isso evita
    // o bug de "travar em 100%" quando o body comeca como placeholder
    // ("Carregando...") que cabe na viewport: se calculassemos no
    // start() e setassemos maxScrollPct=100, o valor nao reduziria
    // quando o conteudo real chegasse (que pode ser muito maior).
    // Avaliamos AGORA usando scrollHeight ATUAL.
    function computeScrollMaxPct() {
        if (!scrollEl || !active) return 0;
        const total = Math.max(scrollEl.scrollHeight, 1);
        const view = scrollEl.clientHeight;
        if (total <= view) return 100;
        const px = Math.max(active.maxScrolledPx, readScrolledPx());
        return Math.min(100, Math.round((px / total) * 100));
    }

    function flush(drilledTo) {
        if (!active) return;
        const dwellMs = Math.max(0, Math.round(performance.now() - active.t0));
        // tabs_visitadas conta distintas (initialTabLabel + Set de
        // tabs `para`). Se nunca trocou de tab, sai 1.
        const tabsCount = 1 + active.tabsVisited.size;
        if (typeof trackEvent === 'function') {
            const props = {
                tipo: active.tipo,
                dwell_ms: dwellMs,
                tabs_visitadas: tabsCount,
                scroll_max_pct: computeScrollMaxPct(),
            };
            if (drilledTo) props.drilled_to = drilledTo;
            trackEvent('dialog-fechado', props);
        }
        active = null;
    }

    function start(tipo) {
        if (!scrollEl) {
            const dialog = document.getElementById('empresa-dialog');
            const body = dialog ? dialog.querySelector('.dialog-body') : null;
            if (body) {
                scrollEl = body;
                scrollEl.addEventListener('scroll', onDialogScroll, { passive: true });
            }
        }
        active = {
            tipo: String(tipo || 'unknown'),
            t0: performance.now(),
            tabsVisited: new Set(),
            maxScrolledPx: 0,
            initialTabLabel: null,
        };
    }

    function init() {
        if (typeof document === 'undefined') return;
        // Idempotencia: HMR / hot-reload / chamadas duplicadas de
        // bootstrap podem invocar initDialogEngagement() multiplas
        // vezes. Sem este guard duplicariamos listeners (tabs contadas
        // 2x, dialog-fechado disparado 2x por close).
        if (_inited) return;
        _inited = true;

        document.addEventListener('tpb:tracked', (e) => {
            const detail = e && e.detail;
            if (!detail || !detail.name) return;
            const name = detail.name;
            const props = detail.props || {};

            if (name === 'dialog-aberto' && props.tipo) {
                if (active) flush(String(props.tipo));
                start(props.tipo);
                return;
            }
            if (name === 'dialog-restored' && props.tipo) {
                // Back-button: flush atual marcando como 'back-<tipo>'
                // pra distinguir nas metricas de drilldown puro.
                if (active) flush('back-' + String(props.tipo));
                start(props.tipo);
                return;
            }
            if (name === 'dialog-tab-change' && active) {
                const de = typeof props.de === 'string' ? props.de.trim() : '';
                const para = typeof props.para === 'string' ? props.para.trim() : '';
                if (!active.initialTabLabel && de) active.initialTabLabel = de;
                if (!active.initialTabLabel && !de && para) active.initialTabLabel = para;
                if (para && para !== active.initialTabLabel) active.tabsVisited.add(para);
                return;
            }
        });

        const attachClose = () => {
            const dialog = document.getElementById('empresa-dialog');
            if (!dialog) return;
            dialog.addEventListener('closed', () => { flush(null); });
        };
        if (typeof window.whenMD3Ready === 'function') {
            window.whenMD3Ready(attachClose);
        } else if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', attachClose);
        } else {
            attachClose();
        }
    }

    window.initDialogEngagement = init;
})();
