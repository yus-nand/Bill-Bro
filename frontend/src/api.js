// src/api.js
// Axios client for Person A's backend.
//
// The CONFIRMED section below matches FOR_PERSON_C.md + Person A's
// follow-up (RESPONSE_TO_PERSON_C.md) — real, running API at :8000. The
// PROPOSED section is what API_CONTRACT.md speculated for pages Person A
// hasn't built endpoints for yet — treat those as guesses to confirm, not
// working calls.

import axios from "axios";
import { API_BASE_URL } from "./config.js";

export const client = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
  timeout: 15000,
});

// ─────────────────────────────────────────────────────────────────────────
// CONFIRMED — matches FOR_PERSON_C.md
// ─────────────────────────────────────────────────────────────────────────

// ── Items (product catalog — static info: name, sku, price, category) ────
// Per BillBro_TeamUpdates.md, creation starts an item at status "pending"
// — it only becomes checkout-detectable once training succeeds and it's
// flipped to "shelved" (see the Add Item flow below).
//
// `barcode` — dropped from the frontend by decision, confirmed not part
// of the real schema. Most of the catalog is loose produce with no real
// scannable barcode, and there's no scanner integration, so manual text
// entry wasn't worth it. SKU remains the trustworthy unique identifier.
//
// `batch_number` / `batch_arrival_date` — these WERE briefly confirmed
// removed (SYNC_FOR_PERSON_C.md said no such column existed), but are
// back for real now, found directly in Person A's pushed database.py
// and api_app.py: both are genuine optional columns on `items`. Per his
// own code comments, they're really meant for the new
// PATCH /items/{id}/restock flow below (batch tracking for restocking an
// existing item), not initial creation — CreateItemRequest accepts them
// as optional but nothing in his docs suggests Add Item needs to send
// them. Deliberately NOT re-added to the Add Item form for that reason —
// see restockItem() instead.
export const getItems = () => client.get("/items");
export const getItem = (id) => client.get(`/items/${id}`);
// Sends a JSON body, matching the docs — this was previously broken on
// Person A's side (his handler took scalar args, which FastAPI reads as
// query params, not a JSON body — every real submit would 422). Fixed
// and pushed per SYNC_FOR_PERSON_C.md; no frontend change was needed.
export const createItem = (item) => client.post("/items", item);
// New endpoint, found directly in api_app.py — "a new batch of an
// existing item arrived" (POST /items can't handle this case since sku
// is unique). Overwrites the item's current batch_number/batch_arrival_date
// (no per-batch history — items:inventory is 1:1) and adds quantity_added
// to stock. batchNumber/batchArrivalDate are optional; omit either to
// leave that field untouched.
export const restockItem = (id, quantityAdded, batchNumber, batchArrivalDate) =>
  client.patch(`/items/${id}/restock`, {
    quantity_added: quantityAdded,
    ...(batchNumber && { batch_number: batchNumber }),
    ...(batchArrivalDate && { batch_arrival_date: batchArrivalDate }),
  });

// ── Inventory (stock levels — dynamic, changes with each sale) ──────────
// Confirmed shape: [{ id, name, sku, price, current_count,
// low_stock_threshold, status: "OK"|"LOW_STOCK"|"OUT_OF_STOCK" }]
export const getInventory = () => client.get("/inventory");
export const adjustInventory = (id, quantity, reason) =>
  client.patch(`/inventory/${id}`, { quantity, reason });

// ── Alerts ───────────────────────────────────────────────────────────────
export const getAlerts = () => client.get("/alerts");
// Confirmed: no request body — just PATCH the URL.
// Response: { status: "success", alert: { ...updated alert } }
export const resolveAlert = (id) => client.patch(`/alerts/${id}`);

