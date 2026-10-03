// #93 layout check for web/jarvis/demo-map.html (not part of CI).
// Usage, from the repo root:
//   git show origin/main~0:web/jarvis/demo-map.html > web/jarvis/_before.html  # optional "before" copy
//   python3 -m http.server 5369 --bind 127.0.0.1 &
//   PW=$PWD/web/tests/node_modules/playwright SP=/tmp node docs/learnings/93-demo-hint/measure.cjs
// Prints, per page and viewport: whether each zoom/compass button is the
// elementFromPoint at its centre, what the hint overlaps, horizontal scroll,
// console errors. Delete web/jarvis/_before.html afterwards.
const { chromium } = require(process.env.PW);
const base = "http://127.0.0.1:5369/web/jarvis/";
(async () => {
  const browser = await chromium.launch();
  for (const file of ["_before.html", "demo-map.html"]) for (const [w, h] of [[1280, 720], [390, 844]]) {
    const page = await browser.newPage({ viewport: { width: w, height: h } });
    const errors = [];
    page.on("pageerror", e => errors.push(e.message));
    page.on("console", m => { if (m.type() === "error") errors.push(m.text()); });
    await page.goto(base + file);
    await page.waitForSelector("#looper-jarvis .lj-face-btn", { timeout: 15000 });
    await page.waitForTimeout(1500);
    const r = await page.evaluate(() => {
      const box = el => { if (!el || el.hidden) return null; const b = el.getBoundingClientRect(); return b.width ? b : null; };
      const ov = (a, b) => a && b && a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;
      const ctrls = [...document.querySelectorAll(".maplibregl-ctrl-bottom-left button")].map(btn => {
        const b = btn.getBoundingClientRect();
        const hit = document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2);
        return btn.className.split(" ")[0] + ":" + (hit === btn || btn.contains(hit));
      });
      const hint = box(document.querySelector(".hint-wrap") || document.querySelector(".hint"));
      const parts = { chips: box(document.getElementById("chips")), dock: box(document.getElementById("looper-jarvis")),
        attrib: box(document.querySelector(".maplibregl-ctrl-attrib")), nav: box(document.querySelector(".maplibregl-ctrl-bottom-left .maplibregl-ctrl")) };
      const overlaps = Object.entries(parts).filter(([k, b]) => ov(hint, b)).map(([k]) => k);
      const t = document.getElementById("hint-toggle");
      return { ctrls, overlaps, hscroll: document.documentElement.scrollWidth > innerWidth,
        hintOpen: !!box(document.getElementById("hint") || document.querySelector(".hint")),
        apiLine: !!box(document.getElementById("hint-api")),
        toggle: t ? { w: t.offsetWidth, h: t.offsetHeight, name: t.textContent, exp: t.getAttribute("aria-expanded") } : null };
    });
    console.log(file, `${w}x${h}`, JSON.stringify(r), "errors:", errors.length ? errors : "none");
    await page.screenshot({ path: `${process.env.SP}/${file.replace(".html", "")}-${w}.png` });
    if (file === "demo-map.html" && w === 390) {
      await page.focus("#hint-toggle"); await page.keyboard.press("Enter"); await page.waitForTimeout(200);
      const open = await page.evaluate(() => { const h = document.querySelector(".hint-wrap").getBoundingClientRect(), d = document.getElementById("looper-jarvis").getBoundingClientRect(); return { open: !document.getElementById("hint").hidden, overlapsDock: h.left < d.right && d.left < h.right && h.top < d.bottom && d.top < h.bottom, focusOutline: getComputedStyle(document.activeElement).outlineStyle }; });
      console.log("  keyboard open:", JSON.stringify(open));
      await page.screenshot({ path: `${process.env.SP}/demo-map-390-open.png` });
      await page.keyboard.press("Escape");
      console.log("  escape closes:", await page.evaluate(() => document.getElementById("hint").hidden && document.activeElement.id));
    }
    await page.close();
  }
  // standalone (non /web/ path) shows the api line
  await browser.close();
})();
