// src/pages/Checkout.jsx — replaces pages/checkout.py
// Live: photo → POST /detect → editable cart → POST /checkout/bill → receipt.
// Detection architecture is Person A's confirmed Option A (backend wraps
// Person B's model) — see RESPONSE_TO_PERSON_C_FINAL.md / API_CONTRACT.md.

import { useEffect, useRef, useState } from "react";
import PageShell from "../components/PageShell.jsx";
import { detectImage, processCheckout } from "../api.js";
import { aggregateDetections } from "../utils.js";
import { API_BASE_URL } from "../config.js";

// step: "idle" | "camera" | "detecting" | "review" | "billing" | "done" | "error"

// How often the live camera view sends a frame to /detect. 2s gives real
// inference (measured ~600ms-1s on CPU in testing) comfortable room to
// finish before the next frame fires — the in-flight guard below still
// protects against a genuinely slow call overlapping the next tick, but
// this interval keeps that the exception rather than the norm.
const LIVE_DETECT_INTERVAL_MS = 2000;

// Backend defaults confidence_threshold to 0.5 when omitted (same value
// as DEFAULT_CONF_THRESHOLD in config.js). Live mode uses a lower bar —
// found via real testing that a handheld, off-angle, glare-y camera
// frame is a much harder case than the framed, well-lit photos the
// model was trained on, and real detections were landing in the
// 0.3-0.49 range, just under the standard cutoff, showing up as "0
// items" even when the model had genuinely recognized something. The
// one-shot file-upload path deliberately keeps the standard 0.5 — a
// deliberately-taken photo doesn't need the same leniency, and a lower
// bar there would mean more false positives on a photo the user can't
// as easily just retry a second later like they can with the live feed.
const LIVE_CONF_THRESHOLD = 0.25;

// Person B's model is trained on six items. Pepsi WAS unusable (AP50
// 0.000 — a dataset gap, only a generic soda-can in the source data),
// but per TRAINING_RESULTS.md the retrain fixed it for real: AP50 0.885,
// precision 0.944, recall 0.780. Genuinely a working class now, not the
// old workaround. Per Person B's explicit recommendation, softening
// this warning rather than removing it — recall 0.78 means it'll still
// miss roughly 1 in 5 real cans (smallest val set of the six classes),
// so still worth a heads-up, just not "don't trust it" anymore.
const RELIABLE_ITEMS = ["Apple", "Banana", "Dragon Fruit", "Custard Apple", "Diet Coke"];
const UNRELIABLE_ITEM_NOTE = "Pepsi detection has improved a lot, but still misses roughly 1 in 5 cans — slightly less reliable than the other five.";

// Found via real device testing: iPhones default to HEIC for photos
// (both the Photos library and, on some iOS/browser combos, the
// camera-capture flow this page's "Take or upload a photo" button
// triggers). The browser can preview/display HEIC fine, which made this
// look like a backend bug at first — but the raw bytes sent straight
// through were still HEIC, and the backend's decoder (OpenCV's
// cv2.imdecode) only understands JPEG/PNG/BMP/etc., not HEIC. It failed
// with "Could not decode base64 image" — a real, confusing error since
// the photo displayed correctly in this same page's preview right above
// it. Fixed by always re-encoding through a <canvas> to JPEG before
// base64-ing, regardless of the source format — sidesteps HEIC (and any
// other format cv2 can't read) entirely, and as a bonus shrinks the
// payload (HEIC photos from modern iPhones can be several MB).
function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    const objectUrl = URL.createObjectURL(file);

    img.onload = () => {
      URL.revokeObjectURL(objectUrl);
      const canvas = document.createElement("canvas");
      canvas.width = img.naturalWidth;
      canvas.height = img.naturalHeight;
      const ctx = canvas.getContext("2d");
      ctx.drawImage(img, 0, 0);
      // toDataURL always re-encodes to the requested type regardless of
      // the source format, so this is what actually normalizes HEIC (or
      // anything else) into something cv2.imdecode can read.
      const dataUrl = canvas.toDataURL("image/jpeg", 0.9);
      const raw = dataUrl.split(",")[1] || "";
      resolve(raw);
    };
    img.onerror = () => {
      URL.revokeObjectURL(objectUrl);
      reject(
        new Error(
          "Couldn't read this photo — the format may not be supported by this browser. Try a JPEG or PNG instead."
        )
      );
    };
    img.src = objectUrl;
  });
}

