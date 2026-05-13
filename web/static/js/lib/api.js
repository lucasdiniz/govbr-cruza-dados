// === lib/api.js ===
function _cachedPost(url, key, payload) {
    if (_detailCache[key]) return _detailCache[key];
    const promise = fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    }).then(r => {
        if (!r.ok) {
            if (typeof trackEvent === 'function') {
                // Endpoint generico — sem query/IDs sensiveis. Trim pra
                // limite de 50 chars do Umami event_string_value.
                trackEvent('api-error', {
                    endpoint: String(url).slice(0, 50),
                    status: r.status,
                });
            }
            throw new Error(r.status);
        }
        return r.json();
    }).catch((err) => {
        delete _detailCache[key];
        // Network errors (fetch rejected antes de chegar response) — trackeia
        // como status=0 pra distinguir de HTTP errors.
        if (typeof trackEvent === 'function' && !err.message?.match(/^\d{3}$/)) {
            trackEvent('api-error', {
                endpoint: String(url).slice(0, 50),
                status: 0,
            });
        }
        return {};
    });
    _detailCache[key] = promise;
    return promise;
}

function _historyNote(text) {
    const copy = text || 'Historico completo — estes detalhes nao mudam com o filtro de periodo da pagina.';
    return `<p class="period-badge dialog-history-note" role="note">${copy}</p>`;
}

function _fetchServidorDetails(cpf6, nome, cnpjs, municipio) {
    const cnpjList = Array.isArray(cnpjs) ? cnpjs : [];
    const cnpjKey = cnpjList.map(c => String(c || '').replace(/\D/g, '').slice(0, 8)).filter(Boolean).join(',');
    return _cachedPost('/api/servidor/detalhes', `srv:${cpf6}:${nome}:${municipio}:${cnpjKey}`, { cpf6, nome, cnpjs: cnpjList, municipio });
}

function _fetchFornecedorDetails(cnpjBasico, municipio, nomeCredor, cpfCnpj) {
    const exactDoc = String(cpfCnpj || '').replace(/\D/g, '');
    const payload = { cnpj_basico: cnpjBasico, municipio, cpf_cnpj: exactDoc };
    if (nomeCredor) payload.nome_credor = nomeCredor;
    const cacheKey = `forn:${exactDoc}:${municipio}${nomeCredor ? ':' + nomeCredor : ''}`;
    return _cachedPost('/api/fornecedor/detalhes', cacheKey, payload);
}

