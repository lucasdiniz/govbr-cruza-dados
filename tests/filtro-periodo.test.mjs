import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import vm from 'node:vm';

const js = new URL('../web/static/js/', import.meta.url);
const fontes = ['components/date-filter.js', 'components/date-filter-ui.js',
    'pages/cidade-refresh-perfil.js', 'pages/cidade-refresh-kpis.js', 'pages/cidade-bootstrap.js'];

function pagina(perfilOk, kpisOk) {
    const campos = {};
    for (const id of ['dateInicio', 'dateFim', 'dateFilterCurrent', 'dateFilterStatus', 'btnFiltrarData']) {
        campos[id] = {dataset: {}, classList: {toggle() {}}, setAttribute() {}};
    }
    const render = [];
    const ctx = vm.createContext({
        document: {getElementById: id => campos[id], querySelectorAll: () => [], querySelector: () => null},
        console: {warn() {}}, _updateHeroStats: () => render.push('perfil'),
        _updateInsightCards() {}, _updateKpiHeroStrip: () => render.push('kpis'),
        _wireConcentracaoClicks() {}, loadAsyncPanel: async () => true,
        fetch: async (url, opts) => {
            assert.equal(JSON.parse(opts.body).data_fim, '2026-11-27');
            const ok = url === '/api/perfil' ? perfilOk : kpisOk;
            return {ok, status: ok ? 200 : 503, json: async () => url === '/api/perfil'
                ? {perfil: {municipio: 'Teste'}} : {kpis: []}};
        },
    });
    vm.runInContext('let _currentMunicipio = "Teste";', ctx);
    for (const f of fontes) vm.runInContext(readFileSync(new URL(f, js), 'utf8'), ctx);
    vm.runInContext("_dateInicio='2026-01-01'; _dateFim='2026-11-26'; _syncDateFilterUI()", ctx);
    return {campos, render, ctx};
}

for (const [perfilOk, kpisOk] of [[false, true], [true, false], [false, false], [true, true]]) {
    test(`confirmação do filtro: perfil=${perfilOk}, KPIs=${kpisOk}`, async () => {
        const {campos, render, ctx} = pagina(perfilOk, kpisOk);
        const antes = campos.dateFilterCurrent.textContent;
        await vm.runInContext('bootstrapCityReport("Teste","PB","2026-01-01","2026-11-27")', ctx);
        if (perfilOk && kpisOk) {
            assert.deepEqual(render, ['perfil','kpis']);
            assert.match(campos.dateFilterCurrent.textContent, /27\/11\/2026/);
            assert.equal(campos.dateFilterStatus.textContent, 'Filtro aplicado.');
        } else {
            assert.deepEqual(render, []);
            assert.equal(campos.dateFilterCurrent.textContent, antes);
            assert.equal(campos.dateFim.value, '26/11/2026');
            assert.match(campos.dateFilterStatus.textContent, /período exibido foi mantido/);
        }
        assert.equal(campos.btnFiltrarData.disabled, false);
    });
}
