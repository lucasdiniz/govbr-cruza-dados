document.querySelectorAll('.tab:not(:disabled)').forEach((tab) => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.tab').forEach((item) => item.classList.remove('active'));
        document.querySelectorAll('.tab-panel').forEach((panel) => panel.classList.remove('active'));
        tab.classList.add('active');
        document.getElementById(`panel-${tab.dataset.tab}`)?.classList.add('active');
    });
});

// ───────── Helpers UI globais: toast, back-to-top, Web Share ─────────

// ───────── Modo Cidadao / Auditor ─────────
function getMode() {
    try { return localStorage.getItem('mode') === 'auditor' ? 'auditor' : 'citizen'; }
    catch(e) { return 'citizen'; }
}
function setMode(mode) {
    const m = mode === 'auditor' ? 'auditor' : 'citizen';
    try { localStorage.setItem('mode', m); } catch(e) {}
    document.documentElement.classList.toggle('audit-mode', m === 'auditor');
    const btn = document.getElementById('modeToggle');
    if (btn) {
        btn.setAttribute('aria-pressed', m === 'auditor' ? 'true' : 'false');
        btn.setAttribute('aria-label', m === 'auditor' ? 'Desligar modo auditor' : 'Ligar modo auditor');
    }
    document.dispatchEvent(new CustomEvent('modechange', { detail: { mode: m } }));
}
function initModeToggle() {
    // Garante consistencia entre html.audit-mode (setado no head) e localStorage
    setMode(getMode());
    const btn = document.getElementById('modeToggle');
    if (!btn) return;
    btn.addEventListener('click', () => {
        const next = getMode() === 'auditor' ? 'citizen' : 'auditor';
        setMode(next);
        if (navigator.vibrate) { try { navigator.vibrate(10); } catch(e) {} }
        const msg = next === 'auditor'
            ? 'Modo auditor ligado — termos técnicos e dados completos'
            : 'Modo cidadão — linguagem simples';
        if (typeof showToast === 'function') showToast(msg, 2000);
    });
}

// Gera um par de spans citizen/auditor para rotular UI em dois modos.
// Uso: `<span class="stat-label">${dualLabel('Recebido','Total pago')}</span>`
// Se auditor for omitido, usa citizen para ambos (sem duplicar markup).
// Tooltip opcional no span cidadao com o termo tecnico (acessivel via tap).
function dualLabel(citizen, auditor, opts) {
    const aud = (auditor == null) ? citizen : auditor;
    if (citizen === aud) return String(citizen);
    const tip = (opts && opts.tip !== false) ? ` data-tip="Termo t&eacute;cnico: ${aud}"` : '';
    const termCls = (opts && opts.tip !== false) ? ' term' : '';
    return `<span class="citizen-only${termCls}"${tip}>${citizen}</span><span class="auditor-only">${aud}</span>`;
}
// Expose globally for inline usage dentro de template literals
window.dualLabel = dualLabel;

// Remove o prefixo tecnico de codigo em strings como "04021602 - COMISSIONADOS SMN-1"
// ou "5005 - Atencao Integral a Saude". Mantem a string original se nao houver prefixo.
function _stripCodePrefix(s) {
    if (!s) return s;
    const m = String(s).match(/^\s*[0-9A-Z.\-]{2,}\s*[-–—]\s*(.+)$/);
    return m ? m[1].trim() : s;
}
window._stripCodePrefix = _stripCodePrefix;

// Versao string do dualLabel para uso em atributos (ex: data-label no
// padrao stack-mobile). Retorna sempre o rotulo cidadao por padrao; use
// o segundo argumento como data-label-auditor para sobrescrever via CSS.
function _lbl(citizen, auditor) {
    return String(citizen);
}
window._lbl = _lbl;


function initTermTooltips() {
    document.addEventListener('click', (e) => {
        const term = e.target.closest('.term[data-tip]');
        // Fecha abertos em outro clique
        document.querySelectorAll('.term.tip-open').forEach(el => {
            if (el !== term) el.classList.remove('tip-open');
        });
        if (term) {
            // Em touch devices, tap alterna
            if (matchMedia('(hover: none)').matches) {
                e.preventDefault();
                term.classList.toggle('tip-open');
            }
        }
    });
}

function initNarrativeAnchors() {
    // Smooth scroll + flash highlight para links da narrativa da hero
    const narr = document.querySelector('.city-narrative');
    if (!narr) return;
    narr.addEventListener('click', (e) => {
        const link = e.target.closest('a[href^="#"]');
        if (!link) return;
        const targetId = link.getAttribute('href').slice(1);
        const target = document.getElementById(targetId);
        if (!target) return;
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        target.classList.remove('anchor-flash');
        // Force reflow para reiniciar animacao
        void target.offsetWidth;
        target.classList.add('anchor-flash');
        setTimeout(() => target.classList.remove('anchor-flash'), 1800);
        // Atualiza hash sem jumping
        history.replaceState(null, '', '#' + targetId);
    });
}


let _toastTimer = null;
function showToast(message, durationMs = 2200) {
    const el = document.getElementById('toast');
    if (!el) return;
    el.textContent = message;
    el.hidden = false;
    // Next frame para animar entrada
    requestAnimationFrame(() => el.classList.add('visible'));
    if (_toastTimer) clearTimeout(_toastTimer);
    _toastTimer = setTimeout(() => {
        el.classList.remove('visible');
        setTimeout(() => { el.hidden = true; }, 200);
    }, durationMs);
}

function initBackToTop() {
    const btn = document.getElementById('backToTop');
    if (!btn) return;
    const threshold = 400;
    let shown = false;

    const update = () => {
        const y = window.scrollY || document.documentElement.scrollTop;
        const shouldShow = y > threshold;
        if (shouldShow === shown) return;
        shown = shouldShow;
        if (shouldShow) {
            btn.hidden = false;
            requestAnimationFrame(() => btn.classList.add('visible'));
        } else {
            btn.classList.remove('visible');
            setTimeout(() => { if (!shown) btn.hidden = true; }, 220);
        }
    };

    window.addEventListener('scroll', update, { passive: true });
    btn.addEventListener('click', () => {
        const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        window.scrollTo({ top: 0, behavior: prefersReduced ? 'auto' : 'smooth' });
    });
    update();
}

async function triggerShare(data) {
    const url = data.url || window.location.href;
    const title = data.title || document.title;
    const text = data.text || '';
    if (navigator.share) {
        try {
            await navigator.share({ title, text, url });
            return;
        } catch (err) {
            if (err && err.name === 'AbortError') return;
            // segue pra fallback
        }
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
        try {
            await navigator.clipboard.writeText(url);
            showToast('Link copiado para a area de transferencia');
            return;
        } catch { /* noop */ }
    }
    showToast('Nao foi possivel compartilhar');
}

function initShareButtons() {
    document.querySelectorAll('[data-share]').forEach((btn) => {
        btn.addEventListener('click', (ev) => {
            ev.preventDefault();
            triggerShare({
                title: btn.dataset.shareTitle || document.title,
                text: btn.dataset.shareText || '',
                url: btn.dataset.shareUrl || window.location.href,
            });
        });
    });
}

function setupAutocomplete(inputId, listId, endpoint, onSelect) {
    const input = document.getElementById(inputId);
    const list = document.getElementById(listId);
    const status = document.getElementById('cidade-status');
    if (!input || !list) return;

    let timer = null;
    let highlightedIndex = -1;
    let suggestions = [];
    let selectedValue = '';

    const clearList = () => {
        list.innerHTML = '';
        list.classList.remove('open');
        highlightedIndex = -1;
    };

    const renderSuggestions = () => {
        list.innerHTML = '';
        if (!suggestions.length) {
            clearList();
            status && (status.textContent = 'Nenhuma cidade encontrada para esse trecho.');
            return;
        }

        suggestions.forEach((item, index) => {
            const li = document.createElement('li');
            li.textContent = item;
            li.className = 'ac-item';
            li.addEventListener('mousedown', (event) => {
                event.preventDefault();
                commitSelection(item);
            });
            if (index === highlightedIndex) li.classList.add('selected');
            list.appendChild(li);
        });
        list.classList.add('open');
    };

    const commitSelection = (value) => {
        selectedValue = value;
        input.value = value;
        clearList();
        if (status) status.textContent = `Abrindo relatorio de ${value}...`;
        onSelect(value);
    };

    input.addEventListener('input', () => {
        clearTimeout(timer);
        const query = input.value.trim();
        if (query !== selectedValue && status) status.textContent = 'Selecione uma cidade da lista para continuar.';
        selectedValue = '';
        if (query.length < 3) {
            clearList();
            return;
        }
        timer = setTimeout(async () => {
            try {
                const response = await fetch(`${endpoint}?q=${encodeURIComponent(query)}`);
                suggestions = await response.json();
                highlightedIndex = suggestions.length ? 0 : -1;
                renderSuggestions();
            } catch {
                clearList();
            }
        }, 180);
    });

    input.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
            event.preventDefault();
            if (highlightedIndex >= 0 && suggestions[highlightedIndex]) {
                commitSelection(suggestions[highlightedIndex]);
            }
            return;
        }

        if (event.key === 'ArrowDown') {
            event.preventDefault();
            if (!suggestions.length) return;
            highlightedIndex = Math.min(highlightedIndex + 1, suggestions.length - 1);
            renderSuggestions();
        }

        if (event.key === 'ArrowUp') {
            event.preventDefault();
            if (!suggestions.length) return;
            highlightedIndex = Math.max(highlightedIndex - 1, 0);
            renderSuggestions();
        }
    });

    input.addEventListener('blur', () => {
        window.setTimeout(() => {
            if (input.value.trim() !== selectedValue) {
                input.value = '';
                if (status) status.textContent = '';
            }
            clearList();
        }, 120);
    });

    document.addEventListener('click', (event) => {
        if (!event.target.closest('.autocomplete-wrap')) clearList();
    });
}

setupAutocomplete('ac-cidade', 'aclist-cidade', '/api/autocomplete/municipio', (value) => {
    window.location.href = `/search/cidade?q=${encodeURIComponent(value)}`;
});

