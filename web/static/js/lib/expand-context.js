// === lib/expand-context.js ===
function expandReportContext(target) {
    if (!target) return;
    const section = target.closest('.report-section');
    if (section) {
        section.classList.remove('report-collapsed');
        section.dataset.userToggled = 'true';
        const toggle = section.querySelector('[data-section-toggle]');
        if (toggle) toggle.setAttribute('aria-expanded', 'true');
    }
    if (target.classList.contains('finding-card')) {
        target.classList.remove('collapsed');
    }
    // Quando o alvo eh uma report-section inteira (ex: clique em KPI hero
    // -> #fornecedores-irregulares), expande TODOS os finding-cards filhos
    // para que o usuario veja a tabela maximizada e nao precise dar mais
    // um clique. Sem isso o usuario chega na section e ve cards colapsados.
    if (target.classList.contains('report-section')) {
        target.querySelectorAll('.finding-card.collapsed').forEach(c => {
            c.classList.remove('collapsed');
        });
    }
    // Tambem desfaz o estado collapsed em qualquer descendente direto que
    // o usuario possa querer ver (ex: target id="servidores" cobre o panel
    // top-servidores que tambem usa .collapsed).
    target.querySelectorAll(':scope > .collapsed, :scope .async-collapsed').forEach(el => {
        el.classList.remove('collapsed', 'async-collapsed');
    });
    // Secoes colapsaveis das paginas /empresa (<details class="empresa-collapsible-details">):
    // abrir quando o alvo eh a <section> wrapper, OU quando o alvo eh
    // um descendente da <details> (ex: usuario clica em link interno
    // que aponta pra um elemento DENTRO da PGFN).
    // Sem isso, anchor-auto-expand interceptaria o click + preventDefault,
    // o hashchange nao dispararia, e empresa-collapsible.js nunca abriria
    // a details.
    if (target.matches && target.matches('section.empresa-collapsible')) {
        const det = target.querySelector(':scope > .empresa-collapsible-details');
        if (det && !det.open) det.open = true;
    }
    const ancestorDetails = target.closest && target.closest('details.empresa-collapsible-details');
    if (ancestorDetails && !ancestorDetails.open) {
        ancestorDetails.open = true;
    }
}


