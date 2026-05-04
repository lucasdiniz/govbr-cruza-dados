// === lib/cnpj-format.js ===
function _formatCnpj(cnpjBasico, cnpjCompleto) {
    if (cnpjCompleto && cnpjCompleto.length >= 14) {
        const d = cnpjCompleto.replace(/\D/g, '');
        return `${d.slice(0,2)}.${d.slice(2,5)}.${d.slice(5,8)}/${d.slice(8,12)}-${d.slice(12,14)}`;
    }
    // Mask with asterisks for missing digits
    const d = (cnpjBasico || '').replace(/\D/g, '');
    return `${d.slice(0,2)}.${d.slice(2,5)}.${d.slice(5,8)}/****-**`;
}

function _situacaoLabel(sit) {
    const map = {'1': 'Nula', '2': 'Ativa', '3': 'Suspensa', '4': 'Inapta', '8': 'Baixada'};
    return map[String(sit)] || (sit ? `Sit. ${sit}` : '-');
}

function _porteLabel(porte) {
    // Codigos da RFB: 1 nao informado, 2 micro, 3 EPP, 5 demais.
    const map = {'1': 'Nao informado', '2': 'Microempresa', '3': 'Empresa de Pequeno Porte', '5': 'Demais'};
    if (porte === null || porte === undefined || porte === '') return '';
    return map[String(porte)] || `Porte ${porte}`;
}

function _fmtCep(cep) {
    if (!cep) return '';
    const d = String(cep).replace(/\D/g, '');
    if (d.length !== 8) return String(cep);
    return `${d.slice(0,5)}-${d.slice(5,8)}`;
}


