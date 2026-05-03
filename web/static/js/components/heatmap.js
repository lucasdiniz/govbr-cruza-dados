// === components/heatmap.js ===
async function _loadHeatmap(municipio) {
    const grid = document.getElementById('heatmapGrid');
    if (!grid) return;
    try {
        const res = await fetch(`/api/heatmap/${encodeURIComponent(municipio)}`);
        if (!res.ok) throw new Error('http ' + res.status);
        const data = await res.json();
        _renderHeatmap(data.cells || []);
    } catch (e) {
        grid.innerHTML = '<p class="text-sm text-muted">Não foi possível carregar o heatmap.</p>';
    }
}

function _renderHeatmap(cells) {
    const grid = document.getElementById('heatmapGrid');
    const legend = document.getElementById('heatmapLegend');
    if (!grid) return;
    if (!cells.length) {
        grid.innerHTML = '<p class="text-sm text-muted">Sem dados de empenho mensais para este município.</p>';
        if (legend) legend.innerHTML = '';
        return;
    }

    // Build (ano, mes) -> valor
    const byKey = {};
    const anos = new Set();
    let maxVal = 0;
    cells.forEach(c => {
        const v = parseFloat(c.total_empenhado) || 0;
        byKey[`${c.ano}-${c.mes}`] = v;
        anos.add(c.ano);
        if (v > maxVal) maxVal = v;
    });
    const anosSorted = Array.from(anos).sort((a, b) => b - a); // mais recente no topo

    // Média e desvio-padrão (usa todos os valores reais, inclui zeros de meses com registros)
    const vals = Object.values(byKey);
    const mean = vals.reduce((s, v) => s + v, 0) / vals.length;
    const variance = vals.reduce((s, v) => s + (v - mean) ** 2, 0) / vals.length;
    const std = Math.sqrt(variance);

    // Escala linear min-max (ignora zeros — sem-dados usa cor neutra)
    const nonZero = vals.filter(v => v > 0);
    const minVal = nonZero.length ? Math.min(...nonZero) : 0;
    const spread = Math.max(1, maxVal - minVal);
    const mesesLabel = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];

    const ramp = ['#e6efff', '#c2d6f7', '#9bbbed', '#6f9ae0', '#4579cf', '#2555ab', '#0f3380'];
    const colorFor = v => {
        if (!v) return { bg: '#1e2a3a', color: '#4a5568' };
        const t = (v - minVal) / spread;
        const idx = Math.min(ramp.length - 1, Math.max(0, Math.floor(t * ramp.length)));
        return { bg: ramp[idx], color: idx >= 4 ? '#fff' : '#0f2056' };
    };

    const html = ['<div class="hm-row hm-header"><div class="hm-cell hm-year-label"></div>'];
    mesesLabel.forEach(m => html.push(`<div class="hm-cell hm-month-label">${m}</div>`));
    html.push('</div>');

    anosSorted.forEach(ano => {
        html.push(`<div class="hm-row"><div class="hm-cell hm-year-label">${ano}</div>`);
        for (let m = 1; m <= 12; m++) {
            const v = byKey[`${ano}-${m}`] || 0;
            const z = std > 0 ? (v - mean) / std : 0;
            const outlier = z > 2 ? ' hm-outlier' : '';
            const { bg, color } = colorFor(v);
            const label = v ? _shortBrl(v) : '—';
            const title = v ? `${mesesLabel[m - 1]}/${ano}: ${_shortBrl(v)} — clique para drill-down${z > 2 ? ` (${z.toFixed(1)}σ acima da média)` : ''}` : `${mesesLabel[m - 1]}/${ano}: sem dados`;
            const clickable = v ? ' hm-clickable' : '';
            const dataAttrs = v ? ` data-ano="${ano}" data-mes="${m}"` : '';
            html.push(`<div class="hm-cell hm-value${outlier}${clickable}" style="background:${bg};color:${color}" title="${title}"${dataAttrs}><span>${label}</span></div>`);
        }
        html.push('</div>');
    });

    grid.innerHTML = html.join('');

    grid.querySelectorAll('.hm-clickable').forEach(cell => {
        cell.addEventListener('click', () => {
            const ano = parseInt(cell.dataset.ano, 10);
            const mes = parseInt(cell.dataset.mes, 10);
            if (ano && mes) openHeatmapMonthDialog(_currentMunicipio, ano, mes);
        });
    });

    if (legend) {
        const steps = ramp.map((c, i) => {
            const lo = minVal + (i / ramp.length) * spread;
            const hi = minVal + ((i + 1) / ramp.length) * spread;
            return `<div class="hm-legend-step" style="background:${c}" title="${_shortBrl(lo)} – ${_shortBrl(hi)}"></div>`;
        }).join('');
        legend.innerHTML = `
            <span class="hm-legend-label">Menor</span>
            <div class="hm-legend-ramp">${steps}</div>
            <span class="hm-legend-label">Maior</span>
            <span class="hm-legend-sep"></span>
            <span class="hm-legend-outlier"></span>
            <span class="hm-legend-label">Mês atípico (>2σ)</span>
        `;
    }
}

