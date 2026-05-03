// === components/result-table.js ===
function buildResultTable(queryId, columns, rows, municipio) {
    const labelPairs = columns.map(_columnLabelPair);
    const headerCells = columns.map((col, idx) => {
        const labels = labelPairs[idx];
        const cls = labels.auditorOnly ? ' class="auditor-only"' : '';
        const html = labels.auditorOnly || labels.citizen === labels.auditor
            ? _esc(labels.auditor)
            : `<span class="citizen-only">${_esc(labels.citizen)}</span><span class="auditor-only">${_esc(labels.auditor)}</span>`;
        return `<th${cls}>${html}</th>`;
    }).join('');

    // Auto-detect clickable columns for dialog reuse
    const iCnpjBasico = columns.indexOf('cnpj_basico');
    const iCpfCnpj = columns.findIndex(c => c === 'cpf_cnpj' || c === 'cpf_cnpj_sancionado' || c === 'cpfcnpj_contratado' || c === 'cpf_cnpj_proponente');
    const iCnpjCompleto = columns.indexOf('cnpj_completo');
    const iNomeCredor = columns.findIndex(c => c === 'nome_credor' || c === 'razao_social' || c === 'nome_sancionado' || c === 'nome_contratado' || c === 'nome_proponente');
    const iCpf6 = columns.indexOf('cpf_digitos_6');
    const iNomeUpper = columns.indexOf('nome_upper');
    const iNomeServidor = columns.indexOf('nome_servidor');
    const iLicNum = columns.indexOf('numero_licitacao');
    const iLicAno = columns.indexOf('ano_licitacao');
    const iLicMod = columns.indexOf('modalidade');
    const iNomeCredorExact = columns.indexOf('nome_credor');
    const hasFornecedor = iCnpjBasico >= 0 || iCpfCnpj >= 0 || iCnpjCompleto >= 0;
    const hasServidor = iCpf6 >= 0 && (iNomeUpper >= 0 || iNomeServidor >= 0);
    const hasLicitacao = iLicNum >= 0;

    // Row highlight: detect abrangencia + categoria_sancao for sanction severity
    const iAbrangencia = columns.indexOf('abrangencia');
    const iCategoria = columns.indexOf('categoria_sancao');

    // Sort by severity when abrangencia column is present: red first, yellow next, rest last
    if (iAbrangencia >= 0) {
        rows = [...rows].sort((a, b) => {
            const aAbr = String(a[iAbrangencia] || '');
            const aCat = iCategoria >= 0 ? String(a[iCategoria] || '') : '';
            const bAbr = String(b[iAbrangencia] || '');
            const bCat = iCategoria >= 0 ? String(b[iCategoria] || '') : '';
            const aRed = /inidone/i.test(aCat) || /Nacional/i.test(aAbr) || /Todas as Esferas/i.test(aAbr);
            const bRed = /inidone/i.test(bCat) || /Nacional/i.test(bAbr) || /Todas as Esferas/i.test(bAbr);
            const aYellow = !aRed && !!aAbr;
            const bYellow = !bRed && !!bAbr;
            const aScore = aRed ? 0 : aYellow ? 1 : 2;
            const bScore = bRed ? 0 : bYellow ? 1 : 2;
            return aScore - bScore;
        });
    }

    const bodyRows = rows.map(row => {
        let cells = row.map((val, ci) => {
            const col = columns[ci] || '';
            const labels = labelPairs[ci] || _columnLabelPair(col);
            const label = _esc(labels.citizen || labels.auditor || col);
            const classes = [ci === 0 ? 'stack-title' : 'stack-meta'];
            if (labels.auditorOnly) classes.push('auditor-only');
            const isNumericColumn = col.startsWith('valor') || col.startsWith('total') || col === 'capital_social' ||
                col === 'maior_salario' || col === 'salario' || col.startsWith('pct') || col.startsWith('qtd') ||
                col === 'empenhos';
            if (isNumericColumn && ci !== 0) classes.push('num');
            const td = (html, sortValue) => {
                const sortAttr = sortValue === undefined || sortValue === null ? '' : ` data-sort="${_esc(sortValue)}"`;
                return `<td data-label="${label}" class="${classes.join(' ')}"${sortAttr}>${html}</td>`;
            };
            if (val === null || val === undefined) return td('-');
            if (typeof val === 'boolean') return td(val ? 'Sim' : 'Nao');
            if (Array.isArray(val)) return td(val.map(item => _esc(item)).join(', '));
            const rawDigits = String(val || '').replace(/\D/g, '');
            if ((col.startsWith('dt_') || col.startsWith('data_')) && typeof val === 'string') {
                return td(_esc(_fmtDate(val)), val);
            }
            if ((col === 'cpf_cnpj' || col.startsWith('cpf_cnpj') || col === 'cpfcnpj_contratado' || col === 'cnpj_completo') && rawDigits.length === 14) {
                return td(_formatCnpj(rawDigits.slice(0, 8), rawDigits), rawDigits);
            }
            if ((col === 'cpf_cnpj' || col.startsWith('cpf_cnpj') || col === 'cpfcnpj_contratado') && rawDigits.length === 11) {
                return td(`***.${rawDigits.slice(3, 6)}.${rawDigits.slice(6, 9)}-**`, rawDigits);
            }
            if (typeof val === 'number' || (typeof val === 'string' && /^-?\d+(\.\d+)?$/.test(val))) {
                const n = parseFloat(val);
                if (!isNaN(n)) {
                    if (col.startsWith('valor') || col.startsWith('total') || col === 'capital_social' || col === 'maior_salario' || col === 'salario') {
                        return td(_shortBrl(n), n);
                    }
                    if (col.startsWith('pct')) {
                        return td(`${n.toFixed(1)}%`, n);
                    }
                    if (col.startsWith('qtd') || col === 'empenhos') {
                        return td(_shortNum(n), n);
                    }
                }
            }
            return td(_esc(val));
        }).join('');

        // Determine row highlight class for sanction severity
        let rowHighlight = '';
        if (iAbrangencia >= 0) {
            const abr = String(row[iAbrangencia] || '');
            const cat = iCategoria >= 0 ? String(row[iCategoria] || '') : '';
            if (/inidone/i.test(cat) || /Nacional/i.test(abr) || /Todas as Esferas/i.test(abr)) rowHighlight = ' row-sancao';
            else if (abr) rowHighlight = ' row-sancao-leve';
        }

        // Servidor row detection (highest priority)
        if (hasServidor) {
            const cpf6 = _esc(row[iCpf6] || '');
            const nomeUp = _esc(row[iNomeUpper] || row[iNomeServidor] || '');
            const displayNome = _esc(row[iNomeServidor >= 0 ? iNomeServidor : iNomeUpper] || '');
            return `<tr class="clickable-row${rowHighlight}" data-cpf6="${cpf6}" data-nome-upper="${nomeUp}" data-nome="${displayNome}" data-cnpjs="[]">${cells}</tr>`;
        }
        // Licitacao row detection (prioritize over fornecedor when both exist)
        if (hasLicitacao) {
            const licNum = String(row[iLicNum] || '');
            const licAno = iLicAno >= 0 ? String(row[iLicAno] || '0') : '0';
            const licMod = iLicMod >= 0 ? String(row[iLicMod] || '') : '';
            if (licNum && licNum !== '000000000') {
                return `<tr class="clickable-row${rowHighlight}" data-licitacao-num="${_esc(licNum)}" data-licitacao-ano="${_esc(licAno)}" data-licitacao-mod="${_esc(licMod)}">${cells}</tr>`;
            }
        }
        // Fornecedor row detection
        if (hasFornecedor) {
            let cnpjB = '';
            let cpfCnpjFull = '';
            if (iCnpjCompleto >= 0) cpfCnpjFull = String(row[iCnpjCompleto] || '').replace(/\D/g, '');
            else if (iCpfCnpj >= 0) cpfCnpjFull = String(row[iCpfCnpj] || '').replace(/\D/g, '');
            if (cpfCnpjFull.length === 14) cnpjB = cpfCnpjFull.slice(0, 8);
            else if (iCnpjBasico >= 0) cnpjB = String(row[iCnpjBasico] || '').replace(/\D/g, '').slice(0, 8);
            const nome = _esc(row[iNomeCredor >= 0 ? iNomeCredor : (iCpfCnpj >= 0 ? iCpfCnpj : 0)] || '');
            if (cnpjB.length === 8 && cpfCnpjFull.length === 14) {
                const nomeCredorAttr = (iNomeCredorExact >= 0 && iNomeCredorExact !== iNomeCredor)
                    ? ` data-fornecedor-nome-credor="${_esc(row[iNomeCredorExact] || '')}"`
                    : '';
                const cpfCnpjAttr = ` data-fornecedor-cpf-cnpj="${_esc(cpfCnpjFull)}"`;
                return `<tr class="clickable-row${rowHighlight}" data-fornecedor-cnpj="${_esc(cnpjB)}" data-fornecedor-nome="${nome}"${nomeCredorAttr}${cpfCnpjAttr}>${cells}</tr>`;
            }
            if (cnpjB.length === 8) {
                cells = cells.replace('</td>', ' <span class="detail-unavailable-hint">Detalhes indisponiveis sem CNPJ completo</span></td>');
                return `<tr class="row-detail-unavailable${rowHighlight}" aria-disabled="true">${cells}</tr>`;
            }
        }
        return `<tr${rowHighlight ? ` class="${rowHighlight.trim()}"` : ''}>${cells}</tr>`;
    }).join('');

    let exportHref = `/api/export/${queryId}?municipio=${encodeURIComponent(municipio)}`;
    if (_dateInicio) exportHref += `&data_inicio=${_dateInicio}`;
    if (_dateFim) exportHref += `&data_fim=${_dateFim}`;

    const legendHtml = iAbrangencia >= 0 ? `<div class="color-legend" style="margin-top:.5rem">
        <span class="color-legend-item"><span class="color-legend-dot" style="background:#ef4444"></span> Sancao de abrangencia nacional ou inidoneidade</span>
        <span class="color-legend-item"><span class="color-legend-dot" style="background:#f59e0b"></span> Sancao de abrangencia restrita (informativo)</span>
    </div>` : '';

    return `<div class="result-block">
        <div class="result-toolbar">
            <div>${legendHtml}</div>
            <a href="${exportHref}" data-export-link class="data-table-export"><span class="citizen-only">Baixar planilha</span><span class="auditor-only">Exportar CSV</span></a>
        </div>
        <div class="table-shell js-data-table" data-page-size="10">
            <div class="table-actions">
                <input type="search" class="table-filter" placeholder="Filtrar nesta tabela" aria-label="Filtrar resultados" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" inputmode="search" enterkeyhint="search">
                <p class="table-meta text-sm text-muted" data-table-meta></p>
            </div>
            <div class="tbl-wrap">
                <table class="stack-mobile">
                    <thead><tr>${headerCells}</tr></thead>
                    <tbody>${bodyRows}</tbody>
                </table>
            </div>
            <div class="table-pagination">
                <md-text-button data-page-prev>Anterior</md-text-button>
                <p class="text-sm text-muted" data-page-label></p>
                <md-text-button data-page-next>Proxima</md-text-button>
            </div>
        </div>
    </div>`;
}

