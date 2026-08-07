"""
BillBro Database Models
SQLAlchemy ORM models for inventory management system

Usage:
    from database import Base, Item, Inventory, Alert, ModelVersion, TrainingJob
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    # Create engine
    engine = create_engine('sqlite:///billbro_mvp.db')
    Base.metadata.create_all(engine)

    # Create session
    Session = sessionmaker(bind=engine)
    session = Session()
"""

from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Date, ForeignKey, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import json

Base = declarative_base()


class Item(Base):
    """Product information and metadata"""
    __tablename__ = 'items'

    id = Column(Integer, primary_key=True, autoincrement=True)
    store_id = Column(String(50), default='store_001', nullable=False)
    name = Column(String(255), unique=True, nullable=False)
    sku = Column(String(50), unique=True, nullable=False)
    price = Column(Float, nullable=False)
    category = Column(String(100))
    expiry_date = Column(Date)
    low_stock_threshold = Column(Integer, default=5)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    inventory = relationship('Inventory', back_populates='item', uselist=False, cascade='all, delete-orphan')
    alerts = relationship('Alert', back_populates='item', cascade='all, delete-orphan')
    training_data = relationship('TrainingData', back_populates='item', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'store_id': self.store_id,
            'name': self.name,
            'sku': self.sku,
            'price': self.price,
            'category': self.category,
            'expiry_date': self.expiry_date.isoformat() if self.expiry_date else None,
            'low_stock_threshold': self.low_stock_threshold,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


class Inventory(Base):
    """Current stock levels for each item"""
    __tablename__ = 'inventory'

    id = Column(Integer, primary_key=True, autoincrement=True)
    item_id = Column(Integer, ForeignKey('items.id'), unique=True, nullable=False)
    current_count = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    item = relationship('Item', back_populates='inventory')

    def to_dict(self):
        return {
            'id': self.id,
            'item_id': self.item_id,
            'current_count': self.current_count,
            'last_updated': self.last_updated.isoformat()
        }

    def decrement(self, quantity: int = 1) -> dict:
        """Decrement stock and return new count"""
        self.current_count = max(0, self.current_count - quantity)
        self.last_updated = datetime.utcnow()
        return {
            'item_id': self.item_id,
            'new_count': self.current_count,
            'previous_count': self.current_count + quantity
        }


class TrainingData(Base):
    """Images and labels for model training"""
    __tablename__ = 'training_data'

    id = Column(Integer, primary_key=True, autoincrement=True)
    item_id = Column(Integer, ForeignKey('items.id'), nullable=False)
    image_path = Column(String(500), nullable=False)
    bbox_coordinates = Column(Text)  # JSON format: [[x1,y1,x2,y2], ...]
    labeled_by = Column(String(50), default='auto')
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    item = relationship('Item', back_populates='training_data')

    def to_dict(self):
        bbox = []
        if self.bbox_coordinates:
            try:
                bbox = json.loads(self.bbox_coordinates)
            except json.JSONDecodeError:
                bbox = []

        return {
            'id': self.id,
            'item_id': self.item_id,
            'image_path': self.image_path,
            'bbox_coordinates': bbox,
            'labeled_by': self.labeled_by,
            'created_at': self.created_at.isoformat()
        }


class ModelVersion(Base):
    """Trained model versions per store"""
    __tablename__ = 'model_versions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    store_id = Column(String(50), default='store_001', nullable=False)
    version = Column(String(50), nullable=False)  # e.g., 'v1', 'v2'
    model_path = Column(String(500), nullable=False)
    metrics = Column(Text)  # JSON: {"mAP50": 0.92, "mAP": 0.87, "accuracy": 0.90}
    is_active = Column(Boolean, default=False)
    trained_at = Column(DateTime, default=datetime.utcnow)
    deployed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        metrics = {}
        if self.metrics:
            try:
                metrics = json.loads(self.metrics)
            except json.JSONDecodeError:
                metrics = {}

        return {
            'id': self.id,
            'store_id': self.store_id,
            'version': self.version,
            'model_path': self.model_path,
            'metrics': metrics,
            'is_active': self.is_active,
            'trained_at': self.trained_at.isoformat(),
            'deployed_at': self.deployed_at.isoformat() if self.deployed_at else None,
            'created_at': self.created_at.isoformat()
        }


class Alert(Base):
    """Inventory and expiry alerts"""
    __tablename__ = 'alerts'

    id = Column(Integer, primary_key=True, autoincrement=True)
    store_id = Column(String(50), default='store_001', nullable=False)
    item_id = Column(Integer, ForeignKey('items.id'), nullable=False)
    alert_type = Column(String(50), nullable=False)  # 'STOCK_OUT', 'EXPIRY', 'LOW_STOCK'
    severity = Column(String(20), nullable=False)  # 'critical', 'warning'
    message = Column(String(500), nullable=False)
    resolved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime)

    # Relationships
    item = relationship('Item', back_populates='alerts')

    def to_dict(self):
        return {
            'id': self.id,
            'store_id': self.store_id,
            'item_id': self.item_id,
            'item_name': self.item.name if self.item else None,
            'alert_type': self.alert_type,
            'severity': self.severity,
            'message': self.message,
            'resolved': self.resolved,
            'created_at': self.created_at.isoformat(),
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None
        }


