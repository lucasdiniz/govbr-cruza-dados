// === md3/imports.js ===
//
// Material Web Components - imports.
//
// IMPORTANTE: usamos `@material/web/all.js` (bundle unico) em vez de imports
// individuais. Razao: ao importar componentes individuais via esm.run, cada
// arquivo arrasta seu proprio chunk de @lit/reactive-element, gerando varias
// instancias do registry de custom elements e causando NotSupportedError ao
// definir nomes duplicados como "md-elevation". O bundle `all.js` resolve as
// dependencias internamente, garantindo uma unica instancia de lit.
//
// Trade-off: tamanho do bundle e maior (~250KB gzip vs ~30KB para subset),
// mas eh servido com cache e Service Worker pre-cacheia em primeira visita.
// Em fases futuras podemos otimizar hospedando @material/web localmente
// (sem build step, apenas copiando o bundle do npm).

import "@material/web/all.js";

// Marca um flag global para que componentes nao-modulares (plain scripts)
// possam consultar se MD3 ja carregou.
window.__MD3_READY__ = true;
window.dispatchEvent(new CustomEvent("md3-ready"));

