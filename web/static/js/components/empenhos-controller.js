// === components/empenhos-controller.js ===
//
// Controller generico pra tabela paginada+filtravel de empenhos. Funciona em
// 3 superficies:
//   1. Pagina /empresa/<cnpj>/<municipio> — initial empenhos vem do warmer
//      cache (server-side rendered pg1). Endpoint: /api/empresa/empenhos.
//   2. Pagina /empresa/<cnpj> (global) — idem, scope=global. Page 1
//      vem do cache `empenhos_global` ou (se cache velho pre-PR) lazy fetch
//      automatico ao mount.
//   3. Dialog de fornecedor em /cidade/<slug> — initial empenhos vem do
//      payload do /api/fornecedor/detalhes. Endpoint:
//      /api/fornecedor/empenhos. Identidade: cpf_cnpj exato.
//
// Mount:
//   Procura `[data-empenhos-mount]` na arvore. Para cada container, le os
//   data-* attrs (endpoint, scope, cnpj, municipio, cpf_cnpj, total) e
//   wirea filter bar + paginacao + lazy fetch.
//
// Fallback compat: se data-empenhos-initial="0" (sem empenhos server-side
// renderizados), faz fetch live de page 1 ao mount. Isso cobre entries
// cacheadas pre-PR de paginacao que nao tem `empenhos_global` no payload.

function initEmpenhosControllers(root) {
    const scope = root || document;
    scope.querySelectorAll('[data-empenhos-mount]').forEach((mount) => {
        if (mount.dataset.empenhosWired === '1') return;
        mount.dataset.empenhosWired = '1';
        try {
            new EmpenhosController(mount).init();
        } catch (err) {
            console.warn('empenhos-controller init failed', err);
        }
    });
}

class EmpenhosController {
    constructor(mount) {
        this.mount = mount;
        this.endpoint = mount.dataset.empenhosEndpoint || '/api/empresa/empenhos';
        this.scope = mount.dataset.empenhosScope || 'municipio';
        this.cnpj = mount.dataset.empenhosCnpj || '';
        this.cpfCnpj = mount.dataset.empenhosCpfCnpj || '';
        this.municipio = mount.dataset.empenhosMunicipio || '';
        this.total = parseInt(mount.dataset.empenhosTotal || '0', 10) || 0;
        this.hasInitial = mount.dataset.empenhosInitial === '1';
        this.page = 1;
        this.pageSize = 50;
        this.filters = { q: '', dateInicio: '', dateFim: '' };
        this.busy = false;
        this.searchDebounceMs = 300;
        this._searchTimer = null;
        this._reqSeq = 0;

        // Refs
        this.tableContainer = mount.querySelector('[data-empenhos-table]');
        this.summary = mount.querySelector('[data-empenhos-summary]');
        this.filterSummary = mount.querySelector('[data-empenhos-filter-summary]');
        this.qInput = mount.querySelector('[data-empenhos-q]');
        this.dateInicioInput = mount.querySelector('[data-empenhos-date-inicio]');
        this.dateFimInput = mount.querySelector('[data-empenhos-date-fim]');
        this.applyBtn = mount.querySelector('[data-empenhos-apply]');
        this.statusEl = mount.querySelector('[data-empenhos-status]');
        this.clearBtn = mount.querySelector('[data-empenhos-clear]');
        this.pagination = mount.querySelector('[data-empenhos-pagination]');
        this.prevBtn = mount.querySelector('[data-empenhos-prev]');
        this.nextBtn = mount.querySelector('[data-empenhos-next]');
        this.pageInfo = mount.querySelector('[data-empenhos-page-info]');
    }

    init() {
        this._wireEvents();
        this._updatePagination();
        this._updateFilterSummary();
        if (!this.hasInitial) {
            this._fetchAndRender();
        } else {
            // Empenhos ja renderizados server-side. So inicializa
            // clickable rows pra wirear empenho-dialog.
            if (typeof initClickableRows === 'function') {
                initClickableRows(this.tableContainer);
            }
        }
    }

