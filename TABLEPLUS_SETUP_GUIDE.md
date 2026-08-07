# TablePlus Setup Guide for BillBro Database

## Overview
This guide walks you through setting up your BillBro inventory database in TablePlus using SQLite for MVP development.

---

## Step 1: Create SQLite Database File

### Option A: Using TablePlus UI
1. Open TablePlus
2. Click **File** → **New** → **SQLite**
3. Choose location: `C:\Users\Admin\Desktop\BE Project\billbro_mvp.db`
4. Name it: `billbro_mvp`
5. Click **Save**

### Option B: Using Command Line
```bash
cd C:\Users\Admin\Desktop\BE Project
sqlite3 billbro_mvp.db
```

---

## Step 2: Import Database Schema

### In TablePlus:
1. Open your `billbro_mvp.db` connection
2. Click **File** → **Import**
3. Select `billbro_database_schema.sql`
4. Click **Import**
5. Wait for all tables to be created
6. Verify in the left sidebar that you see all tables:
   - `items`
   - `inventory`
   - `training_data`
   - `model_versions`
   - `alerts`
   - `transactions`
   - `training_jobs`

---

## Step 3: Load Sample Data

### In TablePlus:
1. Click **File** → **Import**
2. Select `billbro_sample_data.sql`
3. Click **Import**
4. Verify data loaded:
   - Click **items** table → Should see 6 items (apple, banana, dragon fruit, custard apple, diet coke, pepsi)
   - Click **inventory** table → Should see stock levels
   - Click **alerts** table → Should see 3 low-stock alerts
   - Click **transactions** table → Should see 3 sample receipts

---

## Step 4: Verify Database Structure

### Check Tables:
In TablePlus, run this query to verify all tables exist:

```sql
SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;
```

Expected output:
```
alerts
inventory
items
model_versions
training_data
training_jobs
transactions
```

### Check Indexes:
```sql
SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%';
```

### Check Views:
```sql
SELECT name FROM sqlite_master WHERE type='view';
```

---

## Step 5: Test Sample Queries

Run these in TablePlus to verify everything works:

### 1. Get All Items
```sql
SELECT id, name, sku, price, expiry_date, low_stock_threshold
FROM items
ORDER BY name;
```

### 2. Check Inventory Status
```sql
SELECT
    i.id, i.name, i.sku, inv.current_count, i.low_stock_threshold,
    CASE
        WHEN inv.current_count = 0 THEN 'OUT_OF_STOCK'
        WHEN inv.current_count < i.low_stock_threshold THEN 'LOW_STOCK'
        ELSE 'OK'
    END as status
FROM items i
LEFT JOIN inventory inv ON inv.item_id = i.id
ORDER BY inv.current_count ASC;
```

### 3. Get Active Alerts
```sql
SELECT
    a.id, a.alert_type, a.severity, a.message,
    i.name as item_name,
    inv.current_count
FROM alerts a
JOIN items i ON a.item_id = i.id
LEFT JOIN inventory inv ON inv.item_id = i.id
WHERE a.resolved = 0
ORDER BY a.severity DESC, a.created_at DESC;
```

### 4. Check Transactions
```sql
SELECT receipt_id, total_amount, status, created_at
FROM transactions
ORDER BY created_at DESC;
```

### 5. Get Active Model
```sql
SELECT version, model_path, deployed_at, metrics
FROM model_versions
WHERE is_active = 1;
```

---

## Step 6: Setup for API Development

Once database is verified, you'll create API endpoints (Flask/FastAPI) that connect to this database.

### Python Connection Example (for your API):
```python
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "billbro_mvp.db"

def get_db_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row  # Return rows as dicts
    return conn

# Example: Get all items
def get_all_items():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM items ORDER BY name")
    items = cursor.fetchall()
    conn.close()
    return [dict(row) for row in items]
```

---

## Step 7: Common Operations for Development

### Add New Item
```sql
INSERT INTO items (store_id, name, sku, price, category, expiry_date, low_stock_threshold)
VALUES ('store_001', 'Maggi Noodles', 'MAG001', 15.00, 'snacks', '2026-12-31', 5);

-- Get the inserted ID
SELECT last_insert_rowid() as item_id;

-- Create inventory entry for new item
INSERT INTO inventory (item_id, current_count)
VALUES (7, 50);  -- Replace 7 with actual item_id
```

