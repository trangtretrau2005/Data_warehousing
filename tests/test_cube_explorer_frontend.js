// Run with a read-only Cube server available at COFFEE_CUBE_URL (default8503):
// node --test tests/test_cube_explorer_frontend.js
// These exercise the real app controller in a small DOM adapter, not a browser
// or a WebGL renderer. Fixtures are fetched from the current warehouse API.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {pathToFileURL} = require('node:url');

const apiRoot = process.env.COFFEE_CUBE_URL || 'http://127.0.0.1:8503';
const appSource = fs.readFileSync(path.join(__dirname, '../apps/cube_explorer/app.js'), 'utf8');
const html = fs.readFileSync(path.join(__dirname, '../apps/cube_explorer/index.html'), 'utf8');
let fixture;

test.before(async () => {
  const response = await fetch(`${apiRoot}/api/data`, {signal: AbortSignal.timeout(5000)});
  assert.equal(response.status, 200, 'Start apps/cube_explorer/server.py before this integration test.');
  fixture = await response.json();
  assert.equal(fixture.meta.reconciliation, 'passed');
  assert.equal(fixture.marketPeriod.length, 96);
  assert.equal(fixture.productPeriod.length, 1008);
});

function clone(value) { return JSON.parse(JSON.stringify(value)); }

