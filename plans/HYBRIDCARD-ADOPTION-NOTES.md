# HybridCard adoption notes (Looper ↔ HybridCard)

**Supa-admin in this document means the HybridCard owner dashboard** (the whole `/dashboard` journey, site-admin is one tab). It does not mean the HybridCard `/Supa-admin` override-key door, and it does not mean LocalLoop's `/Supa-admin/` ops hub (SPEC-058).

Date: 2026-09-12 · Owner: Bill (QikFlo Pty Ltd) · Deliverable **D8** from the 3-repo uplift plan. Finding IDs (B7 to B30) continue `$HC/.seed/workflow-intent-audit/REVIEW.md`.

Path roots used below:

| Root | Repo | Path |
|---|---|---|
| `$HC` | HybridCard (Next 16) | `/Users/user/Qikflo GIT/02_Web_Builds/hybridcard.ai/new-card` |
| `$LP` | Looper (FastAPI + Electron) | `/Users/user/Qikflo GIT/02_Web_Builds/looper` |
| `$LL` | LocalLoop map worktree | `/Users/user/Qikflo GIT/02_Web_Builds/localloop.pro/localloop.pro-main/llx11/localloop.pro-main/.claude/worktrees/eloquent-booth-684876` |

House rule (from `$HC/.seed/decisions.md:1151`, 2026-09-10): a workflow is "done" only when there is outcome evidence. Every "Done when" line below names a persisted state, an HTTP status, or a test name. "Text generated" is never done.

This document changes no code. Every `file:line` was re-checked with `sed -n` / `grep -n` on 2026-09-13. Where the plan dossier's line was off, the correct line is cited and the difference is noted.

---

## PART A. What HybridCard should adopt from Looper

Five patterns. Each one: where it lives in Looper, a short excerpt, why it matters for the owner dashboard, and the HybridCard file where it would land.

### A1. Deterministic REST stays separate from the assistant

**Looper:** `$LP/backend/main.py:41-48` registers plain REST routers. The Electron assistant never touches the database; every tool goes through one HTTP helper, `$LP/looper-bot/electron/main.cjs:1056-1066`.

```js
// $LP/looper-bot/electron/main.cjs:1056-1066
async function localloopApi(path, params) {
  const qs = new URLSearchParams();
  for (const [key, value] of Object.entries(params || {})) {
    if (value !== undefined && value !== null && value !== "") qs.set(key, String(value));
  }
  const url = `${LOOPER_API_BASE}${path}${qs.size ? `?${qs}` : ""}`;
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`LOOPER API ${response.status}: ${await response.text()}`);
  }
  return response.json();
}
```

**Why it matters for the dashboard:** every assistant action produces an HTTP status you can log, test, and retry. The assistant cannot "half do" a thing. This is the direct cure for the B-series blind spot that Office workflows produce Act text without a persisted operation (`REVIEW.md` B1-B6, and `decisions.md:1151`).

**Lands in HybridCard:** keep the existing route handlers as the only executors, for example `$HC/src/app/api/admin/cards/lifecycle/route.ts:13-21` (`requireSiteAdmin()` then `adminCardLifecycle(...)` then `{ ok: true, updated, failed }`). The assistant (`$HC/src/components/card/OfficeChatDock.tsx`) should call these routes, never Mongoose directly. No new executor code is needed.

**Done when:** an integration test posts to `/api/admin/cards/lifecycle` through the assistant path and asserts HTTP 200 plus the card's persisted `status` field.

### A2. Declarative tool registry with one dispatcher and one result envelope

**Looper:** the registry `toolSpecs` is `$LP/looper-bot/electron/main.cjs:86-495` (30 entries, first `name:` at `:89`, last at `:487`). The dispatcher is `ipcMain.handle("tools:execute", ...)` at `:787`. Every branch returns `{ ok, ...data, artifact }`; unknown tools return `{ ok:false, error }` at `:1050`; thrown errors become `{ ok:false, error }` at `:1051-1053`.

```js
// $LP/looper-bot/electron/main.cjs:86-100
const toolSpecs = [
  {
    type: "function",
    name: "set_mode",
    description: "Switch Looper between display mode and computer use mode.",
    parameters: {
      type: "object",
      properties: {
        mode: { type: "string", enum: ["display", "computer"] },
      },
      required: ["mode"],
      additionalProperties: false,
    },
  },
```

