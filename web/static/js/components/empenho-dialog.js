// === components/empenho-dialog.js ===
async function openEmpenhoDialog(empenhoId, options = {}) {
    const dialog = document.getElementById('empresa-dialog');
    if (!dialog) return;
    const fromUrl = !!options.fromUrl;
    const isInitialOpen = !dialog.open;
    // Captura tipo do dialog atual ANTES do push (perdido depois). Vazio
    // quando isInitialOpen=true.
    const drilledFrom = isInitialOpen ? '' : _currentDialogType;
    if (dialog.open) { _dialogPush(); } else { _dialogReset(); }
    _currentDialogType = 'empenho';
    if (typeof _dialogStateApply === 'function') {
        _dialogStateApply({ d: 'empenho', id: String(empenhoId || '') }, fromUrl, isInitialOpen);
    }
    const seq = (typeof _dialogNextSeq === 'function') ? _dialogNextSeq() : null;
    const title = dialog.querySelector('.dialog-title');
    const body = dialog.querySelector('.dialog-body');
    title.textContent = 'Detalhes do empenho';
    body.innerHTML = '<p class="text-sm text-muted">Carregando...</p>';
    if (!dialog.open) dialog.show();
    document.body.classList.add('dialog-open');
    if (isInitialOpen) trackEvent && trackEvent('dialog-aberto', {
        tipo: 'empenho',
        empenho: String(empenhoId || ''),
        municipio: _currentMunicipio || '',
    });
    else if (drilledFrom) trackEvent && trackEvent('dialog-aberto', {
        tipo: 'empenho',
        empenho: String(empenhoId || ''),
        municipio: _currentMunicipio || '',
        drilled_from: drilledFrom,
    });

    const data = await _cachedPost('/api/empenho/detalhes', `emp:${empenhoId}`, { id: parseInt(empenhoId) });
    if (seq !== null && typeof _dialogSeqValid === 'function' && !_dialogSeqValid(seq)) return;
    if (!data || !data.numero_empenho) {
        body.innerHTML = '<p class="text-sm text-muted">Empenho nao encontrado.</p>';
        return;
    }

    title.textContent = `Empenho ${data.numero_empenho}`;
    let html = _historyNote('Historico completo do empenho — este detalhamento nao muda com o filtro de periodo da pagina.');

    // Descricao do empenho (historico livre escrito pelo orgao explicando
    // o gasto). Primeiro bloco apos a nota de historico porque eh o texto
    // que melhor responde "o que e este empenho?" pra usuario casual.
    // Antes (PR #150) estava mesclada na secao final "Origem e descricao"
    // mas usuario reportou que enterrar a descricao no fim do dialog
    // confunde a leitura — descricao eh o "lede" do empenho.
    if (data.historico) {
        html += `<div class="dialog-section"><h4>${dualLabel('O que diz o empenho','Descricao')}</h4>`;
        html += `<p class="text-sm empenho-historico" style="line-height:1.6;margin:0">${_esc(data.historico)}</p>`;
        html += '</div>';
    }

    // Licitacao vinculada — primeiro bloco logo apos descricao, pra dar
    // contexto imediato do empenho (qual processo originou o pagamento).
    // Renderiza como link direto pra /licitacao/<mun>/<ano>/<ug>/<modnum>
    // quando temos os campos canonicos vindos de tce_pb_licitacao via
    // LATERAL JOIN no /api/empenho/detalhes (lic_modalidade, lic_numero_licitacao,
    // lic_descricao_ug, ano_licitacao). Esses sao OBRIGATORIOS pro slug bater
    // com o cache key do warmer; usar campos do empenho direto (data.modalidade_licitacao,
    // data.numero_licitacao) gera URLs broken porque os formatos divergem entre
    // tce_pb_despesa e tce_pb_licitacao (ex: "Pregao (Lei 14.133/21)" vs
    // "Pregao (Lei No 14.133/2021)", "000032025" vs "00003/2025"). Fallback
    // dialog-link quando lic_* nao vem da API (licitacao nao encontrada na
    // canonical match).
    {
        const mod = data.modalidade_licitacao || '';
        const numLic = data.numero_licitacao || '';
        const semLic = !numLic || numLic === '000000000' || mod.toLowerCase().includes('sem licit');
        const empMun = data.municipio || '';
        const labelDisplay = `${_esc(mod || data.lic_modalidade || 'Licitacao')} (${_esc(numLic || data.lic_numero_licitacao || '')})`;
        if (!semLic) {
            const _txtSlug = (s) => String(s || '').toLowerCase()
                .normalize('NFKD').replace(/[\u0300-\u036f]/g, '')
                .replace(/[^a-z0-9]+/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '');
            const ano = parseInt(data.ano_licitacao) || 0;
            const licMod = data.lic_modalidade || '';
            const licNum = data.lic_numero_licitacao || '';
            const licUg = data.lic_descricao_ug || data.descricao_ug || '';
            if (ano && empMun && licMod && licNum) {
                const munSlug = _txtSlug(empMun);
                const ugSlug = _txtSlug(licUg) || 'prefeitura';
                const modSlug = _txtSlug(licMod) || 'lic';
                const numSlug = _txtSlug(licNum) || '0';
                const pagePath = `/licitacao/${munSlug}/${ano}/${ugSlug}/${modSlug}-${numSlug}`;
                html += `<div class="dialog-section"><h4>${dualLabel('Origem do gasto (licitacao)','Licitacao vinculada')}</h4>`;
                html += `<p class="text-sm"><a href="${pagePath}" class="ext-link-inline" title="Ver pagina dedicada desta licitacao (mais detalhes e SEO)">${labelDisplay} &#8599;</a></p>`;
                html += '</div>';
            } else {
                // Sem campos canonicos da licitacao (LATERAL match falhou).
                // Cai no dialog-link, que abre o licitacao-dialog e tenta
                // resolver via /api/licitacao/detalhes (canonical match server-side).
                // Repassa codigo_ug do empenho (data.codigo_ug) pra API narrow
                // ao 4-tuple canonico.
                html += `<div class="dialog-section"><h4>${dualLabel('Origem do gasto (licitacao)','Licitacao vinculada')}</h4>`;
                html += `<p class="text-sm"><a href="#" class="dialog-link" data-lic-num="${_esc(numLic)}" data-lic-ano="${ano || 0}" data-lic-mun="${_esc(empMun)}" data-lic-mod="${_esc(mod)}" data-lic-ug="${_esc(data.codigo_ug || '')}">${labelDisplay}</a></p>`;
                html += '</div>';
            }
        } else {
            html += `<div class="dialog-section"><h4>${dualLabel('Origem do gasto (licitacao)','Licitacao vinculada')}</h4>`;
            html += '<p class="text-sm"><span class="badge badge-yellow">Sem licitacao</span></p>';
            html += '</div>';
        }
    }

    // Historico do empenho movido para secao "Descricao" no topo do
    // dialog (logo apos a nota de historico). Esta secao "Origem" agora
    // contem apenas campos estruturais (UG, fonte, unidade, municipio,
    // data) — o "de onde veio" o gasto.

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
    // data-forn-mun: igual ao licitacao link logo abaixo, repassa o
    // municipio do empenho pra que o fornecedor-dialog tenha context
    // correto na pagina /empresa/<cnpj> global onde _currentMunicipio
    // eh vazio.
    const credorMun = _esc(data.municipio || '');
    const credorLink = isClickable
        ? `<a href="#" class="dialog-link" data-forn-cnpj="${cnpjB}" data-forn-cpf-cnpj="${cnpjRaw}" data-forn-nome="${credorNome}" data-forn-nome-credor="${credorNome}" data-forn-mun="${credorMun}">${credorNome}</a>`
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

    // Origem — campos estruturais do empenho (UG, fonte, unidade,
    // municipio, data). Descricao livre fica na secao "Descricao" no
    // topo do dialog (separada propositalmente apos feedback do usuario:
    // misturar texto livre + campos estruturais no fim do dialog
    // dificulta leitura).
    html += `<div class="dialog-section"><h4>${dualLabel('De onde veio','Origem')}</h4>`;
    html += '<div class="empresa-card"><div class="empresa-details">';
    html += `<span><strong>Data:</strong> ${_fmtDate(data.data_empenho)}</span>`;
    if (data.descricao_ug) html += `<span><strong>${dualLabel('Setor:','UG:')}</strong> ${_esc(data.descricao_ug)}</span>`;
    if (data.descricao_unidade_orcamentaria) html += `<span><strong>Unidade:</strong> ${_esc(data.descricao_unidade_orcamentaria)}</span>`;
    if (data.descricao_fonte_recurso) html += `<span><strong>${dualLabel('Origem do recurso:','Fonte:')}</strong> ${_esc(data.descricao_fonte_recurso)}</span>`;
    if (data.municipio) html += `<span><strong>Municipio:</strong> ${_esc(data.municipio)}</span>`;
    html += '</div></div>';
    html += '</div>';

    body.innerHTML = html;
    _reattachDialogLinks(body);
    _decorateDialogBody(body);
}

