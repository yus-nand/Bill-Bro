# BillBro — API Contract

**Status: fully reconciled with Person A's real API** as of
`RESPONSE_TO_PERSON_C_FINAL.md` / `FINAL_STATUS_WEEK_1.md`. Backend is
FastAPI at `localhost:8000`, docs at `/docs`, SQLite-backed, 9 endpoints
live plus `/detect` landing this week.

`frontend/src/api.js` mirrors this — confirmed calls at the top,
proposed/unbuilt ones (Weeks 4/7/8) below a clear divider.

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
| 8 | `POST /detect` | ✅ Confirmed — Option A decided | Checkout — **Integrated** |
| 9 | `POST /checkout/bill` | ✅ Confirmed | Checkout — **Integrated** |
| 10 | `GET /models/active` | ✅ Confirmed, full shape | Models (not built yet) |
| 11 | `GET /health` | ✅ Confirmed, full shape | not called yet |
| 12 | `POST /admin/import_csv`, settings | ❌ Not built (Week 7) | Admin |
| 13 | `POST /training/upload_images`, job status | ❌ Not built (Weeks 2-3) | Add Item |
| 14 | `GET /models`, activate/rollback | ❌ Not built (Week 8) | Models |
| 15 | `GET/PUT /prices` | Unnecessary | `GET /items` already returns `price` |

**No open blockers left for Checkout, Inventory, or Alerts.** Add Item,
Admin, and the fuller Models page are waiting on endpoints Person A hasn't
built yet (by design — those are later weeks).

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
  "category": "snacks", "expiry_date": "2026-12-31", "low_stock_threshold": 5 }
// Response
{ "status": "success", "item_id": 7, "item": { "...": "full item object" } }
```
`name`, `sku`, `price` required. `category`, `expiry_date` optional.
`low_stock_threshold` defaults to 5.

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

## Resolved — no longer open

- ~~Detection endpoint (Option A vs B)~~ — **Option A**, `POST /detect`,
  live in Checkout now.
- ~~CORS~~ — configured for `localhost:5173`. Still need the production
  origin once nginx is actually deployed somewhere.
- ~~`/inventory` vs `/items`~~ — documented (with one lingering
  inconsistency noted above).
- ~~`PATCH /alerts/{id}` body~~ — none needed.
- ~~`POST /items` body~~ — documented above.
- ~~`GET /models/active` / `GET /health` shapes~~ — documented above.

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
- Admin, training/add-item, and fuller model-management endpoints — not
  built yet (Weeks 2-3, 7, 8 respectively, per his own timeline).
