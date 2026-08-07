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
// Per BillBro_TeamUpdates.md, items also carry `batch_number`, and
// creation starts an item at status "pending" — it only becomes
// checkout-detectable once training succeeds and it's flipped to
// "shelved" (see the Add Item flow below). `barcode` was in the original
// schema note too, but was dropped from the frontend by decision — most
// of the catalog is loose produce that doesn't have real scannable
// barcodes, and manual text entry (no scanner integration exists) isn't
// reliable enough to be worth the field. SKU remains the trustworthy
// unique identifier.
export const getItems = () => client.get("/items");
export const getItem = (id) => client.get(`/items/${id}`);
export const createItem = (item) => client.post("/items", item);

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
// new build order). Endpoints aren't live on Person A's API yet, but the
// shapes are reasonably well documented — just from two DOCS THAT DISAGREE
// WITH EACH OTHER:
//   - BillBro_TeamUpdates.md's TrainingJob table: { id, item_id, status,
//     progress, current_epoch, metrics, error_message, created_at, completed_at }
//   - PERSON_B_DELIVERABLES_ANALYSIS.md's job status file: { job_id, status,
//     progress, stage, epoch, metrics, updated_at }
// Different field names for what's presumably the same thing. Until Person
// A confirms which one his endpoint actually returns, getTrainingJob()'s
// caller (AddItem.jsx) reads both possible field names defensively.
// ─────────────────────────────────────────────────────────────────────────

export const uploadTrainingImages = (itemId, files, storeId) => {
  const form = new FormData();
  form.append("item_id", itemId);
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