async function bootstrapCityReport(municipio, uf, dataInicio, dataFim) {
    uf = uf || 'PB';
    _currentMunicipio = municipio;
    _currentUf = uf;
    _dateInicio = dataInicio || null;
    _dateFim = dataFim || null;

    const periodo = _getPeriodo();

    // Update filter bar UI to reflect current state
    if (_isDateFiltered()) {
        const btnLimpar = document.getElementById('btnLimparData');
        if (btnLimpar) btnLimpar.style.display = '';
        const status = document.getElementById('dateFilterStatus');
        if (status) status.textContent = `Periodo: ${_formatDatePt(_dateInicio)} a ${_formatDatePt(_dateFim)}`;
    }

    // Single batch request for everything (skip for CUSTOM — no cache)
    let batchData = {};
    if (periodo !== 'CUSTOM') {
        try {
            const batchUrl = `/api/batch/${encodeURIComponent(municipio)}${periodo ? '?periodo=' + periodo : ''}`;
            const res = await fetch(batchUrl, { method: 'POST' });
            if (res.ok) batchData = await res.json();
        } catch {}
    }

    // Heatmap mensal (PB apenas, all-time — não responde ao filtro de data)
    if ((uf || 'PB') === 'PB' && document.getElementById('heatmapGrid')) {
        _loadHeatmap(municipio);
    }

    // Update hero/insight when date-filtered
    if (_isDateFiltered()) {
        // Show loading placeholders to avoid flash of all-time data
        const el = id => document.getElementById(id);
        ['heroQtdEmpenhos', 'heroTotalPago', 'heroQtdFornecedores'].forEach(id => {
            if (el(id)) el(id).textContent = '...';
        });
        ['insightPctPago', 'insightPctSemLicit', 'insightPctDispensa', 'insightPctFolha'].forEach(id => {
            if (el(id)) el(id).textContent = '...';
        });
        if (el('insightGapFinanceiro')) el('insightGapFinanceiro').textContent = '';
        if (el('progressPctPago')) el('progressPctPago').style.width = '0%';
        if (el('barEmpenhado')) el('barEmpenhado').textContent = '...';
        if (el('barPago')) el('barPago').textContent = '...';
        if (el('barFillPago')) el('barFillPago').style.width = '0%';

        // Always fetch via /api/perfil (handles ANO cache + live fallback internally)
        await _refreshPerfilLive(municipio, uf);
    }

    // Render fornecedores and servidores from batch (or fallback to HTML endpoint)
    const fornPanel = document.querySelector('[data-async-panel="fornecedores"]');
    const servPanel = document.querySelector('[data-async-panel="servidores"]');
    const panelPromises = [];

    if (batchData.TOP_FORNECEDORES && batchData.TOP_FORNECEDORES.row_count > 0) {
        if (fornPanel) {
            fornPanel.innerHTML = buildFornecedoresPanel(batchData.TOP_FORNECEDORES);
            initDataTables(fornPanel);
            initClickableRows(fornPanel);
        }
    } else {
        panelPromises.push(loadAsyncPanel('fornecedores', municipio, uf));
    }

    if (servPanel) {
        if (!_isDateFiltered() && batchData.TOP_SERVIDORES && batchData.TOP_SERVIDORES.row_count > 0) {
            const servData = batchData.TOP_SERVIDORES;
            servPanel.innerHTML = buildServidoresPanel(servData);
            initDataTables(servPanel);
            initClickableRows(servPanel);
        } else {
            panelPromises.push(loadAsyncPanel('servidores', municipio, uf));
        }
    }

    if (panelPromises.length) await Promise.all(panelPromises);

    const cards = Array.from(document.querySelectorAll('.finding-card[data-query]'));
    if (!cards.length) return;

    // Cards with cache: render instantly. Cards without: fetch individually.
    const uncachedCards = [];
    for (const card of cards) {
        const queryId = card.dataset.query;
        const cached = batchData[queryId];
        if (cached && cached.columns && cached.rows) {
            renderFindingCard(card, queryId, cached, municipio);
        } else {
            uncachedCards.push(card);
        }
    }
    updateSectionSummaries();

    // Fetch uncached cards individually (fallback)
    if (uncachedCards.length) {
        await runLimited(uncachedCards, 4, async (card) => {
            const queryId = card.dataset.query;
            const countEl = card.querySelector('[data-count]');
            const body = card.querySelector('.finding-body');
            try {
                const response = await fetch(`/api/run/${queryId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(_buildBody(municipio, uf)),
                });

                if (!response.ok) {
                    countEl.textContent = 'Tempo excedido';
                    body.innerHTML = '<p class="text-sm text-muted">Esse bloco nao terminou a tempo nesta tentativa.</p>';
                    card.classList.remove('loading');
                    card.classList.add('is-timeout');
                    updateSectionSummaries();
                    return;
                }

                const html = await response.text();
                const rowCount = Number(response.headers.get('X-Row-Count') || 0);
                countEl.textContent = rowCount;
                card.dataset.count = String(rowCount);
                body.innerHTML = html;
                body.classList.add('fade-in');
                setTimeout(() => body.classList.remove('fade-in'), 300);
                const exportLink = body.querySelector('[data-export-link]');
                if (exportLink) {
                    let exportUrl = `/api/export/${queryId}?municipio=${encodeURIComponent(municipio)}`;
                    if (_dateInicio) exportUrl += `&data_inicio=${_dateInicio}`;
                    if (_dateFim) exportUrl += `&data_fim=${_dateFim}`;
                    exportLink.href = exportUrl;
                }
                if (rowCount === 0) card.classList.add('is-empty', 'collapsed');
                card.classList.remove('loading');
                initDataTables(body);
                initClickableRows(body);
            } catch {
                countEl.textContent = '—';
                const countLabel = countEl.nextElementSibling;
                if (countLabel) countLabel.style.display = 'none';
                body.innerHTML = '<p class="text-sm text-muted">Nao foi possivel carregar este bloco agora.</p>';
                card.classList.remove('loading');
                card.classList.add('is-timeout');
            }
            updateSectionSummaries();
        });
    }
}

function renderFindingCard(card, queryId, data, municipio) {
    const countEl = card.querySelector('[data-count]');
    const body = card.querySelector('.finding-body');
    const rowCount = data.row_count || data.rows.length;

    countEl.textContent = rowCount;
    card.dataset.count = String(rowCount);
    if (rowCount === 0) {
        card.classList.add('is-empty', 'collapsed');
        body.innerHTML = '<p class="text-sm text-muted">Nenhum registro encontrado.</p>';
    } else {
        body.innerHTML = buildResultTable(queryId, data.columns, data.rows, municipio);
        initDataTables(body);
        initClickableRows(body);
    }
    body.classList.add('fade-in');
    setTimeout(() => body.classList.remove('fade-in'), 300);
    card.classList.remove('loading');
}

function buildResultTable(queryId, columns, rows, municipio) {
    const headerCells = columns.map(c =>
        `<th>${c.replace(/_/g, ' ')}</th>`
    ).join('');

    // Auto-detect clickable columns for dialog reuse
    const iCnpjBasico = columns.indexOf('cnpj_basico');
    const iCpfCnpj = columns.findIndex(c => c === 'cpf_cnpj' || c === 'cpf_cnpj_sancionado' || c === 'cpfcnpj_contratado' || c === 'cpf_cnpj_proponente');
    const iCnpjCompleto = columns.indexOf('cnpj_completo');
    const iNomeCredor = columns.findIndex(c => c === 'nome_credor' || c === 'razao_social' || c === 'nome_sancionado' || c === 'nome_contratado' || c === 'nome_proponente');
    const iCpf6 = columns.indexOf('cpf_digitos_6');
    const iNomeUpper = columns.indexOf('nome_upper');
    const iNomeServidor = columns.indexOf('nome_servidor');
    const iLicNum = columns.indexOf('numero_licitacao');
    const iLicAno = columns.indexOf('ano_licitacao');
    const iLicMod = columns.indexOf('modalidade');
    const iNomeCredorExact = columns.indexOf('nome_credor');
    const hasFornecedor = iCnpjBasico >= 0 || iCpfCnpj >= 0;
    const hasServidor = iCpf6 >= 0 && (iNomeUpper >= 0 || iNomeServidor >= 0);
    const hasLicitacao = iLicNum >= 0;

    // Row highlight: detect abrangencia + categoria_sancao for sanction severity
    const iAbrangencia = columns.indexOf('abrangencia');
    const iCategoria = columns.indexOf('categoria_sancao');

    // Sort by severity when abrangencia column is present: red first, yellow next, rest last
    if (iAbrangencia >= 0) {
        rows = [...rows].sort((a, b) => {
            const aAbr = String(a[iAbrangencia] || '');
            const aCat = iCategoria >= 0 ? String(a[iCategoria] || '') : '';
            const bAbr = String(b[iAbrangencia] || '');
            const bCat = iCategoria >= 0 ? String(b[iCategoria] || '') : '';
            const aRed = /inidone/i.test(aCat) || /Nacional/i.test(aAbr) || /Todas as Esferas/i.test(aAbr);
            const bRed = /inidone/i.test(bCat) || /Nacional/i.test(bAbr) || /Todas as Esferas/i.test(bAbr);
            const aYellow = !aRed && !!aAbr;
            const bYellow = !bRed && !!bAbr;
            const aScore = aRed ? 0 : aYellow ? 1 : 2;
            const bScore = bRed ? 0 : bYellow ? 1 : 2;
            return aScore - bScore;
        });
    }

    const bodyRows = rows.map(row => {
        const cells = row.map((val, ci) => {
            if (val === null || val === undefined) return '<td>-</td>';
            if (typeof val === 'boolean') return `<td>${val ? 'Sim' : 'Nao'}</td>`;
            if (Array.isArray(val)) return `<td>${val.join(', ')}</td>`;
            const col = columns[ci] || '';
            if (typeof val === 'number' || (typeof val === 'string' && /^-?\d+(\.\d+)?$/.test(val))) {
                const n = parseFloat(val);
                if (!isNaN(n)) {
                    if (col.startsWith('valor') || col.startsWith('total') || col === 'capital_social' || col === 'maior_salario' || col === 'salario') {
                        return `<td>${_shortBrl(n)}</td>`;
                    }
                    if (col.startsWith('pct')) {
                        return `<td>${n.toFixed(1)}%</td>`;
                    }
                    if (col.startsWith('qtd') || col === 'empenhos') {
                        return `<td>${_shortNum(n)}</td>`;
                    }
                }
            }
            return `<td>${val}</td>`;
        }).join('');

        // Determine row highlight class for sanction severity
        let rowHighlight = '';
        if (iAbrangencia >= 0) {
            const abr = String(row[iAbrangencia] || '');
            const cat = iCategoria >= 0 ? String(row[iCategoria] || '') : '';
            if (/inidone/i.test(cat) || /Nacional/i.test(abr) || /Todas as Esferas/i.test(abr)) rowHighlight = ' row-sancao';
            else if (abr) rowHighlight = ' row-sancao-leve';
        }

        // Servidor row detection (highest priority)
        if (hasServidor) {
            const cpf6 = _esc(row[iCpf6] || '');
            const nomeUp = _esc(row[iNomeUpper] || row[iNomeServidor] || '');
            const displayNome = _esc(row[iNomeServidor >= 0 ? iNomeServidor : iNomeUpper] || '');
            return `<tr class="clickable-row${rowHighlight}" data-cpf6="${cpf6}" data-nome-upper="${nomeUp}" data-nome="${displayNome}" data-cnpjs="[]">${cells}</tr>`;
        }
        // Licitacao row detection (prioritize over fornecedor when both exist)
        if (hasLicitacao) {
            const licNum = String(row[iLicNum] || '');
            const licAno = iLicAno >= 0 ? String(row[iLicAno] || '0') : '0';
            const licMod = iLicMod >= 0 ? String(row[iLicMod] || '') : '';
            if (licNum && licNum !== '000000000') {
                return `<tr class="clickable-row${rowHighlight}" data-licitacao-num="${_esc(licNum)}" data-licitacao-ano="${_esc(licAno)}" data-licitacao-mod="${_esc(licMod)}">${cells}</tr>`;
            }
        }
        // Fornecedor row detection
        if (hasFornecedor) {
            let cnpjB = '';
            if (iCnpjBasico >= 0) {
                cnpjB = String(row[iCnpjBasico] || '').replace(/\D/g, '').slice(0, 8);
            } else if (iCpfCnpj >= 0) {
                cnpjB = String(row[iCpfCnpj] || '').replace(/\D/g, '').slice(0, 8);
            }
            const nome = _esc(row[iNomeCredor >= 0 ? iNomeCredor : (iCpfCnpj >= 0 ? iCpfCnpj : 0)] || '');
            if (cnpjB.length === 8) {
                const nomeCredorAttr = (iNomeCredorExact >= 0 && iNomeCredorExact !== iNomeCredor)
                    ? ` data-fornecedor-nome-credor="${_esc(row[iNomeCredorExact] || '')}"`
                    : '';
                let cpfCnpjFull = '';
                if (iCnpjCompleto >= 0) cpfCnpjFull = String(row[iCnpjCompleto] || '').replace(/\D/g, '');
                else if (iCpfCnpj >= 0) cpfCnpjFull = String(row[iCpfCnpj] || '').replace(/\D/g, '');
                const cpfCnpjAttr = cpfCnpjFull.length >= 14
                    ? ` data-fornecedor-cpf-cnpj="${_esc(cpfCnpjFull)}"`
                    : '';
                return `<tr class="clickable-row${rowHighlight}" data-fornecedor-cnpj="${_esc(cnpjB)}" data-fornecedor-nome="${nome}"${nomeCredorAttr}${cpfCnpjAttr}>${cells}</tr>`;
            }
        }
        return `<tr${rowHighlight ? ` class="${rowHighlight.trim()}"` : ''}>${cells}</tr>`;
    }).join('');

    let exportHref = `/api/export/${queryId}?municipio=${encodeURIComponent(municipio)}`;
    if (_dateInicio) exportHref += `&data_inicio=${_dateInicio}`;
    if (_dateFim) exportHref += `&data_fim=${_dateFim}`;

    const legendHtml = iAbrangencia >= 0 ? `<div class="color-legend" style="margin-top:.5rem">
        <span class="color-legend-item"><span class="color-legend-dot" style="background:#ef4444"></span> Sancao de abrangencia nacional ou inidoneidade</span>
        <span class="color-legend-item"><span class="color-legend-dot" style="background:#f59e0b"></span> Sancao de abrangencia restrita (informativo)</span>
    </div>` : '';

    return `<div class="result-block">
        <div class="result-toolbar">
            <div>${legendHtml}</div>
            <a href="${exportHref}" data-export-link class="btn btn-outline btn-sm">Exportar CSV</a>
        </div>
        <div class="table-shell js-data-table" data-page-size="10">
            <div class="table-actions">
                <input type="search" class="table-filter" placeholder="Filtrar nesta tabela">
                <p class="table-meta text-sm text-muted" data-table-meta></p>
            </div>
            <div class="tbl-wrap">
                <table>
                    <thead><tr>${headerCells}</tr></thead>
                    <tbody>${bodyRows}</tbody>
                </table>
            </div>
            <div class="table-pagination">
                <button type="button" class="btn btn-outline btn-sm" data-page-prev>Anterior</button>
                <p class="text-sm text-muted" data-page-label></p>
                <button type="button" class="btn btn-outline btn-sm" data-page-next>Proxima</button>
            </div>
        </div>
    </div>`;
}

function _colIndex(cols, name) {
    return cols.indexOf(name);
}

function _val(row, cols, name) {
    const i = _colIndex(cols, name);
    return i >= 0 ? row[i] : null;
}

function _shortBrl(v) {
    const n = parseFloat(v) || 0;
    const a = Math.abs(n);
    if (a >= 1e9) return `R$ ${(n/1e9).toFixed(1)} bi`;
    if (a >= 1e6) return `R$ ${(n/1e6).toFixed(1)} mi`;
    if (a >= 1e3) return `R$ ${(n/1e3).toFixed(1)} mil`;
    return `R$ ${n.toFixed(0)}`;
}

function _shortNum(v) {
    const n = parseFloat(v) || 0;
    const a = Math.abs(n);
    if (a >= 1e6) return `${(n/1e6).toFixed(1)} mi`;
    if (a >= 1e3) return `${(n/1e3).toFixed(1)} mil`;
    return `${n.toFixed(0)}`;
}

function _esc(v) {
    if (v === null || v === undefined) return '-';
    return String(v).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function _fmtDate(v) {
    if (!v || v === '-') return '-';
    const s = String(v);
    // YYYYMM -> MM/YYYY
    if (/^\d{6}$/.test(s)) return `${s.slice(4,6)}/${s.slice(0,4)}`;
    // YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS -> DD/MM/YYYY
    const m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (m) return `${m[3]}/${m[2]}/${m[1]}`;
    return s;
}

function buildFornecedoresPanel(data) {
    const cols = data.columns;
    const bodyRows = data.rows.map(r => {
        const cnpjBasico = _esc(_val(r, cols, 'cnpj_basico') || '');
        const cnpjCompleto = _val(r, cols, 'cnpj_completo') || '';
        const cnpjFmt = _formatCnpj(cnpjBasico, cnpjCompleto);
        const nome = _esc(_val(r, cols, 'nome_credor'));
        const razao = _esc(_val(r, cols, 'razao_social') || '');
        const total = _shortBrl(_val(r, cols, 'total_pago') || _val(r, cols, 'total_contratado'));
        const qtd = _shortNum(_val(r, cols, 'qtd_empenhos') || _val(r, cols, 'qtd_contratos'));
        const situacao = _esc(_val(r, cols, 'desc_situacao') || '-');
        const sitClass = situacao === 'Ativa' ? '' : (situacao === '-' ? '' : 'badge badge-gray');
        let badges = '';
        const isInidoneidade = _val(r, cols, 'flag_inidoneidade');
        const abrangenciaRaw = _val(r, cols, 'abrangencia_sancao_info') || '';
        const sancaoAplica = abrangenciaRaw.startsWith('!');
        const abrangenciaInfo = abrangenciaRaw.replace(/^!/, '');
        const parenMatch = abrangenciaInfo.match(/\(([^)]+)\)/);
        const scopeSuffix = abrangenciaInfo.startsWith('Nacional')
            ? ' (Nacional)'
            : parenMatch ? ` (${parenMatch[1].slice(0, 50)})` : '';
        if (isInidoneidade) badges += '<span class="badge badge-red" title="Inidoneidade - CEIS (Nacional)">Inidoneidade - CEIS (Nacional)</span>';
        else if (_val(r, cols, 'flag_ceis')) badges += `<span class="badge badge-orange" title="Impedimento - CEIS${_esc(scopeSuffix)}">Impedimento - CEIS${_esc(scopeSuffix)}</span>`;
        if (_val(r, cols, 'flag_cnep')) badges += `<span class="badge badge-orange" title="CNEP${_esc(scopeSuffix)}">CNEP${_esc(scopeSuffix)}</span>`;
        if (_val(r, cols, 'flag_acordo_leniencia')) badges += '<span class="badge badge-blue" title="Acordo de Leniencia">Acordo de Leniencia</span>';
        if (_val(r, cols, 'flag_pgfn')) badges += '<span class="badge badge-yellow" title="Divida ativa">Divida ativa</span>';
        if (_val(r, cols, 'flag_inativa')) badges += '<span class="badge badge-gray" title="Empresa inativa na Receita">Cadastro inativo</span>';
        if (!badges) badges = '<span class="text-sm text-muted">Sem sinal automatico</span>';
        const rowClass = (() => {
            const recInid = _val(r, cols, 'flag_recebeu_durante_inidoneidade');
            const recSan = _val(r, cols, 'flag_recebeu_durante_sancao_aplicavel');
            if (recInid) return 'clickable-row row-sancao';
            if (recSan) return 'clickable-row row-sancao-leve';
            return 'clickable-row';
        })();
        return `<tr class="${rowClass}" data-fornecedor-cnpj="${cnpjBasico}" data-fornecedor-cpf-cnpj="${_esc(cnpjCompleto)}" data-fornecedor-nome="${razao || nome}" data-fornecedor-nome-credor="${nome}"><td>${nome}</td><td class="auditor-only"><code class="text-sm">${cnpjFmt}</code></td><td class="text-right">${total}</td><td class="text-right auditor-only">${qtd}</td><td>${badges}</td></tr>`;
    }).join('');

    const hasRecInid = data.rows.some(r => _val(r, data.columns, 'flag_recebeu_durante_inidoneidade'));
    const hasRecSancao = data.rows.some(r => _val(r, data.columns, 'flag_recebeu_durante_sancao_aplicavel'));
    const hasAcordo = data.rows.some(r => _val(r, data.columns, 'flag_acordo_leniencia'));
    const _fldot = (bg) => `<span class="color-legend-dot" style="background:${bg}"></span>`;
    let fornLegend = '';
    if (hasRecInid || hasRecSancao || hasAcordo) {
        let items = [];
        if (hasRecInid) items.push(`<span class="color-legend-item">${_fldot('#ef4444')} Recebeu durante Inidoneidade</span>`);
        if (hasRecSancao) items.push(`<span class="color-legend-item">${_fldot('#f59e0b')} Recebeu durante sancao aplicavel</span>`);
        if (hasAcordo) items.push(`<span class="color-legend-item">${_fldot('#3b82f6')} Acordo de leniencia vigente</span>`);
        fornLegend = `<div class="color-legend">${items.join('')}</div>`;
    }

    return `<section class="result-block">
        <div class="result-toolbar"><div>
            <h3 class="card-title">Maiores fornecedores do municipio</h3>
            <p class="text-muted text-sm">Concentracao de pagamentos e sinais automaticos de cada fornecedor. Clique em um fornecedor para ver detalhes.</p>
            ${fornLegend}
        </div></div>
        <div class="table-shell js-data-table" data-page-size="10">
            <div class="table-actions">
                <input type="search" class="table-filter" placeholder="Filtrar nesta tabela" aria-label="Filtrar fornecedores">
                <p class="table-meta text-sm text-muted" data-table-meta></p>
            </div>
            <div class="tbl-wrap"><table>
                <thead><tr>
                    <th><span class="citizen-only">Empresa</span><span class="auditor-only">Fornecedor</span></th>
                    <th class="auditor-only">CNPJ</th>
                    <th class="text-right"><span class="citizen-only">Recebido</span><span class="auditor-only">Total Pago</span></th>
                    <th class="text-right auditor-only">Empenhos</th>
                    <th><span class="citizen-only">Sinais</span><span class="auditor-only">Sinais de Atencao</span></th>
                </tr></thead>
                <tbody>${bodyRows}</tbody>
            </table></div>
            <div class="table-pagination">
                <button type="button" class="btn btn-outline btn-sm" data-page-prev>Anterior</button>
                <p class="text-sm text-muted" data-page-label></p>
                <button type="button" class="btn btn-outline btn-sm" data-page-next>Proxima</button>
            </div>
        </div>
    </section>`;
}

function _formatCnpj(cnpjBasico, cnpjCompleto) {
    if (cnpjCompleto && cnpjCompleto.length >= 14) {
        const d = cnpjCompleto.replace(/\D/g, '');
        return `${d.slice(0,2)}.${d.slice(2,5)}.${d.slice(5,8)}/${d.slice(8,12)}-${d.slice(12,14)}`;
    }
    // Mask with asterisks for missing digits
    const d = (cnpjBasico || '').replace(/\D/g, '');
    return `${d.slice(0,2)}.${d.slice(2,5)}.${d.slice(5,8)}/****-**`;
}

function _situacaoLabel(sit) {
    const map = {'1': 'Nula', '2': 'Ativa', '3': 'Suspensa', '4': 'Inapta', '8': 'Baixada'};
    return map[String(sit)] || (sit ? `Sit. ${sit}` : '-');
}

// ── Date filter state ───────────────────────────────────────────
let _dateInicio = null;
let _dateFim = null;
let _currentUf = 'PB';

function _isDateFiltered() { return !!(_dateInicio || _dateFim); }

function _getPeriodo() {
    if (!_isDateFiltered()) return '';
    const yr = new Date().getFullYear();
    if (_dateInicio === `${yr}-01-01` && _dateFim && _dateFim.startsWith(`${yr}`)) return 'ANO';
    return 'CUSTOM';
}

function _buildBody(municipio, uf) {
    const body = { municipio, uf: uf || _currentUf };
    if (_dateInicio) body.data_inicio = _dateInicio;
    if (_dateFim) body.data_fim = _dateFim;
    return body;
}

function _formatDatePt(iso) {
    if (!iso) return '';
    const [y, m, d] = iso.split('-');
    return `${d}/${m}/${y}`;
}

function _updateHeroStats(perfil) {
    const el = id => document.getElementById(id);
    if (el('heroQtdEmpenhos')) el('heroQtdEmpenhos').textContent = _shortNum(perfil.qtd_empenhos || 0);
    if (el('heroTotalPago')) el('heroTotalPago').textContent = _shortBrl(perfil.total_pago || 0);
    if (el('heroQtdFornecedores')) el('heroQtdFornecedores').textContent = _shortNum(perfil.qtd_fornecedores || 0);
}

function _updateInsightCards(perfil) {
    const el = id => document.getElementById(id);
    const totalEmpenhado = parseFloat(perfil.total_empenhado) || 0;
    const totalPago = parseFloat(perfil.total_pago) || 0;
    const pctPago = totalEmpenhado ? (totalPago / totalEmpenhado * 100) : 0;
    const gap = totalEmpenhado - totalPago;

    if (el('insightPctPago')) el('insightPctPago').innerHTML =
        `<span class="citizen-only">${pctPago.toFixed(1)}% do planejado foi pago</span>`
        + `<span class="auditor-only">${pctPago.toFixed(1)}% do valor empenhado foi pago</span>`;
    if (el('progressPctPago')) el('progressPctPago').style.width = `${pctPago.toFixed(1)}%`;
    if (el('insightGapFinanceiro')) el('insightGapFinanceiro').innerHTML =
        `<span class="citizen-only">Ainda n&atilde;o pago: ${_shortBrl(gap)}</span>`
        + `<span class="auditor-only">Diferenca entre empenhado e pago: ${_shortBrl(gap)}</span>`;

    const pctSemLicit = perfil.pct_sem_licitacao;
    if (el('insightPctSemLicit')) el('insightPctSemLicit').textContent = pctSemLicit != null ? `${parseFloat(pctSemLicit).toFixed(1)}%` : 'N/D';

    const pctDispensa = perfil.pct_sem_licitacao;
    if (el('insightPctDispensa')) el('insightPctDispensa').textContent = pctDispensa != null ? `${parseFloat(pctDispensa).toFixed(1)}%` : 'N/D';

    const pctFolha = perfil.pct_folha_receita;
    if (el('insightPctFolha')) el('insightPctFolha').textContent = pctFolha != null ? `${parseFloat(pctFolha).toFixed(1)}%` : 'N/D';

    // Update bar chart
    if (el('barEmpenhado')) el('barEmpenhado').textContent = _shortBrl(totalEmpenhado);
    if (el('barPago')) el('barPago').textContent = _shortBrl(totalPago);
    if (el('barFillPago')) el('barFillPago').style.width = `${pctPago.toFixed(1)}%`;
}

async function _loadHeatmap(municipio) {
    const grid = document.getElementById('heatmapGrid');
    if (!grid) return;
    try {
        const res = await fetch(`/api/heatmap/${encodeURIComponent(municipio)}`);
        if (!res.ok) throw new Error('http ' + res.status);
        const data = await res.json();
        _renderHeatmap(data.cells || []);
    } catch (e) {
        grid.innerHTML = '<p class="text-sm text-muted">Não foi possível carregar o heatmap.</p>';
    }
}

function _renderHeatmap(cells) {
    const grid = document.getElementById('heatmapGrid');
    const legend = document.getElementById('heatmapLegend');
    if (!grid) return;
    if (!cells.length) {
        grid.innerHTML = '<p class="text-sm text-muted">Sem dados de empenho mensais para este município.</p>';
        if (legend) legend.innerHTML = '';
        return;
    }

    // Build (ano, mes) -> valor
    const byKey = {};
    const anos = new Set();
    let maxVal = 0;
    cells.forEach(c => {
        const v = parseFloat(c.total_empenhado) || 0;
        byKey[`${c.ano}-${c.mes}`] = v;
        anos.add(c.ano);
        if (v > maxVal) maxVal = v;
    });
    const anosSorted = Array.from(anos).sort((a, b) => b - a); // mais recente no topo

    // Média e desvio-padrão (usa todos os valores reais, inclui zeros de meses com registros)
    const vals = Object.values(byKey);
    const mean = vals.reduce((s, v) => s + v, 0) / vals.length;
    const variance = vals.reduce((s, v) => s + (v - mean) ** 2, 0) / vals.length;
    const std = Math.sqrt(variance);

    // Escala linear min-max (ignora zeros — sem-dados usa cor neutra)
    const nonZero = vals.filter(v => v > 0);
    const minVal = nonZero.length ? Math.min(...nonZero) : 0;
    const spread = Math.max(1, maxVal - minVal);
    const mesesLabel = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];

    const ramp = ['#e6efff', '#c2d6f7', '#9bbbed', '#6f9ae0', '#4579cf', '#2555ab', '#0f3380'];
    const colorFor = v => {
        if (!v) return { bg: '#1e2a3a', color: '#4a5568' };
        const t = (v - minVal) / spread;
        const idx = Math.min(ramp.length - 1, Math.max(0, Math.floor(t * ramp.length)));
        return { bg: ramp[idx], color: idx >= 4 ? '#fff' : '#0f2056' };
    };

    const html = ['<div class="hm-row hm-header"><div class="hm-cell hm-year-label"></div>'];
    mesesLabel.forEach(m => html.push(`<div class="hm-cell hm-month-label">${m}</div>`));
    html.push('</div>');

    anosSorted.forEach(ano => {
        html.push(`<div class="hm-row"><div class="hm-cell hm-year-label">${ano}</div>`);
        for (let m = 1; m <= 12; m++) {
            const v = byKey[`${ano}-${m}`] || 0;
            const z = std > 0 ? (v - mean) / std : 0;
            const outlier = z > 2 ? ' hm-outlier' : '';
            const { bg, color } = colorFor(v);
            const label = v ? _shortBrl(v) : '—';
            const title = v ? `${mesesLabel[m - 1]}/${ano}: ${_shortBrl(v)} — clique para drill-down${z > 2 ? ` (${z.toFixed(1)}σ acima da média)` : ''}` : `${mesesLabel[m - 1]}/${ano}: sem dados`;
            const clickable = v ? ' hm-clickable' : '';
            const dataAttrs = v ? ` data-ano="${ano}" data-mes="${m}"` : '';
            html.push(`<div class="hm-cell hm-value${outlier}${clickable}" style="background:${bg};color:${color}" title="${title}"${dataAttrs}><span>${label}</span></div>`);
        }
        html.push('</div>');
    });

    grid.innerHTML = html.join('');

    grid.querySelectorAll('.hm-clickable').forEach(cell => {
        cell.addEventListener('click', () => {
            const ano = parseInt(cell.dataset.ano, 10);
            const mes = parseInt(cell.dataset.mes, 10);
            if (ano && mes) openHeatmapMonthDialog(_currentMunicipio, ano, mes);
        });
    });

    if (legend) {
        const steps = ramp.map((c, i) => {
            const lo = minVal + (i / ramp.length) * spread;
            const hi = minVal + ((i + 1) / ramp.length) * spread;
            return `<div class="hm-legend-step" style="background:${c}" title="${_shortBrl(lo)} – ${_shortBrl(hi)}"></div>`;
        }).join('');
        legend.innerHTML = `
            <span class="hm-legend-label">Menor</span>
            <div class="hm-legend-ramp">${steps}</div>
            <span class="hm-legend-label">Maior</span>
            <span class="hm-legend-sep"></span>
            <span class="hm-legend-outlier"></span>
            <span class="hm-legend-label">Mês atípico (>2σ)</span>
        `;
    }
}

async function _refreshPerfilLive(municipio, uf) {
    try {
        const res = await fetch('/api/perfil', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(_buildBody(municipio, uf)),
        });
        if (res.ok) {
            const perfil = await res.json();
            _updateHeroStats(perfil);
            _updateInsightCards(perfil);
        } else {
            console.warn('perfil endpoint returned', res.status);
        }
    } catch (e) {
        console.warn('perfil fetch failed', e);
    }
}

// ── Dialog navigation stack ─────────────────────────────────────
let _currentMunicipio = '';
const _dialogStack = []; // [{title, html}]

function _dialogPush() {
    const dialog = document.getElementById('empresa-dialog');
    if (!dialog) return;
    const title = dialog.querySelector('.dialog-title').textContent;
    const html = dialog.querySelector('.dialog-body').innerHTML;
    _dialogStack.push({ title, html });
    dialog.querySelector('.dialog-back').style.visibility = 'visible';
}

function _dialogPop() {
    const dialog = document.getElementById('empresa-dialog');
    if (!dialog || !_dialogStack.length) return;
    const prev = _dialogStack.pop();
    dialog.querySelector('.dialog-title').textContent = prev.title;
    const body = dialog.querySelector('.dialog-body');
    body.innerHTML = prev.html;
    _reattachDialogLinks(body);
    if (!_dialogStack.length) dialog.querySelector('.dialog-back').style.visibility = 'hidden';
}

function _dialogReset() {
    _dialogStack.length = 0;
    const dialog = document.getElementById('empresa-dialog');
    if (dialog) dialog.querySelector('.dialog-back').style.visibility = 'hidden';
    document.body.classList.remove('dialog-open');
}

// ── Dialog: history integration + swipe-to-close (mobile) ──────────
// Objetivo: botao voltar do Android/gesto iOS fecha o dialog em vez de
// sair da pagina. Ao abrir o dialog empilhamos um state; se o usuario
// voltar, o popstate fecha o dialog.
let _dialogHistoryState = false;

function _dialogOnOpen() {
    const dialog = document.getElementById('empresa-dialog');
    if (!dialog) return;
    document.body.classList.add('dialog-open');
    if (!_dialogHistoryState) {
        try {
            history.pushState({ tpbDialog: true }, '', '');
            _dialogHistoryState = true;
        } catch { /* ignore */ }
    }
}

function _dialogOnClose() {
    _dialogReset();
    if (_dialogHistoryState) {
        _dialogHistoryState = false;
        if (history.state && history.state.tpbDialog) {
            // Removemos nosso state do historico sem disparar navegacao
            try { history.back(); } catch { /* ignore */ }
        }
    }
}

window.addEventListener('popstate', () => {
    const dialog = document.getElementById('empresa-dialog');
    if (!dialog || !dialog.open) {
        _dialogHistoryState = false;
        return;
    }
    // Popstate com dialog aberto -> fechamos o dialog (state ja foi consumido)
    _dialogHistoryState = false;
    dialog.close();
});

function _initDialogSwipeToClose() {
    const dialog = document.getElementById('empresa-dialog');
    if (!dialog) return;

    // So ativa em dispositivos touch + viewport mobile
    const isTouchMobile = () =>
        window.matchMedia('(hover: none) and (pointer: coarse)').matches &&
        window.innerWidth <= 640;

    let startY = 0;
    let lastY = 0;
    let lastTime = 0;
    let velocity = 0;
    let dragging = false;
    let allowDrag = false;
    const CLOSE_DIST = 120;
    const CLOSE_VELOCITY = 0.8; // px/ms

    const header = () => dialog.querySelector('.dialog-header');
    const body = () => dialog.querySelector('.dialog-body');

    dialog.addEventListener('touchstart', (e) => {
        if (!isTouchMobile()) return;
        if (e.touches.length !== 1) return;
        const touch = e.touches[0];
        // Swipe-down so inicia se o toque comeca no header OU no topo do body com scrollTop=0
        const target = e.target;
        const inHeader = header() && header().contains(target);
        const b = body();
        const scrolledTop = b && b.scrollTop <= 0;
        if (!inHeader && !scrolledTop) {
            allowDrag = false;
            return;
        }
        allowDrag = true;
        startY = touch.clientY;
        lastY = startY;
        lastTime = e.timeStamp;
        velocity = 0;
        dragging = false;
    }, { passive: true });

    dialog.addEventListener('touchmove', (e) => {
        if (!allowDrag || !isTouchMobile()) return;
        const touch = e.touches[0];
        const dy = touch.clientY - startY;
        // So arrasta pra baixo
        if (dy <= 0) {
            dragging = false;
            dialog.classList.remove('dragging');
            dialog.style.transform = '';
            return;
        }
        // Se o body esta rolado, nao arrasta o dialog
        const b = body();
        const inHeader = header() && header().contains(e.target);
        if (!inHeader && b && b.scrollTop > 0) {
            allowDrag = false;
            dialog.classList.remove('dragging');
            dialog.style.transform = '';
            return;
        }
        dragging = true;
        dialog.classList.add('dragging');
        const dt = e.timeStamp - lastTime;
        if (dt > 0) velocity = (touch.clientY - lastY) / dt;
        lastY = touch.clientY;
        lastTime = e.timeStamp;
        // Aplica translate com resistencia leve
        dialog.style.transform = `translateY(${dy}px)`;
        dialog.style.opacity = String(Math.max(0.5, 1 - dy / 600));
    }, { passive: true });

    const finishDrag = (cancelled) => {
        if (!dragging) {
            dialog.classList.remove('dragging');
            dialog.style.transform = '';
            dialog.style.opacity = '';
            return;
        }
        dragging = false;
        const dy = lastY - startY;
        const shouldClose = !cancelled && (dy > CLOSE_DIST || velocity > CLOSE_VELOCITY);
        dialog.classList.remove('dragging');
        if (shouldClose) {
            dialog.classList.add('closing');
            dialog.style.transform = '';
            dialog.style.opacity = '';
            setTimeout(() => {
                dialog.classList.remove('closing');
                dialog.close();
            }, 220);
            if ('vibrate' in navigator) { try { navigator.vibrate(10); } catch {} }
        } else {
            dialog.style.transform = '';
            dialog.style.opacity = '';
        }
    };

    dialog.addEventListener('touchend', () => finishDrag(false), { passive: true });
    dialog.addEventListener('touchcancel', () => finishDrag(true), { passive: true });
}

// ── Skeleton helpers: gera HTML prenunciando formato do conteudo ───
function skeletonTableHtml(rows = 5, cols = 3) {
    const parts = ['<div class="skeleton-table">'];
    for (let i = 0; i < rows; i++) {
        parts.push('<div class="skeleton-row">');
        for (let c = 0; c < cols; c++) {
            const cls = c === 0 ? '' : (c === cols - 1 ? 'narrow' : 'wide');
            parts.push(`<div class="skeleton-block ${cls}"></div>`);
        }
        parts.push('</div>');
    }
    parts.push('</div>');
    return parts.join('');
}

function skeletonCardHtml(items = 3) {
    const parts = ['<div class="skeleton-card">'];
    for (let i = 0; i < items; i++) {
        parts.push(
            '<div class="skeleton-card-item">' +
                '<div class="skeleton-block avatar"></div>' +
                '<div class="skeleton-card-lines">' +
                    '<div class="skeleton-block title"></div>' +
                    '<div class="skeleton-block subtitle"></div>' +
                '</div>' +
                '<div class="skeleton-block tag"></div>' +
            '</div>'
        );
    }
    parts.push('</div>');
    return parts.join('');
}

function _reattachDialogLinks(body) {
    body.querySelectorAll('.dialog-link[data-lic-num]').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            openLicitacaoDialog(link.dataset.licNum, link.dataset.licAno || '0', _currentMunicipio, link.textContent);
        });
    });
    body.querySelectorAll('.dialog-link[data-forn-cnpj]').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            openFornecedorDialog(link.dataset.fornCnpj, link.dataset.fornNome || 'Fornecedor', null, false, link.dataset.fornNomeCredor || '', link.dataset.fornCpfCnpj || '');
        });
    });
    body.querySelectorAll('tr.clickable-row[data-empenho-id]').forEach(row => {
        row.addEventListener('click', (e) => {
            if (e.target.closest('a')) return;
            openEmpenhoDialog(row.dataset.empenhoId);
        });
    });
    // Municipality selector in fornecedor dialog
    body.querySelectorAll('.mun-selector').forEach(sel => {
        sel.addEventListener('change', () => {
            const cnpj = sel.dataset.fornCnpj;
            const nome = sel.dataset.fornNome;
            const mun = sel.value;
            const nc = sel.dataset.fornNomeCredor || '';
            const cc = sel.dataset.fornCpfCnpj || '';
            openFornecedorDialog(cnpj, nome, mun, true, nc, cc);
        });
    });
    // Cross-municipality sanction rows
    body.querySelectorAll('tr[data-switch-mun]').forEach(row => {
        row.addEventListener('click', () => {
            const cnpj = row.dataset.fornCnpj;
            const nome = row.dataset.fornNome;
            const mun = row.dataset.switchMun;
            const nc = row.dataset.fornNomeCredor || '';
            const cc = row.dataset.fornCpfCnpj || '';
            openFornecedorDialog(cnpj, nome, mun, true, nc, cc);
        });
    });
    _initDialogTableSort(body);
}

