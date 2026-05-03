// === components/kpi-strip.js ===
// ── KPI hero strip live refresh ─────────────────────────────────
// Quando o filtro temporal muda, busca KPIs recalculados do servidor
// e re-renderiza a hero strip + card de concentracao top-5 + nota de
// atencao na narrativa. Mantem a UI consistente com o filtro aplicado.
function _shortBrlLocal(v) {
    return typeof _shortBrl === 'function' ? _shortBrl(v) : `R$ ${v}`;
}

function _shortNumLocal(v) {
    return typeof _shortNum === 'function' ? _shortNum(v) : String(v);
}

function _renderKpiCardValue(kpi) {
    let valHtml = '';
    if (kpi.is_money) {
        valHtml = _shortBrlLocal(kpi.value);
    } else {
        valHtml = _shortNumLocal(kpi.value);
    }
    if (kpi.value_suffix) {
        valHtml += `<span class="kpi-card-suffix">${_esc(kpi.value_suffix)}</span>`;
    }
    return valHtml;
}

function _updateKpiHeroStrip(kpis) {
    if (!Array.isArray(kpis)) return;
    const orderedCards = [];
    kpis.forEach(kpi => {
        const card = document.getElementById(kpi.id);
        if (!card) return;
        // severity class
        card.classList.remove('severity-red', 'severity-yellow', 'severity-neutral');
        card.classList.add(`severity-${kpi.severity || 'neutral'}`);
        card.dataset.kpiSeverity = kpi.severity || 'neutral';
        // value
        const valEl = card.querySelector('.kpi-card-value');
        if (valEl) valEl.innerHTML = _renderKpiCardValue(kpi);
        // extra
        let extraEl = card.querySelector('.kpi-card-extra');
        if (kpi.value_extra) {
            if (!extraEl) {
                extraEl = document.createElement('span');
                extraEl.className = 'kpi-card-extra';
                const tip = card.querySelector('.kpi-card-tip');
                card.insertBefore(extraEl, tip);
            }
            extraEl.textContent = kpi.value_extra;
        } else if (extraEl) {
            extraEl.remove();
        }
        orderedCards.push(card);
    });
    const grid = document.querySelector('.city-kpi-grid');
    if (grid) orderedCards.forEach(card => grid.appendChild(card));
}

