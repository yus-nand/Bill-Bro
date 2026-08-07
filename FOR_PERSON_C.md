# For Person C - Frontend Developer

Hi! This is what you need to know to connect your React/Streamlit frontend to Person A's backend API.

---

## Quick Start

### 1. Person A's API is running here:
- **URL:** `http://localhost:8000`
- **Docs:** `http://localhost:8000/docs` ← Try this first!

### 2. What you can do with it:

---

## 📊 Inventory Endpoints Explained

### GET /items - Product Catalog
Returns product information (what items exist, prices, etc.)

**Use this for:** Looking up product details, searching products, creating dropdowns

**Response:**
```json
[
  {
    "id": 1,
    "name": "Apple",
    "sku": "APL001",
    "price": 35.00,
    "category": "fruits",
    "low_stock_threshold": 5,
    "expiry_date": "2026-09-15",
    "created_at": "2026-08-07T10:00:00"
  }
]
```

### GET /inventory - Stock Levels + Status
Returns current stock counts and alert status for each item

**Use this for:** Inventory Dashboard, displaying stock levels, showing which items are low/out

**Response:**
```json
[
  {
    "id": 1,
    "name": "Apple",
    "sku": "APL001",
    "price": 35.00,
    "current_count": 47,
    "low_stock_threshold": 5,
    "status": "OK"  // "OK" | "LOW_STOCK" | "OUT_OF_STOCK"
  },
  {
    "id": 2,
    "name": "Banana",
    "sku": "BAN001",
    "price": 25.00,
    "current_count": 3,
    "low_stock_threshold": 10,
    "status": "LOW_STOCK"
  }
]
```

**Key difference:**
- `/items` = Product info (static, rarely changes)
- `/inventory` = Stock status (dynamic, changes with each sale)

---

### GET /alerts - Active Alerts
Returns all unresolved alerts (low stock, out of stock, expiry, etc.)

**Response:**
```json
[
  {
    "id": 1,
    "alert_type": "LOW_STOCK",
    "severity": "warning",
    "message": "Apple stock running low: 4 units",
    "item_name": "Apple",
    "resolved": false,
    "created_at": "2026-08-07T15:30:00"
  },
  {
    "id": 2,
    "alert_type": "OUT_OF_STOCK",
    "severity": "critical",
    "message": "Banana is out of stock",
    "item_name": "Banana",
    "resolved": false,
    "created_at": "2026-08-07T16:00:00"
  }
]
```

### PATCH /alerts/{id} - Resolve Alert
Mark an alert as resolved.

**Request:**
```
PATCH http://localhost:8000/alerts/1
```
No request body needed.

**Response:**
```json
{
  "status": "success",
  "alert": {
    "id": 1,
    "alert_type": "LOW_STOCK",
    "severity": "warning",
    "message": "Apple stock running low: 4 units",
    "item_name": "Apple",
    "resolved": true,
    "resolved_at": "2026-08-07T17:00:00"
  }
}
```

---

### POST /checkout/bill - Process Checkout
Process a checkout: decrement inventory, generate receipt, trigger alerts.

**Required:** Detection results first (see below)

**Request:**
```json
{
  "detections": [
    {"item_name": "apple", "confidence": 0.95, "quantity": 2},
    {"item_name": "diet_coke", "confidence": 0.92, "quantity": 1}
  ]
}
```

**Response:**
```json
{
  "status": "success",
  "receipt_id": "RCP_20260807_153000",
  "cart": [
    {
      "item_id": 1,
      "name": "Apple",
      "price": 35.00,
      "quantity": 2,
      "subtotal": 70.00,
      "confidence": 0.95
    }
  ],
  "total": 120.00,
  "alerts": []  // Any new alerts triggered
}
```

---

## 🚨 Detection Endpoint (COMING WEEK 3)

Checkout is blocked until you have detections. Person A is deciding how to get them:

**Option A:** Backend has `/detect` endpoint
- Frontend sends image → Your API → Person B's model → Get detections

**Option B:** Frontend calls Person B's model directly
- Frontend sends image → Person B's model service
- Frontend transforms response into detection format
- Frontend sends to `/checkout/bill`

**Status:** ✅ DECIDED - Option A (backend endpoint)

**Your API gets:**
```
POST /detect
Input: { "image": "base64_string" }
Output: Raw per-instance detections
```

