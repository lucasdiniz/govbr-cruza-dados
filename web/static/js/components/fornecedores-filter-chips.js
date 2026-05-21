// === components/fornecedores-filter-chips.js ===
// Filtros de chips por flag pra tabela de fornecedores. Plugga no _refilter
// exposto pelo data-table.js. Semantica OR: row visivel se tem >=1 dos flags
// ativos (ou se nenhum chip ativo).
//
// Espelha components/servidores-filter-chips.js. Eventos Umami catalogados
// em docs/analytics.md: fornecedores-filtro-toggle, fornecedores-filtro-limpar.

function initFornecedoresFilterChips(root = document) {
    root.querySelectorAll('[data-fornecedores-filter-chips]').forEach((chipsEl) => {
        if (chipsEl.dataset.enhanced === 'true') return;
        chipsEl.dataset.enhanced = 'true';

        const tableShell = chipsEl.closest('.js-data-table');
        if (!tableShell || typeof tableShell._refilter !== 'function') return;

        const chips = Array.from(chipsEl.querySelectorAll('.filter-chip[data-flag]'));
        const clearBtn = chipsEl.querySelector('[data-clear]');
        const active = new Set();

        const flagToAttr = (flag) => `data-flag-${flag.replace(/_/g, '-')}`;

        const apply = () => {
            if (!active.size) {
                const total = tableShell._refilter(null);
                if (clearBtn) clearBtn.hidden = true;
                return total;
            }
            const attrs = Array.from(active).map(flagToAttr);
            const matched = tableShell._refilter((row) => attrs.some((a) => row.hasAttribute(a)));
            if (clearBtn) clearBtn.hidden = false;
            return matched;
        };

        const trackToggle = (flag, on, visiveis) => {
            if (typeof trackEvent !== 'function') return;
            const ativos = Array.from(active).sort().join(',');
            const total = tableShell.querySelectorAll('tbody tr').length;
            trackEvent('fornecedores-filtro-toggle', {
                flag,
                action: on ? 'on' : 'off',
                ativos,
                qtd_ativos: active.size,
                visiveis,
                total,
            });
        };

        chips.forEach((chip) => {
            chip.addEventListener('click', () => {
                const flag = chip.dataset.flag;
                const willActivate = !active.has(flag);
                if (willActivate) active.add(flag);
                else active.delete(flag);
                chip.classList.toggle('filter-chip--active', willActivate);
                chip.setAttribute('aria-pressed', String(willActivate));
                const matched = apply();
                trackToggle(flag, willActivate, matched);
            });
        });

        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                const ativosPrev = Array.from(active).sort().join(',');
                const qtdPrev = active.size;
                active.clear();
                chips.forEach((c) => {
                    c.classList.remove('filter-chip--active');
                    c.setAttribute('aria-pressed', 'false');
                });
                const matched = apply();
                if (typeof trackEvent === 'function') {
                    trackEvent('fornecedores-filtro-limpar', {
                        ativos_anteriores: ativosPrev,
                        qtd_ativos_anteriores: qtdPrev,
                        visiveis: matched,
                    });
                }
            });
        }
    });
}
