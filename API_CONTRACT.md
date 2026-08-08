# BillBro — API Contract

**Status: fully reconciled with Person A's real API**, plus a build-order
change from `BillBro_TeamUpdates.md`. Backend is FastAPI at
`localhost:8000`, docs at `/docs`, SQLite-backed.

## 🔧 New: full backend audit, four real bugs found and fixed, Admin now built

Person C spent a session pulling Person A's `Person-A` branch directly
into a local worktree and reading every route line-by-line — not waiting
on his own doc claims. Found and fixed **four previously-unknown bugs**
none of the three of us had caught, applied the fixes directly in the
worktree (not pushed — not this branch to push to), and separately
**built out the entire Admin backend** (`GET`/`PUT /admin/settings`,
`POST /admin/bulk_upload`) that was still a frontend-only placeholder.
All changes syntax-verified (`python3 -m py_compile`) and their core
logic hand-simulated against the real seeded `billbro_mvp.db`, but
**not runtime-tested** — no FastAPI/uvicorn install available from this
side. Full list of what changed:

1. **`POST /checkout/bill` body-format bug** — `detections: List[dict]`
   was the sole body parameter with no wrapping model. FastAPI's rule for
   a single bare `List`/`Dict` body param is that it expects the raw
   array to BE the entire request body, unwrapped — but every doc and
   `api.js` send `{"detections": [...]}`. Real checkouts would have
   422'd. Fixed with a `CheckoutRequest(BaseModel)` wrapper.
2. **`PATCH /inventory/{item_id}` query-param bug** — same root cause as
   the already-fixed `POST /items` bug: `quantity`/`reason` were bare
   scalar args, which FastAPI reads as query params, not the JSON body
   `adjustInventory()` actually sends. Lower urgency since no manual-
   adjust UI calls this yet, but fixed the same way — wrapped in
   `AdjustInventoryRequest(BaseModel)`.
3. **Unhandled 500 on duplicate item name** — `create_item()` only
   pre-checked SKU uniqueness; `Item.name` is also DB-unique, so a
   duplicate name would hit an unhandled `IntegrityError` on commit
   instead of a clean 400. Added a name pre-check mirroring the SKU one.
4. **Missing `status` in `Item.to_dict()`** — the `status` column
   (`pending`/`training`/`shelved`/`failed`) was never actually surfaced
   in any `/items` response, despite being central to the whole Add Item
   pipeline. Added.
5. **CRITICAL: training upload was completely non-functional** — worse
   than the others. `uploadTrainingImages()` in `api.js` never sent
   `item_name` at all (backend requires it, no default → instant 422
   before a single photo processed), AND `item_id`/`item_name`/`store_id`
   were bare scalar params in a route that also has `File(...)` params —
   FastAPI does **not** auto-promote sibling scalars to form fields just
   because the route is multipart; they were still being read as query
   params. Fixed on both sides: backend params changed to explicit
   `Form(...)`, and `api.js`/`AddItem.jsx` updated to actually derive and
   send `item_name` (see "Add Item" section below for the new
   `toClassName()` slugify helper).

None of these five were previously flagged by either Person A or Person
B in their own review — found only by reading every route against what
the frontend actually sends, end to end.

**Also seeded the live `billbro_mvp.db`** directly via Python's sqlite3
(no server needed) — the six base items (Apple/Banana/Dragon
Fruit/Custard Apple/Diet Coke/Pepsi), all `status='shelved'`, matching
`billbro_sample_data.sql`, plus `models/versions.json` with the real
Pepsi-retrain metrics so the fixed `/models/active` route has something
to return. Re-ran the standalone `_normalize_name()` matching simulation
against this real seeded data — confirmed the checkout-matching fix
genuinely works, not just reads correctly.

## ✅ `/checkout/bill`'s item-matching bug is confirmed fixed — but read the new caveat

The bug (`Item.name.ilike(item_name)` never matching "Diet Coke" against
"diet_coke", or "Dragon Fruit" against "dragonfruit" with no separator
at all) is **confirmed fixed directly in `api_app.py`** — pulled Person
A's branch and read the real code, not relying on a doc claim. He
implemented exactly the `_normalize_name()` fix Person B suggested
(strip all non-alphanumerics on both sides before comparing), with a
clear explanatory comment in the code itself.

**New behavior that shipped in the same commit, worth knowing:**
`process_checkout()` now also filters `if item.status != "shelved": continue`
— an item has to actually be shelved to ring up at checkout, matching
the `pending → training → shelved` gate `API_CONTRACT.md` has described
for a while, but which nothing was actually enforcing until now. This
means **checkout depends on `migrate_items_training_columns.py` having
been run** — that script backfills existing items (the 6 base-model
items included) to `status = "shelved"` so they don't silently vanish
from checkout the moment this filtering went live. If a real checkout
test still comes back empty, this migration not having been run is the
first thing to check, not the matching logic (that part's confirmed
correct now).

