// === lib/format.js ===
function _colIndex(cols, name) {
    return cols.indexOf(name);
}

function _val(row, cols, name) {
    const i = _colIndex(cols, name);
    return i >= 0 ? row[i] : null;
}

function _shortBrl(v) {
    const n = parseFloat(v) || 0;
    const a = Math.abs(n);
    if (a >= 1e9) return `R$ ${(n/1e9).toFixed(1)} bi`;
    if (a >= 1e6) return `R$ ${(n/1e6).toFixed(1)} mi`;
    if (a >= 1e3) return `R$ ${(n/1e3).toFixed(1)} mil`;
    return `R$ ${n.toFixed(0)}`;
}

function _shortNum(v) {
    const n = parseFloat(v) || 0;
    const a = Math.abs(n);
    if (a >= 1e6) return `${(n/1e6).toFixed(1)} mi`;
    if (a >= 1e3) return `${(n/1e3).toFixed(1)} mil`;
    return `${n.toFixed(0)}`;
}

function _esc(v) {
    if (v === null || v === undefined) return '-';
    return String(v)
        .replace(/&/g,'&amp;')
        .replace(/</g,'&lt;')
        .replace(/>/g,'&gt;')
        .replace(/"/g,'&quot;')
        .replace(/'/g,'&#39;');
}

function _fmtDate(v) {
    if (!v || v === '-') return '-';
    const s = String(v);
    // YYYYMM -> MM/YYYY
    if (/^\d{6}$/.test(s)) return `${s.slice(4,6)}/${s.slice(0,4)}`;
    // YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS -> DD/MM/YYYY
    const m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (m) return `${m[3]}/${m[2]}/${m[1]}`;
    return s;
}

