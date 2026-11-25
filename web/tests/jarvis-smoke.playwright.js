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

const mx = (lng) => (lng + 180) / 360;
const my = (lat) => (1 - Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360)) / Math.PI) / 2;

// Screen pixels of [lng, lat] points after map.fitBounds(bounds, opts) on a
// flat (unpitched) w x h Web Mercator map, as MapLibre places them: fit the
// bounds into the box left after padding (capped at maxZoom), centred in it.
function placeFitBounds(bounds, opts, w, h, points) {
  const pad = typeof opts.padding === "number"
    ? { top: opts.padding, bottom: opts.padding, left: opts.padding, right: opts.padding }
    : Object.assign({ top: 0, bottom: 0, left: 0, right: 0 }, opts.padding);
  const [[west, south], [east, north]] = bounds;
  const boxW = w - pad.left - pad.right, boxH = h - pad.top - pad.bottom;
  let scale = Math.min(boxW / (mx(east) - mx(west)), boxH / (my(south) - my(north)));
  if (typeof opts.maxZoom === "number") scale = Math.min(scale, 512 * 2 ** opts.maxZoom);
  const cx = (mx(west) + mx(east)) / 2, cy = (my(north) + my(south)) / 2;
  const boxCx = pad.left + boxW / 2, boxCy = pad.top + boxH / 2;
  return points.map(([lng, lat]) => ({
    x: Math.round(boxCx + (mx(lng) - cx) * scale),
    y: Math.round(boxCy + (my(lat) - cy) * scale),
  }));
}