```js
// $LP/looper-bot/electron/main.cjs:787-792 and :1050-1053
ipcMain.handle("tools:execute", async (_event, toolCall) => {
  const name = String(toolCall?.name || "");
  const args = asObject(toolCall?.arguments);

  try {
    if (name === "set_mode") {
    // ... one branch per tool ...
    return { ok: false, error: `Unknown tool: ${name}` };
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : String(error) };
  }
});
```

**Why it matters for the dashboard:** the dashboard's Admin tab has five separate routes with five separate hand-written shapes. A registry gives one place to list what admins can do, one schema per action (`additionalProperties: false` rejects typos), and one envelope the UI can render the same way every time (sonner toast on `ok:false`, table artifact on `ok:true`).

**Lands in HybridCard:** new `$HC/src/lib/admin/tools.ts` with entries `{ name, params (zod), readOnly, handler }` returning `{ ok, ...data, artifact }`. Reuse the zod body schema style already at `$HC/src/app/api/admin/cards/lifecycle/route.ts:6-9` and the `{ ok: true, ... }` shape already used at `lifecycle/route.ts:21`, `homepage-card/route.ts:80`, `homepage-demo/route.ts:87`. This is D4 phase P6.

**Done when:** `tests/unit/adminTools.test.ts` asserts every registry entry has a handler, every handler returns `ok` as a boolean, and a call with an unknown name returns `{ ok:false }`.

### A3. Read-only gateway allow-list (fixed filters, bounded pages, field allow-list, fail-closed env)

**Looper:** `$LP/looper-bot/electron/localloop-gateway-tools.cjs:7-33` fixes source and status and lists the only fields that may pass through; `:47-59` refuses non-HTTPS origins (loopback excepted); `:70-80` bounds `page` (1..10000) and `limit` (1..50); `:82-87` strips every field not in the allow-list; `:190-204` returns `{ ok:false, missingEnv }` when the URL or token is missing; `:215-221` sends `redirect: "error"` plus `AbortSignal.timeout(timeoutMs)`.

```js
// $LP/looper-bot/electron/localloop-gateway-tools.cjs:7-11 and :70-80
const PENDING_PINS_PATH = "/api/bot/map/pins";
const FIXED_SOURCE = "hybridcard";
const FIXED_STATUS = "pending_review";
const MIN_TOKEN_BYTES = 32;
const PIN_FIELDS = [
// ...
function buildPendingPinsUrl(baseUrl, args = {}) {
  const normalized = validatedBaseUrl(baseUrl);
  const page = boundedInteger(args.page, 1, 1, 10000, "page");
  const limit = boundedInteger(args.limit, 20, 1, 50, "limit");
  const url = new URL(PENDING_PINS_PATH, `${normalized}/`);
  url.searchParams.set("source", FIXED_SOURCE);
  url.searchParams.set("status", FIXED_STATUS);
```

**Why it matters for the dashboard:** B15 found unbounded admin reads: `$HC/src/lib/admin/tenants.ts:24-35` `listAdminTenants()` runs `BusinessProfile.find()` with no limit and no `.select()`. As tenants grow the Admin page gets slower and returns more fields than the table shows. The Looper pattern caps the page and names the columns.

**Lands in HybridCard:** `$HC/src/lib/admin/tenants.ts:24-35` (add `page`/`limit` with the same 1..50 bounds and a `.select()` list). HybridCard already has a good local example of a field allow-list at `$HC/src/lib/bridge/localLoopBridgeStatus.ts:21-28` (`.select('status type sentAt').lean()`); copy that shape.

**Done when:** `tests/unit/adminTenants.test.ts` asserts a call with `limit: 999` is clamped to 50 and the returned rows contain only the allow-listed keys.

### A4. HMAC over the raw body, eventId ledger, commit before 200

**Looper:** `$LP/backend/routes/ingest.py:77-93` `_verified_raw_body` reads at most 64 KB (`:74`), returns 413 on oversize and 401 on any signature failure, all before JSON parsing. `:110-129` `_record_event_and_commit` writes the ledger row and commits; only a genuine `eventId` replay is reported as `duplicate`. `:147-148` skips stale retries by the sender's `updated_at`. Verification itself is `$LP/backend/services/bridge_hmac.py:29-59` (constant-time compare, ±5 min window).

