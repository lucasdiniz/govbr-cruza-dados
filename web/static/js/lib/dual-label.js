// === lib/dual-label.js ===
// Gera um par de spans citizen/auditor para rotular UI em dois modos.
// Uso: `<span class="stat-label">${dualLabel('Recebido','Total pago')}</span>`
// Se auditor for omitido, usa citizen para ambos (sem duplicar markup).
// Tooltip opcional no span cidadao com o termo tecnico (acessivel via tap).
function dualLabel(citizen, auditor, opts) {
    const aud = (auditor == null) ? citizen : auditor;
    if (citizen === aud) return String(citizen);
    const tip = (opts && opts.tip !== false) ? ` data-tip="Termo t&eacute;cnico: ${aud}"` : '';
    const termCls = (opts && opts.tip !== false) ? ' term' : '';
    return `<span class="citizen-only${termCls}"${tip}>${citizen}</span><span class="auditor-only">${aud}</span>`;
}
// Expose globally for inline usage dentro de template literals
window.dualLabel = dualLabel;

function mobileDescToggleHtml() {
    return `<button type="button" class="mobile-desc-toggle" data-mobile-desc-next aria-expanded="false" aria-label="Ver descri&ccedil;&atilde;o" title="Ver descri&ccedil;&atilde;o">?</button>`;
}

