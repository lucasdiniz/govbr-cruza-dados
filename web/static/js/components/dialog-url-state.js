// === components/dialog-url-state.js ===
//
// Encapsula o "estado do dialog" na URL (query params) pra que links
// possam ser compartilhados e restaurados. Funciona junto com:
//   - dialog-nav.js: stack de HTML in-dialog (_dialogPush/_dialogPop)
//   - dialog-history-swipe.js: integração com history.pushState (back-nav fecha)
//
// Modelo de history:
//   - Open inicial (dialog fechado): pushState com URL contendo `d=...&d_*=...`
//   - Open nested (já aberto, _dialogPush): replaceState com URL atualizada
//   - Stack pop in-dialog (_dialogPop): replaceState para URL anterior salva
//   - Close: history.back() (consome o pushState; popstate fecha de volta)
//   - Browser Back: popstate fecha dialog (dialog-history-swipe handler)
//
// Per-dialog schemas (params com prefixo `d_` pra evitar colisão com page params):
//   d=fornecedor & d_cnpj=14d & d_nome=... & d_ncred=... & d_mun=...
//   d=servidor   & d_cpf6=... & d_nome=... & d_snome=... & d_cnpjs=8d,8d,...
//   d=empenho    & d_id=<numeric>
//   d=licitacao  & d_num=... & d_ano=... & d_mod=... & d_mun=...
//   d=heatmap    & d_ano=... & d_mes=... & d_mun=...

const DIALOG_URL_PARAM = 'd';
const DIALOG_URL_PREFIX = 'd_';
const DIALOG_TYPES = ['fornecedor', 'servidor', 'empenho', 'licitacao', 'heatmap'];
const _CNPJS_MAX = 12;

// Counter global usado por _seqCheck para abortar continuações async
// quando outro dialog é aberto / o atual é fechado durante o fetch.
let _dialogReqSeq = 0;

function _dialogNextSeq() {
    return ++_dialogReqSeq;
}
function _dialogSeqValid(seq) {
    if (seq !== _dialogReqSeq) return false;
    const dialog = document.getElementById('empresa-dialog');
    return !!(dialog && dialog.open);
}
function _dialogBumpSeq() {
    _dialogReqSeq++;
}

// ── URL helpers ──────────────────────────────────────────────────────

function _stripDialogParams(url) {
    const u = (url instanceof URL) ? url : new URL(url);
    const toDelete = [];
    u.searchParams.forEach((_, k) => {
        if (k === DIALOG_URL_PARAM || k.startsWith(DIALOG_URL_PREFIX)) toDelete.push(k);
    });
    toDelete.forEach((k) => u.searchParams.delete(k));
    return u;
}

function _buildDialogUrl(state) {
    const u = _stripDialogParams(window.location.href);
    if (state && state.d) {
        u.searchParams.set(DIALOG_URL_PARAM, state.d);
        Object.entries(state).forEach(([k, v]) => {
            if (k === 'd') return;
            if (v === undefined || v === null || v === '') return;
            u.searchParams.set(`${DIALOG_URL_PREFIX}${k}`, String(v));
        });
    }
    return u.toString();
}

function _dialogUrlPush(state) {
    const newUrl = _buildDialogUrl(state);
    try {
        history.pushState({ tpbDialog: true, dialogState: state }, '', newUrl);
    } catch { /* ignore */ }
}

function _dialogUrlReplace(state) {
    const newUrl = _buildDialogUrl(state);
    try {
        history.replaceState({ tpbDialog: true, dialogState: state }, '', newUrl);
    } catch { /* ignore */ }
}

function _dialogUrlClear() {
    const u = _stripDialogParams(window.location.href);
    try {
        history.replaceState(null, '', u.toString());
    } catch { /* ignore */ }
}

// Atualiza apenas o campo `tab` do state atual (sem nova history entry).
// Usado quando user clica em outra tab dentro do dialog: URL passa a
// refletir a tab visivel pra share-link funcionar corretamente.
function _dialogUrlUpdateTab(tabId) {
    const current = (history.state && history.state.dialogState) || _readDialogStateFromUrl();
    if (!current) return;
    const next = { ...current, tab: tabId || '' };
    if (!next.tab) delete next.tab;
    const newUrl = _buildDialogUrl(next);
    try {
        const restoredFlag = history.state && history.state.restoredFromUrl;
        history.replaceState(
            { tpbDialog: true, dialogState: next, ...(restoredFlag ? { restoredFromUrl: true } : {}) },
            '',
            newUrl,
        );
    } catch { /* ignore */ }
}

