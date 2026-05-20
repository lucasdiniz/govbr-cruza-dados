// === components/licitacao-dialog.js ===
function _fetchLicitacaoDetails(numeroLicitacao, anoLicitacao, municipio, modalidade, codigoUg) {
    // codigo_ug entra na cache key pra evitar colisao quando 2 UGs distintas
    // (ex: Camara 101065 + Prefeitura 201065) compartilham numero_licitacao
    // + modalidade no mesmo municipio.
    return _cachedPost('/api/licitacao/detalhes',
        `lic:${numeroLicitacao}:${anoLicitacao}:${municipio}:${modalidade}:${codigoUg || ''}`,
        { numero_licitacao: numeroLicitacao, ano_licitacao: parseInt(anoLicitacao) || 0,
          municipio, modalidade: modalidade || '', codigo_ug: codigoUg || '' });
}

async function openLicitacaoDialog(numeroLicitacao, anoLicitacao, municipio, label, modalidade, codigoUg, options = {}) {
    // Suporte chamada legacy onde codigoUg vinha como `options` (5 args + obj):
    // openLicitacaoDialog(num, ano, mun, label, mod, {fromUrl: true})
    if (codigoUg && typeof codigoUg === 'object' && !options) {
        options = codigoUg;
        codigoUg = '';
    }
    options = options || {};
    codigoUg = codigoUg || '';
    const dialog = document.getElementById('empresa-dialog');
    if (!dialog) return;
    const fromUrl = !!options.fromUrl;
    const isInitialOpen = !dialog.open;
    const drilledFrom = isInitialOpen ? '' : _currentDialogType;
    if (dialog.open) { _dialogPush(); } else { _dialogReset(); }
    _currentDialogType = 'licitacao';
    if (typeof _dialogStateApply === 'function') {
        _dialogStateApply({
            d: 'licitacao',
            num: String(numeroLicitacao || ''),
            ano: String(anoLicitacao || ''),
            mod: modalidade || '',
            mun: municipio || '',
            ug: codigoUg || '',
        }, fromUrl, isInitialOpen);
    }
    const seq = (typeof _dialogNextSeq === 'function') ? _dialogNextSeq() : null;
    const title = dialog.querySelector('.dialog-title');
    const body = dialog.querySelector('.dialog-body');
    title.textContent = label || `Licitacao ${numeroLicitacao}`;
    body.innerHTML = '<p class="text-sm text-muted">Carregando...</p>';
    if (!dialog.open) dialog.show();
    document.body.classList.add('dialog-open');
    if (isInitialOpen) trackEvent && trackEvent('dialog-aberto', {
        tipo: 'licitacao',
        numero: String(numeroLicitacao || ''),
        ano: String(anoLicitacao || ''),
        modalidade: modalidade || '',
        municipio: municipio || _currentMunicipio || '',
        codigo_ug: codigoUg || '',
    });
    else if (drilledFrom) trackEvent && trackEvent('dialog-aberto', {
        tipo: 'licitacao',
        numero: String(numeroLicitacao || ''),
        ano: String(anoLicitacao || ''),
        modalidade: modalidade || '',
        municipio: municipio || _currentMunicipio || '',
        codigo_ug: codigoUg || '',
        drilled_from: drilledFrom,
    });

    const data = await _fetchLicitacaoDetails(numeroLicitacao, anoLicitacao, municipio, modalidade, codigoUg);
    if (seq !== null && typeof _dialogSeqValid === 'function' && !_dialogSeqValid(seq)) return;

    // Metadata — always render header
    const _licNumLabel = `N. ${_esc(numeroLicitacao)}${anoLicitacao && anoLicitacao !== '0' ? ` / ${anoLicitacao}` : ''}`;
    if (!data.licitacao && !(data.proponentes && data.proponentes.length) && !(data.despesas && data.despesas.length)) {
        body.innerHTML = `<p class="text-sm text-muted">Nenhum detalhe disponivel para esta licitacao (${_licNumLabel}).</p>`;
        return;
    }

    let html = _historyNote('Historico completo da licitacao — este detalhamento nao muda com o filtro de periodo da pagina.');

    // Link pra pagina dedicada da licitacao (indexavel, mais conteudo).
    // Hide quando ja na pagina /licitacao/X (auto-detect via URL).
    // PREFERE campos canonicos vindos da API (data.licitacao.modalidade /
    // data.licitacao.numero_licitacao) — esses sao do tce_pb_licitacao e
    // batem com o slug usado pelo warmer/SSR. Quando o dialog e aberto a
    // partir do empenho-dialog, os argumentos `modalidade` e `numeroLicitacao`
    // vem em formato de tce_pb_despesa (ex: "Pregao (Lei 14.133/21)" /
    // "000032025") que NAO bate com o slug do warmer ("Pregao (Lei No
    // 14.133/2021)" / "00003/2025") — gera 503 cache miss. So renderiza o
    // link quando data.licitacao foi resolvida (canonical match server-side).
    if (data.licitacao && data.licitacao.modalidade && data.licitacao.numero_licitacao
        && anoLicitacao && municipio) {
        const _txtSlug = (s) => String(s || '').toLowerCase()
            .normalize('NFKD').replace(/[\u0300-\u036f]/g, '')
            .replace(/[^a-z0-9]+/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '');
        const munSlug = _txtSlug(municipio);
        const ugSlug = _txtSlug(data.licitacao.descricao_ug) || 'prefeitura';
        const modSlug = _txtSlug(data.licitacao.modalidade) || 'lic';
        const numSlug = _txtSlug(data.licitacao.numero_licitacao) || '0';
        const modNumSlug = `${modSlug}-${numSlug}`;
        const pagePath = `/licitacao/${munSlug}/${anoLicitacao}/${ugSlug}/${modNumSlug}`;
        const isOnPage = location.pathname === pagePath;
        if (!isOnPage) {
            html += `<p class="text-sm" style="margin:.5rem 0"><a href="${pagePath}" class="ext-link-inline" title="Ver pagina dedicada desta licitacao (mais detalhes e SEO)">Ver pagina completa da licitacao &#8599;</a></p>`;
        }
    }

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
                <td data-label="Empresa" class="stack-title">${nomeLink}</td>
                <td data-label="CNPJ/CPF" class="auditor-only"><code class="text-sm">${_esc(p.cpf_cnpj_proponente || '-')}</code></td>
                <td data-label="Valor" class="text-right num">${_shortBrl(p.valor_ofertado)}</td>
                <td data-label="Resultado" class="stack-meta">${_esc(p.situacao_proposta || '-')}</td>
            </tr>`;
        }).join('');
        html += `<div class="tbl-wrap"><table class="dialog-table stack-mobile">
            <thead><tr><th>${dualLabel('Empresa','Proponente')}</th><th class="auditor-only">CNPJ/CPF</th><th class="text-right">${dualLabel('Valor proposto','Valor ofertado')}</th><th>${dualLabel('Resultado','Situacao')}</th></tr></thead>
            <tbody>${propRows}</tbody>
        </table></div>`;
        html += '</div>';
    }

    // Despesas vinculadas. Renderiza como mount do empenhos-controller
    // (paginado + filtravel — paridade exata com a pagina /licitacao/<...>).
    // Initial table = data.despesas (top 50 do /api/licitacao/detalhes,
    // ja PJ-filtered). Paginas 2+ / filtros fetcham /api/licitacao/empenhos.
    const despTotal = parseInt(data.despesas_total || 0, 10) || 0;
    if ((data.despesas && data.despesas.length) || despTotal > 0) {
        html += `<div class="dialog-section" id="lic-empenhos" data-nav-label="Empenhos"><h4>${dualLabel('Pagamentos desta licitacao','Empenhos vinculados')}</h4>`;
        // Container montado pelo empenhos-controller. Total conhecido
        // (totalKnown=1) — controller nao faz fetch live ao mount.
        const totalKnown = (typeof data.despesas_total === 'number') ? '1' : '0';
        html += `<section
            class="empenhos-section empenhos-section-dialog"
            data-empenhos-mount
            data-empenhos-endpoint="/api/licitacao/empenhos"
            data-empenhos-scope="licitacao"
            data-empenhos-lic-numero="${_esc(String(numeroLicitacao || ''))}"
            data-empenhos-lic-ano="${_esc(String(anoLicitacao || ''))}"
            data-empenhos-lic-modalidade="${_esc(String(modalidade || ''))}"
            data-empenhos-lic-codigo-ug="${_esc(String(codigoUg || ''))}"
            data-empenhos-total="${despTotal || (data.despesas ? data.despesas.length : 0)}"
            data-empenhos-total-known="${totalKnown}"
            data-empenhos-initial="${data.despesas && data.despesas.length ? '1' : '0'}">
            <p class="text-sm text-muted" data-empenhos-summary>
                ${despTotal > 0 ? despTotal.toLocaleString('pt-BR') + ' empenhos encontrados.' : 'Clique em uma linha para ver os detalhes.'}
            </p>`;
        // Filter bar (sub-template inline pra evitar dependencia de Jinja
        // no dialog que eh montado client-side).
        html += `<details class="date-filter-bar empenhos-filter-bar">
            <summary class="date-filter-summary">
                <span class="date-filter-current" data-empenhos-filter-summary>Periodo: todo o historico</span>
                <span class="date-filter-action">Filtrar empenhos</span>
            </summary>
            <div class="date-filter-panel" role="group" aria-label="Filtros de empenhos">
                <div class="empenhos-search-row">
                    <label class="date-field empenhos-search-field"><span>Buscar</span>
                        <input type="search" data-empenhos-q placeholder="Numero, elemento, historico, credor..." inputmode="search" maxlength="100" autocomplete="off">
                    </label>
                </div>
                <div class="date-filter-inputs">
                    <label class="date-field"><span>De</span>
                        <input type="text" data-empenhos-date-inicio inputmode="numeric" placeholder="DD/MM/AAAA" maxlength="10" autocomplete="off">
                    </label>
                    <label class="date-field"><span>Ate</span>
                        <input type="text" data-empenhos-date-fim inputmode="numeric" placeholder="DD/MM/AAAA" maxlength="10" autocomplete="off">
                    </label>
                    <md-filled-button data-empenhos-apply class="date-filter-submit">Aplicar</md-filled-button>
                    <p class="date-filter-status text-sm text-muted" data-empenhos-status aria-live="polite"></p>
                </div>
                <div class="date-filter-presets" role="group" aria-label="Atalhos de periodo">
                    <md-filter-chip label="Tudo" data-empenhos-preset="all" selected></md-filter-chip>
                    <md-filter-chip label="Ano atual" data-empenhos-preset="current-year"></md-filter-chip>
                    <md-filter-chip label="12 meses" data-empenhos-preset="last-12m"></md-filter-chip>
                    <md-text-button data-empenhos-clear style="display:none">Limpar filtros</md-text-button>
                </div>
            </div>
        </details>`;
        // Tabela inicial: data.despesas do payload (se houver). Senao
        // placeholder pro controller fetch live page 1.
        if (data.despesas && data.despesas.length) {
            const despRows = data.despesas.map(d => {
                const cnpjRaw = String(d.cnpj_clean || d.cpf_cnpj || '').replace(/\D/g, '');
                const cnpjB = cnpjRaw.slice(0, 8);
                const isClickable = cnpjB.length === 8 && /^\d{8}$/.test(cnpjB) && cnpjRaw.length >= 14;
                const nome = _esc(d.razao_social || d.nome_credor || '-');
                const nomeCell = isClickable
                    ? `<a href="#" class="dialog-link" data-forn-cnpj="${cnpjB}" data-forn-cpf-cnpj="${cnpjRaw}" data-forn-nome="${nome}" data-forn-nome-credor="${_esc(d.nome_credor || '')}">${nome}</a>`
                    : nome;
                return `<tr class="clickable-row" data-empenho-id="${d.id}">
                    <td data-label="Data">${_fmtDate(d.data_empenho)}</td>
                    <td data-label="Numero"><code>${_esc(d.numero_empenho || '-')}</code></td>
                    <td data-label="Credor" class="stack-title">${nomeCell}</td>
                    <td data-label="Elemento">${_esc(d.elemento_despesa || '-')}</td>
                    <td data-label="Empenhado" class="text-right num">${_shortBrl(d.valor_empenhado)}</td>
                    <td data-label="Pago" class="text-right num"><strong>${_shortBrl(d.valor_pago)}</strong></td>
                </tr>`;
            }).join('');
            html += `<div data-empenhos-table><div class="tbl-wrap"><table class="stack-mobile data-table empresa-empenhos-table">
                <thead><tr><th>Data</th><th>Numero</th><th>Credor</th><th>Elemento de despesa</th><th class="text-right">Empenhado</th><th class="text-right">Pago</th></tr></thead>
                <tbody>${despRows}</tbody>
            </table></div></div>`;
        } else {
            html += '<div data-empenhos-table><p class="text-sm text-muted empenhos-loading-placeholder">Carregando empenhos...</p></div>';
        }
        // Pagination footer
        html += `<nav class="empenhos-pagination" data-empenhos-pagination aria-label="Paginacao de empenhos" hidden>
            <md-text-button data-empenhos-prev disabled aria-label="Pagina anterior">
                <md-icon slot="icon">chevron_left</md-icon>Anterior
            </md-text-button>
            <span class="empenhos-page-info" data-empenhos-page-info aria-live="polite">Pagina 1</span>
            <md-text-button data-empenhos-next aria-label="Proxima pagina">
                Proxima<md-icon slot="icon">chevron_right</md-icon>
            </md-text-button>
        </nav>`;
        html += '</section>';
        html += '</div>';
    }
    body.innerHTML = html;
    _reattachDialogLinks(body);
    _decorateDialogBody(body);
    if (typeof initEmpenhosControllers === 'function') {
        initEmpenhosControllers(body);
    }
}

