-- BillBro Sample Data for MVP Testing
-- Use this to populate database after schema creation
-- Store: store_001 (Test Store)

-- Insert sample items (base model: apple, banana, dragonfruit, custard_apple, diet_coke, pepsi)
-- status='shelved' explicitly: these are pre-trained into the base
-- model, not added via the Add Item -> Train -> Shelve pipeline, so they
-- should be immediately checkout-detectable rather than sitting at the
-- schema's 'pending' default (which would make POST /checkout/bill
-- silently reject all six of them).
INSERT INTO items (store_id, name, sku, price, category, expiry_date, low_stock_threshold, status) VALUES
('store_001', 'Apple', 'APL001', 35.00, 'fruits', '2026-09-15', 5, 'shelved'),
('store_001', 'Banana', 'BAN001', 25.00, 'fruits', '2026-08-12', 10, 'shelved'),
('store_001', 'Dragon Fruit', 'DRF001', 120.00, 'fruits', '2026-08-20', 3, 'shelved'),
('store_001', 'Custard Apple', 'CUS001', 80.00, 'fruits', '2026-08-25', 4, 'shelved'),
('store_001', 'Diet Coke', 'DCK001', 50.00, 'beverages', '2026-12-31', 10, 'shelved'),
('store_001', 'Pepsi', 'PEP001', 50.00, 'beverages', '2026-12-15', 10, 'shelved');

-- Insert inventory levels
INSERT INTO inventory (item_id, current_count) VALUES
(1, 47),  -- Apple: 47 units
(2, 19),  -- Banana: 19 units
(3, 8),   -- Dragon Fruit: 8 units
(4, 12),  -- Custard Apple: 12 units
(5, 99),  -- Diet Coke: 99 units
(6, 85);  -- Pepsi: 85 units

-- Insert sample alerts
INSERT INTO alerts (store_id, item_id, alert_type, severity, message, resolved) VALUES
('store_001', 2, 'LOW_STOCK', 'warning', 'Banana stock running low: 19 units', 0),
('store_001', 3, 'LOW_STOCK', 'warning', 'Dragon Fruit stock running low: 8 units', 0),
('store_001', 4, 'LOW_STOCK', 'warning', 'Custard Apple stock running low: 12 units', 0);

-- Insert base model version
INSERT INTO model_versions (store_id, version, model_path, metrics, is_active, trained_at, deployed_at) VALUES
('store_001', 'v1', 'models/store_001_v1.pt', '{"mAP50": 0.92, "mAP": 0.87, "accuracy": 0.90}', 1, '2026-08-01 09:00:00', '2026-08-01 09:20:00');

-- Insert sample training data (images captured)
INSERT INTO training_data (item_id, image_path, bbox_coordinates, labeled_by) VALUES
(1, 'images/apple_001.jpg', '[[50,50,150,150]]', 'auto'),
(1, 'images/apple_002.jpg', '[[60,40,160,160]]', 'auto'),
(2, 'images/banana_001.jpg', '[[30,80,130,200]]', 'auto'),
(5, 'images/diet_coke_001.jpg', '[[100,50,180,200]]', 'auto'),
(5, 'images/diet_coke_002.jpg', '[[90,60,170,210]]', 'auto');

-- Insert sample transactions
INSERT INTO transactions (store_id, receipt_id, total_amount, items_json, status) VALUES
('store_001', 'RCP_20260807_001', 185.00, '[{"item_id":1,"name":"Apple","price":35.00,"quantity":2,"confidence":0.95},{"item_id":5,"name":"Diet Coke","price":50.00,"quantity":2,"confidence":0.92}]', 'completed'),
('store_001', 'RCP_20260807_002', 150.00, '[{"item_id":2,"name":"Banana","price":25.00,"quantity":3,"confidence":0.88}]', 'completed'),
('store_001', 'RCP_20260807_003', 235.00, '[{"item_id":3,"name":"Dragon Fruit","price":120.00,"quantity":1,"confidence":0.91},{"item_id":6,"name":"Pepsi","price":50.00,"quantity":2,"confidence":0.94}]', 'completed');

-- Insert sample training job
INSERT INTO training_jobs (id, item_id, store_id, status, progress, current_epoch, total_epochs, accuracy, model_version, created_at) VALUES
('job_20260807_001', NULL, 'store_001', 'success', 100, 5, 5, 0.88, 'v2', '2026-08-07 10:00:00');
