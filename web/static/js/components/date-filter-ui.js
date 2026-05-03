// === components/date-filter-ui.js ===
function _getDateFilterCopy() {
    const preset = _getDatePreset();
    const range = `${_formatDatePt(_dateInicio)} a ${_formatDatePt(_dateFim)}`;
    if (preset === 'all') {
        return { headline: 'Periodo: todo o historico', clear: false };
    }
    if (preset === 'current-year') {
        return { headline: `Periodo: ano atual (${range})`, clear: false };
    }
    if (preset === 'last-12m') {
        return { headline: `Periodo: ultimos 12 meses (${range})`, clear: false };
    }
    return { headline: `Periodo: ${range}`, clear: true };
}

function _syncDateFilterUI() {
    const btnLimpar = document.getElementById('btnLimparData');
    const current = document.getElementById('dateFilterCurrent');
    const copy = _getDateFilterCopy();
    if (btnLimpar) btnLimpar.style.display = copy.clear ? '' : 'none';
    if (current) current.textContent = copy.headline;
    document.querySelectorAll('[data-date-preset]').forEach((btn) => {
        btn.classList.toggle('is-active', btn.dataset.datePreset === _getDatePreset());
    });
    if (!_dateFilterBusy) _setDateFilterStatus('');
}

function _resetCityPanelsLoading() {
    document.querySelectorAll('.finding-card').forEach(card => {
        card.classList.add('loading');
        card.classList.remove('is-empty', 'is-timeout');
        card.setAttribute('aria-busy', 'true');
        const body = card.querySelector('.finding-body');
        if (body) body.innerHTML = skeletonTableHtml(3, 3);
        const countEl = card.querySelector('[data-count]');
        if (countEl) countEl.textContent = '...';
        delete card.dataset.count;
    });
    document.querySelectorAll('[data-section-total]').forEach(el => el.textContent = 'Carregando...');
    document.querySelectorAll('[data-report-count]').forEach(el => el.textContent = 'Carregando...');
    document.querySelectorAll('[data-async-panel]').forEach(panel => {
        panel.setAttribute('aria-busy', 'true');
        panel.innerHTML = skeletonTableHtml(4, 3);
    });
}

