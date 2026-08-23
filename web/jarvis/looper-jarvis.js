/* LOOPER Jarvis — the voice companion that lives ON the map (F3.3 + F4.2).
 *
 * One script tag turns any Mapbox-GL-compatible page into a Jarvis-driven
 * map: the animated Looper face docks bottom-right, listens ("Hey Looper"),
 * routes speech through the ported voice grammar (voice-command-router.js),
 * answers from the LOOPER brain (/api/search), and drives the map through
 * LooperMapBus. Falls back to typed input where Web Speech is unavailable
 * (Firefox — gotcha: HTTPS-only mic, Chrome/Edge/Safari only).
 *
 * Load order: voice-command-router.js, looper-map-bus.js, looper-face.js,
 * then this file. Then:
 *
 *   LooperJarvis.init({
 *     map: mapInstance,                        // mapbox-gl or maplibre-gl
 *     apiBase: "http://localhost:8000/api",   // or LocalLoopConfig.looperApi
 *     district: "Bondi",
 *     home: { lng: 151.2743, lat: -33.8915, zoom: 14.5 },
 *     markerLib: window.maplibregl,
 *     onCategory: (cat) => {...},              // sync host filter chips
 *   });
 *
 * PERSONA (from SEED.md / the master plan — Looper is LocalLoop's community
 * connection agent): warm, local, useful. NEVER declares a "best" business,
 * always offers multiple options ranked only by community reviews, recency
 * and distance. Discounts size markers, never rankings. Its mission is to
 * connect locals to each other and to the businesses around them.
 */
