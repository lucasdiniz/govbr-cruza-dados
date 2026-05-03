// === lib/column-meta.js ===
// Remove o prefixo tecnico de codigo em strings como "04021602 - COMISSIONADOS SMN-1"
// ou "5005 - Atencao Integral a Saude". Mantem a string original se nao houver prefixo.
function _stripCodePrefix(s) {
    if (!s) return s;
    const m = String(s).match(/^\s*[0-9A-Z.\-]{2,}\s*[-–—]\s*(.+)$/);
    return m ? m[1].trim() : s;
}
window._stripCodePrefix = _stripCodePrefix;

// Versao string do dualLabel para uso em atributos (ex: data-label no
// padrao stack-mobile). Retorna sempre o rotulo cidadao por padrao; use
// o segundo argumento como data-label-auditor para sobrescrever via CSS.
function _lbl(citizen, auditor) {
    return String(citizen);
}
window._lbl = _lbl;

const _COLUMN_META = window.COLUMN_META || {};

function _defaultColumnLabel(col) {
    return String(col || '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function _columnMeta(col) {
    return _COLUMN_META[col] || {};
}

function _columnLabelPair(col) {
    const meta = _columnMeta(col);
    return {
        citizen: meta.citizen || meta.auditor || _defaultColumnLabel(col),
        auditor: meta.auditor || _defaultColumnLabel(col),
        auditorOnly: !!meta.auditor_only,
    };
}