```python
# $LP/backend/routes/ingest.py:110-126
def _record_event_and_commit(db: Session, event_id: str, event_type: str, raw: bytes,
                             *, stale: bool = False) -> dict:
    """Append the idempotency ledger row and commit. 200 ONLY after the
    commit is durable."""
    db.add(BridgeEvent(event_id=event_id, event_type=event_type,
                       status="stale_skipped" if stale else "processed",
                       payload=raw.decode("utf-8", "replace")))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if db.query(BridgeEvent).filter(BridgeEvent.event_id == event_id).first():
            return {"ok": True, "duplicate": True}
        raise HTTPException(status_code=500, detail="transient conflict, retry")
    result = {"ok": True, "duplicate": False}
```

**Why it matters for the dashboard:** the owner dashboard has bulk actions (lifecycle: active / suspend / delete, up to 50 ids at `lifecycle/route.ts:7`). A double-tap or a retried request must not apply twice. The Looper ledger makes "did this already run?" a database question, not a guess.

**Lands in HybridCard:** do not rebuild signing. The sender side already exists: `$HC/src/lib/bridge/hmac.ts:15-23` `signBody`, `:27` `verifySignature` (present, kept for the day LocalLoop or Looper calls back), and the outbox already dedupes on `{ eventId, target }` with `$setOnInsert` at `$HC/src/lib/bridge/outbox.ts:38-40` and dead-letters after `MAX_ATTEMPTS = 6` (`:19`). What to add is an `actionId` ledger for admin bulk actions in `$HC/src/lib/cards/adminLifecycle.ts` (imported at `lifecycle/route.ts:4`), keyed the same way `BridgeEvent.event_id` is unique in `$LP/backend/models.py:127`.

**Done when:** `tests/integration/adminLifecycle.test.ts` posts the same `actionId` twice and asserts the second response is HTTP 200 with `duplicate: true` and the card's `status` changed exactly once.

### A5. An `engine` degradation field on every read that can fall back

**Looper:** `$LP/backend/routes/discover.py:264-270` tries the graph when `TYPEDB_ENABLED=true` and silently falls back to SQLite on any error; the response always carries `"engine"` (`:357`, or `"graph"` at `:240`). The desktop tool surfaces it: `$LP/looper-bot/electron/main.cjs:1117` `engine: data.engine` and `:1123` prints `Engine: ...` in the artifact.

```python
# $LP/backend/routes/discover.py:264-270
    engine = "fallback"
    if os.getenv("TYPEDB_ENABLED", "false").lower() == "true":
        try:
            return _graph_discover(db, suburb, lat, lng, radius_km, category, limit,
                                   intent=intent, session_id=session)
        except Exception:
            engine = "fallback"  # graph down → transparent fallback (additive rule)
```

**Why it matters for the dashboard:** B29 found that the card's "Ready" chip says ready when the outbox row was sent, while the map shows nothing until LocalLoop moderation approves the pin (`$LL/workers/looper-gateway/src/bridge-pin.mjs:142` forces `pending_review`). A status that cannot say "sent, but not visible" violates the outcome-evidence rule. The `engine` idea generalises: every status the dashboard shows should carry how it was computed (`live`, `cached`, `outbox-only`, `fallback`).

**Lands in HybridCard:** `$HC/src/lib/bridge/localLoopBridgeChip.ts` (`deriveLocalLoopBridgeChip`, re-exported at `localLoopBridgeStatus.ts:5-9`). Today the chip derives only from `getLatestLocalLoopPinOutbox` (`localLoopBridgeStatus.ts:15-37`), which is outbox truth, not map truth. Add a `source: 'outbox' | 'gateway'` field and, when the LocalLoop gateway read (`GET /api/bot/map/pins`, the same one Looper reads at `localloop-gateway-tools.cjs:7`) is configured, prefer it.

**Done when:** `tests/unit/localLoopBridgeStatus.test.ts` (exists) gains a case where the outbox row is `sent` but the gateway reports `pending_review`, and the chip label is "Sent, awaiting map approval", never "Ready".

---

## PART B. What Looper should fix

