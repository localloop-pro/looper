const { test } = require('node:test');
const assert = require('node:assert/strict');
const { createLocalLoopApi } = require('../localloop-api.cjs');
const rows = [{ name: 'Private Cafe', category: 'food' }, { name: 'Second' }];
function client(options = {}) {
  return createLocalLoopApi({ baseUrl: 'http://localhost:8010', log: () => {}, fetchImpl: async () => new Response(JSON.stringify({ results: rows, message: 'Found', count: 2, counts: { total_events: 3 } }), { headers: { 'x-looper-cache': 'MISS' } }), ...options });
}
test('success preserves order and sends opaque request id and safe fetch options', async () => {
  let init;
  const api = client({ fetchImpl: async (_, options) => { init = options; return new Response(JSON.stringify({ results: rows }), { headers: { 'x-looper-cache': 'HIT' } }); } });
  const result = await api.search({ query: 'lunch' });
  assert.equal(result.ok, true);
  assert.deepEqual(result.results, rows);
  assert.ok(result.timing.ms >= 0);
  assert.match(result.timing.rid, /^lb-[0-9a-f-]{36}$/);
  assert.equal(init.headers['X-Request-ID'], result.timing.rid);
  assert.equal(init.headers.Accept, 'application/json');
  assert.equal(init.redirect, 'error');
  assert.equal(init.method, 'GET');
  assert.equal(result.timing.cache, 'HIT');
  assert.ok(result.artifact.content.indexOf('Private Cafe') < result.artifact.content.indexOf('Second'));
});
test('HTTP errors never read or expose the response body', async () => {
  const result = await client({ fetchImpl: async () => ({ ok: false, status: 500, text() { throw Error('secret origin text'); } }) }).search({});
  assert.deepEqual(result, { ok: false, error: 'looper_api_500', message: 'The LOOPER API answered 500.' });
});
test('timeout settles even when fetch ignores abort', async () => {
  let signal;
  const start = performance.now();
  const result = await client({ timeoutMs: 50, fetchImpl: (_, init) => { signal = init.signal; return new Promise(() => {}); } }).search({});
  assert.equal(result.error, 'looper_api_timeout');
  assert.ok(performance.now() - start < 200);
  assert.equal(signal.aborted, true);
});
test('timeout also bounds a stalled response body', async () => {
  const result = await client({ timeoutMs: 20, fetchImpl: async () => ({ ok: true, status: 200, json: () => new Promise(() => {}) }) }).bridgeStatus();
  assert.equal(result.error, 'looper_api_timeout');
});
test('table escapes cells, retains text, rejects dangerous schemes, and preserves rows', () => {
  const table = client().businessesTable([{ name: 'A | [x] ` &<>\nnext', card_url: 'javascript:alert(1)' }, { name: 'B', website: 'https://example.com/a)b' }]);
  assert.ok(table.includes('A \\| \\[x\\] \\` &<> next'));
  assert.ok(!table.includes('(javascript:'));
  assert.ok(table.includes('https://example.com/a%29b'));
  assert.ok(table.indexOf('next') < table.indexOf('| B |'));
});
test('invalid bases reject every operation without fetching', async () => {
  for (const baseUrl of ['http://evil.example', 'https://u:p@example.com', 'https://example.com/path', 'not a URL']) {
    const api = client({ baseUrl, fetchImpl: () => { throw Error('must not fetch'); } });
    for (const method of ['search', 'discover', 'businesses', 'bridgeStatus']) {
      const result = await api[method]({});
      assert.equal(result.error, 'invalid_api_base');
      assert.equal(result.missingEnv, 'LOOPER_API_BASE');
    }
  }
});
test('one privacy-safe log line for success, failure, timeout and invalid base', async () => {
  for (const options of [{}, { fetchImpl: async () => { throw Error('secret origin text'); } }, { timeoutMs: 5, fetchImpl: () => new Promise(() => {}) }, { baseUrl: 'http://evil.example' }, { fetchImpl: async () => new Response('{"results":[]}', { headers: { 'x-looper-cache': 'https://secret.example?q=private' } }) }]) {
    const logs = [];
    await client({ ...options, log: line => logs.push(line) }).search({ query: 'Private Cafe', lat: -33, lng: 151 });
    assert.equal(logs.length, 1);
    assert.match(logs[0], /^\[looper-api\] search \d+ms status=\S+ cache=\S+ rid=lb-[0-9a-f-]{36}$/);
    assert.doesNotMatch(logs[0], /q=|Private Cafe|https?:|secret|-33/);
  }
});
test('other success shapes remain available and network/JSON errors are fixed', async () => {
  assert.equal((await client().discover({ suburb: 'Bondi' })).ok, true);
  assert.equal((await client().businesses({})).count, 2);
  assert.equal((await client().bridgeStatus()).counts.total_events, 3);
  for (const fetchImpl of [async () => { throw Error('private error'); }, async () => new Response('private invalid JSON')]) {
    const result = await client({ fetchImpl }).search({});
    assert.equal(result.error, 'looper_api_unreachable');
    assert.doesNotMatch(JSON.stringify(result), /private/);
  }
});