    _wireEvents() {
        if (this.qInput) {
            this.qInput.addEventListener('input', () => {
                clearTimeout(this._searchTimer);
                this._searchTimer = setTimeout(() => {
                    this.filters.q = (this.qInput.value || '').trim();
                    this.page = 1;
                    this._fetchAndRender();
                }, this.searchDebounceMs);
            });
            this.qInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    clearTimeout(this._searchTimer);
                    this.filters.q = (this.qInput.value || '').trim();
                    this.page = 1;
                    this._fetchAndRender();
                }
            });
        }
        // Date input mask (DD/MM/AAAA) — reusa _maskBrDate se disponivel
        [this.dateInicioInput, this.dateFimInput].forEach((el) => {
            if (!el) return;
            if (typeof _maskBrDate === 'function') _maskBrDate(el);
            el.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    this._applyDateInputs();
                }
            });
        });
        if (this.applyBtn) {
            this.applyBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this._applyDateInputs();
            });
        }
        if (this.clearBtn) {
            this.clearBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this._clearFilters();
            });
        }
        // Presets
        this.mount.querySelectorAll('[data-empenhos-preset]').forEach((chip) => {
            chip.addEventListener('click', () => {
                const preset = chip.dataset.empenhosPreset;
                this._applyPreset(preset);
            });
        });
        if (this.prevBtn) {
            this.prevBtn.addEventListener('click', (e) => {
                e.preventDefault();
                if (this.page > 1) {
                    this.page -= 1;
                    this._fetchAndRender({ scrollTop: true });
                }
            });
        }
        if (this.nextBtn) {
            this.nextBtn.addEventListener('click', (e) => {
                e.preventDefault();
                const totalPages = this._totalPages();
                if (totalPages === 0 || this.page < totalPages) {
                    this.page += 1;
                    this._fetchAndRender({ scrollTop: true });
                }
            });
        }
    }

    _applyDateInputs() {
        const inicioBr = (this.dateInicioInput && this.dateInicioInput.value) || '';
        const fimBr = (this.dateFimInput && this.dateFimInput.value) || '';
        const inicioIso = _empBrToIso(inicioBr);
        const fimIso = _empBrToIso(fimBr);
        if (inicioBr && !inicioIso) {
            this._setStatus('Data inicial invalida (use DD/MM/AAAA).', true);
            return;
        }
        if (fimBr && !fimIso) {
            this._setStatus('Data final invalida (use DD/MM/AAAA).', true);
            return;
        }
        if (inicioIso && fimIso && inicioIso > fimIso) {
            this._setStatus('Data inicial maior que data final.', true);
            return;
        }
        this.filters.dateInicio = inicioIso || '';
        this.filters.dateFim = fimIso || '';
        this.page = 1;
        this._fetchAndRender();
    }

    _applyPreset(preset) {
        const today = new Date();
        const yyyy = today.getFullYear();
        const mm = String(today.getMonth() + 1).padStart(2, '0');
        const dd = String(today.getDate()).padStart(2, '0');
        const todayIso = `${yyyy}-${mm}-${dd}`;
        if (preset === 'all') {
            this.filters.dateInicio = '';
            this.filters.dateFim = '';
        } else if (preset === 'current-year') {
            this.filters.dateInicio = `${yyyy}-01-01`;
            this.filters.dateFim = todayIso;
        } else if (preset === 'last-12m') {
            const start = new Date(today);
            start.setFullYear(start.getFullYear() - 1);
            const sy = start.getFullYear();
            const sm = String(start.getMonth() + 1).padStart(2, '0');
            const sd = String(start.getDate()).padStart(2, '0');
            this.filters.dateInicio = `${sy}-${sm}-${sd}`;
            this.filters.dateFim = todayIso;
        }
        // Sync UI
        if (this.dateInicioInput) {
            this.dateInicioInput.value = this.filters.dateInicio
                ? _empIsoToBr(this.filters.dateInicio) : '';
        }
        if (this.dateFimInput) {
            this.dateFimInput.value = this.filters.dateFim
                ? _empIsoToBr(this.filters.dateFim) : '';
        }
        // Marca chip ativo
        this.mount.querySelectorAll('[data-empenhos-preset]').forEach((c) => {
            const isActive = c.dataset.empenhosPreset === preset;
            if (c.tagName === 'MD-FILTER-CHIP') {
                if (isActive) c.setAttribute('selected', '');
                else c.removeAttribute('selected');
            }
        });
        this.page = 1;
        this._fetchAndRender();
    }

    _clearFilters() {
        this.filters = { q: '', dateInicio: '', dateFim: '' };
        if (this.qInput) this.qInput.value = '';
        if (this.dateInicioInput) this.dateInicioInput.value = '';
        if (this.dateFimInput) this.dateFimInput.value = '';
        // Volta preset pra "all"
        this.mount.querySelectorAll('[data-empenhos-preset]').forEach((c) => {
            const isAll = c.dataset.empenhosPreset === 'all';
            if (c.tagName === 'MD-FILTER-CHIP') {
                if (isAll) c.setAttribute('selected', '');
                else c.removeAttribute('selected');
            }
        });
        this.page = 1;
        this._fetchAndRender();
    }

    _hasActiveFilters() {
        return !!(this.filters.q || this.filters.dateInicio || this.filters.dateFim);
    }

    _setStatus(msg, isError) {
        if (!this.statusEl) return;
        this.statusEl.textContent = msg || '';
        this.statusEl.classList.toggle('color-red', !!isError);
    }

    _updateFilterSummary() {
        if (!this.filterSummary) return;
        const parts = [];
        if (this.filters.dateInicio || this.filters.dateFim) {
            const di = this.filters.dateInicio
                ? _empIsoToBr(this.filters.dateInicio) : '...';
            const df = this.filters.dateFim
                ? _empIsoToBr(this.filters.dateFim) : '...';
            parts.push(`${di} a ${df}`);
        } else {
            parts.push('todo o historico');
        }
        if (this.filters.q) parts.push(`busca: "${this.filters.q}"`);
        this.filterSummary.textContent = `Periodo: ${parts.join(' · ')}`;
        if (this.clearBtn) {
            this.clearBtn.style.display = this._hasActiveFilters() ? '' : 'none';
        }
    }

    _totalPages() {
        if (this.total <= 0) return 0;
        return Math.ceil(this.total / this.pageSize);
    }

    _updatePagination() {
        if (!this.pagination) return;
        const totalPages = this._totalPages();
        if (totalPages <= 1) {
            this.pagination.hidden = true;
            return;
        }
        this.pagination.hidden = false;
        if (this.prevBtn) this.prevBtn.disabled = this.page <= 1;
        if (this.nextBtn) this.nextBtn.disabled = this.page >= totalPages;
        if (this.pageInfo) {
            const totalLabel = this.total.toLocaleString('pt-BR');
            this.pageInfo.textContent =
                `Pagina ${this.page} de ${totalPages} · ${totalLabel} empenhos`;
        }
    }

    _updateSummary() {
        if (!this.summary) return;
        const totalLabel = this.total.toLocaleString('pt-BR');
        if (this.total > 0) {
            const filterMsg = this._hasActiveFilters() ? ' (com filtros)' : '';
            this.summary.textContent =
                `${totalLabel} empenhos encontrados${filterMsg}. ` +
                'Clique em uma linha para ver os detalhes.';
        } else if (this._hasActiveFilters()) {
            this.summary.textContent =
                'Nenhum empenho encontrado com os filtros atuais.';
        } else {
            this.summary.textContent = 'Nenhum empenho disponivel.';
        }
    }

    _buildBody() {
        const body = { page: this.page };
        if (this.cnpj) body.cnpj = this.cnpj;
        if (this.cpfCnpj) body.cpf_cnpj = this.cpfCnpj;
        if (this.municipio) body.municipio = this.municipio;
        if (this.filters.q) body.q = this.filters.q;
        if (this.filters.dateInicio) body.data_inicio = this.filters.dateInicio;
        if (this.filters.dateFim) body.data_fim = this.filters.dateFim;
        return body;
    }

    async _fetchAndRender(opts) {
        const options = opts || {};
        if (this.busy) return;
        this.busy = true;
        const seq = ++this._reqSeq;
        this._setStatus('Carregando...');
        if (this.tableContainer) {
            this.tableContainer.classList.add('loading');
        }
        let data;
        try {
            const resp = await fetch(this.endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(this._buildBody()),
            });
            if (resp.status === 504) {
                if (seq !== this._reqSeq) return;
                this._setStatus(
                    'A busca demorou muito. Use filtros (data ou texto) para refinar.',
                    true
                );
                return;
            }
            if (!resp.ok) {
                if (seq !== this._reqSeq) return;
                this._setStatus(`Erro ao carregar (${resp.status}).`, true);
                return;
            }
            data = await resp.json();
        } catch (err) {
            if (seq !== this._reqSeq) return;
            this._setStatus('Falha de rede ao carregar empenhos.', true);
            return;
        } finally {
            this.busy = false;
            if (this.tableContainer) {
                this.tableContainer.classList.remove('loading');
            }
        }
        if (seq !== this._reqSeq) return; // request stale
        this._setStatus('');
        this.total = parseInt(data.total || 0, 10) || 0;
        this.page = parseInt(data.page || 1, 10) || 1;
        this.pageSize = parseInt(data.page_size || 50, 10) || 50;
        this._renderTable(data.empenhos || []);
        this._updateSummary();
        this._updatePagination();
        this._updateFilterSummary();
        if (options.scrollTop && this.mount.scrollIntoView) {
            this.mount.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }

    _renderTable(empenhos) {
        if (!this.tableContainer) return;
        if (!empenhos.length) {
            this.tableContainer.innerHTML =
                '<p class="text-sm text-muted empenhos-empty">' +
                'Nenhum empenho encontrado.</p>';
            return;
        }
        const showMun = this.scope === 'global';
        const rows = empenhos.map((e) => _empRenderRow(e, showMun)).join('');
        const munTh = showMun ? '<th>Municipio</th>' : '';
        this.tableContainer.innerHTML =
            '<div class="tbl-wrap">' +
            '<table class="stack-mobile data-table empresa-empenhos-table">' +
            '<thead><tr>' +
            '<th>Data</th>' +
            '<th>Numero</th>' +
            munTh +
            '<th>Elemento de despesa</th>' +
            '<th>Modalidade / Licitacao</th>' +
            '<th class="text-right">Empenhado</th>' +
            '<th class="text-right">Pago</th>' +
            '</tr></thead>' +
            `<tbody>${rows}</tbody>` +
            '</table></div>';
        if (typeof initClickableRows === 'function') {
            initClickableRows(this.tableContainer);
        }
    }
}