function _initDialogTableSort(root) {
    root.querySelectorAll('.dialog-table').forEach(table => {
        const headers = Array.from(table.querySelectorAll('thead th'));
        let sortCol = -1, sortAsc = true;
        headers.forEach((th, colIndex) => {
            th.style.cursor = 'pointer';
            th.addEventListener('click', () => {
                if (sortCol === colIndex) { sortAsc = !sortAsc; } else { sortCol = colIndex; sortAsc = true; }
                headers.forEach(h => h.classList.remove('sort-asc', 'sort-desc'));
                th.classList.add(sortAsc ? 'sort-asc' : 'sort-desc');
                const tbody = table.querySelector('tbody');
                const rows = Array.from(tbody.querySelectorAll('tr'));
                rows.sort((a, b) => {
                    const cellA = a.children[colIndex]?.textContent.trim() || '';
                    const cellB = b.children[colIndex]?.textContent.trim() || '';
                    const numA = parseFloat(cellA.replace(/[R$%\s.]/g, '').replace(',', '.'));
                    const numB = parseFloat(cellB.replace(/[R$%\s.]/g, '').replace(',', '.'));
                    if (!isNaN(numA) && !isNaN(numB)) return sortAsc ? numA - numB : numB - numA;
                    return sortAsc ? cellA.localeCompare(cellB, 'pt-BR') : cellB.localeCompare(cellA, 'pt-BR');
                });
                rows.forEach(r => tbody.appendChild(r));
            });
        });
    });
}