async function setup(customFixture) {
  const input = clone(customFixture || fixture);
  const elements = new Map(), selections = [], exports = [], events = [];
  let focusedElement = null;
  function element(id = '', tagName = 'DIV') {
    if (id && elements.has(id)) return elements.get(id);
    const listeners = new Map();
    const node = {
      id, tagName, textContent: '', innerHTML: '', hidden: false, disabled: false,
      value: '', style: {}, className: '', dataset: {}, children: [], attrs: {},
      classList: {toggle() {}, add() {}, remove() {}},
      setAttribute(name, value) {this.attrs[name] = String(value);},
      getAttribute(name) {return this.attrs[name] ?? null;},
      focus() {focusedElement = this;},
      replaceChildren(...children) {this.children = children;},
      append(...children) {this.children.push(...children);},
      addEventListener(name, listener) {
        if (!listeners.has(name)) listeners.set(name, []);
        listeners.get(name).push(listener);
      },
      dispatch(name, extras = {}) {
        for (const listener of listeners.get(name) || []) listener({target: this, ...extras});
      },
      querySelectorAll(selector) {return selector === 'button' ? this.children : [];},
      showModal() {this.open = true;}, close() {this.open = false;},
      click() {if (tagName === 'A') exports.push({href: this.href, download: this.download}); this.dispatch('click');},
    };
    if (id) elements.set(id, node);
    return node;
  }
  for (const [, tag, attributes, id] of html.matchAll(/<([a-z][\w-]*)\b([^>]*\bid="([^"]+)"[^>]*)>/gi)) {
    const node = element(id, tag.toUpperCase());
    for (const [, name, value] of attributes.matchAll(/([\w:-]+)(?:="([^"]*)")?/g)) node.attrs[name] = value ?? '';
    node.hidden = Object.hasOwn(node.attrs, 'hidden');
    node.disabled = Object.hasOwn(node.attrs, 'disabled');
    node.open = Object.hasOwn(node.attrs, 'open');
  }
  for (const [id, key, values] of [
    ['level-control', 'level', ['type', 'product']],
    ['view-control', 'mode', ['all', 'slice', 'explode']],
  ]) {
    element(id).children = values.map(value => {
      const button = element('', 'BUTTON'); button.dataset[key] = value; return button;
    });
  }
  const productLabel = element('product-label', 'LABEL');
  const document = {
    get activeElement() {return focusedElement;},
    getElementById(id) {
      assert.ok(elements.has(id), `Controller requested unknown DOM id ${id}`);
      return elements.get(id);
    },
    createElement(tag) {return element('', tag.toUpperCase());},
    querySelector(selector) {
      assert.equal(selector, 'label[for="product-select"]'); return productLabel;
    },
    querySelectorAll(selector) {
      if (selector === '[role="tab"]' || selector === '.section-tabs [role="tab"]' || selector === '.section-tabs button') {
        return ['explore-tab', 'analysis-tab', 'lineage-tab'].map(id => element(id));
      }
      throw new Error(`Unexpected document querySelectorAll in controller test: ${selector}`);
    },
    addEventListener(name, listener) {events.push({name, listener});},
  };
  class StubCubeScene {
    constructor(viewport, onSelect) {this.onSelect = onSelect; this.snapshots = []; selections.push(this);}
    setData(rows, state, months, markets, products) {this.snapshots.push(clone({rows, state, months, markets, products}));}
    reset() {this.wasReset = true;}
    resize() {this.wasResized = true;}
  }
  const blobs = new Map();
  class TestURL extends URL {
    static createObjectURL(blob) {const key = `blob:test-${blobs.size}`; blobs.set(key, blob); return key;}
    static revokeObjectURL() {}
  }
  const context = vm.createContext({
    __CubeScene: StubCubeScene, document, window: {}, Intl, URL: TestURL, URLSearchParams, Blob,
    setTimeout() {return 1;}, clearTimeout() {}, requestAnimationFrame(callback) {callback();},
    fetch: async (url) => {
      if (url === '/api/data') return {ok: true, json: async () => clone(input)};
      return fetch(new URL(url, apiRoot), {signal: AbortSignal.timeout(5000)});
    },
  });
  const source = appSource.replace(/^import \{CubeScene\} from '\.\/cube\.js';/m, 'const CubeScene = __CubeScene;')
    .replace(/boot\(\);\s*$/, 'globalThis.bootPromise = boot();');
  vm.runInContext(source, context, {filename: 'app.js'});
  await context.bootPromise;
  assert.equal(element('error-banner').hidden, true, element('error-banner').textContent);
  assert.ok(context.window.coffeeAtlas, 'The app should finish booting.');
  return {
    context, element, exports, blobs,
    scene: selections[0],
    summary: () => clone(context.window.coffeeAtlas.getSummary()),
    state: () => clone(context.window.coffeeAtlas.getState()),
    evaluate: code => vm.runInContext(code, context),
    change(id, value, event = 'change') {const node = element(id); node.value = value; node.dispatch(event);},
    click(id) {element(id).click();},
    async drill() {await vm.runInContext('updateStateDrill()', context);},
    async csv() {
      element('export-button').click(); const download = exports.at(-1);
      return {download, text: await blobs.get(download.href).text()};
    },
  };
}

test('boot reads real mart fixture and groups four product types without changing Sales', async () => {
  const app = await setup();
  const expected = fixture.marketPeriod.filter(row => row.MonthStart === '2013-08-01')
    .reduce((sum, row) => sum + row.Sales, 0);
  assert.equal(app.summary().scopeTotals.Sales, expected);
  assert.equal(app.summary().visibleMonths, 12);
  // One Market/ProductType combination has no source rows. Do not fill the
  // theoretical 12×4×4=192 lattice with invented zero observations.
  assert.equal(app.summary().cubeCells, 180);
  assert.equal(app.scene.snapshots.at(-1).products.length, 4);
});

test('South case shows exact Market totals and signed Product ranking', async () => {
  const app = await setup(); app.click('case-south');
  assert.deepEqual(app.summary().scopeTotals, {Sales: 4601, BudgetSales: 4610, Profit: 1704, Gap: -9});
  assert.equal(app.state().mode, 'slice');
  assert.equal(app.state().level, 'product');
  assert.match(app.element('scope-sentence').textContent, /hụt 9/);
  const ranking = app.element('product-ranking').children;
  assert.match(ranking[0].innerHTML, /Colombian/);
  assert.match(ranking[0].innerHTML, /-268/);
  assert.match(ranking[1].innerHTML, /Decaf Irish Cream/);
  assert.match(ranking[1].innerHTML, /-105/);
});

test('Product selection drills to the actual SQL State API and reconciles', async () => {
  const app = await setup(); app.click('case-south'); app.change('product-select', 'Colombian');
  await app.drill();
  assert.equal(app.summary().scopeTotals.Gap, -268);
  assert.equal(app.element('state-section').hidden, false);
  assert.match(app.element('state-caption').textContent, /Tổng State khớp/);
  assert.ok(app.element('state-list').children.length > 0);
  assert.match(app.element('cell-title').textContent, /Colombian/);
});

test('export CSV respects month, Market and Product selection exactly', async () => {
  const app = await setup(); app.click('case-south'); app.change('product-select', 'Colombian');
  const exported = await app.csv();
  assert.match(exported.download.download, /2013-08_South\.csv$/);
  const lines = exported.text.trim().split('\r\n');
  assert.equal(lines.length, 2);
  assert.equal(lines[0], '"MonthStart","Market","ProductName","Sales","BudgetSales","Profit","Gap"');
  assert.match(lines[1], /^"2013-08-01","South","Colombian",/);
  assert.match(lines[1], /"-268"$/);
  assert.doesNotMatch(lines[1], /"'-268"/);
});

test('type rollup, Product detail and pivot preserve scope totals', async () => {
  const app = await setup(); app.change('market-select', 'West');
  const expected = app.summary().scopeTotals;
  app.element('level-control').children.find(button => button.dataset.level === 'product').click();
  assert.deepEqual(app.summary().scopeTotals, expected);
  app.click('pivot-button');
  assert.deepEqual(app.summary().scopeTotals, expected);
  assert.equal(app.state().pivot, true);
  assert.equal(app.scene.snapshots.at(-1).state.pivot, true);
});

test('clicking a cube cell synchronizes sidebar, KPIs, month and export scope', async () => {
  const app = await setup();
  const cell = app.scene.snapshots.at(-1).rows.find(row => row.MonthStart === '2013-11-01' && row.Market === 'West' && row.Product === 'Coffee');
  app.scene.onSelect(cell);
  assert.equal(app.state().month, '2013-11-01');
  assert.equal(app.element('market-select').value, 'West');
  assert.equal(app.element('product-select').value, 'Coffee');
  assert.equal(app.element('month-slider').value, 10);
  const rows = fixture.productPeriod.filter(row => row.MonthStart === cell.MonthStart && row.Market === cell.Market && fixture.meta.productTypes[row.ProductName] === 'Coffee');
  assert.equal(app.summary().scopeTotals.Sales, rows.reduce((sum, row) => sum + row.Sales, 0));
  assert.equal((await app.csv()).text.trim().split('\r\n').length, rows.length + 1);
});

test('year and time controls retain the correct source month across the boundary', async () => {
  const app = await setup(); app.change('year-select', 'all');
  assert.equal(app.summary().visibleMonths, 24);
  app.change('month-slider', '11', 'input');
  assert.equal(app.state().month, '2012-12-01');
  app.click('next-month');
  assert.equal(app.state().month, '2013-01-01');
  app.change('year-select', '2012');
  assert.equal(app.state().month, '2012-01-01');
  assert.equal(app.summary().visibleMonths, 12);
});

test('missing Product combinations stay missing rather than display zero', async () => {
  const app = await setup(); app.click('case-south');
  const absent = fixture.meta.products.find(product => !fixture.productPeriod.some(row => row.MonthStart === '2013-08-01' && row.Market === 'South' && row.ProductName === product));
  assert.ok(absent, 'Snapshot should contain at least one missing South/Product combination.');
  app.change('product-select', absent);
  assert.equal(app.summary().scopeRows, 0);
  assert.equal(app.summary().scopeTotals, null);
  assert.equal(app.element('kpi-sales').textContent, '—');
  assert.match(app.element('scope-sentence').textContent, /không có bản ghi/);
  assert.equal(app.element('state-section').hidden, true);
});

test('zero Budget returns a missing ratio rather than infinity or an invented zero', async () => {
  const changed = clone(fixture);
  for (const row of changed.productPeriod) {
    if (row.MonthStart === '2013-08-01') {row.BudgetSales = 0; row.Gap = row.Sales;}
  }
  for (const row of changed.marketPeriod) {
    if (row.MonthStart === '2013-08-01') {row.BudgetSales = 0; row.Gap = row.Sales; row.BudgetAchievement = null;}
  }
  const app = await setup(changed);
  assert.equal(app.element('kpi-ratio').textContent, '—');
  assert.equal(app.element('achievement-fill').style.width, '0%');
});

test('static host serves only the app resources and never exposes Python or repo files', async () => {
  for (const resource of ['/app.js', '/cube.js', '/styles.css', '/vendor/three.module.min.js']) {
    assert.equal((await fetch(apiRoot + resource)).status, 200, resource);
  }
  for (const resource of ['/server.py', '/data.py', '/README.md', '/vendor/%2e%2e/server.py', '/%2e%2e/.env']) {
    assert.equal((await fetch(apiRoot + resource)).status, 404, resource);
  }
});

test('the three top tabs expose only their own content and retain the current data selection', async () => {
  const app = await setup();
  assert.equal(app.element('explorer').hidden, false);
  assert.equal(app.element('drill-section').hidden, true);
  assert.equal(app.element('lineage-section').hidden, true);
  assert.equal(app.element('explore-tab').attrs['aria-selected'], 'true');

  app.click('case-south');
  app.change('product-select', 'Colombian');
  const selected = app.state(), totals = app.summary().scopeTotals;
  app.click('analysis-tab');
  assert.equal(app.element('explorer').hidden, true);
  assert.equal(app.element('drill-section').hidden, false);
  assert.equal(app.element('lineage-section').hidden, true);
  assert.equal(app.element('analysis-tab').attrs['aria-selected'], 'true');
  assert.equal(app.element('explore-tab').attrs['aria-selected'], 'false');
  assert.deepEqual(app.summary().scopeTotals, totals);
  assert.equal(app.element('analysis-month-select').value, '2013-08-01');
  assert.equal(app.element('analysis-market-select').value, 'South');
  assert.equal(app.element('analysis-product-select').value, 'Colombian');

  app.click('lineage-tab');
  assert.equal(app.element('explorer').hidden, true);
  assert.equal(app.element('drill-section').hidden, true);
  assert.equal(app.element('lineage-section').hidden, false);
  assert.equal(app.element('lineage-tab').attrs['aria-selected'], 'true');
  app.click('explore-tab');
  assert.equal(app.element('explorer').hidden, false);
  assert.equal(app.element('drill-section').hidden, true);
  assert.equal(app.element('lineage-section').hidden, true);
  const after = app.state(); delete after.view; delete selected.view;
  assert.deepEqual(after, selected, 'Changing presentation tabs must not reset filters or camera mode.');
  assert.deepEqual(app.summary().scopeTotals, totals);
  assert.equal(app.scene.wasResized, true);
});

test('analysis filters use the same warehouse slice as cube KPIs and CSV export', async () => {
  const app = await setup();
  app.click('case-south');
  app.click('analysis-tab');
  app.change('analysis-month-select', '2013-08-01');
  app.change('analysis-market-select', 'South');
  app.change('analysis-product-select', 'Colombian');
  const row = fixture.productPeriod.find(row => row.MonthStart === '2013-08-01' && row.Market === 'South' && row.ProductName === 'Colombian');
  const expected = Object.fromEntries(['Sales', 'BudgetSales', 'Profit', 'Gap'].map(field => [field, row[field]]));
  assert.deepEqual(app.summary().scopeTotals, expected);
  for (const field of ['sales', 'budget', 'gap', 'ratio']) {
    assert.equal(app.element(`analysis-${field}`).textContent, app.element(`kpi-${field}`).textContent, `Analysis and cube disagree for ${field}.`);
  }
  assert.match(app.element('analysis-scope').textContent, /South/);
  assert.match(app.element('analysis-scope').textContent, /08\/2013/);
  assert.match(app.element('analysis-scope').textContent, /Colombian/);
  assert.equal(app.element('market-select').value, 'South');
  assert.equal(app.element('product-select').value, 'Colombian');
  await app.drill();
  assert.equal(app.element('state-section').hidden, false);
  assert.match(app.element('state-caption').textContent, /Tổng State khớp/);
  const exported = await app.csv();
  const lines = exported.text.trim().split('\r\n');
  assert.equal(lines.length, 2);
  assert.match(lines[1], /^"2013-08-01","South","Colombian",/);
  assert.match(lines[1], /"-268"$/);
});

test('analysis month selection crosses a year boundary without silently reverting the date', async () => {
  const app = await setup();
  app.click('analysis-tab');
  app.change('analysis-market-select', 'Central');
  app.change('analysis-month-select', '2012-01-01');
  assert.equal(app.state().month, '2012-01-01');
  assert.equal(app.state().year, '2012');
  assert.equal(app.element('year-select').value, '2012');
  assert.equal(app.summary().scopeTotals.Sales, 10346);
  assert.equal(app.summary().scopeTotals.BudgetSales, 9970);
  app.click('explore-tab');
  assert.equal(app.state().month, '2012-01-01');
  assert.equal(app.element('month-slider').value, 0);
  assert.equal(app.element('month-label').textContent, '01 / 2012');
});

test('analysis level switches from a product-type rollup to actual Product drill without carrying an invalid selection', async () => {
  const app = await setup();
  app.click('analysis-tab');
  app.change('analysis-market-select', 'South');
  app.change('analysis-product-select', 'Coffee');
  const coffeeRows = fixture.productPeriod.filter(row => row.MonthStart === '2013-08-01' && row.Market === 'South' && fixture.meta.productTypes[row.ProductName] === 'Coffee');
  assert.equal(app.summary().scopeTotals.Sales, coffeeRows.reduce((sum, row) => sum + row.Sales, 0));
  assert.equal(app.state().level, 'type');
  assert.equal(app.element('analysis-level-select').value, 'type');

  app.change('analysis-level-select', 'product');
  assert.equal(app.state().level, 'product');
  assert.equal(app.state().product, '', 'A ProductType name must not survive as an invalid ProductName filter.');
  assert.equal(app.element('product-select').value, '');
  assert.equal(app.element('analysis-product-select').value, '');
  assert.equal(app.summary().scopeTotals.Sales, 4601);
  assert.equal(app.scene.snapshots.at(-1).products.length, fixture.meta.products.length);
  assert.ok(app.element('analysis-product-select').children.some(option => option.value === 'Colombian'));

  app.change('analysis-product-select', 'Colombian');
  await app.drill();
  assert.equal(app.summary().scopeTotals.Gap, -268);
  assert.match(app.element('state-caption').textContent, /Tổng State khớp/);
  app.change('analysis-level-select', 'type');
  assert.equal(app.state().product, '');
  assert.equal(app.scene.snapshots.at(-1).products.length, 4);
  assert.equal(app.summary().scopeTotals.Sales, 4601);
  assert.equal(app.element('state-section').hidden, true);
});

test('analysis summary keeps a missing ratio when selected budget is zero', async () => {
  const changed = clone(fixture);
  for (const row of changed.productPeriod) {
    if (row.MonthStart === '2013-08-01') {row.BudgetSales = 0; row.Gap = row.Sales;}
  }
  for (const row of changed.marketPeriod) {
    if (row.MonthStart === '2013-08-01') {row.BudgetSales = 0; row.Gap = row.Sales; row.BudgetAchievement = null;}
  }
  const app = await setup(changed);
  app.click('analysis-tab');
  assert.equal(app.element('analysis-ratio').textContent, '—');
  assert.equal(app.element('analysis-ratio').textContent, app.element('kpi-ratio').textContent);
});

test('tab keyboard navigation moves focus and the selected panel together', async () => {
  const app = await setup();
  app.element('explore-tab').focus();
  app.element('explore-tab').dispatch('keydown', {key: 'ArrowRight', preventDefault() {}});
  assert.equal(app.evaluate('document.activeElement.id'), 'analysis-tab');
  assert.equal(app.element('analysis-tab').attrs['aria-selected'], 'true');
  assert.equal(app.element('drill-section').hidden, false);
  assert.equal(app.element('analysis-tab').attrs.tabindex, '0');
  assert.equal(app.element('explore-tab').attrs.tabindex, '-1');

  app.element('analysis-tab').dispatch('keydown', {key: 'End', preventDefault() {}});
  assert.equal(app.evaluate('document.activeElement.id'), 'lineage-tab');
  assert.equal(app.element('lineage-section').hidden, false);
  app.element('lineage-tab').dispatch('keydown', {key: 'Home', preventDefault() {}});
  assert.equal(app.evaluate('document.activeElement.id'), 'explore-tab');
  assert.equal(app.element('explorer').hidden, false);
  app.element('explore-tab').dispatch('keydown', {key: 'ArrowLeft', preventDefault() {}});
  assert.equal(app.evaluate('document.activeElement.id'), 'lineage-tab');
  assert.equal(app.element('lineage-section').hidden, false);
});

async function makeGeometryScene(level = 'type') {
  const THREE = await import(pathToFileURL(path.join(__dirname, '../apps/cube_explorer/vendor/three.module.min.js')).href);
  const cubeSource = fs.readFileSync(path.join(__dirname, '../apps/cube_explorer/cube.js'), 'utf8');
  const geometryContext = vm.createContext({
    THREE,
    Intl,
    matchMedia: () => ({matches: false}),
    document: {createElement: () => ({className: '', textContent: ''})},
  });
  vm.runInContext(cubeSource.replace(/^import \* as THREE from '[^']+';\s*/m, '')
    .replace('export class CubeScene', 'class CubeScene') + '\nglobalThis.CubeScene = CubeScene;', geometryContext);
  // Instantiate the actual geometry methods without constructing a browser or
  // WebGLRenderer. Raycasting runs on Three.js matrices and bounding volumes.
  const cube = Object.create(geometryContext.CubeScene.prototype);
  Object.assign(cube, {
    rows: [], axes: [], selectedIndex: -1, hoverIndex: -1,
    desired: {theta: .74, phi: 1.12, radius: 18.3},
    mesh: new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshBasicMaterial(), 2000),
    matrix: new THREE.Object3D(),
    outline: {position: new THREE.Vector3(), scale: new THREE.Vector3(), visible: false},
    sliceFrame: {geometry: new THREE.BufferGeometry()},
    slicePlane: {rotation: new THREE.Euler(), position: new THREE.Vector3()},
    tooltip: {hidden: true},
    labelRoot: {children: [], replaceChildren() {this.children = [];}, append(node) {this.children.push(node);}},
    camera: new THREE.PerspectiveCamera(36, 800 / 600, .1, 100),
    raycaster: new THREE.Raycaster(),
    pointer: new THREE.Vector2(),
    canvas: {getBoundingClientRect: () => ({left: 0, top: 0, width: 800, height: 600})},
  });
  const app = await setup(); app.change('year-select', 'all');
  if (level === 'product') app.element('level-control').children.find(button => button.dataset.level === 'product').click();
  const snapshot = app.scene.snapshots.at(-1);
  return {cube, snapshot, THREE};
}