// Screen pixels of [lng, lat] points after a recorded fake-map camera call:
// fitBounds as above, flyTo with its centre in the middle of the w x h map.
function placeCamera(call, w, h, points) {
  if (call[0] === "fitBounds") return placeFitBounds(call[1], call[2] || {}, w, h, points);
  const o = call[1], scale = 512 * 2 ** o.zoom;
  return points.map(([lng, lat]) => ({
    x: Math.round(w / 2 + (mx(lng) - mx(o.center[0])) * scale),
    y: Math.round(h / 2 + (my(lat) - my(o.center[1])) * scale),
  }));
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
// Rows the API could not place (no coordinates): distance_km is null, so
// no distance is known and speech must not claim "within N kilometres".
const UNPLACED_VETS = {
  query: "vet",
  message: "Here are 2 options for 'vet': best match first, then most community reviews, then nearest.",
  total_results: 2,
  results: [
    Object.assign({ business_id: 13, name: "Unmapped Vet", lat: null, lng: null, distance_km: null }, VET),
    Object.assign({ business_id: 14, name: "Nowhere Vet", lat: null, lng: null, distance_km: null }, VET),
  ],
};
// One known distance is enough to keep the radius wording.
const MIXED_VETS = {
  query: "vet",
  message: "Here are 2 options for 'vet': best match first, then most community reviews, then nearest.",
  total_results: 2,
  results: [
    Object.assign({ business_id: 15, name: "Bondi Vet", lat: -33.8915, lng: 151.2743, distance_km: 0.4 }, VET),
    Object.assign({ business_id: 16, name: "Unmapped Vet", lat: null, lng: null, distance_km: null }, VET),
  ],
};

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.PW_CHROMIUM || undefined });
  try {
    const page = await browser.newPage({ viewport: { width: 900, height: 700 } });
    page.setDefaultTimeout(10_000);
    const errors = [];
    page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
    page.on("console", (m) => { if (m.type() === "error") errors.push("console: " + m.text()); });

    // A browser with speech recognition must still offer typing before any mic use.
    await page.addInitScript(() => {
      window.__micStarts = 0;
      window.SpeechRecognition = function () { this.start = () => { window.__micStarts++; }; this.stop = () => {}; };
    });
    await page.goto("http://127.0.0.1:8088/tests/jarvis-harness.html");
    await page.waitForSelector("#looper-jarvis .lj-face-btn .looper-face");
    await page.locator('#lj-type').focus();
    await page.keyboard.press('Enter');
    if (!(await page.locator('#lj-input').isVisible()) || !(await page.locator('#lj-input').evaluate(el => el === document.activeElement))) {
      throw new Error('Typed search is not visible and focused before microphone use when SpeechRecognition exists');
    }
    await page.keyboard.type('find me a cafe near me');
    await page.keyboard.press('Enter');
    await page.waitForSelector('#looper-jarvis .lj-option a');
    if (new URL(await page.locator('#looper-jarvis .lj-option a').first().getAttribute('href')).origin !== 'https://gertrude.hybridcard.ai') throw new Error('Typed search did not reach the supplied card');
    if (await page.evaluate(() => window.__micStarts) !== 0) throw new Error('Typed search started recognition');
    await page.locator('#lj-face-btn').click();
    await page.waitForFunction(() => window.__micStarts === 1);
    const noSpeech = await browser.newPage();
    await noSpeech.addInitScript(() => { window.SpeechRecognition = undefined; window.webkitSpeechRecognition = undefined; });
    await noSpeech.goto('http://127.0.0.1:8088/tests/jarvis-harness.html');
    await noSpeech.locator('#lj-type').focus();
    await noSpeech.keyboard.press('Enter');
    await noSpeech.keyboard.type('find me a cafe');
    await noSpeech.keyboard.press('Enter');
    await noSpeech.waitForSelector('#looper-jarvis .lj-option a');
    if (new URL(await noSpeech.locator('#looper-jarvis .lj-option a').first().getAttribute('href')).origin !== 'https://gertrude.hybridcard.ai') throw new Error('Typed fallback did not reach the supplied card');
    await noSpeech.close();

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
    const t = await page.evaluate(() => LooperJarvis.timings());
    const lastTiming = t[t.length - 1];
    const timingKeys = ["intent", "rid", "cache", "status", "route_ms", "fetch_ms", "parse_ms", "render_ms", "to_speech_ms", "results"].sort();
    console.log("turn timing:", JSON.stringify(lastTiming));
    if (t.length < 1) errors.push("search turn did not record timing");
    if (!lastTiming || Object.keys(lastTiming).sort().join(",") !== timingKeys.join(",")) {
      errors.push("search timing does not have exactly ten public keys: " + JSON.stringify(lastTiming));
    }
    if (!lastTiming || lastTiming.intent !== "search" || lastTiming.results !== 4) {
      errors.push("search timing has wrong intent/results: " + JSON.stringify(lastTiming));
    }
    for (const key of ["route_ms", "fetch_ms", "parse_ms", "render_ms", "to_speech_ms"]) {
      if (!lastTiming || typeof lastTiming[key] !== "number" || lastTiming[key] < 0) {
        errors.push("search timing has invalid " + key + ": " + JSON.stringify(lastTiming));
      }
    }
    const timingJson = JSON.stringify(t);
    for (const forbidden of ['"q"', "cafe", '"lat"']) {
      if (timingJson.includes(forbidden)) errors.push("timing leaked " + forbidden + ": " + timingJson);
    }
    const hookedTiming = await page.evaluate(() => window.__timingHook.slice(-1)[0]);
    if (JSON.stringify(hookedTiming) !== JSON.stringify(lastTiming)) {
      errors.push("onTiming hook missed or changed the search record: " + JSON.stringify(hookedTiming));
    }

    // A non-2xx response records the same PII-free shape as an error and
    // keeps the existing offline panel/speech behavior.
    await page.evaluate(() => {
      window.__searchFor = () => ({ ok: false, status: 500, body: {} });
      LooperJarvis.ask("find me a cafe");
    });
    await page.waitForFunction(() => LooperJarvis.timings().some((row) => row.status === "error"));
    const errorTiming = await page.evaluate(() => LooperJarvis.timings().slice(-1)[0]);
    console.log("error timing:", JSON.stringify(errorTiming));
    if (!errorTiming || errorTiming.status !== "error") errors.push("500 did not record an error timing");
    if (!errorTiming || Object.keys(errorTiming).sort().join(",") !== timingKeys.join(",")) {
      errors.push("error timing does not have exactly ten public keys: " + JSON.stringify(errorTiming));
    }
    await page.evaluate(() => { window.__searchFor = null; });

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
    // desktop (looper#142): the panel sits beside the pins, padding stays 50
    if (fit && (fit[2].padding !== 50 || "pitch" in fit[2])) errors.push("desktop fit options changed: " + JSON.stringify(fit[2]));
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

      // looper#153: no known distance -> no "within N kilometres" claim
      const unplaced = await spokenFor(sp, "find me a vet", UNPLACED_VETS);
      console.log(tag + " no known distance:", JSON.stringify(unplaced));
      if (/within \d/.test(unplaced)) errors.push(tag + ": claimed a radius with no known distance: " + unplaced);
      if (!/I found 2 options\./.test(unplaced)) errors.push(tag + ": no-distance speech wrong: " + unplaced);
      const mixed = await spokenFor(sp, "find me a vet", MIXED_VETS);
      console.log(tag + " one known distance:", JSON.stringify(mixed));
      if (!/I found 2 options within 1\.5 kilometres\./.test(mixed)) errors.push(tag + ": mixed-distance speech wrong: " + mixed);

      // looper#153: a 4xx is a bad request, not an outage — no "brain
      // offline", a short "couldn't read that request" line, typed input open.
      // A 5xx keeps the offline treatment.
      for (const [label, text, status] of [["search 422", "find me a cafe", 422], ["business 400", "take me to gertrude and alice", 400]]) {
        await sp.evaluate((st) => {
          window.__spoken = [];
          window.__searchFor = () => ({ ok: false, status: st, body: { detail: "bad request" } });
        }, status);
        await sp.evaluate((t) => LooperJarvis.ask(t), text);
        await sp.waitForFunction(() => window.__spoken.length > 0);
        const st = await sp.evaluate(() => ({
          spoken: window.__spoken.join(" "),
          status: document.querySelector("#looper-jarvis .lj-status").textContent,
          panel: document.querySelector("#looper-jarvis .lj-panel").textContent,
          inputOpen: document.querySelector("#looper-jarvis .lj-input-row").classList.contains("lj-open"),
        }));
        console.log(tag + " " + label + ":", JSON.stringify(st));
        if (/offline/i.test(st.status + " " + st.panel + " " + st.spoken)) errors.push(tag + " " + label + ": 4xx reported as brain offline: " + JSON.stringify(st));
        if (!/couldn't read that request/i.test(st.panel)) errors.push(tag + " " + label + ": 4xx panel missing the bad-request line: " + st.panel);
        if (!st.inputOpen) errors.push(tag + " " + label + ": 4xx left the typed input closed");
      }
      await sp.evaluate(() => {
        window.__spoken = [];
        window.__searchFor = () => ({ ok: false, status: 503, body: {} });
      });
      await sp.evaluate(() => LooperJarvis.ask("find me a cafe"));
      await sp.waitForFunction(() => window.__spoken.length > 0);
      const down = await sp.evaluate(() => document.querySelector("#looper-jarvis .lj-status").textContent);
      if (down !== "Looper brain offline") errors.push(tag + ": 503 no longer reports brain offline: " + down);
      await sp.evaluate(() => { window.__searchFor = null; });
      await sp.close();
    }

    // 9. Phone result pins (looper#142): on 375 x 780 and 375 x 667 phones, after ALL the
    // camera moves of a turn, every pin the user is shown must land on the
    // map OUTSIDE the open result panel and below the host's 120 px top bar
    // (topInset, like the /demo chip bar). The fake map has no renderer, so
    // the final camera call is replayed the way MapLibre places pins (flat
    // Web Mercator; fitBounds padding and maxZoom; flyTo centres the target).
    for (const vp of [{ width: 375, height: 780 }, { width: 375, height: 667 }]) {
    const phone = await browser.newPage({ viewport: vp });
    phone.setDefaultTimeout(10_000);
    phone.on("pageerror", (e) => errors.push("phone pageerror: " + e.message));
    await phone.goto("http://127.0.0.1:8088/tests/jarvis-harness.html?defer=1");
    await phone.evaluate(() => LooperJarvis.init({ map: window.fakeMap, district: "Bondi", apiBase: "http://stub", topInset: () => 120 }));
    await phone.waitForSelector("#looper-jarvis .lj-face-btn .looper-face");
    const R = 12; // a result marker is 24 px across: half under the panel is hidden
    async function checkPhonePins(tag, pins) {
      const st = await phone.evaluate(() => {
        const cam = window.__calls.filter((c) => c[0] === "fitBounds" || c[0] === "flyTo").slice(-1)[0];
        const p = document.querySelector("#looper-jarvis .lj-panel").getBoundingClientRect();
        return { cam, panel: { left: p.left, right: p.right, top: p.top, bottom: p.bottom } };
      });
      tag = vp.height + "px " + tag;
      if (!st.cam) { errors.push("phone " + tag + ": no camera move"); return; }
      const placed = placeCamera(st.cam, vp.width, vp.height, pins);
      console.log("phone " + tag + " pins:", JSON.stringify(placed), "panel:", JSON.stringify(st.panel),
        "final camera:", JSON.stringify(st.cam));
      const under = placed.filter((pt) => pt.x >= st.panel.left - R && pt.x <= st.panel.right + R &&
        pt.y >= st.panel.top - R && pt.y <= st.panel.bottom + R);
      if (under.length) errors.push("phone " + tag + ": " + under.length + " of " + pins.length + " result pins under the result panel");
      const hidden = placed.filter((pt) => pt.y < 120 + R || pt.x < R || pt.x > vp.width - R);
      if (hidden.length) errors.push("phone " + tag + ": " + hidden.length + " of " + pins.length + " result pins under the top bar or off screen");
      // the placement is flat, like MapLibre's fit: a tilted phone map would
      // push the nearest pins back under the panel (seen on the real /demo)
      if (st.cam[0] === "fitBounds" && st.cam[2].pitch !== 0) errors.push("phone " + tag + ": final camera keeps the map tilted: " + JSON.stringify(st.cam[2]));
    }
    async function askOnPhone(text, response, firstName) {
      return phone.evaluate(async ({ text, response, firstName }) => {
        window.__searchResponse = response;
        window.__calls = [];
        const cmd = LooperJarvis.ask(text);
        const t0 = Date.now();
        while (!Array.from(document.querySelectorAll("#looper-jarvis .lj-option .lj-name")).some((e) => e.textContent.includes(firstName))) {
          if (Date.now() - t0 > 5000) break;
          await new Promise((r) => setTimeout(r, 20));
        }
        return cmd && cmd.intent;
      }, { text, response, firstName });
    }
    const CAFE = { category: "café", review_count: 1, avg_rating: 4, top_review: null, website: null, card_url: null };
    // a full list (search limit 5) with one mappable row: the panel is as
    // tall as a real Food answer
    const SOLO = { query: "cafe", message: "Here are 5 options for 'cafe': best match first, then most community reviews, then nearest.", total_results: 5, results: [
      Object.assign({ business_id: 31, name: "Solo Pin Cafe", lat: -33.8893, lng: 151.2735, distance_km: 0.4 }, CAFE),
    ].concat([32, 33, 34, 35].map((id) => Object.assign({ business_id: id, name: "No Coords Cafe " + id, lat: "", lng: "", distance_km: 0.5 }, CAFE))) };
    // a named lookup returns up to 3 matches (runBusiness limit)
    const NAMED = { query: "gertrude", message: "Matching options.", total_results: 3, results: [
      Object.assign({ business_id: 1, name: "Gertrude & Alice", lat: -33.8893, lng: 151.2735, distance_km: 0.4 }, CAFE),
      Object.assign({ business_id: 2, name: "Bondi Wholefoods", lat: -33.8908, lng: 151.2748, distance_km: 0.6 }, CAFE),
      Object.assign({ business_id: 3, name: "Gertrude Street Deli", lat: -33.8902, lng: 151.2741, distance_km: 0.5 }, CAFE),
    ] };

    // 9a. several pins: fitted between the top bar and the panel
    await askOnPhone("find me a cafe", null, "Gertrude");
    await checkPhonePins("search", [[151.2735, -33.8893], [151.2748, -33.8908], [151.2750, -33.8910]]);
    // 9b. one mappable pin among the listed results (fitPoints flies to it)
    await askOnPhone("find me a cafe", SOLO, "Solo Pin Cafe");
    await checkPhonePins("one valid pin", [[151.2735, -33.8893]]);
    // 9c. named business: pins, then a zoom-17 flight to the top match
    const namedIntent = await askOnPhone("take me to gertrude and alice", NAMED, "Gertrude");
    if (namedIntent !== "business") errors.push("phone: named lookup routed as " + namedIntent);
    await checkPhonePins("named business", [[151.2735, -33.8893]]);
    // 9d. tapping a listed option flies to that business
    await phone.evaluate(() => { window.__calls = []; });
    await phone.click('#looper-jarvis .lj-option[data-i="1"]');
    await checkPhonePins("option tap", [[151.2748, -33.8908]]);
    await phone.close();
    }

    console.log("errors:", errors.length ? errors : "none");
    if (errors.length) throw new Error("Jarvis smoke failed: " + errors.join("; "));
  } finally {
    await browser.close();
  }
})().catch((e) => { console.error(e); process.exitCode = 1; });
