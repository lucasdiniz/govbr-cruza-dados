// === components/mobile-descriptions.js ===
function initMobileDescriptions(root = document) {
    root.querySelectorAll('.mobile-desc-toggle[data-mobile-desc-next], .mobile-desc-toggle[data-mobile-desc-target]').forEach((btn) => {
        if (btn.dataset.enhanced === 'true') return;
        btn.dataset.enhanced = 'true';
        const extraPanels = [];
        let panel = btn.dataset.mobileDescTarget
            ? document.getElementById(btn.dataset.mobileDescTarget)
            : btn.nextElementSibling;
        if (!panel || !panel.classList.contains('mobile-collapsible-desc')) {
            const title = btn.closest('.card-title, .finding-title');
            panel = title ? title.nextElementSibling : panel;
        }
        if (!panel || !panel.classList.contains('mobile-collapsible-desc')) {
            panel = btn.closest('div, section, article')?.querySelector('.mobile-collapsible-desc') || panel;
        }
        if (!panel || !panel.classList.contains('mobile-collapsible-desc')) return;
        if (btn.dataset.mobileDescExplainer) {
            const explainer = document.getElementById(btn.dataset.mobileDescExplainer);
            if (explainer) {
                explainer.hidden = true;
                extraPanels.push(explainer);
            }
        }
        panel.classList.remove('is-open');
        btn.setAttribute('aria-expanded', 'false');
        btn.addEventListener('click', (event) => {
            event.preventDefault();
            event.stopPropagation();
            const willOpen = !panel.classList.contains('is-open');
            panel.classList.toggle('is-open', willOpen);
            extraPanels.forEach((extraPanel) => {
                extraPanel.hidden = !willOpen;
                extraPanel.classList.toggle('is-open', willOpen);
            });
            btn.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
        });
    });
}


