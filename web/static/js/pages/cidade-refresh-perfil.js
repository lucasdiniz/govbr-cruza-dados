// === pages/cidade-refresh-perfil.js ===
function _exibirPerfilDoPeriodo(data) {
    const perfil = data.perfil || data;
    _updateHeroStats(perfil);
    _updateInsightCards(perfil);
    if (data.narrative) _updateNarrative(data.narrative);
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
