/**
 * scripts/build-assets.mjs
 *
 * Pipeline de build dos assets do frontend.
 *
 * Estratégia:
 * - JS: os 54 arquivos em web/main.py:JS_FILES sao classic scripts globais
 *   (sem export/import). NAO podemos usar esbuild --bundle (que assume ESM).
 *   Em vez disso, CONCATENAMOS na ordem definida pelo Python e rodamos
 *   esbuild apenas como minifier classic-script (sem wrap, sem mangle de
 *   top-level globals — top-level function declarations sao preservadas).
 *   Separator entre arquivos: "\n;\n" (defensivo contra ASI quebrada).
 * - mapa.js: minify standalone, virou bundle hashed pra cache control.
 * - CSS: index.css usa @import — esbuild --bundle resolve a árvore e
 *   produz arquivo único minificado.
 * - Hash content-based (sha256 truncado em 8 chars) embutido no filename.
 * - manifest.json mapeia nome lógico -> nome hashed.
 * - Sourcemaps externas .map (sem sourcesContent — código é open source).
 *
 * Saída: web/static/dist/{core,mapa}.<hash>.min.js + index.<hash>.min.css
 *        + manifest.json.
 *
 * Uso: `node scripts/build-assets.mjs` (ou `npm run build`).
 *      `--check` valida saída pós-build.
 */

import { build as esbuild } from "esbuild";
import { createHash } from "node:crypto";
import { readFile, writeFile, mkdir, rm, readdir, stat, copyFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "..");
const STATIC_DIR = path.join(REPO_ROOT, "web", "static");
const JS_DIR = path.join(STATIC_DIR, "js");
const CSS_DIR = path.join(STATIC_DIR, "css");
const DIST_DIR = path.join(STATIC_DIR, "dist");
const MAIN_PY = path.join(REPO_ROOT, "web", "main.py");

const HASH_LEN = 8;

// ─────────────────────────────────────────────────────────────────────────
// Util
// ─────────────────────────────────────────────────────────────────────────

function log(...args) {
    console.log("[build]", ...args);
}

function err(...args) {
    console.error("[build][ERR]", ...args);
}

function contentHash(buffer) {
    return createHash("sha256").update(buffer).digest("hex").slice(0, HASH_LEN);
}

async function ensureCleanDir(dir) {
    if (existsSync(dir)) await rm(dir, { recursive: true, force: true });
    await mkdir(dir, { recursive: true });
}

// ─────────────────────────────────────────────────────────────────────────
// JS_FILES extraction from web/main.py (single source of truth).
// ─────────────────────────────────────────────────────────────────────────

async function extractJsFiles() {
    const py = await readFile(MAIN_PY, "utf8");
    const startMarker = "JS_FILES: list[str] = [";
    const startIdx = py.indexOf(startMarker);
    if (startIdx === -1) throw new Error(`Não encontrei "${startMarker}" em ${MAIN_PY}`);
    const after = py.slice(startIdx + startMarker.length);
    const endIdx = after.indexOf("]");
    if (endIdx === -1) throw new Error(`Não encontrei "]" fechando JS_FILES em ${MAIN_PY}`);
    const block = after.slice(0, endIdx);

    const files = [];
    for (const line of block.split("\n")) {
        const trimmed = line.trim();
        if (!trimmed || trimmed.startsWith("#")) continue;
        const m = trimmed.match(/^"([^"]+)",?\s*(?:#.*)?$/);
        if (!m) {
            // Fail loud em vez de silenciosamente pular linhas mal-formatadas
            // (evita um arquivo novo em JS_FILES sumir do bundle de produção
            // se alguém usar aspas simples ou outra formatacao).
            throw new Error(
                `Parser de JS_FILES não reconheceu linha: ${JSON.stringify(line)} ` +
                `(esperado: "path/to/file.js", com aspas duplas)`
            );
        }
        files.push(m[1]);
    }
    if (files.length === 0) throw new Error("JS_FILES vazio — parser quebrado?");
    return files;
}

