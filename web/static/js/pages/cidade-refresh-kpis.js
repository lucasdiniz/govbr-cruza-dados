// === pages/cidade-refresh-kpis.js ===
async function _refreshKpisLive(municipio, uf) {
    try {
        const res = await fetch(`/api/kpis/${encodeURIComponent(municipio)}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(_buildBody(municipio, uf || 'PB')),
        });
        if (!res.ok) {
            const msg = await _handleDateApiError(res, 'Nao foi possivel carregar os indicadores deste periodo.');
            console.warn('kpis endpoint returned', res.status, msg);
            return;
        }
        const data = await res.json();
        if (data && data.kpis) _updateKpiHeroStrip(data.kpis);
        if (data && data.top_concentracao) {
            _updateConcentracaoCard(data.top_concentracao, data.pct_top5, data.concentracao_red);
        }
        // Atualiza a nota de atencao na narrativa, se houver elemento expondo o score.
        if (data && data.score_unificado != null) {
            document.querySelectorAll('[data-score-unificado]').forEach(el => {
                el.textContent = data.score_unificado;
            });
            _updateRiskSummary(data.score_unificado);
        }
    } catch (e) {
        console.warn('kpis fetch failed', e);
    }
}

