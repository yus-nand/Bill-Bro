# BillBro Backend - Smart Inventory System

## Project Overview

BillBro is an AI-powered grocery checkout + smart inventory system. This repository contains the **backend** code for database management, API endpoints, and inventory operations.

**Role:** Backend Lead (Person A)  
**Timeline:** 12 weeks (Weeks 1-2: Foundation Phase)  
**Tech Stack:** FastAPI, SQLAlchemy, SQLite (MVP) → PostgreSQL (Production), YOLOv8

---

## 📁 Repository Structure

```
BE Project/
├── billbro_mvp.db                      # SQLite database (created by TablePlus)
├── billbro_database_schema.sql         # Database schema (7 tables + indexes + views)
├── billbro_sample_data.sql             # Sample data for testing
│
├── database.py                         # SQLAlchemy ORM models
├── api_app.py                          # FastAPI application (9 endpoints)
├── test_database.py                    # Unit tests (40+ test cases)
│
├── requirements.txt                    # Python dependencies
├── QUICK_START.md                      # Getting started guide
├── TABLEPLUS_SETUP_GUIDE.md            # Database setup instructions
├── README.md                           # This file
│
└── [Future] api/
    ├── app.py                          # Main API (restructured)
    └── routes/
        ├── items.py
        ├── inventory.py
        ├── alerts.py
        ├── checkout.py
        └── training.py
```

---

## 🚀 Quick Start

### 1. Setup Database in TablePlus
```bash
# Follow TABLEPLUS_SETUP_GUIDE.md
1. Open TablePlus
2. Create SQLite database: billbro_mvp.db
3. Import schema: billbro_database_schema.sql
4. Load sample data: billbro_sample_data.sql
```

### 2. Setup Python Environment
```bash
cd C:\Users\Admin\Desktop\BE Project
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Run API
```bash
python api_app.py
```

Visit: http://127.0.0.1:8000/docs for interactive API docs

---

## 📊 Database Schema

### Tables (7 total)

#### 1. **items** - Product Information
```sql
id, store_id, name, sku, price, category, expiry_date, low_stock_threshold, created_at, updated_at
```
- Base model items: apple, banana, dragon fruit, custard apple, diet coke, pepsi

#### 2. **inventory** - Current Stock Levels
```sql
id, item_id, current_count, last_updated
```
- One record per item
- Tracks real-time stock

#### 3. **alerts** - Inventory & Expiry Alerts
```sql
id, store_id, item_id, alert_type, severity, message, resolved, created_at, resolved_at
```
- Types: `STOCK_OUT`, `LOW_STOCK`, `EXPIRY`
- Severity: `critical`, `warning`

#### 4. **training_data** - Model Training Images
```sql
id, item_id, image_path, bbox_coordinates, labeled_by, created_at
```
- Stores images captured for training new items
- Auto-labeled by base model

#### 5. **model_versions** - Model Deployment History
```sql
id, store_id, version, model_path, metrics, is_active, trained_at, deployed_at, created_at
```
- Tracks all model versions per store
- Only one `is_active=1` per store

#### 6. **transactions** - Checkout History
```sql
id, store_id, receipt_id, total_amount, items_json, status, created_at
```
- Logs all checkout transactions
- Item details stored as JSON

#### 7. **training_jobs** - Async Training Job Tracking
```sql
id, item_id, store_id, status, progress, current_epoch, total_epochs, accuracy, error_message, model_version, created_at, completed_at
```
- Tracks background training jobs
- Status: `pending`, `running`, `success`, `failed`

### Views (3 total)
- `active_alerts` - Unresolved alerts with item details
- `inventory_status` - Stock levels with alert status
- `active_models` - Currently deployed models

---

## 🔌 API Endpoints (9 total)

### Items Management
```
GET    /items                    # List all items
GET    /items/{item_id}          # Get single item
POST   /items                    # Create new item
```

### Inventory Management
```
GET    /inventory                # Get stock levels
PATCH  /inventory/{item_id}      # Decrement stock (checkout)
```

### Alerts
```
GET    /alerts                   # Get active alerts
PATCH  /alerts/{alert_id}        # Resolve alert
```

### Checkout
```
POST   /checkout/bill            # Process checkout (decrement + alerts)
```

### Models
```
GET    /models/active            # Get active model info
```

### System
```
GET    /health                   # Health check
```

---

## 📝 Example API Requests

### Create Item
```bash
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

### Get Inventory
```bash
GET /inventory
Response: [
    {
        "id": 1,
        "name": "Apple",
        "sku": "APL001",
        "price": 35.00,
        "current_count": 47,
        "low_stock_threshold": 5,
        "status": "OK"
    },
    ...
]
```

### Process Checkout
```bash
POST /checkout/bill
{
    "detections": [
        {
            "item_name": "Apple",
            "confidence": 0.95,
            "quantity": 2
        },
        {
            "item_name": "Diet Coke",
            "confidence": 0.92,
            "quantity": 1
        }
    ]
}

Response: {
    "status": "success",
    "receipt_id": "RCP_20260807_123456",
    "cart": [...],
    "total": 120.00,
    "alerts": []
}
```

### Get Alerts
```bash
GET /alerts
Response: [
    {
        "id": 1,
        "alert_type": "LOW_STOCK",
        "severity": "warning",
        "message": "Banana stock low: 3 units",
        "item_name": "Banana",
        "resolved": false
    }
]
```

---

## 🧪 Testing