// ─────────────────────────────────────────────────────────────────────────
// Concat helper
// ─────────────────────────────────────────────────────────────────────────

async function concatFiles(rootDir, relativePaths) {
    const parts = [];
    for (const rel of relativePaths) {
        const abs = path.join(rootDir, rel);
        if (!existsSync(abs)) throw new Error(`Arquivo não encontrado: ${abs}`);
        const content = await readFile(abs, "utf8");
        // Banner de origem + separator defensivo (\n;\n protege contra
        // arquivos terminando sem ; e proxima linha começando com [ ou (
        // que poderiam ser interpretados como continuação na ASI).
        parts.push(`/* === ${rel} === */`);
        parts.push(content);
        parts.push(";");
    }
    return parts.join("\n");
}

// ─────────────────────────────────────────────────────────────────────────
// JS bundle pipeline
// ─────────────────────────────────────────────────────────────────────────

async function buildJsBundle({ name, sources, manifest }) {
    log(`JS bundle "${name}": ${sources.length} arquivo(s)`);
    const concatenated = await concatFiles(JS_DIR, sources);

    // Sourcemaps DESABILITADOS pra bundles JS porque:
    // - Concatenamos arquivos manualmente antes do esbuild → o sourcemap
    //   resultante mapeia tudo pra um único "core-concat.js" virtual, sem
    //   valor de debugging real (não aponta pros 56 arquivos originais).
    // - Pra ter sourcemap útil precisaríamos gerar uma source-map indexada
    //   manualmente (offset por arquivo) — complexidade não justificável
    //   pra um app open-source onde o source completo está no GitHub.
    // - Pra mapa.js (1 arquivo só), seria útil mas mantemos consistência.
    const result = await esbuild({
        stdin: {
            contents: concatenated,
            loader: "js",
            sourcefile: `${name}-concat.js`,
            resolveDir: JS_DIR,
        },
        format: undefined,
        bundle: false,
        minify: true,
        outfile: path.join(DIST_DIR, `${name}.tmp.js`),
        target: "es2020",
        sourcemap: false,
        write: false,
        legalComments: "none",
        charset: "utf8",
    });

    if (result.errors?.length) {
        err("esbuild errors:", JSON.stringify(result.errors, null, 2));
        throw new Error(`Falha ao minificar bundle ${name}`);
    }
    if (result.warnings?.length) {
        for (const w of result.warnings) log("warning:", w.text);
    }

    const jsOut = result.outputFiles.find((f) => f.path.endsWith(".js")) ?? result.outputFiles[0];
    if (!jsOut) throw new Error(`Sem output JS para bundle ${name}`);

    const code = jsOut.text;
    const hash = contentHash(code);
    const filename = `${name}.${hash}.min.js`;

    await writeFile(path.join(DIST_DIR, filename), code);

    manifest[`${name}.js`] = filename;
    log(`  -> ${filename} (${(code.length / 1024).toFixed(1)} KB)`);
}

// ─────────────────────────────────────────────────────────────────────────
// CSS bundle pipeline (resolve @imports)
// ─────────────────────────────────────────────────────────────────────────

