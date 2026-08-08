"""
BillBro FastAPI Application
Main API server for inventory management
"""

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime, date
from typing import List, Optional, Any
from functools import lru_cache
from pydantic import BaseModel
import json
import os
import threading
import uuid
from pathlib import Path

from database import Base, Item, Inventory, Alert, ModelVersion, Transaction, TrainingJob

try:
    from predict import GroceryDetector
    DETECTOR_AVAILABLE = True
except ImportError:
    DETECTOR_AVAILABLE = False

try:
    from training import retrain_model, read_job_status
    TRAINING_AVAILABLE = True
except ImportError:
    TRAINING_AVAILABLE = False

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
    FOR_PERSON_C.md / RESPONSES_TO_PERSON_B_AND_C.md, plus batch_number
    and batch_arrival_date (added on request).

    Note: still no `barcode` field — that one genuinely doesn't exist in
    the `items` table. batch_number/batch_arrival_date DO now exist
    (see database.py) and are stored — this is the ONE current/most
    recent batch per item, not per-batch history (items:inventory is a
    1:1 relationship, so there's no concept of multiple concurrent
    batches of the same item yet).
    """
    name: str
    sku: str
    price: float
    category: Optional[str] = None
    expiry_date: Optional[date] = None
    low_stock_threshold: int = 5
    batch_number: Optional[str] = None
    batch_arrival_date: Optional[date] = None


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
        low_stock_threshold=body.low_stock_threshold,
        batch_number=body.batch_number,
        batch_arrival_date=body.batch_arrival_date
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    # Create corresponding inventory record
    inventory = Inventory(item_id=item.id, current_count=0)
    db.add(inventory)
    db.commit()

    return {"status": "success", "item_id": item.id, "item": item.to_dict()}


class RestockRequest(BaseModel):
    """
    Request body for PATCH /items/{item_id}/restock.

    Covers the "new batch of an existing item arrived" case that
    POST /items alone can't handle (sku is unique, so an existing item
    can't be re-created). batch_number/batch_arrival_date, if given,
    overwrite the item's current batch fields — per the "one active
    batch per item" model, there's no history kept of the previous batch.
    """
    quantity_added: int
    batch_number: Optional[str] = None
    batch_arrival_date: Optional[date] = None


@app.patch("/items/{item_id}/restock", tags=["Items"])
def restock_item(
    item_id: int,
    body: RestockRequest,
    db: Session = Depends(get_db)
):
    """
    Record a new batch arriving for an existing item: adds to current
    stock and overwrites the item's batch_number/batch_arrival_date.

    Does NOT auto-resolve existing LOW_STOCK/STOCK_OUT alerts — those
    stay manually resolved via PATCH /alerts/{id}, consistent with how
    alerts are handled everywhere else in this API.
    """
    if body.quantity_added <= 0:
        raise HTTPException(status_code=400, detail="quantity_added must be positive")

    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    inventory = item.inventory
    if not inventory:
        raise HTTPException(status_code=404, detail="Inventory record not found for this item")

    old_count = inventory.current_count
    inventory.current_count += body.quantity_added
    inventory.last_updated = datetime.utcnow()

    if body.batch_number is not None:
        item.batch_number = body.batch_number
    if body.batch_arrival_date is not None:
        item.batch_arrival_date = body.batch_arrival_date

    db.commit()
    db.refresh(item)
    db.refresh(inventory)

    return {
        "status": "success",
        "item_id": item.id,
        "item_name": item.name,
        "old_count": old_count,
        "new_count": inventory.current_count,
        "batch_number": item.batch_number,
        "batch_arrival_date": item.batch_arrival_date.isoformat() if item.batch_arrival_date else None
    }


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
# TRAINING ENDPOINTS (Add Item -> Train -> Shelve, wraps Person B's training.py)
# ============================================================================

# The 6-class base model's data.yaml, repo root. Only read on a store's
# FIRST ever training run (bootstraps training.py's ReplayPool) — every
# run after that ignores it and uses the persisted pool instead, so this
# never needs per-store configuration.
BASE_DATA_YAML = "data.yaml"


@app.post("/training/upload_images", tags=["Training"])
def upload_training_images(
    item_id: int,
    item_name: str,
    store_id: str = "store_001",
    images: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """
    Save staff-captured photos for a new item and kick off fine-tuning in
    the background (retrain_model() is a blocking call — ~15 min GPU /
    ~1 hr CPU per Person B — so it never runs inside the request handler).

    item_name should already be lowercase/underscored (e.g.
    "maggi_noodles") — training.py uses it directly as the new class
    label. Flips Item.status to 'training' immediately, then
    'shelved'/'failed' once the background job settles.
    """
    if not TRAINING_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Training pipeline not available. Check that training.py's dependencies "
                   "(ultralytics, torch, pyyaml) are installed."
        )

    # retrain_model() needs this to bootstrap the replay pool on a store's
    # first-ever run — without it, the background thread below would fail
    # with an uncaught FileNotFoundError *before* any job-status write, so
    # the item would silently get stuck at 'training' forever with no
    # error surfaced anywhere. Fail fast here instead, at request time.
    if not Path(BASE_DATA_YAML).exists():
        raise HTTPException(
            status_code=503,
            detail=f"{BASE_DATA_YAML} not found at repo root — required to bootstrap the "
                    "replay pool for training. Add the base model's data.yaml (6 classes: "
                    "apple, banana, dragonfruit, custard_apple, diet_coke, pepsi) before "
                    "using this endpoint."
        )

    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    upload_dir = Path("training_uploads") / f"item_{item_id}"
    upload_dir.mkdir(parents=True, exist_ok=True)
    image_paths = []
    for i, img in enumerate(images):
        dest = upload_dir / f"{item_name}_{i:03d}.jpg"
        with open(dest, "wb") as f:
            f.write(img.file.read())
        image_paths.append(str(dest))

    if len(image_paths) < 5:
        raise HTTPException(status_code=400, detail="Need at least 5 photos")

    job_id = str(uuid.uuid4())

    def run():
        # Belt-and-suspenders: retrain_model() already writes
        # status="failed" to the job file for its own documented failure
        # modes (too few labeled images, mAP50 below threshold). This
        # catches anything ELSE unexpected (GPU error, corrupt image,
        # disk full, etc.) so the item doesn't get stuck at 'training'
        # forever with zero explanation. Note: training.py doesn't expose
        # a public "mark job failed" function, so an exception here means
        # read_job_status(job_id) will still report "unknown" — only
        # Item.status reliably reflects the failure in that case.
        try:
            retrain_model(
                store_id=store_id,
                item_name=item_name,
                image_paths=image_paths,
                base_data_yaml=BASE_DATA_YAML,
                job_id=job_id,
                item_id=item_id,
            )
        except Exception as e:
            print(f"Training job {job_id} (item {item_id}) crashed unexpectedly: {e}")
            db_err = SessionLocal()
            try:
                it = db_err.query(Item).filter(Item.id == item_id).first()
                if it:
                    it.status = "failed"
                    db_err.commit()
            finally:
                db_err.close()
            return

        # Flip item status once the job file settles. Uses its own DB
        # session rather than the request's `db` — this runs in a
        # background thread well after the request (and its session)
        # have already returned.
        result = read_job_status(job_id)
        db2 = SessionLocal()
        try:
            it = db2.query(Item).filter(Item.id == item_id).first()
            if it:
                it.status = "shelved" if result.get("status") == "success" else "failed"
                db2.commit()
        finally:
            db2.close()

    item.status = "training"
    db.commit()
    threading.Thread(target=run, daemon=True).start()

    return {"job_id": job_id, "item_id": item_id, "status": "training"}


@app.get("/training/job/{job_id}", tags=["Training"])
def get_training_job(job_id: str):
    """
    Poll training job status. Reads straight from Person B's file-based
    tracker (models/jobs/{job_id}.json via read_job_status()) — this does
    NOT query the TrainingJob SQL table; training.py is intentionally
    decoupled from the DB layer (see its module docstring). Response
    shape matches TrainingJob's columns: status, progress, item_id,
    current_epoch, metrics, error_message, created_at, completed_at
    (plus stage/model_version as harmless extras).
    """
    if not TRAINING_AVAILABLE:
        raise HTTPException(status_code=503, detail="Training pipeline not available.")

    result = read_job_status(job_id)
    if result.get("status") == "unknown":
        raise HTTPException(status_code=404, detail="Job not found")
    return result


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
