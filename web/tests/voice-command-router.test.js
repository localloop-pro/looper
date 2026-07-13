/* Unit tests for the LOOPER Jarvis voice command router (F3.2).
 * Run: node web/tests/voice-command-router.test.js
 * Node-only, zero deps — same style as the gateway unit tests.
 */
"use strict";

const router = require("../jarvis/voice-command-router.js");

let passed = 0;
let failed = 0;

function check(name, actual, expected) {
  const problems = [];
  for (const key of Object.keys(expected)) {
    const want = expected[key];
    const got = actual[key];
    if (JSON.stringify(got) !== JSON.stringify(want)) {
      problems.push(`  ${key}: expected ${JSON.stringify(want)}, got ${JSON.stringify(got)}`);
    }
  }
  if (problems.length === 0) {
    passed++;
    console.log(`ok   - ${name}`);
  } else {
    failed++;
    console.error(`FAIL - ${name}\n${problems.join("\n")}\n  full: ${JSON.stringify(actual)}`);
  }
}

const route = (t, ctx) => router.route(t, ctx);

// ---- stop (misfire fix is the headline requirement) ------------------------
check("plain stop", route("stop"), { intent: "stop" });
check("stop talking", route("Stop talking!"), { intent: "stop" });
check("hey looper stop", route("hey looper, stop"), { intent: "stop" });
check("okay looper stop (wake variant)", route("OK Looper stop"), { intent: "stop" });
check("okay looper cancel (wake variant)", route("okay looper cancel"), { intent: "stop" });
check("hey looper stop listening", route("hey looper stop listening"), { intent: "stop" });
check("shut up", route("shut up"), { intent: "stop" });
check("MISFIRE: bus stop near me is NOT stop", route("bus stop near me"), { intent: "search", radiusM: 1000 });
check("MISFIRE: stop inside sentence is NOT stop", route("find me a shop to stop at"), { intent: "search" });

// ---- greetings / help -------------------------------------------------------
check("greeting", route("hey looper"), { intent: "greet" });
check("gday", route("g'day mate"), { intent: "greet" });
check("help", route("what can you do"), { intent: "help" });

// ---- categories + synonyms (old build: hungry/eat→food, stay→accommodation…) -
check("hungry → Food", route("I'm hungry"), { intent: "search", category: "Food" });
check("cafe → Food (accent-folded)", route("find me a café"), { intent: "search", category: "Food" });
check("cafe plain ascii", route("find me a cafe"), { intent: "search", category: "Food" });
check("somewhere to stay → Accommodation", route("I need somewhere to stay tonight"), { intent: "connect", category: "Accommodation" });
check("hotel → Accommodation", route("show me hotels in bondi"), { intent: "search", category: "Accommodation", suburb: "bondi" });
check("job → Job-Offers", route("any jobs going around here"), { intent: "search", category: "Job-Offers" });
check("job offers → Job-Offers, not deals", route("job offers near me"), { intent: "search", category: "Job-Offers", radiusM: 1000 });
check("delivery → Fetch_Deliveries", route("I need a courier"), { intent: "connect" });
check("spa/relax → brain-only search (no pin category)", route("I want to relax at a spa"), { intent: "search", category: undefined });
check("plumber noun reaches the brain", route("find me a plumber"), { intent: "search", searchTerm: "plumber trades services" });
check("dentist noun reaches the brain", route("i want a dentist"), { intent: "search", searchTerm: "dentist health fitness wellness" });

// ---- radius (stale-closure fix: radius travels in the command) --------------
check("within 2 km", route("cafes within 2 km"), { intent: "search", category: "Food", radiusM: 2000 });
check("3 kilometres", route("restaurants within 3 kilometres"), { intent: "search", radiusM: 3000 });
check("near me → 1000", route("coffee near me"), { intent: "search", category: "Food", radiusM: 1000 });
check("explicit radius beats near me", route("cafes near me within 5 km"), { intent: "search", category: "Food", radiusM: 5000 });
check("radius-only utterance", route("within 1 km"), { intent: "set_radius", radiusM: 1000 });