## ⚠️ Build order reversed — read this first

Per `BillBro_TeamUpdates.md`, the team is no longer following the original
Week 1→12 phase order. **"Add Item → Train → Shelve" is now the first
core feature**, ahead of checkout/billing. Checkout was already built and
is live (see below) — that doesn't change — but Add Item has been
reprioritized and built out on the frontend ahead of Person A's backend
endpoints landing, so it's ready the moment they exist.

This also introduces schema changes:
- Items now carry **`batch_number`** in addition to the original fields.
  (The team update doc also mentioned `barcode`, but that's been dropped
  from the frontend — see "Barcode dropped" below.)
- Items have a **status lifecycle**: `pending → training → shelved` (or
  `failed`). An item is only checkout-detectable once `status = "shelved"`.
  This didn't exist before — item creation and checkout-availability used
  to be the same event.

`frontend/src/api.js` mirrors this — confirmed calls at the top, the Add
Item / training section next (built ahead of the backend), then other
proposed/unbuilt calls below a clear divider.

## ✅ Update via `CONTEXT_FOR_PERSON_C_v2.md`: `/detect` was silently broken, now fixed

Person A found a real bug while preparing for the end-to-end test he
knew was coming: `api_app.py` has always hardcoded
`model_path = "models/grocery_yolov8.pt"`, but the model file was
actually committed at the repo root (`./grocery_yolov8.pt`) — no
`models/` directory ever existed. So `/detect` has likely been returning
`503` since the commit that introduced it, entirely separate from
anything on the frontend. Confirmed via `git log`/`git ls-files`, fixed
with `git mv` (preserves history), pushed and verified via `git ls-tree`
on the actual commit.

**This means the planned real end-to-end `/detect` test (pull
`Person-A`, `npm run dev`, real photo) hasn't actually been run against
working conditions yet** — worth doing now that the model path is fixed,
since it should behave differently than it would have before.

Also swapped in while he was in there: Person B's retrained model,
`billbro_v3_best.pt` (YOLOv8m, 5,435 images, same 6 classes, mAP50
~0.92) — SHA-256 verified against what Person B sent. **Update: Pepsi is
now confirmed fixed** — see the Pepsi section below, real training-log
numbers, not a guess anymore. Checkout's warning has been softened to
match (not removed — there's a real, if smaller, miss rate).

`PERSON_C_NEXT_STEPS.md` / `PERSON_A_NEXT_STEPS.md` (same stale-template
family, sent by Person B alongside the model file) — independently
confirmed dead by Person A too, reached the same conclusion before
seeing this project's note about it. Nothing to build from either.

## ✅ Update via `SYNC_FOR_PERSON_C.md`: the gaps below are now closed

Person A re-checked and fixed things after the git-log audit found his
docs running ahead of what was pushed. As of `Person-A` @ `42874b8`:
- **`/detect` is genuinely pushed now** — a `git stash pop` merge-conflict
  bug (literal `<<<<<<<` markers left in `api_app.py`) is what had been
  silently blocking it; fixed. Still needs a real end-to-end test from
  this side (`npm run dev` against his running API) to confirm — spec
  match isn't the same as having actually run it together yet.
- **`POST /items` had a real bug** — his handler took plain scalar args,
  which FastAPI reads as query params, not a JSON body, so every real
  submit would have 422'd. Fixed with a proper Pydantic request model.
  No frontend change needed — `api.js` was already sending JSON.
- **`batch_number` confirmed dead** — no such column in `database.py`.
  Removed from the Add Item form entirely (previously sent but silently
  ignored — Pydantic drops unknown fields by default).
- **`/items` vs `/inventory`** — confirmed for real: `/inventory` has
  `current_count`/`status`, `/items` is catalog-only. Was a docs bug, not
  a behavior bug. Inventory page was already using the right one.
- **`FRONTEND_INTEGRATION_GUIDE.md`** exists in the repo root on
  Person A's side (pushed with Week 1 foundation) — not yet pulled into
  this local checkout since it's a different branch; worth grabbing
  before picking an nginx deploy target, it apparently covers that.
- Person B's branch has real commits now too (ML pipeline, not just
  placeholder files) — separate from anything the frontend calls
  directly, but consistent with the detect fix landing.
- `main` merge is intentionally on hold pending a team sync — not a gap
  anyone needs to individually fix.

## ✅ Resolved (round 1), then a second real bug found (round 2)

