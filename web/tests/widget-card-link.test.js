// Reproduction: node web/tests/widget-card-link.test.js
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const elements = {};
function element(tag) {
  return {
    tagName: tag.toUpperCase(), style: {}, children: [], value: '',
    appendChild(child) { this.children.push(child); },
    focus() {},
  };
}
for (const id of ['looper-toggle', 'looper-panel', 'looper-close', 'looper-chat', 'looper-input', 'looper-send']) elements[id] = element('div');
const document = { createElement: element, createTextNode: text => ({ tagName: '#TEXT', textContent: text, children: [] }), body: element('body'), getElementById: id => elements[id] };
const cardUrl = 'http://localhost:3000/c/example?source=widget#details';
const context = {
  document, window: {}, navigator: {}, AbortController, URLSearchParams, URL, setTimeout, clearTimeout,
  fetch: async () => ({ ok: true, json: async () => ({ message: 'Found results', results: [
    { name: 'Example cafe', category: 'cafe', avg_rating: 4, review_count: 2, card_url: cardUrl },
  ] }) }),
};
vm.runInNewContext(fs.readFileSync('web/looper-widget.js', 'utf8'), context);
elements['looper-input'].value = 'cafe';
elements['looper-send'].onclick();
setImmediate(() => {
  const findLink = node => node.tagName === 'A' ? node : node.children.flatMap(child => findLink(child) || [])[0];
  const link = findLink(elements['looper-chat']);
  assert.ok(link, 'search result with card_url should contain a View card link');
  assert.equal(link.href, cardUrl);
  console.log('PASS widget preserves card URL');
});
