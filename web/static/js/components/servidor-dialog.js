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
    const vinculosFederais = data.vinculos_federais || [];
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
    if (vinculosFederais.length) html += `<div class="stat-cell stat-cell--yellow"><span class="stat-value">${vinculosFederais.length}</span><span class="stat-label">${dualLabel('Cadastro federal','Vinculos SIAPE')}</span></div>`;
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
    if (vinculos.length || vinculosFederais.length) {
        html += `<div class="dialog-section"><h4>${dualLabel('Empregos publicos','Vinculos como servidor')}</h4>`;
        if (vinculos.length) {
            html += `<p class="text-xs text-muted" style="margin:.2rem 0 .5rem">${dualLabel('Vinculos municipais informados ao TCE-PB.','Vinculos municipais — TCE-PB')}</p>`;
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
        }
        if (vinculosFederais.length) {
            html += `<p class="text-xs text-muted" style="margin:.75rem 0 .5rem">${dualLabel('Tambem aparece no cadastro federal SIAPE. Acumulacao pode ser permitida em alguns casos.','Vinculos federais — SIAPE/Portal da Transparencia')}</p>`;
            html += vinculosFederais.map(v => {
                const cargoRaw = v.descricao_cargo || v.funcao || v.atividade || '';
                const cargoStripped = _stripCodePrefix(cargoRaw) || '-';
                const org = v.org_exercicio || v.org_lotacao || v.orgsup_exercicio || 'SIAPE';
                const remun = v.remuneracao_apos_deducoes || v.remuneracao_basica_bruta || 0;
                const competencia = (v.remuneracao_ano && v.remuneracao_mes)
                    ? `${String(v.remuneracao_mes).padStart(2, '0')}/${v.remuneracao_ano}`
                    : '';
                return `<div class="empresa-card severity-yellow">
                    <div class="empresa-header">
                        <strong>${_esc(org)}</strong>
                        <span class="badge badge-yellow">SIAPE</span>
                    </div>
                    <div class="empresa-details">
                        <span><span class="citizen-only">${_esc(cargoStripped)}</span><span class="auditor-only">${_esc(cargoRaw || '-')}</span></span>
                        ${v.uorg_exercicio ? `<span>${dualLabel('Unidade:','UORG exercicio:')} ${_esc(v.uorg_exercicio)}</span>` : ''}
                        ${v.uf_exercicio ? `<span>UF exercicio: ${_esc(v.uf_exercicio)}</span>` : ''}
                        ${v.tipo_vinculo ? `<span>${dualLabel('Tipo de vinculo:','Tipo vinculo:')} ${_esc(v.tipo_vinculo)}</span>` : ''}
                        ${v.situacao_vinculo ? `<span>${dualLabel('Situacao:','Situacao vinculo:')} ${_esc(v.situacao_vinculo)}</span>` : ''}
                        ${v.regime_juridico ? `<span class="auditor-only">Regime: ${_esc(v.regime_juridico)}</span>` : ''}
                        ${v.jornada_trabalho ? `<span class="auditor-only">Jornada: ${_esc(v.jornada_trabalho)}</span>` : ''}
                        ${v.dt_ingresso_orgao ? `<span>${dualLabel('Entrada no orgao:','Ingresso orgao:')} ${_fmtDate(v.dt_ingresso_orgao)}</span>` : ''}
                        ${remun ? `<span>${dualLabel('Remuneracao federal:','Remuneracao SIAPE:')} ${_shortBrl(remun)}${competencia ? ` (${competencia})` : ''}</span>` : ''}
                    </div>
                </div>`;
            }).join('');
        }
        // Expandable com regras de acumulacao de cargos publicos. So renderiza
        // quando ha duplo vinculo de fato (municipal + federal SIAPE). Reutiliza
        // o estilo .bf-regras-info (generico apesar do prefixo) e dispara o
        // mesmo evento Umami 'secao-toggle' com section='duplo-vinculo-regras'.
        if (vinculos.length && vinculosFederais.length) {
            html += `<details class="bf-regras-info" data-duplo-vinculo-regras>
                <summary class="bf-regras-info__summary">
                    <span class="bf-regras-info__title">${dualLabel('Pode acumular dois cargos publicos?','Regras de acumulacao de cargos publicos')}</span>
                    <span class="bf-regras-info__chevron" aria-hidden="true">›</span>
                </summary>
                <div class="bf-regras-info__body">
                    <div class="citizen-only">
                        <p>A regra geral da Constituicao e que <strong>nao pode acumular dois empregos publicos</strong> — municipal, estadual, federal, autarquia, empresa publica ou estatal. Quem entra em dois cargos sem se enquadrar em uma das excecoes pode ser <strong>demitido por improbidade</strong> e tem que devolver o que recebeu a mais.</p>
                        <p><strong>Excecoes permitidas</strong> (somente nestes casos, com horarios comprovadamente compativeis e <strong>respeitando o teto do STF</strong>: R$ 46.366,19 em 2024):</p>
                        <ul class="bf-regras-info__lista">
                            <li><strong>Dois cargos de professor</strong>.</li>
                            <li><strong>Um cargo de professor + um cargo tecnico ou cientifico</strong>.</li>
                            <li><strong>Dois cargos privativos da area da saude</strong> com profissoes regulamentadas (medico, enfermeiro, dentista, farmaceutico, psicologo etc).</li>
                        </ul>
                        <p>Mesmo nas excecoes, a soma das remuneracoes <strong>nao pode ultrapassar o teto do STF</strong>. Quem ja recebe acima do teto so pode acumular se devolver o que excede. Acumular fora das excecoes da <strong>demissao + ressarcimento + acao por improbidade</strong>.</p>
                        <p class="bf-regras-info__fonte">Constituicao Federal, Art. 37, incisos XI e XVI.</p>
                    </div>
                    <div class="auditor-only">
                        <p><strong>Regra geral (CF/88 Art. 37, XVI):</strong> vedada a acumulacao remunerada de cargos publicos. Aplica-se a empregos e funcoes publicas, abrangendo autarquias, fundacoes, empresas publicas, sociedades de economia mista e subsidiarias da Uniao, Estados, DF e Municipios.</p>
                        <p><strong>Excecoes (havendo compatibilidade de horarios):</strong></p>
                        <ul class="bf-regras-info__lista">
                            <li>Dois cargos de <strong>professor</strong> (alinea a).</li>
                            <li>Um cargo de <strong>professor + um tecnico ou cientifico</strong> (alinea b).</li>
                            <li>Dois cargos privativos de <strong>profissionais de saude</strong> com profissoes regulamentadas (alinea c, EC 34/2001).</li>
                        </ul>
                        <p><strong>Teto remuneratorio (CF/88 Art. 37, XI):</strong> subsidio mensal dos Ministros do STF (R$ 46.366,19 desde fev/2024, MP 1.230/2024). Aplica-se a soma de todas as remuneracoes acumulaveis, incluindo proventos de inatividade.</p>
                        <p><strong>Compatibilidade de horarios:</strong> jornadas semanais devem permitir o exercicio efetivo dos dois cargos. STF (RE 1.176.440, Tema 1.072) afastou limite generico de 60h/sem — analise caso a caso, mas jornadas que comprovadamente impossibilitem o exercicio sao causa de demissao.</p>
                        <p><strong>Sancao em caso de acumulacao ilicita:</strong> demissao por improbidade administrativa (Lei 8.112/90, Art. 132, XII; Lei 8.429/92, Art. 11). Servidor notificado pode optar por um dos cargos em ate 10 dias; opcao pos-prazo implica demissao do mais recente + ressarcimento ao erario.</p>
                        <p class="bf-regras-info__fonte">CF/88 Art. 37, XI e XVI; Lei 8.112/90 Art. 118-120 e 132; Sumula 246/TCU; EC 19/98 e EC 34/2001.</p>
                    </div>
                </div>
            </details>`;
        }
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
    // carregados). Padrao: parcela recebida durante vinculo ativo =>
    // highlight red badge. dualLabel cidadao/auditor.
    //
    // Mes minimo da grade (BF_GRID_MIN_YM): controla o quao longe pra tras
    // mostramos meses "sem registro". Atualmente 2026-01 porque o framework
    // incremental comecou a carregar a partir desse mes. Quando carregarmos
    // historico (e.g., 2023-03+), atualizar essa constante.
    const BF_GRID_MIN_YM = 202601;
    if (bfParcelas.length > 0) {
        // bfStats pode ser null no formato antigo; com parcelas, recalculamos
        // um resumo minimo no frontend.
        const stats = bfStats || {
            qtd_parcelas: bfParcelas.length,
            qtd_meses: bfParcelas.length,
            total_recebido: bfParcelas.reduce((s, b) => s + (b.valor_parcela || 0), 0),
            primeiro_mes: bfParcelas[bfParcelas.length - 1]?.mes_competencia || null,
            ultimo_mes: bfParcelas[0]?.mes_competencia || null,
            qtd_durante_vinculo: 0,
            total_durante_vinculo: 0,
        };
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
            html += `<div class="stat-cell stat-cell--red"><span class="stat-value">${_shortBrl(stats.total_durante_vinculo)}</span><span class="stat-label">${dualLabel('Recebido enquanto servidor','Recebido enquanto era servidor publico')}</span></div>`;
        }
        html += '</div>';

        // Texto informativo sobre as regras do PBF (versao cidadao +
        // auditor). Inserido logo apos os stats agregados — especialmente
        // relevante quando o badge vermelho "Recebeu enquanto servidor"
        // aparece, pois contextualiza por que ter emprego + BF eh
        // potencialmente problematico. Fontes confirmadas: gov.br/mds
        // (FAQ oficial e pagina principal do PBF) e Lei 14.601/2023.
        // Importante: regra mudou em jul/2025 — agora sao 3 categorias
        // (12m para renda instavel, 2m para renda fixa, 24m grandfathered).
        // CadUnico recebe alimentacao automatica de renda formal via
        // eSocial/RAIS/CAGED desde 2023, entao omissao eh detectada.
        html += `<details class="bf-regras-info" data-bf-regras>
            <summary class="bf-regras-info__summary">
                <span class="bf-regras-info__title">Regras para recebimento do Bolsa Familia</span>
                <span class="bf-regras-info__chevron" aria-hidden="true">›</span>
            </summary>
            <div class="bf-regras-info__body">
                <div class="citizen-only">
                    <p>O Bolsa Familia e para familias com renda baixa — ate <strong>R$ 218 por pessoa, por mes</strong>. Quando alguem da familia consegue emprego ou a renda aumenta, e obrigatorio atualizar o Cadastro Unico.</p>
                    <p>Se a renda por pessoa passar de R$ 218 mas ficar <strong>ate R$ 706</strong>, a familia entra na <strong>Regra de Protecao</strong>: continua recebendo <strong>metade</strong> do beneficio por <strong>ate 12 meses</strong> (caso tipico de emprego formal). Acima de R$ 706, o beneficio e cancelado.</p>
                    <p>Se mais tarde a renda cair de novo abaixo de R$ 218, a familia pode voltar ao programa com prioridade em ate <strong>3 anos</strong> (Retorno Garantido). <strong>Receber sem comunicar emprego ou renda extra da bloqueio, devolucao do dinheiro e pode virar processo por estelionato</strong> — o governo cruza automaticamente o CadUnico com eSocial, RAIS e CAGED.</p>
                    <p class="bf-regras-info__fonte">Regras do Programa Bolsa Familia (Lei 14.601/2023).</p>
                </div>
                <div class="auditor-only">
                    <p><strong>Programa Bolsa Familia (Lei 14.601, de 19/06/2023):</strong> renda per capita maxima de R$ 218/mes para elegibilidade.</p>
                    <p><strong>Regra de Protecao (vigente desde jul/2025 — 3 categorias):</strong> familia que ultrapassa R$ 218 mas fica ate R$ 706 per capita mantem 50% do beneficio por:</p>
                    <ul class="bf-regras-info__lista">
                        <li><strong>12 meses</strong> — renda instavel (emprego formal, MEI, autonomo);</li>
                        <li><strong>2 meses</strong> — renda fixa (aposentadoria, BPC, pensao);</li>
                        <li><strong>24 meses</strong> com teto R$ 759 — direito adquirido para familias que ja estavam na regra ate jun/2025.</li>
                    </ul>
                    <p><strong>Retorno Garantido:</strong> reingresso prioritario em ate 3 anos se renda cair a &le; R$ 218.</p>
                    <p><strong>Cruzamentos automaticos</strong> alimentam o CadUnico com renda formal (eSocial/RAIS/CAGED, INSS, RFB). Deteccao de irregularidade pela Rede Federal de Fiscalizacao (art. 13, Lei 14.601/2023) implica cancelamento, devolucao dos valores e eventual responsabilizacao penal por estelionato (CP art. 171).</p>
                </div>
            </div>
        </details>`;
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
        //   - Tem snapshot + sem parcela: "Nao recebeu Bolsa Familia" (afirma)
        //   - Sem snapshot: "Sem dados disponiveis ainda"
        const mesesDisponiveis = new Set(
            (bfRaw && Array.isArray(bfRaw.meses_disponiveis))
                ? bfRaw.meses_disponiveis.map(String) : []
        );
        // Estende gridEnd ate o ultimo snapshot disponivel (para mostrar
        // meses recentes que ainda nao tem parcela mas TEMOS snapshot).
        if (mesesDisponiveis.size) {
            const maxDisponivelInt = Math.max(...[...mesesDisponiveis].map(ymToInt).filter(Boolean));
            if (maxDisponivelInt > gridEnd) gridEnd = maxDisponivelInt;
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
                    const badgeTitle = "Parcela recebida enquanto era servidor publico";
                    const totalNoMes = parcelas.reduce((s, p) => s + (p.valor_parcela || 0), 0);
                    const badge = anyDuranteVinculo
                        ? ` <span class="badge badge-red" title="${badgeTitle}">${dualLabel('Era servidor','Durante vinculo')}</span>`
                        : '';
                    // Coluna "Mes referencia" no header:
                    //   - se ha varias parcelas no mes (retroativos), mostra "N parcelas
                    //     (retroativas)" e os mes_referencia individuais vao nas detail rows;
                    //   - se ha so 1 parcela, mostra direto o mes_referencia formatado dela
                    //     (caso comum — sem isso a coluna ficaria sempre vazia).
                    let refLabel;
                    if (parcelas.length > 1) {
                        refLabel = parcelas.length + ' parcelas (retroativas)';
                    } else {
                        const ref = parcelas[0].mes_referencia;
                        refLabel = ref ? _fmtDate(ref) : '';
                    }
                    // Cabecalho do mes
                    let html2 = `<tr class="bf-mes-header${anyDuranteVinculo ? ' row-flag-red' : ''}">
                        <td><strong>${_fmtDate(k)}</strong>${badge}</td>
                        <td class="text-sm text-muted">${refLabel}</td>
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
                    ? `<span class="text-xs text-muted">${dualLabel('Era servidor neste mes — nao recebeu Bolsa Familia','Vinculo ativo neste mes — sem parcela do Bolsa Familia')}</span>`
                    : `<span class="text-xs text-muted">${dualLabel('Nao recebeu Bolsa Familia neste mes','Sem parcela')}</span>`;
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

    // Umami tracking pro details colapsavel das regras do BF. Usa o mesmo
    // event name 'secao-toggle' do components/collapsible.js (kebab-case,
    // sem prefix de pagina) com {section: 'bf-regras', action}. Anexado
    // inline porque o details eh dialog-rendered, sem data-collapsible-id
    // — entao o global initCollapsibles() nao o pega (evita duplo handler).
    const regrasDetails = body.querySelector('details.bf-regras-info[data-bf-regras]');
    if (regrasDetails) {
        regrasDetails.addEventListener('toggle', () => {
            if (typeof trackEvent === 'function') {
                trackEvent('secao-toggle', {
                    section: 'bf-regras',
                    action: regrasDetails.open ? 'open' : 'close',
                });
            }
        });
    }

    const duploRegrasDetails = body.querySelector('details.bf-regras-info[data-duplo-vinculo-regras]');
    if (duploRegrasDetails) {
        duploRegrasDetails.addEventListener('toggle', () => {
            if (typeof trackEvent === 'function') {
                trackEvent('secao-toggle', {
                    section: 'duplo-vinculo-regras',
                    action: duploRegrasDetails.open ? 'open' : 'close',
                });
            }
        });
    }
}