// Helpers
function _empRenderRow(e, showMun) {
    const semLic = !e.numero_licitacao
        || e.numero_licitacao === '000000000'
        || ((e.modalidade_licitacao || '').toLowerCase().indexOf('sem licit') === 0);
    const modCell = semLic
        ? '<span class="badge badge-yellow" title="Empenho sem licitacao identificada">Sem licitacao</span>'
        : `${_empEsc(e.modalidade_licitacao || '')}${
            e.numero_licitacao && e.numero_licitacao !== '000000000'
                ? `<br><span class="text-sm text-muted"><code>${_empEsc(e.numero_licitacao)}</code></span>`
                : ''
        }`;
    const munCell = showMun
        ? `<td data-label="Municipio">${_empEsc(e.municipio || '—')}</td>`
        : '';
    const empenhoIdAttr = e.id ? ` data-empenho-id="${_empEsc(String(e.id))}"` : '';
    return `<tr class="clickable-row"${empenhoIdAttr}>
        <td data-label="Data">${_empFmtDate(e.data_empenho)}</td>
        <td data-label="Numero"><code>${_empEsc(e.numero_empenho || '—')}</code></td>
        ${munCell}
        <td data-label="Elemento">${_empEsc(e.elemento_despesa || '—')}</td>
        <td data-label="Modalidade">${modCell}</td>
        <td data-label="Empenhado" class="text-right num">${_empBrl(e.valor_empenhado)}</td>
        <td data-label="Pago" class="text-right num"><strong>${_empBrl(e.valor_pago)}</strong></td>
    </tr>`;
}

