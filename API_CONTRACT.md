# BillBro — API Contract

**Status: fully reconciled with Person A's real API**, plus a build-order
change from `BillBro_TeamUpdates.md`. Backend is FastAPI at
`localhost:8000`, docs at `/docs`, SQLite-backed.

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

## 🚨 New: `/detect`'s "LIVE" claim is shakier than it sounds

`RESPONSES_TO_PERSON_B_AND_C.md` headlines with "`/detect` endpoint LIVE,
ready for integration" — but its own bottom section contradicts that:

> **🚨 Current Issue: numpy/torch Compatibility** — Working on fixing ML
> dependency installation issue. Once resolved: 1. `pip install` will
> work 2. `/detect` endpoint will be fully testable 3. Can share working
> API with Person C
>
> **Immediate Next Steps:** 1. Fix numpy/torch installation (in
> progress) 2. Test `/detect` endpoint locally 3. Commit to GitHub
> (branch: `feat/detect-endpoint`) ... **Timeline:** GitHub push
> today/tomorrow

So per the same doc: the code isn't fully testable yet, isn't pushed to
GitHub yet (sitting on an unmerged local branch), and hasn't actually
been run successfully end-to-end. That's a spec-complete, code-written
state — not a confirmed-working one. Doesn't change anything on the
frontend (already built against the documented shape, which multiple
docs agree on), but **"Integrated"** below should be read as "wired up
against the documented contract," not "verified working against a
live backend" until this is confirmed resolved.

## 🚩 Possible team misalignment — flagging, not resolving

`FOR_PERSON_C_CHECKOUT_INTEGRATION.md` (Person A, sent after
`BillBro_TeamUpdates.md`) frames Checkout as "This week (Week 1)" work
and Add Item as "Next Week (Week 2 Preview)" — i.e. **the original,
un-reversed order.** That directly conflicts with
`BillBro_TeamUpdates.md`'s "Add Item → Train → Shelve comes first"
decision. Possibilities: Person A hasn't seen the team update, the
reversal got walked back and nobody told this doc's author, or the two
docs are just talking about different things (this one is scoped
narrowly to "/detect is ready, go wire up Checkout" and may not be
making a claim about overall sequencing). Worth a quick sync to confirm
which order is actually current — doesn't block frontend work either way
since both Checkout and Add Item are now built, but worth knowing which
one Person A/B are actually prioritizing on their end.

## Status tracker

| # | Endpoint | Status | Used by |
|---|---|---|---|
| 1 | `GET /items` | ✅ Confirmed (`store_id` query param, default `store_001`) | not called yet |
| 2 | `GET /items/{id}` | ✅ Confirmed | not called yet |
| 3 | `POST /items` | ✅ Confirmed, full request/response shape | Add Item (not built yet) |
| 4 | `GET /inventory` | ✅ Confirmed | Inventory — **Integrated** |
| 5 | `PATCH /inventory/{id}` | ✅ Confirmed, response shape now known | Inventory manual adjust (not wired yet) |
| 6 | `GET /alerts` | ✅ Confirmed (`resolved=false` default filter) | Alerts — **Integrated** |
| 7 | `PATCH /alerts/{id}` | ✅ Confirmed, no request body | Alerts resolve — **Integrated** |
| 8 | `POST /detect` | ✅ Confirmed shape — Option A decided. ⚠️ Person A's own doc says still unverified/unpushed on his end (numpy/torch issue) | Checkout — **Integrated against spec** |
| 9 | `POST /checkout/bill` | ✅ Confirmed | Checkout — **Integrated** |
| 10 | `GET /models/active` | ✅ Confirmed, full shape | Models (not built yet) |
| 11 | `GET /health` | ✅ Confirmed, full shape | not called yet |
| 12 | `POST /admin/import_csv`, settings | ❌ Not built (Week 7) | Admin |
| 13 | `POST /training/upload_images`, job status | ❌ Backend not built yet — **frontend built ahead of it** (see below) | Add Item — UI done, waiting on backend |
| 14 | `GET /models`, activate/rollback | ❌ Not built yet, versioning scheme now known (Week 8) | Models |
| 15 | `GET/PUT /prices` | Unnecessary | `GET /items` already returns `price` |

**No open blockers left for Checkout, Inventory, or Alerts** — all three
are live. **Add Item's UI is fully built** (details form → photo capture →
training progress → shelved/failed result) but will error out until
Person A's `POST /training/upload_images` and `GET /training/job/{id}`
exist — built ahead of time on purpose, per the reprioritization above.
Admin and the fuller Models page are still genuinely waiting (Weeks 7, 8).

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

