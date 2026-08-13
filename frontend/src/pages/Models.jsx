// src/pages/Models.jsx — replaces the Week 8 roadmap placeholder.
// Version history + activate/rollback for the per-store YOLOv8 model.
// Backend confirmed live: GET /models (history), GET /models/active,
// POST /models/{version}/activate (same handler also serves .../rollback
// — StoreModelManager doesn't distinguish the two operations, see
// api_app.py's MODELS ENDPOINTS section).
//
// Source of truth is models/versions.json (StoreModelManager), NOT the
// SQL ModelVersion table — nothing ever writes to that table. Each
// version record: { store_id, version, model_path, metrics, is_active,
// trained_at, deployed_at }. metrics is whatever retrain_model() passed
// in — in practice mAP50/mAP50-95/precision/recall plus a per_class_AP50
// breakdown, but treated as a loose bag of numbers here since nothing
// guarantees every key is present on every version.

import { useEffect, useState } from "react";
import PageShell from "../components/PageShell.jsx";
import { getModelVersions, activateModel } from "../api.js";
import { API_BASE_URL } from "../config.js";
import { IconCube } from "../components/Icons.jsx";

const METRIC_LABELS = {
  mAP50: "mAP@50",
  "mAP50-95": "mAP@50-95",
  precision: "Precision",
  recall: "Recall",
};

function formatMetricValue(v) {
  return typeof v === "number" ? v.toFixed(3) : String(v);
}

function formatTimestamp(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

export default function Models() {
  const [versions, setVersions] = useState(null); // null while loading
  const [loadState, setLoadState] = useState("loading"); // loading | ready | error
  // Per-version action state, keyed by version string, so activating one
  // row doesn't disable buttons on every other row.
  const [actingVersion, setActingVersion] = useState(null);
  const [actionError, setActionError] = useState("");
  const [actionNotice, setActionNotice] = useState("");

  const load = () => {
    setLoadState("loading");
    getModelVersions()
      .then((res) => {
        // Newest last, per the backend's own docstring — reverse for
        // display so the most recent version leads the table.
        const list = Array.isArray(res.data) ? [...res.data].reverse() : [];
        setVersions(list);
        setLoadState("ready");
      })
      .catch(() => setLoadState("error"));
  };

  useEffect(() => {
    load();
  }, []);

  const handleActivate = async (version) => {
    setActingVersion(version);
    setActionError("");
    setActionNotice("");
    try {
      await activateModel(version);
      setActionNotice(`${version} is now active.`);
      load(); // re-fetch so is_active flips across the whole table
    } catch (err) {
      setActionError(
        err?.response?.data?.detail ||
          `Couldn't reach POST /models/${version}/activate at ${API_BASE_URL}.`
      );
    } finally {
      setActingVersion(null);
    }
  };

  const activeVersion = versions?.find((v) => v.is_active);

  const statusMessage =
    loadState === "loading"
      ? "Loading model versions…"
      : loadState === "error"
      ? `Couldn't reach the backend at ${API_BASE_URL} — make sure it's running.`
      : versions && versions.length === 0
      ? "No trained versions yet — versions appear here after a successful Add Item training run."
      : activeVersion
      ? `${activeVersion.version} is currently active.`
      : "Version history loaded, but none are marked active.";

  return (
    <PageShell
      group="Catalog & Management"
      icon={<IconCube />}
      title="Models"
      caption="See what's trained, how well it's performing, and roll back if needed."
      status={statusMessage}
    >
      {loadState === "ready" && versions && versions.length > 0 && (
        <div className="bb-card">
          <p className="bb-roadmap-title" style={{ marginBottom: 12 }}>
            Version history
          </p>

          {actionError && <p className="bb-form-error">{actionError}</p>}
          {!actionError && actionNotice && (
            <p className="bb-caption" style={{ margin: "0 0 12px" }}>
              {actionNotice}
            </p>
          )}

          <table className="bb-table">
            <thead>
              <tr>
                <th>Version</th>
                <th>Status</th>
                <th>Trained</th>
                <th>Key metrics</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {versions.map((v) => (
                <tr key={v.version}>
                  <td>{v.version}</td>
                  <td>
                    {v.is_active ? (
                      <span className="bb-status-pill">Active</span>
                    ) : (
                      <span className="bb-caption" style={{ margin: 0 }}>
                        —
                      </span>
                    )}
                  </td>
                  <td className="bb-caption" style={{ margin: 0 }}>
                    {formatTimestamp(v.trained_at)}
                  </td>
                  <td>
                    {v.metrics && Object.keys(v.metrics).length > 0 ? (
                      <span className="bb-caption" style={{ margin: 0 }}>
                        {Object.entries(v.metrics)
                          .filter(([key]) => key !== "per_class_AP50")
                          .map(
                            ([key, val]) =>
                              `${METRIC_LABELS[key] || key}: ${formatMetricValue(val)}`
                          )
                          .join(" · ")}
                      </span>
                    ) : (
                      <span className="bb-caption" style={{ margin: 0 }}>
                        —
                      </span>
                    )}
                  </td>
                  <td>
                    {!v.is_active && (
                      <button
                        type="button"
                        className="bb-btn bb-btn-secondary bb-btn-small"
                        onClick={() => handleActivate(v.version)}
                        disabled={actingVersion !== null}
                      >
                        {actingVersion === v.version ? "Activating…" : "Activate"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {versions.some(
            (v) => v.metrics && v.metrics.per_class_AP50 && Object.keys(v.metrics.per_class_AP50).length > 0
          ) && (
            <>
              <p className="bb-roadmap-title" style={{ margin: "20px 0 12px" }}>
                Per-class AP50 (active version)
              </p>
              {activeVersion?.metrics?.per_class_AP50 ? (
                <table className="bb-table">
                  <thead>
                    <tr>
                      <th>Class</th>
                      <th>AP50</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(activeVersion.metrics.per_class_AP50).map(
                      ([className, ap]) => (
                        <tr key={className}>
                          <td style={{ textTransform: "capitalize" }}>
                            {className.replace(/_/g, " ")}
                          </td>
                          <td>{formatMetricValue(ap)}</td>
                        </tr>
                      )
                    )}
                  </tbody>
                </table>
              ) : (
                <p className="bb-caption" style={{ marginTop: 0 }}>
                  No per-class breakdown on the active version.
                </p>
              )}
            </>
          )}
        </div>
      )}

      {loadState === "ready" && versions && versions.length === 0 && (
        <div className="bb-card">
          <p className="bb-caption" style={{ margin: 0 }}>
            Once you train a new item through the Add Item flow, its
            resulting model version will show up here with the option to
            activate or roll back to any earlier version.
          </p>
        </div>
      )}
    </PageShell>
  );
}
