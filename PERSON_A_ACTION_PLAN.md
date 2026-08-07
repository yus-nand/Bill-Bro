# Action Plan - Response to Person C's Feedback

## Status Summary

Person C has started building the frontend and found 4 critical gaps. Here's what you need to do:

---

## ✅ Item 1: CORS - FIXED

**Status:** Done
**What was needed:** Frontend runs on port 5173, API on 8000 → browser blocks cross-origin requests

**What I did:** Updated `api_app.py` to include:
```python
allow_origins=[
    "http://localhost:5173",  # Person C's Vite dev server
    "http://localhost:3000",  # If they switch to React
    ...
]
```

**Your action:** None! This is already live in your code.

---

## ⚠️ Item 2: Detection Endpoint - CRITICAL DECISION

**Status:** Blocked  
**What Person C needs:** A way to convert image → detections (item_name, confidence, quantity)

**The question:** 
- **Option A:** You add a `/detect` or `/predict` endpoint that wraps Person B's model
  - Frontend sends image → Your API → Person B's model → Returns detections
  - Frontend then sends detections to `/checkout/bill`
  - **Pros:** Cleaner API, everything goes through you
  - **Cons:** You need to integrate Person B's service

- **Option B:** Frontend calls Person B's model service directly
  - Frontend sends image → Person B's model (separate service)
  - Frontend aggregates response into detections shape
  - Frontend sends detections to `/checkout/bill`
  - **Pros:** Simpler for you (no new endpoint needed)
  - **Cons:** Frontend needs to know about Person B's service

**Action Required:**
1. **Discuss with Person B:** When will the model service be ready? What does it return?
2. **Decide:** Option A or B?
3. **Tell Person C:** In a message or update `FOR_PERSON_C.md`

**For now:** Add this placeholder to `FOR_PERSON_C.md`:
```markdown
### Detection Endpoint (Coming Week 3)

Checkout flow blocked until detection endpoint ready.
- Option: `/detect` endpoint (wraps Person B's model)
- Or: Frontend calls Person B's model directly
- Decision TBD with Person A & Person B
```

---

## ❓ Item 3: Clarify Two Endpoint Shapes

**Status:** Needs clarification

### 3a. `GET /inventory` vs `GET /items` - Are they different?

**What Person C is asking:**
In your `FOR_PERSON_C.md`, you list both endpoints but only show `/items` response example.

**Check your code:**
Your `api_app.py` has two different functions:
```python
@app.get("/items", tags=["Items"])
def get_items(...):  # Returns item info + current_count
    ...

@app.get("/inventory", tags=["Inventory"])
def get_inventory(...):  # Returns inventory status
    ...
```

**What should happen:**
- `GET /items` → Product catalog (name, price, SKU, etc.)
- `GET /inventory` → Current stock levels (current_count, status, alerts)

**Your action:**
1. Check what each endpoint actually returns (read your code)
2. Update `FOR_PERSON_C.md` with clear response examples for both
3. Tell Person C which one to use for the Inventory Dashboard

**Example response for Person C:**
```markdown
### GET /items - Product Catalog
Returns all products in the store.

Response:
```json
[
  {
    "id": 1,
    "name": "Apple",
    "sku": "APL001",
    "price": 35.00,
    "category": "fruits"
  }
]
```

### GET /inventory - Stock Levels
Returns current stock, not product info.

Response:
```json
[
  {
    "id": 1,
    "name": "Apple",
    "current_count": 47,
    "status": "OK",
    "low_stock_threshold": 5
  }
]
```

**Use this for:** Inventory Dashboard
```

### 3b. `PATCH /alerts/{id}` - Request body format

**What Person C is asking:**
When resolving an alert, what does the request body need?

**Current guess from Person C:**
```json
{"resolved": true}
```

**Your code currently:**
```python
@app.patch("/alerts/{alert_id}", tags=["Alerts"])
def resolve_alert(alert_id: int, db: Session = Depends(get_db)):
    """Resolve an alert"""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.resolved = True
    alert.resolved_at = datetime.utcnow()
    db.commit()
    return {"status": "success", "alert": alert.to_dict()}
```