Round 1: the earlier gap (headline said "LIVE," but Person A's own doc
admitted an unresolved numpy/torch dependency issue and unpushed code)
closed per `SYNC_FOR_PERSON_C.md`. Root cause was a `git stash pop`
conflict committed with literal `<<<<<<<`/`=======`/`>>>>>>>` markers
still in `api_app.py`. Fixed and pushed.

Round 2, per `CONTEXT_FOR_PERSON_C_v2.md`: even after that fix, `/detect`
was **still silently broken** — a completely separate bug. The model
path was hardcoded to `models/grocery_yolov8.pt`, but the model file was
committed at the repo root instead, so no `models/` directory ever
existed. `/detect` had likely been 503ing since the commit that
introduced it. Fixed with `git mv` (path corrected, history preserved),
and Person B's retrained model (`billbro_v3_best.pt`, mAP50 ~0.92) was
swapped in at the same time, SHA-256 verified.

Still true: **"Integrated" here means "wired up against the documented
contract,"** not "confirmed against a live run." That confirmation is a
`git pull origin Person-A && npm run dev` + real photo away — hasn't
happened yet from this side, and is worth doing now specifically because
the last attempt would have failed for reasons that had nothing to do
with the frontend.

## 🚩 Team misalignment — confirmed harmless, not resolved

`FOR_PERSON_C_CHECKOUT_INTEGRATION.md` (Checkout = Week 1, Add Item =
"Week 2 Preview") and `BillBro_TeamUpdates.md` (Add Item first) still
disagree. Per `SYNC_FOR_PERSON_C.md`, Person A confirms this is genuinely
just a doc sync issue, not a real prioritization conflict — he doesn't
have a strong reason to insist on one order over the other, and both
pages are built regardless. Practical answer for right now: test
Checkout first since `/detect` is what's actually live; Add Item stays
blocked on his two training endpoints either way.

## Status tracker

