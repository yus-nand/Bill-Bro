// src/utils.js
// Ported from utils.py. Only the pure, environment-agnostic logic moves to
// the browser — image preprocessing and model inference in predict.py stay
// server-side (whatever detection model Person A settles on) and are
// reached via api.js instead.

// ─── Price lookups ─────────────────────────────────────────────────────────
// utils.py's load_prices()/save_prices() read/write a local prices.json file.
// In the React app that file lives on the backend, so use api.js
// (getPrices / savePrices) instead of a local file read.

export function getPrice(itemName, prices, fallback = 0.0) {
  const key = itemName.toLowerCase().replace(/ /g, "_");
  return prices?.[key] ?? fallback;
}

// ─── Cart operations ────────────────────────────────────────────────────────

/**
 * Aggregate detections into a cart (item → count).
 * @param {Array<{name: string, confidence: number, box: number[]}>} detections
 * @returns {Record<string, number>}
 */
export function buildCart(detections) {
  const cart = {};
  for (const { name } of detections) {
    cart[name] = (cart[name] || 0) + 1;
  }
  return cart;
}

export function mergeCarts(existing, newItems) {
  const merged = { ...existing };
  for (const [item, count] of Object.entries(newItems)) {
    merged[item] = (merged[item] || 0) + count;
  }
  return merged;
}

export function removeItem(cart, item, quantity = 1) {
  const next = { ...cart };
  if (item in next) {
    next[item] = Math.max(0, next[item] - quantity);
    if (next[item] === 0) delete next[item];
  }
  return next;
}

/**
 * Group raw per-instance detections from POST /detect —
 * [{ item_name, confidence, bbox }, ...], one entry per detected object —
 * into the { item_name, confidence, quantity } shape POST /checkout/bill
 * expects. Per-item confidence is the average across that item's
 * detections (Person A's doc doesn't say how to pick one, so this is a
 * reasonable default — adjust if he confirms otherwise).
 */
export function aggregateDetections(rawDetections) {
  const groups = {};
  for (const d of rawDetections) {
    const key = d.item_name;
    if (!groups[key]) groups[key] = { item_name: key, quantity: 0, confidenceSum: 0 };
    groups[key].quantity += 1;
    groups[key].confidenceSum += d.confidence;
  }
  return Object.values(groups).map((g) => ({
    item_name: g.item_name,
    quantity: g.quantity,
    confidence: Math.round((g.confidenceSum / g.quantity) * 1000) / 1000,
  }));
}

/**
 * Calculate subtotals, tax, and grand total.
 * @returns {{ lineItems: Array, subtotal: number, tax: number, total: number }}
 */
export function calculateTotal(cart, prices, taxRate = 0.0) {
  const lineItems = [];
  let subtotal = 0;

  for (const item of Object.keys(cart).sort()) {
    const qty = cart[item];
    const unitPrice = getPrice(item, prices);
    const sub = unitPrice * qty;
    subtotal += sub;
    lineItems.push({
      name: item.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
      qty,
      unitPrice,
      subtotal: sub,
    });
  }

  const tax = subtotal * taxRate;
  const total = subtotal + tax;

  return {
    lineItems,
    subtotal: Math.round(subtotal * 100) / 100,
    tax: Math.round(tax * 100) / 100,
    total: Math.round(total * 100) / 100,
  };
}

// ─── Receipt formatting ─────────────────────────────────────────────────────

export const STORE_NAME = "Smart Mart";
export const STORE_ADDRESS = "123 Vision Street, Mumbai";
export const STORE_PHONE = "+91 98765 43210";

function center(str, width) {
  const pad = Math.max(width - str.length, 0);
  const left = Math.floor(pad / 2);
  const right = pad - left;
  return " ".repeat(left) + str + " ".repeat(right);
}

function receiptNumber() {
  return `RC${Math.floor(100000 + Math.random() * 900000)}`;
}

/**
 * Generate a plain-text receipt string (same layout as format_receipt()).
 */
export function formatReceipt(cart, prices, taxRate = 0.05, width = 40) {
  const sep = "─".repeat(width);
  const dsep = "═".repeat(width);
  const now = new Date().toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  const lines = [
    dsep,
    center(STORE_NAME, width),
    center(STORE_ADDRESS, width),
    center(STORE_PHONE, width),
    dsep,
    center(`Date: ${now}`, width),
    center(`Receipt #: ${receiptNumber()}`, width),
    sep,
    "ITEM".padEnd(22) + "QTY".padStart(4) + "PRICE".padStart(7) + "AMT".padStart(7),
    sep,
  ];

  const bill = calculateTotal(cart, prices, taxRate);

  for (const li of bill.lineItems) {
    const name = li.name.slice(0, 20);
    lines.push(
      name.padEnd(22) +
        String(li.qty).padStart(4) +
        li.unitPrice.toFixed(2).padStart(7) +
        li.subtotal.toFixed(2).padStart(7)
    );
    if (li.unitPrice === 0) {
      lines.push("  * Price not found - assumed Rs.0.00");
    }
  }

  const subtotalStr = `Rs.${bill.subtotal.toFixed(2)}`;
  const taxStr = `Rs.${bill.tax.toFixed(2)}`;
  const totalStr = `Rs.${bill.total.toFixed(2)}`;
  const taxLabel = `GST (${Math.round(taxRate * 100)}%)`;

  lines.push(
    sep,
    "Subtotal".padEnd(28) + subtotalStr.padStart(12),
    taxLabel.padEnd(28) + taxStr.padStart(12),
    dsep,
    "TOTAL".padEnd(28) + totalStr.padStart(12),
    dsep,
    "",
    center("Thank you for shopping at Smart Mart!", width),
    center("Powered by Computer Vision", width),
    dsep
  );

  return lines.join("\n");
}

// ─── Stats & analytics ──────────────────────────────────────────────────────

export function detectionSummary(detections) {
  const counts = {};
  for (const { name } of detections) {
    counts[name] = (counts[name] || 0) + 1;
  }
  return {
    total: detections.length,
    uniqueItems: Object.keys(counts).length,
    byClass: counts,
  };
}

export function confidenceStats(detections) {
  if (!detections.length) return { mean: 0, min: 0, max: 0 };
  const confs = detections.map((d) => d.confidence);
  const round3 = (n) => Math.round(n * 1000) / 1000;
  return {
    mean: round3(confs.reduce((a, b) => a + b, 0) / confs.length),
    min: round3(Math.min(...confs)),
    max: round3(Math.max(...confs)),
  };
}