**Issue:** Your endpoint doesn't accept a request body! It just sets `resolved=True`.

**Your action - Choose one:**

**Option 1:** Keep it simple (no request body needed)
```markdown
### PATCH /alerts/{id} - Resolve Alert

No request body needed. Just call it.

```bash
curl -X PATCH http://localhost:8000/alerts/1
```

Response:
```json
{
  "status": "success",
  "alert": { ... }
}
```
```

**Option 2:** Accept a request body for flexibility
```python
from pydantic import BaseModel

class AlertUpdate(BaseModel):
    resolved: bool = True
    notes: Optional[str] = None

@app.patch("/alerts/{alert_id}", tags=["Alerts"])
def resolve_alert(alert_id: int, data: AlertUpdate, db: Session = Depends(get_db)):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    alert.resolved = data.resolved
    if data.resolved:
        alert.resolved_at = datetime.utcnow()
    db.commit()
    return {"status": "success", "alert": alert.to_dict()}
```

**Recommendation:** Option 1 is simpler. Tell Person C:
```markdown
### PATCH /alerts/{id}

No request body. Call it directly:
```bash
PATCH /alerts/1
```
Returns the resolved alert.
```

---

## 📅 Item 4: Future Endpoints (Weeks 4, 7, 8)

**Status:** Not urgent, plan for later

### Week 4: Training Image Upload + Job Status
```
POST /training/upload_images
  - Takes images for new item
  - Creates training job
  - Returns job_id for polling

GET /training/job/{job_id}
  - Check training progress
  - Returns status, progress %, metrics
```

### Week 7: Bulk CSV Upload + Settings
```
POST /admin/import_csv
  - Takes CSV file
  - Bulk creates items + inventory

GET /admin/settings
POST /admin/settings
  - Store settings (thresholds, etc.)
```

### Week 8: Model Version History
```
GET /models
  - All model versions (not just active)

POST /models/{id}/activate
  - Switch to different model version

POST /models/{id}/rollback
  - Revert to previous version
```

**Action:** 
- Add these to your backlog
- Start Week 4: `/training/upload_images` and `/training/job/{job_id}`
- Don't need to build them now, just be aware

---

## Summary - What to Do This Week

### ✅ Done:
- [x] CORS middleware configured for `localhost:5173`

### ⚠️ Do This:
- [ ] **Decide with Person B:** Detection endpoint (Option A or B?)
- [ ] **Clarify & document:** `/items` vs `/inventory` response shapes
- [ ] **Clarify & document:** `/alerts/{id}` PATCH request body format
- [ ] **Update:** `FOR_PERSON_C.md` with final response shapes + detection plan
- [ ] **Message Person C:** "Here's what you need to know..."

### 📅 Plan Ahead (not urgent):
- Week 4: Training endpoints
- Week 7: Admin/CSV endpoints
- Week 8: Model version history

---

## How to Respond to Person C

Once you've made these decisions, update `FOR_PERSON_C.md` (or send a message to Person C) with:

```markdown
## Responses to Your Questions

### 1. CORS ✅
Configured in `api_app.py`. Uses `localhost:5173` for Vite dev server.

### 2. Detection Endpoint
[Your decision: Option A or B, and timeline]

### 3. Response Shapes

#### GET /inventory
Returns: [actual response example]
Use this for: Inventory Dashboard

#### GET /items
Returns: [actual response example]
Use this for: Product catalog lookups

#### PATCH /alerts/{id}
Request body: [format or "no body needed"]
Example: [curl command]

### 4. Future Endpoints
Week 4: Will add training endpoints
Week 7: Will add admin/CSV endpoints
Week 8: Will add model version history
```

---

## Questions for Your Standup

- **To Person B:** "When will detection/model service be ready? Can we integrate it into my API or should frontend call it directly?"
- **To Person C:** "Does this clarification help? Any other blockers?"
- **To yourself:** "Can I build detection endpoint by Week 3?"

Good luck! 🚀
