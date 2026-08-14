// src/pages/AddItem.jsx — replaces pages/add_item.py
// Reprioritized as the first core feature per BillBro_TeamUpdates.md:
// item details → capture photos → train → shelve. An item only becomes
// checkout-detectable once it's "shelved" (training succeeded).
//
// All three endpoints (POST /items, POST /training/upload_images,
// GET /training/job/{id}) are live on Person A's side now.
//
// State that needs to survive navigating away mid-flow lives in two
// contexts mounted above the router (see App.jsx): AddItemDraftContext
// for the pre-training wizard (which item, what step, staged photos),
// and TrainingJobsContext for the actual training-in-progress tracking
// (shared with Inventory's Retrain flow) — this page just reads/writes
// through them instead of owning that state itself.

import PageShell from "../components/PageShell.jsx";
import PhotoCaptureField from "../components/PhotoCaptureField.jsx";
import TrainingProgressCard from "../components/TrainingProgressCard.jsx";
import { useAddItemDraft } from "../context/AddItemDraftContext.jsx";
import { useTrainingJobs } from "../context/TrainingJobsContext.jsx";
import { useToast } from "../context/ToastContext.jsx";
import { createItem } from "../api.js";
import { API_BASE_URL } from "../config.js";
import { toClassName } from "../imageUtils.js";
import { IconPlus, IconCheck, IconAlert } from "../components/Icons.jsx";
import { useState } from "react";

const RECOMMENDED_PHOTOS = 15;
const MIN_PHOTOS = 5;

export default function AddItem() {
  const { step, setStep, form, setForm, itemId, setItemId, images, setImages, resetDraft } =
    useAddItemDraft();
  const { getJob, startTraining, dismissJob } = useTrainingJobs();
  const toast = useToast();

  const [formError, setFormError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [uploadError, setUploadError] = useState("");

  const entry = itemId ? getJob(itemId) : null;
  // Once training has actually been kicked off for this item, the
  // context's phase takes over as the source of truth for what to show
  // — overrides the local "details"/"capture" step.
  const effectivePhase = entry?.phase || null;

  const resetAll = () => {
    if (itemId) dismissJob(itemId);
    resetDraft();
    setFormError("");
    setUploadError("");
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
      toast.success(`${form.name} added — now capture photos to train it.`);
    } catch (err) {
      const message =
        err?.response?.data?.detail ||
        `Couldn't reach POST /items at ${API_BASE_URL} — is the backend running?`;
      setFormError(message);
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleStartTraining = async () => {
    setUploadError("");
    const result = await startTraining(
      itemId,
      toClassName(form.name),
      images.map((img) => img.file)
    );
    if (!result.ok) {
      setUploadError(result.error);
      toast.error(result.error);
    } else {
      toast.info(`Training ${form.name} — this can take a while on CPU. Feel free to navigate away, we'll track it.`);
    }
  };

  const statusMessage =
    effectivePhase === "uploading"
      ? "Uploading photos…"
      : effectivePhase === "upload_failed"
      ? "Upload failed — see details below."
      : effectivePhase === "training"
      ? entry?.job
        ? `Training… ${entry.job.progress ?? 0}%${
            entry.job.epoch ? ` (epoch ${entry.job.epoch})` : ""
          }${entry.elapsedSec > 0 ? ` — ${entry.elapsedSec}s elapsed` : ""}`
        : "Starting training… (this can take 15 min on GPU, up to an hour on CPU)"
      : effectivePhase === "shelved"
      ? `${entry?.itemName || form.name} is shelved — detectable at checkout now.`
      : effectivePhase === "failed"
      ? "Training failed — see details below."
      : step === "details"
      ? "Enter the new product's details to get started."
      : `Capture photos from different angles — ${images.length}/${RECOMMENDED_PHOTOS} (minimum ${MIN_PHOTOS}).`;

  return (
    <PageShell
      group="Catalog & Management"
      icon={<IconPlus />}
      title="Add Item"
      caption="Bring a new product online: details, photos, train, shelve."
      status={statusMessage}
    >
      {!effectivePhase && step === "details" && (
        <form className="bb-card" onSubmit={handleCreateItem} data-tour="additem-form">
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

      {!effectivePhase && step === "capture" && (
        <div className="bb-card">
          <PhotoCaptureField
            images={images}
            setImages={setImages}
            error={uploadError}
            setError={setUploadError}
            inputId="add-item-photo-input"
          />
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

      {(effectivePhase === "uploading" || effectivePhase === "training") && (
        <TrainingProgressCard entry={entry} />
      )}

      {effectivePhase === "upload_failed" && (
        <div className="bb-card">
          <p className="bb-form-error">{entry?.errorAtUpload}</p>
          <div className="bb-checkout-actions">
            <button
              type="button"
              className="bb-btn bb-btn-primary"
              onClick={() => dismissJob(itemId)}
            >
              Back to photos
            </button>
          </div>
        </div>
      )}

      {effectivePhase === "shelved" && (
        <div className="bb-card">
          <div className="bb-result-icon bb-result-success">
            <IconCheck width={22} height={22} />
          </div>
          <p className="bb-cart-item-name" style={{ textAlign: "center" }}>
            {entry?.itemName ? entry.itemName.replace(/_/g, " ") : form.name} is shelved
            and detectable at checkout.
          </p>
          {entry?.job?.metrics?.mAP50 != null && (
            <p className="bb-caption" style={{ textAlign: "center" }}>
              mAP50: {Math.round(entry.job.metrics.mAP50 * 100)}%
            </p>
          )}
          <div className="bb-checkout-actions" style={{ justifyContent: "center" }}>
            <button type="button" className="bb-btn bb-btn-primary" onClick={resetAll}>
              Add another item
            </button>
          </div>
        </div>
      )}

      {effectivePhase === "failed" && (
        <div className="bb-card">
          <div className="bb-result-icon bb-result-failure">
            <IconAlert width={22} height={22} />
          </div>
          <p className="bb-cart-item-name" style={{ textAlign: "center" }}>
            Training didn't clear the accuracy bar.
          </p>
          {entry?.job?.errorMessage && (
            <p className="bb-caption" style={{ textAlign: "center" }}>
              {entry.job.errorMessage}
            </p>
          )}
          <div className="bb-checkout-actions" style={{ justifyContent: "center" }}>
            <button
              type="button"
              className="bb-btn bb-btn-secondary"
              onClick={() => dismissJob(itemId)}
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
