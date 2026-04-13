document.querySelectorAll('.tab:not(:disabled)').forEach((tab) => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.tab').forEach((item) => item.classList.remove('active'));
        document.querySelectorAll('.tab-panel').forEach((panel) => panel.classList.remove('active'));
        tab.classList.add('active');
        document.getElementById(`panel-${tab.dataset.tab}`)?.classList.add('active');
    });
});

function setupAutocomplete(inputId, listId, endpoint, onSelect) {
    const input = document.getElementById(inputId);
    const list = document.getElementById(listId);
    const status = document.getElementById('cidade-status');
    if (!input || !list) return;

    let timer = null;
    let highlightedIndex = -1;
    let suggestions = [];
    let selectedValue = '';

    const clearList = () => {
        list.innerHTML = '';
        list.classList.remove('open');
        highlightedIndex = -1;
    };

    const renderSuggestions = () => {
        list.innerHTML = '';
        if (!suggestions.length) {
            clearList();
            status && (status.textContent = 'Nenhuma cidade encontrada para esse trecho.');
            return;
        }

        suggestions.forEach((item, index) => {
            const li = document.createElement('li');
            li.textContent = item;
            li.className = 'ac-item';
            li.addEventListener('mousedown', (event) => {
                event.preventDefault();
                commitSelection(item);
            });
            if (index === highlightedIndex) li.classList.add('selected');
            list.appendChild(li);
        });
        list.classList.add('open');
    };

    const commitSelection = (value) => {
        selectedValue = value;
        input.value = value;
        clearList();
        if (status) status.textContent = `Abrindo relatorio de ${value}...`;
        onSelect(value);
    };

    input.addEventListener('input', () => {
        clearTimeout(timer);
        const query = input.value.trim();
        if (query !== selectedValue && status) status.textContent = 'Selecione uma cidade da lista para continuar.';
        selectedValue = '';
        if (query.length < 3) {
            clearList();
            return;
        }
        timer = setTimeout(async () => {
            try {
                const response = await fetch(`${endpoint}?q=${encodeURIComponent(query)}`);
                suggestions = await response.json();
                highlightedIndex = suggestions.length ? 0 : -1;
                renderSuggestions();
            } catch {
                clearList();
            }
        }, 180);
    });

    input.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
            event.preventDefault();
            if (highlightedIndex >= 0 && suggestions[highlightedIndex]) {
                commitSelection(suggestions[highlightedIndex]);
            }
            return;
        }

        if (event.key === 'ArrowDown') {
            event.preventDefault();
            if (!suggestions.length) return;
            highlightedIndex = Math.min(highlightedIndex + 1, suggestions.length - 1);
            renderSuggestions();
        }

        if (event.key === 'ArrowUp') {
            event.preventDefault();
            if (!suggestions.length) return;
            highlightedIndex = Math.max(highlightedIndex - 1, 0);
            renderSuggestions();
        }
    });

    input.addEventListener('blur', () => {
        window.setTimeout(() => {
            if (input.value.trim() !== selectedValue) {
                input.value = '';
                if (status) status.textContent = 'Escolha uma cidade da lista para abrir a analise.';
            }
            clearList();
        }, 120);
    });

    document.addEventListener('click', (event) => {
        if (!event.target.closest('.autocomplete-wrap')) clearList();
    });
}

setupAutocomplete('ac-cidade', 'aclist-cidade', '/api/autocomplete/municipio', (value) => {
    window.location.href = `/search/cidade?q=${encodeURIComponent(value)}`;
});

