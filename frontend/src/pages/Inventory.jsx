// src/pages/Inventory.jsx — replaces pages/inventory.py
// Live: pulls from Person A's GET /inventory (confirmed shape as of
// RESPONSE_TO_PERSON_C.md — distinct from GET /items, which is the static
// product catalog without stock counts).
//
// Retrain flow added alongside TrainingJobsContext (shared with Add
// Item — see that context's header comment for why job state lives
// there instead of local state): when you hit Retrain, you're asked
// whether to reuse the item's existing training photos (still sitting
// server-side from whenever it was last trained) or capture fresh ones,
// rather than the app silently picking one for you.

import { Fragment, useEffect, useMemo, useState } from "react";
import PageShell from "../components/PageShell.jsx";
import PhotoCaptureField from "../components/PhotoCaptureField.jsx";
import TrainingProgressCard from "../components/TrainingProgressCard.jsx";
import { getInventory, restockItem, deleteItem } from "../api.js";
import { API_BASE_URL } from "../config.js";
import { useTrainingJobs } from "../context/TrainingJobsContext.jsx";
import { useToast } from "../context/ToastContext.jsx";
import { toClassName } from "../imageUtils.js";
import { IconBox, IconSearch, IconCheck } from "../components/Icons.jsx";

function statusTone(status) {
  const s = (status || "").toUpperCase();
  if (s === "OUT_OF_STOCK") return "bb-severity-critical";
  if (s === "LOW_STOCK") return "bb-severity-warning";
  return "bb-severity-info";
}

// Empty draft for the restock form — quantity required, batch/expiry
// fields optional (per restockItem()'s contract in api.js).
const emptyRestockDraft = {
  quantityAdded: "",
  batchNumber: "",
  batchArrivalDate: "",
  expiryDate: "",
};

