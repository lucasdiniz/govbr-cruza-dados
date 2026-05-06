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
        // Nota de atencao: quando filtro de data NAO esta ativo, prefere o
        // score canonico (= mv_municipio_pb_kpi_score.risco_score_unificado
        // = mesmo valor exibido no mapa coropletico). Garante que a nota
        // bata 1:1 entre /mapa e /search/cidade quando ambos sao all-time.
        // Quando filtro ativo, usa score_unificado computed live (refleta
        // o periodo selecionado).
        const useCanonical = !_isDateFiltered() && data && data.score_canonical != null;
        const scoreToShow = useCanonical ? data.score_canonical : (data ? data.score_unificado : null);
        if (scoreToShow != null) {
            document.querySelectorAll('[data-score-unificado]').forEach(el => {
                el.textContent = scoreToShow;
            });
            _updateRiskSummary(scoreToShow);
        }
    } catch (e) {
        console.warn('kpis fetch failed', e);
    }
}