function _empEsc(s) {
    if (s === null || s === undefined) return '';
    return String(s)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;')
        .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function _empFmtDate(iso) {
    if (!iso) return '—';
    const m = String(iso).match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (!m) return _empEsc(iso);
    return `${m[3]}/${m[2]}/${m[1]}`;
}

function _empBrToIso(br) {
    if (!br) return '';
    const m = String(br).match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
    if (!m) return '';
    const [, dd, mm, yyyy] = m;
    const d = parseInt(dd, 10), mo = parseInt(mm, 10), y = parseInt(yyyy, 10);
    if (mo < 1 || mo > 12 || d < 1 || d > 31) return '';
    if (y < 1900 || y > 2100) return '';
    return `${yyyy}-${mm}-${dd}`;
}

function _empIsoToBr(iso) {
    if (!iso) return '';
    const m = String(iso).match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (!m) return iso;
    return `${m[3]}/${m[2]}/${m[1]}`;
}

function _empBrl(v) {
    if (v === null || v === undefined || v === '') return '—';
    const n = typeof v === 'number' ? v : parseFloat(v);
    if (!isFinite(n)) return '—';
    if (typeof _shortBrl === 'function') return _shortBrl(n);
    return 'R$ ' + n.toLocaleString('pt-BR', {
        minimumFractionDigits: 2, maximumFractionDigits: 2,
    });
}
