/* Headless smoke test for the Jarvis map layer (no mic/CDN/backend needed).
 * Run: cd web/tests && npm ci && npx playwright install chromium
 *      bash run-jarvis-smoke.sh (owns and cleans up the local server)
 * Set PW_CHROMIUM to your chromium/headless_shell path if not auto-found.
 */
const { chromium } = require("playwright");

// Replaces speechSynthesis before the page loads; every utterance's text
// lands in window.__spoken and ends at once, so speech is synchronous.
function captureSpeech() {
  window.__spoken = [];
  Object.defineProperty(window, "speechSynthesis", {
    configurable: true,
    value: {
      speak: (u) => { window.__spoken.push(u.text); if (u.onend) u.onend(); },
      cancel: () => {},
      getVoices: () => [],
      addEventListener: () => {},
    },
  });
}

// Ask Jarvis something with one stubbed API answer (null = harness
// default) and return everything it said for that answer.
async function spokenFor(page, text, response) {
  await page.evaluate((r) => { window.__searchResponse = r; window.__spoken = []; }, response);
  await page.evaluate((t) => LooperJarvis.ask(t), text);
  await page.waitForFunction(() => /I found|listed|couldn't find/.test(window.__spoken.join(" ")));
  return page.evaluate(() => window.__spoken.join(" "));
}

const VET = { category: "vet", review_count: 0, avg_rating: null, top_review: null, website: null, card_url: null };
const WIDENED_VETS = {
  query: "vet",
  message: "Nothing within 1.5 km for 'vet'. The nearest match is 2.3 km away. " +
    "Here are 2 options for 'vet': best match first, then most community reviews, then nearest.",
  total_results: 2,
  widened_to_km: 10,
  results: [
    Object.assign({ business_id: 11, name: "Coogee Vet", lat: -33.9115, lng: 151.2748, distance_km: 2.3 }, VET),
    Object.assign({ business_id: 12, name: "Clovelly Vet", lat: -33.9113, lng: 151.2752, distance_km: 2.3 }, VET),
  ],
};
const EMPTY_VETS = { query: "vet", message: "No one's listed for 'vet' within 10 km yet.", total_results: 0, widened_to_km: 10, results: [] };

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.PW_CHROMIUM || undefined });
  try {
    const page = await browser.newPage({ viewport: { width: 900, height: 700 } });
    page.setDefaultTimeout(10_000);
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
    // Ghost Listing has blank-string coords — a marker/bounds at [0,0]
    // (Gulf of Guinea) means the coordinate guard let '' coerce to 0
    const fit = calls.find((c) => c[0] === "fitBounds");
    if (fit && (Math.abs(fit[1][0][0]) < 100 || Math.abs(fit[1][0][1]) < 20)) {
      errors.push("blank-coord result dragged fitBounds toward [0,0]: " + JSON.stringify(fit[1]));
    }

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
    // uses the host's "category" spelling — the alias must behave like "cat"
    await page.goto("http://127.0.0.1:8088/tests/jarvis-harness.html?category=Offers&q=pizza&fly=153.6120,-28.6474,14");
    await page.waitForSelector("#looper-jarvis .lj-option");
    const dlCat = await page.evaluate(() => LooperMapBus.getActiveCategory());
    const dlFetch = await page.evaluate(() => (window.__calls.find((c) => c[0] === "fetch") || [])[1] || "");
    console.log("deep-link q category:", dlCat);
    if (dlCat !== "Offers") errors.push("deep-link cat overridden by routed q: " + dlCat);
    if (!/lat=-28.6474/.test(dlFetch) || !/lng=153.612/.test(dlFetch)) {
      errors.push("deep-link search ignored fly centre: " + dlFetch);
    }
    // explicit cat owns the layer AND the query: the parser must not swap
    // in another category's vocabulary (q=pizza is NOT a Food search here)
    if (!/[?&]q=pizza&/.test(dlFetch)) {
      errors.push("deep-link q was rewritten by the parser: " + dlFetch);
    }

    // 6. Screenshot the dock with results open
    await page.evaluate(() => LooperJarvis.ask("find me a cafe"));
    await page.waitForSelector("#looper-jarvis .lj-option");
    await page.evaluate(() => { document.querySelector("#looper-jarvis .looper-face").className = "looper-face lf-speaking"; });
    await page.screenshot({ path: require("node:path").join(__dirname, "jarvis-smoke.png") });

    // 6b. ask() before init (a /demo chip clicked before map load, looper#70):
    // no error, nothing fetched until the dock is mounted, then exactly ONE
    // search for the LATEST queued request.
    const early = await browser.newPage({ viewport: { width: 900, height: 700 } });
    early.setDefaultTimeout(10_000);
    early.on("pageerror", (e) => errors.push("pre-init pageerror: " + e.message));
    early.on("console", (m) => { if (m.type() === "error") errors.push("pre-init console: " + m.text()); });
    await early.goto("http://127.0.0.1:8088/tests/jarvis-harness.html?defer=1");
    const preInit = await early.evaluate(() => {
      const r = [LooperJarvis.ask("food"), LooperJarvis.ask("find me a cafe")]; // latest wins
      return { returned: r, fetches: window.__calls.filter((c) => c[0] === "fetch").length, dock: !!document.querySelector("#looper-jarvis") };
    });
    if (preInit.fetches) errors.push("ask() fetched before init: " + preInit.fetches);
    if (preInit.dock) errors.push("dock mounted before init");
    if (preInit.returned.some((x) => x !== null)) errors.push("pre-init ask() should return null: " + JSON.stringify(preInit.returned));
    await early.evaluate(() => window.__initJarvis());
    await early.waitForSelector("#looper-jarvis .lj-option");
    const earlyFetches = await early.evaluate(() => window.__calls.filter((c) => c[0] === "fetch" && /\/search\?/.test(c[1])).map((c) => c[1]));
    console.log("pre-init ask ran after init:", JSON.stringify(earlyFetches));
    if (earlyFetches.length !== 1 || !/q=cafe/.test(earlyFetches[0])) {
      errors.push("queued ask should search 'cafe' exactly once, got " + JSON.stringify(earlyFetches));
    }
    await early.close();

    // 6c. Deep link + a chip clicked before init (looper#70 race): the deep
    // link's cat/fly still apply, the later user request wins, and the deep
    // link's SLOWER, now-stale answer must never overwrite the cards.
    const race = await browser.newPage({ viewport: { width: 900, height: 700 } });
    race.setDefaultTimeout(10_000);
    race.on("pageerror", (e) => errors.push("race pageerror: " + e.message));
    await race.goto("http://127.0.0.1:8088/tests/jarvis-harness.html?defer=1&cat=Offers&q=pizza&fly=153.6120,-28.6474,14");
    await race.evaluate((vets) => {
      const pizza = { query: "pizza", message: "Here are 2 options for 'pizza'.", total_results: 2, results: [
        { business_id: 21, name: "Stale Pizza A", category: "pizza", lat: -28.64, lng: 153.61, review_count: 1, avg_rating: 4, distance_km: 0.2 },
        { business_id: 22, name: "Stale Pizza B", category: "pizza", lat: -28.65, lng: 153.62, review_count: 1, avg_rating: 4, distance_km: 0.3 },
      ] };
      window.__searchFor = (url) => /q=pizza/.test(url) ? { body: pizza, delayMs: 400 } : { body: vets, delayMs: 0 };
      LooperJarvis.ask("find me a vet");
      window.__initJarvis();
    }, WIDENED_VETS);
    await race.waitForSelector("#looper-jarvis .lj-option");
    await race.waitForTimeout(700); // let the stale pizza answer land
    const raceNames = await race.$$eval("#looper-jarvis .lj-option .lj-name", (els) => els.map((e) => e.textContent));
    const raceState = await race.evaluate(() => ({
      cat: LooperMapBus.getActiveCategory(),
      fly: window.__calls.filter((c) => c[0] === "flyTo").length,
    }));
    console.log("deep-link race:", JSON.stringify(raceNames), JSON.stringify(raceState));
    if (raceNames.some((n) => /Stale Pizza/.test(n)) || !raceNames.some((n) => /Vet/.test(n))) {
      errors.push("stale deep-link answer overwrote the later request: " + JSON.stringify(raceNames));
    }
    if (!raceState.fly) errors.push("deep-link fly not applied when an ask was queued");
    await race.close();

    // 7. Mobile fit: on a 320px phone the dock must stay inside the viewport
    const mob = await browser.newPage({ viewport: { width: 320, height: 640 } });
    mob.setDefaultTimeout(10_000);
    mob.on("console", (m) => { if (m.type() === "error") errors.push("mobile console: " + m.text()); });
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

    // 8. Spoken answers follow the API's widened radius (looper#73 QA r1):
    // vets 2.3 km away must never be announced "within 1.5 kilometres",
    // and an empty answer speaks the API's message, not an "add it" invite.
    for (const vp of [{ width: 900, height: 700 }, { width: 390, height: 844 }]) {
      const sp = await browser.newPage({ viewport: vp });
      sp.setDefaultTimeout(10_000);
      sp.on("pageerror", (e) => errors.push(vp.width + "px pageerror: " + e.message));
      await sp.addInitScript(captureSpeech);
      await sp.goto("http://127.0.0.1:8088/tests/jarvis-harness.html");
      await sp.waitForSelector("#looper-jarvis .lj-face-btn .looper-face");
      const tag = "speech " + vp.width + "px";

      const widened = await spokenFor(sp, "find me a vet", WIDENED_VETS);
      console.log(tag + " widened:", JSON.stringify(widened));
      if (/options? within 1\.5 kilometres/.test(widened)) errors.push(tag + ": said 'within 1.5' for 2.3 km results");
      for (const want of ["Nothing within 1.5 kilometres", "The nearest is 2.3 kilometres away", "I found 2 options within 10 kilometres"]) {
        if (!widened.includes(want)) errors.push(tag + ": widened speech missing '" + want + "': " + widened);
      }

      const inRange = await spokenFor(sp, "find me a cafe", null); // harness default: all < 1.5 km
      console.log(tag + " in range:", JSON.stringify(inRange));
      if (!/I found 4 options within 1\.5 kilometres\./.test(inRange) || /Nothing within/.test(inRange)) {
        errors.push(tag + ": in-range speech wrong: " + inRange);
      }

      const empty = await spokenFor(sp, "find me a vet", EMPTY_VETS);
      console.log(tag + " empty:", JSON.stringify(empty));
      if (empty !== EMPTY_VETS.message) errors.push(tag + ": empty speech ignored the API message: " + empty);

      const bare = await spokenFor(sp, "find me a vet", { query: "vet", results: [], total_results: 0 });
      console.log(tag + " empty, no message:", JSON.stringify(bare));
      if (/add (it|one)|first to add/i.test(bare)) errors.push(tag + ": empty speech invites adding: " + bare);
      await sp.close();
    }

    console.log("errors:", errors.length ? errors : "none");
    if (errors.length) throw new Error("Jarvis smoke failed: " + errors.join("; "));
  } finally {
    await browser.close();
  }
})().catch((e) => { console.error(e); process.exitCode = 1; });