| # | Finding | Fix | Effort | Risk | Done when |
|---|---|---|---|---|---|
| B-1 | B25: CORS list hardcoded at `backend/main.py:23-39`, `allow_credentials=True` | `LOOPER_CORS_ORIGINS` env, forwarded in `docker-compose.yml` | S | Empty env in Coolify must not blank the list | `tests/test_cors.py` passes; `curl -H "Origin: https://localloop.ai"` returns the `access-control-allow-origin` header |
| B-2 | B26: N+1 review queries and Python-side radius in `search.py:109-129`, `discover.py:294-309` | One `GROUP BY business_id` aggregate, `lat/lng BETWEEN` prefilter | M | Ranking ties must not move | `test_search_antibias.py` still green; new `test_search_query_count.py` asserts the statement count for one search does not grow with the number of matching businesses |
| B-3 | B27: contract sample hardcoded in `tests/conftest.py:43-66`, `extra="ignore"` at `schemas.py:98,125` hides drift | Export JSON fixture from HybridCard, load it in `conftest.py`, `extra="forbid"` in tests only | S | Two repos must copy the same file | `test_contract_fixture.py::test_fixture_has_no_unknown_fields` passes in Looper; `bridge.test.ts` in HybridCard writes the same JSON |
| B-4 | B26b: kaspa badge `fetch` has no timeout, `fresh` never expires client-side (`web/kaspa-identity.js:91-102`) | `AbortSignal.timeout(8000)`, local expiry timer at `expiresAt` | S | Flicker if `expiresAt` is already past on arrival | Playwright stalled-refresh regression: `data-state` leaves `fresh` at `expiresAt` and the request count keeps rising |
| B-5 | B25: `POST /api/onboard`, `/api/reviews`, `/api/pins` are unauthenticated, untested, unlimited | Tests plus a per-IP rate limit dependency | M | TestClient IP is constant; limit must be env-tunable | `tests/test_public_writes.py` passes, including one HTTP 429 case |
| B-6 | B26: `docker-compose.yml:9-20` forwards no `TYPEDB_*`, so `/api/discover` is always `engine: fallback` in Docker | Forward `TYPEDB_ENABLED`, `TYPEDB_ADDRESS`, `TYPEDB_DB`, or document graph-off | S | Wrong address adds a failed connect to every request before fallback | `docker compose config` shows the three vars; `/api/discover?suburb=Bondi` returns `engine: graph` when enabled |
| B-7 | Tool count drift: docs say 23, code has 30 specs and 31 dispatch branches | One node test that counts and cross-checks; update the four doc lines | S | None | `npm test` in `looper-bot` includes `tool-registry.test.cjs` and it passes |

Verify commands used throughout (the venv exists at `backend/.venv/bin/python`):

```bash
cd "$LP/backend" && .venv/bin/python -m pytest -q
cd "$LP/looper-bot" && npm run typecheck && npm run build && npm test
```

Current baseline from `plans/evidence/kaspa-identity-review/README.md:34`: 107 passed, 1 skipped (the opt-in TypeDB test). `looper-bot` gateway tests: 15 (`electron/tests/localloop-gateway-tools.test.cjs`).

### B-1. Env-driven CORS

**Today** (`$LP/backend/main.py:23-39`): nine origins in code, `allow_credentials=True`, `allow_methods=["*"]`, `allow_headers=["*"]`. Adding a host means a code change and a redeploy. `.SEED/gotchas.md:3-10` (the dossier cited `:1-9`; line 1 is the heading) records that a missing origin was one of the two "brain offline" causes on 2026-07-28. Note also that `$LP/.env.example:62` documents `CORS_ORIGIN=http://localhost:3000`, but no file under `backend/` reads it (checked with `grep -rn CORS_ORIGIN backend`). Pick one name and make the example match.

**Snippet** (replaces `main.py:23-39`):

```python
DEFAULT_CORS_ORIGINS = (
    "http://localhost:3000,http://localhost:5173,"
    "https://localloop.ai,https://www.localloop.ai,"
    "https://localloop.pro,https://www.localloop.pro,"
    "https://explorer.localloop.ai,"
    "https://hybridcard.ai,https://www.hybridcard.ai"
)
# Empty env (Coolify can inject declared-but-empty vars) falls back to the default list.
CORS_ORIGINS = [o.strip() for o in (os.getenv("LOOPER_CORS_ORIGINS") or DEFAULT_CORS_ORIGINS).split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Keep the list explicit. Browsers reject `allow_credentials=True` together with `*`, so never "simplify" to a wildcard. Nothing in `backend/routes` sets cookies today, so a follow-up may drop `allow_credentials` entirely; that is a separate decision.

**docker-compose line to add** (after `$LP/docker-compose.yml:12`):

```yaml
      LOOPER_CORS_ORIGINS: ${LOOPER_CORS_ORIGINS:-}
```

**Test** (`$LP/backend/tests/test_cors.py`, new, uses the `client` fixture from `conftest.py:36-40`):

```python
def test_allowed_origin_gets_cors_header(client):
    r = client.get("/health", headers={"Origin": "https://localloop.ai"})
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == "https://localloop.ai"

