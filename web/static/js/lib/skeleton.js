// === lib/skeleton.js ===
// ── Skeleton helpers: gera HTML prenunciando formato do conteudo ───
function skeletonTableHtml(rows = 5, cols = 3) {
    const parts = ['<div class="skeleton-table">'];
    for (let i = 0; i < rows; i++) {
        parts.push('<div class="skeleton-row">');
        for (let c = 0; c < cols; c++) {
            const cls = c === 0 ? '' : (c === cols - 1 ? 'narrow' : 'wide');
            parts.push(`<div class="skeleton-block ${cls}"></div>`);
        }
        parts.push('</div>');
    }
    parts.push('</div>');
    return parts.join('');
}

function skeletonCardHtml(items = 3) {
    const parts = ['<div class="skeleton-card">'];
    for (let i = 0; i < items; i++) {
        parts.push(
            '<div class="skeleton-card-item">' +
                '<div class="skeleton-block avatar"></div>' +
                '<div class="skeleton-card-lines">' +
                    '<div class="skeleton-block title"></div>' +
                    '<div class="skeleton-block subtitle"></div>' +
                '</div>' +
                '<div class="skeleton-block tag"></div>' +
            '</div>'
        );
    }
    parts.push('</div>');
    return parts.join('');
}