### Run All Tests
```bash
pytest test_database.py -v
```

### Test Coverage
- 40+ unit tests covering:
  - Model creation
  - Inventory operations (decrement, constraints)
  - Alert triggering
  - Transaction logging
  - Training job tracking
  - Integration workflows (checkout, low stock alerts)

### Key Test Cases
- ✅ Create items with unique SKU
- ✅ Decrement inventory without going negative
- ✅ Trigger alerts on low stock / stock out
- ✅ Create and resolve alerts
- ✅ Process complete checkout workflow
- ✅ Track training job progress

---

## 🔄 Key Workflows

### Checkout Flow
```
1. Customer puts items on counter
2. Camera captures image
3. YOLOv8 detects items + confidence scores
4. Staff confirms detections
5. Click "Complete Bill" → POST /checkout/bill
6. Backend:
   - Decrements inventory for each item
   - Checks stock levels vs thresholds
   - Triggers LOW_STOCK / STOCK_OUT alerts
   - Creates transaction receipt
7. Frontend displays receipt + any alerts
```

### Add New Item Flow
```
1. Store manager: "We have new item"
2. Staff captures 15 images (different angles)
3. POST /training/upload_images
4. Backend:
   - Auto-labels images using base model (2 min)
   - Stores labeled dataset
   - Starts async training job
5. Frontend polls GET /training/job/{job_id}
6. After training (15 min):
   - If accuracy ≥ 80%: Deploy new model
   - If accuracy < 80%: Ask for more images
7. Next checkout: Detect new item
```

### Alert Triggering
```
When inventory.current_count < low_stock_threshold:
  - Create LOW_STOCK alert
  - Display to staff

When inventory.current_count == 0:
  - Create STOCK_OUT alert (critical)
  - Display prominently

When expiry_date == today:
  - Create EXPIRY alert
```

---

## 🛠️ Development Checklist

### Week 1-2: Foundation ✅
- [x] Database schema created (7 tables)
- [x] SQLAlchemy models implemented
- [x] FastAPI app with 9 endpoints
- [x] Sample data loaded
- [x] Unit tests (40+ cases)
- [x] API documentation (Swagger)

### Week 3-5: Core Features (Next)
- [ ] Implement async training jobs (Person B)
- [ ] Inventory decrement logic (alert triggering)
- [ ] Connect to Streamlit frontend (Person C)
- [ ] Integration tests
- [ ] Error handling + validation

### Week 6-8: Polish
- [ ] Performance optimization
- [ ] PostgreSQL migration
- [ ] Admin dashboards
- [ ] Monitoring + logging
- [ ] Full test coverage (80%+)

### Week 9-12: Pilot & Production
- [ ] Real-world testing
- [ ] Production deployment
- [ ] Performance monitoring
- [ ] Model retraining

---

## 🤝 Team Communication

### To Person B (ML/Training):
```
Database and API ready for integration.

Needed from you:
1. Model version saved to: models/{store_id}_v1.pt
2. Metrics object: {"mAP50": ..., "mAP": ..., "accuracy": ...}
3. Training job status format (for progress polling)

When ready:
1. Call POST /training/upload_images with images
2. I'll create training_jobs record
3. You update progress via UPDATE training_jobs
4. When done, insert ModelVersion and set is_active=1
```

### To Person C (Frontend/Streamlit):
```
API endpoints ready. Here's what you need:

For Checkout Tab:
- POST /checkout/bill → Process detection
- GET /alerts → Show active alerts
- PATCH /alerts/{id} → Resolve alerts

For Inventory Dashboard:
- GET /inventory → Show all stock levels
- GET /items → Search products

For Admin Panel:
- POST /items → Add new items
- GET /models/active → Show current model

Full API docs: http://localhost:8000/docs
```

---

## 📚 Resources

### Documentation
- **FastAPI:** https://fastapi.tiangolo.com/
- **SQLAlchemy:** https://docs.sqlalchemy.org/
- **SQLite:** https://www.sqlite.org/docs.html
- **TablePlus:** https://tableplus.com/blog

### Project
- **Git Workflow:** Feature branches (feat/a/database-schema)
- **Code Standards:** Python 3.10+, PEP 8, type hints, tests
- **Merge Process:** 2 approvals → merge to develop

---

## ⚠️ Common Issues & Solutions

### "Database is locked"
Close other connections, restart API

### "Foreign key constraint error"
Ensure parent record exists before child (item before inventory)

### "Port 8000 already in use"
Kill process: `netstat -ano | findstr :8000` → `taskkill /PID <PID> /F`

### "Module not found"
Activate venv: `venv\Scripts\activate` → `pip install -r requirements.txt`

---

## 🎯 Success Criteria (Week 8 MVP)

✅ Database schema complete (7 tables)  
✅ API endpoints working (9 total)  
✅ Checkout flow end-to-end  
✅ Inventory decrements on bill  
✅ Alerts trigger on low stock / stock out  
✅ Unit tests passing (40+ cases)  
✅ API docs auto-generated  
✅ Sample data for testing  

---

## 📞 Support

**Stuck for >30 min?** Post in Slack immediately.

**Design decision?** Create GitHub issue or sync during Wednesday check-in.

**Merge conflict?** Resolve together in quick call.

---

## 📄 License

Internal project - BillBro Team Only

---

**Last Updated:** August 2026  
**Status:** Week 1-2 Foundation Phase ✅ Complete  
**Next Phase:** Week 3-5 Core Features (In Progress)

Good luck! 🚀