def test_unknown_origin_gets_no_cors_header(client):
    r = client.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in r.headers
```

Effort S · Risk: an env override that omits `https://localloop.ai` reintroduces the 2026-07-28 outage; the test above plus a curl with an `Origin:` header (curl without one always "works", per the gotcha) is the guard.

**Verify:** `cd "$LP/backend" && .venv/bin/python -m pytest -q tests/test_cors.py` then `curl -si -H "Origin: https://localloop.ai" http://localhost:8010/health | grep -i access-control`.

### B-2. Grouped review aggregates and a bounding-box prefilter

**Today:**

- `$LP/backend/routes/search.py:109` loads every matching business with `query.all()`, then per business runs a count (`:114-116`), an average (`:118-120`) and the top review (`:129`, which is `get_top_review` at `:24-35`). Three statements per row.
- The radius test runs in Python after the load (`search.py:124-127`), so a Bondi query still reads Byron rows.
- `$LP/backend/routes/discover.py:294` does the same with a fourth statement (`:301-309` count, avg, max created_at; `:338` top review).
- `_graph_discover` adds three full-table scans at `discover.py:125-158`.
- `$LP/backend/models.py:56-57` stores `lat`/`lng` as plain `Float` with no index (the only indexes are on `category`, `suburb`, `join_code`, `business_id`, `event_id`, `deal_id`). SQLite has no geo index; a `BETWEEN` on two floats is still a full scan, but it moves the filter out of Python and into one statement.

**Grouped aggregate** (SQLAlchemy, reusable by both routes; put it in `search.py` next to `get_top_review`):

```python
from sqlalchemy import func

def review_stats(db, business_ids):
    """One statement: {business_id: (count, avg, latest_at)} for public reviews."""
    if not business_ids:
        return {}
    rows = (db.query(Review.business_id,
                     func.count(Review.id),
                     func.avg(Review.rating),
                     func.max(Review.created_at))
              .filter(Review.business_id.in_(business_ids), Review.is_public == True)
              .group_by(Review.business_id)
              .all())
    return {bid: (n, avg, latest) for bid, n, avg, latest in rows}
```

Then in `search.py:113-151` read `stats.get(biz.id, (0, None, None))` instead of the three queries. `get_top_review` can be grouped the same way with a window function, or left as-is for only the `limit` rows that survive ranking (`:162`), which cuts it from N calls to at most 20.

**Bounding-box prefilter** (before `query.all()` at `search.py:109` and `discover.py:294`):

```python
if lat is not None and lng is not None:
    dlat = radius_km / 111.0
    dlng = radius_km / (111.0 * max(0.1, math.cos(math.radians(lat))))
    query = query.filter(Business.lat.between(lat - dlat, lat + dlat),
                         Business.lng.between(lng - dlng, lng + dlng))
```

Keep the exact haversine check after the prefilter (`search.py:125-127`). The box is a superset of the circle, so results do not change; only the rows loaded change.

Effort M · Risk: the anti-bias ordering at `search.py:158` and `discover.py:320-324` must produce the same order for the same data; `tests/test_search_antibias.py` and `tests/test_search_voice.py` are the guards. `avg_rating` rounding (`:147`) must stay `round(x, 1)`.

**Verify:** `cd "$LP/backend" && .venv/bin/python -m pytest -q tests/test_search_antibias.py tests/test_search_voice.py tests/test_discover_telemetry.py`. Add `tests/test_search_query_count.py` that attaches a SQLAlchemy `before_cursor_execute` listener to `models.engine`, runs one `/api/search?q=café&limit=5` call with 5 matching businesses and again with 40, and asserts the two statement counts are equal. Today the count rises by 3 per extra match (the count, avg and top-review queries at `:114-129`); after the fix only the per-result calls remain (`get_top_review` at `:129` and `resolve_card_url` at `:177`, both bounded by `limit`), so the count depends on `limit`, not on how many rows match.

### B-3. Shared contract fixture with HybridCard

**Today:**