async function bootstrapCityReport(municipio, uf) {
    uf = uf || 'PB';
    // Single batch request for everything
    let batchData = {};
    try {
        const res = await fetch(`/api/batch/${encodeURIComponent(municipio)}`, { method: 'POST' });
        if (res.ok) batchData = await res.json();
    } catch {}

    // Render fornecedores and servidores from batch (or fallback to HTML endpoint)
    const fornPanel = document.querySelector('[data-async-panel="fornecedores"]');
    const servPanel = document.querySelector('[data-async-panel="servidores"]');
    const panelPromises = [];

    if (batchData.TOP_FORNECEDORES && batchData.TOP_FORNECEDORES.row_count > 0) {
        if (fornPanel) {
            fornPanel.innerHTML = buildFornecedoresPanel(batchData.TOP_FORNECEDORES);
            initDataTables(fornPanel);
        }
    } else {
        panelPromises.push(loadAsyncPanel('fornecedores', municipio, uf));
    }

    if (servPanel) {
        if (batchData.TOP_SERVIDORES && batchData.TOP_SERVIDORES.row_count > 0) {
            servPanel.innerHTML = buildServidoresPanel(batchData.TOP_SERVIDORES);
            initDataTables(servPanel);
            initInteractiveToggles(servPanel);
            initExpandableRows(servPanel);
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
                    body: JSON.stringify({ municipio }),
                });

                if (!response.ok) {
                    countEl.textContent = 'Tempo excedido';
                    body.innerHTML = '<p class="text-sm text-muted">Esse bloco nao terminou a tempo nesta tentativa.</p>';
                    card.classList.remove('loading');
                    card.classList.add('is-timeout');
                    updateSectionSummaries();
                    return;
                }

                const html = await response.text();
                const rowCount = Number(response.headers.get('X-Row-Count') || 0);
                countEl.textContent = rowCount;
                card.dataset.count = String(rowCount);
                body.innerHTML = html;
                const exportLink = body.querySelector('[data-export-link]');
                if (exportLink) exportLink.href = `/api/export/${queryId}?municipio=${encodeURIComponent(municipio)}`;
                if (rowCount === 0) card.classList.add('is-empty');
                card.classList.remove('loading');
                initDataTables(body);
            } catch {
                countEl.textContent = 'Erro';
                body.innerHTML = '<p class="text-sm text-muted">Nao foi possivel carregar este bloco agora.</p>';
                card.classList.remove('loading');
                card.classList.add('is-timeout');
            }
            updateSectionSummaries();
        });
    }
}

function renderFindingCard(card, queryId, data, municipio) {
    const countEl = card.querySelector('[data-count]');
    const body = card.querySelector('.finding-body');
    const rowCount = data.row_count || data.rows.length;

    countEl.textContent = rowCount;
    card.dataset.count = String(rowCount);
    if (rowCount === 0) {
        card.classList.add('is-empty');
        body.innerHTML = '<p class="text-sm text-muted">Nenhum registro encontrado.</p>';
    } else {
        body.innerHTML = buildResultTable(queryId, data.columns, data.rows, municipio);
        initDataTables(body);
    }
    card.classList.remove('loading');
}

function buildResultTable(queryId, columns, rows, municipio) {
    const headerCells = columns.map(c =>
        `<th>${c.replace(/_/g, ' ')}</th>`
    ).join('');
    const bodyRows = rows.map(row => {
        const cells = row.map(val => {
            if (val === null || val === undefined) return '<td>-</td>';
            if (typeof val === 'boolean') return `<td>${val ? 'Sim' : 'Nao'}</td>`;
            if (Array.isArray(val)) return `<td>${val.join(', ')}</td>`;
            return `<td>${val}</td>`;
        }).join('');
        return `<tr>${cells}</tr>`;
    }).join('');

    return `<div class="result-block">
        <div class="result-toolbar">
            <div></div>
            <a href="/api/export/${queryId}?municipio=${encodeURIComponent(municipio)}" data-export-link class="btn btn-outline btn-sm">Exportar CSV</a>
        </div>
        <div class="table-shell js-data-table" data-page-size="10">
            <div class="table-actions">
                <input type="search" class="table-filter" placeholder="Filtrar nesta tabela">
                <p class="table-meta text-sm text-muted" data-table-meta></p>
            </div>
            <div class="tbl-wrap">
                <table>
                    <thead><tr>${headerCells}</tr></thead>
                    <tbody>${bodyRows}</tbody>
                </table>
            </div>
            <div class="table-pagination">
                <button type="button" class="btn btn-outline btn-sm" data-page-prev>Anterior</button>
                <p class="text-sm text-muted" data-page-label></p>
                <button type="button" class="btn btn-outline btn-sm" data-page-next>Proxima</button>
            </div>
        </div>
    </div>`;
}

function _colIndex(cols, name) {
    return cols.indexOf(name);
}

function _val(row, cols, name) {
    const i = _colIndex(cols, name);
    return i >= 0 ? row[i] : null;
}

function _shortBrl(v) {
    const n = parseFloat(v) || 0;
    const a = Math.abs(n);
    if (a >= 1e9) return `R$ ${(n/1e9).toFixed(1)} bi`;
    if (a >= 1e6) return `R$ ${(n/1e6).toFixed(1)} mi`;
    if (a >= 1e3) return `R$ ${(n/1e3).toFixed(1)} mil`;
    return `R$ ${n.toFixed(0)}`;
}

function _shortNum(v) {
    const n = parseFloat(v) || 0;
    const a = Math.abs(n);
    if (a >= 1e6) return `${(n/1e6).toFixed(1)} mi`;
    if (a >= 1e3) return `${(n/1e3).toFixed(1)} mil`;
    return `${n.toFixed(0)}`;
}

