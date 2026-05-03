// === lib/md3-ready.js ===
//
// MD3 readiness gate. The MD3 component bundle (web/static/js/md3/imports.js)
// loads as a deferred ES module via importmap; the 53 plain (classic) scripts
// loaded later in <body> can race with it. Once we start consuming <md-*>
// elements (next PR), legacy code that calls .show()/.value/etc. on them must
// wait for upgrade to avoid no-ops.
//
// This helper exposes `window.whenMD3Ready(cb)`:
//   - resolves immediately if window.__MD3_READY__ === true
//   - otherwise listens for the "md3-ready" event dispatched by imports.js
//
// Usage from any plain script:
//   whenMD3Ready(() => {
//     const dialog = document.getElementById('empresa-dialog');
//     dialog?.show();
//   });
//
// Or as a Promise:
//   await whenMD3Ready();
//
// Note: this file is currently a no-op for existing code (no <md-*> consumed
// yet). It's shipping now so the next PR (primitive swaps) can rely on it
// without another round-trip.

(function () {
  function whenMD3Ready(cb) {
    if (window.__MD3_READY__ === true) {
      if (typeof cb === 'function') {
        // Defer one tick so callers using the callback form behave the same
        // whether MD3 was already ready or not (no synchronous re-entrancy).
        Promise.resolve().then(cb);
      }
      return Promise.resolve();
    }
    return new Promise(function (resolve) {
      window.addEventListener('md3-ready', function handler() {
        window.removeEventListener('md3-ready', handler);
        if (typeof cb === 'function') cb();
        resolve();
      }, { once: true });
    });
  }
  window.whenMD3Ready = whenMD3Ready;
})();
