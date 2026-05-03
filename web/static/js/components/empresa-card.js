// === components/empresa-card.js ===
function _renderEmpresaCard(e, cnpjBasico, extraBadges) {
    if (!e) {
        return `<div class="empresa-card empresa-missing">
            <div class="empresa-header">
                <strong class="text-muted">Dados cadastrais da empresa indisponiveis na RFB</strong>
                <code>${_formatCnpj(cnpjBasico, null)}</code>
            </div>
            <div class="empresa-details">
                <span>O vinculo societario existe nos dados de socios, mas nao ha cadastro completo da empresa para abrir detalhes.</span>
            </div>
            ${extraBadges ? `<div class="empresa-details" style="margin-top:.3rem">${extraBadges}</div>` : ''}
        </div>`;
    }
    const cnpjFmt = _formatCnpj(e.cnpj_basico, e.cnpj_completo);
    const sit = _situacaoLabel(e.situacao_cadastral);
    const sitClass = String(e.situacao_cadastral) === '2' ? '' : 'badge badge-red';
    const capital = e.capital_social ? _shortBrl(e.capital_social) : '-';
    const local = [e.municipio, e.uf].filter(Boolean).join(' - ') || '-';
    const nome = _esc(e.razao_social || 'Razao social nao disponivel');
    const cnpjCompleto = String(e.cnpj_completo || '').replace(/\D/g, '');
    const nomeLink = cnpjCompleto.length === 14
        ? `<a href="#" class="dialog-link" data-forn-cnpj="${_esc(e.cnpj_basico)}" data-forn-cpf-cnpj="${_esc(cnpjCompleto)}" data-forn-nome="${nome}">${nome}</a>`
        : `${nome} <span class="detail-unavailable-hint">Detalhes indisponiveis sem CNPJ completo</span>`;
    const qualif = e.qualificacao_socio ? `<span>${dualLabel('Papel:','Qualificacao:')} <strong>${_esc(e.qualificacao_socio)}</strong></span>` : '';
    const dtEntrada = e.dt_entrada_sociedade ? `<span class="auditor-only">Entrada: ${_fmtDate(e.dt_entrada_sociedade)}</span>` : '';
    return `<div class="empresa-card">
        <div class="empresa-header">
            <strong>${nomeLink}</strong>
            <code class="auditor-only">${cnpjFmt}</code>
        </div>
        <div class="empresa-details">
            ${qualif}${dtEntrada}
            <span>${dualLabel('Cadastro:','Situacao:')} <span class="${sitClass}">${sit}</span></span>
            <span class="auditor-only">Capital: ${capital}</span>
            <span>Sede: ${_esc(local)}</span>
            ${e.cnae_principal ? `<span class="auditor-only">CNAE: ${_esc(e.cnae_principal)}</span>` : ''}
        </div>
        ${extraBadges ? `<div style="margin-top:.35rem">${extraBadges}</div>` : ''}
    </div>`;
}