### Decrement Stock (on checkout)
```sql
UPDATE inventory
SET current_count = current_count - 1,
    last_updated = CURRENT_TIMESTAMP
WHERE item_id = 1;  -- Apple

-- Check if low stock threshold triggered
SELECT 
    i.name, 
    inv.current_count,
    CASE 
        WHEN inv.current_count < i.low_stock_threshold 
        THEN 'LOW_STOCK_ALERT'
        WHEN inv.current_count = 0 
        THEN 'STOCK_OUT_ALERT'
        ELSE 'OK'
    END as alert_status
FROM items i
JOIN inventory inv ON inv.item_id = i.id
WHERE i.id = 1;
```

### Create Alert
```sql
INSERT INTO alerts (store_id, item_id, alert_type, severity, message)
VALUES ('store_001', 1, 'LOW_STOCK', 'warning', 'Apple stock running low: 4 units');
```

### Start Training Job
```sql
INSERT INTO training_jobs (id, item_id, store_id, status, current_epoch, total_epochs)
VALUES ('job_20260807_new', 7, 'store_001', 'pending', 0, 5);
```

### Update Training Progress
```sql
UPDATE training_jobs
SET status = 'running',
    progress = 20,
    current_epoch = 1
WHERE id = 'job_20260807_new';
```

---

## Step 8: Migration to PostgreSQL (Week 6+)

When you're ready to scale beyond MVP, follow these steps:

### Create PostgreSQL Database
```bash
# Install PostgreSQL (if not already installed)
# Then create database:
createdb billbro_prod

# Connect
psql billbro_prod
```

### Adapt Schema
The SQL schema provided works for both SQLite and PostgreSQL. Minor changes needed:
- Replace `AUTOINCREMENT` with `SERIAL`
- Replace `TIMESTAMP DEFAULT CURRENT_TIMESTAMP` with `TIMESTAMP DEFAULT NOW()`
- Use `UUID` for `id` columns instead of `SERIAL` (optional but recommended)

### Migrate Data
```bash
# Export from SQLite
sqlite3 billbro_mvp.db ".dump" > backup.sql

# Import to PostgreSQL
psql billbro_prod -f backup.sql
```

---

## Troubleshooting

### Q: "Database is locked" error
**A:** Close any other connections to the database and try again.

### Q: Foreign key constraint error on insert
**A:** Make sure parent record exists first. For example, insert into `items` before `inventory`.

### Q: Schema file not importing
**A:** Check that file path is correct and file is readable. Try importing line-by-line.

### Q: TablePlus not showing updated data
**A:** Right-click table → **Refresh** or press Cmd+R

### Q: Need to reset database
```sql
-- Drop all tables (careful! data will be deleted)
DROP TABLE IF EXISTS training_jobs;
DROP TABLE IF EXISTS transactions;
DROP TABLE IF EXISTS alerts;
DROP TABLE IF EXISTS training_data;
DROP TABLE IF EXISTS model_versions;
DROP TABLE IF EXISTS inventory;
DROP TABLE IF EXISTS items;

-- Then re-import schema and sample data
```

---

## Next Steps

1. ✅ Database setup complete
2. 📝 Create SQLAlchemy models (Python ORM) → File: `database.py`
3. 🔌 Build Flask/FastAPI endpoints → File: `api/app.py`
4. 🧪 Write unit tests → File: `tests/test_database.py`
5. 🔗 Connect Streamlit frontend to API

---

## Files in Your BE Project Folder

```
BE Project/
├── billbro_mvp.db                      ← Database file (created by TablePlus)
├── billbro_database_schema.sql         ← Schema (all tables & indexes)
├── billbro_sample_data.sql             ← Sample data for testing
├── TABLEPLUS_SETUP_GUIDE.md            ← This file
└── [Future] database.py                ← Python SQLAlchemy models
```

---

## Support

- **TablePlus Docs:** https://tableplus.com/blog
- **SQLite Docs:** https://www.sqlite.org/docs.html
- **PostgreSQL Docs:** https://www.postgresql.org/docs/

Good luck with your database! 🚀