test('actual Three.js outer cells stay ray-pickable after explode, slice and pivot', async () => {
  const {cube, snapshot, THREE} = await makeGeometryScene();
  for (const mode of ['all', 'explode', 'slice']) {
    for (const pivot of [false, true]) {
      cube.hoverIndex = 15;
      cube.setData(snapshot.rows, {...snapshot.state, month: '2013-12-01', market: 'West', product: 'Tea', mode, pivot}, snapshot.months, snapshot.markets, snapshot.products);
      cube.drawMatrices(true);
      cube.mesh.updateMatrixWorld(true);
      const index = cube.rows.findIndex(row => row.MonthStart === '2013-12-01' && row.Market === 'West' && row.Product === 'Tea');
      assert.ok(index >= 0);
      const origin = cube.rows[index].position.clone().add(new THREE.Vector3(0, 10, 0));
      const hits = new THREE.Raycaster(origin, new THREE.Vector3(0, -1, 0)).intersectObject(cube.mesh);
      assert.equal(hits[0]?.instanceId, index, `${mode}/${pivot}: the outside West/Tea/December cube should be pickable.`);
    }
  }
});

test('actual instance transforms and colors remain finite at full Product grain in all layouts', async () => {
  const {cube, snapshot} = await makeGeometryScene('product');
  assert.equal(snapshot.rows.length, 1008);
  for (const mode of ['all', 'slice', 'explode']) {
    for (const pivot of [false, true]) {
      cube.setData(snapshot.rows, {...snapshot.state, month: '2013-08-01', market: 'South', product: 'Colombian', mode, pivot}, snapshot.months, snapshot.markets, snapshot.products);
      cube.drawMatrices(true);
      assert.equal(cube.mesh.count, 1008);
      assert.ok(Array.from(cube.mesh.instanceMatrix.array.slice(0, cube.mesh.count * 16)).every(Number.isFinite));
      assert.ok(Array.from(cube.mesh.instanceColor.array.slice(0, cube.mesh.count * 3)).every(Number.isFinite));
      assert.ok(Number.isFinite(cube.mesh.boundingSphere.radius) && cube.mesh.boundingSphere.radius > 0);
      assert.ok(cube.rows.some(row => row.active && !row.hidden));
      if (mode === 'slice') {
        assert.equal(cube.rows.filter(row => !row.hidden).length, 1);
        assert.ok(cube.rows.filter(row => row.hidden).every(row => row.currentScale.length() === 0));
      }
    }
  }
});

