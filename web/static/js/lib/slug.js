// === lib/slug.js ===
// Espelha web/utils/slug.py:municipio_slug. Mantenha SINCRONIZADO!
// Se mudar logica aqui, ajuste tambem o helper Python.
//
// Uso:
//     window.municipioSlug("Joao Pessoa")  // "joao-pessoa"
//
// Diferenca proposital com Python: aqui aceitamos UTF-8 input dos usuarios
// (typed e mostrado com acentos), removemos via NFKD + filtro ASCII.

(function() {
    'use strict';

    function municipioSlug(name) {
        if (!name) return '';
        // Normalizacao NFKD: separa caracteres-base de marcas (acentos)
        // depois remove qualquer codepoint na faixa de combining marks.
        let s = String(name).normalize('NFKD').replace(/[\u0300-\u036f]/g, '');
        s = s.toLowerCase();
        // Espacos e hifens viram um unico hifen
        s = s.replace(/[\s-]+/g, '-');
        // Drop tudo que nao for [a-z0-9-]
        s = s.replace(/[^a-z0-9-]+/g, '');
        // Trim hifens das pontas
        return s.replace(/^-+|-+$/g, '');
    }

    window.municipioSlug = municipioSlug;
})();
