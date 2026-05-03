// === components/empenho-dialog.js ===
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
    let html = _historyNote('Historico completo do empenho — este detalhamento nao muda com o filtro de periodo da pagina.');

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
    _decorateDialogBody(body);
}