- HybridCard defines the Looper deal contract at `$HC/src/lib/bridge/payload.ts:183-203` (`LooperIngestPayload`) and the card contract at `:234-253` (`LooperCardIngestPayload`). The dossier cited `payload.ts:37-107`; those lines are the LocalLoop `MarkerPayload` (`:37`) and `CardPinPayload` (`:71`), not the Looper shape. Corrected here.
- HybridCard already builds a real payload in a test: `$HC/tests/integration/bridge.test.ts:68` `buildLooperPayload(deal, card, 'evt-1')` and `:78` `buildLooperCardPayload(card, 'evt-card-1')`.
- Looper re-types the same shape by hand in `$LP/backend/tests/conftest.py:43-66` `sample_deal_payload()`.
- `$LP/backend/schemas.py:98` and `:125` set `extra="ignore"`. That is correct in production (receivers adapt, sender is frozen), but it means a new sender field such as `capabilities` (`payload.ts:252`) is dropped silently and no test notices.

**Fix:**

1. In HybridCard, extend `bridge.test.ts:68-78` to write the two built payloads to `$HC/.seed/card-map-bridge/fixtures/looper-deal.v1.json` and `looper-card.v1.json` (the folder `$HC/.seed/card-map-bridge/` already holds `SPEC.md`, `RECEIVER-CHECKLIST.md`, `TECHNICAL-NOTES.md`). Freeze `eventId`, ids and `updated_at` so the file is stable.
2. Copy both files to `$LP/backend/tests/fixtures/` (same names). Change `conftest.py:43-66` to `json.load` the file and apply `overrides`. Keep the function name `sample_deal_payload` so `test_ingest_deal.py:3` and friends need no edit.
3. Tests only: subclass the schemas with `extra="forbid"` and validate the fixture.

```python
# $LP/backend/tests/test_contract_fixture.py (new)
import json, pathlib
from pydantic import ConfigDict
from schemas import HybridCardDealPayload, HybridCardCardPayload

FIX = pathlib.Path(__file__).parent / "fixtures"

class StrictDeal(HybridCardDealPayload):
    model_config = ConfigDict(extra="forbid")

class StrictCard(HybridCardCardPayload):
    model_config = ConfigDict(extra="forbid")

def test_fixture_has_no_unknown_fields():
    StrictDeal.model_validate(json.loads((FIX / "looper-deal.v1.json").read_text()))
    StrictCard.model_validate(json.loads((FIX / "looper-card.v1.json").read_text()))
```

When HybridCard adds a field, this test fails in Looper with the field name. That is the wanted outcome: the receiver is told to adapt. Production `schemas.py` keeps `extra="ignore"`.

Effort S (M if the card fixture reveals that `capabilities` should be stored) · Risk: the two copies drift if only one repo is updated; add a one-line `contract_version` to each JSON and assert it in both suites.

**Verify:** `cd "$HC" && npx vitest run tests/integration/bridge.test.ts --config vitest.integration.config.ts` then `cd "$LP/backend" && .venv/bin/python -m pytest -q tests/test_contract_fixture.py tests/test_ingest_deal.py tests/test_ingest_card.py`.

### B-4. Client timeout and local expiry for the kaspa badge (resolved 2026-09-27 in `dc680f1`, PR #15)

This was the one "changes requested" item on the current branch; it is now fixed as described below (implemented with an expiry timer plus mount-generation invalidation rather than a render-time guard) (`plans/COMPLETION_STATUS.md`, section "Kaspa identity branch review", and `plans/evidence/kaspa-identity-review/README.md:6-29`).

**Today** (`$LP/web/kaspa-identity.js`; the dossier cited `:91-96`, the exact lines are below):

- `:91` opens `try`, `:92-94` is the bare `fetch(...)` with no `signal`, `:97` is the `catch`.
- `:19` `render` derives `host.dataset.state` from `record.verificationState` only. Nothing on the client compares `record.expiresAt` with `Date.now()`.
- `:100` renders, then `:102` schedules the next poll only after the fetch settles. A stalled connection means no next poll, so a `fresh` badge stays `fresh` forever.
- `:67-74` `nextRefreshMs` already reads `expiresAt`, so the expiry time is available to the client.
- The server can legitimately hand back a `fresh` record whose `expiresAt` is already past (`$LP/backend/services/kaspa_identity.py:433-436` comment; the server deliberately starts the window when verification completes so this is rare, not impossible), so a client guard is needed regardless.

**Fix** (three small edits in `web/kaspa-identity.js`):

```js
// :92-94  bound the request the same way the gateway client does
// ($LP/looper-bot/electron/localloop-gateway-tools.cjs:218)
var response = await fetch(apiBase + '/api/identity/domains/' + encodeURIComponent(domain), {
  headers: { Accept: 'application/json' }, credentials: 'omit', cache: 'no-store',
  signal: AbortSignal.timeout(8000)
});
```