// ---- specific business regex (find|show|tell me about → flyTo) ---------------
check("tell me about X → business", route("tell me about Gertrude and Alice"), { intent: "business", businessName: "gertrude and alice" });
check("where is X → business", route("where is speedos"), { intent: "business", businessName: "speedos" });
check("show X → business", route("show me Bondi Wholefoods"), { intent: "business", businessName: "bondi wholefoods" });
check("find me A florist → search (article = discovery)", route("find me a florist"), { intent: "search", searchTerm: "florist" });
check("find me a florist in Bronte → scoped search", route("find me a florist in bronte"), { intent: "search", searchTerm: "florist", suburb: "bronte" });
check("find me a florist near me → clean term + radius", route("find me a florist near me"), { intent: "search", searchTerm: "florist", radiusM: 1000 });
check("find me an accountant within 5 km → clean term + radius", route("find me an accountant within 5 km"), { intent: "search", searchTerm: "accountant", radiusM: 5000 });
check("search for an accountant bondi → scoped search", route("search for an accountant bondi"), { intent: "search", searchTerm: "accountant", suburb: "bondi" });
check("find florist in Bronte (no article) → scoped search", route("find florist in bronte"), { intent: "search", searchTerm: "florist", suburb: "bronte" });
check("search for accountant near me (no article) → scoped search", route("search for accountant near me"), { intent: "search", searchTerm: "accountant", radiusM: 1000 });
check("show me Bondi Wholefoods stays a business (name contains suburb)", route("show me Bondi Wholefoods"), { intent: "business", businessName: "bondi wholefoods" });
check("find me AN accountant → search", route("find me an accountant"), { intent: "search", searchTerm: "accountant" });
check("where is Bondi Pizza → business (naming verb beats Food)", route("where is Bondi Pizza"), { intent: "business", businessName: "bondi pizza" });
check("tell me about The Burger Shop → business", route("tell me about The Burger Shop"), { intent: "business", businessName: "burger shop" });
check("where is A cafe near me → scoped search (article)", route("where is a cafe near me"), { intent: "search", searchTerm: "cafe", radiusM: 1000 });
check("tell me about restaurants in Bronte → scoped search (locative)", route("tell me about restaurants in bronte"), { intent: "search", searchTerm: "restaurants", suburb: "bronte" });

// ---- suburbs ----------------------------------------------------------------
check("take me to suburb", route("take me to bondi junction"), { intent: "suburb", suburb: "bondi junction" });
check("go to bronte", route("go to Bronte"), { intent: "suburb", suburb: "bronte" });
check("fly to byron bay", route("fly to Byron Bay"), { intent: "suburb", suburb: "byron bay" });
check("bare suburb", route("rose bay"), { intent: "suburb", suburb: "rose bay" });
check("florist in Bronte → scoped search, not just fly", route("florist in bronte"), { intent: "search", searchTerm: "florist", suburb: "bronte" });
check("accountant bondi → scoped search", route("accountant bondi"), { intent: "search", searchTerm: "accountant", suburb: "bondi" });
check("florist in bronte within 5 km → clean term + scope + radius", route("florist in bronte within 5 km"), { intent: "search", searchTerm: "florist", suburb: "bronte", radiusM: 5000 });
check("bonding therapist is NOT bondi (word boundary)", route("bonding therapist near me"), { intent: "search", searchTerm: "bonding therapist", suburb: undefined, radiusM: 1000 });
check("best dog wash in coogee → scoped free text", route("best dog wash in coogee"), { intent: "search", suburb: "coogee", superlative: true });
check("take me to a business (not suburb)", route("take me to the health emporium"), { intent: "business", businessName: "health emporium" });
check("take me to A cafe near me → scoped search", route("take me to a cafe near me"), { intent: "search", searchTerm: "cafe", radiusM: 1000 });
check("navigate to restaurants in Bronte → scoped search", route("navigate to restaurants in bronte"), { intent: "search", searchTerm: "restaurants", suburb: "bronte" });
check("go to plumber within 2 km → scoped search", route("go to plumber within 2 km"), { intent: "search", searchTerm: "plumber", radiusM: 2000 });