**Response format:**
```json
{
  "detections": [
    {
      "item_name": "apple",
      "confidence": 0.95,
      "bbox": [100, 50, 200, 150]
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

**How to use:**
1. Call `/detect` with image
2. Frontend aggregates into `{item_name, confidence, quantity}` format
3. Send aggregated detections to `/checkout/bill`

---

**Decrement inventory:**
```
PATCH http://localhost:8000/inventory/1
{"quantity": 1, "reason": "billed"}
```

---

## Additional Endpoints

### POST /items - Create New Item

**Request:**
```json
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
    "category": "snacks"
  }
}
```

### GET /models/active - Current Model

**Response:**
```json
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
  "deployed_at": "2026-08-07T09:20:00"
}
```

### GET /health - Health Check

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-08-07T18:15:30",
  "version": "1.0.0",
  "database": "connected",
  "uptime_seconds": 3600
}
```

---

## For React Frontend

### Setup (2 minutes)

1. **Create API client file** - `src/api/client.js`:
```javascript
import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000',
  headers: {'Content-Type': 'application/json'},
});

export const getInventory = () => api.get('/inventory');
export const getItems = () => api.get('/items');
export const getAlerts = () => api.get('/alerts');
export const processCheckout = (detections) => 
  api.post('/checkout/bill', { detections });

export default api;
```

2. **Use in your component:**
```javascript
import { useState, useEffect } from 'react';
import { getInventory } from '../api/client';

function Dashboard() {
  const [inventory, setInventory] = useState([]);

  useEffect(() => {
    getInventory().then(res => setInventory(res.data));
  }, []);

  return <div>{inventory.map(item => ...)}</div>;
}
```

3. **Install axios:**
```bash
npm install axios
```

---

## For Streamlit Frontend

### Setup (3 minutes)

```python
import requests
import streamlit as st

API_URL = "http://localhost:8000"

# Get inventory
response = requests.get(f"{API_URL}/inventory")
inventory = response.json()

st.write("Inventory Status:")
st.dataframe(inventory)

# Get alerts
response = requests.get(f"{API_URL}/alerts")
alerts = response.json()

st.write("Active Alerts:")
for alert in alerts:
    st.warning(alert['message'])

# Process checkout
if st.button("Complete Bill"):
    detections = [
        {"item_name": "apple", "confidence": 0.95, "quantity": 2}
    ]
    response = requests.post(f"{API_URL}/checkout/bill", json={"detections": detections})
    receipt = response.json()
    st.write(receipt)
```

---

## All Available Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/items` | Get all items |
| GET | `/items/{id}` | Get specific item |
| POST | `/items` | Create new item |
| GET | `/inventory` | Get stock levels |
| PATCH | `/inventory/{id}` | Decrement stock |
| GET | `/alerts` | Get active alerts |
| PATCH | `/alerts/{id}` | Resolve alert |
| POST | `/checkout/bill` | Process checkout |
| GET | `/models/active` | Get current model |
| GET | `/health` | Check API health |

---

## Testing Without Frontend

### Use the API Docs (easiest way):
1. Go to: `http://localhost:8000/docs`
2. Click on any endpoint
3. Click "Try it out"
4. Enter values and click "Execute"

### Or use curl:
```bash
# Get inventory
curl http://localhost:8000/inventory

# Process checkout
curl -X POST http://localhost:8000/checkout/bill \
  -H "Content-Type: application/json" \
  -d '{"detections": [{"item_name": "apple", "confidence": 0.95, "quantity": 2}]}'
```

### Or use Postman:
1. Download Postman
2. Import API: `http://localhost:8000/openapi.json`
3. Test endpoints

---

## Common Response Formats

### Success Response:
```json
{
  "status": "success",
  "data": {...}
}
```

### Error Response:
```json
{
  "detail": "Item not found"
}
```

### Alert Object:
```json
{
  "id": 1,
  "alert_type": "LOW_STOCK",
  "severity": "warning",
  "message": "Apple stock running low: 4 units",
  "item_name": "Apple",
  "resolved": false,
  "created_at": "2026-08-07T15:30:00"
}
```

---

## Questions to Ask Person A

- "Can you add search/filter to /items?"
- "Can you add pagination to /inventory?"
- "What's the max file size for images in training?"
- "Should alerts auto-refresh or do I poll for them?"
- "Do you have rate limiting enabled?"

---

## Need Help?

1. Check API docs: `http://localhost:8000/docs`
2. Read the full guide: `FRONTEND_INTEGRATION_GUIDE.md`
3. Ask Person A for clarification on API format

Good luck with the frontend! 🚀
