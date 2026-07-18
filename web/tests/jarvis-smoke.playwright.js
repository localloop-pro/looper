/* Headless smoke test for the Jarvis map layer (no mic/CDN/backend needed).
 * Run:  cd web && python3 -m http.server 8088 &
 *       node tests/jarvis-smoke.playwright.js   (needs playwright + chromium)
 * Set PW_CHROMIUM to your chromium/headless_shell path if not auto-found.
 */
const { chromium } = require("playwright");

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.PW_CHROMIUM || undefined });
  const page = await browser.newPage({ viewport: { width: 900, height: 700 } });
  const errors = [];
  page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
  page.on("console", (m) => { if (m.type() === "error") errors.push("console: " + m.text()); });

  await page.goto("http://127.0.0.1:8088/tests/jarvis-harness.html");
  await page.waitForSelector("#looper-jarvis .lj-face-btn .looper-face");

  // 1. Face mounted + idle
  const mood = await page.getAttribute("#looper-jarvis .lj-face-btn .looper-face", "class");
  console.log("face class:", mood);

  // 2. Drive a full search flow through the public API (typed path)
  const cmd = await page.evaluate(() => LooperJarvis.ask("find me a cafe near me"));
  console.log("routed cmd:", JSON.stringify(cmd));
  await page.waitForSelector("#looper-jarvis .lj-option");
  const options = await page.$$eval("#looper-jarvis .lj-option .lj-name", (els) => els.map((e) => e.textContent));
  console.log("options rendered:", JSON.stringify(options));
  const cardLink = await page.$eval("#looper-jarvis .lj-option a", (a) => a.href + " | " + a.textContent);
  console.log("first link:", cardLink);

  // XSS guard: owner-supplied javascript:/data: URLs must never render
  const badLinks = await page.$$eval("#looper-jarvis a", (as) =>
    as.map((a) => a.getAttribute("href") || "").filter((h) => /^(javascript|data):/i.test(h.trim())));
  console.log("unsafe links rendered:", badLinks.length ? JSON.stringify(badLinks) : "none");
  if (badLinks.length) { errors.push("unsafe scheme rendered: " + JSON.stringify(badLinks)); }

  // 3. Map bus effects (fitBounds from showResults; radius from command)
  let calls = await page.evaluate(() => window.__calls);
  console.log("map/API calls:", JSON.stringify(calls));

  // 4. Suburb + zoom + reset via voice grammar
  await page.evaluate(() => LooperJarvis.ask("take me to bronte"));
  // suburb navigation must clear the previous search's cards/markers —
  // stale results would read as belonging to the destination
  const staleOptions = await page.$$("#looper-jarvis .lj-option");
  if (staleOptions.length) errors.push("suburb fly left stale result cards: " + staleOptions.length);
  await page.evaluate(() => LooperJarvis.ask("zoom in"));
  await page.evaluate(() => LooperJarvis.ask("reset the map"));
  calls = await page.evaluate(() => window.__calls.slice(-4));
  console.log("after suburb/zoom/reset:", JSON.stringify(calls));

  // 5. Deep-link parsing (F4.2)
  await page.goto("http://127.0.0.1:8088/tests/jarvis-harness.html?cat=Food&fly=151.2743,-33.8908,16");
  await page.waitForSelector("#looper-jarvis .lj-face-btn .looper-face");
  const dlCalls = await page.evaluate(() => window.__calls);
  console.log("deep-link calls:", JSON.stringify(dlCalls));
  const activeCat = await page.evaluate(() => LooperMapBus.getActiveCategory());
  console.log("deep-link category:", activeCat);

  // 5b. Deep-link with explicit cat + q + fly (F4.2 contract): the routed
  // q must not override cat, and the search must centre on the fly target.
  await page.goto("http://127.0.0.1:8088/tests/jarvis-harness.html?cat=Offers&q=pizza&fly=153.6120,-28.6474,14");
  await page.waitForSelector("#looper-jarvis .lj-option");
  const dlCat = await page.evaluate(() => LooperMapBus.getActiveCategory());
  const dlFetch = await page.evaluate(() => (window.__calls.find((c) => c[0] === "fetch") || [])[1] || "");
  console.log("deep-link q category:", dlCat);
  if (dlCat !== "Offers") errors.push("deep-link cat overridden by routed q: " + dlCat);
  if (!/lat=-28.6474/.test(dlFetch) || !/lng=153.612/.test(dlFetch)) {
    errors.push("deep-link search ignored fly centre: " + dlFetch);
  }

  // 6. Screenshot the dock with results open
  await page.evaluate(() => LooperJarvis.ask("find me a cafe"));
  await page.waitForSelector("#looper-jarvis .lj-option");
  await page.evaluate(() => { document.querySelector("#looper-jarvis .looper-face").className = "looper-face lf-speaking"; });
  await page.screenshot({ path: require("node:path").join(__dirname, "jarvis-smoke.png") });

  // 7. Mobile fit: on a 320px phone the dock must stay inside the viewport
  const mob = await browser.newPage({ viewport: { width: 320, height: 640 } });
  mob.on("pageerror", (e) => errors.push("mobile pageerror: " + e.message));
  await mob.goto("http://127.0.0.1:8088/tests/jarvis-harness.html");
  await mob.waitForSelector("#looper-jarvis .lj-face-btn .looper-face");
  const dockBox = await mob.$eval("#looper-jarvis", (el) => {
    const r = el.getBoundingClientRect();
    return { left: r.left, right: r.right, width: r.width };
  });
  const fits = dockBox.left >= 0 && dockBox.right <= 320;
  console.log("mobile dock fits 320px viewport:", fits, JSON.stringify(dockBox));
  if (!fits) errors.push("dock overflows 320px viewport: " + JSON.stringify(dockBox));
  await mob.close();

  console.log("errors:", errors.length ? errors : "none");
  await browser.close();
  process.exit(errors.length ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(1); });
