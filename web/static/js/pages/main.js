// === pages/main.js ===
document.addEventListener('DOMContentLoaded', () => {
    initDataTables(document);
    initCidadeAutocomplete();
    initInteractiveToggles(document);
    initClickableRows(document);
    initBackToTop();
    initShareButtons();
    initModeToggle();
    initTopnavElevation();
    initTermTooltips();
    initCityNarrativeToggle();
    initNarrativeAnchors();
    initMobileDescriptions(document);
    initAnchorAutoExpand();
    initExplainers();
    initCredibilityDialog();
    initFontSizeToggle();
    initTour();
    initDenunciaDialog();
    initReportSections();

    // Finding card collapse toggle
    document.querySelectorAll('.finding-card .finding-head').forEach(head => {
        head.addEventListener('click', () => {
            head.closest('.finding-card').classList.toggle('collapsed');
        });
    });

    const dialog = document.getElementById('empresa-dialog');
    if (dialog) {
        // Wait for md-dialog upgrade before wiring handlers — the slotted
        // back/close <md-icon-button> elements need their click events to
        // bubble and the [open] attribute observation to behave reliably.
        const initEmpresaDialog = () => {
            // Observa abertura/fechamento do dialog via atributo [open]
            // (md-dialog reflete `open` no host, igual ao <dialog> nativo).
            let wasOpen = dialog.open;
            const obs = new MutationObserver(() => {
                const isOpen = dialog.open;
                if (isOpen && !wasOpen) _dialogOnOpen();
                wasOpen = isOpen;
            });
            obs.observe(dialog, { attributes: true, attributeFilter: ['open'] });
            dialog.addEventListener('close', () => { _dialogOnClose(); });
            // Back button (slot=headline) -> pop the dialog stack.
            const backBtn = dialog.querySelector('[data-dialog-back], .dialog-back');
            if (backBtn) backBtn.addEventListener('click', () => { _dialogPop(); });
            // Close button (data-md-dialog-close, also class=dialog-close).
            dialog.querySelectorAll('[data-md-dialog-close], .dialog-close').forEach(b => {
                b.addEventListener('click', () => dialog.close());
            });
            _initDialogSwipeToClose();
        };
        if (typeof window.whenMD3Ready === 'function') {
            window.whenMD3Ready(initEmpresaDialog);
        } else {
            initEmpresaDialog();
        }
    }

    // Date filter handlers
    _initDateInputsBr();
    const runDateRefresh = async (message, refreshFn) => {
        if (_dateFilterBusy) return;
        _dateFilterBusy = true;
        _setDateFilterButtonBusy(true);
        _setDateFilterStatus(message || 'Atualizando dados do periodo...');
        try {
            await refreshFn();
            const statusEl = document.getElementById('dateFilterStatus');
            if (!statusEl?.classList.contains('color-red')) _setDateFilterStatus('Filtro aplicado.');
        } catch (err) {
            console.warn('Falha ao atualizar filtro de periodo', err);
            _setDateFilterStatus('Nao foi possivel atualizar os dados agora.', 'error');
        } finally {
            _dateFilterBusy = false;
            _setDateFilterButtonBusy(false);
        }
    };
    const applyDateFilter = () => {
        const range = _validateDateInputs();
        if (!range) return;
        runDateRefresh('Atualizando dados para o periodo selecionado...', async () => {
            _setDateInputs(range.inicio, range.fim);
            _resetCityPanelsLoading();
            await bootstrapCityReport(_currentMunicipio, _currentUf, range.inicio, range.fim);
        });
    };
    document.getElementById('btnFiltrarData')?.addEventListener('click', applyDateFilter);
    ['dateInicio', 'dateFim'].forEach((id) => {
        document.getElementById(id)?.addEventListener('keydown', (event) => {
            if (event.key !== 'Enter') return;
            event.preventDefault();
            applyDateFilter();
        });
    });

    document.getElementById('btnLimparData')?.addEventListener('click', () => {
        runDateRefresh('Voltando para todo o historico...', async () => {
            _setDateInputs('', '');
            _resetCityPanelsLoading();
            await bootstrapCityReport(_currentMunicipio, _currentUf);
        });
    });

    document.querySelectorAll('[data-date-preset]').forEach((btn) => {
        btn.addEventListener('click', () => {
            const preset = btn.dataset.datePreset || 'all';
            const { inicio, fim } = _datePresetRange(preset);
            runDateRefresh('Atualizando dados para o periodo selecionado...', async () => {
                _setDateInputs(inicio, fim);
                _resetCityPanelsLoading();
                if (preset === 'all') {
                    await bootstrapCityReport(_currentMunicipio, _currentUf);
                    return;
                }
                await bootstrapCityReport(_currentMunicipio, _currentUf, inicio, fim);
            });
        });
    });
});

function initInteractiveToggles(root = document) {
    root.querySelectorAll('[data-hide-medicos]').forEach((checkbox) => {
        if (checkbox.dataset.enhanced === 'true') return;
        checkbox.dataset.enhanced = 'true';

        const container = checkbox.closest('.result-block') || checkbox.closest('.table-shell')?.parentElement;
        const tableShell = container ? container.querySelector('.js-data-table') : null;

        const apply = () => {
            const hide = checkbox.checked;
            if (tableShell && tableShell._refilter) {
                tableShell._refilter(hide ? (row) => {
                    const cargo = (row.dataset.cargo || '').toLowerCase();
                    return !cargo.includes('medico');
                } : null);
            }
        };

        checkbox.addEventListener('change', apply);
        apply();
    });
}
