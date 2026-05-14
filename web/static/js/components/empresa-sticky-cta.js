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
    bar.setAttribute('aria-hidden', 'true');
    let heroOut = false;
    // gridPassed eh one-way: uma vez que o user chegou no "Continue
    // investigando", consideramos que ja foi exposto aos CTAs principais
    // e a sticky bar nao deve reaparecer mais. Sem isso, ao rolar pra
    // alem do grid (FAQ + site-footer), gridIn volta a false e a barra
    // cobre links do footer (Sobre/Glossario/Contato).
    let gridPassed = false;

    const update = () => {
        const shouldShow = heroOut && !gridPassed;
        bar.classList.toggle('is-visible', shouldShow);
        bar.setAttribute('aria-hidden', shouldShow ? 'false' : 'true');
        // Tira o link do tab order quando invisivel (transform translateY
        // mantem ele no accessibility tree e focusable sem inert).
        if (shouldShow) {
            bar.removeAttribute('inert');
        } else {
            bar.setAttribute('inert', '');
        }
        // Comunica estado pro back-to-top FAB esconder via CSS
        // (.has-empresa-sticky-cta seletor). Sticky bar ocupa width
        // total e o FAB (z-index:60) ficaria sobreposto cobrindo a
        // seta -> do CTA, prejudicando o tap target.
        document.body.classList.toggle('has-empresa-sticky-cta', shouldShow);
    };

    const obsHero = new IntersectionObserver((entries) => {
        // hero out = top do hero passou do viewport top
        heroOut = !entries[0].isIntersecting;
        update();
    }, { rootMargin: '0px' });
    obsHero.observe(hero);

    const obsGrid = new IntersectionObserver((entries) => {
        if (entries[0].isIntersecting) {
            gridPassed = true;
            obsGrid.disconnect();
        }
        update();
    }, { rootMargin: '120px 0px 0px 0px' });
    obsGrid.observe(grid);

    update();
}
