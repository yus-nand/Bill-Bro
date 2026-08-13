// src/pages/Admin.jsx — replaces the Week 7 roadmap placeholder.
// Two independent tools: store settings (tax rate, currency, default
// low-stock threshold) and bulk CSV catalog upload. Backend confirmed
// live this session — GET/PUT /admin/settings, POST /admin/bulk_upload
// — see API_CONTRACT.md's Admin section for the full contract.

import { useEffect, useRef, useState } from "react";
import PageShell from "../components/PageShell.jsx";
import { getStoreSettings, updateStoreSettings, uploadBulkCsv } from "../api.js";
import { API_BASE_URL, STORE_ID, APP_VERSION } from "../config.js";
import { IconSettings } from "../components/Icons.jsx";

export default function Admin() {
  // ── Store settings ───────────────────────────────────────────────────
  const [settings, setSettings] = useState(null); // last-saved values from the server
  const [draft, setDraft] = useState(null); // editable copy the form binds to
  const [settingsState, setSettingsState] = useState("loading"); // loading | ready | error
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [settingsError, setSettingsError] = useState("");
  const [settingsSavedAt, setSettingsSavedAt] = useState(null);

  useEffect(() => {
    let cancelled = false;
    getStoreSettings()
      .then((res) => {
        if (cancelled) return;
        setSettings(res.data);
        setDraft(res.data);
        setSettingsState("ready");
      })
      .catch(() => {
        if (!cancelled) setSettingsState("error");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Only send fields that actually changed from what's on the server —
  // matches the backend's partial-update contract (StoreSettingsRequest:
  // all fields Optional, only provided ones get written) rather than
  // re-sending the whole object every time.
  const handleSettingsSubmit = async (e) => {
    e.preventDefault();
    if (!settings || !draft) return;

    const changed = {};
    if (draft.tax_rate_pct !== settings.tax_rate_pct) {
      const n = Number(draft.tax_rate_pct);
      if (Number.isNaN(n) || n < 0) {
        setSettingsError("Tax rate must be a non-negative number.");
        return;
      }
      changed.tax_rate_pct = n;
    }
    if (draft.currency_symbol !== settings.currency_symbol) {
      if (!draft.currency_symbol.trim()) {
        setSettingsError("Currency symbol can't be empty.");
        return;
      }
      changed.currency_symbol = draft.currency_symbol.trim();
    }
    if (draft.low_stock_default_threshold !== settings.low_stock_default_threshold) {
      const n = Number(draft.low_stock_default_threshold);
      if (!Number.isInteger(n) || n < 0) {
        setSettingsError("Default low-stock threshold must be a non-negative whole number.");
        return;
      }
      changed.low_stock_default_threshold = n;
    }

    if (Object.keys(changed).length === 0) {
      setSettingsError("");
      return; // nothing actually changed, no need to hit the network
    }

    setSettingsSaving(true);
    setSettingsError("");
    try {
      const res = await updateStoreSettings(changed);
      const saved = res.data.settings;
      setSettings(saved);
      setDraft(saved);
      setSettingsSavedAt(new Date());
    } catch (err) {
      setSettingsError(
        err?.response?.data?.detail || `Couldn't reach PUT /admin/settings at ${API_BASE_URL}.`
      );
    } finally {
      setSettingsSaving(false);
    }
  };

  const settingsDirty =
    settings &&
    draft &&
    (draft.tax_rate_pct !== settings.tax_rate_pct ||
      draft.currency_symbol !== settings.currency_symbol ||
      draft.low_stock_default_threshold !== settings.low_stock_default_threshold);

  // ── Bulk CSV upload ──────────────────────────────────────────────────
  const csvInputRef = useRef(null);
  const [csvFile, setCsvFile] = useState(null);
  const [csvUploading, setCsvUploading] = useState(false);
  const [csvResult, setCsvResult] = useState(null); // { created, updated, error_count, errors }
  const [csvError, setCsvError] = useState(""); // request-level failure (bad file, network, etc.)

  const handleCsvFileChange = (e) => {
    setCsvFile(e.target.files?.[0] || null);
    setCsvResult(null);
    setCsvError("");
  };

  const handleCsvUpload = async () => {
    if (!csvFile) return;
    setCsvUploading(true);
    setCsvError("");
    setCsvResult(null);
    try {
      const res = await uploadBulkCsv(csvFile);
      setCsvResult(res.data);
      // Clear the picked file once it's actually been processed —
      // re-uploading the exact same file by accident would just
      // re-upsert the same rows, harmless but confusing to leave staged.
      setCsvFile(null);
      if (csvInputRef.current) csvInputRef.current.value = "";
    } catch (err) {
      setCsvError(
        err?.response?.data?.detail || `Couldn't reach POST /admin/bulk_upload at ${API_BASE_URL}.`
      );
    } finally {
      setCsvUploading(false);
    }
  };

  const statusMessage =
    settingsState === "loading"
      ? "Loading store settings…"
      : settingsState === "error"
      ? `Couldn't reach the backend at ${API_BASE_URL} — make sure it's running.`
      : "Store settings and bulk catalog tools.";

  return (
    <PageShell
      group="Catalog & Management"
      icon={<IconSettings />}
      title="Admin"
      caption="Store settings, bulk edits, and manual overrides."
      status={statusMessage}
    >
      {settingsState === "ready" && draft && (
        <div className="bb-card" data-tour="admin-settings">
          <p className="bb-roadmap-title" style={{ marginBottom: 12 }}>
            Store settings
          </p>
          <form className="bb-admin-settings-form" onSubmit={handleSettingsSubmit}>
            {settingsError && <p className="bb-form-error">{settingsError}</p>}
            <label className="bb-form-field">
              <span>Tax rate (%)</span>
              <input
                type="number"
                step="0.1"
                min="0"
                value={draft.tax_rate_pct}
                onChange={(e) => setDraft((d) => ({ ...d, tax_rate_pct: e.target.value }))}
              />
            </label>
            <label className="bb-form-field">
              <span>Currency symbol</span>
              <input
                type="text"
                maxLength={10}
                value={draft.currency_symbol}
                onChange={(e) => setDraft((d) => ({ ...d, currency_symbol: e.target.value }))}
              />
            </label>
            <label className="bb-form-field">
              <span>Default low-stock threshold</span>
              <input
                type="number"
                step="1"
                min="0"
                value={draft.low_stock_default_threshold}
                onChange={(e) =>
                  setDraft((d) => ({ ...d, low_stock_default_threshold: e.target.value }))
                }
              />
            </label>
            <p className="bb-caption" style={{ margin: "0 0 12px" }}>
              This only sets the default for newly created items — existing
              items keep their own low-stock threshold until edited
              individually.
            </p>
            <div className="bb-checkout-actions" style={{ justifyContent: "flex-start" }}>
              <button
                type="submit"
                className="bb-btn bb-btn-primary bb-btn-small"
                disabled={!settingsDirty || settingsSaving}
              >
                {settingsSaving ? "Saving…" : "Save settings"}
              </button>
              {!settingsSaving && settingsSavedAt && !settingsDirty && (
                <span className="bb-alert-meta">
                  Saved at {settingsSavedAt.toLocaleTimeString()}
                </span>
              )}
            </div>
          </form>
        </div>
      )}

      <div className="bb-card">
        <p className="bb-roadmap-title" style={{ marginBottom: 12 }}>
          Bulk catalog upload
        </p>
        <p className="bb-caption" style={{ marginTop: 0, marginBottom: 12 }}>
          CSV with a header row: <code>name, sku, price</code> required,{" "}
          <code>category, expiry_date (YYYY-MM-DD), low_stock_threshold</code>{" "}
          optional. Matches an existing SKU → updates that item's details
          (stock count and status are left alone). New SKU → creates a new
          item, starting unshelved just like adding one by hand.
        </p>

        <input
          ref={csvInputRef}
          type="file"
          accept=".csv,text/csv"
          onChange={handleCsvFileChange}
          id="admin-csv-input"
          className="bb-visually-hidden"
        />
        <div className="bb-checkout-actions" style={{ justifyContent: "flex-start" }}>
          <label htmlFor="admin-csv-input" className="bb-btn bb-btn-secondary bb-btn-small">
            {csvFile ? csvFile.name : "Choose CSV file"}
          </label>
          <button
            type="button"
            className="bb-btn bb-btn-primary bb-btn-small"
            onClick={handleCsvUpload}
            disabled={!csvFile || csvUploading}
          >
            {csvUploading ? "Uploading…" : "Upload"}
          </button>
        </div>

        {csvError && (
          <p className="bb-form-error" style={{ marginTop: 12 }}>
            {csvError}
          </p>
        )}

        {csvResult && (
          <div style={{ marginTop: 16 }}>
            <p className="bb-caption" style={{ margin: "0 0 8px" }}>
              {csvResult.created} created · {csvResult.updated} updated
              {csvResult.error_count > 0
                ? ` · ${csvResult.error_count} row${csvResult.error_count === 1 ? "" : "s"} skipped`
                : ""}
            </p>
            {csvResult.errors && csvResult.errors.length > 0 && (
              <table className="bb-table">
                <thead>
                  <tr>
                    <th>Row</th>
                    <th>Error</th>
                  </tr>
                </thead>
                <tbody>
                  {csvResult.errors.map((err, i) => (
                    <tr key={i}>
                      <td>{err.row}</td>
                      <td className="bb-caption" style={{ margin: 0 }}>
                        {err.error}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>

      <div className="bb-card bb-env-card">
        <p className="bb-roadmap-title" style={{ marginBottom: 8 }}>
          Environment
        </p>
        <p className="bb-caption" style={{ margin: "0 0 2px" }}>
          Store: <code>{STORE_ID}</code>
        </p>
        <p className="bb-caption" style={{ margin: "0 0 2px" }}>
          API: <code>{API_BASE_URL}</code>
        </p>
        <p className="bb-caption" style={{ margin: 0 }}>
          Version: <code>{APP_VERSION}</code>
        </p>
      </div>
    </PageShell>
  );
}
