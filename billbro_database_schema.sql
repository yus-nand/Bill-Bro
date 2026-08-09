-- BillBro Smart Inventory System Database Schema
-- Database: billbro_mvp
-- Created: August 2026
-- Tech: SQLite (MVP) → PostgreSQL (Production)

-- TABLE: items
-- Stores product information and metadata
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id TEXT NOT NULL DEFAULT 'store_001',
    name TEXT NOT NULL UNIQUE,
    sku TEXT NOT NULL UNIQUE,
    price REAL NOT NULL,
    category TEXT,
    expiry_date DATE,
    low_stock_threshold INTEGER DEFAULT 5,
    -- Shelve gate for Add Item -> Train -> Shelve. An item is only
    -- checkout-detectable once status='shelved' (enforced in
    -- POST /checkout/bill). Items created via a fresh setup of this
    -- schema (e.g. sample data) should be set to 'shelved' explicitly if
    -- they're meant to be immediately sellable, since they bypass the
    -- training pipeline entirely.
    status TEXT DEFAULT 'pending', -- pending | training | shelved | failed
    -- Tracks the CURRENT/most recent batch only (Item:Inventory is 1:1,
    -- no per-batch history). See PATCH /items/{id}/restock.
    batch_number TEXT,
    batch_arrival_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TABLE: inventory
-- Tracks current stock levels for each item
CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL UNIQUE,
    current_count INTEGER DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
);

-- TABLE: training_data
-- Stores images and labels for model training
CREATE TABLE IF NOT EXISTS training_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    image_path TEXT NOT NULL,
    bbox_coordinates TEXT, -- JSON format: [[x1,y1,x2,y2], ...]
    labeled_by TEXT DEFAULT 'auto',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
);

-- TABLE: model_versions
-- Tracks all trained model versions per store
CREATE TABLE IF NOT EXISTS model_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id TEXT NOT NULL DEFAULT 'store_001',
    version TEXT NOT NULL, -- e.g., "v1", "v2"
    model_path TEXT NOT NULL,
    metrics TEXT, -- JSON format: {"mAP50": 0.92, "mAP": 0.87, "accuracy": 0.90}
    is_active BOOLEAN DEFAULT 0,
    trained_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deployed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TABLE: alerts
-- Tracks inventory and expiry alerts
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id TEXT NOT NULL DEFAULT 'store_001',
    item_id INTEGER NOT NULL,
    alert_type TEXT NOT NULL, -- 'STOCK_OUT', 'EXPIRY', 'LOW_STOCK'
    severity TEXT NOT NULL, -- 'critical', 'warning'
    message TEXT NOT NULL,
    resolved BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
);

-- TABLE: transactions
-- Logs all checkout transactions
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id TEXT NOT NULL DEFAULT 'store_001',
    receipt_id TEXT NOT NULL UNIQUE,
    total_amount REAL NOT NULL,
    items_json TEXT, -- JSON: [{item_id, name, price, quantity, confidence}, ...]
    status TEXT DEFAULT 'completed', -- 'pending', 'completed', 'failed'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TABLE: training_jobs
-- Tracks async training jobs
CREATE TABLE IF NOT EXISTS training_jobs (
    id TEXT PRIMARY KEY, -- job_id
    item_id INTEGER,
    store_id TEXT NOT NULL DEFAULT 'store_001',
    status TEXT DEFAULT 'pending', -- 'pending', 'running', 'success', 'failed'
    progress INTEGER DEFAULT 0, -- 0-100
    -- SQLite has no strict typing (type affinity only) - a "3/5"-style
    -- progress string works fine here despite the INTEGER declaration
    -- below, but matches database.py's ORM model (String) if a fresh
    -- setup is ever moved to a stricter engine (e.g. Postgres).
    current_epoch TEXT DEFAULT '0',
    total_epochs INTEGER DEFAULT 5,
    accuracy REAL,
    metrics TEXT, -- JSON: mAP50, mAP50-95, precision, recall, per_class_AP50, epochs, new_item_train_images
    error_message TEXT,
    model_version TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (item_id) REFERENCES items(id)
);

-- INDEXES (for performance)
CREATE INDEX IF NOT EXISTS idx_items_store ON items(store_id);
CREATE INDEX IF NOT EXISTS idx_inventory_item ON inventory(item_id);
CREATE INDEX IF NOT EXISTS idx_alerts_store ON alerts(store_id);
CREATE INDEX IF NOT EXISTS idx_alerts_item ON alerts(item_id);
CREATE INDEX IF NOT EXISTS idx_alerts_resolved ON alerts(resolved);
CREATE INDEX IF NOT EXISTS idx_transactions_store ON transactions(store_id);
CREATE INDEX IF NOT EXISTS idx_training_data_item ON training_data(item_id);
CREATE INDEX IF NOT EXISTS idx_model_versions_store ON model_versions(store_id);
CREATE INDEX IF NOT EXISTS idx_training_jobs_status ON training_jobs(status);

-- VIEWS (useful for queries)
-- Active alerts view
CREATE VIEW IF NOT EXISTS active_alerts AS
SELECT
    a.id, a.alert_type, a.severity, a.message, a.created_at,
    i.name as item_name, i.price,
    inv.current_count
FROM alerts a
JOIN items i ON a.item_id = i.id
LEFT JOIN inventory inv ON inv.item_id = i.id
WHERE a.resolved = 0
ORDER BY a.severity DESC, a.created_at DESC;

-- Inventory status view
CREATE VIEW IF NOT EXISTS inventory_status AS
SELECT
    i.id, i.name, i.sku, i.price, i.expiry_date, i.low_stock_threshold,
    inv.current_count,
    CASE
        WHEN inv.current_count = 0 THEN 'OUT_OF_STOCK'
        WHEN inv.current_count < i.low_stock_threshold THEN 'LOW_STOCK'
        ELSE 'OK'
    END as status
FROM items i
LEFT JOIN inventory inv ON inv.item_id = i.id
ORDER BY inv.current_count ASC;

-- Model status view
CREATE VIEW IF NOT EXISTS active_models AS
SELECT
    store_id, version, model_path, is_active,
    deployed_at, metrics
FROM model_versions
WHERE is_active = 1
ORDER BY deployed_at DESC;
