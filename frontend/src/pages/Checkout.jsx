// src/pages/Checkout.jsx — replaces pages/checkout.py
// Live: photo → POST /detect → editable cart → POST /checkout/bill → receipt.
// Detection architecture is Person A's confirmed Option A (backend wraps
// Person B's model) — see RESPONSE_TO_PERSON_C_FINAL.md / API_CONTRACT.md.

import { useEffect, useRef, useState } from "react";
import PageShell from "../components/PageShell.jsx";
import { detectImage, processCheckout } from "../api.js";
import { aggregateDetections } from "../utils.js";
import { API_BASE_URL } from "../config.js";

// step: "idle" | "detecting" | "review" | "billing" | "done" | "error"

// Person B's base model (as of the Week 1 delivery) is only trained on
// these six items — worth surfacing so staff know what to expect before
// Week 4's training pipeline adds more.
const SUPPORTED_ITEMS = [
  "Apple",
  "Banana",
  "Dragon Fruit",
  "Custard Apple",
  "Diet Coke",
  "Pepsi",
];

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      // reader.result is a data URL ("data:image/jpeg;base64,...."). The
      // API contract wants the raw base64 payload without that prefix.
      const raw = String(reader.result).split(",")[1] || "";
      resolve(raw);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function titleCase(itemName) {
  return itemName.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function Checkout() {
  const fileInputRef = useRef(null);
  const [preview, setPreview] = useState(null);
  const [step, setStep] = useState("idle");
  const [errorMessage, setErrorMessage] = useState("");
  const [cart, setCart] = useState([]); // [{ item_name, confidence, quantity }]
  const [processingTimeMs, setProcessingTimeMs] = useState(null);
  const [receipt, setReceipt] = useState(null);
  const [detectingElapsedSec, setDetectingElapsedSec] = useState(0);

  // Person B's delivery notes flag no default GPU acceleration — detection
  // can take up to ~2 minutes per image on CPU. Surface that once the wait
  // gets long instead of leaving staff staring at a bare "Detecting…".
  useEffect(() => {
    if (step !== "detecting") {
      setDetectingElapsedSec(0);
      return;
    }
    const id = setInterval(() => setDetectingElapsedSec((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, [step]);

  const reset = () => {
    setPreview(null);
    setStep("idle");
    setErrorMessage("");
    setCart([]);
    setProcessingTimeMs(null);
    setReceipt(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setPreview(URL.createObjectURL(file));
    setStep("detecting");
    setErrorMessage("");

    try {
      const base64 = await fileToBase64(file);
      const res = await detectImage(base64);
      const detections = res.data.detections || [];
      setProcessingTimeMs(res.data.processing_time_ms ?? null);
      setCart(aggregateDetections(detections));
      setStep("review");
    } catch (err) {
      setErrorMessage(
        err?.response?.data?.detail ||
          `Couldn't reach POST /detect at ${API_BASE_URL} — is the backend running?`
      );
      setStep("error");
    }
  };

  const updateQuantity = (itemName, delta) => {
    setCart((prev) =>
      prev
        .map((row) =>
          row.item_name === itemName
            ? { ...row, quantity: Math.max(0, row.quantity + delta) }
            : row
        )
        .filter((row) => row.quantity > 0)
    );
  };

  const handleBill = async () => {
    setStep("billing");
    setErrorMessage("");
    try {
      const res = await processCheckout(cart);
      setReceipt(res.data);
      setStep("done");
    } catch (err) {
      setErrorMessage(
        err?.response?.data?.detail ||
          `Couldn't reach POST /checkout/bill at ${API_BASE_URL}.`
      );
      setStep("error");
    }
  };

  const statusMessage =
    step === "idle"
      ? "Take or upload a photo of the cart to get started."
      : step === "detecting"
      ? detectingElapsedSec < 5
        ? "Detecting items…"
        : `Still detecting (${detectingElapsedSec}s) — the first request of a session loads the model and takes a few seconds longer.`
      : step === "review"
      ? `Found ${cart.length} item type${cart.length === 1 ? "" : "s"}${
          processingTimeMs != null ? ` in ${processingTimeMs}ms` : ""
        } — check quantities before billing.`
      : step === "billing"
      ? "Processing bill…"
      : step === "done"
      ? `Billed — receipt ${receipt?.receipt_id ?? ""}.`
      : `Something went wrong: ${errorMessage}`;

  return (
    <PageShell
      group="Store Operations"
      icon="🛒"
      title="Checkout"
      caption="Scan items, build the cart, and print the receipt."
      status={statusMessage}
    >
      {step === "idle" && (
        <div className="bb-card bb-checkout-upload">
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            capture="environment"
            onChange={handleFileChange}
            id="checkout-photo-input"
            className="bb-visually-hidden"
          />
          <label htmlFor="checkout-photo-input" className="bb-btn bb-btn-primary">
            📷 Take or upload a photo
          </label>
          <p className="bb-caption" style={{ marginTop: 14, marginBottom: 0 }}>
            Detectable right now: {SUPPORTED_ITEMS.join(", ")}. More items
            arrive as they're trained in (Week 4+).
          </p>
        </div>
      )}

      {preview && step !== "idle" && (
        <div className="bb-card bb-checkout-preview">
          <img src={preview} alt="Cart preview" />
        </div>
      )}

      {step === "review" && (
        <div className="bb-card">
          {cart.length === 0 ? (
            <p className="bb-caption" style={{ margin: 0 }}>
              No items detected — try another photo.
            </p>
          ) : (
            <ul className="bb-cart-list">
              {cart.map((row) => (
                <li className="bb-cart-item" key={row.item_name}>
                  <div>
                    <p className="bb-cart-item-name">{titleCase(row.item_name)}</p>
                    <p className="bb-alert-meta">
                      {Math.round(row.confidence * 100)}% confidence
                    </p>
                  </div>
                  <div className="bb-qty-stepper">
                    <button type="button" onClick={() => updateQuantity(row.item_name, -1)}>
                      −
                    </button>
                    <span>{row.quantity}</span>
                    <button type="button" onClick={() => updateQuantity(row.item_name, 1)}>
                      +
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
          <div className="bb-checkout-actions">
            <button type="button" className="bb-btn bb-btn-secondary" onClick={reset}>
              Retake photo
            </button>
            <button
              type="button"
              className="bb-btn bb-btn-primary"
              onClick={handleBill}
              disabled={cart.length === 0}
            >
              Complete bill
            </button>
          </div>
        </div>
      )}

      {step === "done" && receipt && (
        <div className="bb-card">
          <div className="total-banner">₹{Number(receipt.total).toFixed(2)}</div>
          <ul className="bb-cart-list">
            {(receipt.cart || []).map((li) => (
              <li className="bb-cart-item" key={li.item_id ?? li.name}>
                <div>
                  <p className="bb-cart-item-name">{li.name}</p>
                  <p className="bb-alert-meta">
                    {li.quantity} × ₹{Number(li.price).toFixed(2)}
                  </p>
                </div>
                <p className="bb-cart-item-name">₹{Number(li.subtotal).toFixed(2)}</p>
              </li>
            ))}
          </ul>
          {receipt.alerts && receipt.alerts.length > 0 && (
            <p className="bb-caption">
              {receipt.alerts.length} new alert{receipt.alerts.length === 1 ? "" : "s"}{" "}
              triggered by this sale — check the Alerts page.
            </p>
          )}
          <div className="bb-checkout-actions">
            <button type="button" className="bb-btn bb-btn-primary" onClick={reset}>
              New checkout
            </button>
          </div>
        </div>
      )}

      {step === "error" && (
        <div className="bb-checkout-actions">
          <button type="button" className="bb-btn bb-btn-secondary" onClick={reset}>
            Try again
          </button>
        </div>
      )}
    </PageShell>
  );
}
