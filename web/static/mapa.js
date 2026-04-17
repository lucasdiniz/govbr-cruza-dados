// Mapa coropletico PB - 5 metricas com toggle
(function () {
    const CUTOFF_PAGO = 5_000_000; // R$5mi: abaixo disso, municipio fica cinza

    // Breaks calibrados aos percentis p20/p40/p60/p80/p95 da distribuicao real na PB
    const METRICS = {
        risco: {
            label: 'Risco composto (0-100)',
            unit: '',
            ramp: ['#1a4d1a', '#4b6b20', '#8a7a1a', '#b85c1a', '#d13a1a', '#8a0505'],
            breaks: [62, 65, 69, 73, 77],
            format: (v) => `${v}`,
        },
        pct_irregulares: {
            label: '% pago a fornecedores irregulares',
            unit: '%',
            ramp: ['#1a4d1a', '#4b6b20', '#8a7a1a', '#b85c1a', '#d13a1a', '#8a0505'],
            breaks: [17, 28, 45, 60, 70],
            format: (v) => `${v.toFixed(1)}%`,
        },
        pct_sem_licitacao: {
            label: '% de empenhos sem licitacao',
            unit: '%',
            ramp: ['#1a4d1a', '#4b6b20', '#8a7a1a', '#b85c1a', '#d13a1a', '#8a0505'],
            breaks: [55, 65, 72, 80, 90],
            format: (v) => `${v.toFixed(1)}%`,
        },
        pct_top5: {
            label: '% pago concentrado nos top-5 fornecedores',
            unit: '%',
            ramp: ['#1a4d1a', '#4b6b20', '#8a7a1a', '#b85c1a', '#d13a1a', '#8a0505'],
            breaks: [50, 58, 62, 66, 72],
            format: (v) => `${v.toFixed(1)}%`,
        },
        pago_per_capita: {
            label: 'R$ pago por habitante',
            unit: 'R$',
            ramp: ['#0d2340', '#17416b', '#1e5e99', '#2a85c6', '#49a8e0', '#88d0f5'],
            breaks: [6000, 9000, 12000, 17000, 24000],
            format: (v) => {
                if (v >= 1_000) return `R$ ${(v / 1_000).toFixed(1)} mil`;
                return `R$ ${v.toFixed(0)}`;
            },
        },
    };

    const FALLBACK_COLOR = '#333';

    const state = {
        geojson: null,
        data: {},        // { "Municipio Nome": { risco, pct_* , total_pago } }
        pop: {},         // { "2500106": 9335 }
        metric: 'risco',
        map: null,
        layer: null,
    };

    function normKey(s) {
        return (s || '')
            .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
            .toUpperCase().trim();
    }

    function buildDataIndex(rawData) {
        const idx = {};
        Object.entries(rawData).forEach(([name, obj]) => {
            idx[normKey(name)] = { ...obj, _name: name };
        });
        return idx;
    }

    function featureMetricValue(feat) {
        const geoName = feat.properties.name;
        const codigo = feat.properties.id;
        const entry = state.dataIdx[normKey(geoName)];
        if (!entry) return { v: null, pago: 0, pop: state.pop[codigo] || null };
        const pop = state.pop[codigo] || null;
        let v;
        if (state.metric === 'pago_per_capita') {
            v = pop && pop > 0 ? entry.total_pago / pop : null;
        } else {
            v = entry[state.metric];
        }
        return { v, pago: entry.total_pago || 0, pop, entry };
    }

    function colorFor(value, pago, metric) {
        const cfg = METRICS[metric];
        if (value === null || value === undefined || isNaN(value)) return FALLBACK_COLOR;
        // Cutoff aplica so a metricas de %/risco, nao a per-capita
        if (metric !== 'pago_per_capita' && pago < CUTOFF_PAGO) return FALLBACK_COLOR;
        const breaks = cfg.breaks;
        for (let i = 0; i < breaks.length; i++) {
            if (value < breaks[i]) return cfg.ramp[i];
        }
        return cfg.ramp[cfg.ramp.length - 1];
    }

    function styleFeature(feat) {
        const { v, pago } = featureMetricValue(feat);
        return {
            fillColor: colorFor(v, pago, state.metric),
            weight: 0.5,
            color: '#000',
            fillOpacity: 0.85,
        };
    }

    function formatMetric(v, metric) {
        if (v === null || v === undefined || isNaN(v)) return '—';
        return METRICS[metric].format(v);
    }

    function tooltipHTML(feat) {
        const { v, pago, pop, entry } = featureMetricValue(feat);
        const name = feat.properties.name;
        const lines = [`<strong>${name}</strong>`];
        if (!entry) {
            lines.push('<em>sem dados</em>');
            return lines.join('<br>');
        }
        lines.push(`<span class="tt-k">Valor:</span> <span class="tt-v">${formatMetric(v, state.metric)}</span>`);
        lines.push('<hr>');
        lines.push(`<span class="tt-k">Risco:</span> ${formatMetric(entry.risco, 'risco')}`);
        lines.push(`<span class="tt-k">Irregulares:</span> ${formatMetric(entry.pct_irregulares, 'pct_irregulares')}`);
        lines.push(`<span class="tt-k">Sem licitacao:</span> ${formatMetric(entry.pct_sem_licitacao, 'pct_sem_licitacao')}`);
        lines.push(`<span class="tt-k">Top-5:</span> ${formatMetric(entry.pct_top5, 'pct_top5')}`);
        const perc = pop && pop > 0 ? entry.total_pago / pop : null;
        lines.push(`<span class="tt-k">Per capita:</span> ${formatMetric(perc, 'pago_per_capita')}`);
        lines.push(`<span class="tt-k tt-small">Total pago:</span> <span class="tt-small">R$ ${(entry.total_pago / 1e6).toFixed(1)} mi</span>`);
        if (pop) lines.push(`<span class="tt-k tt-small">Populacao:</span> <span class="tt-small">${pop.toLocaleString('pt-BR')}</span>`);
        return lines.join('<br>');
    }

    function onEachFeature(feat, layer) {
        layer.bindTooltip(tooltipHTML(feat), { sticky: true, className: 'mapa-tooltip' });
        layer.on('click', () => {
            const name = feat.properties.name;
            window.location.href = `/search/cidade?q=${encodeURIComponent(name)}`;
        });
        layer.on('mouseover', () => layer.setStyle({ weight: 2, color: '#fff' }));
        layer.on('mouseout', () => state.layer.resetStyle(layer));
    }

    function renderLegend() {
        const el = document.getElementById('mapa-legend');
        const cfg = METRICS[state.metric];
        const items = ['<div class="legend-inline">'];
        items.push(`<span class="legend-label">${cfg.label}:</span>`);
        items.push(`<span class="legend-item"><span class="legend-swatch" style="background:${cfg.ramp[0]}"></span>&lt; ${cfg.format(cfg.breaks[0])}</span>`);
        for (let i = 1; i < cfg.breaks.length; i++) {
            items.push(`<span class="legend-item"><span class="legend-swatch" style="background:${cfg.ramp[i]}"></span>${cfg.format(cfg.breaks[i - 1])} – ${cfg.format(cfg.breaks[i])}</span>`);
        }
        items.push(`<span class="legend-item"><span class="legend-swatch" style="background:${cfg.ramp[cfg.ramp.length - 1]}"></span>&gt; ${cfg.format(cfg.breaks[cfg.breaks.length - 1])}</span>`);
        items.push(`<span class="legend-item legend-nodata"><span class="legend-swatch"></span>sem dados</span>`);
        items.push('</div>');
        el.innerHTML = items.join('');
    }

    function renderMetricDesc() {
        const el = document.getElementById('mapa-metric-desc');
        if (!el) return;
        const btn = document.querySelector(`.mt-btn[data-metric="${state.metric}"]`);
        el.textContent = btn ? (btn.dataset.desc || '') : '';
    }

    function updateLayer() {
        if (!state.layer) return;
        state.layer.setStyle(styleFeature);
        state.layer.eachLayer(l => l.setTooltipContent(tooltipHTML(l.feature)));
        renderLegend();
        renderMetricDesc();
    }

    function wireToggle() {
        document.querySelectorAll('.mt-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.mt-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                state.metric = btn.dataset.metric;
                const note = document.getElementById('mapa-cutoff-note');
                if (note) {
                    note.style.display = state.metric === 'pago_per_capita' ? 'none' : '';
                }
                updateLayer();
            });
        });
    }

    async function init() {
        const [geojsonRes, dataRes, popRes] = await Promise.all([
            fetch('/static/geo/pb-municipios.geojson').then(r => r.json()),
            fetch('/api/mapa/pb').then(r => r.json()),
            fetch('/static/geo/pb-populacao.json').then(r => r.json()),
        ]);
        state.geojson = geojsonRes;
        state.data = dataRes;
        state.dataIdx = buildDataIndex(dataRes);
        state.pop = popRes;

        const map = L.map('mapa-pb', {
            zoomControl: true,
            attributionControl: false,
            scrollWheelZoom: false,
            tap: true,
            touchZoom: true,
            dragging: true,
        }).setView([-7.25, -36.8], 8);
        state.map = map;

        state.layer = L.geoJSON(state.geojson, {
            style: styleFeature,
            onEachFeature,
        }).addTo(state.map);

        const bounds = state.layer.getBounds();
        state.map.fitBounds(bounds, { padding: [10, 10] });
        // Trava o zoom-out no enquadramento inicial e impede pan para fora da PB.
        const minZoom = state.map.getZoom();
        state.map.setMinZoom(minZoom);
        state.map.setMaxBounds(bounds.pad(0.1));
        wireToggle();
        renderLegend();
        renderMetricDesc();
    }

    document.addEventListener('DOMContentLoaded', init);
})();
