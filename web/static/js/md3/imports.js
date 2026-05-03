// === md3/imports.js ===
//
// Material Web Components - registro dos custom elements <md-*>.
//
// O bundle real (`material-web-bundle.js`) eh vendorado localmente em
// /static/vendor/material-web/ e ja faz o registro + dispatch de "md3-ready".
// Este arquivo existe somente para acionar o import via importmap, garantindo
// que o bundle seja carregado quando este modulo for incluido em base.html.
//
// O bundle inclui:
//   * @material/web@2.0.0/all.js (todos os componentes)
//   * lit, lit-html, lit-element, @lit/reactive-element, tslib (deps)
//
// Tamanho: ~475 KB raw / ~79 KB gzip. Servido same-origin, cacheado pelo
// Service Worker (CORE_ASSETS em sw.js) e pelo HTTP cache do browser.
//
// Para atualizar a versao do @material/web ou re-gerar o bundle, ver
// web/static/vendor/material-web/README.md.

import "@material/web/all.js";

// O bundle ja seta __MD3_READY__ e dispara "md3-ready", entao aqui nao
// precisamos repetir. Mas garantimos que o flag exista mesmo que o bundle
// falhe ao carregar (debug-friendly: fica `false` em vez de `undefined`).
if (typeof window !== "undefined" && window.__MD3_READY__ !== true) {
  // Bundle nao carregou (ou ainda nao executou): deixa explicitamente como
  // false para que whenMD3Ready() use o caminho de espera por evento.
  window.__MD3_READY__ = false;
}