// Unified detail cache — evicts on fetch error
const _detailCache = {};

function _cachedPost(url, key, payload) {
    if (_detailCache[key]) return _detailCache[key];
    const promise = fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    }).then(r => {
        if (!r.ok) throw new Error(r.status);
        return r.json();
    }).catch(() => {
        delete _detailCache[key];
        return {};
    });
    _detailCache[key] = promise;
    return promise;
}

function _fetchServidorDetails(cpf6, nome, cnpjs, municipio) {
    return _cachedPost('/api/servidor/detalhes', `srv:${cpf6}:${nome}:${municipio}`, { cpf6, nome, cnpjs, municipio });
}

function _fetchFornecedorDetails(cnpjBasico, municipio, nomeCredor, cpfCnpj) {
    const payload = { cnpj_basico: cnpjBasico, municipio };
    if (cpfCnpj) payload.cpf_cnpj = cpfCnpj;
    if (nomeCredor) payload.nome_credor = nomeCredor;
    const cacheKey = `forn:${cpfCnpj || cnpjBasico}:${municipio}${nomeCredor ? ':' + nomeCredor : ''}`;
    return _cachedPost('/api/fornecedor/detalhes', cacheKey, payload);
}

function _buildEmpenhoTable(empenhos, sancaoRanges) {
    const rows = empenhos.map(e => {
        const dt = _fmtDate(e.data_empenho);
        const mod = e.modalidade_licitacao || '-';
        const numLic = e.numero_licitacao || '';
        const semLic = !numLic || numLic === '000000000' || (mod && mod.toLowerCase().includes('sem licit'));
        let modCell;
        if (semLic) {
            modCell = `<span class="badge badge-yellow"><span class="citizen-only">Sem concorrencia</span><span class="auditor-only">Sem licitacao</span></span>`;
        } else {
            const licLabel = `${mod} (${numLic})`;
            modCell = `<a href="#" class="dialog-link" data-lic-num="${_esc(numLic)}" data-lic-ano="0">${_esc(licLabel)}</a>`;
        }
        const empDate = e.data_empenho ? new Date(e.data_empenho) : null;
        const overlapping = empDate ? sancaoRanges.filter(r =>
            empDate >= r.inicio && (!r.fim || empDate <= r.fim)
        ) : [];
        const matchedSancao = overlapping.find(r => r.grave) || overlapping[0];
        const afeta = !!(matchedSancao && matchedSancao.grave);
        const rowClass = afeta ? 'clickable-row row-sancao' : 'clickable-row';
        let sancaoTag = '';
        if (afeta) {
            sancaoTag = ` <span class="badge badge-red" style="font-size:.6rem" title="${_esc(matchedSancao.categoria || '')} — ${_esc(matchedSancao.abrangencia || '')}"><span class="citizen-only">empresa estava punida</span><span class="auditor-only">durante sancao</span></span>`;
        } else if (matchedSancao) {
            sancaoTag = ` <span class="badge badge-muted" style="font-size:.6rem" title="Sancao vigente neste periodo mas nao afeta contratos com este municipio (${_esc(matchedSancao.abrangencia || 'abrangencia limitada')})"><span class="citizen-only">punicao nao vale aqui</span><span class="auditor-only">sancao nao aplicavel</span></span>`;
        }
        const elRaw = e.elemento_despesa || '-';
        const elCitizen = _stripCodePrefix(elRaw) || elRaw;
        return `<tr class="${rowClass}" data-empenho-id="${e.id}">
            <td>${dt}${sancaoTag}</td>
            <td><span class="citizen-only">${_esc(elCitizen)}</span><span class="auditor-only">${_esc(elRaw)}</span></td>
            <td class="text-right">${_shortBrl(e.valor_empenhado)}</td>
            <td class="text-right">${_shortBrl(e.valor_pago)}</td>
            <td>${modCell}</td>
        </tr>`;
    }).join('');
    return `<div class="tbl-wrap"><table class="dialog-table">
        <thead><tr>
            <th>Data</th>
            <th><span class="citizen-only">Tipo de gasto</span><span class="auditor-only">Elemento</span></th>
            <th class="text-right"><span class="citizen-only">Reservado</span><span class="auditor-only">Empenhado</span></th>
            <th class="text-right">Pago</th>
            <th><span class="citizen-only">Tipo de licita&ccedil;&atilde;o</span><span class="auditor-only">Modalidade</span></th>
        </tr></thead>
        <tbody>${rows}</tbody>
    </table></div>`;
}

function _renderEmpresaCard(e, cnpjBasico, extraBadges) {
    if (!e) {
        return `<div class="empresa-card empresa-missing">
            <div class="empresa-header">
                <strong class="text-muted">Empresa nao encontrada na base RFB</strong>
                <code>${_formatCnpj(cnpjBasico, null)}</code>
            </div>
            ${extraBadges ? `<div class="empresa-details" style="margin-top:.3rem">${extraBadges}</div>` : ''}
        </div>`;
    }
    const cnpjFmt = _formatCnpj(e.cnpj_basico, e.cnpj_completo);
    const sit = _situacaoLabel(e.situacao_cadastral);
    const sitClass = String(e.situacao_cadastral) === '2' ? '' : 'badge badge-red';
    const capital = e.capital_social ? _shortBrl(e.capital_social) : '-';
    const local = [e.municipio, e.uf].filter(Boolean).join(' - ') || '-';
    const nome = _esc(e.razao_social || 'Razao social nao disponivel');
    const nomeLink = `<a href="#" class="dialog-link" data-forn-cnpj="${_esc(e.cnpj_basico)}" data-forn-nome="${nome}">${nome}</a>`;
    const qualif = e.qualificacao_socio ? `<span>${dualLabel('Papel:','Qualificacao:')} <strong>${_esc(e.qualificacao_socio)}</strong></span>` : '';
    const dtEntrada = e.dt_entrada_sociedade ? `<span class="auditor-only">Entrada: ${_fmtDate(e.dt_entrada_sociedade)}</span>` : '';
    return `<div class="empresa-card">
        <div class="empresa-header">
            <strong>${nomeLink}</strong>
            <code class="auditor-only">${cnpjFmt}</code>
        </div>
        <div class="empresa-details">
            ${qualif}${dtEntrada}
            <span>${dualLabel('Cadastro:','Situacao:')} <span class="${sitClass}">${sit}</span></span>
            <span class="auditor-only">Capital: ${capital}</span>
            <span>Sede: ${_esc(local)}</span>
            ${e.cnae_principal ? `<span class="auditor-only">CNAE: ${_esc(e.cnae_principal)}</span>` : ''}
        </div>
        ${extraBadges ? `<div style="margin-top:.35rem">${extraBadges}</div>` : ''}
    </div>`;
}

async function openServidorDialog(cpf6, nome, cnpjs, servidorNome) {
    const dialog = document.getElementById('empresa-dialog');
    if (!dialog) return;
    if (dialog.open) { _dialogPush(); } else { _dialogReset(); }
    const title = dialog.querySelector('.dialog-title');
    const body = dialog.querySelector('.dialog-body');
    const cpfMask = cpf6.length === 6 ? `***.${cpf6.slice(0,3)}.${cpf6.slice(3,6)}-**` : '';
    title.textContent = cpfMask ? `${servidorNome}  —  CPF: ${cpfMask}` : servidorNome;
    body.innerHTML = '<p class="text-sm text-muted">Carregando...</p>';
    if (!dialog.open) dialog.showModal();
    document.body.classList.add('dialog-open');

    const data = await _fetchServidorDetails(cpf6, nome, cnpjs, _currentMunicipio);
    const sancoes = data.empresa_sancoes || {};
    const pgfn = data.empresa_pgfn || {};
    const empMap = data.empresa_empenhos || {};
    const acordosMap = data.empresa_acordos || {};
    let html = '';

    // Stats grid
    const vinculos = data.vinculos || [];
    const empresas = data.empresas || [];
    const bf = data.bolsa_familia || [];
    const qtdEmpresas = cnpjs ? cnpjs.length : 0;
    const qtdSancionadas = Object.keys(sancoes).length;
    const qtdPgfn = Object.keys(pgfn).length;
    const totalPago = Object.values(empMap).reduce((s, e) => s + (e.total_pago || 0), 0);
    const empVincData = data.empenhos_durante_vinculo || [];
    const totalDuranteVinc = empVincData.reduce((s, e) => s + (e.valor_pago || 0), 0);
    const maiorSalario = vinculos.reduce((m, v) => Math.max(m, v.maior_salario || 0), 0);

    html += '<div class="stats-grid">';
    if (maiorSalario > 0) html += `<div class="stat-cell"><span class="stat-value">${_shortBrl(maiorSalario)}</span><span class="stat-label">Maior salario</span></div>`;
    html += `<div class="stat-cell"><span class="stat-value">${qtdEmpresas}</span><span class="stat-label">${dualLabel('Empresas onde atua','Empresas vinculadas')}</span></div>`;
    if (totalDuranteVinc > 0) html += `<div class="stat-cell" style="border-color:#fecaca"><span class="stat-value" style="color:var(--red)">${_shortBrl(totalDuranteVinc)}</span><span class="stat-label">${dualLabel('Pago as empresas enquanto era servidor','Pago as empresas durante vinculo')}</span></div>`;
    if (totalPago > 0 && totalPago !== totalDuranteVinc) html += `<div class="stat-cell"><span class="stat-value">${_shortBrl(totalPago)}</span><span class="stat-label">Pago as empresas (total)</span></div>`;
    if (qtdSancionadas > 0) html += `<div class="stat-cell" style="border-color:#fecaca"><span class="stat-value" style="color:var(--red)">${qtdSancionadas}</span><span class="stat-label">${dualLabel('Empresas punidas','Empresas sancionadas')}</span></div>`;
    if (qtdPgfn > 0) html += `<div class="stat-cell" style="border-color:#fdba74"><span class="stat-value" style="color:#c2410c">${qtdPgfn}</span><span class="stat-label">${dualLabel('Empresas devendo impostos','Empresas c/ divida PGFN')}</span></div>`;
    if (bf.length > 0) html += `<div class="stat-cell" style="border-color:#fed7aa"><span class="stat-value" style="color:var(--yellow)">Sim</span><span class="stat-label">Bolsa Familia</span></div>`;
    if (data.ceaf && data.ceaf.length) html += `<div class="stat-cell" style="border-color:var(--red)"><span class="stat-value" style="color:var(--red)">${data.ceaf.length}</span><span class="stat-label">${dualLabel('Expulso do servico publico federal','Expulsao federal')}</span></div>`;
    html += '</div>';

    // Vinculos como servidor (first)
    if (vinculos.length) {
        html += `<div class="dialog-section"><h4>${dualLabel('Empregos publicos','Vinculos como servidor')}</h4>`;
        html += vinculos.map(v => {
            const admissao = _fmtDate(v.data_admissao);
            const ultimo = _fmtDate(v.ultimo_registro);
            const salario = v.maior_salario ? _shortBrl(v.maior_salario) : '-';
            const cargoRaw = v.descricao_cargo || '';
            const cargoStripped = _stripCodePrefix(cargoRaw) || '-';
            return `<div class="empresa-card">
                <div class="empresa-header">
                    <strong>${_esc(v.municipio)}</strong>
                    <span class="text-sm text-muted"><span class="citizen-only">${_esc(cargoStripped)}</span><span class="auditor-only">${_esc(cargoRaw || '-')}</span></span>
                </div>
                <div class="empresa-details">
                    <span>${dualLabel('Entrada:','Admissao:')} ${admissao}</span>
                    <span>${dualLabel('Ultimo registro:','Ultimo registro:')} ${ultimo}</span>
                    <span>${dualLabel('Maior salario:','Maior salario:')} ${salario}</span>
                </div>
            </div>`;
        }).join('');
        html += '</div>';
    }

    // Empresas vinculadas (with badges)
    if (cnpjs && cnpjs.length) {
        html += `<div class="dialog-section"><h4>${dualLabel('Empresas onde aparece como socio','Empresas vinculadas')}</h4>`;
        const empresaMap = {};
        for (const e of empresas) empresaMap[e.cnpj_basico] = e;
        html += cnpjs.map(c => {
            let badges = '';
            // Sancao badges
            const sanList = sancoes[c] || [];
            const vigentes = sanList.filter(s => !s.dt_final_sancao || s.dt_final_sancao >= new Date().toISOString().slice(0, 10));
            if (vigentes.length) {
                const hasInid = vigentes.some(s => /inidone/i.test(s.categoria_sancao || ''));
                if (hasInid) {
                    badges += '<span class="badge badge-red">Inidoneidade (bloqueio nacional)</span>';
                } else {
                    const abr = vigentes[0].abrangencia_sancao || '';
                    const orgao = vigentes[0].orgao_sancionador || '';
                    const scopeLabel = abr ? `${abr}` : (vigentes[0].esfera_orgao_sancionador || 'Restrita ao ente');
                    const tipos = [...new Set(vigentes.map(s => s.fonte))];
                    tipos.forEach(t => {
                        badges += `<span class="badge badge-orange">Sancionada - ${_esc(t)} (${_esc(scopeLabel)})</span>`;
                    });
                }
            }
            // PGFN badge
            const pgfnList = pgfn[c] || [];
            if (pgfnList.length) {
                const totalDiv = pgfnList.reduce((s, d) => s + (d.valor_consolidado || 0), 0);
                badges += `<span class="badge badge-orange">Divida PGFN ${_shortBrl(totalDiv)}</span>`;
            }
            // Acordo de Leniencia badge
            const acordoList = acordosMap[c] || [];
            if (acordoList.length) {
                const ativos = acordoList.filter(a => a.situacao_acordo !== 'Cumprido');
                if (ativos.length) badges += '<span class="badge badge-blue">Acordo de Leniencia ativo</span>';
                else badges += '<span class="badge badge-gray">Acordo de Leniencia (cumprido)</span>';
            }
            // Empenhos badge
            const emp = empMap[c];
            if (emp) {
                badges += `<span class="badge badge-yellow">Recebeu ${_shortBrl(emp.total_pago)} (${emp.qtd_empenhos} empenhos)</span>`;
            }
            return _renderEmpresaCard(empresaMap[c], c, badges);
        }).join('');
        html += '</div>';
    }

    // Bolsa Familia
    if (bf.length) {
        html += `<div class="dialog-section"><h4>${dualLabel('Recebeu Bolsa Familia','Bolsa Familia')}</h4>`;
        const ultimo = bf[0];
        const total = bf.reduce((s, b) => s + (b.valor_parcela || 0), 0);
        html += `<div class="empresa-card">
            <div class="empresa-header">
                <strong>${_esc(ultimo.nm_municipio || '-')}</strong>
                <span class="badge badge-yellow">Ultimo recebimento: ${_fmtDate(ultimo.mes_competencia)}</span>
            </div>
            <div class="empresa-details">
                <span>Valor ultima parcela: ${_shortBrl(ultimo.valor_parcela)}</span>
                <span>Ultimos ${bf.length} registros somam ${_shortBrl(total)}</span>
            </div>
        </div>`;
        html += '</div>';
    }

    // CEAF - Expulsoes da Administracao Federal
    if (data.ceaf && data.ceaf.length) {
        html += `<div class="dialog-section"><h4>${dualLabel('Expulsoes do servico publico federal','Expulsoes da Administracao Federal (CEAF)')}</h4>`;
        html += data.ceaf.map(c => {
            return `<div class="empresa-card" style="border-left: 3px solid var(--red)">
                <div class="empresa-header">
                    <strong>${_esc(c.categoria_sancao || 'Sancao')}</strong>
                    <span class="badge badge-red" title="CEAF - Cadastro de Expulsoes da Administracao Federal"><span class="citizen-only">Expulso do servico publico federal</span><span class="auditor-only">CEAF</span></span>
                </div>
                <div class="empresa-details">
                    ${c.cargo_efetivo ? `<span>${dualLabel('Cargo:','Cargo efetivo:')} ${_esc(_stripCodePrefix(c.cargo_efetivo))}</span>` : ''}
                    ${c.funcao_confianca ? `<span>${dualLabel('Funcao:','Funcao de confianca:')} ${_esc(c.funcao_confianca)}</span>` : ''}
                    ${c.orgao_lotacao ? `<span>${dualLabel('Onde trabalhava:','Orgao de lotacao:')} ${_esc(c.orgao_lotacao)}</span>` : ''}
                    ${c.orgao_sancionador ? `<span>${dualLabel('Quem puniu:','Sancionador:')} ${_esc(c.orgao_sancionador)}</span>` : ''}
                    ${c.dt_inicio_sancao ? `<span>${dualLabel('Desde:','Inicio:')} ${_fmtDate(c.dt_inicio_sancao)}</span>` : ''}
                    ${c.dt_final_sancao ? `<span>${dualLabel('Ate:','Fim:')} ${_fmtDate(c.dt_final_sancao)}</span>` : ''}
                    ${c.dt_transito_julgado ? `<span class="auditor-only">Transito em julgado: ${_fmtDate(c.dt_transito_julgado)}</span>` : ''}
                    ${c.fundamentacao_legal ? `<span class="auditor-only">Fund. legal: ${_esc(c.fundamentacao_legal)}</span>` : ''}
                    ${c.numero_processo ? `<span class="auditor-only">Processo: ${_esc(c.numero_processo)}</span>` : ''}
                </div>
            </div>`;
        }).join('');
        html += '</div>';
    }

    // Empenhos das empresas vinculadas durante o vinculo do servidor
    if (data.empenhos_durante_vinculo && data.empenhos_durante_vinculo.length) {
        const empVinc = data.empenhos_durante_vinculo;
        const totalVinc = empVinc.reduce((s, e) => s + (e.valor_pago || 0), 0);
        const empresasMap = {};
        for (const e of empVinc) {
            empresasMap[e.cnpj_basico] = (empresasMap[e.cnpj_basico] || 0) + (e.valor_pago || 0);
        }
        const empresasSorted = Object.entries(empresasMap).sort((a, b) => b[1] - a[1]);
        const empresaNames = {};
        for (const emp of (data.empresas || [])) {
            empresaNames[emp.cnpj_basico] = emp.razao_social || emp.cnpj_basico;
        }

        html += `<div class="dialog-section"><h4>${dualLabel('Pagamentos do governo as empresas enquanto era servidor','Empenhos recebidos pelas empresas durante vinculo')}</h4>`;
        html += `<p class="text-sm text-muted" style="margin-bottom:.5rem">Pagamentos realizados pelo municipio as empresas das quais o servidor e socio, durante o periodo em que manteve vinculo ativo.</p>`;

        // Summary by empresa
        html += '<div style="margin-bottom:.8rem">';
        html += empresasSorted.map(([cnpj, val]) => {
            const name = empresaNames[cnpj] || cnpj;
            return `<div class="empresa-card" style="border-left: 3px solid var(--red)">
                <div class="empresa-header">
                    <strong>${_esc(name)}</strong>
                    <span class="badge badge-red">${_shortBrl(val)}</span>
                </div>
                <div class="empresa-details">
                    <span class="auditor-only">CNPJ: ${cnpj.slice(0,2)}.${cnpj.slice(2,5)}.${cnpj.slice(5,8)}/****-**</span>
                    <span>${empVinc.filter(e => e.cnpj_basico === cnpj).length} empenhos durante vinculo</span>
                </div>
            </div>`;
        }).join('');
        html += '</div>';

        // Empenho table
        const empRows = empVinc.slice(0, 50).map(e => {
            const mod = e.modalidade_licitacao || '-';
            const numLic = e.numero_licitacao || '';
            const semLic = !numLic || numLic === '000000000' || (mod && mod.toLowerCase().includes('sem licit'));
            const modCell = semLic ? '<span class="badge badge-yellow">Sem licitacao</span>' : _esc(`${mod} (${numLic})`);
            return `<tr class="clickable-row" data-empenho-id="${e.id}">
                <td>${_fmtDate(e.data_empenho)}</td>
                <td>${_esc(e.elemento_despesa || '-')}</td>
                <td class="text-right">${_shortBrl(e.valor_pago)}</td>
                <td>${modCell}</td>
            </tr>`;
        }).join('');
        html += `<div class="tbl-wrap"><table class="dialog-table">
            <thead><tr><th>Data</th><th>Elemento</th><th class="text-right">Pago</th><th>Modalidade</th></tr></thead>
            <tbody>${empRows}</tbody>
        </table></div>`;
        if (empVinc.length >= 100) html += '<p class="text-sm text-muted">Mostrando os 100 empenhos mais recentes.</p>';
        html += `<p class="text-sm text-muted" style="margin-top:.5rem">Total durante vinculo: <strong>${_shortBrl(totalVinc)}</strong></p>`;
        html += '</div>';
    }

    if (!html || html === '<div class="stats-grid"></div>') html = '<p class="text-sm text-muted">Nenhum detalhe disponivel.</p>';
    body.innerHTML = html;
    _reattachDialogLinks(body);
}

