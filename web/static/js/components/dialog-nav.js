// === components/dialog-nav.js ===
// ── Dialog navigation stack ─────────────────────────────────────
let _currentMunicipio = '';
const _dialogStack = []; // [{title, html, activePanelId, urlState, tipo}]

// Tipo do dialog atualmente aberto (empenho|servidor|fornecedor|licitacao|
// heatmap). Vazio quando nenhum dialog aberto. Usado pra trackear drill
// chains (ex: dialog-aberto vem com drilled_from='fornecedor' quando user
// abriu um empenho a partir do dialog de fornecedor).
let _currentDialogType = '';

function _dialogPush() {
    const dialog = document.getElementById('empresa-dialog');
    if (!dialog) return;
    const title = dialog.querySelector('.dialog-title').textContent;
    const body = dialog.querySelector('.dialog-body');
    const html = body.innerHTML;
    const activePanelId = body._activeDialogSectionId || body.querySelector('.dialog-tab-panel:not([hidden])')?.id || '';
    // Salva snapshot do URL state atual (antes de a próxima open()
    // chamar _dialogStateApply replaceState com o novo state).
    const urlState = (history.state && history.state.dialogState) ? { ...history.state.dialogState } : null;
    _dialogStack.push({ title, html, activePanelId, urlState, tipo: _currentDialogType });
    dialog.querySelector('.dialog-back').style.visibility = 'visible';
}

function _dialogPop() {
    const dialog = document.getElementById('empresa-dialog');
    if (!dialog || !_dialogStack.length) return;
    const prev = _dialogStack.pop();

    // Engagement tracking: dispara `dialog-restored` ANTES de substituir
    // o body.innerHTML. O listener de dialog-engagement faz flush() das
    // metricas (dwell/scroll/tabs) do tipo atual lendo as dimensions do
    // .dialog-body ainda intactas — i.e. ainda exibindo o conteudo do
    // dialog que estamos saindo. Depois disso o body eh trocado e o
    // listener tambem chama start(prev.tipo) pra reiniciar tracking limpo.
    // Sem essa ordem, flush() leria scrollHeight/clientHeight do conteudo
    // ja restaurado e atribuiria scroll_max errado ao tipo que estamos
    // fechando (achado do review: gpt-5.5).
    _currentDialogType = prev.tipo || '';
    if (typeof trackEvent === 'function' && _currentDialogType) {
        trackEvent('dialog-restored', { tipo: _currentDialogType });
    }

    dialog.querySelector('.dialog-title').textContent = prev.title;
    const body = dialog.querySelector('.dialog-body');
    body.innerHTML = prev.html;
    _reattachDialogLinks(body);
    _decorateDialogBody(body);
    if (prev.activePanelId) _activateDialogSection(body, prev.activePanelId, { focus: false, scroll: false });
    if (!_dialogStack.length) dialog.querySelector('.dialog-back').style.visibility = 'hidden';
    // Atualiza URL pro state do nivel anterior (sem nova history entry).
    // Race guard: bumpa seq pra cancelar fetches inflight da camada que
    // estamos saindo.
    if (typeof _dialogBumpSeq === 'function') _dialogBumpSeq();
    if (prev.urlState && typeof _dialogUrlReplace === 'function') {
        _dialogUrlReplace(prev.urlState);
    } else if (typeof _dialogUrlClear === 'function' && !_dialogStack.length) {
        // Stack vazio sem state salvo (caso edge) — limpa params dialog.
        _dialogUrlClear();
    }
}

function _activateDialogSection(body, id, opts = {}) {
    if (!body || !id || typeof body._activateDialogSection !== 'function') return false;
    return body._activateDialogSection(id, opts);
}

function _dialogReset() {
    _dialogStack.length = 0;
    _currentDialogType = '';
    const dialog = document.getElementById('empresa-dialog');
    if (dialog) dialog.querySelector('.dialog-back').style.visibility = 'hidden';
    document.body.classList.remove('dialog-open');
}