class Transaction(Base):
    """Checkout transactions"""
    __tablename__ = 'transactions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    store_id = Column(String(50), default='store_001', nullable=False)
    receipt_id = Column(String(100), unique=True, nullable=False)
    total_amount = Column(Float, nullable=False)
    items_json = Column(Text)  # JSON: [{item_id, name, price, quantity, confidence}, ...]
    status = Column(String(20), default='completed')  # 'pending', 'completed', 'failed'
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        items = []
        if self.items_json:
            try:
                items = json.loads(self.items_json)
            except json.JSONDecodeError:
                items = []

        return {
            'id': self.id,
            'store_id': self.store_id,
            'receipt_id': self.receipt_id,
            'total_amount': self.total_amount,
            'items': items,
            'status': self.status,
            'created_at': self.created_at.isoformat()
        }


class TrainingJob(Base):
    """Async training job tracking"""
    __tablename__ = 'training_jobs'

    id = Column(String(100), primary_key=True)  # job_id
    item_id = Column(Integer, ForeignKey('items.id'))
    store_id = Column(String(50), default='store_001', nullable=False)
    status = Column(String(20), default='pending')  # 'pending', 'running', 'success', 'failed'
    progress = Column(Integer, default=0)  # 0-100
    current_epoch = Column(Integer, default=0)
    total_epochs = Column(Integer, default=5)
    accuracy = Column(Float)
    error_message = Column(String(500))
    model_version = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)

    def to_dict(self):
        return {
            'id': self.id,
            'item_id': self.item_id,
            'store_id': self.store_id,
            'status': self.status,
            'progress': self.progress,
            'current_epoch': self.current_epoch,
            'total_epochs': self.total_epochs,
            'accuracy': self.accuracy,
            'error_message': self.error_message,
            'model_version': self.model_version,
            'created_at': self.created_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }


# ============================================================================
# Helper Functions for Common Operations
# ============================================================================

def init_db(db_url: str = 'sqlite:///billbro_mvp.db'):
    """Initialize database tables"""
    from sqlalchemy import create_engine
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    return engine


def get_session(engine):
    """Get database session"""
    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=engine)
    return Session()


def get_active_model(session, store_id: str = 'store_001'):
    """Get active model for store"""
    return session.query(ModelVersion).filter(
        ModelVersion.store_id == store_id,
        ModelVersion.is_active == True
    ).order_by(ModelVersion.deployed_at.desc()).first()


def get_inventory_status(session, store_id: str = 'store_001'):
    """Get inventory status for all items in store"""
    items = session.query(Item).filter(Item.store_id == store_id).all()

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
            'status': alert_status,
            'expiry_date': item.expiry_date.isoformat() if item.expiry_date else None
        })

    return status


def get_active_alerts(session, store_id: str = 'store_001'):
    """Get unresolved alerts for store"""
    alerts = session.query(Alert).filter(
        Alert.store_id == store_id,
        Alert.resolved == False
    ).order_by(Alert.severity.desc(), Alert.created_at.desc()).all()

    return [alert.to_dict() for alert in alerts]
