// === components/empenho-table.js ===
function _buildEmpenhoTable(empenhos, sancaoRanges) {
    const rows = empenhos.map(e => {
        const dt = _fmtDate(e.data_empenho);
        const mod = e.modalidade_licitacao || '-';
        const numLic = e.numero_licitacao || '';
        const semLic = !numLic || numLic === '000000000' || (mod && mod.toLowerCase().includes('sem licit'));
        let modCell;
        if (semLic) {
            modCell = `<span class="badge badge-yellow"><span class="citizen-only">Sem concorrencia</span><span class="auditor-only">Sem licitacao</span></span>`;
        } else {
            const licLabel = `${mod} (${numLic})`;
            modCell = `<a href="#" class="dialog-link" data-lic-num="${_esc(numLic)}" data-lic-ano="0">${_esc(licLabel)}</a>`;
        }
        const empDate = e.data_empenho ? new Date(e.data_empenho) : null;
        const overlapping = empDate ? sancaoRanges.filter(r =>
            empDate >= r.inicio && (!r.fim || empDate <= r.fim)
        ) : [];
        const matchedSancao = overlapping.find(r => r.grave) || overlapping[0];
        const afeta = !!(matchedSancao && matchedSancao.grave);
        const rowClass = afeta ? 'clickable-row row-sancao' : 'clickable-row';
        let sancaoTag = '';
        if (afeta) {
            sancaoTag = ` <span class="badge badge-red" style="font-size:.6rem" title="${_esc(matchedSancao.categoria || '')} — ${_esc(matchedSancao.abrangencia || '')}"><span class="citizen-only">empresa estava punida</span><span class="auditor-only">durante sancao</span></span>`;
        } else if (matchedSancao) {
            sancaoTag = ` <span class="badge badge-muted" style="font-size:.6rem" title="Sancao vigente neste periodo mas nao afeta contratos com este municipio (${_esc(matchedSancao.abrangencia || 'abrangencia limitada')})"><span class="citizen-only">punicao nao vale aqui</span><span class="auditor-only">sancao nao aplicavel</span></span>`;
        }
        const elRaw = e.elemento_despesa || '-';
        const elCitizen = _stripCodePrefix(elRaw) || elRaw;
        return `<tr class="${rowClass}" data-empenho-id="${e.id}">
            <td data-label="Data" class="stack-meta">${dt}${sancaoTag}</td>
            <td data-label="Tipo de gasto" class="stack-title"><span class="citizen-only">${_esc(elCitizen)}</span><span class="auditor-only">${_esc(elRaw)}</span></td>
            <td data-label="Reservado" class="text-right num">${_shortBrl(e.valor_empenhado)}</td>
            <td data-label="Pago" class="text-right num">${_shortBrl(e.valor_pago)}</td>
            <td data-label="Licitacao" class="stack-meta">${modCell}</td>
        </tr>`;
    }).join('');
    return `<div class="tbl-wrap"><table class="dialog-table stack-mobile">
        <thead><tr>
            <th>Data</th>
            <th><span class="citizen-only">Tipo de gasto</span><span class="auditor-only">Elemento</span></th>
            <th class="text-right"><span class="citizen-only">Reservado</span><span class="auditor-only">Empenhado</span></th>
            <th class="text-right">Pago</th>
            <th><span class="citizen-only">Tipo de licita&ccedil;&atilde;o</span><span class="auditor-only">Modalidade</span></th>
        </tr></thead>
        <tbody>${rows}</tbody>
    </table></div>`;
}

