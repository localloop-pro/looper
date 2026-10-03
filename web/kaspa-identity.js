(function (root) {
  'use strict';

  function short(value, head, tail) {
    if (!value) return 'Not available';
    return value.length > head + tail + 1 ? value.slice(0, head) + '…' + value.slice(-tail) : value;
  }

  function stateCopy(state) {
    return {
      fresh: ['Verified on KNS', 'Chain record checked recently'],
      stale: ['Previously verified', 'KNS is temporarily unavailable; no privileged action is permitted'],
      mismatch: ['Verification mismatch', 'The current KNS record does not match LocalLoop’s configured identity'],
      unavailable: ['Verification unavailable', 'No current KNS verification is available'],
    }[state] || ['Verification unavailable', 'No current KNS verification is available'];
  }

  function render(host, record, label, domain) {
    var state = record && record.verificationState || 'unavailable';
    var copy = stateCopy(state);
    host.dataset.state = state;
    host.innerHTML = '';

    var details = document.createElement('details');
    details.className = 'kaspa-identity';
    var summary = document.createElement('summary');
    // Every collapsed state names the organization (.SEED/decisions.md: every UI
    // must scope the claim), so a stale/mismatch/unavailable badge can never be
    // read as belonging to an adjacent listing or user.
    var scope = (record && record.domain) || domain || 'localloop.kas';
    var collapsed = state === 'fresh' ? label : copy[0] + ' \u00b7 ' + scope;
    summary.innerHTML = '<span class="kaspa-identity__mark" aria-hidden="true">K</span><span>' +
      collapsed + '</span><span class="kaspa-identity__state">' + state + '</span>';
    details.appendChild(summary);

    var panel = document.createElement('div');
    panel.className = 'kaspa-identity__panel';
    var verifiedAt = record && record.verifiedAt ? new Date(record.verifiedAt).toLocaleString() : 'Not available';
    panel.innerHTML = '<strong>' + copy[0] + '</strong><p>' + copy[1] + '</p>' +
      '<dl><div><dt>Domain</dt><dd>' + ((record && record.domain) || domain || 'localloop.kas') + '</dd></div>' +
      '<div><dt>Owner</dt><dd>' + short(record && record.ownerAddress, 14, 8) + '</dd></div>' +
      '<div><dt>Asset</dt><dd>' + short(record && record.assetId, 12, 6) + '</dd></div>' +
      '<div><dt>Checked</dt><dd>' + verifiedAt + '</dd></div></dl>';
    if (record && record.explorerUrl && (state === 'fresh' || state === 'stale')) {
      var link = document.createElement('a');
      link.href = record.explorerUrl;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.textContent = 'Inspect transaction ↗';
      panel.appendChild(link);
    }
    var note = document.createElement('small');
    note.textContent = 'Organization identity only — this does not verify individual listings or users.';
    panel.appendChild(note);
    details.appendChild(panel);
    host.appendChild(details);
  }

  // Refresh cadence: a fresh record is re-checked when its expiresAt passes
  // (plus a little jitter); anything else is re-checked on a bounded interval,
  // so a long-lived tab never keeps "Verified on KNS" past the verification
  // window and surfaces a later mismatch.
  var MIN_REFRESH_MS = 30 * 1000;
  var FALLBACK_REFRESH_MS = 5 * 60 * 1000;
  var MAX_REFRESH_MS = 6 * 60 * 60 * 1000;

  function nextRefreshMs(record) {
    var due = FALLBACK_REFRESH_MS;
    if (record && record.verificationState === 'fresh' && record.expiresAt) {
      var until = new Date(record.expiresAt).getTime() - Date.now();
      if (!isNaN(until)) due = until + Math.floor(Math.random() * 15000);
    }
    return Math.min(MAX_REFRESH_MS, Math.max(MIN_REFRESH_MS, due));
  }

  // A refresh request is bounded so a stalled browser-to-API connection can
  // never keep the previous badge on screen indefinitely, and the retry is
  // re-armed after every settle (success, error or timeout).
  var REQUEST_TIMEOUT_MS = 8 * 1000;

  function clearMountState(host) {
    if (host.__kaspaIdentityTimer) clearTimeout(host.__kaspaIdentityTimer);
    if (host.__kaspaIdentityExpiry) clearTimeout(host.__kaspaIdentityExpiry);
    if (host.__kaspaIdentityAbort) { try { host.__kaspaIdentityAbort.abort(); } catch (_) { /* ignore */ } }
    host.__kaspaIdentityTimer = null;
    host.__kaspaIdentityExpiry = null;
    host.__kaspaIdentityAbort = null;
  }

  // Verified wording expires on its own clock: when expiresAt passes without a
  // newer record, the badge downgrades to "Previously verified" (state
  // `stale`) regardless of whether the refresh request has completed.
  function armExpiry(host, record, label, domain, gen) {
    if (!record || record.verificationState !== 'fresh' || !record.expiresAt) return;
    var until = new Date(record.expiresAt).getTime() - Date.now();
    if (isNaN(until)) return;
    host.__kaspaIdentityExpiry = setTimeout(function () {
      if (gen !== host.__kaspaIdentityGen) return;
      if (host.dataset.state !== 'fresh') return;
      var expired = {};
      for (var key in record) if (Object.prototype.hasOwnProperty.call(record, key)) expired[key] = record[key];
      expired.verificationState = 'stale';
      render(host, expired, label, domain);
    }, Math.max(0, until));
  }

  async function mount(hostOrSelector, options) {
    var host = typeof hostOrSelector === 'string' ? document.querySelector(hostOrSelector) : hostOrSelector;
    if (!host) return;
    options = options || {};
    var domain = options.domain || 'localloop.kas';
    var label = options.label || ('Official · ' + domain);
    var apiBase = (options.apiBase || (root.LocalLoopConfig && root.LocalLoopConfig.looperApi) || root.location.origin).replace(/\/$/, '');
    // Re-mounting the same host invalidates the previous mount entirely: its
    // timers are cleared, its in-flight request is aborted, and its generation
    // token stops a late completion from rendering or rescheduling.
    clearMountState(host);
    var gen = (host.__kaspaIdentityGen || 0) + 1;
    host.__kaspaIdentityGen = gen;

    async function refresh(initial) {
      if (gen !== host.__kaspaIdentityGen) return;
      // The requested domain is shown while loading and on failure, so a
      // qikflo.kas badge never discloses localloop.kas during an outage.
      if (initial) render(host, null, label, domain);
      var record = null;
      var controller = typeof AbortController === 'function' ? new AbortController() : null;
      var timeout = controller ? setTimeout(function () { controller.abort(); }, REQUEST_TIMEOUT_MS) : null;
      host.__kaspaIdentityAbort = controller;
      try {
        var response = await fetch(apiBase + '/api/identity/domains/' + encodeURIComponent(domain), {
          headers: { Accept: 'application/json' }, credentials: 'omit', cache: 'no-store',
          signal: controller ? controller.signal : undefined
        });
        if (!response.ok) throw new Error('identity unavailable');
        record = await response.json();
      } catch (_) {
        record = null;
      } finally {
        if (timeout) clearTimeout(timeout);
      }
      if (gen !== host.__kaspaIdentityGen) return; // superseded by a newer mount
      host.__kaspaIdentityAbort = null;
      if (host.__kaspaIdentityExpiry) clearTimeout(host.__kaspaIdentityExpiry);
      render(host, record, label, domain);
      if (!host.isConnected) return; // badge removed from the page: stop polling
      armExpiry(host, record, label, domain, gen);
      host.__kaspaIdentityTimer = setTimeout(function () { refresh(false); }, nextRefreshMs(record));
    }

    await refresh(true);
  }

  root.LocalLoopKaspaIdentity = { mount: mount };
})(typeof window !== 'undefined' ? window : this);
