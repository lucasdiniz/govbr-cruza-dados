# Material Web Components — bundle vendored

Este diretório contém um bundle ESM minificado de `@material/web@2.0.0` com
todas as dependências (`lit`, `lit-html`, `lit-element`, `@lit/reactive-element`,
`tslib`) embutidas em um único arquivo.

## Por que vendoramos

A primeira tentativa carregava `@material/web` direto de `esm.sh` em runtime.
Isso tem três problemas para produção:

1. **Indisponibilidade**: outage do esm.sh quebra TODA a UI MD3 (botões,
   diálogos, FAB, chips, tabs, etc.).
2. **Segurança**: módulo arbitrário com execução same-origin (sem SRI viável
   para um grafo de módulos).
3. **Cache**: o service worker só cacheia recursos same-origin, então cada
   visita pagaria o round-trip pra esm.sh.

Vendorar localmente resolve os três e ainda diminui o número de arquivos
servidos (1 bundle de 475 KB / 79 KB gzip, vs ~539 arquivos unbundled).

## Como atualizar este bundle (one-shot, sem build step no projeto)

Quando subir uma versão nova do `@material/web`, repetir:

```powershell
$tmp = "$env:TEMP\mwc-vendor"
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
Push-Location $tmp
npm init -y --silent | Out-Null
npm install --silent @material/web@2.0.0 esbuild@0.24.0  # <-- pinar a versao
@'
import "@material/web/all.js";
window.__MD3_READY__ = true;
window.dispatchEvent(new CustomEvent("md3-ready"));
'@ | Set-Content -Path entry.js -Encoding utf8
node_modules\.bin\esbuild entry.js `
    --bundle `
    --format=esm `
    --target=es2020 `
    --minify `
    --outfile=material-web-bundle.js
Pop-Location
Copy-Item "$tmp\material-web-bundle.js" `
          -Destination web\static\vendor\material-web\material-web-bundle.js `
          -Force
# bumpar ASSET_VERSION em web/main.py e CACHE_VERSION em web/static/sw.js
```

O bundle gerado é determinístico para uma versão do `@material/web` + esbuild,
salvo se uma transitive dep tiver `^x.y.z` que resolva para uma minor diferente.
Para reproduzibilidade total, use lockfile (`npm ci`) com versões pinadas.

## Por que esbuild

Apenas um one-shot tooling — não fica como dependência permanente do projeto
(zero `package.json`, zero `node_modules` no repo). Roda em `$env:TEMP` quando
quisermos atualizar a versão do `@material/web` e some.

Razão pra um bundler em vez de copiar `node_modules` direto:
* `@material/web` usa bare specifiers (`lit/decorators.js`, `tslib`) que precisariam
  de entradas extras no importmap, e `@material/web/all.js` re-exporta ~70 arquivos
  individuais que cada um faria um round-trip http (mesmo com HTTP/2 multiplex,
  é um waterfall de dependency resolution).
* esbuild colapsa tudo num arquivo só, ESM, dedupes `@lit/reactive-element` no
  processo (era exatamente o bug que esm.run produzia).
