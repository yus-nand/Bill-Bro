"""
BillBro FastAPI Application
Main API server for inventory management
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime, date
from typing import List, Optional, Any
from functools import lru_cache
from pydantic import BaseModel
import json
import os
from pathlib import Path

from database import Base, Item, Inventory, Alert, ModelVersion, Transaction, TrainingJob

try:
    from predict import GroceryDetector
    DETECTOR_AVAILABLE = True
except ImportError:
    DETECTOR_AVAILABLE = False

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

# ============================================================================
# CORS Configuration (Allow Frontend to Call API)
# ============================================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",       # React dev server (if Person C uses React)
        "http://localhost:5173",       # Vite dev server (Person C is using this)
        "http://localhost:8000",       # API docs
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000",
        # Add your production domain here later:
        # "https://billbro.yourcompany.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],              # Allow all HTTP methods
    allow_headers=["*"],              # Allow all headers
)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================================
# DETECTION SETUP (Person B's YOLOv8 Model)
# ============================================================================

@lru_cache(maxsize=1)
def get_detector() -> Optional['GroceryDetector']:
    """Load and cache the YOLOv8 detector model"""
    if not DETECTOR_AVAILABLE:
        return None

    model_path = "models/grocery_yolov8.pt"
    if not Path(model_path).exists():
        return None

    try:
        return GroceryDetector(model_path)
    except Exception as e:
        print(f"Warning: Could not load detector: {e}")
        return None


class DetectRequest(BaseModel):
    """Request body for /detect endpoint"""
    image: str  # Base64-encoded image (no data-URL prefix)
    confidence_threshold: float = 0.5  # Detection confidence threshold


class CreateItemRequest(BaseModel):
    """
    Request body for POST /items — matches the documented contract in
    FOR_PERSON_C.md / RESPONSES_TO_PERSON_B_AND_C.md exactly.

    Note: no `batch_number` or `barcode` field — neither exists in the
    `items` table (see database.py). If the frontend sends them anyway,
    Pydantic's default behavior silently ignores unknown fields (no error),
    so this is safe either way, but the frontend should stop sending
    batch_number since it's never persisted.
    """
    name: str
    sku: str
    price: float
    category: Optional[str] = None
    expiry_date: Optional[date] = None
    low_stock_threshold: int = 5


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
    body: CreateItemRequest,
    store_id: str = "store_001",
    db: Session = Depends(get_db)
):
    """
    Create new item.

    Takes a JSON body (CreateItemRequest) — previously this used plain
    scalar function args, which FastAPI reads as query params, not a JSON
    body. That mismatched every doc's example and frontend/src/api.js,
    which both POST a JSON body. Fixed here; store_id stays a query param
    since it's not part of the documented request body.
    """
    # Check if SKU already exists
    existing = db.query(Item).filter(Item.sku == body.sku).first()
    if existing:
        raise HTTPException(status_code=400, detail="SKU already exists")

    item = Item(
        store_id=store_id,
        name=body.name,
        sku=body.sku,
        price=body.price,
        category=body.category,
        expiry_date=body.expiry_date,
        low_stock_threshold=body.low_stock_threshold
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
# DETECTION ENDPOINT (Wraps Person B's YOLOv8 Model)
# ============================================================================

@app.post("/detect", tags=["Detection"])
def detect(body: DetectRequest):
    """
    Run YOLOv8 detection on base64-encoded image.

    Request:
        image: Base64-encoded image string (no "data:image/..." prefix)
        confidence_threshold: Detection confidence threshold (0.0-1.0)

    Response:
        {
            "detections": [
                {"item_name": str, "confidence": float, "bbox": [x1, y1, x2, y2]},
                ...
            ],
            "processing_time_ms": int
        }

    Raised by Person B's GroceryDetector:
        - ValueError: If image_b64 cannot be decoded
        - FileNotFoundError: If model file not found
    """
    detector = get_detector()

    if detector is None:
        raise HTTPException(
            status_code=503,
            detail="Detection model not available. Check that models/grocery_yolov8.pt exists and ultralytics is installed."
        )

    try:
        result = detector.detect_from_base64(
            body.image,
            confidence_threshold=body.confidence_threshold
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid image: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Detection failed: {str(e)}")


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
