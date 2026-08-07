# BillBro Frontend Integration Guide

## Overview
This guide explains how to connect Person C's React/Streamlit frontend to your FastAPI backend, and how to integrate everything into the complete BillBro project.

---

## Part 1: API Server Setup (Person A - You)

### Your API is already ready!

**Backend Location:** `C:\Users\Admin\Desktop\BE Project\`

**API Server Details:**
- **Host:** `http://localhost:8000` (for local development)
- **Production:** Will be deployed to a server (e.g., AWS, Heroku, Azure)
- **API Docs:** `http://localhost:8000/docs` (interactive Swagger UI)

**To start your API:**
```bash
cd C:\Users\Admin\Desktop\BE Project
python api_app.py
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete
```

---

## Part 2: React Frontend Integration (Person C)

### What Person C needs to do:

**1. Create React app (if not already done):**
```bash
npx create-react-app billbro-frontend
cd billbro-frontend
```

**2. Install dependencies for API communication:**
```bash
npm install axios react-router-dom
```

**3. Create API client file** - `src/api/client.js`:
```javascript
import axios from 'axios';

// Configure API base URL
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Items endpoints
export const getItems = (storeId = 'store_001') => 
  api.get(`/items?store_id=${storeId}`);

export const getItem = (itemId) => 
  api.get(`/items/${itemId}`);

export const createItem = (itemData) => 
  api.post('/items', itemData);

// Inventory endpoints
export const getInventory = (storeId = 'store_001') => 
  api.get(`/inventory?store_id=${storeId}`);

export const decrementInventory = (itemId, quantity = 1, reason = 'billed') => 
  api.patch(`/inventory/${itemId}`, { quantity, reason });

// Alerts endpoints
export const getAlerts = (storeId = 'store_001', resolved = false) => 
  api.get(`/alerts?store_id=${storeId}&resolved=${resolved}`);

export const resolveAlert = (alertId) => 
  api.patch(`/alerts/${alertId}`);

// Checkout endpoint
export const processCheckout = (detections, storeId = 'store_001') => 
  api.post('/checkout/bill', { detections, store_id: storeId });

// Models endpoint
export const getActiveModel = (storeId = 'store_001') => 
  api.get(`/models/active?store_id=${storeId}`);

// Health check
export const healthCheck = () => 
  api.get('/health');

export default api;
```

**4. Create environment file** - `.env`:
```
REACT_APP_API_URL=http://localhost:8000
```

**5. Use API in React components** - Example component:
```javascript
import { useState, useEffect } from 'react';
import { getInventory, decrementInventory, getAlerts } from '../api/client';

function InventoryDashboard() {
  const [inventory, setInventory] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const invResponse = await getInventory();
      const alertsResponse = await getAlerts();
      
      setInventory(invResponse.data);
      setAlerts(alertsResponse.data);
    } catch (error) {
      console.error('Failed to load data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDecrement = async (itemId) => {
    try {
      await decrementInventory(itemId, 1, 'manual');
      loadData(); // Refresh data
    } catch (error) {
      console.error('Failed to decrement inventory:', error);
    }
  };

  if (loading) return <div>Loading...</div>;

  return (
    <div>
      <h1>Inventory Dashboard</h1>
      
      <section>
        <h2>Active Alerts ({alerts.length})</h2>
        {alerts.map(alert => (
          <div key={alert.id} className={`alert ${alert.severity}`}>
            <p>{alert.item_name}: {alert.message}</p>
          </div>
        ))}
      </section>

      <section>
        <h2>Stock Levels</h2>
        <table>
          <thead>
            <tr>
              <th>Item</th>
              <th>Count</th>
              <th>Status</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {inventory.map(item => (
              <tr key={item.id}>
                <td>{item.name}</td>
                <td>{item.current_count}</td>
                <td>{item.status}</td>
                <td>
                  <button onClick={() => handleDecrement(item.id)}>
                    Decrement
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}

export default InventoryDashboard;
```

**6. Start React dev server:**
```bash
npm start
```

Your React app will run on `http://localhost:3000`

---

## Part 3: CORS Configuration (Critical!)

### Problem:
React frontend (port 3000) cannot call backend API (port 8000) due to CORS restrictions.

### Solution:
Add CORS middleware to your FastAPI app. Update your `api_app.py`:

```python
from fastapi.middleware.cors import CORSMiddleware

# Add this after creating the FastAPI app
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",      # React dev server
        "http://localhost:8000",      # Your API docs
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    expose_headers=["*"],
    allow_headers=["*"],
)
```

For production, change `allow_origins` to your actual domain:
```python
allow_origins=[
    "https://billbro.yourcompany.com",
    "https://app.billbro.yourcompany.com",
]
```

---

## Part 4: Project Structure

Your complete project should look like this:

