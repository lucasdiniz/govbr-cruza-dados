// === components/servidor-dialog.js ===
async function openServidorDialog(cpf6, nome, cnpjs, servidorNome, servidorFallback = {}, options = {}) {
    const dialog = document.getElementById('empresa-dialog');
    if (!dialog) return;
    const fromUrl = !!options.fromUrl;
    const isInitialOpen = !dialog.open;
    const drilledFrom = isInitialOpen ? '' : _currentDialogType;
    if (dialog.open) { _dialogPush(); } else { _dialogReset(); }
    _currentDialogType = 'servidor';
    // URL state push/replace.
    if (typeof _dialogStateApply === 'function') {
        const cnpjsStr = (Array.isArray(cnpjs) ? cnpjs : [])
            .map(c => String(c || '').replace(/\D/g, '').slice(0, 8))
            .filter(Boolean).slice(0, 12).join(',');
        _dialogStateApply({
            d: 'servidor',
            cpf6: String(cpf6 || ''),
            nome: nome || '',
            snome: servidorNome || '',
            cnpjs: cnpjsStr,
        }, fromUrl, isInitialOpen);
    }
    const seq = (typeof _dialogNextSeq === 'function') ? _dialogNextSeq() : null;
    const title = dialog.querySelector('.dialog-title');
    const body = dialog.querySelector('.dialog-body');
    const cpfMask = cpf6.length === 6 ? `***.${cpf6.slice(0,3)}.${cpf6.slice(3,6)}-**` : '';
    title.textContent = cpfMask ? `${servidorNome}  —  CPF: ${cpfMask}` : servidorNome;
    body.innerHTML = '<p class="text-sm text-muted">Carregando...</p>';
    if (!dialog.open) dialog.show();
    document.body.classList.add('dialog-open');
    if (isInitialOpen) trackEvent && trackEvent('dialog-aberto', {
        tipo: 'servidor',
        cpf6: String(cpf6 || ''),
        nome: servidorNome || nome || '',
        municipio: _currentMunicipio || '',
    });
    else if (drilledFrom) trackEvent && trackEvent('dialog-aberto', {
        tipo: 'servidor',
        cpf6: String(cpf6 || ''),
        nome: servidorNome || nome || '',
        municipio: _currentMunicipio || '',
        drilled_from: drilledFrom,
    });

    const data = await _fetchServidorDetails(cpf6, nome, cnpjs, _currentMunicipio);
    if (seq !== null && typeof _dialogSeqValid === 'function' && !_dialogSeqValid(seq)) return;
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
    // BF agora pode ser array (formato antigo) ou {parcelas, stats} (novo
    // — apos commit feat(web): /api/servidor/detalhes historico completo).
    // Normaliza para acessar uniformemente parcelas[] e stats{}.
    const bfRaw = data.bolsa_familia;
    let bfParcelas = [];
    let bfStats = null;
    if (Array.isArray(bfRaw)) {
        bfParcelas = bfRaw;
    } else if (bfRaw && typeof bfRaw === 'object') {
        bfParcelas = Array.isArray(bfRaw.parcelas) ? bfRaw.parcelas : [];
        bfStats = bfRaw.stats || null;
    }
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
    // Stat BF no overview:
    //   - qtd_meses = quantos meses distintos tem registro de pagamento
    //   - maior_valor = maior parcela individual recebida
    // Mostra "N meses · R$ MAIOR" em vez do total — total fica na secao
    // detalhada abaixo, evitando duplicidade.
    if (bfParcelas.length > 0) {
        const qtdMesesBF = bfStats ? bfStats.qtd_meses : new Set(bfParcelas.map(p => p.mes_competencia)).size;
        const maiorValorBF = bfParcelas.reduce((m, p) => Math.max(m, p.valor_parcela || 0), 0);
        html += `<div class="stat-cell stat-cell--yellow">`
            + `<span class="stat-value">${qtdMesesBF} ${qtdMesesBF === 1 ? 'mes' : 'meses'}</span>`
            + `<span class="stat-label">${dualLabel('Recebeu Bolsa Familia (maior parcela: ' + _shortBrl(maiorValorBF) + ')','Bolsa Familia — maior parcela: ' + _shortBrl(maiorValorBF))}</span>`
            + `</div>`;
    }
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

    // Bolsa Familia: secao dedicada com stats agregados + grade mes-a-mes
    // visivel por default (sem <details> wrapper). Janela: a partir de
    // janeiro/2026 (primeiro mes onde temos snapshots cumulativos via
    // framework incremental — meses anteriores so existem se ja foram
    // carregados). Padrao: meses dentro do vinculo TCE-PB com parcela =>
    // highlight red badge. dualLabel cidadao/auditor.
    //
    // Mes minimo da grade (BF_GRID_MIN_YM): controla o quao longe pra tras
    // mostramos meses "sem registro". Atualmente 2026-01 porque o framework
    // incremental comecou a carregar a partir desse mes. Quando carregarmos
    // historico (e.g., 2023-03+), atualizar essa constante.
    const BF_GRID_MIN_YM = 202601;
    if (bfParcelas.length || (bfRaw && Array.isArray(bfRaw.meses_disponiveis))) {
        // bfStats pode ser null (caso "servidor sem parcela mas com vinculo")
        const stats = bfStats || (bfParcelas.length ? {
            qtd_parcelas: bfParcelas.length,
            qtd_meses: bfParcelas.length,
            total_recebido: bfParcelas.reduce((s, b) => s + (b.valor_parcela || 0), 0),
            primeiro_mes: bfParcelas[bfParcelas.length - 1]?.mes_competencia || null,
            ultimo_mes: bfParcelas[0]?.mes_competencia || null,
            qtd_durante_vinculo: 0,
            total_durante_vinculo: 0,
        } : {
            qtd_parcelas: 0, qtd_meses: 0, total_recebido: 0,
            primeiro_mes: null, ultimo_mes: null,
            qtd_durante_vinculo: 0, total_durante_vinculo: 0,
        });
        const hasDuranteVinculo = (stats.qtd_durante_vinculo || 0) > 0;
        html += `<div class="dialog-section"><h4>${dualLabel('Recebeu Bolsa Familia','Bolsa Familia — historico completo')}</h4>`;
        // Stats overview cells (secao propria)
        html += '<div class="stats-grid">';
        html += `<div class="stat-cell"><span class="stat-value">${_shortBrl(stats.total_recebido)}</span><span class="stat-label">${dualLabel('Total recebido','Total acumulado')}</span></div>`;
        html += `<div class="stat-cell"><span class="stat-value">${stats.qtd_meses}</span><span class="stat-label">${dualLabel('Meses com pagamento','Meses competencia distintos')}</span></div>`;
        if (stats.primeiro_mes && stats.ultimo_mes) {
            html += `<div class="stat-cell"><span class="stat-value">${_fmtDate(stats.primeiro_mes)} &rarr; ${_fmtDate(stats.ultimo_mes)}</span><span class="stat-label">${dualLabel('Periodo','Janela temporal')}</span></div>`;
        }
        if (hasDuranteVinculo && Math.abs((stats.total_durante_vinculo || 0) - (stats.total_recebido || 0)) > 0.01) {
            // So mostra "Recebido enquanto servidor" se for diferente do total
            // (caso contrario, todos os meses estao no vinculo => stats
            // sao iguais e duplicar o valor confunde).
            html += `<div class="stat-cell stat-cell--red"><span class="stat-value">${_shortBrl(stats.total_durante_vinculo)}</span><span class="stat-label">${dualLabel('Recebido enquanto servidor','Recebido durante vinculo TCE-PB')}</span></div>`;
        } else if (hasDuranteVinculo) {
            // Todos meses sao "durante vinculo" — destaca o total ja existente
            // com badge red em vez de duplicar.
            html += `<div class="stat-cell stat-cell--red"><span class="stat-value">100%</span><span class="stat-label">${dualLabel('Recebeu enquanto servidor','Todo BF durante vinculo TCE-PB')}</span></div>`;
        }
        html += '</div>';
        // Constroi grade mes-a-mes:
        // - Janela: max(BF_GRID_MIN_YM, primeiro_mes BF) ate
        //   max(ultimo_mes BF, ultimo mes do vinculo).
        // - Para cada mes, mostra parcelas que caem nele OU placeholder
        //   "Sem registro" se nao houver.
        const vincStart = vinculos.length ? vinculos
            .map(v => (v.primeiro_registro || (v.data_admissao || '').slice(0, 7).replace('-', '')) || '')
            .filter(Boolean).sort()[0] : null;
        const vincEnd = vinculos.length ? vinculos
            .map(v => (v.ultimo_registro || '').replace('-', ''))
            .filter(Boolean).sort().slice(-1)[0] : null;
        // Helpers
        const ymToInt = (ym) => parseInt(String(ym || '').replace('-', '').slice(0, 6), 10);
        const intToYm = (n) => `${Math.floor(n/100)}${String(n%100).padStart(2,'0')}`;
        const ymNext = (n) => {
            const y = Math.floor(n/100), m = n % 100;
            return m === 12 ? (y+1) * 100 + 1 : n + 1;
        };
        // Start: nunca anterior ao mes minimo (evita listar 30+ meses vazios
        // ate o framework carregar historico). Mas se BF tem parcela mais
        // antiga, comeca dela.
        let gridStart = Math.max(BF_GRID_MIN_YM, ymToInt(stats.primeiro_mes) || BF_GRID_MIN_YM);
        let gridEnd = ymToInt(stats.ultimo_mes);
        if (vincEnd) {
            const v = ymToInt(vincEnd);
            if (v && v > gridEnd) gridEnd = v;
        }
        // Set de meses_competencia com snapshot carregado (vem do endpoint).
        // Permite distinguir 3 estados:
        //   - Tem snapshot + tem parcela: linha normal
        //   - Tem snapshot + sem parcela: "Nao recebeu BF" (afirma)
        //   - Sem snapshot: "Sem dados disponiveis ainda"
        const mesesDisponiveis = new Set(
            (bfRaw && Array.isArray(bfRaw.meses_disponiveis))
                ? bfRaw.meses_disponiveis.map(String) : []
        );
        // Clamp gridEnd ao ultimo snapshot BF disponivel. Razao: se vinculo
        // TCE-PB tem ano_mes mais recente que o ultimo BF carregado (e.g.,
        // vinculo 2026-03 mas BF carregado ate 2026-02), NAO mostrar esses
        // meses na grade — evita renderizar 202603 enquanto ETL incremental
        // ainda nao commitou aquele snapshot. Versao anterior usava `if (... >
        // gridEnd) gridEnd = ...` (so estendia), o que permitia gridEnd ficar
        // alem do max disponivel quando vincEnd era recente.
        if (mesesDisponiveis.size) {
            const maxDisponivelInt = Math.max(...[...mesesDisponiveis].map(ymToInt).filter(Boolean));
            gridEnd = maxDisponivelInt;
        }
        // Indexar parcelas por mes_competencia
        const parcelasPorMes = {};
        for (const p of bfParcelas) {
            const k = String(p.mes_competencia || '');
            if (!parcelasPorMes[k]) parcelasPorMes[k] = [];
            parcelasPorMes[k].push(p);
        }
        // Range vinculo (para marcar visualmente)
        const vincStartInt = vincStart ? ymToInt(vincStart) : null;
        const vincEndInt = vincEnd ? ymToInt(vincEnd) : null;
        const inVinculo = (n) => vincStartInt && vincEndInt && n >= vincStartInt && n <= vincEndInt;

        // Renderizar tabela DIRETO (sem <details>) — UX request: nao esconder.
        // Cobertura atual: BF_GRID_MIN_YM em diante (snapshots cumulativos
        // via ETL incremental). Meses anteriores nao tem dado, por isso
        // nao mostramos linhas vazias para 2023-03..2025-12 — seria ruido.
        const coberturaLabel = `Cobertura: ${_fmtDate(String(BF_GRID_MIN_YM))} em diante. Meses anteriores nao estao disponiveis ainda.`;
        const coberturaTec = `Periodo coberto: ${_fmtDate(String(BF_GRID_MIN_YM))} em diante.`;
        html += `<p class="bf-cobertura text-xs text-muted"><span class="citizen-only">${coberturaLabel}</span><span class="auditor-only">${coberturaTec}</span></p>`;
        html += `<table class="bf-parcelas-table">
            <thead><tr>
                <th>${dualLabel('Mes','Competencia')}</th>
                <th>${dualLabel('Mes referencia','Referencia')}</th>
                <th>${dualLabel('Cidade','Municipio')}</th>
                <th>${dualLabel('Valor','Valor parcela')}</th>
            </tr></thead>
            <tbody>`;
        if (gridStart && gridEnd && gridStart <= gridEnd) {
            // Iterar do mais recente para o mais antigo (mesma ordem da lista)
            const meses = [];
            let cur = gridStart;
            let safety = 0;
            while (cur <= gridEnd && safety < 600) {
                meses.push(cur);
                cur = ymNext(cur);
                safety++;
            }
            meses.reverse();  // mais recente primeiro
            html += meses.map(mInt => {
                const k = intToYm(mInt);
                const parcelas = parcelasPorMes[k];
                const inVinc = inVinculo(mInt);
                const temSnapshot = mesesDisponiveis.has(k);
                if (parcelas && parcelas.length) {
                    // Pode haver multiplas parcelas no mesmo mes_competencia
                    // (mes_referencia diferentes — recebimentos retroativos).
                    // Renderiza 1 linha "header" com mes_competencia + badge,
                    // + linhas indentadas para cada (mes_referencia, valor)
                    // distintos.
                    //
                    // IMPORTANTE: title= NAO pode conter dualLabel() porque
                    // este retorna HTML <span>; quebraria o attr. Usar
                    // texto plano + dualLabel APENAS no conteudo do badge.
                    const anyDuranteVinculo = parcelas.some(p => p.durante_vinculo);
                    const badgeTitle = "Parcela dentro do periodo do vinculo TCE-PB";
                    const totalNoMes = parcelas.reduce((s, p) => s + (p.valor_parcela || 0), 0);
                    const badge = anyDuranteVinculo
                        ? ` <span class="badge badge-red" title="${badgeTitle}">${dualLabel('Era servidor','Durante vinculo')}</span>`
                        : '';
                    // Cabecalho do mes
                    let html2 = `<tr class="bf-mes-header${anyDuranteVinculo ? ' row-flag-red' : ''}">
                        <td><strong>${_fmtDate(k)}</strong>${badge}</td>
                        <td class="text-sm text-muted">${parcelas.length > 1 ? parcelas.length + ' parcelas (retroativas)' : ''}</td>
                        <td>${_esc(parcelas[0].nm_municipio || '-')}${parcelas[0].uf ? ' / ' + _esc(parcelas[0].uf) : ''}</td>
                        <td><strong>${_shortBrl(totalNoMes)}</strong></td>
                    </tr>`;
                    // Linhas detalhe (so se mais de 1 parcela)
                    if (parcelas.length > 1) {
                        html2 += parcelas.map(b => {
                            return `<tr class="bf-mes-detail">
                                <td></td>
                                <td class="text-sm text-muted">&hookrightarrow; ${dualLabel('referente a','ref.')} ${_fmtDate(b.mes_referencia)}</td>
                                <td></td>
                                <td>${_shortBrl(b.valor_parcela)}</td>
                            </tr>`;
                        }).join('');
                    }
                    return html2;
                }
                // Sem parcela neste mes — distinguir 3 estados
                const labelMes = _fmtDate(k);
                if (!temSnapshot) {
                    // Sem dados disponiveis (snapshot nao carregado ainda)
                    return `<tr class="row-empty row-empty--sem-snapshot">
                        <td>${labelMes}</td>
                        <td colspan="3"><span class="text-xs text-muted">${dualLabel('Sem dados disponiveis ainda','Snapshot BF nao carregado')}</span></td>
                    </tr>`;
                }
                // Tem snapshot e nao recebeu — afirmar
                const cls = inVinc ? ' class="row-empty row-empty--vinculo"' : ' class="row-empty"';
                const subt = inVinc
                    ? `<span class="text-xs text-muted">${dualLabel('Era servidor neste mes — nao recebeu BF','Em vinculo — sem parcela')}</span>`
                    : `<span class="text-xs text-muted">${dualLabel('Nao recebeu BF neste mes','Sem parcela')}</span>`;
                return `<tr${cls}>
                    <td>${labelMes}</td>
                    <td colspan="3">${subt}</td>
                </tr>`;
            }).join('');
        }
        html += `</tbody></table>`;
        html += '</div>';
    }

    // CEAF - Expulsoes da Administracao Federal
    if (data.ceaf && data.ceaf.length) {
        // Link pro Portal da Transparencia (busca por nome — CPF mascarado
        // nao serve pra deep-link). Mesmo padrao que CEIS/CNEP em
        // fornecedor-dialog.js linha ~248.
        const nomeBusca = (servidorNome || nome || '').trim();
        const ceafUrl = nomeBusca
            ? `https://portaldatransparencia.gov.br/sancoes/consulta?cadastro=3&nomeSancionado=${encodeURIComponent(nomeBusca)}`
            : '';
        const ceafLink = ceafUrl
            ? ` <a href="${ceafUrl}" target="_blank" rel="noopener" class="ext-link-inline" title="Ver no Portal da Transparencia">&#8599;</a>`
            : '';
        html += `<div class="dialog-section"><h4>${dualLabel('Expulsoes do servico publico federal','Expulsoes da Administracao Federal (CEAF)')}${ceafLink}</h4>`;
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

