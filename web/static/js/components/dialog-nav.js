// === components/dialog-nav.js ===
// ── Dialog navigation stack ─────────────────────────────────────
let _currentMunicipio = '';
const _dialogStack = []; // [{title, html, activePanelId}]

function _dialogPush() {
    const dialog = document.getElementById('empresa-dialog');
    if (!dialog) return;
    const title = dialog.querySelector('.dialog-title').textContent;
    const body = dialog.querySelector('.dialog-body');
    const html = body.innerHTML;
    const activePanelId = body._activeDialogSectionId || body.querySelector('.dialog-tab-panel:not([hidden])')?.id || '';
    _dialogStack.push({ title, html, activePanelId });
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
}

function _activateDialogSection(body, id, opts = {}) {
    if (!body || !id || typeof body._activateDialogSection !== 'function') return false;
    return body._activateDialogSection(id, opts);
}

function _dialogReset() {
    _dialogStack.length = 0;
    const dialog = document.getElementById('empresa-dialog');
    if (dialog) dialog.querySelector('.dialog-back').style.visibility = 'hidden';
    document.body.classList.remove('dialog-open');
}