```js
// inside render(), after :19  never show fresh wording past expiresAt
if (state === 'fresh' && record && record.expiresAt &&
    Date.now() >= new Date(record.expiresAt).getTime()) {
  state = 'stale';
}
```

```js
// inside refresh(), after :102  arm an expiry timer independent of the network
if (host.__kaspaExpiryTimer) clearTimeout(host.__kaspaExpiryTimer);
if (record && record.verificationState === 'fresh' && record.expiresAt) {
  var untilExpiry = new Date(record.expiresAt).getTime() - Date.now();
  if (untilExpiry > 0) host.__kaspaExpiryTimer = setTimeout(function () { render(host, record, label, domain); }, untilExpiry);
}
```

Downgrading to `stale` (copy "Previously verified", `:12`) is the honest wording; `unavailable` would hide that a verification once existed. Because the timeout rejects the promise, the existing `catch` at `:97` runs and `:102` still schedules the retry, so retries after failure are preserved.

Effort S · Risk: a `fresh` record arriving with a past `expiresAt` now renders `stale` immediately; that is the correct behaviour per the server comment, but it changes what one Playwright state check expects.

**Verify:**

```bash
node --check "$LP/web/kaspa-identity.js"
cd "$LP/backend" && .venv/bin/python -m pytest -q tests/test_kaspa_identity.py      # 27 tests
```

Then the Playwright steps in `plans/evidence/kaspa-identity-review/README.md:17-24` (mount fresh with 60 s expiry, leave the second fetch pending, advance the clock two minutes, then two days). Done when `data-state` is no longer `fresh` after the 60 s mark and the intercepted request count keeps rising. Add that script under `$LP/web/tests/` next to `jarvis-smoke.playwright.js`.

### B-5. Tests and a rate limit for the three unauthenticated writes

**Today:**

| Route | File | Auth | Tests | Note |
|---|---|---|---|---|
| `POST /api/onboard` | `$LP/backend/routes/users.py:20-21` | none | none | duplicate mobile returns the existing join code (`:23-30`) |
| `POST /api/reviews` | `$LP/backend/routes/reviews.py:11-12` | none | none | checks business (`:14-17`), user (`:19-22`), duplicate (`:24-30`) |
| `POST /api/pins` | `$LP/backend/routes/map.py:11-12` | none | none | accepts any `user_id` without checking it exists (`:18-30`) |

`grep -rln "/api/onboard\|/api/reviews\|/api/pins" backend/tests` returns nothing. `backend/requirements.txt` has no rate-limit library.

**Fix:**

1. `$LP/backend/services/rate_limit.py` (new, no new dependency): an in-process token bucket keyed by `request.client.host` plus a bucket name, exposed as a FastAPI dependency `Depends(rate_limit("onboard", per_minute=5))`. Limits read from env (`LOOPER_RATE_ONBOARD_PER_MIN`, etc.) so tests can set them low and Coolify can tune them. Return HTTP 429 with `Retry-After`.
2. Add the dependency to the three route decorators.
3. `map.py:11-30`: look up the `User` like `reviews.py:19-22` does and return 404 when missing, so an anonymous caller cannot attach pins to arbitrary user ids.
4. `$LP/backend/tests/test_public_writes.py` (new) using `client` and `db` from `conftest.py`:

| Test name | Asserts |
|---|---|
| `test_onboard_creates_user_and_join_code` | HTTP 200, `join_code` is 6 digits, one `User` row |
| `test_onboard_same_mobile_returns_existing_code` | second call HTTP 200, same `join_code`, still one row |
| `test_review_unknown_business_404` | HTTP 404 |
| `test_review_duplicate_409` | HTTP 409 on second review by same user |
| `test_pin_unknown_user_404` | HTTP 404 (new behaviour) |
| `test_pin_sets_expires_at` | HTTP 200, `MapPin.expires_at` ≈ now + 30 days |
| `test_rate_limit_returns_429` | with limit 2, third `POST /api/onboard` in one minute is HTTP 429 |

Effort M · Risk: behind Coolify's proxy `request.client.host` may be the proxy; read `X-Forwarded-For` first hop only when a `LOOPER_TRUST_PROXY=true` env is set. This is a hot zone (auth-adjacent); confirm with Bill before deploying the limit values.

**Verify:** `cd "$LP/backend" && .venv/bin/python -m pytest -q tests/test_public_writes.py` then the full suite.

### B-6. Forward `TYPEDB_*` in docker-compose, or document graph-off

