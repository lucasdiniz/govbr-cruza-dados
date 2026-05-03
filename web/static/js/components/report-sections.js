// === components/report-sections.js ===
function _setReportSectionCollapsed(section, collapsed) {
    if (!section) return;
    section.classList.toggle('report-collapsed', collapsed);
    const toggle = section.querySelector('[data-section-toggle]');
    if (toggle) toggle.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
}

function initReportSections() {
    document.querySelectorAll('.report-section').forEach((section) => {
        const toggle = section.querySelector('[data-section-toggle]');
        toggle?.addEventListener('click', (e) => {
            e.stopPropagation();
            const collapsed = !section.classList.contains('report-collapsed');
            section.dataset.userToggled = 'true';
            _setReportSectionCollapsed(section, collapsed);
        });
    });

    document.querySelectorAll('.report-index-link[data-report-link]').forEach((link) => {
        link.addEventListener('click', (e) => {
            const slug = link.dataset.reportLink;
            const target = slug ? document.getElementById(slug) : null;
            if (!target) return;
            e.preventDefault();
            target.dataset.userToggled = 'true';
            _setReportSectionCollapsed(target, false);
            target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            history.replaceState(null, '', `#${slug}`);
        });
    });
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
        const summaryLabel = summary.nextElementSibling;
        const sectionSlug = section.dataset.sectionSlug;
        const indexCount = sectionSlug
            ? document.querySelector(`[data-report-link="${sectionSlug}"] [data-report-count]`)
            : null;

        if (!findings) {
            summary.textContent = 'Nenhum achado carregado';
            if (summaryLabel) summaryLabel.style.display = 'none';
            if (indexCount) indexCount.textContent = 'Sem achados';
            return;
        }

        if (summaryLabel) summaryLabel.style.display = '';
        summary.textContent = `${total} registros em ${findings} blocos`;
        if (indexCount) indexCount.textContent = `${total} registros`;
    });
}

