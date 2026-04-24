// Mapa coropletico PB - 5 metricas com toggle
(function () {
    const CUTOFF_PAGO = 5_000_000; // R$5mi: abaixo disso, municipio fica cinza

    // Percentis usados para distribuir as cores pela amostra atual da PB.
    // Mantem o mapa incremental mesmo quando a formula dos indicadores muda.
    const QUANTILE_LEVELS = [0.20, 0.40, 0.60, 0.80, 0.95];

    const METRICS = {
        risco: {
            label: 'Nota de atenção (0-100)',
            unit: '',
            ramp: ['#1a4d1a', '#4b6b20', '#8a7a1a', '#b85c1a', '#d13a1a', '#8a0505'],
            fallbackBreaks: [42, 47, 52, 60, 69],
            format: (v) => `${v}`,
        },
        pct_irregulares: {
            label: '% pago a fornecedores irregulares',
            unit: '%',
            ramp: ['#1a4d1a', '#4b6b20', '#8a7a1a', '#b85c1a', '#d13a1a', '#8a0505'],
            fallbackBreaks: [17, 28, 45, 60, 70],
            format: (v) => `${v.toFixed(1)}%`,
        },
        pct_sem_licitacao: {
            label: '% de empenhos sem licitacao',
            unit: '%',
            ramp: ['#1a4d1a', '#4b6b20', '#8a7a1a', '#b85c1a', '#d13a1a', '#8a0505'],
            fallbackBreaks: [55, 65, 72, 80, 90],
            format: (v) => `${v.toFixed(1)}%`,
        },
        pct_top5: {
            label: '% pago concentrado nos top-5 fornecedores',
            unit: '%',
            ramp: ['#1a4d1a', '#4b6b20', '#8a7a1a', '#b85c1a', '#d13a1a', '#8a0505'],
            fallbackBreaks: [50, 58, 62, 66, 72],
            format: (v) => `${v.toFixed(1)}%`,
        },
        pago_per_capita: {
            label: 'R$ pago por habitante',
            unit: 'R$',
            ramp: ['#0d2340', '#17416b', '#1e5e99', '#2a85c6', '#49a8e0', '#88d0f5'],
            fallbackBreaks: [6000, 9000, 12000, 17000, 24000],
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
        dataIdx: {},
        pop: {},         // { "2500106": 9335 }
        metricBreaks: {},
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

    function featureMetricValueFor(feat, metric) {
        const geoName = feat.properties.name;
        const codigo = feat.properties.id;
        const entry = state.dataIdx[normKey(geoName)];
        if (!entry) return { v: null, pago: 0, pop: state.pop[codigo] || null };
        const pop = state.pop[codigo] || null;
        let v;
        if (metric === 'pago_per_capita') {
            v = pop && pop > 0 ? entry.total_pago / pop : null;
        } else {
            v = entry[metric];
        }
        return { v, pago: entry.total_pago || 0, pop, entry };
    }

    function featureMetricValue(feat) {
        return featureMetricValueFor(feat, state.metric);
    }

    function roundBreak(value, metric) {
        if (metric === 'risco') return Math.round(value);
        if (metric === 'pago_per_capita') {
            if (value >= 10_000) return Math.round(value / 500) * 500;
            if (value >= 1_000) return Math.round(value / 100) * 100;
            return Math.round(value / 50) * 50;
        }
        return Math.round(value * 10) / 10;
    }

    function percentile(sortedValues, q) {
        if (!sortedValues.length) return null;
        const pos = (sortedValues.length - 1) * q;
        const lower = Math.floor(pos);
        const upper = Math.ceil(pos);
        if (lower === upper) return sortedValues[lower];
        const weight = pos - lower;
        return sortedValues[lower] * (1 - weight) + sortedValues[upper] * weight;
    }

    function uniqueIncreasingBreaks(values, metric) {
        const breaks = [];
        values.forEach(raw => {
            if (raw === null || raw === undefined || isNaN(raw)) return;
            const rounded = roundBreak(raw, metric);
            if (!breaks.length || rounded > breaks[breaks.length - 1]) breaks.push(rounded);
        });
        return breaks;
    }

    function collectMetricValues(metric) {
        const features = (state.geojson && state.geojson.features) || [];
        return features
            .map(feat => {
                const { v, pago } = featureMetricValueFor(feat, metric);
                if (v === null || v === undefined || isNaN(v)) return null;
                if (metric !== 'pago_per_capita' && pago < CUTOFF_PAGO) return null;
                return v;
            })
            .filter(v => v !== null)
            .sort((a, b) => a - b);
    }

    function equalIntervalBreaks(sortedValues, metric, buckets) {
        if (!sortedValues.length) return [];
        const min = sortedValues[0];
        const max = sortedValues[sortedValues.length - 1];
        if (min === max) return [];
        const step = (max - min) / buckets;
        const values = [];
        for (let i = 1; i < buckets; i++) values.push(min + step * i);
        return uniqueIncreasingBreaks(values, metric);
    }

    function computeMetricBreaks(metric) {
        const cfg = METRICS[metric];
        const needed = cfg.ramp.length - 1;
        const values = collectMetricValues(metric);
        if (values.length < cfg.ramp.length) return cfg.fallbackBreaks;

        const quantileBreaks = uniqueIncreasingBreaks(
            QUANTILE_LEVELS.map(q => percentile(values, q)),
            metric
        );
        if (quantileBreaks.length === needed) return quantileBreaks;

        const intervalBreaks = equalIntervalBreaks(values, metric, cfg.ramp.length);
        if (intervalBreaks.length === needed) return intervalBreaks;

        return cfg.fallbackBreaks;
    }

    function computeAllMetricBreaks() {
        state.metricBreaks = {};
        Object.keys(METRICS).forEach(metric => {
            state.metricBreaks[metric] = computeMetricBreaks(metric);
        });
    }

    function breaksFor(metric) {
        return state.metricBreaks[metric] || METRICS[metric].fallbackBreaks;
    }

    function colorFor(value, pago, metric) {
        const cfg = METRICS[metric];
        if (value === null || value === undefined || isNaN(value)) return FALLBACK_COLOR;
        // Cutoff aplica so a metricas de %/risco, nao a per-capita
        if (metric !== 'pago_per_capita' && pago < CUTOFF_PAGO) return FALLBACK_COLOR;
        const breaks = breaksFor(metric);
        for (let i = 0; i < breaks.length; i++) {
            if (value < breaks[i]) return cfg.ramp[i];
        }
        return cfg.ramp[Math.min(breaks.length, cfg.ramp.length - 1)];
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
        lines.push(`<span class="tt-k">Nota:</span> ${formatMetric(entry.risco, 'risco')}`);
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
        const breaks = breaksFor(state.metric);
        const items = ['<div class="legend-inline">'];
        items.push(`<span class="legend-label">${cfg.label}:</span>`);
        items.push('<span class="legend-scale-note">faixas por percentil PB</span>');
        items.push(`<span class="legend-item"><span class="legend-swatch" style="background:${cfg.ramp[0]}"></span>&lt; ${cfg.format(breaks[0])}</span>`);
        for (let i = 1; i < breaks.length; i++) {
            items.push(`<span class="legend-item"><span class="legend-swatch" style="background:${cfg.ramp[i]}"></span>${cfg.format(breaks[i - 1])} – ${cfg.format(breaks[i])}</span>`);
        }
        items.push(`<span class="legend-item"><span class="legend-swatch" style="background:${cfg.ramp[Math.min(breaks.length, cfg.ramp.length - 1)]}"></span>&gt; ${cfg.format(breaks[breaks.length - 1])}</span>`);
        items.push(`<span class="legend-item legend-nodata"><span class="legend-swatch"></span>sem dados</span>`);
        items.push('</div>');
        el.innerHTML = items.join('');
    }

    function renderMetricDesc() {
        const el = document.getElementById('mapa-metric-desc');
        const btn = document.querySelector(`.mt-btn[data-metric="${state.metric}"]`);
        const isCitizen = !document.documentElement.classList.contains('audit-mode');
        const desc = btn
            ? (isCitizen ? (btn.dataset.descLay || btn.dataset.desc || '') : (btn.dataset.desc || ''))
            : '';
        if (el) el.textContent = desc;
        // popover comeca fechado a cada troca de metrica
        if (el) el.hidden = true;
        const infoBtn = document.getElementById('mapaInfoBtn');
        if (infoBtn) infoBtn.setAttribute('aria-expanded', 'false');
    }

    function wireMetricDescToggle() {
        const el = document.getElementById('mapa-metric-desc');
        const btn = document.getElementById('mapaInfoBtn');
        if (!el || !btn) return;
        const close = () => { el.hidden = true; btn.setAttribute('aria-expanded', 'false'); };
        btn.addEventListener('click', (ev) => {
            ev.stopPropagation();
            const open = el.hidden;
            el.hidden = !open;
            btn.setAttribute('aria-expanded', open ? 'true' : 'false');
        });
        document.addEventListener('click', (ev) => {
            if (el.hidden) return;
            if (ev.target === btn || el.contains(ev.target)) return;
            close();
        });
        document.addEventListener('keydown', (ev) => { if (ev.key === 'Escape') close(); });
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
            btn.setAttribute('aria-pressed', btn.classList.contains('active') ? 'true' : 'false');
            btn.addEventListener('click', () => {
                document.querySelectorAll('.mt-btn').forEach(b => {
                    b.classList.remove('active');
                    b.setAttribute('aria-pressed', 'false');
                });
                btn.classList.add('active');
                btn.setAttribute('aria-pressed', 'true');
                state.metric = btn.dataset.metric;
                const note = document.getElementById('mapa-cutoff-note');
                if (note) {
                    note.style.display = state.metric === 'pago_per_capita' ? 'none' : '';
                }
                updateLayer();
            });
        });
    }

    async function fetchJson(url) {
        const res = await fetch(url);
        if (!res.ok) throw new Error(`${url} retornou ${res.status}`);
        return res.json();
    }

    function renderMapError(message) {
        const el = document.getElementById('mapa-pb');
        if (el) {
            el.innerHTML = `<div class="mapa-error" role="status">${message}</div>`;
        }
        const legend = document.getElementById('mapa-legend');
        if (legend) legend.innerHTML = '';
    }

    async function init() {
        let dataWarning = false;
        try {
            state.geojson = await fetchJson('/static/geo/pb-municipios.geojson');
            const [dataRes, popRes] = await Promise.allSettled([
                fetchJson('/api/mapa/pb'),
                fetchJson('/static/geo/pb-populacao.json'),
            ]);
            if (dataRes.status === 'fulfilled') {
                state.data = dataRes.value;
                state.dataIdx = buildDataIndex(dataRes.value);
            } else {
                state.data = {};
                state.dataIdx = {};
                dataWarning = true;
            }
            state.pop = popRes.status === 'fulfilled' ? popRes.value : {};
        } catch (err) {
            console.warn('mapa init failed', err);
            renderMapError('Nao foi possivel carregar o mapa agora. Tente novamente em instantes.');
            return;
        }
        computeAllMetricBreaks();
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
        wireMetricDescToggle();
        renderLegend();
        renderMetricDesc();
        if (dataWarning) {
            const note = document.getElementById('mapa-cutoff-note');
            if (note) note.textContent = 'Mapa carregado, mas os indicadores municipais nao responderam agora.';
        }
    }

    document.addEventListener('DOMContentLoaded', init);
    // Re-render metric desc when citizen/auditor mode changes
    document.addEventListener('modechange', () => {
        try { renderMetricDesc(); } catch(e) {}
    });
})();
