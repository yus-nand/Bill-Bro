# Final Response to Person C - All Questions Answered

Hi Person C! I've read your latest feedback. Here are **all remaining clarifications**:

---

## 🎯 BLOCKING ISSUE: Detection Endpoint Decision

**Status:** DECIDED - Going with **Option A**

**Your Backend Gets:**
```
POST /detect
Input: { "image": "base64_string" }
Output: Raw per-instance detections
```

**Response Format (Raw detections):**
```json
{
  "detections": [
    {
      "item_name": "apple",
      "confidence": 0.95,
      "bbox": [100, 50, 200, 150]  // x1, y1, x2, y2
    },
    {
      "item_name": "diet_coke",
      "confidence": 0.92,
      "bbox": [250, 75, 350, 225]
    }
  ],
  "processing_time_ms": 45
}
```

**Who Does Aggregation:**
- **Frontend** receives raw detections
- **Frontend** aggregates into `{item_name, confidence, quantity}` format
- **Frontend** sends aggregated to `/checkout/bill`

**Why This Split:**
- Frontend already has the UI for staff to adjust quantities
- Cleaner separation: detection vs checkout logic
- Frontend can show "2x apple + 1x diet_coke" to user before billing

**Example Workflow:**
```
1. Frontend calls POST /detect with image
   ↓ Gets back: [{apple, 0.95, bbox}, {diet_coke, 0.92, bbox}]

2. Frontend shows staff: "Detected: apple (95%), diet_coke (92%)"
   ↓ Staff can adjust quantities: apple x2, diet_coke x1

3. Frontend calls POST /checkout/bill with:
   {
     "detections": [
       {"item_name": "apple", "confidence": 0.95, "quantity": 2},
       {"item_name": "diet_coke", "confidence": 0.92, "quantity": 1}
     ]
   }
```

---

## ✅ CLARIFIED: POST /items Request Body

**Shape for creating an item:**

```json
POST /items
{
  "name": "Maggi Noodles",
  "sku": "MAG001",
  "price": 15.00,
  "category": "snacks",
  "expiry_date": "2026-12-31",
  "low_stock_threshold": 5
}
```

**Response:**
```json
{
  "status": "success",
  "item_id": 7,
  "item": {
    "id": 7,
    "name": "Maggi Noodles",
    "sku": "MAG001",
    "price": 15.00,
    "category": "snacks",
    "low_stock_threshold": 5,
    "expiry_date": "2026-12-31",
    "created_at": "2026-08-07T18:00:00"
  }
}
```

**Notes:**
- `name` and `sku` are required
- `price` is required
- `category`, `expiry_date` are optional
- `low_stock_threshold` defaults to 5 if not provided
- Returns the created item object

---

## ✅ CLARIFIED: GET /models/active Response

```json
GET /models/active

{
  "id": 1,
  "store_id": "store_001",
  "version": "v1",
  "model_path": "models/store_001_v1.pt",
  "metrics": {
    "mAP50": 0.92,
    "mAP": 0.87,
    "accuracy": 0.90
  },
  "is_active": true,
  "trained_at": "2026-08-07T09:00:00",
  "deployed_at": "2026-08-07T09:20:00",
  "created_at": "2026-08-07T09:00:00"
}
```

**Use for:** Displaying current model version in UI

---

## ✅ CLARIFIED: GET /health Response

```json
GET /health

{
  "status": "healthy",
  "timestamp": "2026-08-07T18:15:30",
  "version": "1.0.0",
  "database": "connected",
  "uptime_seconds": 3600
}
```

**Use for:** Health checks, monitoring, debugging

---

## 📚 FRONTEND_INTEGRATION_GUIDE.md

**Location:** `C:\Users\Admin\Desktop\BE Project\FRONTEND_INTEGRATION_GUIDE.md`

**Content includes:**
- Full React setup guide
- API client implementation
- CORS configuration
- Project structure
- Data flow examples
- Deployment steps

**Key sections for you:**
- Part 2: React Frontend Integration (has the axios client code)
- Part 5: Running the Full Stack (how to start everything)

---

## 📝 COMPLETE API REFERENCE

Here's every endpoint with full specs:

### Items Management

**GET /items**
```
Query params: store_id (default: "store_001")
Response: List of items with current_count
Use for: Product catalog, search, inventory page
```

