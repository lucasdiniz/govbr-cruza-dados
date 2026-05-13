// === lib/dialog-engagement.js ===
// Dispara evento `dialog-fechado` pareado com `dialog-aberto`, medindo
// engagement REAL por dialog: dwell time, tabs distintas exploradas,
// profundidade do scroll. Sem este evento, so sabemos "abriu" — nao
// "leu/explorou".
//
// Como funciona:
//   1. Hook em document `tpb:tracked` (dispatchado pelo trackEvent em
//      lib/umami-track.js).
//   2. Quando vem `dialog-aberto` com props.tipo, comecamos a sessao:
//        { tipo, t0, tabsVisited:Set, maxScrollPct, initialTabLabel }
//      Se ja havia sessao ativa (drilldown — usuario abriu outro tipo
//      de dialog SEM fechar o md-dialog), fechamos a sessao anterior
//      com `drilled_to = props.tipo` e iniciamos nova.
//   3. Quando vem `dialog-restored` (botao "voltar" do dialog stack),
//      fechamos a sessao atual marcando `drilled_to = 'back-<tipo>'`
//      e iniciamos nova sessao com tipo restaurado.
//      IMPORTANTE: `dialog-nav.js _dialogPop()` dispara dialog-restored
//      ANTES de substituir o body.innerHTML — pra que esse flush leia
//      dimensoes do conteudo que esta saindo, nao do que esta entrando.
//   4. Quando vem `dialog-tab-change`, adicionamos `de` e `para` ao Set
//      de tabs visitadas + capturamos initialTabLabel se ainda nulo.
//      Reportamos `tabs_visitadas = 1 + tabsVisited.size` (1 conta a
//      tab inicial). Se zero tab-changes ocorreram, size=0 e reportamos 1.
//   5. Scroll: tracking PROGRESSIVO de maxScrollPct. updateMaxScroll
//      computa pct usando scrollHeight/clientHeight ATUAIS a cada
//      scroll event e armazena o max. NAO faz calc-at-flush porque:
//        a) Calc-at-close-time: o evento `closed` do md-dialog fire
//           APOS display:none ter sido aplicado, entao scrollHeight=0
//           e clientHeight=0 — calc-at-flush produziria 100 ou 0
//           binario (achado do review: opus-4.7).
//        b) Calc-at-restore-time: em dialog-restored o body.innerHTML
//           ja eh do dialog restaurado quando o evento fire — calc
//           leria dimensoes do nivel errado (achado: gpt-5.5).
//      Como mitigamos as duas: tracking progressivo evita ler dimensoes
//      no momento da flush; valor armazenado eh o max ja computado em
//      momentos validos.
//   6. Para capturar o caso "user abriu conteudo pequeno que cabia na
//      viewport e fechou sem scrollar" (que progressivo nao captura
//      porque nao ha scroll events): adicionamos listener pro evento
//      `close` do md-dialog. Esse evento fire ANTES da animacao de
//      close e ANTES do display:none — dimensions ainda validas. Fazemos
//      uma leitura final que captura 100% quando content fits viewport.
//      Para drilldown/restored, o updateMaxScroll a cada scroll ja
//      capturou o max corretamente.
//   7. No `closed` (post display:none), apenas flushamos o valor ja
//      armazenado. Nao re-medimos.
//
// Idempotencia: `_inited` flag protege contra duplo-init (HMR,
// hot-reload). Re-anexar listeners faria contar tabs em dobro e flushar
// 2x cada dialog-fechado.

