// === pages/cidade-refresh-kpis.js ===
function _exibirKpisDoPeriodo(data) {
    _updateKpiHeroStrip(data.kpis);
    if (data.top_concentracao) {
        _updateConcentracaoCard(data.top_concentracao, data.pct_top5, data.concentracao_red);
    }
    // A nota canônica do município não depende do período.
    const score = data.score_canonical ?? data.score_unificado;
    if (score != null) {
        document.querySelectorAll('[data-score-unificado]').forEach(el => {
            el.textContent = score;
        });
        _updateRiskSummary(score);
    }
}
