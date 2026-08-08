// src/pages/Inventory.jsx — replaces pages/inventory.py
// Live: pulls from Person A's GET /inventory (confirmed shape as of
// RESPONSE_TO_PERSON_C.md — distinct from GET /items, which is the static
// product catalog without stock counts).

import { Fragment, useEffect, useMemo, useState } from "react";
import PageShell from "../components/PageShell.jsx";
import { getInventory, restockItem } from "../api.js";
import { API_BASE_URL } from "../config.js";

function statusTone(status) {
  const s = (status || "").toUpperCase();
  if (s === "OUT_OF_STOCK") return "bb-severity-critical";
  if (s === "LOW_STOCK") return "bb-severity-warning";
  return "bb-severity-info";
}

// Empty draft for the restock form — quantity required, batch fields
// optional (per restockItem()'s contract in api.js).
const emptyRestockDraft = { quantityAdded: "", batchNumber: "", batchArrivalDate: "" };

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
    try {
      await restockItem(
        itemId,
        qty,
        restockDraft.batchNumber.trim() || undefined,
        restockDraft.batchArrivalDate || undefined
      );
      closeRestock();
      loadInventory();
    } catch (err) {
      setRestockError(
        err?.response?.data?.detail || `Couldn't reach PATCH /items/${itemId}/restock.`
      );
    } finally {
      setRestockSubmitting(false);
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
      icon="📦"
      title="Inventory"
      caption="See what's on the shelves right now."
      status={statusMessage}
    >
      {state === "ready" && items.length > 0 && (
        <div className="bb-card">
          <input
            className="bb-search"
            type="text"
            placeholder="Search items…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <table className="bb-table">
            <thead>
              <tr>
                <th>Item</th>
                <th>SKU</th>
                <th>Price</th>
                <th>Stock</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((item) => (
                <Fragment key={item.id ?? item.sku}>
                  <tr>
                    <td>{item.name}</td>
                    <td>{item.sku}</td>
                    <td>
                      {item.price != null ? `₹${Number(item.price).toFixed(2)}` : "—"}
                    </td>
                    <td>{item.current_count ?? "—"}</td>
                    <td>
                      <span className={`bb-status-pill ${statusTone(item.status)}`}>
                        {item.status || "OK"}
                      </span>
                    </td>
                    <td>
                      <button
                        type="button"
                        className="bb-btn bb-btn-secondary bb-btn-small"
                        onClick={() =>
                          restockOpenFor === item.id ? closeRestock() : openRestock(item.id)
                        }
                      >
                        {restockOpenFor === item.id ? "Cancel" : "Restock"}
                      </button>
                    </td>
                  </tr>
                  {restockOpenFor === item.id && (
                    <tr>
                      <td colSpan={6}>
                        <form
                          className="bb-restock-form"
                          onSubmit={(e) => handleRestockSubmit(e, item.id)}
                        >
                          {restockError && <p className="bb-form-error">{restockError}</p>}
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
                </Fragment>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={6} className="bb-table-empty">
                    No items match "{query}".
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </PageShell>
  );
}