| # | Endpoint | Status | Used by |
|---|---|---|---|
| 1 | `GET /items` | ✅ Confirmed (`store_id` query param, default `store_001`) | not called yet |
| 2 | `GET /items/{id}` | ✅ Confirmed | not called yet |
| 3 | `POST /items` | ✅ Confirmed, full request/response shape, JSON-body bug fixed | Add Item — **Integrated** |
| 4 | `GET /inventory` | ✅ Confirmed | Inventory — **Integrated** |
| 5 | `PATCH /inventory/{id}` | ✅ Confirmed, response shape now known. ⚠️ Had the same query-param-vs-JSON-body bug as `POST /items` — found in this session's audit, fixed with `AdjustInventoryRequest` | Inventory manual adjust (not wired yet) |
| 5b | `PATCH /items/{id}/restock` | ✅ New, found directly in his pushed code (not doc'd by him yet). Full shape below | Inventory — **Integrated** (restock button + inline form) |
| 6 | `GET /alerts` | ✅ Confirmed (`resolved=false` default filter) | Alerts — **Integrated** |
| 7 | `PATCH /alerts/{id}` | ✅ Confirmed, no request body | Alerts resolve — **Integrated** |
| 8 | `POST /detect` | ✅ Confirmed shape. Two real bugs found and fixed (merge-conflict markers, then a wrong model path) — new retrained model swapped in too. Not yet tested end-to-end from this side | Checkout — **Integrated against spec** |
| 9 | `POST /checkout/bill` | ✅ Confirmed, item-matching bug fixed in real code. ⚠️ Now enforces `status == "shelved"` — needs the DB migration run or it'll find zero items. **Also had a body-format bug** (raw `List[dict]` body param expected the request body to BE the array, not `{"detections":[...]}`) — found and fixed this session with a `CheckoutRequest` wrapper | Checkout — **Integrated, confirmed fixed, pending real test** |
| 10 | `GET /models/active` | ✅ **Fix applied directly in Person A's worktree this session** — now reads from `StoreModelManager`/`models/versions.json` instead of the dead SQL table. Also added `GET /models` + activate/rollback while in there. Seeded `models/versions.json` with real Pepsi-retrain metrics so it returns something. Not pushed — his branch, his call | Models (not built yet) |
| 11 | `GET /health` | ✅ Confirmed, full shape | not called yet |
| 12 | `GET`/`PUT /admin/settings`, `POST /admin/bulk_upload` | ✅ **Built this session**, directly in Person A's worktree (not pushed). Full shape below | Admin — ready to wire up |
| 13 | `POST /training/upload_images`, job status | ✅ Live, wired to Person B's `training.py`. ⚠️ Real `TrainingJob`/`Item` schema mismatches found (see below), plus a deeper-than-expected `data.yaml` blocker — base training images were never committed to the repo, needs a team infra decision. **Also: was completely broken** — `item_name` never sent by the frontend, and the multipart form fields were being read as query params. Fixed both sides this session (see critical bug #5 above) | Add Item — **Integrated, blocked on base-dataset infra for real testing** |
| 14 | `GET /models`, activate/rollback | ✅ **Built this session** alongside the `/models/active` fix, in Person A's worktree. **Versioning scheme confirmed: strings (`v1`/`v2`), not numeric ids** | Models |
| 15 | `GET/PUT /prices` | Unnecessary | `GET /items` already returns `price` |

**Checkout, Inventory, Alerts are wired and spec-correct, still not yet
confirmed by a real run** — `/detect`'s two bugs and `/checkout/bill`'s
matching bug are all now confirmed fixed in the actual pushed code, but
no one's actually run the full flow against a live backend yet from this
side. Restock is new and integrated. **Add Item is fully wired, endpoints
and all**, but blocked on a real infra decision (base training dataset
location), not just a missing file — though Person A did add a clean
fail-fast `503` if `data.yaml` itself is missing, so at least that
failure mode won't be silent. Admin and the fuller Models page are still
genuinely waiting (Weeks 7, 8).

---

## Confirmed endpoints

### `GET /items?store_id=store_001` — product catalog
```json
[
  {
    "id": 1, "name": "Apple", "sku": "APL001", "price": 35.00,
    "category": "fruits", "low_stock_threshold": 5,
    "expiry_date": "2026-09-15", "created_at": "2026-08-07T10:00:00"
  }
]
```
Note: Person A's later doc says this "includes current_count" for
inventory-page use too, which contradicts the example above (no
current_count shown) and his earlier "‌/items has no stock info" framing.
Given the inconsistency, the Inventory page keeps using `GET /inventory`
(explicitly and repeatedly confirmed as correct for that page) rather than
switching to `/items`.

### `POST /items` — create an item
```json
// Request
{ "name": "Maggi Noodles", "sku": "MAG001", "price": 15.00,
  "category": "snacks", "expiry_date": "2026-12-31", "low_stock_threshold": 5,
  "batch_number": "B2026-08-14" }
// Response
{ "status": "success", "item_id": 7, "item": { "...": "full item object" } }
```
`name`, `sku`, `price` required. `category`, `expiry_date`,
`batch_number` optional. `low_stock_threshold` defaults to 5.
`batch_number` is new per `BillBro_TeamUpdates.md` — not shown in Person
A's original examples, so the exact field name is the frontend's best
guess at what he'll expect; confirm once his endpoint exists. Per the
same doc, the created item starts at **`status: "pending"`** — it isn't
checkout-detectable until training succeeds and it flips to `"shelved"`.

🔄 **Reversal: `batch_number` is back, plus a new `batch_arrival_date`.**
It was briefly confirmed removed (`SYNC_FOR_PERSON_C.md` — no such
column existed at the time), but reading Person A's currently-pushed
`database.py`/`api_app.py` directly shows both are now real, optional
columns on `items`. **Deliberately not re-added to the Add Item form**
— his own code comments frame these as belonging to the new restock flow
below (batch tracking for *re*-stocking an existing item), not initial
item creation. `POST /items`'s `CreateItemRequest` accepts them as
optional, so nothing breaks either way, but Add Item doesn't send them.

`barcode`'s absence is separately and independently confirmed still
correct — checked directly, not just inferred.

Also resolved: `POST /items` had a real backend bug (handler took scalar
args, which FastAPI parses as query params, not JSON body — every real
submit would 422). Fixed by Person A, pushed. No frontend change needed,
`api.js` was already sending JSON matching the docs.

### `PATCH /items/{item_id}/restock` — new endpoint, now built on the frontend

Found directly in Person A's `api_app.py` — not something he flagged in
a doc, discovered by reading his branch. Covers "a new batch of an
existing item arrived," which `POST /items` can't handle (`sku` is
unique, so an existing item can't be re-created):
```json
// Request
{ "quantity_added": 24, "batch_number": "B2026-08-14",
  "batch_arrival_date": "2026-08-09" }
// Response
{ "status": "success", "item_id": 7, "item_name": "Maggi Noodles",
  "old_count": 6, "new_count": 30,
  "batch_number": "B2026-08-14", "batch_arrival_date": "2026-08-09" }
```
`quantity_added` required (must be positive). `batch_number` and
`batch_arrival_date` both optional — if given, they overwrite the item's
current batch fields (no per-batch history; `items:inventory` is a 1:1
relationship, so there's no concept of multiple concurrent batches of
the same item). Does **not** auto-resolve existing `LOW_STOCK`/`STOCK_OUT`
alerts — those still need a manual `PATCH /alerts/{id}` resolve, same as
everywhere else. **Built on the Inventory page** — a "Restock" button per
row opens an inline form (quantity required, batch fields optional).

#### Barcode dropped from the frontend

`BillBro_TeamUpdates.md` also listed `barcode` as a new field, but it's
been deliberately left out of the Add Item form. Reasoning: most of
BillBro's actual catalog is loose produce (apple, banana, dragon fruit,
custard apple), which typically doesn't have real scannable barcodes at
retail — only the packaged goods (Diet Coke, Pepsi) would. There's also
no scanner integration built (no USB scanner or camera-decode library),
so "barcode" would just be a manually-typed text field, which is exactly
the failure mode barcodes' check-digit design exists to prevent. Rather
than store an unreliable, largely-empty field, SKU stays the one
enforced-unique identifier. If Person A's backend still expects a
`barcode` field on `POST /items`, it can just be omitted — worth
confirming his validation doesn't require it.

