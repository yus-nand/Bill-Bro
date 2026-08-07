"""
Unit Tests for BillBro Database Models and Operations
Run with: pytest test_database.py -v
"""

import pytest
from datetime import datetime, date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import models
from database import Base, Item, Inventory, Alert, ModelVersion, Transaction, TrainingJob

# Use in-memory SQLite for testing
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture
def db_session():
    """Create test database session"""
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestItemModel:
    """Test Item model"""

    def test_create_item(self, db_session):
        """Test creating an item"""
        item = Item(
            store_id="store_001",
            name="Apple",
            sku="APL001",
            price=35.00,
            category="fruits",
            expiry_date=date(2026, 9, 15),
            low_stock_threshold=5
        )
        db_session.add(item)
        db_session.commit()

        # Verify
        saved_item = db_session.query(Item).filter(Item.sku == "APL001").first()
        assert saved_item is not None
        assert saved_item.name == "Apple"
        assert saved_item.price == 35.00

    def test_item_to_dict(self, db_session):
        """Test item.to_dict() conversion"""
        item = Item(
            store_id="store_001",
            name="Banana",
            sku="BAN001",
            price=25.00
        )
        db_session.add(item)
        db_session.commit()

        item_dict = item.to_dict()
        assert item_dict['name'] == "Banana"
        assert item_dict['sku'] == "BAN001"
        assert 'created_at' in item_dict

    def test_unique_sku_constraint(self, db_session):
        """Test SKU uniqueness"""
        item1 = Item(name="Apple", sku="APL001", price=35.00)
        item2 = Item(name="Banana", sku="APL001", price=25.00)  # Duplicate SKU

        db_session.add(item1)
        db_session.commit()

        db_session.add(item2)
        with pytest.raises(Exception):  # Should raise IntegrityError
            db_session.commit()


class TestInventoryModel:
    """Test Inventory model"""

    def test_create_inventory(self, db_session):
        """Test creating inventory record"""
        item = Item(name="Apple", sku="APL001", price=35.00)
        db_session.add(item)
        db_session.commit()

        inv = Inventory(item_id=item.id, current_count=50)
        db_session.add(inv)
        db_session.commit()

        # Verify
        saved_inv = db_session.query(Inventory).filter(Inventory.item_id == item.id).first()
        assert saved_inv.current_count == 50

    def test_decrement_inventory(self, db_session):
        """Test inventory decrement operation"""
        item = Item(name="Apple", sku="APL001", price=35.00)
        db_session.add(item)
        db_session.commit()

        inv = Inventory(item_id=item.id, current_count=50)
        db_session.add(inv)
        db_session.commit()

        # Decrement
        result = inv.decrement(5)
        db_session.commit()

        assert inv.current_count == 45
        assert result['previous_count'] == 50
        assert result['new_count'] == 45

    def test_decrement_cannot_go_negative(self, db_session):
        """Test that inventory cannot go below 0"""
        item = Item(name="Apple", sku="APL001", price=35.00)
        db_session.add(item)
        db_session.commit()

        inv = Inventory(item_id=item.id, current_count=3)
        db_session.add(inv)
        db_session.commit()

        # Try to decrement more than available
        inv.decrement(10)
        db_session.commit()

        assert inv.current_count == 0  # Should not go negative


class TestAlertModel:
    """Test Alert model"""

    def test_create_alert(self, db_session):
        """Test creating an alert"""
        item = Item(name="Apple", sku="APL001", price=35.00, low_stock_threshold=5)
        db_session.add(item)
        db_session.commit()

        alert = Alert(
            store_id="store_001",
            item_id=item.id,
            alert_type="LOW_STOCK",
            severity="warning",
            message="Apple stock running low"
        )
        db_session.add(alert)
        db_session.commit()

        # Verify
        saved_alert = db_session.query(Alert).filter(Alert.item_id == item.id).first()
        assert saved_alert.alert_type == "LOW_STOCK"
        assert saved_alert.severity == "warning"
        assert saved_alert.resolved == False

    def test_resolve_alert(self, db_session):
        """Test resolving an alert"""
        item = Item(name="Apple", sku="APL001", price=35.00)
        db_session.add(item)
        db_session.commit()

        alert = Alert(
            item_id=item.id,
            alert_type="LOW_STOCK",
            severity="warning",
            message="Low stock"
        )
        db_session.add(alert)
        db_session.commit()

        # Resolve
        alert.resolved = True
        alert.resolved_at = datetime.utcnow()
        db_session.commit()

        saved_alert = db_session.query(Alert).filter(Alert.id == alert.id).first()
        assert saved_alert.resolved == True
        assert saved_alert.resolved_at is not None

    def test_alert_to_dict(self, db_session):
        """Test alert.to_dict() conversion"""
        item = Item(name="Apple", sku="APL001", price=35.00)
        db_session.add(item)
        db_session.commit()

        alert = Alert(
            item_id=item.id,
            alert_type="STOCK_OUT",
            severity="critical",
            message="Out of stock"
        )
        db_session.add(alert)
        db_session.commit()

        alert_dict = alert.to_dict()
        assert alert_dict['alert_type'] == "STOCK_OUT"
        assert alert_dict['severity'] == "critical"
        assert alert_dict['item_name'] == "Apple"