// ---- offers / anti-bias -------------------------------------------------------
check("deals → offers intent", route("any deals around"), { intent: "offers", category: "Offers" });
check("pizza deals keeps subject", route("pizza deals near me"), { intent: "offers", category: "Offers", searchTerm: "pizza deals offers", radiusM: 1000 });
check("hairdresser discounts in coogee keeps subject + scope", route("hairdresser discounts in coogee"), { intent: "offers", suburb: "coogee", searchTerm: "hairdresser discounts deals offers" });
check("specials → offers", route("show me today's specials"), { intent: "offers", category: "Offers" });
check("deals in Bronte keeps suburb scope", route("any deals in bronte"), { intent: "offers", category: "Offers", suburb: "bronte" });
check("news in Byron Bay keeps suburb scope", route("news in byron bay"), { intent: "news", category: "News", suburb: "byron bay" });
check("restaurant deals → Offers beats Food", route("restaurant deals near me"), { intent: "offers", category: "Offers", radiusM: 1000 });
check("hotel offers → Offers beats Accommodation", route("hotel offers"), { intent: "offers", category: "Offers" });

// ---- sales (own frozen pin category, distinct from Offers) ---------------------
check("show me sales → Sales", route("show me sales"), { intent: "search", category: "Sales" });
check("anything for sale → Sales", route("anything for sale nearby"), { intent: "search", category: "Sales", radiusM: 1000 });
check("second hand → Sales", route("second hand furniture"), { intent: "search", category: "Sales" });
check("best cafe → superlative flagged (anti-bias)", route("what's the best cafe"), { intent: "search", category: "Food", superlative: true });

// ---- booking ------------------------------------------------------------------
check("booking intent", route("book a table for two"), { intent: "booking", searchTerm: "restaurant" });
check("booking + category", route("book me a restaurant"), { intent: "booking", category: "Food" });
check("book a table in Bronte → restaurant + scope", route("book a table in bronte"), { intent: "booking", searchTerm: "restaurant", suburb: "bronte" });
check("table for two near me → restaurant + radius", route("table for two near me"), { intent: "booking", searchTerm: "restaurant", radiusM: 1000 });
check("book a haircut keeps its noun", route("book a haircut"), { intent: "booking", searchTerm: "haircut" });

// ---- connect (the mission) ------------------------------------------------------
check("connect me with a plumber", route("connect me with a plumber"), { intent: "connect", searchTerm: "plumber" });
check("i need an electrician", route("I need an electrician"), { intent: "connect", searchTerm: "electrician" });
check("i need an electrician near me → clean term", route("I need an electrician near me"), { intent: "connect", searchTerm: "electrician", radiusM: 1000 });
check("connect me with a plumber in bronte → clean + scoped", route("connect me with a plumber in bronte"), { intent: "connect", searchTerm: "plumber", suburb: "bronte" });
check("who can help with garden", route("who can help me with my garden"), { intent: "connect" });

// ---- news / events ---------------------------------------------------------------
check("what's happening → news", route("what's happening around here"), { intent: "news", category: "News" });
check("markets → events", route("any markets on this weekend"), { intent: "news", category: "Events" });
check("sports news keeps qualifier", route("sports news in bondi"), { intent: "news", category: "News", suburb: "bondi", searchTerm: "sports news" });
check("concerts near me keeps noun", route("concerts near me"), { intent: "news", category: "Events", searchTerm: "concerts events", radiusM: 1000 });
check("find Pizza Hut → business despite category word", route("find pizza hut"), { intent: "business", businessName: "pizza hut" });
check("find pizza (bare category) → category search", route("find pizza"), { intent: "search", category: "Food" });

// ---- zoom / reset (new verbs) ------------------------------------------------------
check("zoom in", route("zoom in"), { intent: "zoom", zoomDelta: 1 });
check("zoom out", route("zoom out a bit"), { intent: "zoom", zoomDelta: -1 });
check("reset view", route("reset the view"), { intent: "reset" });

// ---- wake word stripping ------------------------------------------------------------
check("hey looper prefix stripped", route("hey looper find me a coffee"), { intent: "search", category: "Food" });

// ---- fallbacks -----------------------------------------------------------------------
check("free text → search", route("gluten free bakery bondi"), { intent: "search", category: "Food" });
check("single junk word → unknown", route("banana"), { intent: "unknown" });
check("empty → unknown", route(""), { intent: "unknown" });

console.log(`\n${passed} passed, ${failed} failed (${passed + failed} total)`);
process.exit(failed === 0 ? 0 : 1);