### `GET /inventory?store_id=store_001` — stock levels (live, integrated)
```json
[
  { "id": 1, "name": "Apple", "sku": "APL001", "price": 35.00,
    "current_count": 47, "low_stock_threshold": 5, "status": "OK" }
]
```
`status`: `OK | LOW_STOCK | OUT_OF_STOCK`.

### `PATCH /inventory/{id}`
```json
// Request
{ "quantity": 1, "reason": "billed" }
// Response
{ "status": "success", "item_name": "Apple", "new_count": 46, "old_count": 47, "alerts": [] }
```

### `GET /alerts?store_id=...&resolved=false` (live, integrated)
```json
[
  { "id": 1, "alert_type": "LOW_STOCK", "severity": "warning",
    "message": "Apple stock running low: 4 units", "item_name": "Apple",
    "resolved": false, "created_at": "2026-08-07T15:30:00" }
]
```

### `PATCH /alerts/{id}` — resolve (live, integrated)
No request body.
```json
{ "status": "success", "alert": { "...": "resolved: true, resolved_at: ..." } }
```

### `POST /detect` — Option A, decided (live, integrated)
```json
// Request
{ "image": "<base64, no data-URL prefix>", "confidence_threshold": 0.7 }
// Response
{
  "detections": [
    { "item_name": "apple", "confidence": 0.95, "bbox": [100, 50, 200, 150] },
    { "item_name": "diet_coke", "confidence": 0.92, "bbox": [250, 75, 350, 225] }
  ],
  "processing_time_ms": 45
}
```
Raw per-instance detections (one entry per detected object, not
pre-grouped). **Frontend does the aggregation** into
`{item_name, confidence, quantity}` — `utils.js`'s `aggregateDetections()`
does this (confidence = average across that item's detections; Person A's
docs don't specify how to pick one, so this is a judgment call).

**Confirmed LIVE** as of `FOR_PERSON_C_CHECKOUT_INTEGRATION.md` (Person A
finished implementing it, not just deciding on it):
- `detector.detect_from_base64()` is the exact backend implementation —
  shape matches this doc precisely, no surprises.
- The base model (`models/grocery_yolov8.pt`) is trained on exactly six
  items: **Apple, Banana, Dragon Fruit, Custard Apple, Diet Coke, Pepsi**.
  Checkout's idle screen says so, so staff aren't surprised when other
  items don't detect.
- Default `confidence_threshold` is 0.5 if omitted.
- **Real measured latency** (per Person A, supersedes Person B's earlier
  "~2 min on CPU" worst-case estimate): first request of a session takes
  ~2-3s (model load), subsequent ones are ~100-200ms. `detectImage()`'s
  timeout in `api.js` was accordingly dialed back from a defensive 3
  minutes to 30 seconds, and the Checkout "still detecting" message
  updated to match — no longer implies a 2-minute wait is normal.
- Testing options Person A provided: Swagger UI at `/docs`, a
  `test_detect_endpoint.py` script, or curl — useful if something looks
  broken and you want to isolate frontend vs. backend.
- ⚠️ **See the callout above** — Person A's own doc says he hasn't
  actually run this successfully yet (unresolved numpy/torch dependency
  issue) and the code isn't pushed to GitHub. Spec-complete, not
  verified-working.

**✅ Pepsi: fixed, with real numbers.** Was AP50 = 0.000 (dataset gap —
the source data only had a generic soda-can image standing in, zero real
Pepsi images ever entered training). Person B retrained with a real
Pepsi dataset (202 images) and confirmed from the actual training log
(`TRAINING_RESULTS.md` on his branch, not a template guess):

| | Before | After retrain |
|---|---|---|
| AP50 | 0.000 | **0.885** |
| Precision | — | 0.944 |
| Recall | — | 0.780 |

Genuinely a working trained class now, not a "detect as diet_coke"
workaround. Recall 0.780 means it'll still miss roughly 1 in 5 real
cans (smallest val set of the six classes — 50 instances vs 200-400 for
the fruit classes), so Person B's own recommendation was to **soften**
the Checkout warning rather than remove it outright — done: it now says
detection "has improved a lot" but still "misses roughly 1 in 5 cans,"
instead of the old blanket "don't trust it."

Separate real-world finding from Person B's own testing worth knowing:
**Pepsi and Diet Coke can get confused with each other** — the two most
visually similar classes (both cylindrical cans) and by far the smallest
val sets. A lone Diet Coke was once mislabeled "pepsi"; both together in
one frame detected with swapped labels. Called acceptable for
proof-of-concept, not being re-opened right now — just worth knowing if
a demo shows a soda mislabeled as the other one, that's a known,
accepted limitation, not a new bug.

### `POST /checkout/bill` (live, integrated)
```json
// Request
{ "detections": [
    { "item_name": "apple", "confidence": 0.95, "quantity": 2 },
    { "item_name": "diet_coke", "confidence": 0.92, "quantity": 1 }
] }
// Response
{
  "status": "success", "receipt_id": "RCP_20260807_153000",
  "cart": [{ "item_id": 1, "name": "Apple", "price": 35.00, "quantity": 2,
             "subtotal": 70.00, "confidence": 0.95 }],
  "total": 120.00, "alerts": []
}
```
The frontend renders the receipt straight from this response — backend is
the source of truth for pricing/totals, not the frontend's local
`calculateTotal()`.

### `GET /models/active`
```json
{ "id": 1, "store_id": "store_001", "version": "v1",
  "model_path": "models/store_001_v1.pt",
  "metrics": { "mAP50": 0.92, "mAP": 0.87, "accuracy": 0.90 },
  "is_active": true, "trained_at": "...", "deployed_at": "...", "created_at": "..." }
```
⚠️ **Bug found by Person B:** this shape is right, but as currently wired
the route queries a SQL `ModelVersion` table that nothing ever writes to
— `StoreModelManager.register_version()` (called at the end of every
successful `retrain_model()`) writes to `models/versions.json` instead,
by design, to keep the DB out of the ML code. Two parallel, unsynced
sources of truth — the route will 404 no matter how many models get
trained. Fix: read from `StoreModelManager` directly instead of the SQL
table (full route code in Person B's `FOR_PERSON_A_MODELS_ENDPOINTS.md`).
Not confirmed landed yet as of this doc's last update — worth checking
before building the Models page against this endpoint.

**Also resolved:** the open question below about whether model versions
are strings or numeric ids — **confirmed strings** (`"v1"`, `"v2"`, not
numeric). `activateModel(versionId)` / `rollbackModel(versionId)` in
`api.js`'s proposed section should pass that string straight through.

### `GET /health`
```json
{ "status": "healthy", "timestamp": "...", "version": "1.0.0",
  "database": "connected", "uptime_seconds": 3600 }
```

---

## Admin — built this session, in Person A's worktree (not pushed yet)

`api.js`'s `uploadBulkCsv()`/`updateStoreSettings()` were written speculatively
(the "PROPOSED" section) against a guessed shape, before Person A had built
anything. This session built the real thing against exactly that guessed
shape — no frontend change needed, `api.js` already matches.

New `store_settings` table (one row per `store_id`) added to `database.py`
and to the live `.db` via an extension to `migrate_items_training_columns.py`
(idempotent, same pattern as the rest of that script — safe to re-run).

### `GET /admin/settings?store_id=store_001`
```json
{ "store_id": "store_001", "tax_rate_pct": 18.0, "currency_symbol": "₹",
  "low_stock_default_threshold": 5, "updated_at": null }
```
Upserts a default row on first read — never 404s for a store that hasn't
customized anything yet.

### `PUT /admin/settings?store_id=store_001`
```json
// Request — partial update, only send what's changing
{ "tax_rate_pct": 12.5 }
// Response
{ "status": "success", "settings": { "...": "full settings object" } }
```

### `POST /admin/bulk_upload` — multipart, field `file` (.csv)
CSV header row required: `name, sku, price` mandatory,
`category, expiry_date (YYYY-MM-DD), low_stock_threshold` optional.
Upserts **by `sku`** — existing items get name/price/category/expiry/
threshold overwritten, but **status and current stock count are left
alone** (a catalog re-upload shouldn't silently wipe live inventory or
un-shelve an item). New items are created `status: "pending"` with a
zeroed inventory row, same as `POST /items`. Per-row errors (bad price,
missing field, name collision) are collected rather than failing the
whole upload.
```json
// Response
{ "status": "success", "created": 3, "updated": 12, "error_count": 1,
  "errors": [{ "row": 7, "error": "price 'abc' is not a number" }] }
```

⚠️ **Not runtime-tested** — same caveat as everything else built this
session, no FastAPI install available to actually start the server.
Syntax-verified and the SQL upsert logic hand-simulated directly against
the real `billbro_mvp.db` (confirmed a known SKU reads as "existing",
an unknown one reads as "new"), but never exercised through an actual
HTTP request.

---

## Add Item / training — both endpoints now live, one real-world blocker left

The Add Item page (`frontend/src/pages/AddItem.jsx`) is fully built —
details form (no `barcode` or `batch_number` — both confirmed unnecessary,
see above) → photo capture (15 recommended, 5 minimum) →
`POST /training/upload_images` → polls `GET /training/job/{id}` every 5s
→ shows shelved/failed result. Both endpoints are now live on Person A's
side, wired to Person B's `training.py` exactly as the locked-in shape
below.

**Still not testable end-to-end — and the fix is deeper than "get the
file."** `data.yaml` itself has since been handed over by Person B (it's
in his branch, `Person B/BillBro (FYP)/data.yaml`), but he flagged it
won't actually unblock training: `ReplayPool.bootstrap_from_base()`
doesn't just read the yaml, it reads the *actual base training images
and labels* it points to (samples 30 per class, ~180 images, to seed the
replay buffer). Those files only ever lived on Colab/local machines —
never committed to the shared repo (~5,000+ images, never made sense to
commit as raw training data). So having `data.yaml` alone would either
error immediately, or — the scarier version — silently produce an empty,
permanently-broken replay pool with no error at all. Person B already
fixed that silent-failure mode (`bootstrap_from_base()` now raises
`FileNotFoundError` loudly instead), but the actual unblock needs a team
decision on where a ~180-image representative sample should live (repo,
Git LFS, a cloud bucket) — not something to guess at. Nothing for the
frontend to do here either way, just flagging this is a real
infra/team-decision blocker, not a "waiting on one file" blocker.

### ✅ `GET /training/job/{id}` shape — now locked

Previously two docs disagreed on field names; `RESPONSES_TO_PERSON_B_AND_C.md`
resolves it — Person A confirms "Your TrainingJob table alignment: 100%
locked" against Person B's actual table:

```json
{ "id": 1, "item_id": 7, "status": "running", "progress": 35,
  "current_epoch": "2/5", "metrics": null, "error_message": null,
  "created_at": "...", "completed_at": null }
```

This is `BillBro_TeamUpdates.md`'s version, confirmed as final —
`PERSON_B_DELIVERABLES_ANALYSIS.md`'s `job_id`/`stage`/`epoch`/`updated_at`
naming was the earlier draft, not what shipped. Notes:
- The job's own id field is **`id`**, not `job_id` — `job_id` only shows
  up in the *upload* endpoint's response (what you poll with).
- `current_epoch` is a string like `"2/5"`, not a bare number.
- `status` enum is exactly `pending | running | success | failed`.

`AddItem.jsx`'s `normalizeJobStatus()` still checks a couple of
alternate field names as a defensive fallback, but that's no longer
load-bearing — just cheap insurance.

`status` values handled: `success | complete | completed | shelved` as
terminal-success, `failed | error` as terminal-failure, anything else
treated as still in progress.

On success, `metrics` looks like:
```json
{
  "mAP50": 0.92, "mAP50-95": 0.87, "precision": 0.95, "recall": 0.88,
  "per_class_AP50": { "apple": 0.93, "maggi_noodles": 0.90 },
  "epochs": 5, "new_item_train_images": 12
}
```
On failure, expect something like
`{ "status": "failed", "reason": "mAP50 0.75 below threshold 0.80. Capture 30+ more images." }`
— the Add Item UI surfaces that message directly since it's actionable.

Training itself can take **~15 min on GPU, up to ~1 hour on CPU** per
`BillBro_ContextForClaude.txt` — the UI says so and polls indefinitely
rather than timing out.

### Model versioning (Week 8, feeds `GET /models`, activate, rollback)
Backed by Person B's `StoreModelManager`: versions are per-store, named
`v1`, `v2`, etc. — **confirmed strings, not numeric ids** — stored as
`models/{store_id}_v{N}.pt`, with `models/{store_id}_latest.pt` pointing
at whichever is active. `list_versions(store_id)` returns version history
newest-last. Ready-to-paste `GET /models` + activate/rollback routes are
in Person B's `FOR_PERSON_A_MODELS_ENDPOINTS.md` (same file as the
`/models/active` bug fix above).

