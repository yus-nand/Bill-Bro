// src/pages/Inventory.jsx — replaces pages/inventory.py
// Live: pulls from Person A's GET /inventory (confirmed shape as of
// RESPONSE_TO_PERSON_C.md — distinct from GET /items, which is the static
// product catalog without stock counts).

import { useEffect, useMemo, useState } from "react";
import PageShell from "../components/PageShell.jsx";
import { getInventory } from "../api.js";
import { API_BASE_URL } from "../config.js";

function statusTone(status) {
  const s = (status || "").toUpperCase();
  if (s === "OUT_OF_STOCK") return "bb-severity-critical";
  if (s === "LOW_STOCK") return "bb-severity-warning";
  return "bb-severity-info";
}

export default function Inventory() {
  const [items, setItems] = useState([]);
  const [state, setState] = useState("loading"); // loading | ready | error
  const [query, setQuery] = useState("");

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
              </tr>
            </thead>
            <tbody>
              {filtered.map((item) => (
                <tr key={item.id ?? item.sku}>
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
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={5} className="bb-table-empty">
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
