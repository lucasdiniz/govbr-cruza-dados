// === components/date-filter.js ===
// ── Date filter state ───────────────────────────────────────────
let _dateInicio = null;
let _dateFim = null;
let _currentUf = 'PB';

function _isDateFiltered() { return !!(_dateInicio || _dateFim); }

function _formatDateInput(date) {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
}

function _todayGmt3Parts() {
    const gmt3 = new Date(Date.now() - (3 * 60 * 60 * 1000));
    return {
        year: gmt3.getUTCFullYear(),
        month: gmt3.getUTCMonth() + 1,
        day: gmt3.getUTCDate(),
    };
}

function _partsToIso(parts) {
    return `${parts.year}-${String(parts.month).padStart(2, '0')}-${String(parts.day).padStart(2, '0')}`;
}

function _addUtcDaysParts(year, month, day, days) {
    const dt = new Date(Date.UTC(year, month - 1, day + days));
    return { year: dt.getUTCFullYear(), month: dt.getUTCMonth() + 1, day: dt.getUTCDate() };
}

function _todayGmt3Iso() {
    return _partsToIso(_todayGmt3Parts());
}

function _datePresetRange(preset) {
    const today = _todayGmt3Parts();
    const todayIso = _partsToIso(today);
    if (preset === 'current-year') {
        return { inicio: `${today.year}-01-01`, fim: todayIso };
    }
    if (preset === 'last-12m') {
        const start = (today.month === 2 && today.day === 29)
            ? { year: today.year - 1, month: 3, day: 1 }
            : _addUtcDaysParts(today.year - 1, today.month, today.day, 1);
        return { inicio: _partsToIso(start), fim: todayIso };
    }
    return { inicio: '', fim: '' };
}

function _getDatePreset() {
    if (!_isDateFiltered()) return 'all';
    const currentYear = _datePresetRange('current-year');
    if (_dateInicio === currentYear.inicio && _dateFim === currentYear.fim) return 'current-year';
    const last12m = _datePresetRange('last-12m');
    if (_dateInicio === last12m.inicio && _dateFim === last12m.fim) return 'last-12m';
    return 'custom';
}

function _getPeriodo() {
    if (!_isDateFiltered()) return '';
    const currentYear = _datePresetRange('current-year');
    if (_dateInicio === currentYear.inicio && _dateFim === currentYear.fim) return 'ANO';
    const last12m = _datePresetRange('last-12m');
    if (_dateInicio === last12m.inicio && _dateFim === last12m.fim) return '12M';
    return 'CUSTOM';
}

function _buildBody(municipio, uf) {
    const body = { municipio, uf: uf || _currentUf };
    if (_dateInicio) body.data_inicio = _dateInicio;
    if (_dateFim) body.data_fim = _dateFim;
    return body;
}

function _formatDatePt(iso) {
    if (!iso) return '';
    const [y, m, d] = iso.split('-');
    return `${d}/${m}/${y}`;
}

function _brToIso(br) {
    if (!br) return '';
    const m = String(br).trim().match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
    if (!m) return '';
    const [, dd, mm, yyyy] = m;
    const day = parseInt(dd, 10), mon = parseInt(mm, 10), year = parseInt(yyyy, 10);
    if (mon < 1 || mon > 12 || day < 1 || day > 31 || year < 1900 || year > 2100) return '';
    const dt = new Date(year, mon - 1, day);
    if (dt.getFullYear() !== year || dt.getMonth() !== mon - 1 || dt.getDate() !== day) return '';
    return `${yyyy}-${mm}-${dd}`;
}

function _isoToBr(iso) { return _formatDatePt(iso); }

function _readDateInputIso(el) {
    if (!el) return '';
    return _brToIso(el.value);
}

function _maskBrDate(input) {
    if (!input || input.dataset.brMaskBound === '1') return;
    input.dataset.brMaskBound = '1';
    const apply = () => {
        const digits = input.value.replace(/\D/g, '').slice(0, 8);
        let out = digits;
        if (digits.length > 4) out = `${digits.slice(0, 2)}/${digits.slice(2, 4)}/${digits.slice(4)}`;
        else if (digits.length > 2) out = `${digits.slice(0, 2)}/${digits.slice(2)}`;
        if (out !== input.value) input.value = out;
    };
    input.addEventListener('input', apply);
    input.addEventListener('blur', apply);
}

function _initDateInputsBr() {
    ['dateInicio', 'dateFim'].forEach((id) => {
        const el = document.getElementById(id);
        if (!el) return;
        if (el.dataset.isoValue && !el.value) el.value = _isoToBr(el.dataset.isoValue);
        _maskBrDate(el);
    });
}

function _setDateFilterStatus(message, kind) {
    const el = document.getElementById('dateFilterStatus');
    if (!el) return;
    el.textContent = message || '';
    el.classList.toggle('color-red', kind === 'error');
}

let _dateFilterBusy = false;

function _setDateFilterButtonBusy(isBusy) {
    const btn = document.getElementById('btnFiltrarData');
    if (!btn) return;
    if (!btn.dataset.defaultLabel) btn.dataset.defaultLabel = (btn.textContent || 'Filtrar').trim();
    btn.disabled = !!isBusy;
    btn.setAttribute('aria-busy', isBusy ? 'true' : 'false');
    btn.textContent = isBusy ? 'Filtrando...' : btn.dataset.defaultLabel;
}

function _setLiveRefreshState(isBusy) {
    document.querySelectorAll('.city-hero, .insight-grid, .city-kpi-strip').forEach(node => {
        node.setAttribute('aria-busy', isBusy ? 'true' : 'false');
        node.classList.toggle('is-refreshing', !!isBusy);
    });
}

async function _handleDateApiError(response, fallbackMessage) {
    let message = fallbackMessage || 'Nao foi possivel aplicar o filtro de periodo.';
    try {
        const data = await response.json();
        if (data && data.error) message = data.error;
    } catch {}
    if (response.status === 400) {
        _setDateFilterStatus(message, 'error');
    }
    return message;
}

function _validateDateInputs() {
    const inicioEl = document.getElementById('dateInicio');
    const fimEl = document.getElementById('dateFim');
    const inicio = _readDateInputIso(inicioEl);
    const fim = _readDateInputIso(fimEl);
    if (!inicio || !fim) {
        _setDateFilterStatus('Preencha as duas datas no formato DD/MM/AAAA.', 'error');
        return null;
    }
    if (inicio > fim) {
        _setDateFilterStatus('A data inicial nao pode ser maior que a data final.', 'error');
        return null;
    }
    _setDateFilterStatus('');
    return { inicio, fim };
}

function _setDateInputs(inicio, fim) {
    const diEl = document.getElementById('dateInicio');
    const dfEl = document.getElementById('dateFim');
    if (diEl) diEl.value = inicio ? _isoToBr(inicio) : '';
    if (dfEl) dfEl.value = fim ? _isoToBr(fim) : '';
}
