// === pages/cidade-bootstrap.js ===
async function bootstrapCityReport(municipio, uf, dataInicio, dataFim, inicial = false) {
    if (_dateFilterBusy) return;
    uf = uf || 'PB';
    const nextInicio = dataInicio || null;
    const nextFim = dataFim || null;
    if ((nextInicio && !nextFim) || (!nextInicio && nextFim)) {
        _setDateFilterStatus('Informe data inicial e final antes de filtrar.', 'error');
        return;
    }
    _dateFilterBusy = true;
    _setDateFilterButtonBusy(true);
    if (inicial) {
        // A foto do SSR já está visível antes de qualquer resposta assíncrona.
        _currentMunicipio = municipio;
        _currentUf = uf;
        _dateInicio = nextInicio;
        _dateFim = nextFim;
        _syncDateFilterUI();
    }
    _setDateFilterStatus('Atualizando dados do período...');
    _setLiveRefreshState(true);
    let confirmou = false;
    try {
        const body = _buildBody(municipio, uf, nextInicio, nextFim);
        const [perfil, indicadores] = await Promise.all([
            _lerDadosPeriodo('/api/perfil', body),
            _lerDadosPeriodo(`/api/kpis/${encodeURIComponent(municipio)}`, body),
        ]);
        const dadosPerfil = perfil?.perfil || perfil;
        if (!dadosPerfil?.municipio || !Array.isArray(indicadores?.kpis)) {
            throw new Error('Resposta incompleta para o período solicitado');
        }
        _currentMunicipio = municipio;
        _currentUf = uf;
        _dateInicio = nextInicio;
        _dateFim = nextFim;
        _setDateInputs(nextInicio, nextFim);
        _syncDateFilterUI();
        _exibirPerfilDoPeriodo(perfil);
        _exibirKpisDoPeriodo(indicadores);
        confirmou = true;
        if (!inicial) _resetCityPanelsLoading();
        const completo = await _carregarPaineisDoPeriodo(municipio, uf, _getPeriodo());
        if (completo) _setDateFilterStatus(inicial ? '' : 'Filtro aplicado.');
        else _setDateFilterStatus('Período atualizado, mas nem todos os painéis foram carregados.', 'error');
    } catch (err) {
        console.warn('Falha ao atualizar filtro de período', err);
        _setDateInputs(_dateInicio, _dateFim);
        _syncDateFilterUI();
        _setDateFilterStatus(confirmou
            ? 'Período atualizado, mas nem todos os painéis foram carregados.'
            : 'Não foi possível atualizar. O período exibido foi mantido.', 'error');
    } finally {
        _dateFilterBusy = false;
        _setDateFilterButtonBusy(false);
        _setLiveRefreshState(false);
    }
}

async function _carregarPaineisDoPeriodo(municipio, uf, periodo) {
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
            initFornecedoresFilterChips(fornPanel);
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
            initServidoresFilterChips(servPanel);
            initMobileDescriptions(servPanel);
            initClickableRows(servPanel);
        } else {
            panelPromises.push(loadAsyncPanel('servidores', municipio, uf));
        }
    }

    let completo = (await Promise.all(panelPromises)).every(ok => ok !== false);

    const cards = Array.from(document.querySelectorAll('.finding-card[data-query]'));
    if (!cards.length) return completo;

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
                    completo = false;
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
                completo = false;
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
    return completo;
}
