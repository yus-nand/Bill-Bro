# BillBro Backend - Quick Start Guide

## Overview
You're **Person A (Backend Lead)** for BillBro, an AI-powered grocery checkout + inventory system. This guide gets you started with database setup and API development.

**Timeline:** Weeks 1-2 (Foundation Phase)
**Goal:** Build database schema + CRUD endpoints

---

## 📁 Files Created for You

```
BE Project/
├── billbro_mvp.db                    ← Your SQLite database (created in TablePlus)
├── billbro_database_schema.sql       ← Database schema (7 tables + indexes)
├── billbro_sample_data.sql           ← Sample data for testing
├── database.py                       ← SQLAlchemy ORM models
├── requirements.txt                  ← Python dependencies
├── TABLEPLUS_SETUP_GUIDE.md          ← Step-by-step TablePlus setup
├── QUICK_START.md                    ← This file
└── [Future] api/app.py               ← FastAPI application
```

---

## 🚀 Step 1: Set Up Database in TablePlus

### 1a. Open TablePlus
1. Download & install [TablePlus](https://tableplus.com) (free trial available)
2. Launch TablePlus

### 1b. Create SQLite Database
1. Click **File** → **New** → **SQLite**
2. Choose location: `C:\Users\Admin\Desktop\BE Project\billbro_mvp.db`
3. Name: `billbro_mvp`
4. Click **Save**

### 1c. Import Schema
1. In TablePlus, open your `billbro_mvp` connection
2. Click **File** → **Import**
3. Select `billbro_database_schema.sql`
4. Click **Import** and wait for completion
5. Verify left sidebar shows all 7 tables:
   ```
   items
   inventory
   training_data
   model_versions
   alerts
   transactions
   training_jobs
   ```

### 1d. Load Sample Data
1. Click **File** → **Import**
2. Select `billbro_sample_data.sql`
3. Click **Import**
4. Verify data loaded:
   - **items**: 6 products (apple, banana, dragon fruit, custard apple, diet coke, pepsi)
   - **inventory**: Stock levels
   - **alerts**: 3 low-stock alerts
   - **transactions**: 3 sample receipts

✅ Database is ready!

---

## 🔧 Step 2: Set Up Python Environment

### 2a. Create Virtual Environment
```bash
cd C:\Users\Admin\Desktop\BE Project
python -m venv venv
venv\Scripts\activate  # Windows
```

### 2b. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2c. Verify SQLAlchemy Models
```python
python
>>> from database import Base, Item, Inventory, Alert
>>> print("Models loaded successfully!")
```

---

## 📝 Step 3: Create FastAPI Application

Create file: `C:\Users\Admin\Desktop\BE Project\api_app.py`

```python
"""
BillBro FastAPI Application
Main API server for inventory management
"""

from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime, date
from typing import List, Optional
import json
import os

from database import Base, Item, Inventory, Alert, ModelVersion, Transaction, TrainingJob

# ============================================================================
# Setup
# ============================================================================

DATABASE_URL = "sqlite:///billbro_mvp.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

app = FastAPI(
    title="BillBro API",
    description="Smart Inventory Management System",
    version="1.0.0"
)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================================
# ITEMS ENDPOINTS (Manage Products)
# ============================================================================

@app.get("/items", tags=["Items"])
def get_items(store_id: str = "store_001", db: Session = Depends(get_db)):
    """Get all items for a store"""
    items = db.query(Item).filter(Item.store_id == store_id).order_by(Item.name).all()
    return [item.to_dict() for item in items]


@app.get("/items/{item_id}", tags=["Items"])
def get_item(item_id: int, db: Session = Depends(get_db)):
    """Get a specific item by ID"""
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item.to_dict()


@app.post("/items", tags=["Items"])
def create_item(
    name: str,
    sku: str,
    price: float,
    category: Optional[str] = None,
    expiry_date: Optional[date] = None,
    low_stock_threshold: int = 5,
    store_id: str = "store_001",
    db: Session = Depends(get_db)
):
    """Create new item"""
    # Check if SKU already exists
    existing = db.query(Item).filter(Item.sku == sku).first()
    if existing:
        raise HTTPException(status_code=400, detail="SKU already exists")

    item = Item(
        store_id=store_id,
        name=name,
        sku=sku,
        price=price,
        category=category,
        expiry_date=expiry_date,
        low_stock_threshold=low_stock_threshold
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    # Create corresponding inventory record
    inventory = Inventory(item_id=item.id, current_count=0)
    db.add(inventory)
    db.commit()

    return {"status": "success", "item_id": item.id, "item": item.to_dict()}


# ============================================================================
# INVENTORY ENDPOINTS (Stock Management)
# ============================================================================

@app.get("/inventory", tags=["Inventory"])
def get_inventory(store_id: str = "store_001", db: Session = Depends(get_db)):
    """Get inventory status for all items"""
    items = db.query(Item).filter(Item.store_id == store_id).all()

    status = []
    for item in items:
        inv_count = item.inventory.current_count if item.inventory else 0
        alert_status = 'OK'

        if inv_count == 0:
            alert_status = 'OUT_OF_STOCK'
        elif inv_count < item.low_stock_threshold:
            alert_status = 'LOW_STOCK'

        status.append({
            'id': item.id,
            'name': item.name,
            'sku': item.sku,
            'price': item.price,
            'current_count': inv_count,
            'low_stock_threshold': item.low_stock_threshold,
            'status': alert_status
        })

    return status


@app.patch("/inventory/{item_id}", tags=["Inventory"])
def decrement_inventory(
    item_id: int,
    quantity: int = 1,
    reason: str = "billed",
    db: Session = Depends(get_db)
):
    """Decrement stock (called during checkout)"""
    inventory = db.query(Inventory).filter(Inventory.item_id == item_id).first()
    if not inventory:
        raise HTTPException(status_code=404, detail="Inventory record not found")

    item = inventory.item

    # Decrement
    old_count = inventory.current_count
    inventory.decrement(quantity)
    db.commit()

    # Check if alert should be triggered
    alerts = []
    if inventory.current_count == 0:
        alert = Alert(
            store_id=item.store_id,
            item_id=item_id,
            alert_type="STOCK_OUT",
            severity="critical",
            message=f"{item.name} is out of stock"
        )
        db.add(alert)
        alerts.append(alert.to_dict())

    elif inventory.current_count < item.low_stock_threshold:
        # Check if alert already exists
        existing_alert = db.query(Alert).filter(
            Alert.item_id == item_id,
            Alert.alert_type == "LOW_STOCK",
            Alert.resolved == False
        ).first()

        if not existing_alert:
            alert = Alert(
                store_id=item.store_id,
                item_id=item_id,
                alert_type="LOW_STOCK",
                severity="warning",
                message=f"{item.name} stock low: {inventory.current_count} units"
            )
            db.add(alert)
            alerts.append(alert.to_dict())

    db.commit()

    return {
        "status": "success",
        "item_id": item_id,
        "item_name": item.name,
        "old_count": old_count,
        "new_count": inventory.current_count,
        "reason": reason,
        "alerts": alerts
    }


# ============================================================================
# ALERTS ENDPOINTS
# ============================================================================

@app.get("/alerts", tags=["Alerts"])
def get_alerts(
    store_id: str = "store_001",
    resolved: bool = False,
    db: Session = Depends(get_db)
):
    """Get alerts"""
    alerts = db.query(Alert).filter(
        Alert.store_id == store_id,
        Alert.resolved == resolved
    ).order_by(Alert.severity.desc(), Alert.created_at.desc()).all()

    return [alert.to_dict() for alert in alerts]


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


# ============================================================================
# CHECKOUT ENDPOINTS
# ============================================================================

@app.post("/checkout/bill", tags=["Checkout"])
def process_checkout(
    detections: List[dict],
    store_id: str = "store_001",
    db: Session = Depends(get_db)
):
    """
    Process checkout and decrement inventory
    Detections format: [{"item_name": "apple", "confidence": 0.95, "quantity": 2}, ...]
    """
    cart = []
    total = 0.0
    alerts = []

    for detection in detections:
        item_name = detection.get('item_name')
        confidence = detection.get('confidence', 1.0)
        quantity = detection.get('quantity', 1)

        # Find item
        item = db.query(Item).filter(
            Item.store_id == store_id,
            Item.name.ilike(item_name)
        ).first()

        if not item:
            continue

        # Add to cart
        item_total = item.price * quantity
        cart.append({
            'item_id': item.id,
            'name': item.name,
            'price': item.price,
            'quantity': quantity,
            'subtotal': item_total,
            'confidence': confidence
        })
        total += item_total

        # Decrement inventory
        inventory = item.inventory
        if inventory:
            inventory.decrement(quantity)

            # Check alerts
            if inventory.current_count == 0:
                alert = Alert(
                    store_id=store_id,
                    item_id=item.id,
                    alert_type="STOCK_OUT",
                    severity="critical",
                    message=f"{item.name} is out of stock"
                )
                db.add(alert)
                alerts.append(alert.to_dict())

            elif inventory.current_count < item.low_stock_threshold:
                existing_alert = db.query(Alert).filter(
                    Alert.item_id == item.id,
                    Alert.alert_type == "LOW_STOCK",
                    Alert.resolved == False
                ).first()

                if not existing_alert:
                    alert = Alert(
                        store_id=store_id,
                        item_id=item.id,
                        alert_type="LOW_STOCK",
                        severity="warning",
                        message=f"{item.name} stock low: {inventory.current_count} units"
                    )
                    db.add(alert)
                    alerts.append(alert.to_dict())

    # Create transaction
    receipt_id = f"RCP_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    transaction = Transaction(
        store_id=store_id,
        receipt_id=receipt_id,
        total_amount=total,
        items_json=json.dumps(cart),
        status="completed"
    )
    db.add(transaction)
    db.commit()

    return {
        "status": "success",
        "receipt_id": receipt_id,
        "cart": cart,
        "total": total,
        "alerts": alerts
    }


# ============================================================================
# MODELS ENDPOINT
# ============================================================================

@app.get("/models/active", tags=["Models"])
def get_active_model(store_id: str = "store_001", db: Session = Depends(get_db)):
    """Get active model for store"""
    model = db.query(ModelVersion).filter(
        ModelVersion.store_id == store_id,
        ModelVersion.is_active == True
    ).order_by(ModelVersion.deployed_at.desc()).first()

    if not model:
        raise HTTPException(status_code=404, detail="No active model found")

    return model.to_dict()


# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.get("/health", tags=["System"])
def health_check():
    """API health check"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

Save this file as: `C:\Users\Admin\Desktop\BE Project\api_app.py`

---

## ▶️ Step 4: Run the API

### 4a. Start API Server
```bash
cd C:\Users\Admin\Desktop\BE Project
python api_app.py
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete
```

### 4b. Test API
Open browser → http://127.0.0.1:8000/docs

You'll see interactive Swagger documentation for all endpoints.

### 4c. Test Sample Requests

**Get all items:**
```bash
curl http://127.0.0.1:8000/items
```

**Get inventory:**
```bash
curl http://127.0.0.1:8000/inventory
```

**Process checkout:**
```bash
curl -X POST http://127.0.0.1:8000/checkout/bill \
  -H "Content-Type: application/json" \
  -d '{
    "detections": [
      {"item_name": "Apple", "confidence": 0.95, "quantity": 2},
      {"item_name": "Diet Coke", "confidence": 0.92, "quantity": 1}
    ]
  }'