async function openFornecedorDialog(cnpjBasico, fornecedorNome, municipioOverride, switchMun, nomeCredor, cpfCnpj) {
    const dialog = document.getElementById('empresa-dialog');
    if (!dialog) return;
    if (!switchMun) {
        if (dialog.open) { _dialogPush(); } else { _dialogReset(); }
    } else {
        _dialogPush();
    }
    const title = dialog.querySelector('.dialog-title');
    const body = dialog.querySelector('.dialog-body');
    title.textContent = fornecedorNome || 'Fornecedor';
    body.innerHTML = '<p class="text-sm text-muted">Carregando...</p>';
    if (!dialog.open) dialog.showModal();
    document.body.classList.add('dialog-open');

    const viewMunicipio = municipioOverride || _currentMunicipio;
    const data = await _fetchFornecedorDetails(cnpjBasico, viewMunicipio, nomeCredor, cpfCnpj);
    let html = '';

    // Pre-compute sanction date ranges (used by charts and empenho table)
    // grave = sancao legalmente afeta contratos com este municipio
    const normMun = (viewMunicipio || '').normalize('NFD').replace(/\p{Diacritic}/gu, '').toUpperCase();
    const sancaoRanges = (data.sancoes || []).map(s => {
        const cat = s.categoria_sancao || '';
        const abr = s.abrangencia_sancao || '';
        const esfera = (s.esfera_orgao_sancionador || '').toUpperCase();
        const orgao = (s.orgao_sancionador || '').normalize('NFD').replace(/\p{Diacritic}/gu, '').toUpperCase();
        const isInid = /inidone/i.test(cat);
        const isNacional = abr === 'Todas as Esferas em todos os Poderes';
        // Sancao emitida por este municipio e com abrangencia que bloqueia contratos com ele
        const isDoMunicipio = esfera === 'MUNICIPAL' && normMun && orgao.includes(normMun);
        const abrangeEmisor = isDoMunicipio && (
            abr === 'No órgão sancionador'
            || abr === 'Na Esfera e no Poder do órgão sancionador'
            || abr === 'Em todos os Poderes da Esfera do órgão sancionador'
        );
        return {
            inicio: s.dt_inicio_sancao ? new Date(s.dt_inicio_sancao) : null,
            fim: s.dt_final_sancao ? new Date(s.dt_final_sancao) : null,
            grave: isInid || isNacional || abrangeEmisor,
            categoria: cat,
            abrangencia: abr
        };
    }).filter(r => r.inicio);

    // Situacao cadastral
    if (data.estabelecimento) {
        const est = data.estabelecimento;
        const sit = _situacaoLabel(est.situacao_cadastral);
        const sitClass = String(est.situacao_cadastral) === '2' ? '' : 'badge badge-red';
        const cnpjFmt = _formatCnpj(cnpjBasico, est.cnpj_completo);
        const local = [est.municipio, est.uf].filter(Boolean).join(' - ') || '-';
        html += `<div class="dialog-section"><h4>${dualLabel('Dados da empresa','Dados cadastrais')}</h4>`;
        html += `<div class="empresa-card">
            <div class="empresa-header">
                <strong>${_esc(fornecedorNome)}</strong>
                <code class="auditor-only">${cnpjFmt}</code>
            </div>
            <div class="empresa-details">
                <span>${dualLabel('Cadastro:','Situacao:')} <span class="${sitClass}">${sit}</span></span>
                ${est.dt_situacao ? `<span class="auditor-only">Data situacao: ${_fmtDate(est.dt_situacao)}</span>` : ''}
                <span>Sede: ${_esc(local)}</span>
                ${est.cnae_principal ? `<span class="auditor-only">CNAE: ${_esc(est.cnae_principal)}</span>` : ''}
            </div>
        </div>`;
        html += '</div>';
    }

    // Summary stats
    if (data.stats && data.stats.qtd_empenhos > 0) {
        const st = data.stats;
        const pctSemLic = st.qtd_empenhos > 0
            ? ((st.qtd_sem_licitacao / st.qtd_empenhos) * 100).toFixed(1)
            : '0.0';
        const periodo = `${_fmtDate(st.primeiro_empenho)} a ${_fmtDate(st.ultimo_empenho)}`;

        html += `<div class="dialog-section"><h4>${dualLabel('Quanto esta empresa recebeu desta cidade','Resumo de pagamentos neste municipio')}</h4>`;
        html += `<div class="stats-grid">
            <div class="stat-cell">
                <span class="stat-value">${_shortBrl(st.total_pago)}</span>
                <span class="stat-label">${dualLabel('Dinheiro ja entregue','Total pago')}</span>
            </div>
            <div class="stat-cell">
                <span class="stat-value">${_shortBrl(st.total_empenhado)}</span>
                <span class="stat-label">${dualLabel('Reservado no orcamento','Total empenhado')}</span>
            </div>
            <div class="stat-cell">
                <span class="stat-value">${st.qtd_empenhos}</span>
                <span class="stat-label">${dualLabel('Qtd pagamentos','Empenhos')}</span>
            </div>
            <div class="stat-cell">
                <span class="stat-value ${parseFloat(pctSemLic) >= 50 ? 'color-red' : ''}">${pctSemLic}%</span>
                <span class="stat-label">${dualLabel('Sem concorrencia','Sem licitacao')}</span>
            </div>
        </div>`;
        html += `<p class="text-sm text-muted" style="margin-top:.4rem">Periodo: ${periodo}</p>`;

        const hasCharts = (data.monthly && data.monthly.length > 1) || (data.top_elementos && data.top_elementos.length);
        if (hasCharts) html += '<div class="charts-grid">';

        // Mini bar chart - monthly payments
        if (data.monthly && data.monthly.length > 1) {
            const maxVal = Math.max(...data.monthly.map(m => m.total_mes));
            html += '<div>';
            html += '<p class="text-sm text-muted" style="margin-bottom:.2rem">Pagamentos mensais</p>';
            html += '<div class="mini-chart">';
            html += data.monthly.map(m => {
                const pct = maxVal > 0 ? (m.total_mes / maxVal * 100) : 0;
                const [yy, mm] = m.mes.split('-');
                const label = `${mm}/${yy.slice(2)}`;
                // Check if month overlaps with any sanction period
                const monthStart = new Date(m.mes + '-01');
                const monthEnd = new Date(monthStart); monthEnd.setMonth(monthEnd.getMonth() + 1); monthEnd.setDate(0);
                const inSancao = sancaoRanges.find(r =>
                    r.grave && r.inicio <= monthEnd && (!r.fim || r.fim >= monthStart)
                );
                const barClass = inSancao ? 'mini-bar bar-sancao' : 'mini-bar';
                return `<div class="mini-bar-col">
                    <span class="mini-bar-tip">${_shortBrl(m.total_mes)}</span>
                    <div class="${barClass}" style="height:${Math.max(pct, 3)}%"></div>
                    <span class="mini-bar-label">${label}</span>
                </div>`;
            }).join('');
            html += '</div></div>';
        }

        // Top elementos de despesa
        if (data.top_elementos && data.top_elementos.length) {
            const topMax = data.top_elementos[0].total_elemento;
            const totalGeral = data.top_elementos.reduce((s, el) => s + el.total_elemento, 0);
            html += '<div>';
            html += '<p class="text-sm text-muted" style="margin-bottom:.2rem">Principais elementos de despesa</p>';
            html += '<div class="top-elementos">';
            html += data.top_elementos.map(el => {
                const pct = topMax > 0 ? (el.total_elemento / topMax * 100) : 0;
                const pctTotal = totalGeral > 0 ? ((el.total_elemento / totalGeral) * 100).toFixed(0) : 0;
                return `<div class="top-el-row">
                    <span class="top-el-name">${_esc(el.elemento_despesa || '-')}</span>
                    <div class="top-el-track"><div class="top-el-fill" style="width:${pct}%"></div><span class="top-el-pct">${pctTotal}%</span></div>
                    <span class="top-el-value">${_shortBrl(el.total_elemento)}</span>
                </div>`;
            }).join('');
            html += '</div></div>';
        }

        if (hasCharts) html += '</div>';

        html += '</div>';
    }

    // Sancoes (CEIS + CNEP)
    if (data.sancoes && data.sancoes.length) {
        const sanCnpj = (data.sancoes[0].cpf_cnpj_sancionado || '').replace(/\D/g, '');
        const sanUrl = `https://portaldatransparencia.gov.br/sancoes/consulta?paginacaoSimples=true&tamanhoPagina=&offset=&direcaoOrdenacao=asc&cpfCnpj=${sanCnpj}&colunasSelecionadas=linkDetalhamento%2Ccadastro%2CcpfCnpj%2CnomeSancionado%2CufSancionado%2Corgao%2CcategoriaSancao%2CdataPublicacao%2CvalorMulta%2Cquantidade`;
        html += `<div class="dialog-section"><h4>${dualLabel('Punicoes','Sancoes')} ${sanCnpj ? `<a href="${sanUrl}" target="_blank" rel="noopener" class="ext-link-inline" title="Ver no Portal da Transparencia">&#8599;</a>` : ''}</h4>`;
        html += data.sancoes.map(s => {
            const inicio = _fmtDate(s.dt_inicio_sancao);
            const fim = s.dt_final_sancao ? _fmtDate(s.dt_final_sancao) : 'Sem prazo definido';
            const vigente = !s.dt_final_sancao || new Date(s.dt_final_sancao) >= new Date();
            const origem = s.origem || 'CEIS';
            const multa = s.valor_multa ? `<span>Multa: ${_shortBrl(s.valor_multa)}</span>` : '';
            const categoria = s.categoria_sancao || 'Sancao';
            const isInid = /inidone/i.test(categoria);
            const abrang = s.abrangencia_sancao || '';
            const isNacional = isInid || abrang === 'Todas as Esferas em todos os Poderes';
            const abrangenciaLabel = isInid
                ? 'Nacional (Inidoneidade)'
                : abrang === 'Todas as Esferas em todos os Poderes'
                    ? 'Nacional'
                    : abrang
                        ? `${abrang} (${_esc(s.orgao_sancionador || '?')})`
                        : `${_esc(s.esfera_orgao_sancionador || 'Restrita ao ente')}`;
            const abrangencia = isNacional
                ? `<span class="badge badge-red">${_esc(abrangenciaLabel)}</span>`
                : `<span class="badge badge-orange">${_esc(abrangenciaLabel)}</span>`;
            return `<div class="empresa-card">
                <div class="empresa-header">
                    <strong>${_esc(categoria)}</strong>
                    <span>
                        <span class="badge ${origem === 'CNEP' ? 'badge-orange' : (isInid ? 'badge-red' : 'badge-orange')}">${origem}</span>
                        <span class="badge ${vigente ? 'badge-red' : 'badge-gray'}">${vigente ? 'Vigente' : 'Expirada'}</span>
                        ${abrangencia}
                    </span>
                </div>
                <div class="empresa-details">
                    <span>Inicio: ${inicio}</span>
                    <span>Fim: ${fim}</span>
                    ${s.orgao_sancionador ? `<span>Orgao: ${_esc(s.orgao_sancionador)}</span>` : ''}
                    ${s.fundamentacao_legal ? `<span>Base legal: ${_esc(s.fundamentacao_legal)}</span>` : ''}
                    ${multa}
                </div>
            </div>`;
        }).join('');
        html += `<div class="disclaimer-box" style="margin-top:.8rem">
            <p class="text-sm"><strong>O que sao essas sancoes?</strong></p>
            <p class="text-sm" style="margin-top:.3rem"><strong>CEIS</strong> (Cadastro de Empresas Inidoneas e Suspensas): lista mantida pelo governo federal com empresas impedidas ou inidoneas.</p>
            <p class="text-sm" style="margin-top:.3rem">&#8226; <strong>Declaracao de Inidoneidade</strong> (Art. 156, IV — Lei 14.133): bloqueio <strong>nacional</strong> — proibe contratacao com qualquer orgao em qualquer esfera.</p>
            <p class="text-sm" style="margin-top:.3rem">&#8226; <strong>Impedimento de Licitar</strong> (Art. 156, III — Lei 14.133): bloqueio <strong>restrito ao ente federativo</strong> que aplicou a sancao. Outros entes podem contratar legalmente.</p>
            <p class="text-sm" style="margin-top:.3rem"><strong>CNEP</strong> (Cadastro Nacional de Empresas Punidas): registra empresas punidas com base na Lei Anticorrupcao (Lei 12.846/2013). Sancoes incluem multa, publicacao extraordinaria e proibicao de incentivos publicos.</p>
        </div>`;
        html += '</div>';
    }

    // Divida PGFN
    if (data.pgfn && data.pgfn.length) {
        html += `<div class="dialog-section"><h4>${dualLabel('Impostos federais em atraso','Divida ativa (PGFN)')} <a href="https://www.listadevedores.pgfn.gov.br/" target="_blank" rel="noopener" class="ext-link-inline" title="Consultar na Lista de Devedores">&#8599;</a></h4>`;
        html += data.pgfn.map(d => {
            const ajuizado = d.indicador_ajuizado === 'S' || d.indicador_ajuizado === 'Sim';
            return `<div class="empresa-card">
                <div class="empresa-header">
                    <strong>${_esc(d.receita_principal || d.situacao_inscricao || 'Inscricao')}</strong>
                    <span class="badge badge-yellow">${_shortBrl(d.valor_consolidado)}</span>
                </div>
                <div class="empresa-details">
                    <span class="auditor-only">Situacao: ${_esc(d.situacao_inscricao || '-')}</span>
                    ${d.numero_inscricao ? `<span class="auditor-only">Inscricao: ${_esc(d.numero_inscricao)}</span>` : ''}
                    ${d.dt_inscricao ? `<span>${dualLabel('Desde:','Data:')} ${_fmtDate(d.dt_inscricao)}</span>` : ''}
                    ${ajuizado ? '<span class="badge badge-gray auditor-only">Ajuizado</span>' : ''}
                </div>
            </div>`;
        }).join('');
        html += `<a href="https://www.listadevedores.pgfn.gov.br/" target="_blank" rel="noopener" class="ext-link text-sm">Consultar na Lista de Devedores &#8599;</a>`;
        html += '</div>';
    }

    // Acordos de Leniencia
    if (data.acordos_leniencia && data.acordos_leniencia.length) {
        html += `<div class="dialog-section"><h4>${dualLabel('Acordos de colaboracao (Lei Anticorrupcao)','Acordos de Leniencia')}</h4>`;
        html += data.acordos_leniencia.map(a => {
            const status = a.situacao_acordo || 'Desconhecido';
            const statusBadge = status === 'Cumprido'
                ? '<span class="badge badge-green">Cumprido</span>'
                : '<span class="badge badge-blue">Em Execucao</span>';
            const efeitos = (a.efeitos || []).map(e =>
                `<li><strong>${_esc(e.efeito)}</strong>${e.complemento ? ': ' + _esc(e.complemento).slice(0, 150) : ''}</li>`
            ).join('');
            return `<div class="empresa-card" style="border-left: 3px solid #3b82f6">
                <div class="empresa-header">
                    <strong>Acordo de Leniencia</strong> ${statusBadge}
                </div>
                <div class="empresa-details">
                    ${a.orgao_sancionador ? `<span>Orgao: ${_esc(a.orgao_sancionador)}</span>` : ''}
                    ${a.dt_inicio_acordo ? `<span>Inicio: ${_fmtDate(a.dt_inicio_acordo)}</span>` : ''}
                    <span>Fim: ${a.dt_fim_acordo ? _fmtDate(a.dt_fim_acordo) : 'Em aberto'}</span>
                    ${a.numero_processo ? `<span>Processo: ${_esc(a.numero_processo)}</span>` : ''}
                </div>
                ${efeitos ? '<div style="margin-top:0.5rem"><strong style="font-size:0.82rem">Efeitos:</strong><ul style="margin:0.25rem 0 0 1rem;font-size:0.82rem">' + efeitos + '</ul></div>' : ''}
            </div>`;
        }).join('');
        html += '<p class="text-sm text-muted" style="margin-top:0.5rem">Acordos de Leniencia (Lei 12.846/13) nao impedem a empresa de contratar com o poder publico. Sao informacoes de transparencia.</p>';
        html += '</div>';
    }

    // Empenhos recentes
    if (data.empenhos && data.empenhos.length) {
        // Municipality selector
        const munOptions = (data.municipios_ativos || []);
        let munSelect = '';
        if (munOptions.length > 1) {
            const opts = munOptions.map(m => {
                const sel = m.municipio === viewMunicipio ? ' selected' : '';
                return `<option value="${_esc(m.municipio)}"${sel}>${_esc(m.municipio)} (${_shortBrl(m.total_pago)})</option>`;
            }).join('');
            munSelect = `<select class="mun-selector" data-forn-cnpj="${_esc(cnpjBasico)}" data-forn-nome="${_esc(fornecedorNome)}" data-forn-nome-credor="${_esc(nomeCredor || '')}" data-forn-cpf-cnpj="${_esc(cpfCnpj || '')}">${opts}</select>`;
        }

        html += `<div class="dialog-section" id="forn-empenhos"><h4>${dualLabel('Pagamentos recentes','Empenhos recentes')} ${munSelect ? 'em' : 'neste municipio'} ${munSelect}</h4>`;
        html += _buildEmpenhoTable(data.empenhos, sancaoRanges);
        if (data.empenhos.length >= 50) {
            html += '<p class="text-sm text-muted">Mostrando os 50 empenhos mais recentes.</p>';
        }
        html += '</div>';
    }

    // Empenhos durante sancao em outros municipios
    if (data.empenhos_sancao_outros && data.empenhos_sancao_outros.length) {
        const totalOutros = data.empenhos_sancao_outros.reduce((s, m) => s + m.total_pago, 0);
        html += `<div class="dialog-section"><h4>${dualLabel('Recebeu pagamento em outras cidades mesmo estando punida','Pagamentos durante sancao em outros municipios')}</h4>`;
        html += `<p class="text-sm text-muted" style="margin-bottom:.5rem">Total: ${_shortBrl(totalOutros)} em ${data.empenhos_sancao_outros.length} municipio(s)</p>`;
        const outrosRows = data.empenhos_sancao_outros.map(m =>
            `<tr class="row-sancao clickable-row" data-switch-mun="${_esc(m.municipio)}" data-forn-cnpj="${_esc(cnpjBasico)}" data-forn-nome="${_esc(fornecedorNome)}" data-forn-nome-credor="${_esc(nomeCredor || '')}" data-forn-cpf-cnpj="${_esc(cpfCnpj || '')}">
                <td>${_esc(m.municipio)}</td>
                <td class="text-right">${m.qtd_empenhos}</td>
                <td class="text-right">${_shortBrl(m.total_pago)}</td>
            </tr>`
        ).join('');
        html += `<div class="tbl-wrap"><table class="dialog-table">
            <thead><tr><th>Municipio</th><th class="text-right">Empenhos</th><th class="text-right">Total pago</th></tr></thead>
            <tbody>${outrosRows}</tbody>
        </table></div>`;
        html += '</div>';
    }

    if (!html) html = '<p class="text-sm text-muted">Nenhum detalhe disponivel para este fornecedor.</p>';
    body.innerHTML = html;
    _reattachDialogLinks(body);
    if (switchMun) {
        const empSection = body.querySelector('#forn-empenhos');
        if (empSection) empSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

async function openHeatmapMonthDialog(municipio, ano, mes) {
    const dialog = document.getElementById('empresa-dialog');
    if (!dialog) return;
    if (dialog.open) { _dialogPush(); } else { _dialogReset(); }
    const title = dialog.querySelector('.dialog-title');
    const body = dialog.querySelector('.dialog-body');
    const mesesLabel = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'];
    const mesNome = mesesLabel[mes - 1] || mes;
    title.textContent = `${mesNome}/${ano} — ${municipio}`;
    body.innerHTML = '<p class="text-sm text-muted">Carregando...</p>';
    if (!dialog.open) dialog.showModal();
    document.body.classList.add('dialog-open');

    let data;
    try {
        const resp = await fetch(`/api/heatmap/${encodeURIComponent(municipio)}/${ano}/${mes}`);
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        data = await resp.json();
    } catch (err) {
        body.innerHTML = `<p class="text-sm text-muted">Erro ao carregar: ${_esc(err.message || String(err))}</p>`;
        return;
    }

    const resumo = data.resumo || {};
    const fornecedores = data.fornecedores || [];
    const elementos = data.elementos || [];
    const funcoes = data.funcoes || [];
    const modalidades = data.modalidades || [];
    const empenhos = data.empenhos || [];
    let html = '';

    html += '<div class="dialog-section"><h4>Resumo do mes</h4>';
    html += '<div class="stats-grid">';
    html += `<div class="stat"><div class="stat-label">${dualLabel('Reservado','Total empenhado')}</div><div class="stat-value">${_shortBrl(Number(resumo.total_empenhado || 0))}</div></div>`;
    html += `<div class="stat"><div class="stat-label">${dualLabel('Pago','Total pago')}</div><div class="stat-value">${_shortBrl(Number(resumo.total_pago || 0))}</div></div>`;
    html += `<div class="stat"><div class="stat-label">${dualLabel('Qtd pagamentos','Empenhos')}</div><div class="stat-value">${Number(resumo.qtd_empenhos || 0).toLocaleString('pt-BR')}</div></div>`;
    html += `<div class="stat"><div class="stat-label">Fornecedores</div><div class="stat-value">${Number(resumo.qtd_fornecedores || 0).toLocaleString('pt-BR')}</div></div>`;
    html += '</div></div>';

    if (fornecedores.length) {
        html += `<div class="dialog-section"><h4>${dualLabel('Quem mais recebeu','Top fornecedores')}</h4>`;
        html += `<div class="tbl-wrap"><table class="data-table stack-mobile"><thead><tr><th>${dualLabel('Empresa','Fornecedor')}</th><th class="auditor-only">CPF/CNPJ</th><th class="num auditor-only">Empenhos</th><th class="num">${dualLabel('Reservado','Empenhado')}</th><th class="num">Pago</th></tr></thead><tbody>`;
        for (const f of fornecedores) {
            const nome = _esc(f.nome_credor || '-');
            const doc = _esc(f.cpf_cnpj || '-');
            const isPJ = f.eh_pj && f.cpf_cnpj && f.cpf_cnpj.length === 14;
            const nomeCell = isPJ
                ? `<a href="#" class="dialog-link" data-forn-cnpj="${f.cpf_cnpj.substring(0, 8)}" data-forn-nome="${nome}" data-forn-nome-credor="${nome}" data-forn-cpf-cnpj="${_esc(f.cpf_cnpj)}">${nome}</a>`
                : nome;
            html += `<tr>`
                + `<td data-label="Empresa" class="stack-title">${nomeCell}</td>`
                + `<td class="auditor-only" data-label="CPF/CNPJ"><code>${doc}</code></td>`
                + `<td class="num auditor-only" data-label="Empenhos">${Number(f.qtd_empenhos || 0).toLocaleString('pt-BR')}</td>`
                + `<td class="num" data-label="${_lbl('Reservado','Empenhado')}">${_shortBrl(Number(f.total_empenhado || 0))}</td>`
                + `<td class="num" data-label="Pago">${_shortBrl(Number(f.total_pago || 0))}</td>`
                + `</tr>`;
        }
        html += '</tbody></table></div></div>';
    }

    if (elementos.length) {
        html += `<div class="dialog-section"><h4>${dualLabel('Em que a cidade gastou','Top elementos de despesa')}</h4>`;
        html += `<div class="tbl-wrap"><table class="data-table"><thead><tr><th>${dualLabel('Tipo de gasto','Elemento')}</th><th class="num auditor-only">Empenhos</th><th class="num">${dualLabel('Reservado','Empenhado')}</th><th class="num">Pago</th></tr></thead><tbody>`;
        for (const e of elementos) {
            const elemRaw = e.elemento_despesa || '-';
            const elemCell = `<span class="citizen-only">${_esc(_stripCodePrefix(elemRaw))}</span><span class="auditor-only">${_esc(elemRaw)}</span>`;
            html += `<tr><td>${elemCell}</td><td class="num auditor-only">${Number(e.qtd_empenhos || 0).toLocaleString('pt-BR')}</td><td class="num">${_shortBrl(Number(e.total_empenhado || 0))}</td><td class="num">${_shortBrl(Number(e.total_pago || 0))}</td></tr>`;
        }
        html += '</tbody></table></div></div>';
    }

    if (funcoes.length) {
        html += `<div class="dialog-section"><h4>${dualLabel('Areas do governo que gastaram','Funcao / Programa')}</h4>`;
        html += `<div class="tbl-wrap"><table class="data-table"><thead><tr><th>${dualLabel('Area','Funcao')}</th><th>Programa</th><th class="num auditor-only">Empenhos</th><th class="num">${dualLabel('Reservado','Empenhado')}</th><th class="num">Pago</th></tr></thead><tbody>`;
        for (const fu of funcoes) {
            const funcaoRaw = fu.funcao || '-';
            const progRaw = fu.programa || '-';
            const funcaoCell = `<span class="citizen-only">${_esc(_stripCodePrefix(funcaoRaw))}</span><span class="auditor-only">${_esc(funcaoRaw)}</span>`;
            const progCell = `<span class="citizen-only">${_esc(_stripCodePrefix(progRaw))}</span><span class="auditor-only">${_esc(progRaw)}</span>`;
            html += `<tr><td>${funcaoCell}</td><td>${progCell}</td><td class="num auditor-only">${Number(fu.qtd_empenhos || 0).toLocaleString('pt-BR')}</td><td class="num">${_shortBrl(Number(fu.total_empenhado || 0))}</td><td class="num">${_shortBrl(Number(fu.total_pago || 0))}</td></tr>`;
        }
        html += '</tbody></table></div></div>';
    }

    if (modalidades.length) {
        html += `<div class="dialog-section"><h4>${dualLabel('Como foi contratado','Modalidade de licitacao')}</h4>`;
        html += `<div class="tbl-wrap"><table class="data-table"><thead><tr><th>${dualLabel('Tipo de licitacao','Modalidade')}</th><th class="num auditor-only">Empenhos</th><th class="num">Licitacoes</th><th class="num">${dualLabel('Reservado','Empenhado')}</th></tr></thead><tbody>`;
        for (const m of modalidades) {
            html += `<tr><td>${_esc(m.modalidade || '-')}</td><td class="num auditor-only">${Number(m.qtd_empenhos || 0).toLocaleString('pt-BR')}</td><td class="num">${Number(m.qtd_licitacoes || 0).toLocaleString('pt-BR')}</td><td class="num">${_shortBrl(Number(m.total_empenhado || 0))}</td></tr>`;
        }
        html += '</tbody></table></div></div>';
    }

    if (empenhos.length) {
        html += `<div class="dialog-section"><h4>${dualLabel('Maiores pagamentos do mes','Empenhos do mes (top ' + empenhos.length + ' por valor)')}</h4>`;
        html += `<div class="tbl-wrap"><table class="data-table stack-mobile"><thead><tr><th class="auditor-only">Nº</th><th>Data</th><th>${dualLabel('Empresa','Credor')}</th><th>${dualLabel('Tipo de gasto','Elemento')}</th><th class="auditor-only">Funcao</th><th class="num">${dualLabel('Reservado','Empenhado')}</th><th class="num">Pago</th></tr></thead><tbody>`;
        for (const e of empenhos) {
            const dt = e.data_empenho ? _fmtDate(e.data_empenho) : '-';
            const historico = _esc(e.historico_resumo || '');
            const elemRaw = e.elemento_despesa || '-';
            const elemCitizen = _stripCodePrefix(elemRaw) || elemRaw;
            const elemCell = `<span class="citizen-only">${_esc(elemCitizen)}</span><span class="auditor-only">${_esc(elemRaw)}</span>`;
            html += `<tr class="clickable-row" data-empenho-id="${e.id}" title="${historico}">`
                + `<td class="auditor-only" data-label="Nº"><code>${_esc(e.numero_empenho || '-')}</code></td>`
                + `<td data-label="Data" class="stack-meta">${dt}</td>`
                + `<td data-label="${_lbl('Empresa','Credor')}" class="stack-title">${_esc(e.nome_credor || '-')}</td>`
                + `<td data-label="${_lbl('Tipo de gasto','Elemento')}" class="stack-meta">${elemCell}</td>`
                + `<td class="auditor-only" data-label="Funcao">${_esc(e.funcao || '-')}</td>`
                + `<td class="num" data-label="${_lbl('Reservado','Empenhado')}">${_shortBrl(Number(e.valor_empenhado || 0))}</td>`
                + `<td class="num" data-label="Pago">${_shortBrl(Number(e.valor_pago || 0))}</td>`
                + `</tr>`;
        }
        html += '</tbody></table></div>';
        html += '<p class="text-sm text-muted" style="margin-top:.5rem">Clique em uma linha para ver os detalhes do empenho.</p>';
        html += '</div>';
    }

    if (!fornecedores.length && !elementos.length && !empenhos.length) {
        html += '<p class="text-sm text-muted">Sem detalhes disponiveis para este mes.</p>';
    }

    body.innerHTML = html;
    _reattachDialogLinks(body);
}

async function openEmpenhoDialog(empenhoId) {
    const dialog = document.getElementById('empresa-dialog');
    if (!dialog) return;
    if (dialog.open) { _dialogPush(); } else { _dialogReset(); }
    const title = dialog.querySelector('.dialog-title');
    const body = dialog.querySelector('.dialog-body');
    title.textContent = 'Detalhes do empenho';
    body.innerHTML = '<p class="text-sm text-muted">Carregando...</p>';
    if (!dialog.open) dialog.showModal();
    document.body.classList.add('dialog-open');

    const data = await _cachedPost('/api/empenho/detalhes', `emp:${empenhoId}`, { id: parseInt(empenhoId) });
    if (!data || !data.numero_empenho) {
        body.innerHTML = '<p class="text-sm text-muted">Empenho nao encontrado.</p>';
        return;
    }

    title.textContent = `Empenho ${data.numero_empenho}`;
    let html = '';

    // Historico (descricao detalhada)
    if (data.historico) {
        html += '<div class="dialog-section"><h4>Descricao</h4>';
        html += `<p class="text-sm" style="line-height:1.6">${_esc(data.historico)}</p>`;
        html += '</div>';
    }

    // Valores
    html += '<div class="dialog-section"><h4>Valores</h4>';
    html += `<div class="stats-grid" style="grid-template-columns:repeat(3,1fr)">
        <div class="stat-cell">
            <span class="stat-value">${_shortBrl(data.valor_empenhado)}</span>
            <span class="stat-label">${dualLabel('Reservado','Empenhado')}</span>
        </div>
        <div class="stat-cell">
            <span class="stat-value">${_shortBrl(data.valor_liquidado)}</span>
            <span class="stat-label">${dualLabel('Servico entregue','Liquidado')}</span>
        </div>
        <div class="stat-cell">
            <span class="stat-value">${_shortBrl(data.valor_pago)}</span>
            <span class="stat-label">${dualLabel('Dinheiro saiu','Pago')}</span>
        </div>
    </div>`;
    html += '</div>';

    // Credor
    html += `<div class="dialog-section"><h4>${dualLabel('Quem recebeu','Credor')}</h4>`;
    const cnpjRaw = String(data.cpf_cnpj || '').replace(/\D/g, '');
    const cnpjB = cnpjRaw.slice(0, 8);
    const isClickable = cnpjB.length === 8 && /^\d{8}$/.test(cnpjB) && cnpjRaw.length >= 14;
    const credorNome = _esc(data.nome_credor || '-');
    const credorLink = isClickable
        ? `<a href="#" class="dialog-link" data-forn-cnpj="${cnpjB}" data-forn-cpf-cnpj="${cnpjRaw}" data-forn-nome="${credorNome}" data-forn-nome-credor="${credorNome}">${credorNome}</a>`
        : credorNome;
    html += `<div class="empresa-card"><div class="empresa-header">
        <strong>${credorLink}</strong>
        <code>${_esc(data.cpf_cnpj || '-')}</code>
    </div></div>`;
    html += '</div>';

    // Classificacao orcamentaria
    html += `<div class="dialog-section"><h4>${dualLabel('Em que foi gasto','Classificacao orcamentaria')}</h4>`;
    html += '<div class="empresa-card"><div class="empresa-details">';
    if (data.funcao) html += `<span><strong>${dualLabel('Area:','Funcao:')}</strong> ${_esc(data.funcao)}</span>`;
    if (data.subfuncao) html += `<span class="auditor-only"><strong>Subfuncao:</strong> ${_esc(data.subfuncao)}</span>`;
    if (data.programa) html += `<span><strong>Programa:</strong> ${_esc(data.programa)}</span>`;
    if (data.acao) html += `<span class="auditor-only"><strong>Acao:</strong> ${_esc(data.acao)}</span>`;
    if (data.elemento_despesa) html += `<span><strong>${dualLabel('Tipo de gasto:','Elemento:')}</strong> ${_esc(data.elemento_despesa)}</span>`;
    if (data.categoria_economica) html += `<span class="auditor-only"><strong>Categoria:</strong> ${_esc(data.categoria_economica)}</span>`;
    if (data.grupo_natureza_despesa) html += `<span class="auditor-only"><strong>Natureza:</strong> ${_esc(data.grupo_natureza_despesa)}</span>`;
    if (data.modalidade_aplicacao) html += `<span class="auditor-only"><strong>Aplicacao:</strong> ${_esc(data.modalidade_aplicacao)}</span>`;
    html += '</div></div>';
    html += '</div>';

    // Origem / UG / fonte
    html += `<div class="dialog-section"><h4>${dualLabel('De onde veio o dinheiro','Origem')}</h4>`;
    html += '<div class="empresa-card"><div class="empresa-details">';
    html += `<span><strong>Data:</strong> ${_fmtDate(data.data_empenho)}</span>`;
    if (data.descricao_ug) html += `<span><strong>${dualLabel('Setor:','UG:')}</strong> ${_esc(data.descricao_ug)}</span>`;
    if (data.descricao_unidade_orcamentaria) html += `<span><strong>Unidade:</strong> ${_esc(data.descricao_unidade_orcamentaria)}</span>`;
    if (data.descricao_fonte_recurso) html += `<span><strong>${dualLabel('Origem do recurso:','Fonte:')}</strong> ${_esc(data.descricao_fonte_recurso)}</span>`;
    if (data.municipio) html += `<span><strong>Municipio:</strong> ${_esc(data.municipio)}</span>`;
    html += '</div></div>';

    // Licitacao vinculada
    const mod = data.modalidade_licitacao || '';
    const numLic = data.numero_licitacao || '';
    const semLic = !numLic || numLic === '000000000' || mod.toLowerCase().includes('sem licit');
    if (!semLic) {
        html += `<p class="text-sm mt-2"><strong>Licitacao:</strong> <a href="#" class="dialog-link" data-lic-num="${_esc(numLic)}" data-lic-ano="0">${_esc(mod)} (${_esc(numLic)})</a></p>`;
    } else {
        html += '<p class="text-sm mt-2"><strong>Licitacao:</strong> <span class="badge badge-yellow">Sem licitacao</span></p>';
    }
    html += '</div>';

    body.innerHTML = html;
    _reattachDialogLinks(body);
}

function _fetchLicitacaoDetails(numeroLicitacao, anoLicitacao, municipio, modalidade) {
    return _cachedPost('/api/licitacao/detalhes', `lic:${numeroLicitacao}:${anoLicitacao}:${municipio}:${modalidade}`,
        { numero_licitacao: numeroLicitacao, ano_licitacao: parseInt(anoLicitacao) || 0, municipio, modalidade: modalidade || '' });
}

async function openLicitacaoDialog(numeroLicitacao, anoLicitacao, municipio, label, modalidade) {
    const dialog = document.getElementById('empresa-dialog');
    if (!dialog) return;
    if (dialog.open) { _dialogPush(); } else { _dialogReset(); }
    const title = dialog.querySelector('.dialog-title');
    const body = dialog.querySelector('.dialog-body');
    title.textContent = label || `Licitacao ${numeroLicitacao}`;
    body.innerHTML = '<p class="text-sm text-muted">Carregando...</p>';
    if (!dialog.open) dialog.showModal();
    document.body.classList.add('dialog-open');

    const data = await _fetchLicitacaoDetails(numeroLicitacao, anoLicitacao, municipio, modalidade);
    let html = '';

    // Metadata — always render header
    const _licNumLabel = `N. ${_esc(numeroLicitacao)}${anoLicitacao && anoLicitacao !== '0' ? ` / ${anoLicitacao}` : ''}`;
    html += `<div class="dialog-section"><h4>${dualLabel('Dados desta licitacao','Dados da licitacao')}</h4>`;
    if (data.licitacao) {
        const lic = data.licitacao;
        html += `<div class="empresa-card">
            <div class="empresa-header">
                <strong>${_esc(lic.modalidade || 'Licitacao')}</strong>
                <span class="text-sm text-muted">${_licNumLabel}</span>
            </div>
            <div class="empresa-details">
                ${lic.objeto_licitacao ? `<span>Objeto: ${_esc(lic.objeto_licitacao)}</span>` : ''}
                ${lic.descricao_ug ? `<span>UG: ${_esc(lic.descricao_ug)}</span>` : ''}
                ${lic.data_homologacao ? `<span>Homologacao: ${_fmtDate(lic.data_homologacao)}</span>` : ''}
            </div>
        </div>`;
    } else {
        html += `<div class="empresa-card empresa-missing">
            <div class="empresa-header">
                <strong>Licitacao</strong>
                <span class="text-sm text-muted">${_licNumLabel}</span>
            </div>
            <div class="empresa-details">
                <span>Dados cadastrais indisponiveis no TCE-PB para esta licitacao.</span>
            </div>
        </div>`;
    }
    html += '</div>';

    // Proponentes
    if (data.proponentes && data.proponentes.length) {
        html += `<div class="dialog-section"><h4>${dualLabel('Empresas que participaram','Proponentes')}</h4>`;
        const propRows = data.proponentes.map(p => {
            const cnpjRaw = String(p.cpf_cnpj_proponente || '').replace(/\D/g, '');
            const cnpjB = cnpjRaw.slice(0, 8);
            const isClickable = cnpjB.length === 8 && /^\d{8}$/.test(cnpjB) && cnpjRaw.length >= 14;
            const nome = _esc(p.razao_social || p.nome_proponente || '-');
            const nomeLink = isClickable
                ? `<a href="#" class="dialog-link" data-forn-cnpj="${cnpjB}" data-forn-cpf-cnpj="${cnpjRaw}" data-forn-nome="${nome}" data-forn-nome-credor="${_esc(p.nome_proponente || '')}">${nome}</a>`
                : nome;
            return `<tr>
                <td>${nomeLink}</td>
                <td class="auditor-only"><code class="text-sm">${_esc(p.cpf_cnpj_proponente || '-')}</code></td>
                <td class="text-right">${_shortBrl(p.valor_ofertado)}</td>
                <td>${_esc(p.situacao_proposta || '-')}</td>
            </tr>`;
        }).join('');
        html += `<div class="tbl-wrap"><table class="dialog-table">
            <thead><tr><th>${dualLabel('Empresa','Proponente')}</th><th class="auditor-only">CNPJ/CPF</th><th class="text-right">${dualLabel('Valor proposto','Valor ofertado')}</th><th>${dualLabel('Resultado','Situacao')}</th></tr></thead>
            <tbody>${propRows}</tbody>
        </table></div>`;
        html += '</div>';
    }

    // Despesas vinculadas
    if (data.despesas && data.despesas.length) {
        html += `<div class="dialog-section"><h4>${dualLabel('Pagamentos desta licitacao','Despesas vinculadas')}</h4>`;
        const despRows = data.despesas.map(d => {
            const cnpjRaw = String(d.cpf_cnpj || '').replace(/\D/g, '');
            const cnpjB = cnpjRaw.slice(0, 8);
            const isClickable = cnpjB.length === 8 && /^\d{8}$/.test(cnpjB) && cnpjRaw.length >= 14;
            const nome = _esc(d.nome_credor || '-');
            const nomeCell = isClickable
                ? `<a href="#" class="dialog-link" data-forn-cnpj="${cnpjB}" data-forn-cpf-cnpj="${cnpjRaw}" data-forn-nome="${nome}" data-forn-nome-credor="${nome}">${nome}</a>`
                : nome;
            return `<tr class="clickable-row" data-empenho-id="${d.id}">
                <td>${nomeCell}</td>
                <td>${_fmtDate(d.data_empenho)}</td>
                <td>${_esc(d.elemento_despesa || '-')}</td>
                <td class="text-right">${_shortBrl(d.valor_empenhado)}</td>
                <td class="text-right">${_shortBrl(d.valor_pago)}</td>
            </tr>`;
        }).join('');
        html += `<div class="tbl-wrap"><table class="dialog-table">
            <thead><tr><th>${dualLabel('Empresa','Credor')}</th><th>Data</th><th>${dualLabel('Tipo de gasto','Elemento')}</th><th class="text-right">${dualLabel('Reservado','Empenhado')}</th><th class="text-right">Pago</th></tr></thead>
            <tbody>${despRows}</tbody>
        </table></div>`;
        if (data.despesas.length >= 50) {
            html += '<p class="text-sm text-muted">Mostrando as 50 despesas mais recentes.</p>';
        }
        html += '</div>';
    }

    if (!html) html = '<p class="text-sm text-muted">Nenhum detalhe disponivel para esta licitacao.</p>';
    body.innerHTML = html;
    _reattachDialogLinks(body);
}

function buildServidoresPanel(data) {
    const cols = data.columns;

    // Sort by severity: red first, yellow, then rest (preserving salary order within groups)
    const sortedRows = [...data.rows].sort((a, b) => {
        const aRed = _val(a, cols, 'flag_ceaf_expulso') || _val(a, cols, 'total_pago_durante_vinculo') > 0 || _val(a, cols, 'flag_socio_inidoneidade');
        const bRed = _val(b, cols, 'flag_ceaf_expulso') || _val(b, cols, 'total_pago_durante_vinculo') > 0 || _val(b, cols, 'flag_socio_inidoneidade');
        const aYellow = !aRed && (_val(a, cols, 'flag_socio_sancionado') || _val(a, cols, 'flag_bolsa_familia'));
        const bYellow = !bRed && (_val(b, cols, 'flag_socio_sancionado') || _val(b, cols, 'flag_bolsa_familia'));
        const aScore = aRed ? 0 : aYellow ? 1 : 2;
        const bScore = bRed ? 0 : bYellow ? 1 : 2;
        return aScore - bScore;
    });

    const bodyRows = sortedRows.map(r => {
        const nome = _esc(_val(r, cols, 'nome_servidor'));
        const cargo = _esc(_val(r, cols, 'cargo') || '-');
        const salario = _shortBrl(_val(r, cols, 'maior_salario'));
        const qtdEmpresas = _val(r, cols, 'qtd_empresas_socio') || 0;
        const cnpjs = _val(r, cols, 'cnpjs_socio') || [];
        const municipios = _val(r, cols, 'municipios') || [];
        const municipiosStr = municipios.map(m => _esc(m)).join(', ') || '-';
        let badges = '';
        const ceafExpulso = _val(r, cols, 'flag_ceaf_expulso');
        if (ceafExpulso) badges += '<span class="badge badge-red">Expulso da Adm. Federal (CEAF)</span>';
        const totalDuranteVinculo = _val(r, cols, 'total_pago_durante_vinculo');
        if (totalDuranteVinculo > 0) {
            badges += `<span class="badge badge-red">Empresa recebeu ${_shortBrl(totalDuranteVinculo)} durante vinculo</span>`;
        }
        if (_val(r, cols, 'flag_duplo_vinculo_estado')) badges += '<span class="badge badge-red">Tambem recebe pagamentos do governo estadual</span>';
        if (_val(r, cols, 'flag_multi_empresa')) badges += `<span class="badge badge-yellow">Socio de ${qtdEmpresas || 'varias'} empresas</span>`;
        if (_val(r, cols, 'flag_bolsa_familia')) badges += '<span class="badge badge-yellow">Bolsa Familia durante vinculo</span>';
        if (_val(r, cols, 'flag_alto_salario_socio')) badges += '<span class="badge badge-yellow">Salario alto + vinculo societario</span>';
        const socioSancionado = _val(r, cols, 'flag_socio_sancionado');
        const socioInidoneidade = _val(r, cols, 'flag_socio_inidoneidade');
        if (socioInidoneidade) badges += '<span class="badge badge-red">Socio de empresa com Inidoneidade (CEIS)</span>';
        else if (socioSancionado) badges += '<span class="badge badge-orange">Socio de empresa sancionada (CEIS/CNEP)</span>';
        if (!badges) badges = '<span class="text-sm text-muted">Combinacao de indicadores elevada</span>';

        const cpf6 = _esc(_val(r, cols, 'cpf_digitos_6') || '');
        const nomeUpper = _esc(_val(r, cols, 'nome_upper') || '');
        const hasDetail = cpf6 && nomeUpper;
        const detailAttrs = hasDetail ? ` data-cpf6="${cpf6}" data-nome-upper="${nomeUpper}" data-cnpjs='${JSON.stringify(cnpjs)}' data-nome="${nome}"` : '';
        const totalPagoRow = _val(r, cols, 'total_pago_durante_vinculo') > 0;
        const bolsaFamilia = _val(r, cols, 'flag_bolsa_familia');
        const rowClass = (ceafExpulso || totalPagoRow || socioInidoneidade) ? 'clickable-row row-sancao' : (socioSancionado || bolsaFamilia) ? 'clickable-row row-sancao-leve' : 'clickable-row';
        const cpfFmt = cpf6.length === 6 ? `***.${cpf6.slice(0,3)}.${cpf6.slice(3,6)}-**` : '';
        return `<tr data-cargo="${cargo.toLowerCase()}" ${hasDetail ? `class="${rowClass}"` : ''}${detailAttrs}><td>${nome}</td><td><code class="text-sm">${cpfFmt}</code></td><td>${cargo}</td><td>${municipiosStr}</td><td class="text-right">${salario}</td><td class="text-right">${qtdEmpresas || '-'}</td><td>${badges}</td></tr>`;
    }).join('');

    const _ldot = (bg) => `<span class="color-legend-dot" style="background:${bg}"></span>`;
    const hasRedServ = data.rows.some(r => _val(r, data.columns, 'flag_ceaf_expulso') || _val(r, data.columns, 'total_pago_durante_vinculo') > 0 || _val(r, data.columns, 'flag_socio_inidoneidade'));
    const hasYellowServ = data.rows.some(r => (_val(r, data.columns, 'flag_socio_sancionado') && !_val(r, data.columns, 'flag_socio_inidoneidade')) || _val(r, data.columns, 'flag_bolsa_familia'));
    let servLegend = '';
    if (hasRedServ || hasYellowServ) {
        let items = [];
        if (hasRedServ) items.push(`<span class="color-legend-item">${_ldot('#ef4444')} Expulso da adm. federal, empresa recebeu empenhos durante vinculo ou socio de empresa com Inidoneidade</span>`);
        if (hasYellowServ) items.push(`<span class="color-legend-item">${_ldot('#f59e0b')} Socio de empresa com Impedimento/CNEP ou Bolsa Familia durante vinculo</span>`);
        servLegend = `<div class="color-legend">${items.join('')}</div>`;
    }

    return `<section class="result-block">
        <div class="result-toolbar"><div>
            <h3 class="card-title">Servidores com sinais de atencao</h3>
            <p class="text-muted text-sm">Servidores que apresentam ao menos um sinal de risco nos cruzamentos automaticos: vinculo societario com fornecedores, duplo vinculo com o estado, recebimento de beneficio social ou acumulacao atipica. A Constituicao (art. 37, XVI) admite acumulacao para profissionais de saude.</p>
            ${servLegend}
        </div></div>
        <div class="table-shell js-data-table" data-page-size="10">
            <div class="table-actions">
                <input type="search" class="table-filter" placeholder="Filtrar nesta tabela" aria-label="Filtrar servidores">
                <p class="table-meta text-sm text-muted" data-table-meta></p>
            </div>
            <div class="tbl-wrap"><table>
                <thead><tr><th>Servidor</th><th>CPF</th><th>Cargo</th><th>Municipio(s)</th><th class="text-right">Maior Salario</th><th class="text-right">Empresas</th><th>Sinais de Atencao</th></tr></thead>
                <tbody>${bodyRows}</tbody>
            </table></div>
            <div class="table-pagination">
                <button type="button" class="btn btn-outline btn-sm" data-page-prev>Anterior</button>
                <p class="text-sm text-muted" data-page-label></p>
                <button type="button" class="btn btn-outline btn-sm" data-page-next>Proxima</button>
            </div>
        </div>
    </section>`;
}

async function loadAsyncPanel(panelName, municipio, uf) {
    const panel = document.querySelector(`[data-async-panel="${panelName}"]`);
    if (!panel) return;

    // Get UF from data attribute if available
    const panelUf = uf || panel.dataset.uf || '';
    try {
        const response = await fetch(`/api/top/${panelName}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(_buildBody(municipio, panelUf)),
        });
        panel.innerHTML = await response.text();
        initDataTables(panel);
        initInteractiveToggles(panel);
        initClickableRows(panel);
    } catch {
        panel.innerHTML = '<p class="text-sm text-muted">Nao foi possivel carregar este bloco agora.</p>';
    }
}

function updateSectionSummaries() {
    document.querySelectorAll('.report-section').forEach((section) => {
        const cards = Array.from(section.querySelectorAll('.finding-card'));
        let total = 0;
        let findings = 0;

        cards.forEach((card) => {
            const count = Number(card.dataset.count || 0);
            total += count;
            if (count > 0) findings += 1;
        });

        const summary = section.querySelector('[data-section-total]');
        if (!summary) return;
        const summaryLabel = summary.nextElementSibling;

        if (!findings) {
            summary.textContent = 'Nenhum achado carregado';
            if (summaryLabel) summaryLabel.style.display = 'none';
            return;
        }

        if (summaryLabel) summaryLabel.style.display = '';
        summary.textContent = `${total} registros em ${findings} blocos`;
    });
}

async function runLimited(items, limit, worker) {
    const results = [];
    const queue = [...items];

    async function next() {
        const item = queue.shift();
        if (!item) return;
        results.push(await worker(item));
        await next();
    }

    await Promise.all(Array.from({ length: Math.min(limit, items.length) }, () => next()));
    return results;
}

function initDataTables(root = document) {
    root.querySelectorAll('.js-data-table').forEach((tableShell) => {
        if (tableShell.dataset.enhanced === 'true') return;
        tableShell.dataset.enhanced = 'true';

        const filterInput = tableShell.querySelector('.table-filter');
        const meta = tableShell.querySelector('[data-table-meta]');
        const pageLabel = tableShell.querySelector('[data-page-label]');
        const prevBtn = tableShell.querySelector('[data-page-prev]');
        const nextBtn = tableShell.querySelector('[data-page-next]');
        const rows = Array.from(tableShell.querySelectorAll('tbody tr'));
        const pageSize = Number(tableShell.dataset.pageSize || 12);
        let filteredRows = rows;
        let page = 1;
        let externalFilter = null; // set by toggles (e.g. ocultar medicos)

        const applyFilters = () => {
            const term = filterInput ? filterInput.value.trim().toLowerCase() : '';
            filteredRows = rows.filter((row) => {
                if (term && !row.textContent.toLowerCase().includes(term)) return false;
                if (externalFilter && !externalFilter(row)) return false;
                return true;
            });
        };

        const renderPage = () => {
            const totalPages = Math.max(1, Math.ceil(filteredRows.length / pageSize));
            if (page > totalPages) page = totalPages;
            const start = (page - 1) * pageSize;
            const pageRows = filteredRows.slice(start, start + pageSize);

            rows.forEach((row) => {
                row.style.display = pageRows.includes(row) ? '' : 'none';
            });

            if (meta) meta.textContent = `${filteredRows.length} registro(s) encontrados`;
            if (pageLabel) pageLabel.textContent = `Pagina ${page} de ${totalPages}`;
            if (prevBtn) prevBtn.disabled = page === 1;
            if (nextBtn) nextBtn.disabled = page === totalPages;
        };

        // Expose refilter for external toggles
        tableShell._refilter = (filterFn) => {
            externalFilter = filterFn;
            applyFilters();
            page = 1;
            renderPage();
        };

        // Column sorting
        const headers = Array.from(tableShell.querySelectorAll('thead th'));
        let sortCol = -1;
        let sortAsc = true;

        headers.forEach((th, colIndex) => {
            th.style.cursor = 'pointer';
            th.addEventListener('click', () => {
                if (sortCol === colIndex) {
                    sortAsc = !sortAsc;
                } else {
                    sortCol = colIndex;
                    sortAsc = true;
                }
                headers.forEach(h => h.classList.remove('sort-asc', 'sort-desc'));
                th.classList.add(sortAsc ? 'sort-asc' : 'sort-desc');

                filteredRows.sort((a, b) => {
                    const cellA = a.children[colIndex]?.textContent.trim() || '';
                    const cellB = b.children[colIndex]?.textContent.trim() || '';
                    // Try numeric comparison (handle R$, %, commas)
                    const numA = parseFloat(cellA.replace(/[R$%\s.]/g, '').replace(',', '.'));
                    const numB = parseFloat(cellB.replace(/[R$%\s.]/g, '').replace(',', '.'));
                    if (!isNaN(numA) && !isNaN(numB)) {
                        return sortAsc ? numA - numB : numB - numA;
                    }
                    return sortAsc ? cellA.localeCompare(cellB, 'pt-BR') : cellB.localeCompare(cellA, 'pt-BR');
                });
                page = 1;
                renderPage();
            });
        });

        filterInput?.addEventListener('input', () => {
            applyFilters();
            page = 1;
            renderPage();
        });

        prevBtn?.addEventListener('click', () => {
            page = Math.max(1, page - 1);
            renderPage();
        });

        nextBtn?.addEventListener('click', () => {
            const totalPages = Math.max(1, Math.ceil(filteredRows.length / pageSize));
            page = Math.min(totalPages, page + 1);
            renderPage();
        });

        renderPage();
    });
}

function initClickableRows(root = document) {
    root.querySelectorAll('.clickable-row').forEach((row) => {
        if (row.dataset.clickInit === 'true') return;
        row.dataset.clickInit = 'true';
        row.addEventListener('click', () => {
            // Servidor row
            const cpf6 = row.dataset.cpf6 || '';
            const nomeUpper = row.dataset.nomeUpper || '';
            if (cpf6 && nomeUpper) {
                const cnpjs = JSON.parse(row.dataset.cnpjs || '[]') || [];
                const servidorNome = row.dataset.nome || '';
                openServidorDialog(cpf6, nomeUpper, cnpjs, servidorNome);
                return;
            }
            // Fornecedor row
            const fornCnpj = row.dataset.fornecedorCnpj || '';
            if (fornCnpj) {
                const fornNome = row.dataset.fornecedorNome || '';
                const fornNomeCredor = row.dataset.fornecedorNomeCredor || '';
                const fornCpfCnpj = row.dataset.fornecedorCpfCnpj || '';
                openFornecedorDialog(fornCnpj, fornNome, null, false, fornNomeCredor, fornCpfCnpj);
                return;
            }
            // Licitacao row
            const licNum = row.dataset.licitacaoNum || '';
            if (licNum) {
                const licAno = row.dataset.licitacaoAno || '0';
                const licMod = row.dataset.licitacaoMod || '';
                openLicitacaoDialog(licNum, licAno, _currentMunicipio, `Licitacao ${licNum}`, licMod);
            }
        });
    });
}

document.addEventListener('DOMContentLoaded', () => {
    initDataTables(document);
    initInteractiveToggles(document);
    initClickableRows(document);
    initBackToTop();
    initShareButtons();
    initModeToggle();
    initTermTooltips();
    initNarrativeAnchors();

    // Finding card collapse toggle
    document.querySelectorAll('.finding-card .finding-head').forEach(head => {
        head.addEventListener('click', () => {
            head.closest('.finding-card').classList.toggle('collapsed');
        });
    });

    const dialog = document.getElementById('empresa-dialog');
    if (dialog) {
        // Observa abertura/fechamento do dialog via atributo [open]
        // (funciona para qualquer caminho que chame showModal/close).
        let wasOpen = dialog.open;
        const obs = new MutationObserver(() => {
            const isOpen = dialog.open;
            if (isOpen && !wasOpen) _dialogOnOpen();
            wasOpen = isOpen;
        });
        obs.observe(dialog, { attributes: true, attributeFilter: ['open'] });
        dialog.addEventListener('close', () => { _dialogOnClose(); });
        const backBtn = dialog.querySelector('.dialog-back');
        if (backBtn) backBtn.addEventListener('click', () => { _dialogPop(); });
        _initDialogSwipeToClose();
    }

    // Date filter handlers
    document.getElementById('btnFiltrarData')?.addEventListener('click', () => {
        const inicio = document.getElementById('dateInicio')?.value;
        const fim = document.getElementById('dateFim')?.value;
        if (!inicio || !fim) return;

        // Reset all cards to loading state
        document.querySelectorAll('.finding-card').forEach(card => {
            card.classList.add('loading');
            card.classList.remove('is-empty', 'is-timeout');
            const body = card.querySelector('.finding-body');
            if (body) body.innerHTML = skeletonTableHtml(3, 3);
            const countEl = card.querySelector('[data-count]');
            if (countEl) countEl.textContent = '...';
            delete card.dataset.count;
        });
        // Reset section summaries
        document.querySelectorAll('[data-section-total]').forEach(el => el.textContent = 'Carregando...');

        // Reset async panels
        document.querySelectorAll('[data-async-panel]').forEach(panel => {
            panel.innerHTML = skeletonTableHtml(4, 3);
        });

        // Show clear button + status
        const btnLimpar = document.getElementById('btnLimparData');
        if (btnLimpar) btnLimpar.style.display = '';
        const status = document.getElementById('dateFilterStatus');
        if (status) status.textContent = `Periodo: ${_formatDatePt(inicio)} a ${_formatDatePt(fim)}`;

        bootstrapCityReport(_currentMunicipio, _currentUf, inicio, fim);
    });

    document.getElementById('btnLimparData')?.addEventListener('click', () => {
        const diEl = document.getElementById('dateInicio');
        const dfEl = document.getElementById('dateFim');
        if (diEl) diEl.value = '';
        if (dfEl) dfEl.value = '';
        const btnLimpar = document.getElementById('btnLimparData');
        if (btnLimpar) btnLimpar.style.display = 'none';
        const status = document.getElementById('dateFilterStatus');
        if (status) status.textContent = '';

        // Reset all cards to loading
        document.querySelectorAll('.finding-card').forEach(card => {
            card.classList.add('loading');
            card.classList.remove('is-empty', 'is-timeout');
            const body = card.querySelector('.finding-body');
            if (body) body.innerHTML = skeletonTableHtml(3, 3);
            const countEl = card.querySelector('[data-count]');
            if (countEl) countEl.textContent = '...';
            delete card.dataset.count;
        });
        document.querySelectorAll('[data-section-total]').forEach(el => el.textContent = 'Carregando...');
        document.querySelectorAll('[data-async-panel]').forEach(panel => {
            panel.innerHTML = skeletonTableHtml(4, 3);
        });

        // Clear filter — show all-time data
        bootstrapCityReport(_currentMunicipio, _currentUf);
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
