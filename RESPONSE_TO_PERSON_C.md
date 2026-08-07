# Response to Person C's Feedback - COMPLETED

Hi Person C! I've addressed your 4 questions. Here's what's resolved and what's pending:

---

## ✅ Item 1: CORS - RESOLVED

**Status:** Configured in `api_app.py`

Your Vite dev server on `localhost:5173` is now allowed to call the API. Should work without CORS errors now!

---

## ❓ Item 2: Detection Endpoint - DECISION PENDING

**Status:** Waiting on Person B + decision from you & Person A

Right now, Person A is deciding between:
- **Option A:** Backend has `/detect` endpoint (Person A integrates Person B's model)
- **Option B:** Frontend calls Person B's model directly

**What to do:** Check with Person A this week for the decision and timeline.

**For now:** I've updated `FOR_PERSON_C.md` with a placeholder explaining both options.

---

## ✅ Item 3: Endpoint Clarifications - RESOLVED

I've now documented **exactly** what each endpoint returns:

### GET /inventory vs GET /items

**GET /items** - Product Catalog
```json
[
  {
    "id": 1,
    "name": "Apple",
    "sku": "APL001",
    "price": 35.00,
    "category": "fruits",
    "low_stock_threshold": 5
  }
]
```
**Use for:** Product lookups, dropdowns, searching products

**GET /inventory** - Stock Levels
```json
[
  {
    "id": 1,
    "name": "Apple",
    "current_count": 47,
    "status": "OK"  // "OK" | "LOW_STOCK" | "OUT_OF_STOCK"
  }
]
```
**Use for:** Inventory Dashboard, showing what's in stock

### PATCH /alerts/{id} - Resolve Alert

**Request:**
```
PATCH http://localhost:8000/alerts/1
```
**No request body needed** - just call it directly.

**Response:**
```json
{
  "status": "success",
  "alert": { ... }
}
```

---

## ✅ Item 4: Future Endpoints - DOCUMENTED

I've noted these for later weeks:

- **Week 4:** Training image upload endpoints
- **Week 7:** Bulk CSV import + settings
- **Week 8:** Model version history + rollback

Not urgent now, just flagged so Person A knows what's coming.

---

## 📝 Updated Documentation

Everything is now in `FOR_PERSON_C.md`:
- ✅ Clear response examples for each endpoint
- ✅ Explanation of when to use which endpoint
- ✅ Detection endpoint placeholder with options
- ✅ All endpoint shapes documented

---

## Summary Table

| Item | Status | Notes |
|------|--------|-------|
| 1. CORS | ✅ DONE | Configured for `localhost:5173` |
| 2. Detection Endpoint | ⏳ PENDING | Awaiting Person A & Person B decision |
| 3. `/items` vs `/inventory` | ✅ DONE | Fully documented with examples |
| 3b. `/alerts/{id}` | ✅ DONE | No request body needed |
| 4. Future endpoints | ✅ NOTED | Flagged in backlog |

---

## What's Ready to Test

You can now use these endpoints with full confidence:

✅ GET /items
✅ GET /inventory
✅ GET /alerts
✅ PATCH /alerts/{id}
✅ PATCH /inventory/{id}

Just wait on `/checkout/bill` until detection endpoint is decided.

---

## Next Steps

1. **This week:** Person A confirms detection endpoint with Person B
2. **Next week:** Detection endpoint ready OR alternative decided
3. **Then:** You can finish the checkout flow

Reach out if you have other questions!
