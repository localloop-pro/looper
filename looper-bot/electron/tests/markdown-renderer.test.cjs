const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const ts = require('typescript');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const { createLocalLoopApi } = require('../localloop-api.cjs');

// Execute the same TSX renderer ArtifactPanel imports, without a second parser.
const filename = path.resolve(__dirname, '../../src/components/markdown-inline.tsx');
const compiled = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
}).outputText;
const renderer = new Module(filename, module);
renderer.filename = filename;
renderer.paths = Module._nodeModulePaths(path.dirname(filename));
renderer._compile(compiled, filename);
const { renderInline } = renderer.exports;

test('actual artifact renderer keeps forged name/category links as text and legitimate links as anchors', () => {
  const forged = '[Forged link](http://evil.example/path)';
  const api = createLocalLoopApi({ baseUrl: 'http://localhost:8010' });
  for (const prefix of ['', '\\', '\\\\']) {
    const table = api.businessesTable([
      { name: prefix + forged, category: forged, card_url: 'https://cafe.hybridcard.ai/' },
      { name: 'Website row', website: 'https://localloop.ai/' },
    ]);
    const html = renderToStaticMarkup(React.createElement('div', null, renderInline(table)));
    assert.equal((html.match(/<a /g) || []).length, 2);
    assert.ok(!html.includes('href="http://evil.example/path"'));
    assert.ok(html.includes(forged));
    assert.ok(html.includes('href="https://cafe.hybridcard.ai/"'));
    assert.ok(html.includes('href="https://localloop.ai/"'));
  }
});
