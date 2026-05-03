// === components/hero-stats.js ===
function _updateHeroStats(perfil) {
    const el = id => document.getElementById(id);
    if (el('heroQtdEmpenhos')) el('heroQtdEmpenhos').textContent = _shortNum(perfil.qtd_empenhos || 0);
    if (el('heroTotalPago')) el('heroTotalPago').textContent = _shortBrl(perfil.total_pago || 0);
    if (el('heroQtdFornecedores')) el('heroQtdFornecedores').textContent = _shortNum(perfil.qtd_fornecedores || 0);
}

function _updateInsightCards(perfil) {
    const el = id => document.getElementById(id);
    const totalEmpenhado = parseFloat(perfil.total_empenhado) || 0;
    const totalPago = parseFloat(perfil.total_pago) || 0;
    const pctPago = totalEmpenhado ? (totalPago / totalEmpenhado * 100) : 0;
    const gap = totalEmpenhado - totalPago;

    if (el('insightPctPago')) el('insightPctPago').innerHTML =
        `<span class="citizen-only">${pctPago.toFixed(1)}% do planejado foi pago</span>`
        + `<span class="auditor-only">${pctPago.toFixed(1)}% do valor empenhado foi pago</span>`;
    if (el('progressPctPago')) el('progressPctPago').style.width = `${pctPago.toFixed(1)}%`;
    if (el('insightGapFinanceiro')) el('insightGapFinanceiro').innerHTML =
        `<span class="citizen-only">Ainda n&atilde;o pago: ${_shortBrl(gap)}</span>`
        + `<span class="auditor-only">Diferenca entre empenhado e pago: ${_shortBrl(gap)}</span>`;

    const pctSemLicit = perfil.pct_sem_licitacao;
    if (el('insightPctSemLicit')) el('insightPctSemLicit').textContent = pctSemLicit != null ? `${parseFloat(pctSemLicit).toFixed(1)}%` : 'N/D';

    const pctFolha = perfil.pct_folha_receita;
    if (el('insightPctFolha')) el('insightPctFolha').textContent = pctFolha != null ? `${parseFloat(pctFolha).toFixed(1)}%` : 'N/D';

    // Update bar chart
    if (el('barEmpenhado')) el('barEmpenhado').textContent = _shortBrl(totalEmpenhado);
    if (el('barPago')) el('barPago').textContent = _shortBrl(totalPago);
    if (el('barFillPago')) el('barFillPago').style.width = `${pctPago.toFixed(1)}%`;
}

