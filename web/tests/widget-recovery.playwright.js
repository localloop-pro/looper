// Local only: node web/tests/widget-recovery.playwright.js (server on :5369).
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    for (const viewport of [{ width: 1280, height: 720 }, { width: 390, height: 844 }]) {
      const page = await browser.newPage({ viewport });
      const errors = [];
      page.on('pageerror', e => errors.push(e.message));
      page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
      await page.route('**/favicon.ico', route => route.fulfill({ status: 204 }));
      await page.goto(`${process.env.WIDGET_BASE_URL || 'http://127.0.0.1:5369/web'}/looper-widget-frame.html`);
      await page.evaluate(() => {
        navigator.geolocation.getCurrentPosition = (_ok, fail) => fail();
        window.requests = [];
        window.fetch = (_url, options) => {
          const request = { signal: options.signal };
          requests.push(request);
          return new Promise((resolve, reject) => { request.resolve = resolve; request.reject = reject; });
        };
      });
      await page.clock.install();
      await page.locator('#looper-toggle').focus();
      await page.keyboard.press('Enter');
      const input = page.locator('#looper-input');
      const send = page.locator('#looper-send');
      async function submit() {
        await input.fill('cafe');
        await page.keyboard.press('Enter');
        assert(await input.isDisabled());
      }
      async function reply(payload, ok = true, invalid = false) {
        await page.evaluate(({ payload, ok, invalid }) => {
          requests.at(-1).resolve({ ok, json: () => invalid ? Promise.reject(new SyntaxError('invalid')) : Promise.resolve(payload) });
        }, { payload, ok, invalid });
      }
      async function restored() {
        await input.waitFor({ state: 'visible' });
        await page.waitForFunction(() => !document.querySelector('#looper-input').disabled);
        assert(await send.isEnabled());
        assert(await input.evaluate(el => el === document.activeElement));
      }
      const success = { message: '<img src=x onerror=alert(1)>', results: [{ name: 'Cafe One', category: 'cafe', avg_rating: 4, review_count: 2, top_review: 'Friendly', distance_km: 1 }] };
      await submit(); await reply(success); await restored();
      assert((await page.locator('#looper-chat').innerText()).includes('Cafe One'));
      assert.equal(await page.locator('#looper-chat img').count(), 0);
      await submit(); await reply({ message: 'No matches', results: [] }); await restored();
      assert((await page.locator('#looper-chat').innerText()).includes('No matches'));
      for (const [payload, ok, invalid] of [[{results:[]}, false, false], [null, true, true], [{}, true, false], [{results:[null]}, true, false]]) {
        await submit(); await reply(payload, ok, invalid); await restored();
        assert((await page.locator('.looper-bot').last().innerText()).includes('Please try again'));
      }
      await submit();
      await page.evaluate(() => requests.at(-1).reject(new TypeError('offline')));
      await restored();
      assert((await page.locator('.looper-bot').last().innerText()).includes('Please try again'));
      for (const body of [false, true]) {
        await submit();
        if (body) await page.evaluate(() => { requests.at(-1).resolve({ok:true,json:()=>new Promise(resolve => {window.lateBody=resolve;})}); });
        await page.clock.runFor(15001);
        await restored();
        assert(await page.evaluate(() => requests.at(-1).signal.aborted));
        assert((await page.locator('.looper-bot').last().innerText()).includes('Please try again'));
        await submit();
        // Settle the old operation while a retry is active; it cannot render or unlock it.
        await page.evaluate(body => {
          const old = { message: 'STALE', results: [] };
          if (body) lateBody(old);
          else requests.at(-2).resolve({ok:true,json:()=>Promise.resolve(old)});
        }, body);
        assert(await input.isDisabled());
        await reply({message:'Retry succeeded',results:success.results}); await restored();
        assert(!(await page.locator('#looper-chat').innerText()).includes('STALE'));
        assert((await page.locator('.looper-bot').last().innerText()).includes('Retry succeeded'));
      }
      // The whole attempt is bounded even when the host ignores geolocation timeout.
      await page.evaluate(() => { navigator.geolocation.getCurrentPosition = ok => { window.lateLocation = ok; }; });
      const count = await page.evaluate(() => requests.length);
      await submit(); await page.clock.runFor(15001); await restored();
      await page.evaluate(() => lateLocation({coords:{latitude:1,longitude:1}}));
      assert.equal(await page.evaluate(() => requests.length), count);
      await input.focus(); await page.keyboard.press('Tab');
      assert(await send.evaluate(el => el === document.activeElement));
      const bounds = await page.locator('#looper-panel').boundingBox();
      assert(bounds.x >= 0 && bounds.x + bounds.width <= viewport.width);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
      assert.equal(await input.evaluate(el => el.scrollWidth > el.clientWidth), false);
      assert.deepEqual(errors, []);
      console.log(`PASS widget recovery ${viewport.width}x${viewport.height}`);
      await page.close();
    }
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
