// src/pages/AddItem.jsx — replaces pages/add_item.py
// Reprioritized as the first core feature per BillBro_TeamUpdates.md:
// item details → capture photos → train → shelve. An item only becomes
// checkout-detectable once it's "shelved" (training succeeded).
//
// All three endpoints (POST /items, POST /training/upload_images,
// GET /training/job/{id}) are live on Person A's side now.

import { useEffect, useRef, useState } from "react";
import PageShell from "../components/PageShell.jsx";
import { createItem, uploadTrainingImages, getTrainingJob } from "../api.js";
import { STORE_ID, API_BASE_URL } from "../config.js";

// step: "details" | "capture" | "training" | "shelved" | "failed"

const RECOMMENDED_PHOTOS = 15;
const MIN_PHOTOS = 5;
const POLL_INTERVAL_MS = 5000;

// training.py uses this directly as the new model class label (e.g.
// "Maggi Noodles" -> "maggi_noodles") — found missing entirely during a
// backend audit; uploadTrainingImages() never sent it before, which
// would have 422'd instantly since the backend requires it.
function toClassName(name) {
  return name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

// Confirmed locked per RESPONSES_TO_PERSON_B_AND_C.md: status is one of
// pending | running | success | failed. Kept a couple of extra synonyms
// in these sets (complete/completed/shelved/error) as harmless safety —
// doesn't hurt if the real value only ever matches the primary one.
const SUCCESS_STATUSES = new Set(["success", "complete", "completed", "shelved"]);
const FAILURE_STATUSES = new Set(["failed", "error"]);

// Field names are now locked (RESPONSES_TO_PERSON_B_AND_C.md — Person A's
// "100% locked" TrainingJob alignment table), not a guess between
// conflicting docs anymore: status, progress, current_epoch (string like
// "2/5"), metrics, error_message, created_at, completed_at. Note the
// job's own id field in this response is called "id", not "job_id" (that
// name is only used in the upload response). The ?? fallbacks below are
// kept as harmless extra safety, not because the shape is still unclear.
function normalizeJobStatus(raw) {
  return {
    status: raw.status,
    progress: raw.progress ?? raw.progress_percent ?? 0,
    epoch: raw.current_epoch ?? raw.epoch ?? null,
    stage: raw.stage ?? null,
    metrics: raw.metrics ?? null,
    errorMessage: raw.error_message ?? raw.reason ?? null,
  };
}

// barcode and batch_number were both once planned fields (per
// BillBro_TeamUpdates.md) but neither survived contact with the real
// backend: barcode was dropped by frontend decision (see api.js), and
// batch_number was confirmed by Person A (reading database.py directly,
// via SYNC_FOR_PERSON_C.md) to not exist as a column on the items table
// at all — so it's gone from the form too now.
const emptyForm = {
  name: "",
  sku: "",
  price: "",
  category: "",
  expiry_date: "",
  low_stock_threshold: "5",
};

export default function AddItem() {
  const fileInputRef = useRef(null);
  const pollRef = useRef(null);
  const elapsedRef = useRef(null);

  const [step, setStep] = useState("details");
  const [form, setForm] = useState(emptyForm);
  const [formError, setFormError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const [itemId, setItemId] = useState(null);
  const [images, setImages] = useState([]); // [{ file, previewUrl }]
  const [uploadError, setUploadError] = useState("");

  const [jobId, setJobId] = useState(null);
  const [job, setJob] = useState(null); // normalized
  const [pollError, setPollError] = useState("");
  const [elapsedSec, setElapsedSec] = useState(0);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      if (elapsedRef.current) clearInterval(elapsedRef.current);
      images.forEach((img) => URL.revokeObjectURL(img.previewUrl));
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const resetAll = () => {
    if (pollRef.current) clearInterval(pollRef.current);
    if (elapsedRef.current) clearInterval(elapsedRef.current);
    images.forEach((img) => URL.revokeObjectURL(img.previewUrl));
    setStep("details");
    setForm(emptyForm);
    setFormError("");
    setItemId(null);
    setImages([]);
    setUploadError("");
    setJobId(null);
    setJob(null);
    setPollError("");
    setElapsedSec(0);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const updateField = (field) => (e) =>
    setForm((f) => ({ ...f, [field]: e.target.value }));

  const handleCreateItem = async (e) => {
    e.preventDefault();
    setFormError("");

    if (!form.name.trim() || !form.sku.trim() || !form.price) {
      setFormError("Name, SKU, and price are required.");
      return;
    }

    setSubmitting(true);
    try {
      const payload = {
        name: form.name.trim(),
        sku: form.sku.trim(),
        price: Number(form.price),
        low_stock_threshold: form.low_stock_threshold
          ? Number(form.low_stock_threshold)
          : 5,
        ...(form.category && { category: form.category.trim() }),
        ...(form.expiry_date && { expiry_date: form.expiry_date }),
      };
      const res = await createItem(payload);
      const newItemId = res.data.item_id ?? res.data.item?.id ?? res.data.id;
      setItemId(newItemId);
      setStep("capture");
    } catch (err) {
      setFormError(
        err?.response?.data?.detail ||
          `Couldn't reach POST /items at ${API_BASE_URL} — is the backend running?`
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleAddPhotos = (e) => {
    const files = Array.from(e.target.files || []);
    setImages((prev) => [
      ...prev,
      ...files.map((file) => ({ file, previewUrl: URL.createObjectURL(file) })),
    ]);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const removePhoto = (index) => {
    setImages((prev) => {
      URL.revokeObjectURL(prev[index].previewUrl);
      return prev.filter((_, i) => i !== index);
    });
  };

  const startPolling = (newJobId) => {
    setJobId(newJobId);
    setElapsedSec(0);

    const tick = async () => {
      try {
        const res = await getTrainingJob(newJobId);
        const normalized = normalizeJobStatus(res.data);
        setJob(normalized);
        if (
          SUCCESS_STATUSES.has(normalized.status) ||
          FAILURE_STATUSES.has(normalized.status)
        ) {
          clearInterval(pollRef.current);
          clearInterval(elapsedRef.current);
          setStep(SUCCESS_STATUSES.has(normalized.status) ? "shelved" : "failed");
        }
      } catch {
        setPollError(
          `Lost contact with GET /training/job/${newJobId} — will keep retrying.`
        );
      }
    };

    tick();
    pollRef.current = setInterval(tick, POLL_INTERVAL_MS);
    elapsedRef.current = setInterval(() => setElapsedSec((s) => s + 1), 1000);
  };

  const handleStartTraining = async () => {
    setUploadError("");
    setStep("training");
    try {
      const res = await uploadTrainingImages(
        itemId,
        toClassName(form.name),
        images.map((img) => img.file),
        STORE_ID
      );
      const newJobId = res.data.job_id;
      startPolling(newJobId);
    } catch (err) {
      setUploadError(
        err?.response?.data?.detail ||
          `Couldn't reach POST /training/upload_images at ${API_BASE_URL}.`
      );
      setStep("capture");
    }
  };

  const statusMessage =
    step === "details"
      ? "Enter the new product's details to get started."
      : step === "capture"
      ? `Capture photos from different angles — ${images.length}/${RECOMMENDED_PHOTOS} (minimum ${MIN_PHOTOS}).`
      : step === "training"
      ? job
        ? `Training… ${job.progress ?? 0}%${job.epoch ? ` (epoch ${job.epoch})` : ""}${
            elapsedSec > 0 ? ` — ${elapsedSec}s elapsed` : ""
          }`
        : `Starting training… (this can take 15 min on GPU, up to an hour on CPU)`
      : step === "shelved"
      ? `${form.name} is shelved — detectable at checkout now.`
      : `Training failed — see details below.`;

  return (
    <PageShell
      group="Catalog & Management"
      icon="➕"
      title="Add Item"
      caption="Bring a new product online: details, photos, train, shelve."
      status={statusMessage}
    >
      {step === "details" && (
        <form className="bb-card" onSubmit={handleCreateItem}>
          {formError && <p className="bb-form-error">{formError}</p>}
          <div className="bb-form-grid">
            <label className="bb-form-field">
              <span>Name *</span>
              <input value={form.name} onChange={updateField("name")} required />
            </label>
            <label className="bb-form-field">
              <span>SKU *</span>
              <input value={form.sku} onChange={updateField("sku")} required />
            </label>
            <label className="bb-form-field">
              <span>Price *</span>
              <input
                type="number"
                step="0.01"
                min="0"
                value={form.price}
                onChange={updateField("price")}
                required
              />
            </label>
            <label className="bb-form-field">
              <span>Category</span>
              <input value={form.category} onChange={updateField("category")} />
            </label>
            <label className="bb-form-field">
              <span>Expiry date</span>
              <input
                type="date"
                value={form.expiry_date}
                onChange={updateField("expiry_date")}
              />
            </label>
            <label className="bb-form-field">
              <span>Low stock threshold</span>
              <input
                type="number"
                min="0"
                value={form.low_stock_threshold}
                onChange={updateField("low_stock_threshold")}
              />
            </label>
          </div>
          <div className="bb-checkout-actions">
            <button type="submit" className="bb-btn bb-btn-primary" disabled={submitting}>
              {submitting ? "Creating…" : "Next: capture photos"}
            </button>
          </div>
        </form>
      )}

      {step === "capture" && (
        <div className="bb-card">
          {uploadError && <p className="bb-form-error">{uploadError}</p>}
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            capture="environment"
            multiple
            onChange={handleAddPhotos}
            id="add-item-photo-input"
            className="bb-visually-hidden"
          />
          <label htmlFor="add-item-photo-input" className="bb-btn bb-btn-secondary">
            📷 Add photos
          </label>

          {images.length > 0 && (
            <div className="bb-image-grid">
              {images.map((img, i) => (
                <div className="bb-image-thumb" key={img.previewUrl}>
                  <img src={img.previewUrl} alt={`Capture ${i + 1}`} />
                  <button type="button" onClick={() => removePhoto(i)} aria-label="Remove photo">
                    ×
                  </button>
                </div>
              ))}
            </div>
          )}

          <div className="bb-checkout-actions">
            <button type="button" className="bb-btn bb-btn-secondary" onClick={resetAll}>
              Start over
            </button>
            <button
              type="button"
              className="bb-btn bb-btn-primary"
              onClick={handleStartTraining}
              disabled={images.length < MIN_PHOTOS}
            >
              Start training ({images.length} photo{images.length === 1 ? "" : "s"})
            </button>
          </div>
        </div>
      )}

      {step === "training" && (
        <div className="bb-card">
          {pollError && <p className="bb-form-error">{pollError}</p>}
          <div className="bb-progress-bar">
            <div
              className="bb-progress-fill"
              style={{ width: `${Math.min(job?.progress ?? 5, 100)}%` }}
            />
          </div>
          <p className="bb-caption" style={{ marginTop: 10 }}>
            {job?.stage ? `Stage: ${job.stage}. ` : ""}
            Feel free to leave this page open — training keeps running in the
            background either way.
          </p>
        </div>
      )}

      {step === "shelved" && (
        <div className="bb-card">
          <div className="bb-result-icon bb-result-success">✓</div>
          <p className="bb-cart-item-name" style={{ textAlign: "center" }}>
            {form.name} is shelved and detectable at checkout.
          </p>
          {job?.metrics?.mAP50 != null && (
            <p className="bb-caption" style={{ textAlign: "center" }}>
              mAP50: {Math.round(job.metrics.mAP50 * 100)}%
            </p>
          )}
          <div className="bb-checkout-actions" style={{ justifyContent: "center" }}>
            <button type="button" className="bb-btn bb-btn-primary" onClick={resetAll}>
              Add another item
            </button>
          </div>
        </div>
      )}

      {step === "failed" && (
        <div className="bb-card">
          <div className="bb-result-icon bb-result-failure">!</div>
          <p className="bb-cart-item-name" style={{ textAlign: "center" }}>
            Training didn't clear the accuracy bar.
          </p>
          {job?.errorMessage && (
            <p className="bb-caption" style={{ textAlign: "center" }}>
              {job.errorMessage}
            </p>
          )}
          <div className="bb-checkout-actions" style={{ justifyContent: "center" }}>
            <button
              type="button"
              className="bb-btn bb-btn-secondary"
              onClick={() => setStep("capture")}
            >
              Capture more photos and retry
            </button>
            <button type="button" className="bb-btn bb-btn-primary" onClick={resetAll}>
              Start over
            </button>
          </div>
        </div>
      )}
    </PageShell>
  );
}