⚠️ **New wrinkle:** `RESPONSES_TO_PERSON_B_AND_C.md` gives a fuller,
"confirmed" `POST /items` example, and it shows **neither `batch_number`
nor `status`**, in either the request or the response:
```json
// Request
{ "name": "Maggi Noodles", "sku": "MAG001", "price": 15.00,
  "category": "snacks", "expiry_date": "2026-12-31", "low_stock_threshold": 5 }
// Response
{ "status": "success", "item_id": 7,
  "item": { "id": 7, "name": "Maggi Noodles", "sku": "MAG001", "price": 15.00,
    "category": "snacks", "low_stock_threshold": 5, "expiry_date": "2026-12-31",
    "created_at": "2026-08-08T..." } }
```
No `barcode` either, which matches the frontend's decision to drop it —
good. But `batch_number`'s absence is new and unconfirmed either way: it
could just be an abbreviated example (optional fields often get left out
of docs), or it could mean the field isn't actually supported server-side.
The frontend keeps sending `batch_number` for now since removing it on a
guess is riskier than a field the backend silently ignores — **worth a
direct confirm with Person A** rather than assuming. Same logic for the
missing `status` in the response: not proof it doesn't exist, just not
shown here.

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

**⚠️ Pepsi: don't trust it yet.** Per `RESPONSES_TO_PERSON_B_AND_C.md`,
Pepsi has **AP = 0.000** — the training data only had a generic soda-can
image standing in for it, so real Pepsi cans won't reliably detect
despite `pepsi` being a valid model class. Confirmed not a frontend bug.
Checkout's idle screen now lists the five reliable items separately from
Pepsi, with an explicit warning, so staff don't trust it the same way.
Will need real Pepsi training data to fix — tracked as a Person B/ML
backlog item, not a frontend one.

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

### `GET /health`
```json
{ "status": "healthy", "timestamp": "...", "version": "1.0.0",
  "database": "connected", "uptime_seconds": 3600 }
```

---

## Add Item / training — frontend built ahead of the backend

The Add Item page (`frontend/src/pages/AddItem.jsx`) is fully built —
details form (including `batch_number`; `barcode` deliberately omitted,
see above) → photo capture (15 recommended, 5 minimum) →
`POST /training/upload_images` → polls
`GET /training/job/{id}` every 5s → shows shelved/failed result. It will
error out on the training-upload/poll calls until Person A builds those
two endpoints, by design (built ahead of time per the reprioritization).

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
`v1`, `v2`, etc. (strings, not necessarily numeric ids), stored as
`models/{store_id}_v{N}.pt`, with `models/{store_id}_latest.pt` pointing
at whichever is active. `list_versions(store_id)` returns version history
newest-last. Worth confirming with Person A whether `GET /models` returns
that same `v1`/`v2` string scheme or wraps it in numeric ids before
building the Models page against it.

---

## Resolved — no longer open

- ~~Detection endpoint (Option A vs B)~~ — **Option A**, `POST /detect`,
  live in Checkout now.
- ~~CORS~~ — configured for `localhost:5173`. Still need the production
  origin once nginx is actually deployed somewhere.
- ~~`/inventory` vs `/items`~~ — documented (with one lingering
  inconsistency noted above).
- ~~`PATCH /alerts/{id}` body~~ — none needed.
- ~~`POST /items` body~~ — documented above (mostly — see `batch_number`
  caveat below).
- ~~`GET /models/active` / `GET /health` shapes~~ — documented above.
- ~~`GET /training/job/{id}` field-name conflict~~ — locked, see above.
- ~~`barcode` on `POST /items`~~ — Person A's confirmed shape has no
  `barcode` field, matching the frontend's decision to drop it. No
  validation conflict expected.
- ~~Cumulative vs. fresh-from-base retraining strategy~~ — confirmed
  cumulative fine-tuning + Person B's ReplayPool, to avoid catastrophic
  forgetting. Doesn't change anything on the frontend, just no longer
  open.

## Still open

- Auth — none mentioned; assumed open on local network for now.
- Production CORS origin, once a deploy target exists.
- The `/items` vs `/inventory` "current_count" inconsistency noted above —
  not blocking (Inventory works fine off `/inventory`), just worth a
  sanity-check with Person A at some point.
- `FRONTEND_INTEGRATION_GUIDE.md` — Person A has referenced this repeatedly
  but it lives on his machine (`C:\Users\Admin\Desktop\BE Project\...`) and
  hasn't actually been shared. Worth asking for the actual file.
- Search/filter on `/items`, pagination on `/inventory` — his own backlog
  item, not built yet.
- Admin and the fuller model-management endpoints — not built yet
  (Weeks 7, 8).
- **New:** `/detect`'s actual working status — Person A's own doc admits
  an unresolved numpy/torch dependency issue and unpushed code (see
  callout near the top). Worth confirming it's actually resolved and
  pushed before relying on it as truly live.
- **New:** whether `batch_number` is really accepted by `POST /items` —
  the newest "confirmed" example omits it entirely (see `POST /items`
  section above). Frontend keeps sending it for now; needs a direct
  answer either way.
- **New:** Pepsi's AP = 0.000 dataset gap — tracked as Person B's
  backlog, frontend already flags it in the Checkout UI, just noting it
  here so it doesn't get lost.
- Whether shelving (item flipping to `status: "shelved"`) is automatic
  once the accuracy threshold clears, or needs a manual staff-confirm
  step — flagged as an open question in `BillBro_TeamUpdates.md` itself,
  between Person A and Person B.
