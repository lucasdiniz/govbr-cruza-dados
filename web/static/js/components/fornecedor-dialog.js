// === components/fornecedor-dialog.js ===
async function openFornecedorDialog(cnpjBasico, fornecedorNome, municipioOverride, switchMun, nomeCredor, cpfCnpj) {
    const dialog = document.getElementById('empresa-dialog');
    if (!dialog) return;
    const exactDoc = String(cpfCnpj || '').replace(/\D/g, '');
    if (exactDoc.length !== 14) {
        if (typeof showToast === 'function') {
            showToast('Detalhes indisponiveis: esta linha nao traz CNPJ completo.', 3200);
        }
        return;
    }
    if (!switchMun) {
        if (dialog.open) { _dialogPush(); } else { _dialogReset(); }
    } else {
        _dialogPush();
    }
    const title = dialog.querySelector('.dialog-title');
    const body = dialog.querySelector('.dialog-body');
    title.textContent = fornecedorNome || 'Fornecedor';
    body.innerHTML = '<p class="text-sm text-muted">Carregando...</p>';
    if (!dialog.open) dialog.show();
    document.body.classList.add('dialog-open');

    const viewMunicipio = municipioOverride || _currentMunicipio;
    const data = await _fetchFornecedorDetails(cnpjBasico, viewMunicipio, nomeCredor, cpfCnpj);
    let html = _historyNote();

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
    } else {
        const cnpjFmt = _formatCnpj(cnpjBasico, exactDoc);
        html += `<div class="dialog-section"><h4>${dualLabel('Dados da empresa','Identificacao do fornecedor')}</h4>
            <div class="empresa-card empresa-missing">
                <div class="empresa-header">
                    <strong>${_esc(fornecedorNome || nomeCredor || 'Fornecedor')}</strong>
                    <code class="auditor-only">${cnpjFmt}</code>
                </div>
                <div class="empresa-details">
                    <span>Cadastro completo da empresa indisponivel na base RFB para este CNPJ.</span>
                </div>
            </div>
        </div>`;
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
            const vigente = !s.dt_final_sancao || s.dt_final_sancao >= _todayGmt3Iso();
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

    body.innerHTML = html;
    _reattachDialogLinks(body);
    _decorateDialogBody(body);
    if (switchMun) {
        _activateDialogSection(body, 'forn-empenhos', { focus: false, scroll: false, smooth: false });
        const empSection = body.querySelector('#forn-empenhos');
        if (empSection) empSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

