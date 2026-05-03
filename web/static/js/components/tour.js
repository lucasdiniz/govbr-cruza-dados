// === components/tour.js ===
function initTour() {
    // Fase 5: tour de 3 passos na primeira visita.
    const isCityPage = !!document.querySelector('.city-hero');
    const isHomePage = !!document.querySelector('.search-hero') && !isCityPage;
    const restartBtn = document.getElementById('tourRestart');
    const tourAvailable = isCityPage || isHomePage;
    if (!tourAvailable) return;

    const STEPS_CIDADE = [
        {
            selector: '.city-risk-badge, .city-narrative',
            title: 'Resumo em 30 segundos',
            text: 'Aqui fica a nota de aten&ccedil;&atilde;o e um resumo curto da cidade. Clique nas palavras destacadas para ir direto &agrave; se&ccedil;&atilde;o relacionada.',
        },
        {
            selector: '.city-kpi-strip, .findings-list',
            title: 'Os pontos que merecem aten&ccedil;&atilde;o',
            text: 'Aqui ficam os principais sinais investigativos: cada card mostra um cruzamento de dados que merece aten&ccedil;&atilde;o, e clicando voc&ecirc; vai direto para o detalhamento.',
        },
        {
            selector: '#modeToggle',
            title: '&Eacute; jornalista, auditor ou MP?',
            text: 'Ative o <strong>Modo Auditor</strong> aqui para ver todos os dados t&eacute;cnicos (CNPJs, modalidades, scores brutos, colunas extras).',
        },
    ];

    const STEPS_HOME = [
        {
            selector: '.search-card-inline',
            title: 'Comece escolhendo um munic&iacute;pio',
            text: 'Digite o nome da cidade ou use o bot&atilde;o <strong>&#128205;</strong> para detectar sua localiza&ccedil;&atilde;o (funciona em toda a Para&iacute;ba).',
        },
        {
            selector: '.mapa-hero',
            title: 'Mapa da Para&iacute;ba',
            text: 'Cada munic&iacute;pio est&aacute; colorido pelo indicador selecionado (risco, % de dinheiro com fornecedores irregulares, etc). Toque num munic&iacute;pio para abrir os detalhes.',
        },
        {
            selector: '#modeToggle',
            title: '&Eacute; jornalista, auditor ou MP?',
            text: 'Ative o <strong>Modo Auditor</strong> aqui para ver todos os dados t&eacute;cnicos (CNPJs, modalidades, scores brutos, colunas extras).',
        },
    ];

    const STEPS = isCityPage ? STEPS_CIDADE : STEPS_HOME;
    if (restartBtn) {
        restartBtn.style.display = 'inline';
    }

    let current = 0;
    let overlay = null;
    let tooltip = null;

    function firstMatch(sel) {
        return document.querySelector(sel.split(',').map(s => s.trim()).find(s => document.querySelector(s)) || sel.split(',')[0].trim());
    }

    function build() {
        overlay = document.createElement('div');
        overlay.className = 'tour-overlay';
        overlay.innerHTML = '<div class="tour-spotlight"></div>';
        tooltip = document.createElement('div');
        tooltip.className = 'tour-tooltip';
        tooltip.setAttribute('role', 'dialog');
        tooltip.setAttribute('aria-modal', 'true');
        document.body.appendChild(overlay);
        document.body.appendChild(tooltip);
    }

    function render() {
        const step = STEPS[current];
        const target = firstMatch(step.selector);
        if (!target) { next(); return; }
        target.scrollIntoView({ behavior: 'smooth', block: 'center' });
        setTimeout(() => {
            const rect = target.getBoundingClientRect();
            const pad = 8;
            const spot = overlay.querySelector('.tour-spotlight');
            spot.style.top = (rect.top - pad) + 'px';
            spot.style.left = (rect.left - pad) + 'px';
            spot.style.width = (rect.width + pad * 2) + 'px';
            spot.style.height = (rect.height + pad * 2) + 'px';

            const isLast = current === STEPS.length - 1;
            tooltip.innerHTML = `
                <div class="tour-step">Passo ${current + 1} de ${STEPS.length}</div>
                <h3 class="tour-title">${step.title}</h3>
                <p class="tour-text">${step.text}</p>
                <div class="tour-actions">
                    <button type="button" class="tour-skip">Pular</button>
                    <div class="tour-nav">
                        ${current > 0 ? '<button type="button" class="tour-prev">Voltar</button>' : ''}
                        <button type="button" class="tour-next">${isLast ? 'Entendi' : 'Pr&oacute;ximo'}</button>
                    </div>
                </div>
            `;
            // Posicionar tooltip abaixo (ou acima se nao couber)
            const tt = tooltip;
            tt.style.visibility = 'hidden';
            tt.style.display = 'block';
            const ttRect = tt.getBoundingClientRect();
            let top = rect.bottom + 14;
            if (top + ttRect.height > window.innerHeight - 12) {
                top = Math.max(12, rect.top - ttRect.height - 14);
            }
            let left = Math.max(12, Math.min(rect.left, window.innerWidth - ttRect.width - 12));
            tt.style.top = top + 'px';
            tt.style.left = left + 'px';
            tt.style.visibility = 'visible';

            tt.querySelector('.tour-skip').onclick = finish;
            tt.querySelector('.tour-next').onclick = next;
            const prev = tt.querySelector('.tour-prev');
            if (prev) prev.onclick = () => { current = Math.max(0, current - 1); render(); };
        }, 350);
    }

    function next() {
        current++;
        if (current >= STEPS.length) { finish(); return; }
        render();
    }

    function finish() {
        try { localStorage.setItem('tour-v1', 'done'); } catch (_) {}
        if (overlay) overlay.remove();
        if (tooltip) tooltip.remove();
        overlay = null; tooltip = null; current = 0;
    }

    function start() {
        if (overlay) return;
        build();
        render();
    }

    // Mostra link "Como usar" no rodape sempre que o tour esta disponivel.
    if (restartBtn) {
        restartBtn.addEventListener('click', () => { current = 0; start(); });
    }

    // O tour continua disponivel no botao "?", mas nao abre sozinho:
    // no mobile ele competia com a primeira dobra e escondia a busca.
}


