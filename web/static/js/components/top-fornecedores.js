// === components/top-fornecedores.js ===
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
        const cnpjCompletoDigits = String(cnpjCompleto || '').replace(/\D/g, '');
        const abrangenciaRaw = _val(r, cols, 'abrangencia_sancao_info') || '';
        const sancaoAplica = abrangenciaRaw.startsWith('!');
        const abrangenciaInfo = abrangenciaRaw.replace(/^!/, '');
        const parenMatch = abrangenciaInfo.match(/\(([^)]+)\)/);
        const scopeSuffix = abrangenciaInfo.startsWith('Nacional')
            ? ' (Nacional)'
            : parenMatch ? ` (${parenMatch[1].slice(0, 50)})` : '';
        if (isInidoneidade) badges += '<span class="badge badge-red" title="Declaracao de inidoneidade (CEIS) - impede contratar com toda administracao publica (nacional)"><span class="citizen-only">Proibida de contratar (nacional)</span><span class="auditor-only">Inidoneidade - CEIS (Nacional)</span></span>';
        else if (_val(r, cols, 'flag_ceis')) badges += `<span class="badge badge-orange" title="Cadastro de Empresas Inidoneas e Suspensas (CEIS)${_esc(scopeSuffix)}. Pode decorrer de varios motivos: descumprimento contratual, nao assinar contrato, fraude em licitacao, documentacao falsa, entre outros."><span class="citizen-only">Impedida de contratar (CEIS)${_esc(scopeSuffix)}</span><span class="auditor-only">Impedimento - CEIS${_esc(scopeSuffix)}</span></span>`;
        if (_val(r, cols, 'flag_cnep')) badges += `<span class="badge badge-orange" title="Cadastro Nacional de Empresas Punidas (CNEP) - Lei Anticorrupcao 12.846/2013${_esc(scopeSuffix)}"><span class="citizen-only">Punida (Lei Anticorrupcao)${_esc(scopeSuffix)}</span><span class="auditor-only">CNEP${_esc(scopeSuffix)}</span></span>`;
        if (_val(r, cols, 'flag_acordo_leniencia')) badges += '<span class="badge badge-blue" title="Acordo de leniencia firmado com a empresa"><span class="citizen-only">Acordo de leniencia</span><span class="auditor-only">Acordo de Leniencia</span></span>';
        if (_val(r, cols, 'flag_pgfn')) badges += '<span class="badge badge-yellow" title="Divida ativa da Uniao (PGFN) - impostos federais em aberto"><span class="citizen-only">Devendo impostos federais</span><span class="auditor-only">Divida ativa (PGFN)</span></span>';
        if (_val(r, cols, 'flag_inativa')) badges += '<span class="badge badge-gray" title="Cadastro da empresa inativo na Receita Federal"><span class="citizen-only">Empresa inativa na Receita</span><span class="auditor-only">Cadastro inativo</span></span>';
        if (!badges) badges = '<span class="text-sm text-muted">Sem sinal automatico</span>';
        const rowSeverityClass = (() => {
            const recInid = _val(r, cols, 'flag_recebeu_durante_inidoneidade');
            const recSan = _val(r, cols, 'flag_recebeu_durante_sancao_aplicavel');
            if (recInid) return 'row-sancao';
            if (recSan) return 'row-sancao-leve';
            return '';
        })();
        if (cnpjCompletoDigits.length !== 14) {
            return `<tr class="row-detail-unavailable ${rowSeverityClass}" aria-disabled="true"><td data-label="Empresa" class="stack-title">${nome} <span class="detail-unavailable-hint">Detalhes indisponiveis sem CNPJ completo</span></td><td data-label="CNPJ" class="auditor-only stack-meta"><code class="text-sm">${cnpjFmt}</code></td><td data-label="Recebido" class="text-right num">${total}</td><td data-label="Empenhos" class="text-right auditor-only num">${qtd}</td><td data-label="Sinais" class="stack-badges">${badges}</td></tr>`;
        }
        return `<tr class="clickable-row ${rowSeverityClass}" data-fornecedor-cnpj="${cnpjBasico}" data-fornecedor-cpf-cnpj="${_esc(cnpjCompletoDigits)}" data-fornecedor-nome="${razao || nome}" data-fornecedor-nome-credor="${nome}"><td data-label="Empresa" class="stack-title">${nome}</td><td data-label="CNPJ" class="auditor-only stack-meta"><code class="text-sm">${cnpjFmt}</code></td><td data-label="Recebido" class="text-right num">${total}</td><td data-label="Empenhos" class="text-right auditor-only num">${qtd}</td><td data-label="Sinais" class="stack-badges">${badges}</td></tr>`;
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
            <h3 class="card-title title-with-action"><span class="title-text">${dualLabel('Empresas que mais receberam da prefeitura', 'Maiores fornecedores do municipio')}</span> ${mobileDescToggleHtml()}</h3>
            <p class="text-muted text-sm mobile-collapsible-desc"><span class="citizen-only">Concentracao dos pagamentos e sinais de atencao de cada empresa. Toque em uma empresa para detalhes.</span><span class="auditor-only">Concentracao de pagamentos e sinais automaticos de cada fornecedor. Clique em um fornecedor para ver detalhes.</span></p>
            ${fornLegend}
        </div></div>
        <div class="table-shell js-data-table" data-page-size="10">
            <div class="table-actions">
                <input type="search" class="table-filter" placeholder="Filtrar nesta tabela" aria-label="Filtrar fornecedores">
                <p class="table-meta text-sm text-muted" data-table-meta></p>
            </div>
            <div class="tbl-wrap"><table class="stack-mobile">
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
                <md-text-button data-page-prev>Anterior</md-text-button>
                <p class="text-sm text-muted" data-page-label></p>
                <md-text-button data-page-next>Proxima</md-text-button>
            </div>
        </div>
    </section>`;
}