function titleCase(itemName) {
  return itemName.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

// Grabs the current frame of a <video> element and re-encodes it as a
// JPEG data URL, same output shape fileToBase64() produces from a
// <canvas> — this is what lets the webcam path reuse runDetection()
// below instead of needing its own separate /detect call + error
// handling.
function videoFrameToBase64(video) {
  const canvas = document.createElement("canvas");
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(video, 0, 0);
  const dataUrl = canvas.toDataURL("image/jpeg", 0.9);
  return dataUrl.split(",")[1] || "";
}

export default function Checkout() {
  const fileInputRef = useRef(null);
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const liveIntervalRef = useRef(null);
  // Guards against overlapping /detect calls if a frame's inference takes
  // longer than LIVE_DETECT_INTERVAL_MS — the interval tick checks this
  // and skips firing a new request rather than piling one on top of an
  // in-flight one (which could otherwise let an older, slower response
  // land AFTER a newer one and briefly show stale detections).
  const liveRequestInFlightRef = useRef(false);
  const [preview, setPreview] = useState(null);
  const [step, setStep] = useState("idle");
  const [errorMessage, setErrorMessage] = useState("");
  const [cart, setCart] = useState([]); // [{ item_name, confidence, quantity }]
  const [processingTimeMs, setProcessingTimeMs] = useState(null);
  const [receipt, setReceipt] = useState(null);
  const [detectingElapsedSec, setDetectingElapsedSec] = useState(0);
  const [cameraError, setCameraError] = useState("");
  const [liveDetecting, setLiveDetecting] = useState(false); // true while a live-mode /detect call is in flight, for a small non-blocking indicator

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

  // Webcam stream is a real resource — if it's left running after the
  // user navigates away, retakes, or the component unmounts, the camera
  // light stays on and the browser keeps holding the device. Centralized
  // here so every exit path (reset, unmount, error, lock-cart) can call
  // it. Also clears the live-detection interval, since a stopped stream
  // with a still-running interval would just throw on the next tick.
  const stopCamera = () => {
    if (liveIntervalRef.current) {
      clearInterval(liveIntervalRef.current);
      liveIntervalRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    liveRequestInFlightRef.current = false;
    setLiveDetecting(false);
  };

  useEffect(() => {
    // Belt-and-suspenders: also stop the camera if the whole page
    // unmounts while step === "camera" (e.g. navigating to a different
    // page mid-scan), not just on the explicit reset()/lock-cart paths.
    return () => stopCamera();
  }, []);

  const reset = () => {
    stopCamera();
    setCameraError("");
    setPreview(null);
    setStep("idle");
    setErrorMessage("");
    setCart([]);
    setProcessingTimeMs(null);
    setReceipt(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  // Shared by the file-upload path AND the one-off first call before live
  // mode starts looping — takes a base64 JPEG payload (already normalized
  // by fileToBase64/videoFrameToBase64) and runs it through /detect, with
  // the "detecting" step transition + elapsed-time messaging the upload
  // flow relies on. Live mode's recurring ticks use runLiveDetection()
  // below instead, which shares the same /detect call but skips this
  // step-transition dance since the camera view itself stays mounted the
  // whole time.
  const runDetection = async (base64) => {
    setStep("detecting");
    setErrorMessage("");
    try {
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

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setPreview(URL.createObjectURL(file));
    const base64 = await fileToBase64(file).catch((err) => {
      setErrorMessage(err.message);
      setStep("error");
      return null;
    });
    if (base64 != null) await runDetection(base64);
  };

  // One tick of the live-detection loop: grab the current video frame,
  // send it, replace the cart with whatever this frame shows. Stays on
  // step "camera" throughout — no step transitions, since the video feed
  // itself is the persistent UI, not a one-shot preview image. The
  // in-flight guard means a slow response just gets skipped over by the
  // next tick rather than queuing up, so the cart always reflects a
  // reasonably recent frame, never a backlog of stale ones.
  const runLiveDetectionTick = async () => {
    if (liveRequestInFlightRef.current || !videoRef.current) return;
    liveRequestInFlightRef.current = true;
    setLiveDetecting(true);
    try {
      const base64 = videoFrameToBase64(videoRef.current);
      const res = await detectImage(base64, LIVE_CONF_THRESHOLD);
      const detections = res.data.detections || [];
      setProcessingTimeMs(res.data.processing_time_ms ?? null);
      setCart(aggregateDetections(detections));
      setErrorMessage("");
    } catch (err) {
      // A single failed tick (e.g. one dropped network blip) shouldn't
      // kill the whole live session — just surface it quietly and let
      // the next tick try again, rather than bouncing to the full-page
      // "error" step like the one-shot upload/capture flows do.
      setErrorMessage(
        err?.response?.data?.detail || "Live detection is having trouble reaching the backend."
      );
    } finally {
      liveRequestInFlightRef.current = false;
      setLiveDetecting(false);
    }
  };

  const openCamera = async () => {
    setCameraError("");
    setErrorMessage("");
    setCart([]);
    setStep("camera");
    try {
      // facingMode "environment" prefers the rear/world-facing camera on
      // phones/tablets (matches the existing file input's capture=
      // "environment" hint) — on a laptop with just one camera, browsers
      // fall back to whatever's available rather than failing.
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment" },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      // Fire one tick immediately rather than waiting the full interval
      // for the first result, then keep going every LIVE_DETECT_INTERVAL_MS.
      runLiveDetectionTick();
      liveIntervalRef.current = setInterval(runLiveDetectionTick, LIVE_DETECT_INTERVAL_MS);
    } catch (err) {
      // Common real causes: user denied the permission prompt, no camera
      // present, or (on non-HTTPS/non-localhost origins) the browser
      // blocks getUserMedia entirely — surface something more useful
      // than the raw DOMException name where possible.
      const reason =
        err?.name === "NotAllowedError"
          ? "Camera access was denied. Allow camera permission for this site and try again."
          : err?.name === "NotFoundError"
          ? "No camera was found on this device."
          : err?.message || "Couldn't access the camera.";
      setCameraError(reason);
      setStep("idle");
    }
  };

  // "Lock cart" — freezes whatever the live view currently shows and
  // moves to the same review/adjust/bill flow the upload path already
  // has, rather than being a separate parallel flow. Grabs one more
  // frame for the static preview image shown on the review screen, so
  // what's displayed there matches the cart being locked in.
  const lockCart = () => {
    if (videoRef.current) {
      const base64 = videoFrameToBase64(videoRef.current);
      setPreview(`data:image/jpeg;base64,${base64}`);
    }
    stopCamera();
    setStep("review");
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
      : step === "camera"
      ? cart.length === 0
        ? "Point the camera at items — the cart updates automatically."
        : `Seeing ${cart.length} item type${cart.length === 1 ? "" : "s"} right now — lock the cart when ready.`
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
          <div className="bb-checkout-actions" style={{ justifyContent: "center" }}>
            <label htmlFor="checkout-photo-input" className="bb-btn bb-btn-primary">
              📷 Take or upload a photo
            </label>
            <button type="button" className="bb-btn bb-btn-secondary" onClick={openCamera}>
              🎥 Use webcam
            </button>
          </div>
          {cameraError && (
            <p className="bb-caption" style={{ marginTop: 10, marginBottom: 0 }}>
              ⚠️ {cameraError}
            </p>
          )}
          <p className="bb-caption" style={{ marginTop: 14, marginBottom: 4 }}>
            Reliably detectable right now: {RELIABLE_ITEMS.join(", ")}. More
            items arrive as they're trained in.
          </p>
          <p className="bb-caption" style={{ marginTop: 0, marginBottom: 0 }}>
            ⚠️ {UNRELIABLE_ITEM_NOTE}
          </p>
        </div>
      )}

      {step === "camera" && (
        <div className="bb-card bb-checkout-preview">
          <div className="bb-webcam-wrap">
            {/* muted + playsInline required for autoplay to actually work
                across browsers, especially Safari/iOS — a video element
                with sound or without playsInline can get silently blocked
                from playing until the user interacts with the page again. */}
            <video ref={videoRef} autoPlay playsInline muted className="bb-webcam-video" />
            <span
              className={`bb-live-dot ${liveDetecting ? "bb-live-dot-active" : ""}`}
              title={liveDetecting ? "Detecting…" : "Live"}
            />
          </div>

          {cart.length > 0 ? (
            <ul className="bb-cart-list">
              {cart.map((row) => (
                <li className="bb-cart-item" key={row.item_name}>
                  <div>
                    <p className="bb-cart-item-name">{titleCase(row.item_name)}</p>
                    <p className="bb-alert-meta">
                      {Math.round(row.confidence * 100)}% confidence
                    </p>
                  </div>
                  <span className="bb-cart-item-name">×{row.quantity}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="bb-caption" style={{ margin: "0 0 14px" }}>
              Nothing recognized yet — hold an item steady in view.
            </p>
          )}

          {errorMessage && (
            <p className="bb-caption" style={{ marginBottom: 10 }}>
              ⚠️ {errorMessage}
            </p>
          )}

          <div className="bb-checkout-actions">
            <button type="button" className="bb-btn bb-btn-secondary" onClick={reset}>
              Cancel
            </button>
            <button
              type="button"
              className="bb-btn bb-btn-primary"
              onClick={lockCart}
              disabled={cart.length === 0}
            >
              🔒 Lock cart
            </button>
          </div>
        </div>
      )}

      {preview && step !== "idle" && step !== "camera" && (
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