**GET /items/{item_id}**
```
Response: Single item object
Use for: Product detail page
```

**POST /items**
```
Body: {name, sku, price, category?, expiry_date?, low_stock_threshold?}
Response: {status, item_id, item}
Use for: Add Item page (after training completes)
```

### Inventory Management

**GET /inventory**
```
Query params: store_id (default: "store_001")
Response: List of {id, name, sku, price, current_count, status}
Use for: Inventory Dashboard (LIVE - already using this)
```

**PATCH /inventory/{item_id}**
```
Body: {quantity, reason}
Response: {status, item_name, new_count, old_count, alerts}
Use for: Manual inventory adjustments
```

### Alerts

**GET /alerts**
```
Query params: store_id, resolved (default: false)
Response: List of active alerts with {id, alert_type, severity, message, item_name}
Use for: Alerts page (LIVE - already using this)
```

**PATCH /alerts/{id}**
```
No body needed
Response: {status, alert}
Use for: Resolve alert action (LIVE - already using this)
```

### Detection

**POST /detect**
```
Body: {image: "base64_string", confidence_threshold?: 0.7}
Response: {detections, processing_time_ms}
Use for: Checkout flow (YOUR DECISION - Option A: backend endpoint)
```

### Checkout

**POST /checkout/bill**
```
Body: {detections: [{item_name, confidence, quantity}, ...]}
Response: {status, receipt_id, cart, total, alerts}
Use for: Complete bill + trigger inventory decrement + alerts
```

### Models

**GET /models/active**
```
Response: Current active model with metrics
Use for: Display current model version in UI
```

### Health

**GET /health**
```
Response: {status, timestamp, version, database, uptime_seconds}
Use for: Monitoring + debugging
```

---

## 🎯 What's Working Right Now (LIVE)

✅ Inventory page (using `/inventory`)
✅ Alerts page (using `/alerts`)  
✅ Resolve alert action (using `PATCH /alerts/{id}`)
✅ CORS configured for `localhost:5173`

---

## ⏳ What's Blocked (Waiting on Decision)

⏳ Checkout page (waiting on `/detect` endpoint)

---

## 📅 Future Endpoints (Weeks 4, 7, 8)

Not needed yet, but noted for planning:

**Week 4 - Add New Item Workflow:**
- `POST /training/upload_images` - upload 15 images
- `GET /training/job/{job_id}` - poll training progress

**Week 7 - Admin Panel:**
- `POST /admin/import_csv` - bulk upload items
- `GET /admin/settings` / `POST /admin/settings` - store settings

**Week 8 - Models Dashboard:**
- `GET /models` - list all versions
- `POST /models/{id}/activate` - switch active model
- `POST /models/{id}/rollback` - revert to previous

---

## 🚀 Next Steps for You

1. **Checkout Page:** Can now proceed with `/detect` endpoint (Option A)
   - Send image to `POST /detect`
   - Frontend aggregates detections
   - Send to `POST /checkout/bill`

2. **Add Item Page:** Waiting on Person B + Person A Week 2 endpoints
   - Will need `/training/upload_images` + `/training/job/{id}`

3. **Admin Page:** Waiting on Week 7
   - Will need `/admin/import_csv` + settings endpoints

4. **Models Dashboard:** Waiting on Week 8
   - Will need full `/models` endpoints

---

## Summary Table

| Page | Status | Blocking On | Timeline |
|------|--------|-------------|----------|
| Checkout | ⏳ Blocked | `/detect` endpoint | Week 1 |
| Inventory | ✅ Live | Nothing | Ready now |
| Alerts | ✅ Live | Nothing | Ready now |
| Add Item | ⏳ Blocked | Training endpoints | Week 2-3 |
| Admin | ⏳ Blocked | CSV endpoints | Week 7 |
| Models | ⏳ Blocked | Model endpoints | Week 8 |

---

## Questions?

- Detection endpoint format good to go?
- POST /items body shape correct?
- Need any other response shapes clarified?
- Ready to wire up Checkout once `/detect` is ready?

Let me know and we can get you unblocked immediately!

---

**Status:** All remaining questions answered. Checkout can proceed once `/detect` endpoint is ready (this week).