export default function Inventory() {
  const [items, setItems] = useState([]);
  const [state, setState] = useState("loading"); // loading | ready | error
  const [query, setQuery] = useState("");

  // Which row's restock form is open, keyed by item id — only one at a
  // time keeps this simple.
  const [restockOpenFor, setRestockOpenFor] = useState(null);
  const [restockDraft, setRestockDraft] = useState(emptyRestockDraft);
  const [restockSubmitting, setRestockSubmitting] = useState(false);
  const [restockError, setRestockError] = useState("");

  // Retrain flow — separate from restock so both can't be open on the
  // same row at once (keeps the expanded-row markup simple).
  const [retrainOpenFor, setRetrainOpenFor] = useState(null);
  // null = hasn't chosen yet, "reuse" | "fresh" once they pick.
  const [retrainChoice, setRetrainChoice] = useState(null);
  const [retrainImages, setRetrainImages] = useState([]);
  const [retrainImageError, setRetrainImageError] = useState("");
  const [retrainStarting, setRetrainStarting] = useState(false);

  // Delete flow — click Delete once to arm a confirm step (guards against
  // a stray click on an irreversible action), click again to actually
  // send it. Separate from restock/retrain's open-row state since it
  // doesn't need a full expanded panel, just a "are you sure" swap.
  const [deleteConfirmFor, setDeleteConfirmFor] = useState(null);
  const [deletingId, setDeletingId] = useState(null);

  const { getJob, startTraining, startRetrainFromExisting, dismissJob } = useTrainingJobs();
  const toast = useToast();

  const loadInventory = () => {
    getInventory()
      .then((res) => {
        setItems(Array.isArray(res.data) ? res.data : res.data.items || []);
        setState("ready");
      })
      .catch(() => setState("error"));
  };

  useEffect(() => {
    let cancelled = false;
    getInventory()
      .then((res) => {
        if (cancelled) return;
        setItems(Array.isArray(res.data) ? res.data : res.data.items || []);
        setState("ready");
      })
      .catch(() => {
        if (!cancelled) setState("error");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const openRestock = (itemId) => {
    setRetrainOpenFor(null);
    setDeleteConfirmFor(null);
    setRestockOpenFor(itemId);
    setRestockDraft(emptyRestockDraft);
    setRestockError("");
  };

  const closeRestock = () => {
    setRestockOpenFor(null);
    setRestockDraft(emptyRestockDraft);
    setRestockError("");
  };

  const handleRestockSubmit = async (e, itemId) => {
    e.preventDefault();
    const qty = Number(restockDraft.quantityAdded);
    if (!qty || qty <= 0) {
      setRestockError("Quantity added must be a positive number.");
      return;
    }
    setRestockSubmitting(true);
    setRestockError("");
    const itemName = items.find((it) => it.id === itemId)?.name || "item";
    try {
      await restockItem(
        itemId,
        qty,
        restockDraft.batchNumber.trim() || undefined,
        restockDraft.batchArrivalDate || undefined,
        restockDraft.expiryDate || undefined
      );
      closeRestock();
      loadInventory();
      toast.success(`Restocked ${itemName} — added ${qty}.`);
    } catch (err) {
      const message =
        err?.response?.data?.detail || `Couldn't reach PATCH /items/${itemId}/restock.`;
      setRestockError(message);
      toast.error(message);
    } finally {
      setRestockSubmitting(false);
    }
  };

  const openRetrain = (itemId) => {
    closeRestock();
    setDeleteConfirmFor(null);
    setRetrainOpenFor(itemId);
    setRetrainChoice(null);
    setRetrainImages([]);
    setRetrainImageError("");
  };

  const closeRetrain = () => {
    retrainImages.forEach((img) => URL.revokeObjectURL(img.previewUrl));
    setRetrainOpenFor(null);
    setRetrainChoice(null);
    setRetrainImages([]);
    setRetrainImageError("");
  };

  const handleReuseExisting = async (item) => {
    setRetrainStarting(true);
    const result = await startRetrainFromExisting(item.id, toClassName(item.name));
    setRetrainStarting(false);
    if (result.ok) {
      closeRetrain();
      toast.info(`Retraining ${item.name} with ${result.photosUsed ?? "existing"} photo${result.photosUsed === 1 ? "" : "s"} — this can take a while on CPU.`);
    } else if (
      // No photos on disk to reuse — the backend told us clearly, so
      // just drop straight into the fresh-capture choice instead of
      // showing a dead-end error.
      /no existing photos/i.test(result.error || "")
    ) {
      setRetrainChoice("fresh");
    } else {
      setRetrainImageError(result.error);
      toast.error(result.error);
    }
  };

  const handleFreshRetrainSubmit = async (item) => {
    setRetrainStarting(true);
    const result = await startTraining(
      item.id,
      toClassName(item.name),
      retrainImages.map((img) => img.file)
    );
    setRetrainStarting(false);
    if (result.ok) {
      closeRetrain();
      toast.info(`Retraining ${item.name} with ${retrainImages.length} new photo${retrainImages.length === 1 ? "" : "s"} — this can take a while on CPU.`);
    } else {
      setRetrainImageError(result.error);
      toast.error(result.error);
    }
  };

  const handleDelete = async (item) => {
    setDeletingId(item.id);
    try {
      await deleteItem(item.id);
      setDeleteConfirmFor(null);
      setItems((prev) => prev.filter((it) => it.id !== item.id));
      toast.success(`${item.name} deleted.`);
    } catch (err) {
      toast.error(
        err?.response?.data?.detail || `Couldn't reach DELETE /items/${item.id}.`
      );
    } finally {
      setDeletingId(null);
    }
  };

  const filtered = useMemo(
    () =>
      items.filter((it) =>
        (it.name || "").toLowerCase().includes(query.toLowerCase())
      ),
    [items, query]
  );

  const needsAttention = items.filter(
    (it) => (it.status || "OK").toUpperCase() !== "OK"
  ).length;

  const statusMessage =
    state === "loading"
      ? "Loading inventory…"
      : state === "error"
      ? `Couldn't reach the backend at ${API_BASE_URL} — make sure Person A's API is running.`
      : `${items.length} SKU${items.length === 1 ? "" : "s"} tracked · ${needsAttention} need attention.`;

  return (
    <PageShell
      group="Store Operations"
      icon={<IconBox />}
      title="Inventory"
      caption="See what's on the shelves right now."
      status={statusMessage}
    >
      {state === "loading" && (
        <div className="bb-card">
          {[0, 1, 2, 3].map((i) => (
            <div
              key={i}
              style={{ display: "flex", gap: 14, padding: "10px 0", alignItems: "center" }}
            >
              <div className="bb-skeleton-line" style={{ width: "22%" }} />
              <div className="bb-skeleton-line" style={{ width: "14%" }} />
              <div className="bb-skeleton-line" style={{ width: "10%" }} />
              <div className="bb-skeleton-line" style={{ width: "10%" }} />
              <div className="bb-skeleton-line" style={{ width: "16%" }} />
              <div className="bb-skeleton-line" style={{ width: "12%" }} />
            </div>
          ))}
        </div>
      )}

      {state === "ready" && items.length > 0 && (
        <div className="bb-card">
          <div className="bb-search-wrap" data-tour="inventory-search">
            <IconSearch className="bb-search-icon" />
            <input
              className="bb-search"
              type="text"
              placeholder="Search items…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          <table className="bb-table">
            <thead>
              <tr>
                <th>Item</th>
                <th>SKU</th>
                <th>Price</th>
                <th>Stock</th>
                <th>Batch / Expiry</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((item) => {
                const jobEntry = getJob(item.id);
                const jobActive = jobEntry && jobEntry.phase;
                const rowExpanded = retrainOpenFor === item.id || jobActive;

                return (
                  <Fragment key={item.id ?? item.sku}>
                    <tr>
                      <td>{item.name}</td>
                      <td>{item.sku}</td>
                      <td>
                        {item.price != null ? `₹${Number(item.price).toFixed(2)}` : "—"}
                      </td>
                      <td>{item.current_count ?? "—"}</td>
                      <td>
                        {item.batch_number ? (
                          <p className="bb-alert-meta" style={{ margin: 0 }}>
                            {item.batch_number}
                          </p>
                        ) : null}
                        <p className="bb-alert-meta" style={{ margin: 0 }}>
                          {item.expiry_date ? `Exp ${item.expiry_date}` : "—"}
                        </p>
                      </td>
                      <td>
                        <span className={`bb-status-pill ${statusTone(item.status)}`}>
                          {item.status || "OK"}
                        </span>
                      </td>
                      <td>
                        {deleteConfirmFor === item.id ? (
                          <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                            <span className="bb-alert-meta" style={{ whiteSpace: "nowrap" }}>
                              Delete?
                            </span>
                            <button
                              type="button"
                              className="bb-btn bb-btn-danger bb-btn-small"
                              onClick={() => handleDelete(item)}
                              disabled={deletingId === item.id}
                            >
                              {deletingId === item.id ? "Deleting…" : "Confirm"}
                            </button>
                            <button
                              type="button"
                              className="bb-btn bb-btn-secondary bb-btn-small"
                              onClick={() => setDeleteConfirmFor(null)}
                              disabled={deletingId === item.id}
                            >
                              Cancel
                            </button>
                          </div>
                        ) : (
                          <div style={{ display: "flex", gap: 6 }}>
                            <button
                              type="button"
                              className="bb-btn bb-btn-secondary bb-btn-small"
                              onClick={() =>
                                restockOpenFor === item.id ? closeRestock() : openRestock(item.id)
                              }
                            >
                              {restockOpenFor === item.id ? "Cancel" : "Restock"}
                            </button>
                            <button
                              type="button"
                              className="bb-btn bb-btn-secondary bb-btn-small"
                              onClick={() =>
                                retrainOpenFor === item.id ? closeRetrain() : openRetrain(item.id)
                              }
                              disabled={Boolean(jobActive)}
                            >
                              {jobActive
                                ? jobEntry.phase === "shelved"
                                  ? "Shelved"
                                  : jobEntry.phase === "failed"
                                  ? "Failed"
                                  : "Training…"
                                : retrainOpenFor === item.id
                                ? "Cancel"
                                : "Retrain"}
                            </button>
                            <button
                              type="button"
                              className="bb-btn bb-btn-danger bb-btn-small"
                              onClick={() => {
                                closeRestock();
                                closeRetrain();
                                setDeleteConfirmFor(item.id);
                              }}
                              disabled={Boolean(jobActive)}
                              title={jobActive ? "Wait for training to finish before deleting" : "Delete this item"}
                            >
                              Delete
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>

                    {restockOpenFor === item.id && (
                      <tr className="bb-row-expand">
                        <td colSpan={7}>
                          <form
                            className="bb-restock-form"
                            onSubmit={(e) => handleRestockSubmit(e, item.id)}
                          >
                            {restockError && <p className="bb-form-error">{restockError}</p>}
                            <p className="bb-caption" style={{ margin: "0 0 8px" }}>
                              Batch number, arrival date, and expiry date are
                              optional — leave any blank to keep the item's
                              current value.
                            </p>
                            <label className="bb-form-field">
                              <span>Quantity added *</span>
                              <input
                                type="number"
                                min="1"
                                value={restockDraft.quantityAdded}
                                onChange={(e) =>
                                  setRestockDraft((d) => ({ ...d, quantityAdded: e.target.value }))
                                }
                                required
                              />
                            </label>
                            <label className="bb-form-field">
                              <span>Batch number</span>
                              <input
                                value={restockDraft.batchNumber}
                                onChange={(e) =>
                                  setRestockDraft((d) => ({ ...d, batchNumber: e.target.value }))
                                }
                              />
                            </label>
                            <label className="bb-form-field">
                              <span>Batch arrival date</span>
                              <input
                                type="date"
                                value={restockDraft.batchArrivalDate}
                                onChange={(e) =>
                                  setRestockDraft((d) => ({
                                    ...d,
                                    batchArrivalDate: e.target.value,
                                  }))
                                }
                              />
                            </label>
                            <label className="bb-form-field">
                              <span>New expiry date</span>
                              <input
                                type="date"
                                value={restockDraft.expiryDate}
                                onChange={(e) =>
                                  setRestockDraft((d) => ({
                                    ...d,
                                    expiryDate: e.target.value,
                                  }))
                                }
                              />
                            </label>
                            <button
                              type="submit"
                              className="bb-btn bb-btn-primary bb-btn-small"
                              disabled={restockSubmitting}
                            >
                              {restockSubmitting ? "Saving…" : "Confirm restock"}
                            </button>
                          </form>
                        </td>
                      </tr>
                    )}

                    {rowExpanded && (
                      <tr className="bb-row-expand">
                        <td colSpan={7}>
                          {/* Active job for this item — training in
                              progress, or a result to show. Reads from
                              the shared context, so this looks the same
                              whether the job was started from here or
                              from Add Item, and keeps showing correctly
                              even if you left and came back. */}
                          {jobActive && jobEntry.phase === "uploading" && (
                            <p className="bb-caption" style={{ margin: "8px 0" }}>
                              Starting retrain…
                            </p>
                          )}
                          {jobActive && jobEntry.phase === "training" && (
                            <TrainingProgressCard entry={jobEntry} />
                          )}
                          {jobActive && jobEntry.phase === "upload_failed" && (
                            <div className="bb-restock-form">
                              <p className="bb-form-error">{jobEntry.errorAtUpload}</p>
                              <button
                                type="button"
                                className="bb-btn bb-btn-primary bb-btn-small"
                                onClick={() => dismissJob(item.id)}
                              >
                                Dismiss
                              </button>
                            </div>
                          )}
                          {jobActive && jobEntry.phase === "shelved" && (
                            <div className="bb-restock-form">
                              <p className="bb-caption bb-inline-icon-text" style={{ margin: 0 }}>
                                <IconCheck /> Retrained and shelved
                                {jobEntry.job?.metrics?.mAP50 != null &&
                                  ` — mAP50: ${Math.round(jobEntry.job.metrics.mAP50 * 100)}%`}
                                .
                              </p>
                              <button
                                type="button"
                                className="bb-btn bb-btn-secondary bb-btn-small"
                                style={{ marginTop: 8 }}
                                onClick={() => dismissJob(item.id)}
                              >
                                Dismiss
                              </button>
                            </div>
                          )}
                          {jobActive && jobEntry.phase === "failed" && (
                            <div className="bb-restock-form">
                              <p className="bb-form-error">
                                Retraining failed
                                {jobEntry.job?.errorMessage ? `: ${jobEntry.job.errorMessage}` : "."}
                              </p>
                              <button
                                type="button"
                                className="bb-btn bb-btn-secondary bb-btn-small"
                                onClick={() => dismissJob(item.id)}
                              >
                                Dismiss
                              </button>
                            </div>
                          )}

                          {/* No active job — the actual retrain-choice UI. */}
                          {!jobActive && retrainOpenFor === item.id && (
                            <div className="bb-restock-form">
                              {retrainImageError && (
                                <p className="bb-form-error">{retrainImageError}</p>
                              )}

                              {retrainChoice === null && (
                                <>
                                  <p className="bb-caption" style={{ margin: "0 0 10px" }}>
                                    Retrain "{item.name}" using its existing photos
                                    (still on file from last time), or capture new
                                    ones?
                                  </p>
                                  <div style={{ display: "flex", gap: 8 }}>
                                    <button
                                      type="button"
                                      className="bb-btn bb-btn-primary bb-btn-small"
                                      onClick={() => handleReuseExisting(item)}
                                      disabled={retrainStarting}
                                    >
                                      {retrainStarting ? "Starting…" : "Reuse existing photos"}
                                    </button>
                                    <button
                                      type="button"
                                      className="bb-btn bb-btn-secondary bb-btn-small"
                                      onClick={() => setRetrainChoice("fresh")}
                                      disabled={retrainStarting}
                                    >
                                      Capture new photos
                                    </button>
                                  </div>
                                </>
                              )}

                              {retrainChoice === "fresh" && (
                                <>
                                  <p className="bb-caption" style={{ margin: "0 0 10px" }}>
                                    New photos will replace the old ones for future
                                    retrains.
                                  </p>
                                  <PhotoCaptureField
                                    images={retrainImages}
                                    setImages={setRetrainImages}
                                    error={retrainImageError}
                                    setError={setRetrainImageError}
                                    inputId={`retrain-photo-input-${item.id}`}
                                  />
                                  <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
                                    <button
                                      type="button"
                                      className="bb-btn bb-btn-secondary bb-btn-small"
                                      onClick={() => setRetrainChoice(null)}
                                      disabled={retrainStarting}
                                    >
                                      Back
                                    </button>
                                    <button
                                      type="button"
                                      className="bb-btn bb-btn-primary bb-btn-small"
                                      onClick={() => handleFreshRetrainSubmit(item)}
                                      disabled={retrainStarting || retrainImages.length < 5}
                                    >
                                      {retrainStarting
                                        ? "Starting…"
                                        : `Start retraining (${retrainImages.length} photo${
                                            retrainImages.length === 1 ? "" : "s"
                                          })`}
                                    </button>
                                  </div>
                                </>
                              )}
                            </div>
                          )}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={7} className="bb-table-empty">
                    <IconSearch style={{ verticalAlign: "-3px", marginRight: 4 }} /> No items match "{query}".{" "}
                    <button
                      type="button"
                      className="bb-btn bb-btn-secondary bb-btn-small"
                      style={{ marginLeft: 8 }}
                      onClick={() => setQuery("")}
                    >
                      Clear search
                    </button>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {state === "ready" && items.length === 0 && (
        <div className="bb-card bb-empty-state">
          <div className="bb-empty-state-icon" aria-hidden="true">
            <IconBox width={28} height={28} />
          </div>
          <p>No items in the catalog yet — add your first one to get started.</p>
        </div>
      )}
    </PageShell>
  );
}