**Today:** `$LP/docker-compose.yml:9-20` forwards `LOOPER_DB_URL`, the two `HYBRIDCARD_*` vars and the `KNS_*`/`KASPA_*` vars. It forwards nothing named `TYPEDB_*`. The backend reads `TYPEDB_ENABLED` (`discover.py:265`), `TYPEDB_ADDRESS` and `TYPEDB_DB` (`discover.py:73-74`), and `$LP/.env.example:21-22` documents the first two. So in Docker `/api/discover` always returns `engine: "fallback"`, and `_brain_sync` (`ingest.py:29-69`) silently does nothing.

**Fix, option A** (add after `docker-compose.yml:12`):

```yaml
      TYPEDB_ENABLED: ${TYPEDB_ENABLED:-false}
      TYPEDB_ADDRESS: ${TYPEDB_ADDRESS:-}
      TYPEDB_DB: ${TYPEDB_DB:-}
```

Empty values are safe: `discover.py:71-74` treats empty as unset (decision 2026-08-12, `.SEED/decisions.md:186`).

**Fix, option B:** leave compose as is and add one line to `plans/COMPLETION_STATUS.md` under F2.1-F2.3: "Docker deploy runs graph-off by design until the internal-only TypeDB service exists; `engine` is always `fallback`." Option B costs nothing but must be written down so nobody debugs a "missing" graph.

Effort S · Risk: option A with `TYPEDB_ENABLED=true` and an unreachable address adds a failed TypeDB connect to every `/api/discover` call before fallback (`discover.py:266-270`); watch latency after enabling.

**Verify:** `cd "$LP" && docker compose config | grep TYPEDB_` shows three lines; `curl -s "http://localhost:8010/api/discover?suburb=Bondi" | python3 -c "import sys,json; print(json.load(sys.stdin)['engine'])"` prints `fallback` when disabled and `graph` when the service is up.

### B-7. Reconcile the tool count

**Measured 2026-09-13:**

| Where | Count | Evidence |
|---|---|---|
| `toolSpecs` registry | **30** | `grep -c '^    name: "' $LP/looper-bot/electron/main.cjs` = 30; registry spans `main.cjs:86-495` |
| Dispatch branches | **31** | `grep -c 'if (name === "' main.cjs` = 31 (`:792` to `:1024`) |
| Branch with no spec | 1 | `thumbnail_loading_prepare` at `main.cjs:857` |
| Docs | 23 | `plans/IMPLEMENTATION_PLAN.md:29` and `:78`, `SEED.md:20`, `plans/DESIGN_PROMPT.md:22` |

The dossier's "23/29/31" figure: 23 and 31 are confirmed; "29" appears in no repo file other than this sentence (`grep -rn "29 tools" plans SEED.md .SEED --exclude=HYBRIDCARD-ADOPTION-NOTES.md` is empty). The correct middle number is 30.

**Fix:**

1. `$LP/looper-bot/electron/tests/tool-registry.test.cjs` (new, picked up by the existing `"test": "node --test electron/tests/*.test.cjs"` script at `looper-bot/package.json:11`): read `main.cjs` as text, collect the `name:` values inside `toolSpecs`, collect the `if (name === "...")` names, assert every spec has a branch, and assert the spec count equals a constant `EXPECTED_TOOL_COUNT = 30`. Also assert `thumbnail_loading_prepare` either gains a spec or is documented as renderer-internal.
2. Update the four doc lines above to "30 model-facing tools" (or the number after step 1 settles the orphan).

Effort S · Risk: none; the test is read-only over source text.

**Verify:** `cd "$LP/looper-bot" && npm test` and `grep -n "23 tools\|23 model-facing" plans/IMPLEMENTATION_PLAN.md plans/DESIGN_PROMPT.md SEED.md` returns nothing (today it returns four lines).

---

## Order of work

1. B-4 (kaspa) first: it is the only blocker on the current branch and it is small.
2. B-1 (CORS) and B-7 (tool count): both S, both pure tests plus config.
3. B-3 (fixture): S, but needs one HybridCard test edit; do it in the same sitting as any HybridCard bridge work.
4. B-6 (TypeDB env): decide A or B with Bill; either is S.
5. B-2 (aggregates) and B-5 (public writes): M each; B-5 touches a hot zone, so it waits for Bill's approval.

For HybridCard, A2 (registry) and A3 (allow-list) map to D4 phases P6 and P5; A5 (chip truth) is the fix for B29 and should be in P1 alongside owner notification.
