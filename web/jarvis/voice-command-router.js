/* LOOPER Jarvis — voice command router (F3.2 port of the old build's grammar).
 *
 * PURE module: transcript string + context in → command object out.
 * NO map calls, NO speech calls, NO DOM — unit-testable in Node
 * (`node web/tests/voice-command-router.test.js`) and embeddable in the
 * browser as `window.LooperVoiceRouter`.
 *
 * Ported from golive_LocalLoop_Explore_html/explore-local.tsx with the
 * known bugs FIXED (see .SEED/gotchas.md):
 *   - "stop" was a substring match ("bus stop near me" misfired) → stop is
 *     now only a stop when the whole utterance is a stop command.
 *   - stale-closure radius (radius updates lagged one command) → the parsed
 *     radius always travels INSIDE the command object; consumers never read
 *     stale state.
 *   - accent sensitivity → transcripts are diacritic-folded before matching
 *     ("cafe" and "café" behave identically).
 *
 * Command object shape:
 *   {
 *     intent: 'stop'|'greet'|'help'|'search'|'category'|'business'|'suburb'|
 *             'offers'|'booking'|'connect'|'news'|'zoom'|'reset'|'set_radius'|
 *             'unknown',
 *     category?:  one of the FIXED llx11 pin categories
 *                 (News|Sales|Offers|Events|Accommodation|Job-Offers|
 *                  Fetch_Deliveries|Food),
 *     searchTerm?: string   // what to send to the LOOPER /api/search brain
 *     radiusM?: number      // parsed radius for THIS command (stale-bug fix)
 *     businessName?: string
 *     suburb?: string
 *     zoomDelta?: number    // +1 zoom in, -1 zoom out
 *     superlative?: true    // user asked for "the best" → anti-bias phrasing
 *     raw: string           // original transcript
 *   }
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.LooperVoiceRouter = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // Diacritic fold so "café"/"cafe" match (gotcha: backend seed uses "café").
  function fold(text) {
    return String(text || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase();
  }

  function clean(text) {
    return fold(text)
      .replace(/[.,!?;:]+/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  // ---- taxonomy -----------------------------------------------------------
  // Synonyms → { pin: fixed llx11 pin category | null, term: LOOPER search term }
  // Pin categories are FROZEN in Supabase: News, Sales, Offers, Events,
  // Accommodation, Job-Offers, Fetch_Deliveries, Food.
  var SYNONYMS = [
    // food (old build: hungry/eat → food)
    { re: /\b(hungry|eat|eating|food|meals?|restaurants?|cafes?|coffees?|brunch|breakfast|lunch|dinner|pizzas?|burgers?|sushi|baker(?:y|ies)|takeaway|take away|feed me|bars?|pubs?|drinks?|wine|beer)\b/, pin: "Food", term: "café restaurant food" },
    // accommodation (stay/sleep/hotel)
    { re: /\b(stay|sleep|hotels?|motels?|hostels?|accommodation|somewhere to stay|rooms?|airbnb|bnb)\b/, pin: "Accommodation", term: "accommodation hotel" },
    // offers / deals (business discounts — distinct from Sales below)
    { re: /\b(deals?|offers?|discounts?|specials?|bargains?|vouchers?|cheap)\b/, pin: "Offers", term: "deals offers" },
    // sales (for-sale / second-hand items — their own frozen pin category)
    { re: /\b(sales?|for sale|garage sales?|second ?hand|pre ?loved|marketplace)\b/, pin: "Sales", term: "for sale" },
    // jobs (job/work → jobs)
    { re: /\b(jobs?|work|hiring|employment|vacanc(?:y|ies)|careers?|gigs?)\b/, pin: "Job-Offers", term: "jobs" },
    // news
    { re: /\b(news|headlines|happening|going on|what's on|whats on)\b/, pin: "News", term: "news" },
    // events ("show" as a noun is deliberately absent — it collides with "show me X")
    { re: /\b(events?|concerts?|markets?|festivals?|exhibitions?)\b/, pin: "Events", term: "events" },
    // deliveries / couriers
    { re: /\b(deliver(?:y|ies)|couriers?|pick up|pickup|drop off|fetch)\b/, pin: "Fetch_Deliveries", term: "delivery courier" },
    // health & wellbeing (spa/relax/fitness — no fixed pin category; brain-only)
    { re: /\b(spas?|relax|massage|fitness|gyms?|yoga|pilates|doctors?|dentists?|physio|chemist|pharmac(?:y|ies)|health|wellness|hair|barbers?|beauty)\b/, pin: null, term: "health fitness wellness" },
    // shopping (no fixed pin category; brain-only)
    { re: /\b(shops?|shopping|stores?|boutiques?|clothes|clothing|gifts?|surf shop|bookshop|book store)\b/, pin: null, term: "shop retail" },
    // trades & services (brain-only)
    { re: /\b(plumbers?|electricians?|builders?|carpenters?|painters?|hand(?:y|i)m(?:a|e)n|mechanics?|locksmiths?|cleaners?|gardeners?|tradies?|trades)\b/, pin: null, term: "trades services" },
    // pets (brain-only)
    { re: /\b(vets?|veterinarians?|pets?|dog groomers?|dog walkers?|kennels?)\b/, pin: null, term: "vet pets" },
  ];

  // Default suburbs Looper can fly to without a geocoder (Eastern Suburbs
  // seed set from the master plan + Byron). Hosts may extend via context.
  var SUBURBS = {
    "bondi beach": { lng: 151.2743, lat: -33.8908, zoom: 15 },
    "north bondi": { lng: 151.2790, lat: -33.8850, zoom: 15 },
    "bondi junction": { lng: 151.2477, lat: -33.8912, zoom: 15 },
    "bondi": { lng: 151.2743, lat: -33.8915, zoom: 14.5 },
    "tamarama": { lng: 151.2700, lat: -33.8990, zoom: 15 },
    "bronte": { lng: 151.2630, lat: -33.9036, zoom: 15 },
    "clovelly": { lng: 151.2610, lat: -33.9120, zoom: 15 },
    "coogee": { lng: 151.2550, lat: -33.9200, zoom: 15 },
    "randwick": { lng: 151.2410, lat: -33.9140, zoom: 14.5 },
    "maroubra": { lng: 151.2380, lat: -33.9500, zoom: 14.5 },
    "rose bay": { lng: 151.2670, lat: -33.8710, zoom: 15 },
    "double bay": { lng: 151.2430, lat: -33.8770, zoom: 15 },
    "vaucluse": { lng: 151.2780, lat: -33.8560, zoom: 15 },
    "dover heights": { lng: 151.2810, lat: -33.8700, zoom: 15 },
    "waverley": { lng: 151.2540, lat: -33.8980, zoom: 15 },
    "woollahra": { lng: 151.2410, lat: -33.8870, zoom: 15 },
    "paddington": { lng: 151.2260, lat: -33.8840, zoom: 15 },
    "byron bay": { lng: 153.6120, lat: -28.6474, zoom: 14.5 },
  };

  // ---- parsers ------------------------------------------------------------

  // Whole-utterance stop command (misfire fix: "bus stop near me" ≠ stop).
  // Prefix accepts every wake-word variant the orchestrator accepts
  // (hey/ok/okay looper) so "okay looper stop" interrupts hands-free too.
  var STOP_RE = /^(?:(?:hey|ok|okay)\s+looper[,!]?\s*)?(?:please\s+)?(?:stop|cancel|pause|quiet|silence|shut up|be quiet|that's enough|thats enough|never mind|nevermind)(?:\s+(?:talking|listening|it|that|now|please))*$/;

  var GREET_RE = /^(?:hey|hi|hello|yo|g'day|gday|good morning|good arvo|good afternoon|good evening)(?:\s+(?:looper|there|mate))*$/;

  // Whole-utterance help only — "who can HELP me with my garden" is a
  // connect request, not a help request.
  var HELP_RE = /^(?:looper\s+)?(?:help(?: me)?|what can you do|what do you do|how do you work|what are you|who are you|show me the menu|menu)$/;

  // Radius: "within 2 km", "3 kilometres", "500 m", "near me" → 1000 m.
  function parseRadiusM(t) {
    if (/\b(near me|nearby|around me|close by|walking distance)\b/.test(t)) return 1000;
    var km = t.match(/\b(\d+(?:\.\d+)?)\s*(?:km|kilometre|kilometres|kilometer|kilometers|k)\b/);
    if (km) return Math.round(parseFloat(km[1]) * 1000);
    var m = t.match(/\b(\d+)\s*(?:m|metres|meters)\b/);
    if (m) return parseInt(m[1], 10);
    return null;
  }

  // Old build's specific-business regex, widened verbs, greedy name capture.
  // An indefinite article after the verb ("find me A florist") signals a
  // category-style discovery, not a proper business name — captured
  // separately so route() can send those to free-text search instead.
  var BUSINESS_RE = /\b(?:find(?: me)?|show me|show|tell me about|where is|where's|look up|search for)\s+(?:(a|an|some)\s+|the\s+)?([\w\s'&-]+)$/;

  // "take me to X" / "go to X" / "fly to X" — suburb first, else business.
  var GOTO_RE = /\b(?:take me to|go to|fly to|navigate to|head to|jump to)\s+(?:the\s+)?([\w\s'&-]+)$/;

  var ZOOM_IN_RE = /\b(?:zoom in|closer|get closer)\b/;
  var ZOOM_OUT_RE = /\b(?:zoom out|further out|pull back|wider)\b/;
  var RESET_RE = /\b(?:reset(?: the)?(?: view| map)?|start over|show everything|whole map|zoom to fit)\b/;

  var BOOKING_RE = /\b(?:book|booking|reserve|reservation|table for)\b/;

  // The connect-people mission: "connect me with…", "who can help me with…",
  // "i need a plumber", "put me in touch with…". ("find me a X" is plain
  // search — keeping it out of here lets categories route it.)
  var CONNECT_RE = /\b(?:connect me(?: with| to)?|put me in touch with|who can help(?: me)?(?: with)?|i need|looking for)\s+([\w\s'&-]+)$/;

  function stripArticles(text) {
    return text.replace(/^(?:a|an|some|the|my)\s+/, "").trim();
  }

  var SUPERLATIVE_RE = /\b(?:best|greatest|top|number one|no 1)\b/;

  var FILLER_RE = /\b(?:please|now|thanks|thank you|mate|for me)\b/g;

  // exact=true: the text must BE the suburb (plus filler words) — used for
  // goto/business-name candidates so "bondi wholefoods" isn't eaten by
  // "bondi". exact=false: the suburb may appear anywhere ("cafes in bronte").
  function matchSuburb(name, suburbs, exact) {
    var n = clean(name).replace(FILLER_RE, "").replace(/\s+/g, " ").trim();
    if (!n) return null;
    // longest-key-first so "bondi junction" wins over "bondi"
    var keys = Object.keys(suburbs).sort(function (a, b) { return b.length - a.length; });
    for (var i = 0; i < keys.length; i++) {
      if (exact ? n === keys[i] : n.indexOf(keys[i]) !== -1) return keys[i];
    }
    return null;
  }

  function matchCategory(t) {
    for (var i = 0; i < SYNONYMS.length; i++) {
      if (SYNONYMS[i].re.test(t)) return SYNONYMS[i];
    }
    return null;
  }

  /**
   * Route a final transcript to a command object.
   * @param {string} transcript
   * @param {object} [context] { radiusM?, activeCategory?, suburbs? (extra) }
   */
  function route(transcript, context) {
    context = context || {};
    var suburbs = Object.assign({}, SUBURBS, context.suburbs || {});
    var t = clean(transcript);
    var cmd = { intent: "unknown", raw: String(transcript || "") };
    if (!t) return cmd;

    // Strip a leading wake word so "hey looper find me a cafe" routes clean.
    var stripped = t.replace(/^(?:hey|ok|okay)\s+looper[,!]?\s*/, "");

    if (STOP_RE.test(t)) { cmd.intent = "stop"; return cmd; }
    if (GREET_RE.test(t)) { cmd.intent = "greet"; return cmd; }
    if (HELP_RE.test(stripped)) { cmd.intent = "help"; return cmd; }

    var radiusM = parseRadiusM(stripped);
    if (radiusM !== null) cmd.radiusM = radiusM; // stale-closure fix: travels with the command

    if (ZOOM_IN_RE.test(stripped)) { cmd.intent = "zoom"; cmd.zoomDelta = 1; return cmd; }
    if (ZOOM_OUT_RE.test(stripped)) { cmd.intent = "zoom"; cmd.zoomDelta = -1; return cmd; }
    if (RESET_RE.test(stripped)) { cmd.intent = "reset"; return cmd; }

    if (SUPERLATIVE_RE.test(stripped)) cmd.superlative = true;

    // "take me to bronte" → suburb; "take me to gertrude and alice" → business
    var goto_ = stripped.match(GOTO_RE);
    if (goto_) {
      var sub = matchSuburb(goto_[1], suburbs, true);
      if (sub) {
        cmd.intent = "suburb";
        cmd.suburb = sub;
        cmd.coords = suburbs[sub];
        return cmd;
      }
      cmd.intent = "business";
      cmd.businessName = stripArticles(goto_[1].trim());
      return cmd;
    }

    var category = matchCategory(stripped);
    var booking = BOOKING_RE.test(stripped);

    // Connect intent (the mission): "connect me with a plumber",
    // "i need an electrician", "who can help me with my garden"
    var connect = stripped.match(CONNECT_RE);
    if (connect && !booking) {
      var connectTarget = stripArticles(connect[1].trim());
      var connectSuburb = matchSuburb(connectTarget, suburbs, false);
      cmd.intent = "connect";
      cmd.searchTerm = connectTarget;
      if (category) {
        cmd.category = category.pin || undefined;
        if (connectTarget.split(" ").length > 4) cmd.searchTerm = termFor(category);
      }
      if (connectSuburb) { cmd.suburb = connectSuburb; cmd.coords = suburbs[connectSuburb]; }
      return cmd;
    }

    // Suburb scope, computed ONCE so every category-style intent keeps it
    // ("deals in Bronte" must not silently search the current map center).
    var scopeSub = matchSuburb(stripped, suburbs, false);
    function applyScope(c) {
      if (scopeSub) { c.suburb = scopeSub; c.coords = suburbs[scopeSub]; }
      return c;
    }
    // The brain should see the user's actual noun, not just our broad
    // bucket term ("find me a plumber" must send "plumber", not only
    // "trades services") — prepend the matched synonym to the term.
    function termFor(cat) {
      var m = stripped.match(cat.re);
      var noun = m && m[0] ? m[0] : "";
      return noun && cat.term.indexOf(noun) === -1 ? noun + " " + cat.term : cat.term;
    }

    if (booking) {
      cmd.intent = "booking";
      if (category) { cmd.category = category.pin || undefined; cmd.searchTerm = termFor(category); }
      else cmd.searchTerm = stripped.replace(BOOKING_RE, "").trim() || "restaurant";
      return applyScope(cmd);
    }

    // Offers/deals get their own intent (anti-bias handling downstream).
    if (category && category.pin === "Offers") {
      cmd.intent = "offers";
      cmd.category = "Offers";
      cmd.searchTerm = category.term;
      return applyScope(cmd);
    }

    // News/events phrasing like "what's happening"
    if (category && (category.pin === "News" || category.pin === "Events")) {
      cmd.intent = "news";
      cmd.category = category.pin;
      cmd.searchTerm = category.term;
      return applyScope(cmd);
    }

    // Specific business: old build's /(?:find|show|tell me about) X/ regex.
    // Category words win over the business regex ("find me a cafe" = search).
    var biz = stripped.match(BUSINESS_RE);
    if (biz && !category) {
      var name = stripArticles(biz[2].trim());
      var asSuburb = matchSuburb(name, suburbs, true);
      if (asSuburb) {
        cmd.intent = "suburb";
        cmd.suburb = asSuburb;
        cmd.coords = suburbs[asSuburb];
        return cmd;
      }
      if (biz[1]) {
        // "find me a florist" — indefinite article ⇒ discovery, not a name
        cmd.intent = "search";
        cmd.searchTerm = name;
        return cmd;
      }
      cmd.intent = "business";
      cmd.businessName = name;
      return cmd;
    }

    if (category) {
      cmd.intent = "search";
      if (category.pin) cmd.category = category.pin;
      cmd.searchTerm = termFor(category);
      // a mentioned suburb scopes the search ("cafes in bronte")
      return applyScope(cmd);
    }

    // Bare suburb mention: "bondi junction please"
    if (scopeSub && stripped.split(" ").length <= 4) {
      cmd.intent = "suburb";
      cmd.suburb = scopeSub;
      cmd.coords = suburbs[scopeSub];
      return cmd;
    }

    // Radius present: if other words remain once the radius phrase is
    // removed, it's a search ("bus stop near me" → search "bus stop");
    // a bare radius ("within 2 km") re-runs the last search with it.
    if (radiusM !== null) {
      var leftover = stripped
        .replace(/\b(?:within|inside|in)?\s*\d+(?:\.\d+)?\s*(?:km|kilometres?|kilometers?|k|m|metres|meters)\b/g, " ")
        .replace(/\b(?:near me|nearby|around me|close by|walking distance)\b/g, " ")
        .replace(/\s+/g, " ")
        .trim();
      if (leftover) {
        cmd.intent = "search";
        cmd.searchTerm = leftover;
      } else {
        cmd.intent = "set_radius";
      }
      return cmd;
    }

    // Anything else with a few words → free-text search via the brain.
    if (stripped.split(" ").length >= 2) {
      cmd.intent = "search";
      cmd.searchTerm = stripped;
      return cmd;
    }

    return cmd;
  }

  return {
    route: route,
    fold: fold,
    clean: clean,
    SUBURBS: SUBURBS,
    PIN_CATEGORIES: ["News", "Sales", "Offers", "Events", "Accommodation", "Job-Offers", "Fetch_Deliveries", "Food"],
  };
});
