// === components/top-servidores.js ===
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
        const cargoRaw = _val(r, cols, 'cargo') || '-';
        const cargo = _esc(cargoRaw);
        const salario = _shortBrl(_val(r, cols, 'maior_salario'));
        const qtdEmpresas = _val(r, cols, 'qtd_empresas_socio') || 0;
        const cnpjs = _val(r, cols, 'cnpjs_socio') || [];
        let badges = '';
        const ceafExpulso = _val(r, cols, 'flag_ceaf_expulso');
        if (ceafExpulso) badges += `<span class="badge badge-red">${dualLabel('Expulso do servico publico federal','Expulso da Adm. Federal (CEAF)')}</span>`;
        const totalDuranteVinculo = _val(r, cols, 'total_pago_durante_vinculo');
        if (totalDuranteVinculo > 0) {
            badges += `<span class="badge badge-red">${dualLabel(`Empresa ligada a ele recebeu ${_shortBrl(totalDuranteVinculo)} enquanto era servidor`, `Empresa recebeu ${_shortBrl(totalDuranteVinculo)} durante vinculo`)}</span>`;
        }
        if (_val(r, cols, 'flag_duplo_vinculo_estado')) badges += `<span class="badge badge-red">${dualLabel('Recebe salario em dois governos ao mesmo tempo','Tambem recebe pagamentos do governo estadual')}</span>`;
        if (_val(r, cols, 'flag_multi_empresa')) badges += `<span class="badge badge-yellow">${dualLabel(`Socio de ${qtdEmpresas || 'varias'} empresas`, `Socio de ${qtdEmpresas || 'varias'} empresas`)}</span>`;
        if (_val(r, cols, 'flag_bolsa_familia')) badges += `<span class="badge badge-yellow">${dualLabel('Recebe Bolsa Familia sendo servidor','Bolsa Familia durante vinculo')}</span>`;
        if (_val(r, cols, 'flag_alto_salario_socio')) badges += `<span class="badge badge-yellow">${dualLabel('Salario alto + socio de empresa','Salario alto + vinculo societario')}</span>`;
        const socioSancionado = _val(r, cols, 'flag_socio_sancionado');
        const socioInidoneidade = _val(r, cols, 'flag_socio_inidoneidade');
        if (socioInidoneidade) badges += `<span class="badge badge-red">${dualLabel('Socio de empresa proibida de contratar com o governo','Socio de empresa com Inidoneidade (CEIS)')}</span>`;
        else if (socioSancionado) badges += `<span class="badge badge-orange">${dualLabel('Socio de empresa sancionada pelo governo','Socio de empresa sancionada (CEIS/CNEP)')}</span>`;
        if (!badges) badges = `<span class="text-sm text-muted">${dualLabel('Sem sinais especificos detectados','Sem sinal automatico')}</span>`;

        const cpf6 = _esc(_val(r, cols, 'cpf_digitos_6') || '');
        const nomeUpper = _esc(_val(r, cols, 'nome_upper') || '');
        const hasDetail = cpf6 && nomeUpper;
        const detailAttrs = hasDetail ? ` data-cpf6="${cpf6}" data-nome-upper="${nomeUpper}" data-cnpjs='${JSON.stringify(cnpjs)}' data-nome="${nome}"` : '';
        const totalPagoRow = _val(r, cols, 'total_pago_durante_vinculo') > 0;
        const bolsaFamilia = _val(r, cols, 'flag_bolsa_familia');
        const rowClass = (ceafExpulso || totalPagoRow || socioInidoneidade) ? 'clickable-row row-sancao' : (socioSancionado || bolsaFamilia) ? 'clickable-row row-sancao-leve' : 'clickable-row';
        const cpfFmt = cpf6.length === 6 ? `***.${cpf6.slice(0,3)}.${cpf6.slice(3,6)}-**` : '';
        return `<tr data-cargo="${_esc(String(cargoRaw).toLowerCase())}" ${hasDetail ? `class="${rowClass}"` : ''}${detailAttrs}><td data-label="Servidor" class="stack-title">${nome}</td><td data-label="CPF" class="auditor-only stack-meta"><code class="text-sm">${cpfFmt}</code></td><td data-label="Cargo" class="stack-meta">${cargo}</td><td data-label="Maior salario" class="text-right num">${salario}</td><td data-label="Sinais" class="stack-badges">${badges}</td></tr>`;
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
            <h3 class="card-title title-with-action"><span class="title-text">${dualLabel('Servidores com sinais de atencao', 'Servidores com sinais de atencao')}</span> ${mobileDescToggleHtml()}</h3>
            <p class="text-muted text-sm mobile-collapsible-desc"><span class="citizen-only">Servidores com pelo menos um sinal incomum nos cruzamentos automatizados: socio de empresa, salario em mais de um governo, beneficio social irregular, ou acumulacao atipica. A Constituicao permite dois vinculos para profissionais de saude.</span><span class="auditor-only">Servidores que apresentam ao menos um sinal de risco nos cruzamentos automaticos: vinculo societario com fornecedores, duplo vinculo com o estado, recebimento de beneficio social ou acumulacao atipica. A Constituicao (art. 37, XVI) admite acumulacao para profissionais de saude.</span></p>
            ${servLegend}
        </div></div>
        <div class="table-shell js-data-table" data-page-size="10">
            <div class="table-actions">
                <input type="search" class="table-filter" placeholder="Filtrar nesta tabela" aria-label="Filtrar servidores">
                <p class="table-meta text-sm text-muted" data-table-meta></p>
            </div>
            <div class="tbl-wrap"><table class="stack-mobile">
                <thead><tr><th>Servidor</th><th class="auditor-only">CPF</th><th>Cargo</th><th class="text-right">${dualLabel('Maior salario','Maior Salario')}</th><th>${dualLabel('Sinais','Sinais de Atencao')}</th></tr></thead>
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

