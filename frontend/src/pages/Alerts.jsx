// src/pages/Alerts.jsx — replaces pages/alerts.py
// Live: pulls from Person A's real GET /alerts (see FOR_PERSON_C.md /
// API_CONTRACT.md for the confirmed Alert object shape).

import { useEffect, useState } from "react";
import PageShell from "../components/PageShell.jsx";
import { getAlerts, resolveAlert } from "../api.js";
import { API_BASE_URL } from "../config.js";

const SEVERITY_ORDER = ["critical", "warning", "info"];
const SEVERITY_LABEL = { critical: "Critical", warning: "Warning", info: "Info" };

function formatTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function Alerts() {
  const [alerts, setAlerts] = useState([]);
  const [state, setState] = useState("loading"); // loading | ready | error
  const [resolvingId, setResolvingId] = useState(null);

  useEffect(() => {
    let cancelled = false;
    getAlerts()
      .then((res) => {
        if (cancelled) return;
        const list = Array.isArray(res.data) ? res.data : res.data.alerts || [];
        setAlerts(list.filter((a) => !a.resolved));
        setState("ready");
      })
      .catch(() => {
        if (!cancelled) setState("error");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleResolve = async (id) => {
    setResolvingId(id);
    try {
      await resolveAlert(id);
      setAlerts((prev) => prev.filter((a) => a.id !== id));
    } catch {
      // Leave the alert in place if the request fails; a proper toast/
      // error surface can replace this once the endpoint is confirmed.
    } finally {
      setResolvingId(null);
    }
  };

  const grouped = SEVERITY_ORDER.map((severity) => ({
    severity,
    items: alerts.filter((a) => a.severity === severity),
  })).filter((g) => g.items.length > 0);

  const statusMessage =
    state === "loading"
      ? "Loading alerts…"
      : state === "error"
      ? `Couldn't reach the backend at ${API_BASE_URL} — make sure Person A's API is running.`
      : alerts.length === 0
      ? "All clear — no active alerts."
      : `${alerts.length} active alert${alerts.length === 1 ? "" : "s"}.`;

  return (
    <PageShell
      group="Store Operations"
      icon="🚨"
      title="Alerts"
      caption="Know the moment something needs attention."
      status={statusMessage}
    >
      {state === "ready" && alerts.length > 0 && (
        <div>
          {grouped.map((group) => (
            <div className="bb-card bb-alert-group" key={group.severity}>
              <p className={`bb-alert-group-title bb-severity-${group.severity}`}>
                {SEVERITY_LABEL[group.severity]} ({group.items.length})
              </p>
              <ul className="bb-alert-list">
                {group.items.map((alert) => (
                  <li className="bb-alert-item" key={alert.id}>
                    <div>
                      <p className="bb-alert-message">{alert.message}</p>
                      <p className="bb-alert-meta">
                        {alert.item_name ? `${alert.item_name} · ` : ""}
                        {formatTime(alert.created_at)}
                      </p>
                    </div>
                    <button
                      type="button"
                      className="bb-alert-resolve"
                      onClick={() => handleResolve(alert.id)}
                      disabled={resolvingId === alert.id}
                    >
                      {resolvingId === alert.id ? "Resolving…" : "Resolve"}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </PageShell>
  );
}
