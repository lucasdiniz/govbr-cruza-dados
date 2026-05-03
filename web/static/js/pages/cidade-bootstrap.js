// === pages/cidade-bootstrap.js ===
async function bootstrapCityReport(municipio, uf, dataInicio, dataFim) {
    uf = uf || 'PB';
    const nextInicio = dataInicio || null;
    const nextFim = dataFim || null;
    if ((nextInicio && !nextFim) || (!nextInicio && nextFim)) {
        _setDateFilterStatus('Informe data inicial e final antes de filtrar.', 'error');
        return;
    }
    _currentMunicipio = municipio;
    _currentUf = uf;
    _dateInicio = nextInicio;
    _dateFim = nextFim;

    const periodo = _getPeriodo();

    _syncDateFilterUI();

    // Single batch request for everything (skip for CUSTOM — no cache)
    let batchData = {};
    if (periodo !== 'CUSTOM') {
        try {
            const batchUrl = `/api/batch/${encodeURIComponent(municipio)}${periodo ? '?periodo=' + periodo : ''}`;
            const res = await fetch(batchUrl, { method: 'POST' });
            if (res.ok) batchData = await res.json();
        } catch {}
    }

    // Heatmap mensal (PB apenas, all-time — não responde ao filtro de data)
    if ((uf || 'PB') === 'PB' && document.getElementById('heatmapGrid')) {
        _loadHeatmap(municipio);
    }

    // Hero/insights/KPI strip + narrativa SEMPRE refrescam apos o boot.
    // Antes, isso era gated em `_isDateFiltered()`, mas como SSR agora pinta
    // em ANO (default 'Ano atual'), clicar 'Tudo' (sem datas) deixava a hero
    // e a KPI strip presas em ANO enquanto os paineis abaixo iam para
    // all-time. Refrescar sempre garante consistencia em ambas as direcoes
    // (ANO->Tudo e Tudo->ANO/Custom).
    _setLiveRefreshState(true);
    try {
        // /api/perfil retorna perfil + narrativa, ambos respeitando o periodo.
        await _refreshPerfilLive(municipio, uf);
        // /api/kpis retorna kpi strip + concentracao + score unificado.
        await _refreshKpisLive(municipio, uf);
    } finally {
        _setLiveRefreshState(false);
    }
    // Sempre cabla cliques no card de top-5 concentracao (independente de filtro):
    // SSR ja renderizou a versao all-time, queremos que clique abra dialog.
    _wireConcentracaoClicks();

    // Render fornecedores and servidores from batch (or fallback to HTML endpoint)
    const fornPanel = document.querySelector('[data-async-panel="fornecedores"]');
    const servPanel = document.querySelector('[data-async-panel="servidores"]');
    const panelPromises = [];

    if (batchData.TOP_FORNECEDORES && batchData.TOP_FORNECEDORES.row_count > 0) {
        if (fornPanel) {
            fornPanel.innerHTML = buildFornecedoresPanel(batchData.TOP_FORNECEDORES);
            fornPanel.setAttribute('aria-busy', 'false');
            initDataTables(fornPanel);
            initMobileDescriptions(fornPanel);
            initClickableRows(fornPanel);
        }
    } else {
        panelPromises.push(loadAsyncPanel('fornecedores', municipio, uf));
    }

    if (servPanel) {
        if (!_isDateFiltered() && batchData.TOP_SERVIDORES && batchData.TOP_SERVIDORES.row_count > 0) {
            const servData = batchData.TOP_SERVIDORES;
            servPanel.innerHTML = buildServidoresPanel(servData);
            servPanel.setAttribute('aria-busy', 'false');
            initDataTables(servPanel);
            initMobileDescriptions(servPanel);
            initClickableRows(servPanel);
        } else {
            panelPromises.push(loadAsyncPanel('servidores', municipio, uf));
        }
    }

    if (panelPromises.length) await Promise.all(panelPromises);

    const cards = Array.from(document.querySelectorAll('.finding-card[data-query]'));
    if (!cards.length) return;

    // Cards with cache: render instantly. Cards without: fetch individually.
    const uncachedCards = [];
    for (const card of cards) {
        const queryId = card.dataset.query;
        const cached = batchData[queryId];
        if (cached && cached.columns && cached.rows) {
            renderFindingCard(card, queryId, cached, municipio);
        } else {
            uncachedCards.push(card);
        }
    }
    updateSectionSummaries();

    // Fetch uncached cards individually (fallback)
    if (uncachedCards.length) {
        await runLimited(uncachedCards, 4, async (card) => {
            const queryId = card.dataset.query;
            const countEl = card.querySelector('[data-count]');
            const body = card.querySelector('.finding-body');
            try {
                const response = await fetch(`/api/run/${queryId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(_buildBody(municipio, uf)),
                });

                if (!response.ok) {
                    countEl.textContent = 'Tempo excedido';
                    body.innerHTML = '<p class="text-sm text-muted">Esse bloco nao terminou a tempo nesta tentativa.</p>';
                    card.classList.remove('loading');
                    card.setAttribute('aria-busy', 'false');
                    card.classList.add('is-timeout');
                    updateSectionSummaries();
                    return;
                }

                const html = await response.text();
                const rowCount = Number(response.headers.get('X-Row-Count') || 0);
                countEl.textContent = rowCount;
                card.dataset.count = String(rowCount);
                body.innerHTML = html;
                body.classList.add('fade-in');
                setTimeout(() => body.classList.remove('fade-in'), 300);
                const exportLink = body.querySelector('[data-export-link]');
                if (exportLink) {
                    let exportUrl = `/api/export/${queryId}?municipio=${encodeURIComponent(municipio)}`;
                    if (_dateInicio) exportUrl += `&data_inicio=${_dateInicio}`;
                    if (_dateFim) exportUrl += `&data_fim=${_dateFim}`;
                    exportLink.href = exportUrl;
                }
                if (rowCount === 0) card.classList.add('is-empty', 'collapsed');
                card.classList.remove('loading');
                card.setAttribute('aria-busy', 'false');
                initDataTables(body);
                initMobileDescriptions(body);
                initClickableRows(body);
            } catch {
                countEl.textContent = '—';
                const countLabel = countEl.nextElementSibling;
                if (countLabel) countLabel.style.display = 'none';
                body.innerHTML = '<p class="text-sm text-muted">Nao foi possivel carregar este bloco agora.</p>';
                card.classList.remove('loading');
                card.setAttribute('aria-busy', 'false');
                card.classList.add('is-timeout');
            }
            updateSectionSummaries();
        });
    }
}