```

---

## 📋 Weeks 1-2 Checklist (Your Phase 1 Tasks)

### Database Setup ✅
- [ ] TablePlus database created
- [ ] Schema imported (7 tables)
- [ ] Sample data loaded
- [ ] Verified all tables and indexes

### Python Models ✅
- [ ] SQLAlchemy models created (`database.py`)
- [ ] Models tested and verified

### API Foundation ✅
- [ ] FastAPI app created (`api_app.py`)
- [ ] 9 endpoints working:
  - [ ] GET `/items` - List items
  - [ ] GET `/items/{id}` - Get single item
  - [ ] POST `/items` - Create item
  - [ ] GET `/inventory` - Stock levels
  - [ ] PATCH `/inventory/{id}` - Decrement stock
  - [ ] GET `/alerts` - View alerts
  - [ ] PATCH `/alerts/{id}` - Resolve alert
  - [ ] POST `/checkout/bill` - Process checkout
  - [ ] GET `/models/active` - Get active model

### Testing
- [ ] Test each endpoint in Swagger UI
- [ ] Verify database updates after operations
- [ ] Test alert triggering (low stock, stock out)

### Documentation
- [ ] API docs auto-generated (Swagger at `/docs`)
- [ ] Database schema documented
- [ ] README created

---

## 🔗 Communication with Other Team Members

### For Person B (ML):
> "I've set up the database and API. When you have the PyTorch model ready, we need to:
> 1. Save model to `models/{store_id}_v1.pt`
> 2. Insert model version record with metrics
> 3. Set `is_active=1` for deployment
> 
> What format should training results be stored?"

### For Person C (Frontend):
> "Here are the API endpoints you'll use:
> - GET `/items` - for inventory search
> - GET `/inventory` - for dashboard
> - GET `/alerts` - for alerts panel
> - POST `/checkout/bill` - for checkout flow
> 
> Full docs available at http://localhost:8000/docs"

---

## 🚨 Common Issues

### "Database is locked"
- Close other connections to `billbro_mvp.db`
- Restart API server

### "Foreign key constraint error"
- Make sure parent record exists (e.g., item before inventory)

### "Port 8000 already in use"
```bash
# Kill process on port 8000
netstat -ano | findstr :8000  # Find PID
taskkill /PID <PID> /F  # Kill process
```

### "Module not found: fastapi"
```bash
# Activate virtual environment
venv\Scripts\activate
pip install -r requirements.txt
```

---

## 📈 Next Steps (Week 3+)

1. **Implement async training jobs** (Person B integration)
2. **Add input validation** (Pydantic models)
3. **Write unit tests** (`tests/test_api.py`)
4. **Add authentication** (API keys or OAuth)
5. **Connect to Streamlit frontend** (Person C's app)
6. **Deploy to PostgreSQL** (Week 6+)

---

## 📚 Resources

- **FastAPI Docs:** https://fastapi.tiangolo.com/
- **SQLAlchemy Docs:** https://docs.sqlalchemy.org/
- **TablePlus:** https://tableplus.com/
- **SQLite:** https://www.sqlite.org/docs.html

---

## ✅ You're All Set!

You now have:
- ✅ SQLite database with 7 tables
- ✅ SQLAlchemy ORM models
- ✅ FastAPI with 9 endpoints
- ✅ Sample data for testing
- ✅ Interactive API docs

**Next:** Start with simple GET requests, then test inventory decrements and alert triggering.

Good luck! 🚀