(function (root) {
  "use strict";

  var Router = root.LooperVoiceRouter;
  var Bus = root.LooperMapBus;
  var Face = root.LooperFace;

  // ---------------------------------------------------------------- persona
  var PERSONA = {
    name: "Looper",
    // No spoken persona line may BEGIN with a wake prefix + "Looper": the
    // open mic hears Looper's own TTS, and "Hey! I'm Looper…" is one ASR
    // dropped-word away from waking itself mid-greeting.
    greetings: [
      "Hi! I'm Looper, your {district} Local Loop guide. Ask me to find food, deals, jobs — or say take me to Bondi.",
      "G'day! Looper here. What are you after — a feed, a deal, or someone local to help you out?",
    ],
    acks: ["On it.", "One sec.", "Let me have a look.", "Checking the loop."],
    noResults: [
      "I couldn't find anything for that around here yet. Want to be the first to add it to the loop?",
    ],
    apiDown: [
      "Sorry — the Looper brain is offline right now. Try me again in a tick.",
    ],
    unknown: [
      "I didn't catch that. Try: find me a café, any deals nearby, or take me to Bondi Junction.",
    ],
    antiBias: "I don't pick favourites — the community's reviews decide, and the full list is on your screen.",
    superlative: "I don't do 'best' — I show you what locals actually say. ",
    connectOutro: " Tap any card to see how to reach them — that's what the loop is for: locals helping locals.",
    offersNote: " Deals change the size of a pin, never its rank — reviews always come first.",
    bookingNote: " I can't make the booking for you yet, but every card has contact details.",
    help:
      "I'm Looper — the voice of your Local Loop map. You can say: find me a café. Any deals near me? " +
      "Who can help me with my garden? Take me to Bronte. Zoom in. Reset the map. " +
      "I rank by community reviews only — never by who pays. And if you run a business, ask me about getting your Hybrid Card.",
  };

  function pick(list) { return list[Math.floor(Math.random() * list.length)]; }

  // ------------------------------------------------------------------ state
  var S = {
    inited: false,
    apiBase: "http://localhost:8000/api",
    district: "Bondi",
    home: { lng: 151.2743, lat: -33.8915, zoom: 14.5 },
    face: null,
    recognition: null,
    listening: false,
    handsFree: false, // wake-word mode: always listening, only "hey looper …" acts
    recErrorStreak: 0, // consecutive recognition errors — bail to typing at 4
    reqSeq: 0, // request sequence: every new command invalidates in-flight fetch UI
    speaking: false,
    lastSearch: null, // {cmd} for set_radius re-runs (stale-closure fix: radius comes from the NEW command)
    lastRadiusM: 1500,
    wantHandsFree: false, // the USER's intent — survives recognizer deaths so hidden-tab drops can re-arm
    droppedWhileHidden: false, // the last bail happened while the page was hidden (screen-lock/tab-switch)
    statusPinned: false, // "brain offline" stays visible until the next turn instead of being settled away
    ui: {},
    map: null,
    speechSupported: false,
    onMicOpen: null, // host hook: pause a coexisting wake-word mic (Porcupine); may return a Promise
    onMicClose: null, // host hook: resume it when Jarvis lets go
    beforeSpeak: null, // host hook: silence competing audio (news podcast) before TTS
    // anonymous per-page-load session id — telemetry only, never identity
    session: (root.crypto && root.crypto.randomUUID) ? root.crypto.randomUUID() : "s" + String(Math.random()).slice(2),
  };

  // Wake vocabulary lives in the router (single source of truth, incl. ASR
  // mishears like "loopa"/"luper"); fall back to the old literals if an
  // older cached router is loaded alongside a newer dock.
  var WAKE_RE = Router.WAKE_RE || /^(?:hey|ok|okay)\s+looper\b/;
  var WAKE_STRICT_RE = Router.WAKE_STRICT_RE || /^(?:hey|ok|okay)\s+looper\b/;

  // ------------------------------------------------------------------- UI
  var CSS = [
    // Position is host-tunable (init opts.dock) so the dock can clear a
    // site's own fixed UI (mobile bottom nav, Mapbox bottom-right controls).
    "#looper-jarvis{position:fixed;right:var(--lj-right,18px);bottom:var(--lj-bottom,18px);z-index:9999;display:flex;flex-direction:column;align-items:flex-end;gap:10px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;}",
    "@media (max-width:768px){#looper-jarvis{bottom:var(--lj-bottom-mobile,var(--lj-bottom,18px));right:var(--lj-right-mobile,var(--lj-right,12px));}}",
    // narrow phones: the dock row (wake + status + face) must never exceed
    // the viewport — wrap the pills above a smaller face
    "@media (max-width:480px){#looper-jarvis{max-width:calc(100vw - 24px);}#looper-jarvis .lj-dock{flex-wrap:wrap;justify-content:flex-end;row-gap:6px;}#looper-jarvis .lj-status{max-width:140px;font-size:11px;padding:5px 10px;}#looper-jarvis .lj-wake{font-size:11px;padding:5px 9px;}}",
    "#looper-jarvis .lj-panel{width:min(340px,calc(100vw - 36px));max-height:46vh;overflow-y:auto;background:rgba(10,12,18,.94);color:#e8ecf4;border:1px solid rgba(86,189,255,.35);border-radius:16px;padding:12px 14px;backdrop-filter:blur(14px);box-shadow:0 12px 40px rgba(0,0,0,.45);display:none;}",
    "#looper-jarvis .lj-panel.lj-open{display:block;}",
    "#looper-jarvis .lj-msg{font-size:13.5px;line-height:1.45;margin:0 0 8px;}",
    "#looper-jarvis .lj-option{display:flex;justify-content:space-between;gap:8px;padding:8px 10px;margin:6px 0;border:1px solid rgba(255,255,255,.09);border-radius:10px;background:rgba(255,255,255,.04);cursor:pointer;}",
    "#looper-jarvis .lj-option:hover{border-color:rgba(86,189,255,.6);}",
    "#looper-jarvis .lj-option .lj-name{font-weight:650;font-size:13px;}",
    "#looper-jarvis .lj-option .lj-meta{font-size:12px;color:#9fb4c8;}",
    "#looper-jarvis .lj-option a{color:#7ddfff;text-decoration:none;font-size:12px;white-space:nowrap;}",
    "#looper-jarvis .lj-dock{display:flex;align-items:center;gap:10px;}",
    "#looper-jarvis .lj-face-btn{position:relative;border:none;background:none;padding:0;cursor:pointer;border-radius:999px;}",
    "#looper-jarvis .lj-face-btn:focus-visible{outline:3px solid #7ddfff;outline-offset:3px;}",
    "#looper-jarvis .lj-status{max-width:220px;background:rgba(10,12,18,.9);border:1px solid rgba(86,189,255,.3);color:#bfe9ff;font-size:12px;padding:6px 12px;border-radius:999px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}",
    "#looper-jarvis .lj-wake{border:1px solid rgba(86,189,255,.3);background:rgba(10,12,18,.9);color:#7ddfff;font-size:12px;padding:6px 11px;border-radius:999px;cursor:pointer;}",
    "#looper-jarvis .lj-wake.on{background:#56bdff;color:#04121e;border-color:#56bdff;}",
    "#looper-jarvis .lj-input-row{display:none;gap:6px;width:min(340px,calc(100vw - 36px));}",
    "#looper-jarvis .lj-input-row.lj-open{display:flex;}",
    "#looper-jarvis .lj-input-row input{flex:1;background:rgba(10,12,18,.94);border:1px solid rgba(86,189,255,.35);color:#e8ecf4;border-radius:999px;padding:9px 14px;font-size:13px;outline:none;}",
    "#looper-jarvis .lj-input-row button{background:rgba(86,189,255,.9);border:none;color:#04121e;font-weight:700;border-radius:999px;padding:0 16px;cursor:pointer;}",
    ".looper-result-marker{width:18px;height:18px;border-radius:999px;background:#56bdff;border:3px solid #0b2437;box-shadow:0 0 12px rgba(86,189,255,.8);cursor:pointer;}",
    ".looper-popup{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;font-size:13px;line-height:1.45;color:#12202e;}",
    ".looper-popup a{color:#0b76c4;font-weight:600;text-decoration:none;}",
    ".looper-popup-cat{color:#5a7186;font-size:12px;}",
    ".looper-popup-meta{font-size:12px;}",
  ].join("\n");

  function injectCss() {
    if (document.getElementById("looper-jarvis-css")) return;
    var s = document.createElement("style");
    s.id = "looper-jarvis-css";
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  function buildUi(dock) {
    injectCss();
    var wrap = document.createElement("div");
    wrap.id = "looper-jarvis";
    // host offsets → CSS vars (e.g. llx11: clear the mobile bottom nav and
    // the map's bottom-right NavigationControl)
    if (dock) {
      if (dock.right) wrap.style.setProperty("--lj-right", dock.right);
      if (dock.bottom) wrap.style.setProperty("--lj-bottom", dock.bottom);
      if (dock.mobileBottom) wrap.style.setProperty("--lj-bottom-mobile", dock.mobileBottom);
      if (dock.mobileRight) wrap.style.setProperty("--lj-right-mobile", dock.mobileRight);
    }
    wrap.innerHTML =
      '<div class="lj-panel" id="lj-panel"></div>' +
      '<div class="lj-input-row" id="lj-input-row">' +
      '  <input id="lj-input" type="text" placeholder="Ask Looper… e.g. find me a café" aria-label="Ask Looper">' +
      '  <button id="lj-send" aria-label="Send">➤</button>' +
      "</div>" +
      '<div class="lj-dock">' +
      '  <button class="lj-wake" id="lj-wake" title="Hands-free: say ‘Hey Looper …’" aria-label="Toggle hands-free Hey Looper mode">🎙 Hey Looper</button>' +
      '  <div class="lj-status" id="lj-status">Tap my face to talk</div>' +
      '  <button class="lj-face-btn" id="lj-face-btn" aria-label="Talk to Looper"></button>' +
      "</div>";
    document.body.appendChild(wrap);

    S.ui.panel = wrap.querySelector("#lj-panel");
    S.ui.status = wrap.querySelector("#lj-status");
    S.ui.faceBtn = wrap.querySelector("#lj-face-btn");
    S.ui.wake = wrap.querySelector("#lj-wake");
    S.ui.inputRow = wrap.querySelector("#lj-input-row");
    S.ui.input = wrap.querySelector("#lj-input");
    S.ui.send = wrap.querySelector("#lj-send");

    // smaller face on narrow phones so the dock fits beside the map UI
    var faceSize = (root.innerWidth && root.innerWidth <= 480) ? 88 : 118;
    S.face = Face.mount(S.ui.faceBtn, { size: faceSize });

    S.ui.faceBtn.addEventListener("click", toggleListening);
    S.ui.wake.addEventListener("click", toggleHandsFree);
    S.ui.send.addEventListener("click", function () { submitTyped(); });
    S.ui.input.addEventListener("keydown", function (e) { if (e.key === "Enter") submitTyped(); });
  }

  function submitTyped() {
    var q = (S.ui.input.value || "").trim();
    if (!q) return;
    S.ui.input.value = "";
    ask(q);
  }

  function setStatus(text) { S.ui.status.textContent = text; }

  // The dock's resting truth after a turn: listening face + hands-free hint
  // while the mic is hot — never "idle" with an open mic, never a stale ack.
  function settleUi() {
    S.face.setMood(S.listening ? "listening" : "idle");
    if (S.statusPinned) return; // "Looper brain offline" stays until the next turn
    setStatus(S.listening
      ? (S.handsFree ? "Hands-free — say “Hey Looper …”" : "Listening… say “find me a café”")
      : "Tap my face to talk");
  }

  function showPanel(html) {
    S.ui.panel.innerHTML = html;
    S.ui.panel.classList.add("lj-open");
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  // Only http(s) links ever render — owner-supplied card_url/website could
  // otherwise smuggle javascript:/data: URIs into the options panel.
  function safeUrl(value) {
    if (!value) return null;
    try {
      var u = new URL(String(value), root.location ? root.location.href : "https://localloop.ai");
      return (u.protocol === "http:" || u.protocol === "https:") ? u.href : null;
    } catch (e) {
      return null;
    }
  }

  // ------------------------------------------------------------- speech out
  // Old build: rate 0.9 / pitch 1.1, chunk >200 chars (Chrome cutoff bug),
  // cancel() on barge-in. Ported with .lang + onerror (gotcha fixes).
  function chunkText(text, max) {
    max = max || 200;
    var out = [];
    var sentences = String(text).match(/[^.!?]+[.!?]*\s*/g) || [String(text)];
    var buf = "";
    sentences.forEach(function (s) {
      if ((buf + s).length > max && buf) { out.push(buf.trim()); buf = s; }
      else buf += s;
      while (buf.length > max) { out.push(buf.slice(0, max).trim()); buf = buf.slice(max); }
    });
    if (buf.trim()) out.push(buf.trim());
    return out;
  }

  // Barge-in guard: cancel() doesn't stop a dead utterance's async
  // onend/onerror from firing later — each speak() takes a new generation
  // and stale callbacks no-op instead of speaking old chunks or flipping
  // S.speaking under the new answer.
  var speakGen = 0;

  function speak(text, done) {
    if (!("speechSynthesis" in root)) { if (done) done(); return; }
    // host hook: silence competing audio first (e.g. the site's news
    // podcast player) so Looper doesn't talk over it
    if (S.beforeSpeak) { try { S.beforeSpeak(); } catch (e) { /* never block speech */ } }
    stopSpeaking();
    var chunks = chunkText(text);
    if (!chunks.length) { if (done) done(); return; }
    var gen = ++speakGen;
    S.speaking = true;
    S.face.startTalking();
    var i = 0;
    function next() {
      if (gen !== speakGen) return; // canceled: a newer speak()/stop owns the state
      if (!S.speaking || i >= chunks.length) { finish(); return; }
      var u = new SpeechSynthesisUtterance(chunks[i++]);
      u.lang = "en-AU";
      u.rate = 0.95;
      var voice = pickVoice();
      // Neural/natural voices sound artifacted when pitch-shifted — only
      // brighten the plain synthesis engines.
      u.pitch = (voice && /natural|neural/i.test(voice.name)) ? 1.0 : 1.05;
      if (voice) u.voice = voice;
      u.onend = next;
      u.onerror = finish;
      root.speechSynthesis.speak(u);
    }
    function finish() {
      if (gen !== speakGen) return; // stale callback from a canceled utterance
      if (!S.speaking) return;
      S.speaking = false;
      S.face.stopTalking();
      settleUi(); // gen guard above means only the CURRENT turn settles the dock
      if (done) done();
    }
    next();
  }

  var cachedVoice = null;
  // Quality-ranked picker: en-AU still beats other English (the persona is
  // local), but within a tier the Natural/Premium/Google engines beat the
  // robotic compact/eSpeak ones — the single biggest audible upgrade on
  // macOS (Karen vs Karen Premium), Edge (Natasha Online Natural) and Linux.
  function scoreVoice(v) {
    // Tier gap (100) exceeds the max quality bonus (+60) so a premium en-US
    // voice can never tie or beat a plain en-AU one. The one intended
    // tier-break stays: a robotic engine's -60 drops an eSpeak-class en-AU
    // (140) below a premium other-English voice (160).
    var s;
    if (/en[-_]AU/i.test(v.lang)) s = 200; // Aussie accent first
    else if (/^en([-_]|$)/i.test(v.lang)) s = 100; // any English second
    else return -1;
    var n = String(v.name || "");
    if (/natural|neural|premium|enhanced/i.test(n)) s += 30;
    if (/google/i.test(n)) s += 20;
    if (/siri/i.test(n)) s += 10;
    if (/compact|espeak|eloquence/i.test(n)) s -= 60; // known-robotic engines
    return s;
  }
  function pickVoice() {
    if (cachedVoice) return cachedVoice;
    var voices = root.speechSynthesis.getVoices() || [];
    var best = null;
    var bestScore = 0;
    for (var i = 0; i < voices.length; i++) {
      var sc = scoreVoice(voices[i]);
      if (sc > bestScore) { bestScore = sc; best = voices[i]; }
    }
    cachedVoice = best;
    return cachedVoice;
  }
  if ("speechSynthesis" in root) {
    // addEventListener so a host page's own voiceschanged handler coexists
    // instead of one clobbering the other.
    if (root.speechSynthesis.addEventListener) {
      root.speechSynthesis.addEventListener("voiceschanged", function () { cachedVoice = null; });
    } else {
      root.speechSynthesis.onvoiceschanged = function () { cachedVoice = null; };
    }
  }

  function stopSpeaking() {
    speakGen++; // invalidate in-flight utterance callbacks
    if ("speechSynthesis" in root) root.speechSynthesis.cancel();
    if (S.speaking) { S.speaking = false; S.face.stopTalking(); }
  }

  // -------------------------------------------------------------- speech in
  function setupRecognition() {
    var SR = root.SpeechRecognition || root.webkitSpeechRecognition;
    if (!SR) {
      S.speechSupported = false;
      S.ui.inputRow.classList.add("lj-open"); // Firefox et al: typed fallback
      setStatus("Type to ask Looper (voice needs Chrome/Safari)");
      return;
    }
    S.speechSupported = true;
    var rec = new SR();
    rec.lang = "en-AU";
    rec.continuous = false; // one utterance per tap; auto-restarts while enabled
    rec.interimResults = true;

    rec.onresult = function (event) {
      // results that land AFTER the user canceled the turn (tap-to-stop)
      // must not act — the mic was closed deliberately, and a late final
      // would launch the very command the user tried to cancel
      if (!S.listening) return;
      var finalText = "";
      var interim = "";
      for (var i = event.resultIndex; i < event.results.length; i++) {
        if (event.results[i].isFinal) finalText += event.results[i][0].transcript;
        else interim += event.results[i][0].transcript;
      }
      if (interim) {
        setStatus("“" + interim.trim() + "”");
        S.recErrorStreak = 0; // audio is flowing — the mic works
        if (!S.handsFree) stopSpeaking(); // push-to-talk: any voice barges in
        // Hands-free: halt TTS the moment a wake phrase is heard, so the
        // barge-in below feels instant once the final transcript lands.
        else if (S.speaking && WAKE_STRICT_RE.test(Router.clean(interim))) stopSpeaking();
      }
      var text = finalText.trim();
      if (!text) return;
      S.recErrorStreak = 0; // real speech arrived — the mic works
      if (S.handsFree) {
        // Open mic hears Looper's own TTS — while speaking, only an
        // explicit stop command or a wake-PREFIXED command interrupts
        // (else it would cancel itself).
        if (S.speaking) {
          // "hey/okay + looper" is provably the USER: no spoken persona
          // line starts with a wake prefix (see PERSONA comment above).
          if (WAKE_STRICT_RE.test(Router.clean(text))) {
            stopSpeaking();
            ask(text);
            return;
          }
          if (Router.route(text).intent === "stop") {
            stopSpeaking();
            // "stop listening" mid-speech closes the mic too
            if (/\blisten/i.test(text)) stopListening();
          }
          return;
        }
        // Only utterances addressed to Looper act; everything else is
        // ignored (never logged, never sent anywhere).
        if (!WAKE_RE.test(Router.clean(text))) {
          setStatus("Say “Hey Looper …” to ask");
          return;
        }
      } else {
        // Push-to-talk is ONE utterance: don't let onend re-open the mic
        // and keep transcribing ambient speech after the command.
        S.listening = false;
      }
      ask(text);
    };
    rec.onerror = function (event) {
      // gotcha fix: the old build had no onerror at all
      var err = String(event.error || "");
      if (err === "not-allowed" || err === "service-not-allowed" ||
          err === "audio-capture" || err === "network") {
        // Fail closed: a dead mic or speech-service outage must not spin
        // a restart loop — drop to typed input instead.
        S.droppedWhileHidden = !!(document.hidden); // screen-lock kills recognition this way
        stopListening();
        S.ui.inputRow.classList.add("lj-open");
        setStatus(err === "audio-capture" ? "No microphone found — type to ask Looper" : "Mic unavailable — type to ask Looper");
        return;
      }
      // Hands-free: silence is the NORMAL state of a wake-word mic — Chrome
      // ends continuous recognition with "no-speech" after a few quiet
      // seconds, and counting those would bail hands-free in a quiet room.
      // Push-to-talk keeps counting: there, repeated no-speech means the
      // turn is dead.
      if (err === "no-speech" && S.handsFree) return;
      // Transient errors (aborted, push-to-talk no-speech): count them; onend
      // bails out of restarting once the streak shows nothing is getting through.
      S.recErrorStreak = (S.recErrorStreak || 0) + 1;
    };
    rec.onend = function () {
      if (S.listening) {
        if ((S.recErrorStreak || 0) >= 4) {
          S.droppedWhileHidden = !!(document.hidden); // backgrounded tabs die by streak too
          stopListening();
          // this onend is the recognizer's LAST — no later one will run the
          // release branch below, so let the host wake word back in here
          if (S.onMicClose) { try { S.onMicClose(); } catch (e) { /* never block */ } }
          S.ui.inputRow.classList.add("lj-open");
          setStatus("Voice keeps dropping — type to ask Looper");
          return;
        }
        // small delay so an erroring recognizer can't hot-loop restarts
        setTimeout(function () {
          if (!S.listening) return;
          tryStartRecognition();
        }, 300);
      } else {
        // mic session truly over (covers both stopListening and the
        // push-to-talk one-shot path) — let the host's wake word back in
        if (S.onMicClose) { try { S.onMicClose(); } catch (e) { /* host hook — never block */ } }
        if (!S.speaking) S.face.setMood("idle");
      }
    };
    S.recognition = rec;
  }

  function toggleListening() {
    if (!S.speechSupported) {
      S.ui.inputRow.classList.toggle("lj-open");
      if (S.ui.inputRow.classList.contains("lj-open")) S.ui.input.focus();
      return;
    }
    if (S.listening) stopListening();
    else startListening();
  }

  // Wake-word mode: keep the mic open, act only on "Hey Looper …".
  function toggleHandsFree() {
    if (!S.speechSupported) {
      setStatus("Voice needs Chrome/Safari");
      return;
    }
    S.handsFree = !S.handsFree;
    S.wantHandsFree = S.handsFree; // remember the USER's intent for auto re-arm
    S.ui.wake.classList.toggle("on", S.handsFree);
    if (S.handsFree) {
      startListening();
      setStatus("Hands-free — say “Hey Looper …”");
    } else {
      stopListening();
    }
  }

  function startListening() {
    if (!S.recognition) return;
    stopSpeaking();
    // silence the host's competing audio too (news podcast audio_url
    // playback) — an open mic would transcribe it instead of the user
    if (S.beforeSpeak) { try { S.beforeSpeak(); } catch (e) { /* never block the mic */ } }
    S.listening = true;
    S.recErrorStreak = 0;
    S.statusPinned = false;
    S.recognition.continuous = S.handsFree; // hands-free keeps the stream open
    S.face.setMood("listening");
    setStatus(S.handsFree ? "Hands-free — say “Hey Looper …”" : "Listening… say “find me a café”");
    // hand-off: let the host pause its own always-on mic (Porcupine wake
    // word) and WAIT for it — WebVoiceProcessor unsubscribe is async, and
    // starting recognition mid-release can lose the race for the mic.
    var opened = null;
    if (S.onMicOpen) { try { opened = S.onMicOpen(); } catch (e) { opened = null; } }
    Promise.resolve(opened).catch(function () { /* host hook failed — proceed */ }).then(function () {
      return new Promise(function (resolve) { setTimeout(resolve, S.onMicOpen ? 120 : 0); });
    }).then(function () {
      if (!S.listening) {
        // cancelled while the hand-off settled — recognition never started,
        // so onend will never fire: release the host's wake-word mic here
        // or it stays paused until a reload
        if (S.onMicClose) { try { S.onMicClose(); } catch (e) { /* never block */ } }
        return;
      }
      tryStartRecognition();
    });
  }

  // Start the recognizer, failing CLOSED on anything but "already started"
  // (InvalidStateError): a swallowed start() failure — initial OR auto-
  // restart — leaves S.listening true with no recognizer running, so no
  // onend would ever release the host's wake-word mic or the dock UI.
  function tryStartRecognition() {
    try {
      S.recognition.start();
    } catch (e) {
      if (e && e.name === "InvalidStateError") return;
      S.listening = false;
      S.handsFree = false;
      if (S.ui.wake) S.ui.wake.classList.remove("on");
      if (S.onMicClose) { try { S.onMicClose(); } catch (e2) { /* never block */ } }
      S.face.setMood("idle");
      S.ui.inputRow.classList.add("lj-open");
      setStatus("Mic unavailable — type to ask Looper");
    }
  }

  function stopListening() {
    S.listening = false;
    S.handsFree = false;
    if (S.ui.wake) S.ui.wake.classList.remove("on");
    if (S.recognition) { try { S.recognition.stop(); } catch (e) { /* not started */ } }
    S.face.setMood("idle");
    setStatus("Tap my face to talk");
  }

  // ------------------------------------------------------------- the brain
  var API_TIMEOUT_MS = 10000;

  function api(path, params) {
    var qs = new URLSearchParams(params).toString();
    var url = S.apiBase + path + (qs ? "?" + qs : "");
    // Bounded: a brain that accepts the connection but stalls must not
    // leave the face stuck in "thinking" forever — abort into the same
    // offline path as a refused connection.
    var ctrl = typeof AbortController !== "undefined" ? new AbortController() : null;
    var timer = ctrl ? setTimeout(function () { ctrl.abort(); }, API_TIMEOUT_MS) : null;
    return fetch(url, ctrl ? { signal: ctrl.signal } : undefined)
      .then(function (r) {
        if (!r.ok) throw new Error("API " + r.status);
        return r.json();
      })
      .finally(function () { if (timer) clearTimeout(timer); });
  }

  function mapCenter() {
    if (S.map && S.map.getCenter) {
      var c = S.map.getCenter();
      return { lat: c.lat, lng: c.lng };
    }
    return { lat: S.home.lat, lng: S.home.lng };
  }

  function cardUrl(r) {
    // HybridCard connection: prefer the API's card_url; else derive nothing —
    // never guess a slug (public-safe rule: only verifiable links).
    return safeUrl(r.card_url);
  }

  function optionsHtml(results, headline) {
    var html = '<p class="lj-msg">' + escapeHtml(headline) + "</p>";
    results.forEach(function (r, i) {
      // Metadata is API data too — coerce to numbers so a malformed or
      // hostile response can't inject markup through rating fields.
      var rating = Number(r.avg_rating);
      var reviewCount = Number(r.review_count);
      var distKm = Number(r.distance_km);
      var stars = (r.avg_rating != null && isFinite(rating)) ? "⭐ " + rating : "no ratings yet";
      var meta = (r.category || "") + " · " + stars + " · " +
        (isFinite(reviewCount) ? reviewCount : 0) + " reviews" +
        (r.distance_km != null && isFinite(distKm) ? " · " + distKm + " km" : "");
      var siteHref = safeUrl(r.website);
      var link = cardUrl(r)
        ? '<a href="' + escapeHtml(cardUrl(r)) + '" target="_blank" rel="noopener">View card →</a>'
        : (siteHref ? '<a href="' + escapeHtml(siteHref) + '" target="_blank" rel="noopener">Website →</a>' : "");
      html +=
        '<div class="lj-option" data-i="' + i + '">' +
        '<div><div class="lj-name">' + (i + 1) + ". " + escapeHtml(r.name) + "</div>" +
        '<div class="lj-meta">' + escapeHtml(meta) + "</div></div>" +
        "<div>" + link + "</div></div>";
    });
    return html;
  }

  function wireOptionClicks(results) {
    Array.prototype.forEach.call(S.ui.panel.querySelectorAll(".lj-option"), function (el) {
      el.addEventListener("click", function () {
        var r = results[Number(el.getAttribute("data-i"))];
        if (r && r.lng != null && r.lat != null) Bus.flyTo(r.lng, r.lat, 17);
      });
    });
  }

  function speakResults(results, cmd, radiusKm) {
    var n = results.length;
    var lead = (cmd.superlative ? PERSONA.superlative : "") +
      "I found " + n + " option" + (n === 1 ? "" : "s") +
      (radiusKm ? " within " + radiusKm + " kilometres" : "") + ". ";
    var names = results.slice(0, 3).map(function (r) {
      var bit = r.name;
      if (r.avg_rating) bit += " has " + r.avg_rating + " stars from " + r.review_count + " reviews";
      else if (r.review_count) bit += " has " + r.review_count + " reviews";
      return bit;
    });
    var tail = "";
    if (cmd.intent === "connect") tail = PERSONA.connectOutro;
    else if (cmd.intent === "offers") tail = PERSONA.offersNote;
    else if (cmd.intent === "booking") tail = PERSONA.bookingNote;
    speak(lead + names.join(". ") + ". " + PERSONA.antiBias + tail);
  }

  function runSearch(cmd) {
    var center = cmd.coords || mapCenter();
    // Stale-closure fix (gotcha): the radius for THIS command comes from the
    // command object itself, falling back to the last explicitly-set radius.
    var radiusM = cmd.radiusM || S.lastRadiusM;
    if (cmd.radiusM) S.lastRadiusM = cmd.radiusM;
    S.lastSearch = cmd;

    // No pin category clears the host filter — "show cafes" then "find a
    // plumber" must not leave the map filtered to Food while the panel
    // shows plumbers. fromSearch tells the host to skip its own camera
    // moves: this search fits its results itself.
    Bus.setCategory(cmd.category || null, { fromSearch: true });
    S.face.setMood("thinking");
    setStatus(pick(PERSONA.acks));

    var seq = S.reqSeq; // a newer command supersedes this response
    var radiusKm = Math.max(0.1, Math.min(50, radiusM / 1000));
    return api("/search", {
      q: cmd.searchTerm || cmd.raw,
      lat: center.lat,
      lng: center.lng,
      radius_km: radiusKm,
      limit: 5,
      intent: cmd.intent, // telemetry only (F2.5) — never a ranking input
      session: S.session,
    }).then(function (data) {
      if (seq !== S.reqSeq) return; // stale response — a newer query owns the UI
      var results = (data && data.results) || [];
      settleUi();
      if (!results.length) {
        // clear the PREVIOUS search's pins — stale markers next to a
        // "nothing found" panel read as results for the new query
        Bus.clearResults();
        if (cmd.coords) Bus.flyTo(cmd.coords.lng, cmd.coords.lat, cmd.coords.zoom);
        showPanel('<p class="lj-msg">' + escapeHtml(data.message || pick(PERSONA.noResults)) + "</p>");
        speak(pick(PERSONA.noResults));
        return;
      }
      Bus.showResults(results);
      // showResults already fitted bounds over the pins — only fall back to
      // the suburb's own camera when there was nothing to fit
      // same validity rules the bus's markers use — rows with blank or
      // out-of-range coords drew no pin, so they must not suppress the
      // suburb fly ("cafes in Bronte" with unmappable rows still flies)
      var hasPins = results.some(function (r) { return Bus.hasValidCoords(r); });
      if (cmd.coords && !hasPins) Bus.flyTo(cmd.coords.lng, cmd.coords.lat, cmd.coords.zoom);
      showPanel(optionsHtml(results, data.message || "Here's what the loop knows:"));
      wireOptionClicks(results);
      speakResults(results, cmd, radiusKm);
    }).catch(function () {
      if (seq !== S.reqSeq) return; // superseded — don't clobber the newer UI
      Bus.clearResults(); // stale pins next to "brain offline" read as results
      S.face.setMood("error");
      setStatus("Looper brain offline");
      S.statusPinned = true; // keep the offline message up until the next turn
      showPanel('<p class="lj-msg">' + escapeHtml(pick(PERSONA.apiDown)) + "</p>");
      speak(pick(PERSONA.apiDown));
    });
  }

  function runBusiness(cmd) {
    // a leftover category filter from a previous search would contradict
    // the named business about to be shown — clear chips/layers (the host
    // skips its camera: the lookup flies to the business itself)
    Bus.setCategory(null, { fromSearch: true });
    S.face.setMood("thinking");
    var seq = S.reqSeq; // a newer command supersedes this response
    // Named business lookup: pass map center as a soft proximity tiebreaker
    // with a continent-wide radius so nothing is ever filtered out
    // (e.g. Sydney map → The Farm Byron Bay still surfaces).
    // Ranking: relevance → reviews → recency → proximity.
    var center = mapCenter();
    var params = { q: cmd.businessName, limit: 3, intent: "business", session: S.session };
    if (center) { params.lat = center.lat; params.lng = center.lng; params.radius_km = 5000; }
    return api("/search", params).then(function (data) {
      if (seq !== S.reqSeq) return; // stale response — a newer query owns the UI
      var results = (data && data.results) || [];
      settleUi();
      if (!results.length) {
        Bus.clearResults(); // stale pins next to "no match" read as matches
        speak("I couldn't find " + cmd.businessName + " on the loop yet.");
        showPanel('<p class="lj-msg">No match for “' + escapeHtml(cmd.businessName) + '” yet.</p>');
        return;
      }
      var top = results[0];
      // every listed match gets a marker — the panel and the map must agree
      Bus.showResults(results);
      // both coords or no flight — a null lat coerces to the equator
      if (top.lng != null && top.lat != null) Bus.flyTo(top.lng, top.lat, 17); // old build: zoom 17
      showPanel(optionsHtml(results, "Matching options:"));
      wireOptionClicks(results);
      var line = top.name;
      if (top.avg_rating) line += " — " + top.avg_rating + " stars from " + top.review_count + " community reviews.";
      else line += " — no reviews yet. Maybe you'll leave the first one?";
      if (top.top_review) line += " One local said: " + top.top_review;
      speak(line);
    }).catch(function () {
      if (seq !== S.reqSeq) return; // superseded — don't clobber the newer UI
      Bus.clearResults(); // stale marker next to "brain offline" reads as current
      // same offline treatment as runSearch — the dock must not look healthy
      S.face.setMood("error");
      setStatus("Looper brain offline");
      S.statusPinned = true; // keep the offline message up until the next turn
      showPanel('<p class="lj-msg">' + escapeHtml(pick(PERSONA.apiDown)) + "</p>");
      speak(pick(PERSONA.apiDown));
    });
  }

  // ------------------------------------------------------------ the router
  function execute(cmd) {
    switch (cmd.intent) {
      case "stop":
        // "stop" means stop everything: cancel speech AND close the mic
        // ("hey looper stop listening" must actually stop listening) —
        // including the auto re-arm intent, or visibilitychange would
        // resurrect a mic the user explicitly killed.
        S.wantHandsFree = false;
        stopSpeaking();
        stopListening();
        // a superseded in-flight search can no longer restore the mood —
        // stop settles the whole dock back to idle
        S.face.setMood("idle");
        setStatus("Tap my face to talk");
        return;
      case "greet":
        speak(pick(PERSONA.greetings).replace("{district}", S.district));
        return;
      case "help":
        showPanel('<p class="lj-msg">' + escapeHtml(PERSONA.help) + "</p>");
        speak(PERSONA.help);
        return;
      case "suburb":
        // plain navigation: stale result markers/cards would read as
        // belonging to the destination — clear them like reset does
        Bus.clearResults();
        S.ui.panel.classList.remove("lj-open");
        S.ui.panel.innerHTML = "";
        S.lastSearch = null;
        if (cmd.coords) Bus.flyTo(cmd.coords.lng, cmd.coords.lat, cmd.coords.zoom);
        speak("Taking you to " + cmd.suburb + ".");
        return;
      case "zoom":
        Bus.zoom(cmd.zoomDelta);
        // a superseded in-flight search can no longer restore the mood —
        // quick map commands settle the face themselves
        S.face.setMood("idle");
        return;
      case "reset":
        Bus.reset();
        // stale cards would still fly to results that are no longer on the map
        S.ui.panel.classList.remove("lj-open");
        S.ui.panel.innerHTML = "";
        S.lastSearch = null;
        S.face.setMood("idle");
        speak("Back to the whole " + S.district + " loop.");
        return;
      case "set_radius":
        S.lastRadiusM = cmd.radiusM;
        if (S.lastSearch) {
          var rerun = Object.assign({}, S.lastSearch, { radiusM: cmd.radiusM });
          runSearch(rerun);
        } else {
          speak("Got it — I'll search within " + (cmd.radiusM / 1000) + " kilometres.");
        }
        return;
      case "business":
        runBusiness(cmd);
        return;
      case "search":
      case "connect":
      case "offers":
      case "booking":
      case "news":
        runSearch(cmd);
        return;
      default:
        speak(pick(PERSONA.unknown));
        showPanel('<p class="lj-msg">' + escapeHtml(pick(PERSONA.unknown)) + "</p>");
    }
  }

  function ask(text) {
    stopSpeaking(); // barge-in
    S.reqSeq++; // newer command owns the UI — in-flight responses go stale
    S.statusPinned = false; // a new turn unpins "brain offline"
    setStatus("“" + text + "”");
    var cmd = Router.route(text, { radiusM: S.lastRadiusM });
    execute(cmd);
    return cmd;
  }

  // ------------------------------------------------------- deep links (F4.2)
  // ?cat=Food&q=coffee&fly=151.2743,-33.8908,16 — same contract Ricky's
  // localloop_open_map tool builds.
  function applyDeepLinks() {
    var params = new URLSearchParams(root.location.search);
    var fly = params.get("fly");
    var flyCoords = null;
    if (fly) {
      var parts = fly.split(",").map(Number);
      if (parts.length >= 2 && isFinite(parts[0]) && isFinite(parts[1]) &&
          Math.abs(parts[0]) <= 180 && Math.abs(parts[1]) <= 90) {
        flyCoords = { lng: parts[0], lat: parts[1], zoom: isFinite(parts[2]) ? parts[2] : undefined };
        Bus.flyTo(flyCoords.lng, flyCoords.lat, flyCoords.zoom);
      }
    }
    // "category" is the host's own query-param spelling (llx11 writes it
    // via syncCategoryQueryParam) — accept it as an alias of "cat" so
    // existing category links with a Jarvis q aren't reset by the search.
    var cat = params.get("cat") || params.get("category");
    if (cat) Bus.setCategory(cat);
    var q = params.get("q");
    if (!q) return;
    // The link's explicit cat/fly ARE the contract — reparsing q must not
    // override them. "?cat=Offers&q=pizza" is an Offers search for pizza
    // centred on the fly target, not a Food search at the old map centre,
    // and a q the grammar can't classify still searches as free text.
    stopSpeaking();
    S.reqSeq++;
    setStatus("“" + q + "”");
    var cmd = Router.route(q, { radiusM: S.lastRadiusM });
    var searchIntents = { search: 1, connect: 1, offers: 1, booking: 1, news: 1 };
    if (!searchIntents[cmd.intent]) {
      cmd = { intent: "search", raw: q, searchTerm: cmd.searchTerm || cmd.businessName || q };
    }
    if (cat) {
      cmd.category = cat;
      // the parser may have enriched the term with ANOTHER category's
      // vocabulary (q=pizza → Food words) — with an explicit cat the
      // link's own words are the query
      cmd.searchTerm = Router.clean(q) || q;
    }
    if (flyCoords) cmd.coords = flyCoords; // explicit fly= always owns the camera + search center
    runSearch(cmd);
  }

  // ------------------------------------------------------------------- init
  function init(opts) {
    if (S.inited) return API;
    opts = opts || {};
    var cfg = root.LooperJarvisConfig || {};
    var llCfg = root.LocalLoopConfig || {};

    S.apiBase = (opts.apiBase || cfg.apiBase || llCfg.looperApi || S.apiBase).replace(/\/$/, "");
    if (!/\/api$/.test(S.apiBase)) S.apiBase += "/api";
    S.district = opts.district || cfg.district || S.district;
    S.home = opts.home || cfg.home || S.home;
    S.map = opts.map || root.localloopMap || null;
    S.onMicOpen = opts.onMicOpen || cfg.onMicOpen || null;
    S.onMicClose = opts.onMicClose || cfg.onMicClose || null;
    S.beforeSpeak = opts.beforeSpeak || cfg.beforeSpeak || null;

    buildUi(opts.dock || cfg.dock || null);
    setupRecognition();

    // Screen-lock/tab-switch kills the recognizer through the fail-closed
    // paths, which turn hands-free OFF. Re-arm on return ONLY when the drop
    // happened while hidden — a real in-foreground mic failure keeps the
    // deliberate typed-input fallback. A genuinely revoked mic just re-enters
    // tryStartRecognition's fail-closed branch, so this cannot loop.
    if (typeof document !== "undefined" && document.addEventListener) {
      document.addEventListener("visibilitychange", function () {
        if (document.hidden) return;
        if (S.wantHandsFree && !S.listening && S.speechSupported && S.droppedWhileHidden) {
          S.droppedWhileHidden = false;
          S.handsFree = true;
          S.ui.wake.classList.add("on");
          startListening();
        }
      });
    }

    if (S.map) {
      Bus.init(S.map, {
        home: S.home,
        markerLib: opts.markerLib || root.maplibregl || root.mapboxgl,
        onCategory: opts.onCategory || cfg.onCategory || null,
        claimCta: opts.claimCta || cfg.claimCta || null,
        district: S.district,
        resolveBusiness: function (name) {
          return api("/search", { q: name, limit: 1 }).then(function (d) {
            return (d.results && d.results[0]) || null;
          });
        },
      });
      applyDeepLinks();
    }

    S.inited = true;
    return API;
  }

  var API = {
    init: init,
    ask: ask,
    speak: speak,
    stop: function () { stopSpeaking(); stopListening(); },
    startListening: startListening,
    stopListening: stopListening,
    get face() { return S.face; },
    bus: Bus,
    router: Router,
  };

  root.LooperJarvis = API;
})(typeof self !== "undefined" ? self : this);
