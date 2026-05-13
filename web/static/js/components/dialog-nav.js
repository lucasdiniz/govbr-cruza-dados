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
    dialog.querySelector('.dialog-title').textContent = prev.title;
    const body = dialog.querySelector('.dialog-body');
    body.innerHTML = prev.html;
    _reattachDialogLinks(body);
    _decorateDialogBody(body);
    if (prev.activePanelId) _activateDialogSection(body, prev.activePanelId, { focus: false, scroll: false });
    if (!_dialogStack.length) dialog.querySelector('.dialog-back').style.visibility = 'hidden';
    // Restaura tipo do nivel anterior pra que drill chain subsequente
    // (ex: voltar pra fornecedor e abrir outro empenho) tenha drilled_from
    // correto.
    _currentDialogType = prev.tipo || '';
    // Engagement tracking: emite novo evento `dialog-restored` pro
    // listener de dialog-engagement saber que o user voltou pra um
    // dialog anterior (mesma md-dialog, conteudo diferente do que
    // estava no momento do back). Sem isso, dwell/scroll/tabs do nivel
    // restaurado ficam atribuidos ao tipo errado (ultimo aberto antes
    // do back). Como evento separado de dialog-aberto pra permitir
    // contar "voltei" distinto de "abri novo" nas metricas.
    if (typeof trackEvent === 'function' && _currentDialogType) {
        trackEvent('dialog-restored', { tipo: _currentDialogType });
    }
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

