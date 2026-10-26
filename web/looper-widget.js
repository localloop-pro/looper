/* LOOPER Web Search Widget — embed on any page to add the "Hey Looper" search bar */

(() => {
  // API base is configurable (F3.3): window.LocalLoopConfig.looperApi
  // (e.g. "https://api.localloop.ai") — falls back to local dev.
  const configured =
    (window.LocalLoopConfig && window.LocalLoopConfig.looperApi) ||
    (window.LooperJarvisConfig && window.LooperJarvisConfig.apiBase) ||
    'http://localhost:8000';
  const API_BASE = configured.replace(/\/$/, '').replace(/\/api$/, '') + '/api';

  // Create widget container
  const widget = document.createElement('div');
  widget.id = 'looper-widget';
  widget.innerHTML = `
    <div class="looper-container">
      <button class="looper-toggle" id="looper-toggle" aria-label="Ask Looper">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>
        </svg>
      </button>
      <div class="looper-panel" id="looper-panel" style="display:none">
        <div class="looper-header">
          <span>🏠 Hey Looper!</span>
          <button class="looper-close" id="looper-close">&times;</button>
        </div>
        <div class="looper-chat" id="looper-chat" role="log" aria-live="polite">
          <div class="looper-msg looper-bot">
            Hey! I'm Looper, your local connection guide. Ask me anything about businesses, services, or what's happening in the area. 🏠
          </div>
        </div>
        <div class="looper-input-row">
          <input type="text" class="looper-input" id="looper-input"
                 placeholder="e.g. good café near Bondi Beach..."
                 aria-label="Ask Looper">
          <button class="looper-send" id="looper-send" aria-label="Send">➤</button>
        </div>
      </div>
    </div>
  `;
  document.body.appendChild(widget);

  // Elements
  const toggle = document.getElementById('looper-toggle');
  const panel = document.getElementById('looper-panel');
  const close = document.getElementById('looper-close');
  const chat = document.getElementById('looper-chat');
  const input = document.getElementById('looper-input');
  const send = document.getElementById('looper-send');

  // Toggle panel
  toggle.onclick = () => { panel.style.display = 'block'; toggle.style.display = 'none'; };
  close.onclick = () => { panel.style.display = 'none'; toggle.style.display = 'flex'; };

  // Add message to chat
  function addMessage(text, isUser = false) {
    const div = document.createElement('div');
    div.className = `looper-msg ${isUser ? 'looper-user' : 'looper-bot'}`;
    div.textContent = text;
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
  }

  let searching = false;
  const SEARCH_TIMEOUT_MS = 15000;

  // Send query to LOOPER API
  async function askLooper(query) {
    if (searching) return;
    searching = true;
    addMessage(query, true);
    input.value = '';
    input.disabled = true;
    send.disabled = true;

    const controller = new AbortController();
    let timer;
    // Race the entire operation, including body parsing. Abort alone cannot
    // guarantee settlement for every host fetch implementation.
    const deadline = new Promise((_, reject) => {
      timer = setTimeout(() => {
        reject(new Error('Search timed out'));
        controller.abort();
      }, SEARCH_TIMEOUT_MS);
    });

    try {
      const data = await Promise.race([deadline, (async () => {
        let lat, lng;
        if (navigator.geolocation) {
          try {
            const pos = await new Promise((resolve, reject) =>
              navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 5000 })
            );
            lat = pos.coords.latitude;
            lng = pos.coords.longitude;
          } catch (e) { /* no location */ }
        }
        // A late location callback must not start a request after timeout.
        if (controller.signal.aborted) throw new Error('Search cancelled');
        const params = new URLSearchParams({ q: query, limit: '5' });
        if (lat) params.set('lat', lat);
        if (lng) params.set('lng', lng);
        const resp = await fetch(`${API_BASE}/search?${params}`, { signal: controller.signal });
        if (!resp.ok) throw new Error('Search unavailable');
        const payload = await resp.json();
        if (!payload || !Array.isArray(payload.results) ||
            (payload.message != null && typeof payload.message !== 'string') ||
            payload.results.some(r => !r || typeof r.name !== 'string' ||
              typeof r.category !== 'string' ||
              (r.avg_rating != null && (!Number.isFinite(r.avg_rating) || r.avg_rating < 0 || r.avg_rating > 5)))) {
          throw new Error('Invalid search response');
        }
        return payload;
      })()]);

      if (data.results && data.results.length > 0) {
        // Build response
        let resultText = (data.message || '') + '\n\n';
        data.results.forEach((r, i) => {
          const stars = r.avg_rating ? '⭐'.repeat(Math.round(r.avg_rating)) : 'No ratings yet';
          const dist = r.distance_km ? ` (${r.distance_km}km)` : '';
          resultText += `${i+1}. **${r.name}**${dist} — ${r.category}\n`;
          resultText += `   ${stars} · ${r.review_count} review${r.review_count !== 1 ? 's' : ''}\n`;
          if (r.top_review) resultText += `   ${r.top_review}\n`;
          resultText += '\n';
        });
        addMessage(resultText);
      } else {
        addMessage(data.message || "I couldn't find anything matching that yet. Want to be the first to add it? 🌱");
      }
    } catch (err) {
      addMessage("Sorry, I'm having trouble connecting right now. Please try again!");
    } finally {
      clearTimeout(timer);
      searching = false;
      input.disabled = false;
      send.disabled = false;
      if (panel.style.display !== 'none') input.focus();
    }
  }

  // Send on click
  send.onclick = () => {
    const q = input.value.trim();
    if (q) askLooper(q);
  };

  // Send on Enter
  input.onkeydown = (e) => {
    if (e.key === 'Enter') {
      const q = input.value.trim();
      if (q) askLooper(q);
    }
  };
})();