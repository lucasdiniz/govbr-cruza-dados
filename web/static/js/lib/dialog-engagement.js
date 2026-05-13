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
    let active = null;   // { tipo, t0, tabsCount, maxScrollPct }
    let scrollEl = null;
    let scrollTicking = false;

    function updateMaxScroll() {
        scrollTicking = false;
        if (!active || !scrollEl) return;
        const total = Math.max(scrollEl.scrollHeight, 1);
        const view = scrollEl.clientHeight;
        if (total <= view) {
            // Conteudo cabe no viewport do dialog — considera 100%.
            if (active.maxScrollPct < 100) active.maxScrollPct = 100;
            return;
        }
        const scrolled = scrollEl.scrollTop + view;
        const pct = Math.min(100, Math.round((scrolled / total) * 100));
        if (pct > active.maxScrollPct) active.maxScrollPct = pct;
    }

    function onDialogScroll() {
        if (scrollTicking) return;
        scrollTicking = true;
        requestAnimationFrame(updateMaxScroll);
    }

    function flush(drilledTo) {
        if (!active) return;
        const dwellMs = Math.max(0, Math.round(performance.now() - active.t0));
        // Captura ultima leitura do scroll antes de emitir
        updateMaxScroll();
        if (typeof trackEvent === 'function') {
            const props = {
                tipo: active.tipo,
                dwell_ms: dwellMs,
                tabs_visitadas: active.tabsCount,
                scroll_max_pct: active.maxScrollPct,
            };
            if (drilledTo) props.drilled_to = drilledTo;
            trackEvent('dialog-fechado', props);
        }
        active = null;
    }

    function start(tipo) {
        // Inicializa scroll listener no body do empresa-dialog. O elemento
        // eh estavel ao longo de drilldowns (so o innerHTML muda), entao
        // attach uma vez e reaproveita.
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
            tabsCount: 1, // tab inicial sempre conta
            maxScrollPct: 0,
        };
        // Faz uma leitura imediata pra capturar conteudos curtos
        // (que cabem na viewport, scroll_max=100 sem o usuario rolar).
        updateMaxScroll();
    }

    function init() {
        if (typeof document === 'undefined') return;

        document.addEventListener('tpb:tracked', (e) => {
            const detail = e && e.detail;
            if (!detail || !detail.name) return;
            const name = detail.name;
            const props = detail.props || {};

            if (name === 'dialog-aberto' && props.tipo) {
                // Drilldown: dialog ja estava aberto e usuario abriu outro
                // tipo. Fecha a sessao anterior marcando drilled_to.
                if (active) flush(String(props.tipo));
                start(props.tipo);
                return;
            }
            if (name === 'dialog-tab-change' && active) {
                active.tabsCount += 1;
                return;
            }
        });

        // Quando o md-dialog efetivamente fecha (post-animacao), emitimos
        // o evento final. Esperamos pelo MD3 ready pra garantir que o
        // 'closed' event listener nao seja conectado antes do upgrade.
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
