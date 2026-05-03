// === components/finding-card.js ===
function renderFindingCard(card, queryId, data, municipio) {
    const countEl = card.querySelector('[data-count]');
    const body = card.querySelector('.finding-body');
    const rowCount = data.row_count || data.rows.length;

    countEl.textContent = rowCount;
    card.dataset.count = String(rowCount);
    if (rowCount === 0) {
        card.classList.add('is-empty', 'collapsed');
        body.innerHTML = '<p class="text-sm text-muted">Nenhum registro encontrado.</p>';
    } else {
        body.innerHTML = buildResultTable(queryId, data.columns, data.rows, municipio);
        initDataTables(body);
        initMobileDescriptions(body);
        initClickableRows(body);
    }
    body.classList.add('fade-in');
    setTimeout(() => body.classList.remove('fade-in'), 300);
    card.classList.remove('loading');
    card.setAttribute('aria-busy', 'false');
}

