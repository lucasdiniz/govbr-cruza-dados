// === components/data-table.js ===
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
                row.style.display = pageRows.includes(row) ? '' : 'none';
            });

            if (meta) meta.textContent = `${filteredRows.length} registro(s) encontrados`;
            if (pageLabel) pageLabel.textContent = `Pagina ${page} de ${totalPages}`;
            if (prevBtn) prevBtn.disabled = page === 1;
            if (nextBtn) nextBtn.disabled = page === totalPages;
            const pager = tableShell.querySelector('.table-pagination');
            if (pager) pager.hidden = totalPages <= 1;
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
                    const cellElA = a.children[colIndex];
                    const cellElB = b.children[colIndex];
                    const cellA = cellElA?.textContent.trim() || '';
                    const cellB = cellElB?.textContent.trim() || '';
                    const numA = _sortNumber(cellElA);
                    const numB = _sortNumber(cellElB);
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

function _sortNumber(cell) {
    if (!cell) return NaN;
    if (cell.dataset && cell.dataset.sort !== undefined) {
        const byData = parseFloat(String(cell.dataset.sort).replace(',', '.'));
        if (!isNaN(byData)) return byData;
    }
    const text = (cell.textContent || '').toLowerCase();
    let mult = 1;
    if (/\bbi\b/.test(text)) mult = 1e9;
    else if (/\bmi\b/.test(text)) mult = 1e6;
    else if (/\bmil\b/.test(text)) mult = 1e3;
    const cleaned = text
        .replace(/r\$|%|bi|mi|mil|\s/g, '')
        .replace(/\./g, '')
        .replace(',', '.');
    const n = parseFloat(cleaned);
    return isNaN(n) ? NaN : n * mult;
}