// ── Detection (Option A, LIVE per FOR_PERSON_C_CHECKOUT_INTEGRATION.md) ──
// Request: { image: "<base64, no data-URL prefix>", confidence_threshold?: number }
// Response: { detections: [{ item_name, confidence, bbox: [x1,y1,x2,y2] }],
//   processing_time_ms }
// Raw, per-instance detections — one entry per detected object. Group them
// into { item_name, confidence, quantity } with utils.js's
// aggregateDetections() before calling processCheckout().
//
// Timeout: Person A's real measured timing is ~2-3s for the first request
// (model load) and ~100-200ms after that — much better than Person B's
// worst-case "~2min on CPU" estimate this was originally set against.
// Keeping a generous-but-not-extreme safety margin rather than either
// extreme.
const DETECT_TIMEOUT_MS = 30000;
export const detectImage = (base64Image, confidenceThreshold) =>
  client.post(
    "/detect",
    {
      image: base64Image,
      ...(confidenceThreshold != null && { confidence_threshold: confidenceThreshold }),
    },
    { timeout: DETECT_TIMEOUT_MS }
  );

// ── Checkout ─────────────────────────────────────────────────────────────
// Request: { detections: [{ item_name, confidence, quantity }, ...] }
// Response: { status, receipt_id, cart: [{ item_id, name, price, quantity,
//   subtotal, confidence }], total, alerts: [] }
export const processCheckout = (detections) =>
  client.post("/checkout/bill", { detections });

// ── Models ───────────────────────────────────────────────────────────────
export const getActiveModel = () => client.get("/models/active");

// ── Health ───────────────────────────────────────────────────────────────
export const getHealth = () => client.get("/health");

// ─────────────────────────────────────────────────────────────────────────
// ADD ITEM / TRAINING — reprioritized as the first feature per
// BillBro_TeamUpdates.md (item → train → shelve, ahead of checkout in the
// new build order). Endpoints are "ready to build" on Person A's side for
// Week 2 (POST /training/upload_images, GET /training/job/{id}) but not
// live yet — calling these will 404 until he ships them.
//
// GET /training/job/{id} response shape is now LOCKED, per
// RESPONSES_TO_PERSON_B_AND_C.md ("Your TrainingJob table alignment: 100%
// locked"): { id, item_id, status: pending|running|success|failed,
// progress: 0-100, current_epoch: "2/5"-style string, metrics,
// error_message, created_at, completed_at }. Note the job's own id field
// is "id" here — "job_id" only appears in the upload endpoint's response
// (the id you get back to start polling with). No longer a guess between
// disagreeing docs; AddItem.jsx's normalizeJobStatus() still reads a
// couple of alternate field names defensively, which is now just belt-
// and-suspenders rather than load-bearing.
// ─────────────────────────────────────────────────────────────────────────

// Found during a full backend audit: this call was missing `item_name`
// entirely — the endpoint requires it (no default) and uses it directly
// as the new class label, so every real call would have 422'd with
// "field required" before a single photo got processed. Also fixed on
// Person A's side: item_id/item_name/store_id are now properly declared
// as Form() fields (they previously had no Form()/Body() annotation at
// all, so FastAPI was reading them as query params instead of the
// multipart form fields actually being sent here).
export const uploadTrainingImages = (itemId, itemName, files, storeId) => {
  const form = new FormData();
  form.append("item_id", itemId);
  form.append("item_name", itemName);
  if (storeId) form.append("store_id", storeId);
  files.forEach((f) => form.append("images", f));
  return client.post("/training/upload_images", form, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 60000, // uploading 15 photos can take a moment on a slow connection
  });
};
export const getTrainingJob = (jobId) => client.get(`/training/job/${jobId}`);

// ─────────────────────────────────────────────────────────────────────────
// PROPOSED — no confirmed endpoint from Person A yet (see API_CONTRACT.md
// "Open questions"). Calling these will 404 until they exist.
// ─────────────────────────────────────────────────────────────────────────

// Admin (Week 7)
export const uploadBulkCsv = (file) => {
  const form = new FormData();
  form.append("file", file);
  return client.post("/admin/bulk_upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
};
export const updateStoreSettings = (settings) =>
  client.put("/admin/settings", settings);

// Model version history / rollback (Week 8) — doc only confirms
// GET /models/active, not a full version list or activate/rollback.
export const getModelVersions = () => client.get("/models");
export const activateModel = (versionId) =>
  client.post(`/models/${versionId}/activate`);
export const rollbackModel = (versionId) =>
  client.post(`/models/${versionId}/rollback`);

// Prices — likely unnecessary now: GET /items already returns `price` per
// item, so there may be no separate prices endpoint to build against.
export const getPrices = () => client.get("/prices");
export const savePrices = (prices) => client.put("/prices", prices);
