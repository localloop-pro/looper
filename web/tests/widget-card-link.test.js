// Run: node web/tests/widget-card-link.test.js (also run by jarvis-sync.test.js, so CI covers it)
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../looper-widget.js'), 'utf8');

function element(tag) {
  return {
    tagName: tag.toUpperCase(), style: {}, children: [], value: '',
    appendChild(child) { this.children.push(child); },
    focus() {},
  };
}
const findLinks = node => (node.tagName === 'A' ? [node] : []).concat(node.children.flatMap(findLinks));

// Load a fresh widget, send one search whose single result carries `card_url`, return the links rendered.
function renderLinks(cardUrl) {
  const elements = {};
  for (const id of ['looper-toggle', 'looper-panel', 'looper-close', 'looper-chat', 'looper-input', 'looper-send']) elements[id] = element('div');
  const result = { name: 'Example cafe', category: 'cafe', avg_rating: 4, review_count: 2 };
  if (cardUrl !== undefined) result.card_url = cardUrl;
  const context = {
    document: { createElement: element, createTextNode: text => ({ tagName: '#TEXT', textContent: text, children: [] }), body: element('body'), getElementById: id => elements[id] },
    window: {}, navigator: {}, AbortController, URLSearchParams, URL, setTimeout, clearTimeout,
    fetch: async () => ({ ok: true, json: async () => ({ message: 'Found results', results: [result] }) }),
  };
  vm.runInNewContext(source, context);
  elements['looper-input'].value = 'cafe';
  elements['looper-send'].onclick();
  return new Promise(resolve => setImmediate(() => resolve(findLinks(elements['looper-chat']))));
}

async function run(ok) {
  const cardUrl = 'http://localhost:3000/c/example?source=widget#details';
  const links = await renderLinks(cardUrl);
  ok('widget preserves card URL', links.length === 1 && links[0].href === cardUrl, JSON.stringify(links.map(l => l.href)));

  const rejected = {
    'javascript: URL': 'javascript:alert(1)',
    'data: URL': 'data:text/html,<script>alert(1)</script>',
    'file: URL': 'file:///etc/passwd',
    'relative URL': '/c/example',
    'malformed URL': 'http://',
    'empty string': '',
    'non-string card_url': { href: 'https://example.com' },
    'null card_url': null,
    'missing card_url': undefined,
  };
  for (const [label, value] of Object.entries(rejected)) {
    const found = await renderLinks(value);
    ok(`widget renders no link for ${label}`, found.length === 0, JSON.stringify(found.map(l => l.href)));
  }
}

module.exports = { run };

if (require.main === module) {
  let failed = 0;
  run((name, cond, detail) => {
    if (cond) console.log(`ok   - ${name}`);
    else { failed++; console.error(`FAIL - ${name}${detail ? `\n  ${detail}` : ''}`); }
  }).then(() => process.exit(failed ? 1 : 0), e => { console.error(e); process.exit(1); });
}
