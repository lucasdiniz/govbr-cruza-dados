// === components/concentracao-card.js ===
function _riskSummaryMeta(score) {
    const n = Number(score);
    if (!Number.isFinite(n)) return null;
    if (n >= 70) return { level: 'red', label: 'Atencao alta' };
    if (n >= 40) return { level: 'yellow', label: 'Atencao' };
    return { level: 'green', label: 'Baixa atencao' };
}

function _updateRiskSummary(score) {
    const meta = _riskSummaryMeta(score);
    if (!meta) return;
    const rounded = String(Math.round(Number(score)));
    document.querySelectorAll('[data-risk-summary]').forEach(badge => {
        badge.classList.remove('badge-red', 'badge-yellow', 'badge-green');
        badge.classList.add(`badge-${meta.level}`);
        const label = badge.querySelector('[data-risk-label]');
        if (label) label.textContent = meta.label;
        badge.querySelectorAll('[data-score-unificado]').forEach(el => {
            el.textContent = rounded;
        });
    });
}

function _updateConcentracaoCard(topConcentracao, pctTop5, concentracaoRed) {
    const card = document.querySelector('.city-concentracao');
    if (!card) return;
    if (concentracaoRed) {
        card.classList.add('concentracao-alerta');
    } else {
        card.classList.remove('concentracao-alerta');
    }
    const summary = card.querySelector('.section-summary .insight-value');
    if (summary) {
        summary.textContent = `${Math.round(pctTop5 || 0)}%`;
        summary.classList.toggle('text-red', (pctTop5 || 0) > 60);
    }
    const bars = card.querySelector('.chart-bars-concentracao');
    if (!bars || !Array.isArray(topConcentracao)) return;
    const medals = { 1: '\u{1F947}', 2: '\u{1F948}', 3: '\u{1F949}' };
    bars.innerHTML = topConcentracao.map(c => {
        const rankHtml = medals[c.rank]
            ? medals[c.rank]
            : `<span class="chart-bar-rank-num">${c.rank}</span>`;
        const fillClass = c.is_red ? 'fill-red' : 'fill-blue';
        const safeName = String(c.nome || '').replace(/[<>&"]/g, m => ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;'}[m]));
        const pct = (c.pct || 0).toFixed(1);
        const val = _shortBrlLocal(c.total_pago || 0);
        return `<div class="chart-bar-row" data-cnpj-completo="${c.cnpj_completo || ''}" data-cnpj-basico="${c.cnpj_basico || ''}" data-nome="${safeName}">
            <span class="chart-bar-label" title="${safeName}">
                <span class="chart-bar-rank${c.rank <= 3 ? ' chart-bar-rank-medal' : ''}" aria-label="Posicao ${c.rank}">${rankHtml}</span>
                ${safeName.length > 40 ? safeName.slice(0, 37) + '...' : safeName}
            </span>
            <div class="chart-bar-track">
                <div class="chart-bar-fill ${fillClass}" style="width: ${c.pct || 0}%"></div>
            </div>
            <span class="chart-bar-meta">
                <strong>${pct}%</strong>
                <span class="text-sm text-muted">${val}</span>
            </span>
        </div>`;
    }).join('');
    _wireConcentracaoClicks(bars);
}

function _wireConcentracaoClicks(scope) {
    const root = scope || document.querySelector('.chart-bars-concentracao');
    if (!root || root._wired) return;
    root._wired = true;
    root.style.cursor = 'pointer';
    root.addEventListener('click', (e) => {
        const row = e.target.closest('.chart-bar-row');
        if (!row) return;
        const cnpjBasico = row.dataset.cnpjBasico || '';
        const cnpjCompleto = String(row.dataset.cnpjCompleto || '').replace(/\D/g, '');
        const nome = row.dataset.nome || '';
        if (!cnpjBasico || cnpjCompleto.length !== 14) return;
        if (typeof openFornecedorDialog === 'function') {
            openFornecedorDialog(cnpjBasico, nome, null, false, nome, cnpjCompleto);
        }
    });
}

