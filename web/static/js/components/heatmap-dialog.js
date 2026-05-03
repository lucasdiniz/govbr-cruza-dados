// === components/heatmap-dialog.js ===
async function openHeatmapMonthDialog(municipio, ano, mes, options = {}) {
    const dialog = document.getElementById('empresa-dialog');
    if (!dialog) return;
    if (dialog.open && !options.inPlace) { _dialogPush(); }
    else if (!dialog.open) { _dialogReset(); }
    const title = dialog.querySelector('.dialog-title');
    const body = dialog.querySelector('.dialog-body');
    const mesesLabel = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'];
    const mesNome = mesesLabel[mes - 1] || mes;
    title.textContent = `${mesNome}/${ano} — ${municipio}`;
    body.innerHTML = '<p class="text-sm text-muted">Carregando...</p>';
    if (!dialog.open) dialog.show();
    document.body.classList.add('dialog-open');

    let data;
    try {
        const resp = await fetch(`/api/heatmap/${encodeURIComponent(municipio)}/${ano}/${mes}`);
        if (!resp.ok) {
            let msg = 'Nao foi possivel carregar os detalhes deste mes.';
            try {
                const err = await resp.json();
                if (err && err.error) msg = err.error;
            } catch {}
            throw new Error(msg);
        }
        data = await resp.json();
        if (data && data.error) throw new Error(data.error);
    } catch (err) {
        body.innerHTML = `<div class="async-error"><p class="text-sm text-muted">${_esc(err.message || String(err))}</p><md-text-button data-retry-heatmap>Tentar novamente</md-text-button></div>`;
        body.querySelector('[data-retry-heatmap]')?.addEventListener('click', () => openHeatmapMonthDialog(municipio, ano, mes, { inPlace: true }));
        return;
    }

    const resumo = data.resumo || {};
    const fornecedores = data.fornecedores || [];
    const elementos = data.elementos || [];
    const funcoes = data.funcoes || [];
    const modalidades = data.modalidades || [];
    const empenhos = data.empenhos || [];
    let html = _historyNote('Historico completo do mes selecionado — este detalhamento nao muda com o filtro de periodo da pagina.');

    html += '<div class="dialog-section"><h4>Resumo do mes</h4>';
    html += '<div class="stats-grid">';
    html += `<div class="stat"><div class="stat-label">${dualLabel('Reservado','Total empenhado')}</div><div class="stat-value">${_shortBrl(Number(resumo.total_empenhado || 0))}</div></div>`;
    html += `<div class="stat"><div class="stat-label">${dualLabel('Pago','Total pago')}</div><div class="stat-value">${_shortBrl(Number(resumo.total_pago || 0))}</div></div>`;
    html += `<div class="stat"><div class="stat-label">${dualLabel('Qtd pagamentos','Empenhos')}</div><div class="stat-value">${Number(resumo.qtd_empenhos || 0).toLocaleString('pt-BR')}</div></div>`;
    html += `<div class="stat"><div class="stat-label">Fornecedores</div><div class="stat-value">${Number(resumo.qtd_fornecedores || 0).toLocaleString('pt-BR')}</div></div>`;
    html += '</div></div>';

    if (fornecedores.length) {
        html += `<div class="dialog-section"><h4>${dualLabel('Quem mais recebeu','Top fornecedores')}</h4>`;
        html += `<div class="tbl-wrap"><table class="data-table"><thead><tr><th>${dualLabel('Empresa','Fornecedor')}</th><th class="auditor-only">CPF/CNPJ</th><th class="num auditor-only">Empenhos</th><th class="num">${dualLabel('Reservado','Empenhado')}</th><th class="num">Pago</th></tr></thead><tbody>`;
        for (const f of fornecedores) {
            const nome = _esc(f.nome_credor || '-');
            const doc = _esc(f.cpf_cnpj || '-');
            const cnpjRaw = String(f.cpf_cnpj || '').replace(/\D/g, '');
            const isPJ = f.eh_pj && cnpjRaw.length === 14;
            const nomeCell = isPJ
                ? `<a href="#" class="dialog-link" data-forn-cnpj="${cnpjRaw.slice(0, 8)}" data-forn-nome="${nome}" data-forn-nome-credor="${nome}" data-forn-cpf-cnpj="${_esc(cnpjRaw)}">${nome}</a>`
                : nome;
            html += `<tr><td>${nomeCell}</td><td class="auditor-only"><code>${doc}</code></td><td class="num auditor-only">${Number(f.qtd_empenhos || 0).toLocaleString('pt-BR')}</td><td class="num">${_shortBrl(Number(f.total_empenhado || 0))}</td><td class="num">${_shortBrl(Number(f.total_pago || 0))}</td></tr>`;
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
        html += `<div class="tbl-wrap"><table class="data-table stack-mobile"><thead><tr><th>${dualLabel('Area','Funcao')}</th><th>Programa</th><th class="num auditor-only">Empenhos</th><th class="num">${dualLabel('Reservado','Empenhado')}</th><th class="num">Pago</th></tr></thead><tbody>`;
        for (const fu of funcoes) {
            const funcaoRaw = fu.funcao || '-';
            const progRaw = fu.programa || '-';
            const funcaoCitizen = _stripCodePrefix(funcaoRaw) || funcaoRaw;
            const progCitizen = _stripCodePrefix(progRaw) || progRaw;
            const funcaoCell = `<span class="citizen-only">${_esc(funcaoCitizen)}</span><span class="auditor-only">${_esc(funcaoRaw)}</span>`;
            const progCell = `<span class="citizen-only">${_esc(progCitizen)}</span><span class="auditor-only">${_esc(progRaw)}</span>`;
            html += `<tr>`
                + `<td data-label="${_lbl('Area','Funcao')}" class="stack-title">${funcaoCell}</td>`
                + `<td data-label="Programa" class="stack-meta">${progCell}</td>`
                + `<td class="num auditor-only" data-label="Empenhos">${Number(fu.qtd_empenhos || 0).toLocaleString('pt-BR')}</td>`
                + `<td class="num" data-label="${_lbl('Reservado','Empenhado')}">${_shortBrl(Number(fu.total_empenhado || 0))}</td>`
                + `<td class="num" data-label="Pago">${_shortBrl(Number(fu.total_pago || 0))}</td>`
                + `</tr>`;
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
    _decorateDialogBody(body);
}

