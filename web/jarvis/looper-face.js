/* LOOPER Jarvis — the animated Looper face, framework-free.
 *
 * Direct port of looper-bot/src/components/LooperFace.tsx + its CSS
 * (blue ring, gradient eyes with blink + pupil-look, CSS-variable mouth)
 * so the SAME face that lives on Bill's desktop can sit on the map.
 *
 * Usage:
 *   var face = LooperFace.mount(containerEl, { size: 132 });
 *   face.setMood("idle" | "listening" | "thinking" | "speaking" | "error");
 *   face.setMouth({ open, width, round, teeth });   // 0..1 each
 *   face.startTalking(); face.stopTalking();        // procedural lip-sync
 *                                                   // for speechSynthesis
 *   face.attachAnalyser(analyserNode);              // real audio lip-sync
 *   face.destroy();
 */
(function (root) {
  "use strict";

  var CSS = [
    ".looper-face{position:relative;display:grid;place-items:center;border-radius:999px;",
    "background:#08090d;border:5px solid rgba(86,189,255,.82);overflow:hidden;box-sizing:border-box;}",
    ".looper-face::after{content:'';position:absolute;inset:7%;border-radius:999px;border:1px solid rgba(255,255,255,.08);pointer-events:none;}",
    ".looper-face .lf-eye-row{position:relative;z-index:2;display:flex;gap:16%;transform:translateY(-14%);animation:lf-eye-look-row 6.5s infinite ease-in-out;}",
    ".looper-face .lf-eye{position:relative;width:20%;aspect-ratio:0.78;min-width:14px;border-radius:999px;",
    "background:linear-gradient(180deg,#f8fbff,#88e9ff);animation:lf-blink 4.6s infinite;overflow:hidden;}",
    ".looper-face .lf-eye span{position:absolute;inset:24% 30% 32%;border-radius:999px;background:#071019;opacity:.82;animation:lf-pupil-look 6.5s infinite ease-in-out;}",
    ".looper-face.lf-thinking .lf-eye{transform:scaleY(.72);}",
    ".looper-face.lf-error .lf-eye{background:linear-gradient(180deg,#fff5f7,#ff5b72);}",
    ".looper-face.lf-listening{border-color:rgba(125,223,255,1);box-shadow:0 0 18px rgba(86,189,255,.45);}",
    ".looper-face .lf-mouth-wrap{position:absolute;z-index:2;bottom:22%;display:grid;place-items:center;width:56%;height:26%;}",
    ".looper-face .lf-mouth{position:relative;width:calc(40% + (var(--lf-mouth-width) * 38%) - (var(--lf-mouth-round) * 14%));",
    "height:calc(6% + (var(--lf-mouth-open) * 55%));transform-origin:center;",
    "transition:width 55ms linear,height 55ms linear,transform 55ms linear;",
    "transform:translateY(calc(var(--lf-mouth-open) * -5%)) scaleX(calc(1 - (var(--lf-mouth-round) * .28)));}",
    ".looper-face .lf-mouth-line{position:absolute;inset:0;width:100%;height:100%;",
    "border-radius:calc(999px - (var(--lf-mouth-round) * 400px));background:#dff8ff;",
    "transform:scaleY(calc(.35 + (var(--lf-mouth-open) * .9)));}",
    ".looper-face .lf-mouth-teeth{position:absolute;z-index:1;left:50%;top:18%;width:calc(45% + (var(--lf-mouth-width) * 35%));",
    "height:2px;border-radius:999px;background:rgba(255,255,255,.82);opacity:var(--lf-mouth-teeth);transform:translateX(-50%);}",
    ".looper-face.lf-speaking .lf-mouth{width:calc(44% + (var(--lf-mouth-width) * 42%) - (var(--lf-mouth-round) * 16%));}",
    "@keyframes lf-blink{0%,92%,100%{transform:scaleY(1);}95%{transform:scaleY(.08);}}",
    "@keyframes lf-eye-look-row{0%,54%,100%{transform:translateY(-12%) translateX(0);}60%,74%{transform:translateY(-12%) translateX(4%);}80%,92%{transform:translateY(-12%) translateX(-3%);}}",
    "@keyframes lf-pupil-look{0%,54%,100%{transform:translateX(0);}60%,74%{transform:translateX(12%);}80%,92%{transform:translateX(-10%);}}",
  ].join("\n");

  var cssInjected = false;
  function injectCss() {
    if (cssInjected || typeof document === "undefined") return;
    var style = document.createElement("style");
    style.id = "looper-face-css";
    style.textContent = CSS;
    document.head.appendChild(style);
    cssInjected = true;
  }

  var MOODS = ["idle", "listening", "thinking", "speaking", "error"];

  function silentMouth() {
    return { open: 0.08, width: 0.22, round: 0.2, teeth: 0 };
  }

  function mount(container, opts) {
    opts = opts || {};
    injectCss();

    var el = document.createElement("div");
    el.className = "looper-face lf-idle";
    var size = opts.size || 132;
    el.style.width = size + "px";
    el.style.height = size + "px";
    el.setAttribute("role", "img");
    el.setAttribute("aria-label", "Looper");
    el.innerHTML =
      '<div class="lf-eye-row"><div class="lf-eye"><span></span></div><div class="lf-eye"><span></span></div></div>' +
      '<div class="lf-mouth-wrap"><div class="lf-mouth"><div class="lf-mouth-teeth"></div><div class="lf-mouth-line"></div></div></div>';
    container.appendChild(el);

    var mood = "idle";
    var rafId = null;
    var analyser = null;
    var analyserBuf = null;
    var talkTimer = null;
    var mouth = silentMouth();

    function applyMouth(shape) {
      el.style.setProperty("--lf-mouth-open", shape.open.toFixed(3));
      el.style.setProperty("--lf-mouth-width", shape.width.toFixed(3));
      el.style.setProperty("--lf-mouth-round", shape.round.toFixed(3));
      el.style.setProperty("--lf-mouth-teeth", shape.teeth.toFixed(3));
    }
    applyMouth(mouth);

    function setMood(next) {
      if (MOODS.indexOf(next) === -1) next = "idle";
      mood = next;
      el.className = "looper-face lf-" + next;
    }

    function smooth(target, amount) {
      mouth = {
        open: mouth.open + (target.open - mouth.open) * amount,
        width: mouth.width + (target.width - mouth.width) * amount,
        round: mouth.round + (target.round - mouth.round) * amount,
        teeth: mouth.teeth + (target.teeth - mouth.teeth) * amount,
      };
      applyMouth(mouth);
    }

    // Procedural lip-sync for speechSynthesis (no audio stream to analyse):
    // a jittered energy envelope shaped like the RMS-driven desktop version.
    function startTalking() {
      stopTalking();
      setMood("speaking");
      talkTimer = setInterval(function () {
        var energy = 0.25 + Math.random() * 0.65;
        smooth({
          open: Math.min(1, energy * 1.1),
          width: 0.35 + energy * 0.45,
          round: Math.random() * 0.35,
          teeth: energy > 0.55 ? 0.5 : 0.12,
        }, 0.5);
      }, 70);
    }

    function stopTalking() {
      if (talkTimer) { clearInterval(talkTimer); talkTimer = null; }
      smooth(silentMouth(), 1);
      if (mood === "speaking") setMood("idle");
    }

    // Real lip-sync when the host has an audio element / WebRTC stream
    // (same math as looper-bot realtime.ts: RMS → energy → mouth shape).
    function attachAnalyser(node) {
      analyser = node;
      analyserBuf = new Uint8Array(node.fftSize);
      function frame() {
        if (!analyser) return;
        analyser.getByteTimeDomainData(analyserBuf);
        var total = 0;
        for (var i = 0; i < analyserBuf.length; i++) {
          var v = (analyserBuf[i] - 128) / 128;
          total += v * v;
        }
        var rms = Math.sqrt(total / analyserBuf.length);
        var energy = Math.min(1, rms * 10.5);
        smooth({
          open: energy,
          width: 0.3 + energy * 0.5,
          round: 0.2,
          teeth: energy > 0.5 ? 0.5 : 0.1,
        }, 0.36);
        rafId = requestAnimationFrame(frame);
      }
      rafId = requestAnimationFrame(frame);
    }

    function destroy() {
      stopTalking();
      analyser = null;
      if (rafId) cancelAnimationFrame(rafId);
      el.remove();
    }

    return {
      el: el,
      setMood: setMood,
      setMouth: function (shape) { smooth(shape, 1); },
      startTalking: startTalking,
      stopTalking: stopTalking,
      attachAnalyser: attachAnalyser,
      destroy: destroy,
    };
  }

  root.LooperFace = { mount: mount };
  if (typeof module === "object" && module.exports) module.exports = root.LooperFace;
})(typeof self !== "undefined" ? self : this);
