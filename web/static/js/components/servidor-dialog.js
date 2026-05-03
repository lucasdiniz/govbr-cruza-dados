// === components/servidor-dialog.js ===
async function openServidorDialog(cpf6, nome, cnpjs, servidorNome, servidorFallback = {}) {
    const dialog = document.getElementById('empresa-dialog');
    if (!dialog) return;
    if (dialog.open) { _dialogPush(); } else { _dialogReset(); }
    const title = dialog.querySelector('.dialog-title');
    const body = dialog.querySelector('.dialog-body');
    const cpfMask = cpf6.length === 6 ? `***.${cpf6.slice(0,3)}.${cpf6.slice(3,6)}-**` : '';
    title.textContent = cpfMask ? `${servidorNome}  —  CPF: ${cpfMask}` : servidorNome;
    body.innerHTML = '<p class="text-sm text-muted">Carregando...</p>';
    if (!dialog.open) dialog.show();
    document.body.classList.add('dialog-open');

    const data = await _fetchServidorDetails(cpf6, nome, cnpjs, _currentMunicipio);
    if (data.detail_unavailable) {
        body.innerHTML = `<p class="text-sm text-muted">${_esc(data.detail_unavailable)}</p>`;
        return;
    }
    const sancoes = data.empresa_sancoes || {};
    const pgfn = data.empresa_pgfn || {};
    const empMap = data.empresa_empenhos || {};
    const acordosMap = data.empresa_acordos || {};
    const cnpjsNorm = Array.from(new Set((Array.isArray(cnpjs) ? cnpjs : [])
        .map(c => String(c || '').replace(/\D/g, '').slice(0, 8))
        .filter(c => c.length === 8)));
    let html = _historyNote();

    // Stats grid
    const vinculos = data.vinculos || [];
    const empresas = data.empresas || [];
    const bf = data.bolsa_familia || [];
    const qtdEmpresas = cnpjsNorm.length;
    const qtdSancionadas = Object.keys(sancoes).length;
    const qtdPgfn = Object.keys(pgfn).length;
    const totalPago = Object.values(empMap).reduce((s, e) => s + (e.total_pago || 0), 0);
    const empVincData = data.empenhos_durante_vinculo || [];
    const totalDuranteVinc = empVincData.reduce((s, e) => s + (e.valor_pago || 0), 0);
    const maiorSalario = vinculos.reduce((m, v) => Math.max(m, v.maior_salario || 0), 0);

    html += '<div class="stats-grid">';
    if (maiorSalario > 0) html += `<div class="stat-cell"><span class="stat-value">${_shortBrl(maiorSalario)}</span><span class="stat-label">Maior salario</span></div>`;
    html += `<div class="stat-cell"><span class="stat-value">${qtdEmpresas}</span><span class="stat-label">${dualLabel('Empresas onde atua','Empresas vinculadas')}</span></div>`;
    if (totalDuranteVinc > 0) html += `<div class="stat-cell stat-cell--red"><span class="stat-value">${_shortBrl(totalDuranteVinc)}</span><span class="stat-label">${dualLabel('Pago as empresas enquanto era servidor','Pago as empresas durante vinculo')}</span></div>`;
    if (totalPago > 0 && totalPago !== totalDuranteVinc) html += `<div class="stat-cell"><span class="stat-value">${_shortBrl(totalPago)}</span><span class="stat-label">Pago as empresas (total)</span></div>`;
    if (qtdSancionadas > 0) html += `<div class="stat-cell stat-cell--red"><span class="stat-value">${qtdSancionadas}</span><span class="stat-label">${dualLabel('Empresas punidas','Empresas sancionadas')}</span></div>`;
    if (qtdPgfn > 0) html += `<div class="stat-cell stat-cell--orange"><span class="stat-value">${qtdPgfn}</span><span class="stat-label">${dualLabel('Empresas devendo impostos','Empresas c/ divida PGFN')}</span></div>`;
    if (bf.length > 0) html += `<div class="stat-cell stat-cell--yellow"><span class="stat-value">Sim</span><span class="stat-label">Bolsa Familia</span></div>`;
    if (data.ceaf && data.ceaf.length) html += `<div class="stat-cell stat-cell--red"><span class="stat-value">${data.ceaf.length}</span><span class="stat-label">${dualLabel('Expulso do servico publico federal','Expulsao federal')}</span></div>`;
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
    } else {
        const cargoFallback = servidorFallback.cargo ? _stripCodePrefix(servidorFallback.cargo) : '';
        const salarioFallback = servidorFallback.salario || '';
        html += `<div class="dialog-section"><h4>${dualLabel('Dados do servidor','Resumo do servidor')}</h4>
            <div class="empresa-card">
                <div class="empresa-header">
                    <strong>${_esc(servidorNome || nome || 'Servidor')}</strong>
                    ${cpfMask ? `<span class="text-sm text-muted">CPF: ${cpfMask}</span>` : ''}
                </div>
                <div class="empresa-details">
                    ${cargoFallback ? `<span>${dualLabel('Cargo:','Cargo:')} ${_esc(cargoFallback)}</span>` : ''}
                    ${salarioFallback ? `<span>${dualLabel('Maior salario:','Maior salario:')} ${_esc(salarioFallback)}</span>` : ''}
                    ${!cnpjsNorm.length ? '<span>Nenhuma empresa vinculada foi encontrada para este servidor.</span>' : ''}
                </div>
            </div>
        </div>`;
    }

    // Empresas vinculadas (with badges)
    if (cnpjsNorm.length) {
        html += `<div class="dialog-section"><h4>${dualLabel('Empresas onde aparece como socio','Empresas vinculadas')}</h4>`;
        const empresaMap = {};
        for (const e of empresas) empresaMap[e.cnpj_basico] = e;
        html += cnpjsNorm.map(c => {
            let badges = '';
            // Sancao badges
            const sanList = sancoes[c] || [];
            const hojeIso = _todayGmt3Iso();
            const vigentes = sanList.filter(s => !s.dt_final_sancao || s.dt_final_sancao >= hojeIso);
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
            return `<div class="empresa-card severity-red">
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
            return `<div class="empresa-card severity-red">
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
                <td data-label="Data" class="stack-meta">${_fmtDate(e.data_empenho)}</td>
                <td data-label="Elemento" class="stack-title">${_esc(e.elemento_despesa || '-')}</td>
                <td data-label="Pago" class="text-right num">${_shortBrl(e.valor_pago)}</td>
                <td data-label="Modalidade" class="stack-meta">${modCell}</td>
            </tr>`;
        }).join('');
        html += `<div class="tbl-wrap"><table class="dialog-table stack-mobile">
            <thead><tr><th>Data</th><th>Elemento</th><th class="text-right">Pago</th><th>Modalidade</th></tr></thead>
            <tbody>${empRows}</tbody>
        </table></div>`;
        if (empVinc.length >= 100) html += '<p class="text-sm text-muted">Mostrando os 100 empenhos mais recentes.</p>';
        html += `<p class="text-sm text-muted" style="margin-top:.5rem">Total durante vinculo: <strong>${_shortBrl(totalVinc)}</strong></p>`;
        html += '</div>';
    }

    body.innerHTML = html;
    _reattachDialogLinks(body);
    _decorateDialogBody(body);
}