// ── State extraction from URL ────────────────────────────────────────

function _readDialogStateFromUrl() {
    const p = new URLSearchParams(window.location.search);
    const d = p.get(DIALOG_URL_PARAM);
    if (!d || !DIALOG_TYPES.includes(d)) return null;
    const state = { d };
    p.forEach((value, key) => {
        if (key.startsWith(DIALOG_URL_PREFIX)) {
            state[key.slice(DIALOG_URL_PREFIX.length)] = value;
        }
    });
    return state;
}

// ── Restore from URL on page load ────────────────────────────────────

async function _restoreDialogFromUrl() {
    const state = _readDialogStateFromUrl();
    if (!state) return false;

    // Marca history.state pra que popstate-close funcione mesmo em URL
    // restaurada (cabe no estado existente, sem nova entrada).
    try {
        if (!(history.state && history.state.tpbDialog)) {
            history.replaceState({ tpbDialog: true, dialogState: state, restoredFromUrl: true }, '', window.location.href);
        }
    } catch { /* ignore */ }

    try {
        switch (state.d) {
            case 'fornecedor': {
                if (!state.cnpj || state.cnpj.length !== 14) throw new Error('cnpj ausente');
                const cnpjBasico = state.cnpj.slice(0, 8);
                const nome = state.nome || 'Fornecedor';
                const nomeCredor = state.ncred || '';
                const munOverride = state.mun || null;
                if (typeof openFornecedorDialog === 'function') {
                    await openFornecedorDialog(cnpjBasico, nome, munOverride, false, nomeCredor, state.cnpj, { fromUrl: true });
                }
                return true;
            }
            case 'servidor': {
                if (!state.cpf6) throw new Error('cpf6 ausente');
                const nome = state.nome || '';
                const cnpjs = (state.cnpjs || '').split(',').map(s => s.trim()).filter(Boolean).slice(0, _CNPJS_MAX);
                if (typeof openServidorDialog === 'function') {
                    await openServidorDialog(state.cpf6, nome, cnpjs, state.snome || nome, {}, { fromUrl: true });
                }
                return true;
            }
            case 'empenho': {
                if (!state.id) throw new Error('id ausente');
                if (typeof openEmpenhoDialog === 'function') {
                    await openEmpenhoDialog(state.id, { fromUrl: true });
                }
                return true;
            }
            case 'licitacao': {
                if (!state.num) throw new Error('num ausente');
                const mun = state.mun || _currentMunicipio || '';
                if (typeof openLicitacaoDialog === 'function') {
                    await openLicitacaoDialog(state.num, state.ano || '0', mun,
                                              `Licitacao ${state.num}`,
                                              state.mod || '', state.ug || '',
                                              { fromUrl: true });
                }
                return true;
            }
            case 'heatmap': {
                if (!state.ano || !state.mes) throw new Error('ano/mes ausentes');
                const mun = state.mun || _currentMunicipio || '';
                if (typeof openHeatmapMonthDialog === 'function') {
                    await openHeatmapMonthDialog(mun, parseInt(state.ano, 10), parseInt(state.mes, 10), { fromUrl: true });
                }
                return true;
            }
            default:
                return false;
        }
    } catch (err) {
        // Restore falhou — limpa params e mostra toast amigável (sem deixar
        // URL "presa" tentando re-abrir um dialog inválido a cada refresh).
        _dialogUrlClear();
        if (typeof showToast === 'function') {
            showToast('Não foi possível abrir o detalhe compartilhado.', 4000);
        }
        return false;
    }
}

// Expor pra uso no inline script de cidade.html (após bootstrapCityReport).
window.restoreDialogFromUrl = _restoreDialogFromUrl;

// ── Helpers usados pelas funcoes openXxxDialog ───────────────────────
//
// _dialogStateApply(state, fromUrl, isInitialOpen):
//   - fromUrl = true  -> NAO pusha state (já foi setado em _restoreDialogFromUrl)
//   - isInitialOpen   -> pushState (nova entrada no history)
//   - !isInitialOpen  -> replaceState (URL atualizada na mesma entrada)
function _dialogStateApply(state, fromUrl, isInitialOpen) {
    if (fromUrl) return;
    if (isInitialOpen) {
        _dialogUrlPush(state);
    } else {
        _dialogUrlReplace(state);
    }
}
