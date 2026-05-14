// === components/empresa-sticky-cta.js ===
// Sticky CTA bar do /empresa/<cnpj>/<municipio> aparece quando user
// rola pra fora do hero E ainda nao chegou no "Continue investigando"
// grid (pra nao competir com ele). Mobile-only — em desktop o CSS ja
// esconde com display:none.
//
// IntersectionObserver assiste 2 sentinelas: hero (bottom) e grid
// (top). Estado da barra:
//   - oculta antes do hero sair do viewport
//   - visivel entre hero out e grid visible
//   - oculta novamente quando grid ja eh visivel (CTAs proprios cobrem)
//
// Sem dependencias externas. Skip silencioso se elementos ausentes
// (em paginas que nao sao empresa-municipio).
function initEmpresaStickyCta() {
    const bar = document.getElementById('empresa-sticky-cta');
    if (!bar) return;
    // Mobile-only — desktop ignora. matchMedia mais robusto que checar
    // width direto (respeita zoom).
    if (!window.matchMedia('(max-width: 719px)').matches) return;
    const hero = document.querySelector('.empresa-hero');
    const grid = document.querySelector('.empresa-related-grid');
    if (!hero || !grid) return;

    bar.hidden = false;
    let heroOut = false;
    let gridIn = false;

    const update = () => {
        const shouldShow = heroOut && !gridIn;
        bar.classList.toggle('is-visible', shouldShow);
    };

    const obsHero = new IntersectionObserver((entries) => {
        // hero out = top do hero passou do viewport top
        heroOut = !entries[0].isIntersecting;
        update();
    }, { rootMargin: '0px' });
    obsHero.observe(hero);

    const obsGrid = new IntersectionObserver((entries) => {
        gridIn = entries[0].isIntersecting;
        update();
    }, { rootMargin: '120px 0px 0px 0px' });
    obsGrid.observe(grid);
}
