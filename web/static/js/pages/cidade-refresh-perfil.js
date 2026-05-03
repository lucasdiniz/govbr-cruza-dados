// === pages/cidade-refresh-perfil.js ===
async function _refreshPerfilLive(municipio, uf) {
    try {
        const res = await fetch('/api/perfil', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(_buildBody(municipio, uf)),
        });
        if (res.ok) {
            const data = await res.json();
            // Compat: /api/perfil agora retorna {perfil, narrative}.
            // Tolera o formato antigo (perfil flat) caso uma versao em cache do
            // bundle JS antigo bata com um backend novo (ou vice-versa).
            const perfil = (data && data.perfil) ? data.perfil : data;
            _updateHeroStats(perfil);
            _updateInsightCards(perfil);
            if (data && data.narrative) {
                _updateNarrative(data.narrative);
            }
        } else {
            const msg = await _handleDateApiError(res, 'Nao foi possivel carregar o perfil deste periodo.');
            console.warn('perfil endpoint returned', res.status, msg);
        }
    } catch (e) {
        console.warn('perfil fetch failed', e);
    }
}

function _updateNarrative(narrative) {
    if (!narrative) return;
    const block = document.getElementById('cityNarrative');
    if (!block) return;
    const cit = block.querySelector('.citizen-only');
    const aud = block.querySelector('.auditor-only');
    if (cit && typeof narrative.citizen === 'string') cit.innerHTML = narrative.citizen;
    if (aud && typeof narrative.auditor === 'string') aud.innerHTML = narrative.auditor;
}

