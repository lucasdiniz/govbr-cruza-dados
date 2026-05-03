// === pages/cidade-async-panels.js ===
async function loadAsyncPanel(panelName, municipio, uf) {
    const panel = document.querySelector(`[data-async-panel="${panelName}"]`);
    if (!panel) return;

    const panelUf = uf || panel.dataset.uf || '';
    const showPanelError = (message) => {
        panel.setAttribute('aria-busy', 'false');
        panel.innerHTML = `<div class="async-error"><p class="text-sm text-muted">${message}</p><button type="button" class="btn btn-outline btn-sm" data-retry-panel="${panelName}">Tentar novamente</button></div>`;
        panel.querySelector('[data-retry-panel]')?.addEventListener('click', () => {
            panel.setAttribute('aria-busy', 'true');
            panel.innerHTML = skeletonTableHtml(4, 3);
            loadAsyncPanel(panelName, municipio, panelUf);
        });
    };
    try {
        const response = await fetch(`/api/top/${panelName}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'fetch' },
            body: JSON.stringify(_buildBody(municipio, panelUf)),
        });
        if (!response.ok) {
            showPanelError('Nao foi possivel carregar este bloco agora.');
            return;
        }
        panel.innerHTML = await response.text();
        panel.setAttribute('aria-busy', 'false');
        initDataTables(panel);
        initInteractiveToggles(panel);
        initMobileDescriptions(panel);
        initClickableRows(panel);
    } catch {
        showPanelError('Nao foi possivel carregar este bloco agora.');
    }
}