test('ray picking ignores out-of-slice cells while they are still shrinking during transition', async () => {
  const {cube, snapshot, THREE} = await makeGeometryScene();
  const base = {...snapshot.state, month: '2013-12-01', market: '', product: '', mode: 'all', pivot: false};
  cube.setData(snapshot.rows, base, snapshot.months, snapshot.markets, snapshot.products);
  cube.drawMatrices(true);
  cube.setData(snapshot.rows, {...base, mode: 'slice'}, snapshot.months, snapshot.markets, snapshot.products);
  cube.drawMatrices(false);
  cube.mesh.updateMatrixWorld(true);
  const index = cube.rows.findIndex(row => row.MonthStart === '2012-01-01' && row.Market === 'West' && row.Product === 'Tea');
  assert.ok(index >= 0 && cube.rows[index].hidden);
  assert.ok(cube.rows[index].currentScale.length() > 0, 'The chosen hidden cell should still have transitional geometry.');
  const origin = cube.rows[index].position.clone().add(new THREE.Vector3(0, 10, 0));
  const rawHits = new THREE.Raycaster(origin, new THREE.Vector3(0, -1, 0)).intersectObject(cube.mesh);
  assert.ok(rawHits.some(hit => hit.instanceId === index), 'The raw Three.js ray should intersect the shrinking cell.');
  cube.camera.position.copy(origin);
  cube.camera.up.set(0, 0, -1);
  cube.camera.lookAt(cube.rows[index].position);
  cube.camera.updateMatrixWorld(true);
  assert.equal(cube.hit({clientX: 400, clientY: 300}), -1, 'Application picking should omit all hidden transition cells.');
});

test('two-year axis labels remain distinct and a changed layout clears stale hover', async () => {
  const {cube, snapshot} = await makeGeometryScene();
  for (const pivot of [false, true]) {
    cube.hoverIndex = 15;
    cube.setData(snapshot.rows, {...snapshot.state, mode: 'all', pivot}, snapshot.months, snapshot.markets, snapshot.products);
    assert.equal(cube.hoverIndex, -1);
    const labels = cube.axes.map(axis => axis.node.textContent);
    assert.ok(labels.includes('01/12') && labels.includes('01/13'));
    assert.ok(labels.some(label => label.includes('2012–2013')));
    assert.equal(new Set(labels.filter(label => /^\d\d\/\d\d$/.test(label))).size, labels.filter(label => /^\d\d\/\d\d$/.test(label)).length);
  }
});