### ⚠️ `TrainingJob`/`Item` schema — real mismatches found in `database.py`

Person B checked the actual `database.py` against what `training.py`
produces and found the routes will break without these fixes on Person
A's side (not yet confirmed landed):
- **`TrainingJob` has no `metrics` column** — only a single `accuracy`
  float, but `retrain_model()` returns a full dict (`mAP50`, `mAP50-95`,
  `precision`, `recall`, `per_class_AP50`). Needs a `Text`/JSON column,
  or the per-class breakdown gets lost.
- **`current_epoch` is typed `Integer`**, but `training.py` writes
  strings like `"3/5"` (progress-through-a-run, not a bare count). Needs
  `String(20)`, or a mismatch will surface the moment a real job runs.
- **`Item` has no `status` column at all yet** — the whole
  `pending → training → shelved/failed` gate has nowhere to live in the
  DB. Needed before checkout/detection can correctly filter to
  `shelved`-only items.

None of this needs a frontend change — `AddItem.jsx`/`api.js` already
read/send the correct locked shape — but it means the training endpoints
being "live" doesn't yet guarantee a real job would complete cleanly
end-to-end, independent of the separate `data.yaml` blocker below.

---

## Resolved — no longer open

- ~~Detection endpoint (Option A vs B)~~ — **Option A**, `POST /detect`,
  live in Checkout now.