(function () {
    let active = null;   // { tipo, t0, tabsVisited:Set, maxScrollPct, initialTabLabel? }
    let scrollEl = null;
    let scrollTicking = false;
    let _inited = false;

    // Atualiza maxScrollPct progressivamente. Computa pct usando
    // scrollHeight/clientHeight CORRENTES (validos enquanto o dialog
    // estiver visivel). Stored max nunca diminui — entao quando o
    // dialog fecha (dimensions=0) o valor preserva o pct medido em
    // momentos validos.
    function updateMaxScroll() {
        scrollTicking = false;
        if (!active || !scrollEl) return;
        const view = scrollEl.clientHeight;
        if (view === 0) return; // dialog hidden — dimensions invalidas
        const total = Math.max(scrollEl.scrollHeight, 1);
        let pct;
        if (total <= view) {
            // Conteudo cabe inteiro na viewport do dialog — user "viu
            // tudo" sem precisar rolar. Mas SO seta 100 se essa for a
            // condicao no momento (nao trava 100 do passado se conteudo
            // crescer e ultrapassar a viewport depois).
            pct = 100;
        } else {
            const scrolled = scrollEl.scrollTop + view;
            pct = Math.min(100, Math.round((scrolled / total) * 100));
        }
        if (pct > active.maxScrollPct) active.maxScrollPct = pct;
    }

    function onDialogScroll() {
        if (scrollTicking) return;
        scrollTicking = true;
        requestAnimationFrame(updateMaxScroll);
    }

    function flush(drilledTo) {
        if (!active) return;
        // Uma ultima leitura: enquanto scrollEl estiver visivel
        // (clientHeight>0), atualiza maxScrollPct. Cobre drilldown
        // (dialog-aberto/restored com body ainda montado) e flushes
        // pre-close (chamados pelo listener 'close' abaixo).
        updateMaxScroll();
        const dwellMs = Math.max(0, Math.round(performance.now() - active.t0));
        const tabsCount = 1 + active.tabsVisited.size;
        if (typeof trackEvent === 'function') {
            const props = {
                tipo: active.tipo,
                dwell_ms: dwellMs,
                tabs_visitadas: tabsCount,
                scroll_max_pct: active.maxScrollPct,
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
            maxScrollPct: 0,
            initialTabLabel: null,
        };
        // Sample inicial deferred: depois de 1 raf o conteudo da primeira
        // renderizacao tipicamente ja foi layoutado. Captura o caso "user
        // abriu dialog com conteudo curto que cabia, fechou sem scrollar"
        // mesmo quando o user fecha muito rapido (antes do listener
        // 'close' do md-dialog chegar a fazer sua leitura).
        requestAnimationFrame(updateMaxScroll);
    }

    function init() {
        if (typeof document === 'undefined') return;
        // Idempotencia: HMR / hot-reload / chamadas duplicadas de
        // bootstrap podem invocar initDialogEngagement() multiplas
        // vezes. Sem este guard duplicariamos listeners.
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
                // Importante: dialog-nav.js emite dialog-restored ANTES
                // de substituir body.innerHTML, entao flush() le
                // dimensoes do conteudo que esta saindo. Depois start()
                // reinicia tracking; quando o body for substituido logo
                // depois, o proximo scroll event do user ja captura
                // pct do novo conteudo corretamente.
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
                // Re-sample apos tab-change: conteudo novo da tab pode
                // ter altura diferente. Aproveita pra capturar 100 se o
                // novo conteudo tambem cabe na viewport.
                requestAnimationFrame(updateMaxScroll);
                return;
            }
        });

        const attachDialogListeners = () => {
            const dialog = document.getElementById('empresa-dialog');
            if (!dialog) return;
            // 'close' (cancelable, pre-animation): fire enquanto dialog
            // AINDA esta visivel — dimensions validas. Fazemos uma
            // ultima leitura pra capturar o caso "user abriu conteudo
            // pequeno que cabia na viewport, fechou sem scroll" (que
            // updateMaxScroll progressivo nao pegaria sem scroll events).
            // NAO chamamos preventDefault — apenas snapshot.
            dialog.addEventListener('close', () => { updateMaxScroll(); });
            // 'closed' (post display:none): dimensions invalidas (0).
            // Apenas flusha o valor ja armazenado, sem re-medir.
            dialog.addEventListener('closed', () => { flush(null); });
        };
        if (typeof window.whenMD3Ready === 'function') {
            window.whenMD3Ready(attachDialogListeners);
        } else if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', attachDialogListeners);
        } else {
            attachDialogListeners();
        }
    }

    window.initDialogEngagement = init;
})();
