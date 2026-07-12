/* LOOPER Jarvis — LooperMapBus (F3.4): ONE documented control surface for
 * the map. Voice router consumers, askSwarm's <map> tag handler, gateway
 * client actions, and deep links all drive the map through this bus instead
 * of poking the map object directly.
 *
 * Framework-free IIFE. Works with any Mapbox-GL-compatible map instance
 * (mapbox-gl v3 or maplibre-gl v4+ — flyTo/fitBounds/easeTo/Marker APIs).
 *
 * Usage:
 *   LooperMapBus.init(map, {
 *     home: { lng, lat, zoom },              // reset() target
 *     markerLib: window.maplibregl || window.mapboxgl,
 *     onCategory: (cat|null) => {...},       // host syncs its filter chips
 *     resolveBusiness: async (name) => ({name, lng, lat, ...}) | null,
 *   })
 *
 * Every method is safe to call from the DevTools console (F3.4 acceptance).
 */
(function (root) {
  "use strict";

  var state = {
    map: null,
    lib: null,
    home: { lng: 151.2743, lat: -33.8915, zoom: 14.5 }, // Bondi
    onCategory: null,
    resolveBusiness: null,
    activeCategory: null,
    resultMarkers: [],
    resultPopup: null,
  };

  function ready() {
    if (!state.map) {
      console.warn("[LooperMapBus] not initialised — call LooperMapBus.init(map) first");
      return false;
    }
    return true;
  }

  function init(map, opts) {
    opts = opts || {};
    state.map = map;
    state.lib = opts.markerLib || root.maplibregl || root.mapboxgl || null;
    if (opts.home) state.home = opts.home;
    if (opts.onCategory) state.onCategory = opts.onCategory;
    if (opts.resolveBusiness) state.resolveBusiness = opts.resolveBusiness;
    return bus;
  }

  function setCategory(category) {
    if (!ready()) return;
    state.activeCategory = category || null;
    if (state.onCategory) {
      try { state.onCategory(state.activeCategory); } catch (e) { console.warn("[LooperMapBus] onCategory hook failed", e); }
    }
  }

  function flyTo(lng, lat, zoom) {
    if (!ready()) return;
    state.map.flyTo({
      center: [Number(lng), Number(lat)],
      zoom: typeof zoom === "number" ? zoom : Math.max(state.map.getZoom(), 14),
      essential: true,
    });
  }

  // fitBounds over an array of {lng,lat} — old build behaviour:
  // padding 50, maxZoom 15.
  function fitPoints(points) {
    if (!ready() || !points || !points.length) return;
    var minLng = Infinity, minLat = Infinity, maxLng = -Infinity, maxLat = -Infinity;
    points.forEach(function (p) {
      var lng = Number(p.lng), lat = Number(p.lat);
      if (!isFinite(lng) || !isFinite(lat)) return;
      if (lng < minLng) minLng = lng;
      if (lat < minLat) minLat = lat;
      if (lng > maxLng) maxLng = lng;
      if (lat > maxLat) maxLat = lat;
    });
    if (!isFinite(minLng)) return;
    if (points.length === 1) return flyTo(minLng, minLat, 16);
    state.map.fitBounds([[minLng, minLat], [maxLng, maxLat]], { padding: 50, maxZoom: 15 });
  }

  // Category + radius view: sets the filter, then lets the host decide what
  // to show; if the host gave us result points via showResults, fit those.
  function fitCategory(category, radiusM) {
    if (!ready()) return;
    setCategory(category);
    if (state.resultMarkers.length) {
      fitPoints(state.resultMarkers.map(function (m) {
        var ll = m.getLngLat();
        return { lng: ll.lng, lat: ll.lat };
      }));
    } else if (radiusM) {
      // no results yet — approximate the radius as a zoom level around center
      var z = radiusM <= 500 ? 16 : radiusM <= 1000 ? 15 : radiusM <= 2500 ? 14 : radiusM <= 5000 ? 13 : 12;
      state.map.easeTo({ zoom: z });
    }
  }

  function zoom(delta) {
    if (!ready()) return;
    state.map.easeTo({ zoom: state.map.getZoom() + (Number(delta) || 1) });
  }

  function reset() {
    if (!ready()) return;
    clearResults();
    setCategory(null);
    state.map.flyTo({ center: [state.home.lng, state.home.lat], zoom: state.home.zoom, essential: true });
  }

  // Drop/refresh result markers for a set of businesses
  // [{name, lng, lat, category?, review_count?, avg_rating?, card_url?, website?}]
  function showResults(results) {
    if (!ready()) return;
    clearResults();
    var lib = state.lib;
    (results || []).forEach(function (r) {
      if (r.lng == null || r.lat == null) return;
      var el = document.createElement("div");
      el.className = "looper-result-marker";
      el.title = r.name || "";
      var marker;
      if (lib && lib.Marker) {
        marker = new lib.Marker({ element: el }).setLngLat([r.lng, r.lat]);
        if (lib.Popup) {
          marker.setPopup(new lib.Popup({ offset: 18 }).setHTML(popupHtml(r)));
        }
        marker.addTo(state.map);
        state.resultMarkers.push(marker);
      }
    });
    fitPoints(results || []);
  }

  function clearResults() {
    state.resultMarkers.forEach(function (m) {
      try { m.remove(); } catch (e) { /* already gone */ }
    });
    state.resultMarkers = [];
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function popupHtml(r) {
    var stars = r.avg_rating ? "⭐ " + r.avg_rating + " · " : "";
    var reviews = (r.review_count || 0) + " review" + (r.review_count === 1 ? "" : "s");
    var html = '<div class="looper-popup">' +
      "<strong>" + escapeHtml(r.name) + "</strong><br>" +
      '<span class="looper-popup-cat">' + escapeHtml(r.category || "") + "</span><br>" +
      '<span class="looper-popup-meta">' + stars + reviews + "</span>";
    // HybridCard connection: card link when the business has one, claim
    // funnel when it doesn't (F5.3 pattern; UTM for rev-share attribution).
    if (r.card_url) {
      html += '<br><a href="' + escapeHtml(r.card_url) + '" target="_blank" rel="noopener">View card →</a>';
    } else if (r.website) {
      html += '<br><a href="' + escapeHtml(r.website) + '" target="_blank" rel="noopener">Website →</a>';
    } else {
      html += '<br><a class="looper-popup-claim" href="https://hybridcard.ai?src=localloop&district=bondi" target="_blank" rel="noopener">Own this business? Get your Hybrid Card →</a>';
    }
    html += "</div>";
    return html;
  }

  // Fly to a business by name (uses the host's resolver, e.g. LOOPER API).
  function showBusiness(idOrName) {
    if (!ready()) return Promise.resolve(null);
    if (!state.resolveBusiness) {
      console.warn("[LooperMapBus] no resolveBusiness resolver configured");
      return Promise.resolve(null);
    }
    return Promise.resolve(state.resolveBusiness(idOrName)).then(function (biz) {
      if (biz && biz.lng != null && biz.lat != null) {
        showResults([biz]);
        flyTo(biz.lng, biz.lat, 17); // old build: specific business → zoom 17
      }
      return biz || null;
    });
  }

  function openNews(id) {
    // llx11 hosts wire this to their news marker system; demo no-ops with a log.
    console.info("[LooperMapBus] openNews", id);
  }

  var bus = {
    init: init,
    setCategory: setCategory,
    flyTo: flyTo,
    fitCategory: fitCategory,
    fitPoints: fitPoints,
    zoom: zoom,
    reset: reset,
    showBusiness: showBusiness,
    showResults: showResults,
    clearResults: clearResults,
    openNews: openNews,
    getActiveCategory: function () { return state.activeCategory; },
  };

  root.LooperMapBus = bus;
  if (typeof module === "object" && module.exports) module.exports = bus;
})(typeof self !== "undefined" ? self : this);