- ~~CORS~~ — configured for `localhost:5173`. Still need the production
  origin once nginx is actually deployed somewhere.
- ~~`/inventory` vs `/items`~~ — confirmed for real (not just documented):
  `/inventory` has `current_count`/`status`, `/items` is catalog-only.
  Was a docs bug, not a behavior bug.
- ~~`PATCH /alerts/{id}` body~~ — none needed.
- ~~`POST /items` body~~ — documented, and the real backend bug behind it
  (scalar args parsed as query params instead of JSON body) is fixed and
  pushed.
- ~~`GET /models/active` / `GET /health` shapes~~ — documented above.
- ~~`GET /training/job/{id}` field-name conflict~~ — locked, see above.
- ~~`barcode` on `POST /items`~~ — confirmed unnecessary, dropped, and
  confirmed still absent from Person A's real schema (checked directly).
- `batch_number` on `POST /items` — **status changed again, see the new
  Restock section below.** It's real now (was briefly confirmed removed,
  came back), but it's scoped to the new restock flow, not Add Item.
- ~~Cumulative vs. fresh-from-base retraining strategy~~ — confirmed
  cumulative fine-tuning + Person B's ReplayPool, to avoid catastrophic
  forgetting. Doesn't change anything on the frontend, just no longer
  open.
