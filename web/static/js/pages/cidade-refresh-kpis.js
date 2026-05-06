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
        // "Nota de atencao" do hero = score_canonical (= mv_municipio_pb_kpi_score
        // = mesmo valor do mapa coropletico, period-independent). Eh metrica de
        // reputacao geral do municipio; nao varia conforme filtro temporal por
        // contrato (mapa e cidade exibem o mesmo numero). Os KPIs cards
        // continuam refletindo o periodo. Fallback pra score_unificado live
        // apenas quando score_canonical estiver ausente (cidade fora da MV).
        const scoreToShow = (data && data.score_canonical != null)
            ? data.score_canonical
            : (data ? data.score_unificado : null);
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