async function buildCssBundle({ name, entry, manifest }) {
    log(`CSS bundle "${name}": ${entry}`);
    const result = await esbuild({
        entryPoints: [path.join(CSS_DIR, entry)],
        bundle: true,
        minify: true,
        loader: { ".css": "css" },
        // outdir necessário pra esbuild gerar sourcemap external.
        // write: false impede gravação real (capturamos em memória).
        outdir: DIST_DIR,
        sourcemap: "external",
        sourcesContent: false,
        write: false,
        legalComments: "none",
        charset: "utf8",
    });

    if (result.errors?.length) {
        err("esbuild errors:", JSON.stringify(result.errors, null, 2));
        throw new Error(`Falha ao minificar CSS ${name}`);
    }

    const cssOut = result.outputFiles.find((f) => f.path.endsWith(".css"));
    const mapOut = result.outputFiles.find((f) => f.path.endsWith(".map"));
    if (!cssOut) throw new Error(`Sem output CSS para bundle ${name}`);

    // Hash baseado no conteúdo SEM o sourceMappingURL comment — assim o hash
    // é estavel independente de como esbuild nomeia o sourcemap output.
    const codeNoMap = cssOut.text.replace(/\/\*#\s*sourceMappingURL=.+?\*\/\s*$/m, "").trimEnd();
    const hash = contentHash(codeNoMap);
    const filename = `${name}.${hash}.min.css`;
    const mapName = `${filename}.map`;
    const finalCode = `${codeNoMap}\n/*# sourceMappingURL=${mapName} */\n`;

    await writeFile(path.join(DIST_DIR, filename), finalCode);
    if (mapOut) {
        await writeFile(path.join(DIST_DIR, mapName), mapOut.contents);
    }

    manifest[`${name}.css`] = filename;
    log(`  -> ${filename} (${(finalCode.length / 1024).toFixed(1)} KB)`);
}

// ─────────────────────────────────────────────────────────────────────────
// Validation pos-build
// ─────────────────────────────────────────────────────────────────────────

async function validate(manifest) {
    const required = ["core.js", "mapa.js", "index.css"];
    for (const key of required) {
        if (!manifest[key]) throw new Error(`Manifest faltando chave: ${key}`);
        const filepath = path.join(DIST_DIR, manifest[key]);
        if (!existsSync(filepath)) throw new Error(`Arquivo ausente: ${filepath}`);
        const st = await stat(filepath);
        if (st.size === 0) throw new Error(`Arquivo vazio: ${filepath}`);
    }
    log(`Validation OK (${required.length} bundles).`);
}

// ─────────────────────────────────────────────────────────────────────────
// Main
// ─────────────────────────────────────────────────────────────────────────

async function main() {
    const checkOnly = process.argv.includes("--check");

    if (checkOnly) {
        const manifestPath = path.join(DIST_DIR, "manifest.json");
        if (!existsSync(manifestPath)) {
            err("manifest.json ausente — rode `npm run build` primeiro.");
            process.exit(1);
        }
        const manifest = JSON.parse(await readFile(manifestPath, "utf8"));
        await validate(manifest);
        return;
    }

    log(`REPO_ROOT: ${REPO_ROOT}`);
    log(`DIST_DIR : ${DIST_DIR}`);
    await ensureCleanDir(DIST_DIR);

    const jsFiles = await extractJsFiles();
    log(`JS_FILES extraídos de web/main.py: ${jsFiles.length} arquivos`);

    const manifest = {};

    // Core bundle: todos os JS_FILES da lista do Python (carregam em
    // qualquer página via base.html).
    await buildJsBundle({ name: "core", sources: jsFiles, manifest });

    // Mapa bundle: pages/mapa.js standalone (carregado por index.html
    // e mapa.html via <script> dedicado).
    await buildJsBundle({ name: "mapa", sources: ["pages/mapa.js"], manifest });

    // CSS bundle (entry: index.css com @imports resolvidos).
    await buildCssBundle({ name: "index", entry: "index.css", manifest });

    // Manifest com a lista de assets gerados. CACHE_VERSION = hash agregado
    // — usado pelo service worker para invalidar caches a cada deploy.
    const manifestSig = createHash("sha256")
        .update(JSON.stringify(manifest))
        .digest("hex")
        .slice(0, 12);
    manifest["__cache_version__"] = `tpb-${manifestSig}`;

    await writeFile(
        path.join(DIST_DIR, "manifest.json"),
        JSON.stringify(manifest, null, 2) + "\n"
    );
    log(`manifest.json escrito (cache_version=${manifest.__cache_version__}).`);

    await validate(manifest);

    // Lista o conteúdo final
    const entries = (await readdir(DIST_DIR)).sort();
    log(`dist/ (${entries.length} arquivos):`);
    for (const f of entries) {
        const st = await stat(path.join(DIST_DIR, f));
        log(`  ${(st.size / 1024).toFixed(1).padStart(8)} KB  ${f}`);
    }
}

main().catch((e) => {
    err(e?.stack ?? e);
    process.exit(1);
});