class TestModelVersionModel:
    """Test ModelVersion model"""

    def test_create_model_version(self, db_session):
        """Test creating a model version"""
        model = ModelVersion(
            store_id="store_001",
            version="v1",
            model_path="models/store_001_v1.pt",
            metrics='{"mAP50": 0.92, "mAP": 0.87}',
            is_active=True
        )
        db_session.add(model)
        db_session.commit()

        # Verify
        saved_model = db_session.query(ModelVersion).filter(
            ModelVersion.version == "v1"
        ).first()
        assert saved_model.is_active == True
        assert "mAP50" in saved_model.metrics


class TestTransactionModel:
    """Test Transaction model"""

    def test_create_transaction(self, db_session):
        """Test creating a transaction"""
        import json

        cart = [
            {"item_id": 1, "name": "Apple", "price": 35.00, "quantity": 2},
            {"item_id": 2, "name": "Banana", "price": 25.00, "quantity": 1}
        ]

        transaction = Transaction(
            store_id="store_001",
            receipt_id="RCP_20260807_001",
            total_amount=95.00,
            items_json=json.dumps(cart),
            status="completed"
        )
        db_session.add(transaction)
        db_session.commit()

        # Verify
        saved_tx = db_session.query(Transaction).filter(
            Transaction.receipt_id == "RCP_20260807_001"
        ).first()
        assert saved_tx.total_amount == 95.00
        assert saved_tx.status == "completed"


class TestTrainingJobModel:
    """Test TrainingJob model"""

    def test_create_training_job(self, db_session):
        """Test creating a training job"""
        job = TrainingJob(
            id="job_20260807_001",
            store_id="store_001",
            status="pending",
            current_epoch=0,
            total_epochs=5
        )
        db_session.add(job)
        db_session.commit()

        # Verify
        saved_job = db_session.query(TrainingJob).filter(
            TrainingJob.id == "job_20260807_001"
        ).first()
        assert saved_job.status == "pending"
        assert saved_job.progress == 0

    def test_update_training_job_progress(self, db_session):
        """Test updating training job progress"""
        job = TrainingJob(
            id="job_20260807_002",
            store_id="store_001",
            status="pending"
        )
        db_session.add(job)
        db_session.commit()

        # Update progress
        job.status = "running"
        job.progress = 25
        job.current_epoch = 1
        db_session.commit()

        saved_job = db_session.query(TrainingJob).filter(
            TrainingJob.id == "job_20260807_002"
        ).first()
        assert saved_job.status == "running"
        assert saved_job.progress == 25


class TestIntegration:
    """Integration tests for realistic workflows"""

    def test_checkout_workflow(self, db_session):
        """Test complete checkout workflow"""
        # 1. Create item
        item = Item(
            name="Apple",
            sku="APL001",
            price=35.00,
            low_stock_threshold=5
        )
        db_session.add(item)
        db_session.commit()

        # 2. Create inventory
        inv = Inventory(item_id=item.id, current_count=10)
        db_session.add(inv)
        db_session.commit()

        # 3. Checkout (decrement)
        inv.decrement(2)
        db_session.commit()

        assert inv.current_count == 8

        # 4. No alert should trigger (still > threshold)
        alerts = db_session.query(Alert).filter(Alert.item_id == item.id).all()
        assert len(alerts) == 0

    def test_low_stock_alert_workflow(self, db_session):
        """Test low stock alert triggering"""
        # 1. Create item with low threshold
        item = Item(
            name="Apple",
            sku="APL001",
            price=35.00,
            low_stock_threshold=5
        )
        db_session.add(item)
        db_session.commit()

        # 2. Create inventory with few items
        inv = Inventory(item_id=item.id, current_count=6)
        db_session.add(inv)
        db_session.commit()

        # 3. Decrement to trigger alert
        inv.decrement(2)  # 6 - 2 = 4 (below threshold of 5)
        db_session.commit()

        # 4. Create alert
        alert = Alert(
            store_id="store_001",
            item_id=item.id,
            alert_type="LOW_STOCK",
            severity="warning",
            message=f"{item.name} stock low: {inv.current_count} units"
        )
        db_session.add(alert)
        db_session.commit()

        # 5. Verify alert
        saved_alerts = db_session.query(Alert).filter(Alert.item_id == item.id).all()
        assert len(saved_alerts) == 1
        assert saved_alerts[0].alert_type == "LOW_STOCK"

    def test_get_inventory_status(self, db_session):
        """Test getting inventory status for all items"""
        # Create multiple items
        items_data = [
            ("Apple", "APL001", 35.00, 5, 3),   # Low stock
            ("Banana", "BAN001", 25.00, 10, 15),  # OK
            ("Diet Coke", "DCK001", 50.00, 10, 0),  # Out of stock
        ]

        for name, sku, price, threshold, count in items_data:
            item = Item(
                name=name,
                sku=sku,
                price=price,
                low_stock_threshold=threshold
            )
            db_session.add(item)
            db_session.commit()

            inv = Inventory(item_id=item.id, current_count=count)
            db_session.add(inv)
            db_session.commit()

        # Get all items with inventory
        items = db_session.query(Item).all()
        assert len(items) == 3

        # Check statuses
        statuses = {}
        for item in items:
            inv_count = item.inventory.current_count
            if inv_count == 0:
                statuses[item.name] = 'OUT_OF_STOCK'
            elif inv_count < item.low_stock_threshold:
                statuses[item.name] = 'LOW_STOCK'
            else:
                statuses[item.name] = 'OK'

        assert statuses['Apple'] == 'LOW_STOCK'
        assert statuses['Banana'] == 'OK'
        assert statuses['Diet Coke'] == 'OUT_OF_STOCK'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
