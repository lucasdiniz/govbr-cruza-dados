// === components/tce-pdf-viewer.js ===
// ADR-0014 — Visualizador de PDFs do DOE-TCE-PB.
//
// Cada botao .tce-view-btn carrega data-tce-hash + data-tce-label.
// Ao clicar:
//   1. Aguarda upgrade dos custom elements (whenMD3Ready).
//   2. Atualiza titulo e src do iframe apontando pra /api/tce-pb/decisao/<hash>.pdf
//      (proxy local que reescreve Content-Disposition pra inline — ver
//      web/routes/tce_pb.py).
//   3. Wireup do botao "Baixar" e do link "Abrir no TCE-PB".
//   4. dispatch evento Umami 'tce-pdf-view' com prefixo do hash (anonimo).
//   5. Ao fechar o dialog, limpa src do iframe (libera memoria do PDF.js
//      do browser).
function initTcePdfViewer() {
    const dialog = document.getElementById('tce-pdf-dialog');
    if (!dialog) return;
    const buttons = document.querySelectorAll('.tce-view-btn');
    if (!buttons.length) return;

    const ready = typeof window.whenMD3Ready === 'function'
        ? window.whenMD3Ready()
        : Promise.resolve();

    ready.then(() => {
        const frame   = document.getElementById('tce-pdf-frame');
        const title   = document.getElementById('tce-pdf-title');
        const btnDl   = document.getElementById('tce-pdf-download');
        const linkTce = document.getElementById('tce-pdf-open-tce');
        const btnCls  = document.getElementById('tce-pdf-close');
        if (!frame || !title || !btnDl || !linkTce) return;

        buttons.forEach((btn) => {
            btn.addEventListener('click', () => {
                const h = btn.dataset.tceHash;
                const label = btn.dataset.tceLabel || 'Decisao TCE-PB';
                if (!h || !/^[a-f0-9]{32}$/.test(h)) return;

                title.textContent = label;
                // #view=FitH pede ao viewer nativo do browser pra abrir
                // ajustado a largura. Funciona em Chromium e Firefox.
                frame.src = `/api/tce-pb/decisao/${h}.pdf#view=FitH`;

                btnDl.onclick = () => {
                    window.location.href = `/api/tce-pb/decisao/${h}.pdf?download=1`;
                };
                linkTce.href = `https://publicacao.tce.pb.gov.br/${h}`;

                if (dialog.show) {
                    dialog.show();
                } else {
                    dialog.setAttribute('open', '');
                }

                if (typeof trackEvent === 'function') {
                    trackEvent('tce-pdf-view', { hash: h.slice(0, 8) });
                }
            });
        });

        // Limpa src ao fechar (libera memoria; evita PDF renderizado
        // permanecer em background carregando).
        const cleanup = () => {
            if (frame.src && frame.src !== 'about:blank') {
                frame.src = 'about:blank';
            }
        };
        dialog.addEventListener('close', cleanup);
        dialog.addEventListener('closed', cleanup);
        if (btnCls) {
            btnCls.addEventListener('click', () => {
                if (dialog.close) dialog.close();
                else dialog.removeAttribute('open');
            });
        }
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initTcePdfViewer);
} else {
    initTcePdfViewer();
}