```
billbro/
├── backend/                        # Person A's work (you)
│   ├── billbro_mvp.db
│   ├── api_app.py                  # Main API server
│   ├── database.py                 # SQLAlchemy models
│   ├── requirements-minimal.txt
│   ├── billbro_database_schema.sql
│   ├── billbro_sample_data.sql
│   └── tests/
│       └── test_database.py
│
├── frontend/                       # Person C's work
│   ├── src/
│   │   ├── api/
│   │   │   └── client.js           # API calls
│   │   ├── components/
│   │   │   ├── InventoryDashboard.js
│   │   │   ├── CheckoutFlow.js
│   │   │   ├── AlertsPanel.js
│   │   │   └── AdminPanel.js
│   │   ├── App.js
│   │   └── index.js
│   ├── .env
│   ├── package.json
│   └── public/
│
├── ml/                             # Person B's work
│   ├── billbro_v3.onnx            # Base model
│   ├── training.py
│   ├── predict.py
│   └── models/
│       └── store_001_v1.pt
│
└── docs/
    ├── README.md
    ├── API_SPEC.md
    ├── ARCHITECTURE.md
    └── DEPLOYMENT.md
```

---

## Part 5: Running the Full Stack

### Terminal 1 - Backend API:
```bash
cd backend
python api_app.py
# Output: INFO:     Uvicorn running on http://127.0.0.1:8000
```

### Terminal 2 - Frontend:
```bash
cd frontend
npm start
# Output: Compiled successfully! On http://localhost:3000
```

### Terminal 3 - (Future) ML Training Service:
```bash
cd ml
python training_service.py
```

Now you have:
- ✅ Backend API: http://localhost:8000
- ✅ API Docs: http://localhost:8000/docs
- ✅ React Frontend: http://localhost:3000
- ✅ Database: SQLite at `backend/billbro_mvp.db`

---

## Part 6: Data Flow

### Example: Checkout Process

```
1. Person C's Frontend (React)
   └─→ User taps "Complete Bill" button
   
2. React calls your API:
   POST http://localhost:8000/checkout/bill
   {
     "detections": [
       {"item_name": "apple", "confidence": 0.95, "quantity": 2},
       {"item_name": "diet_coke", "confidence": 0.92, "quantity": 1}
     ]
   }

3. Your Backend API (FastAPI)
   └─→ Processes request
   └─→ Decrements inventory in SQLite
   └─→ Checks for alerts
   └─→ Creates transaction record
   └─→ Returns response:
   {
     "status": "success",
     "receipt_id": "RCP_20260807_123456",
     "cart": [...],
     "total": 120.00,
     "alerts": [...]
   }

4. React receives response
   └─→ Displays receipt
   └─→ Shows any alerts
   └─→ Updates inventory UI
```

---

## Part 7: Communication Between Team Members

### Person A (You - Backend):
- ✅ Build APIs
- ✅ Manage database
- ✅ Handle inventory logic
- ✅ Trigger alerts
- **Tell Person C:** "Here are my API endpoints with examples"

### Person B (ML):
- Convert ONNX model to PyTorch
- Implement training pipeline
- **Tell Person A:** "Fine-tuning takes ~15 min, here's the format for training results"
- **Tell Person C:** "Here's the detection output format"

### Person C (Frontend):
- Build React UI
- Call your API endpoints
- Display data
- **Tell Person A:** "I need these endpoints with these response formats"
- **Tell Person B:** "Can you provide detection output in this format?"

---

## Part 8: Environment Variables

### Development (.env):
```
REACT_APP_API_URL=http://localhost:8000
REACT_APP_ENV=development
```

### Production (.env.production):
```
REACT_APP_API_URL=https://api.billbro.yourcompany.com
REACT_APP_ENV=production
```

---

## Part 9: Testing Integration

### 1. Test Backend API directly:
```bash
# In browser or with curl
http://localhost:8000/docs
```

### 2. Test from React:
```javascript
// In React component or console
import { getItems } from './api/client';

getItems().then(response => {
  console.log('Items:', response.data);
}).catch(error => {
  console.error('Error:', error);
});
```

### 3. Test with curl:
```bash
curl http://localhost:8000/items
curl http://localhost:8000/inventory
curl http://localhost:8000/health
```

---

## Part 10: Deployment (Later)

When ready to deploy:

1. **Backend (Person A):**
   - Deploy to Heroku/AWS/Azure
   - Update database to PostgreSQL
   - Set environment variables

2. **Frontend (Person C):**
   - Build: `npm run build`
   - Deploy to Vercel/Netlify
   - Update `REACT_APP_API_URL` to production API

3. **Database:**
   - Migrate from SQLite to PostgreSQL
   - Set up backups

---

## Checklist

- [ ] Person A: API running on http://localhost:8000
- [ ] Person A: CORS middleware added
- [ ] Person C: React app created
- [ ] Person C: API client file created
- [ ] Person C: Environment variables configured
- [ ] Person C: React calling backend APIs
- [ ] Person B: Detection format documented
- [ ] Team: All 3 services running locally
- [ ] Team: Test full checkout flow end-to-end

---

## Questions to Answer Together

**Person A → Person C:**
- "Which endpoints do you need first?"
- "What response format works best for your UI?"
- "What error handling do you need?"

**Person C → Person A:**
- "Can you add pagination to /items?"
- "Can you add search/filter to /inventory?"
- "Should alerts auto-refresh or poll?"

**Person B → Everyone:**
- "When will the training endpoint be ready?"
- "What's the detection confidence threshold?"
- "How often should we retrain?"

---

**Next Steps:**
1. Share this guide with Person C
2. Agree on API response formats
3. Start building React components
4. Test end-to-end integration
5. Deploy to production when ready

Good luck! 🚀
