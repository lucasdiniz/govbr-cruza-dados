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
        let rows = Array.from(tableShell.querySelectorAll('tbody tr'));
        const pageSize = Number(tableShell.dataset.pageSize || 12);
        let filteredRows = rows;
        let page = 1;
        let externalFilter = null; // set by toggles (e.g. ocultar medicos)

        // === Progressive loading (PR #199) ===
        // Tabelas grandes (top-servidores/top-fornecedores em JP tem 51k/13k rows)
        // viraram TTI lento por SSR sincrono de DOM massivo. Template emite
        // primeira leva (50 rows) em <tbody> real + tail em
        // <script type="text/html" data-rest-rows> (inert text, sem custo de DOM).
        // Hidratamos o tail apos paint inicial via requestIdleCallback.
        //
        // Hidratacao = idempotente:
        //   1. lookup do <script data-rest-rows>; se nao existe, no-op
        //   2. parse innerHTML em <table><tbody> auxiliar
        //   3. append novos <tr> no tbody real
        //   4. recolect rows, re-init clickable, applyFilters + renderPage
        //   5. emit umami `tabela-hidratada`
        //
        // Force-flush: capture-phase listener no tableShell para click/input/keydown.
        // Qualquer interacao do usuario ANTES do RIC disparar forca hidratacao
        // sincrona imediata. Evita race onde chip click filtra apenas as 50 iniciais.
        const tbody = tableShell.querySelector('tbody');
        const restScript = tableShell.querySelector('script[type="text/html"][data-rest-rows]');
        const hasProgressive = !!(restScript && tbody);
        let hydrated = !hasProgressive;
        let hydrateScheduled = 0;
        let hydrationStartTs = 0;

        const _hydrateRest = (forced = false) => {
            if (hydrated) return;
            hydrated = true;
            if (hydrateScheduled && typeof cancelIdleCallback === 'function') {
                cancelIdleCallback(hydrateScheduled);
            }
            hydrateScheduled = 0;
            const t0 = (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now();
            const html = restScript.textContent || '';
            const tmp = document.createElement('table');
            tmp.innerHTML = '<tbody>' + html + '</tbody>';
            const tmpBody = tmp.querySelector('tbody');
            const frag = document.createDocumentFragment();
            while (tmpBody && tmpBody.firstChild) frag.appendChild(tmpBody.firstChild);
            tbody.appendChild(frag);
            restScript.remove();
            rows = Array.from(tbody.querySelectorAll('tr'));
            if (typeof initClickableRows === 'function') {
                try { initClickableRows(tbody); } catch (e) { /* no-op */ }
            }
            applyFilters();
            renderPage();
            const t1 = (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now();
            const ms = Math.round(t1 - (hydrationStartTs || t0));
            if (typeof trackEvent === 'function') {
                const tabela = tableShell.dataset.tableId || 'unknown';
                if (tabela !== 'unknown') {
                    trackEvent('tabela-hidratada', {
                        tabela,
                        total: Number(tableShell.dataset.progressiveTotal || rows.length),
                        initial: Number(tableShell.dataset.progressiveInitial || 0),
                        ms_to_hydrate: ms,
                        forced,
                    });
                }
            }
        };

        const applyFilters = () => {
            const term = filterInput ? filterInput.value.trim().toLowerCase() : '';
            filteredRows = rows.filter((row) => {
                if (term && !row.textContent.toLowerCase().includes(term)) return false;
                if (externalFilter && !externalFilter(row)) return false;
                return true;
            });
        };

        // Optimizacao: em datasets grandes (ate 51k rows apos ADR-0011),
        // iterar todas as rows e setar style.display gera N style recalc.
        // Em vez disso, marcamos qualquer row visivel com data-page-row=""
        // (na hora) e usamos CSS pra esconder o resto. Mas pra simplicidade
        // e zero-mudanca em outras tabelas pequenas, mantemos o forEach
        // mas dentro de requestAnimationFrame agrupado.
        let renderRaf = 0;
        const renderPage = () => {
            const totalPages = Math.max(1, Math.ceil(filteredRows.length / pageSize));
            if (page > totalPages) page = totalPages;
            const start = (page - 1) * pageSize;
            const pageRows = filteredRows.slice(start, start + pageSize);
            const visible = new Set(pageRows);

            rows.forEach((row) => {
                row.style.display = visible.has(row) ? '' : 'none';
            });

            if (meta) meta.textContent = `${filteredRows.length} registro(s) encontrados`;
            if (pageLabel) pageLabel.textContent = `Pagina ${page} de ${totalPages}`;
            if (prevBtn) prevBtn.disabled = page === 1;
            if (nextBtn) nextBtn.disabled = page === totalPages;
            const pager = tableShell.querySelector('.table-pagination');
            if (pager) pager.hidden = totalPages <= 1;
        };

        // Expose refilter for external toggles. Retorna o numero de rows que
        // passaram pelos filtros (NAO o numero de rows visiveis na pagina —
        // renderPage so mostra pageSize por vez). Usado por componentes como
        // servidores-filter-chips.js pra reportar metrica de filtro correta.
        //
        // Em datasets grandes (ate 51k rows apos ADR-0011), aplicamos
        // aria-busy + defer via requestAnimationFrame pra browser repintar
        // o estado pressed do chip antes do reflow pesado. Sem isso, o
        // usuario toca o chip e UI freeza ~500-1500ms em mid-tier mobile
        // sem feedback — leva a toggle duplicado por re-tap.
        tableShell._refilter = (filterFn) => {
            externalFilter = filterFn;
            applyFilters();
            page = 1;

            // Defer apenas pra datasets grandes (>1k); pequenos seguem sync
            // pra evitar flicker desnecessario.
            if (rows.length > 1000) {
                tableShell.setAttribute('aria-busy', 'true');
                if (renderRaf) cancelAnimationFrame(renderRaf);
                renderRaf = requestAnimationFrame(() => {
                    renderPage();
                    tableShell.removeAttribute('aria-busy');
                    renderRaf = 0;
                });
            } else {
                renderPage();
            }
            return filteredRows.length;
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
            const from = page;
            page = Math.max(1, page - 1);
            renderPage();
            _trackPageChange(tableShell, from, page, filteredRows.length, pageSize, 'prev');
        });

        nextBtn?.addEventListener('click', () => {
            const totalPages = Math.max(1, Math.ceil(filteredRows.length / pageSize));
            const from = page;
            page = Math.min(totalPages, page + 1);
            renderPage();
            _trackPageChange(tableShell, from, page, filteredRows.length, pageSize, 'next');
        });

        renderPage();

        if (hasProgressive) {
            hydrationStartTs = (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now();
            const flushOnInteraction = () => _hydrateRest(true);
            // Capture-phase: roda ANTES dos handlers de filtro/chip/sort/paginacao,
            // garantindo que applyFilters() veja a lista completa de rows.
            tableShell.addEventListener('click', flushOnInteraction, { capture: true, once: true });
            tableShell.addEventListener('input', flushOnInteraction, { capture: true, once: true });
            tableShell.addEventListener('keydown', flushOnInteraction, { capture: true, once: true });
            if (typeof requestIdleCallback === 'function') {
                hydrateScheduled = requestIdleCallback(() => _hydrateRest(false), { timeout: 1500 });
            } else {
                setTimeout(() => _hydrateRest(false), 0);
            }
        }
    });
}

// Emite tabela-pagina-mudou no painel Umami. Identifica a tabela via
// data-table-id (opt-in nos templates principais); cai em 'unknown' pra
// nao spammar evento sem identificacao util. No-op se page nao mudou
// (clique em prev na pag 1 ou next na ultima).
function _trackPageChange(tableShell, from, to, totalRows, pageSize, via) {
    if (from === to) return;
    if (typeof trackEvent !== 'function') return;
    const tabela = tableShell.dataset.tableId || 'unknown';
    if (tabela === 'unknown') return;
    const totalPaginas = Math.max(1, Math.ceil(totalRows / pageSize));
    trackEvent('tabela-pagina-mudou', {
        tabela,
        de: from,
        para: to,
        total_paginas: totalPaginas,
        via,
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

