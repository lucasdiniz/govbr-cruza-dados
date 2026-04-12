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

async function bootstrapCityReport(municipio) {
    await Promise.all([
        loadAsyncPanel('fornecedores', municipio),
        loadAsyncPanel('servidores', municipio),
    ]);

    const cards = Array.from(document.querySelectorAll('.finding-card[data-query]'));
    if (!cards.length) return;

    await runLimited(cards, 2, async (card) => {
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

async function loadAsyncPanel(panelName, municipio) {
    const panel = document.querySelector(`[data-async-panel="${panelName}"]`);
    if (!panel) return;

    try {
        const response = await fetch(`/api/top/${panelName}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ municipio }),
        });
        panel.innerHTML = await response.text();
        initDataTables(panel);
        initInteractiveToggles(panel);
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
        const rows = Array.from(tableShell.querySelectorAll('tbody tr'));
        const pageSize = Number(tableShell.dataset.pageSize || 12);
        let filteredRows = rows;
        let page = 1;

        const renderPage = () => {
            const totalPages = Math.max(1, Math.ceil(filteredRows.length / pageSize));
            if (page > totalPages) page = totalPages;
            const start = (page - 1) * pageSize;
            const pageRows = filteredRows.slice(start, start + pageSize);

            rows.forEach((row) => {
                row.style.display = pageRows.includes(row) ? '' : 'none';
            });

            if (meta) meta.textContent = `${filteredRows.length} registro(s) encontrados`;
            if (pageLabel) pageLabel.textContent = `Pagina ${page} de ${totalPages}`;
            if (prevBtn) prevBtn.disabled = page === 1;
            if (nextBtn) nextBtn.disabled = page === totalPages;
        };

        filterInput?.addEventListener('input', () => {
            const term = filterInput.value.trim().toLowerCase();
            filteredRows = rows.filter((row) => row.textContent.toLowerCase().includes(term));
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

document.addEventListener('DOMContentLoaded', () => {
    initDataTables(document);
    initInteractiveToggles(document);
});

function initInteractiveToggles(root = document) {
    root.querySelectorAll('[data-hide-medicos]').forEach((checkbox) => {
        if (checkbox.dataset.enhanced === 'true') return;
        checkbox.dataset.enhanced = 'true';

        const container = checkbox.closest('.disclaimer-box')?.parentElement;
        const rows = container ? Array.from(container.querySelectorAll('tbody tr[data-cargo]')) : [];

        const apply = () => {
            const hide = checkbox.checked;
            rows.forEach((row) => {
                const cargo = row.dataset.cargo || '';
                const isMedico = cargo.includes('medico');
                row.style.display = hide && isMedico ? 'none' : '';
            });
        };

        checkbox.addEventListener('change', apply);
        apply();
    });
}