function _esc(v) {
    if (v === null || v === undefined) return '-';
    return String(v).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function buildFornecedoresPanel(data) {
    const cols = data.columns;
    const bodyRows = data.rows.map(r => {
        const nome = _esc(_val(r, cols, 'nome_credor'));
        const total = _shortBrl(_val(r, cols, 'total_pago'));
        const qtd = _shortNum(_val(r, cols, 'qtd_empenhos'));
        let badges = '';
        if (_val(r, cols, 'flag_ceis')) badges += '<span class="badge badge-red">Sancao ativa</span>';
        if (_val(r, cols, 'flag_pgfn')) badges += '<span class="badge badge-yellow">Divida ativa</span>';
        if (_val(r, cols, 'flag_inativa')) badges += '<span class="badge badge-gray">Cadastro inativo</span>';
        if (!badges) badges = '<span class="text-sm text-muted">Sem sinal automatico</span>';
        return `<tr><td>${nome}</td><td class="text-right">${total}</td><td class="text-right">${qtd}</td><td>${badges}</td></tr>`;
    }).join('');

    return `<section class="result-block">
        <div class="result-toolbar"><div>
            <h3 class="card-title">Maiores fornecedores do municipio</h3>
            <p class="text-muted text-sm">Concentracao de pagamentos e sinais automaticos de cada fornecedor.</p>
        </div></div>
        <div class="table-shell js-data-table" data-page-size="10">
            <div class="table-actions">
                <input type="search" class="table-filter" placeholder="Filtrar nesta tabela" aria-label="Filtrar fornecedores">
                <p class="table-meta text-sm text-muted" data-table-meta></p>
            </div>
            <div class="tbl-wrap"><table>
                <thead><tr><th>Fornecedor</th><th class="text-right">Total Pago</th><th class="text-right">Empenhos</th><th>Sinais de Atencao</th></tr></thead>
                <tbody>${bodyRows}</tbody>
            </table></div>
            <div class="table-pagination">
                <button type="button" class="btn btn-outline btn-sm" data-page-prev>Anterior</button>
                <p class="text-sm text-muted" data-page-label></p>
                <button type="button" class="btn btn-outline btn-sm" data-page-next>Proxima</button>
            </div>
        </div>
    </section>`;
}

function buildServidoresPanel(data) {
    const cols = data.columns;
    const bodyRows = data.rows.map(r => {
        const nome = _esc(_val(r, cols, 'nome_servidor'));
        const cargo = _esc(_val(r, cols, 'cargo') || '-');
        const salario = _shortBrl(_val(r, cols, 'maior_salario'));
        const qtdEmpresas = _val(r, cols, 'qtd_empresas_socio') || 0;
        const cnpjs = _val(r, cols, 'cnpjs_socio') || [];
        let badges = '';
        if (_val(r, cols, 'flag_conflito_interesses')) {
            badges += qtdEmpresas > 0
                ? `<span class="badge badge-red">Socio de ${qtdEmpresas} empresa${qtdEmpresas > 1 ? 's' : ''} que fornece ao municipio</span>`
                : '<span class="badge badge-red">Socio de empresa que fornece ao municipio</span>';
        }
        if (_val(r, cols, 'flag_duplo_vinculo_estado')) badges += '<span class="badge badge-red">Tambem recebe pagamentos do governo estadual</span>';
        if (_val(r, cols, 'flag_multi_empresa')) badges += `<span class="badge badge-yellow">Socio de ${qtdEmpresas || 'varias'} empresas</span>`;
        if (_val(r, cols, 'flag_bolsa_familia')) badges += '<span class="badge badge-yellow">Recebe Bolsa Familia</span>';
        if (_val(r, cols, 'flag_alto_salario_socio')) badges += '<span class="badge badge-yellow">Salario alto + vinculo societario</span>';
        if (!badges) badges = '<span class="text-sm text-muted">Combinacao de indicadores elevada</span>';

        const hasDetail = cnpjs.length > 0;
        const mainRow = `<tr data-cargo="${cargo.toLowerCase()}" ${hasDetail ? 'class="clickable-row" style="cursor:pointer"' : ''}><td>${nome} ${hasDetail ? '<span class="text-muted text-sm">&#9654;</span>' : ''}</td><td>${cargo}</td><td class="text-right">${salario}</td><td>${badges}</td></tr>`;
        let detailRow = '';
        if (hasDetail) {
            const cnpjList = cnpjs.map(c => `<code>${c}</code>`).join(', ');
            detailRow = `<tr class="detail-row" style="display:none"><td colspan="4"><div class="detail-content"><strong>CNPJs das empresas:</strong> ${cnpjList}</div></td></tr>`;
        }
        return mainRow + detailRow;
    }).join('');

    return `<section class="result-block">
        <div class="result-toolbar"><div>
            <h3 class="card-title">Servidores com sinais de atencao</h3>
            <p class="text-muted text-sm">Servidores que apresentam ao menos um sinal de risco nos cruzamentos automaticos: vinculo societario com fornecedores, duplo vinculo com o estado, recebimento de beneficio social ou acumulacao atipica. A Constituicao (art. 37, XVI) admite acumulacao para profissionais de saude — por padrao esses cargos ficam ocultos.</p>
        </div>
        <label class="toggle-row">
            <input type="checkbox" data-hide-medicos checked>
            <span>Ocultar medicos</span>
        </label></div>
        <div class="table-shell js-data-table" data-page-size="10">
            <div class="table-actions">
                <input type="search" class="table-filter" placeholder="Filtrar nesta tabela" aria-label="Filtrar servidores">
                <p class="table-meta text-sm text-muted" data-table-meta></p>
            </div>
            <div class="tbl-wrap"><table>
                <thead><tr><th>Servidor</th><th>Cargo</th><th class="text-right">Maior Salario</th><th>Sinais de Atencao</th></tr></thead>
                <tbody>${bodyRows}</tbody>
            </table></div>
            <div class="table-pagination">
                <button type="button" class="btn btn-outline btn-sm" data-page-prev>Anterior</button>
                <p class="text-sm text-muted" data-page-label></p>
                <button type="button" class="btn btn-outline btn-sm" data-page-next>Proxima</button>
            </div>
        </div>
    </section>`;
}

async function loadAsyncPanel(panelName, municipio, uf) {
    const panel = document.querySelector(`[data-async-panel="${panelName}"]`);
    if (!panel) return;

    // Get UF from data attribute if available
    const panelUf = uf || panel.dataset.uf || '';
    try {
        const response = await fetch(`/api/top/${panelName}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ municipio, uf: panelUf }),
        });
        panel.innerHTML = await response.text();
        initDataTables(panel);
        initInteractiveToggles(panel);
        initExpandableRows(panel);
    } catch {
        panel.innerHTML = '<p class="text-sm text-muted">Nao foi possivel carregar este bloco agora.</p>';
    }
}

function updateSectionSummaries() {
    document.querySelectorAll('.report-section').forEach((section) => {
        const cards = Array.from(section.querySelectorAll('.finding-card'));
        let total = 0;
        let findings = 0;

        cards.forEach((card) => {
            const count = Number(card.dataset.count || 0);
            total += count;
            if (count > 0) findings += 1;
        });

        const summary = section.querySelector('[data-section-total]');
        if (!summary) return;

        if (!findings) {
            summary.textContent = 'Nenhum achado carregado';
            return;
        }

        summary.textContent = `${total} registros em ${findings} blocos`;
    });
}

async function runLimited(items, limit, worker) {
    const results = [];
    const queue = [...items];

    async function next() {
        const item = queue.shift();
        if (!item) return;
        results.push(await worker(item));
        await next();
    }

    await Promise.all(Array.from({ length: Math.min(limit, items.length) }, () => next()));
    return results;
}

function initDataTables(root = document) {
    root.querySelectorAll('.js-data-table').forEach((tableShell) => {
        if (tableShell.dataset.enhanced === 'true') return;
        tableShell.dataset.enhanced = 'true';

        const filterInput = tableShell.querySelector('.table-filter');
        const meta = tableShell.querySelector('[data-table-meta]');
        const pageLabel = tableShell.querySelector('[data-page-label]');
        const prevBtn = tableShell.querySelector('[data-page-prev]');
        const nextBtn = tableShell.querySelector('[data-page-next]');
        const rows = Array.from(tableShell.querySelectorAll('tbody tr:not(.detail-row)'));
        const pageSize = Number(tableShell.dataset.pageSize || 12);
        let filteredRows = rows;
        let page = 1;
        let externalFilter = null; // set by toggles (e.g. ocultar medicos)

        const applyFilters = () => {
            const term = filterInput ? filterInput.value.trim().toLowerCase() : '';
            filteredRows = rows.filter((row) => {
                if (term && !row.textContent.toLowerCase().includes(term)) return false;
                if (externalFilter && !externalFilter(row)) return false;
                return true;
            });
        };

        const renderPage = () => {
            const totalPages = Math.max(1, Math.ceil(filteredRows.length / pageSize));
            if (page > totalPages) page = totalPages;
            const start = (page - 1) * pageSize;
            const pageRows = filteredRows.slice(start, start + pageSize);

            rows.forEach((row) => {
                const visible = pageRows.includes(row);
                row.style.display = visible ? '' : 'none';
                // Also hide/show associated detail row
                const detailRow = row.nextElementSibling;
                if (detailRow && detailRow.classList.contains('detail-row')) {
                    detailRow.style.display = (visible && row.classList.contains('expanded')) ? '' : 'none';
                }
            });

            if (meta) meta.textContent = `${filteredRows.length} registro(s) encontrados`;
            if (pageLabel) pageLabel.textContent = `Pagina ${page} de ${totalPages}`;
            if (prevBtn) prevBtn.disabled = page === 1;
            if (nextBtn) nextBtn.disabled = page === totalPages;
        };

        // Expose refilter for external toggles
        tableShell._refilter = (filterFn) => {
            externalFilter = filterFn;
            applyFilters();
            page = 1;
            renderPage();
        };

        // Column sorting
        const headers = Array.from(tableShell.querySelectorAll('thead th'));
        let sortCol = -1;
        let sortAsc = true;

        headers.forEach((th, colIndex) => {
            th.style.cursor = 'pointer';
            th.addEventListener('click', () => {
                if (sortCol === colIndex) {
                    sortAsc = !sortAsc;
                } else {
                    sortCol = colIndex;
                    sortAsc = true;
                }
                headers.forEach(h => h.classList.remove('sort-asc', 'sort-desc'));
                th.classList.add(sortAsc ? 'sort-asc' : 'sort-desc');

                filteredRows.sort((a, b) => {
                    const cellA = a.children[colIndex]?.textContent.trim() || '';
                    const cellB = b.children[colIndex]?.textContent.trim() || '';
                    // Try numeric comparison (handle R$, %, commas)
                    const numA = parseFloat(cellA.replace(/[R$%\s.]/g, '').replace(',', '.'));
                    const numB = parseFloat(cellB.replace(/[R$%\s.]/g, '').replace(',', '.'));
                    if (!isNaN(numA) && !isNaN(numB)) {
                        return sortAsc ? numA - numB : numB - numA;
                    }
                    return sortAsc ? cellA.localeCompare(cellB, 'pt-BR') : cellB.localeCompare(cellA, 'pt-BR');
                });
                page = 1;
                renderPage();
            });
        });

        filterInput?.addEventListener('input', () => {
            applyFilters();
            page = 1;
            renderPage();
        });

        prevBtn?.addEventListener('click', () => {
            page = Math.max(1, page - 1);
            renderPage();
        });

        nextBtn?.addEventListener('click', () => {
            const totalPages = Math.max(1, Math.ceil(filteredRows.length / pageSize));
            page = Math.min(totalPages, page + 1);
            renderPage();
        });

        renderPage();
    });
}

function initExpandableRows(root = document) {
    root.querySelectorAll('.clickable-row').forEach((row) => {
        if (row.dataset.expandable === 'true') return;
        row.dataset.expandable = 'true';
        row.addEventListener('click', () => {
            const detailRow = row.nextElementSibling;
            if (!detailRow || !detailRow.classList.contains('detail-row')) return;
            const isExpanded = row.classList.toggle('expanded');
            detailRow.style.display = isExpanded ? '' : 'none';
            const arrow = row.querySelector('.text-muted.text-sm');
            if (arrow) arrow.innerHTML = isExpanded ? '&#9660;' : '&#9654;';
        });
    });
}

document.addEventListener('DOMContentLoaded', () => {
    initDataTables(document);
    initInteractiveToggles(document);
    initExpandableRows(document);
});

function initInteractiveToggles(root = document) {
    root.querySelectorAll('[data-hide-medicos]').forEach((checkbox) => {
        if (checkbox.dataset.enhanced === 'true') return;
        checkbox.dataset.enhanced = 'true';

        const container = checkbox.closest('.result-block') || checkbox.closest('.table-shell')?.parentElement;
        const tableShell = container ? container.querySelector('.js-data-table') : null;

        const apply = () => {
            const hide = checkbox.checked;
            if (tableShell && tableShell._refilter) {
                tableShell._refilter(hide ? (row) => {
                    const cargo = (row.dataset.cargo || '').toLowerCase();
                    return !cargo.includes('medico');
                } : null);
            }
        };

        checkbox.addEventListener('change', apply);
        apply();
    });
}