- ~~`/detect`'s actual working status~~ — the numpy/torch issue and
  unpushed code are resolved; real bug was a leftover merge-conflict
  block, now fixed and pushed (`42874b8`).

## Still open

- Auth — none mentioned; assumed open on local network for now.
- Production CORS origin, once a deploy target exists.
- ~~`FRONTEND_INTEGRATION_GUIDE.md`~~ — pulled and read directly from
  Person A's branch. **Confirmed stale, no action needed**: it's an early
  planning-era doc for a plain Create React App on port 3000, not the
  real Vite setup this project actually uses. Nothing in it applies.
- Search/filter on `/items`, pagination on `/inventory` — his own backlog
  item, not built yet.
- ~~Admin and the fuller model-management endpoints~~ — **both built this
  session**, directly in Person A's worktree (not pushed). See the new
  Admin section above and the `/models` row in the status tracker.
  Admin.jsx's UI (currently a roadmap placeholder) still needs to
  actually be built against these now-real endpoints.
- **New, replaces the old "run the real test" item:** confirm
  `migrate_items_training_columns.py` has actually been run against the
  live `billbro_mvp.db` — required for `/checkout/bill`'s new
  `status == "shelved"` filter to find the 6 base-model items at all.
  Once confirmed, the real end-to-end test (`git pull` + `npm run dev` +
  actual photo) is genuinely unblocked on both the matching-bug and
  status-gating fronts.
- ~~Pepsi's AP = 0.000 dataset gap~~ — **fixed**, AP50 now 0.885. See
  Pepsi section above. Checkout warning softened, not removed (0.780
  recall still means real misses).
- ~~`GET /models/active` 404 bug~~ — **fixed this session**, applied
  directly in Person A's worktree (not pushed, his branch to push to
  when ready).
- Whether shelving (item flipping to `status: "shelved"`) is automatic
  once the accuracy threshold clears, or needs a manual staff-confirm
  step — flagged as an open question in `BillBro_TeamUpdates.md` itself,
  between Person A and Person B.
- `main` merge — intentionally on hold pending an explicit team sync on
  order/conflicts, per Person A. Not a gap to fix individually.
