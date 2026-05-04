// === components/topnav-elevation.js ===
// MD3 top app bar (small) elevation pattern: at scrollTop 0 the bar is at
// elevation 0 (surface-container); on scroll past a small threshold it
// raises to elevation 2 (surface-container-high + box-shadow). We toggle
// via a [data-scrolled] attribute so the animation lives in CSS.
function initTopnavElevation() {
    const nav = document.querySelector('.topnav');
    if (!nav) return;
    const THRESHOLD = 4;
    let scrolled = false;
    function update() {
        const isScrolled = (window.scrollY || document.documentElement.scrollTop) > THRESHOLD;
        if (isScrolled !== scrolled) {
            scrolled = isScrolled;
            if (isScrolled) nav.setAttribute('data-scrolled', '');
            else nav.removeAttribute('data-scrolled');
        }
    }
    update();
    window.addEventListener('scroll', update, { passive: true });
}
