// src/context/ToastContext.jsx
//
// Small, dependency-free toast system. Several pages had a real gap here
// already — Alerts.jsx's resolve handler used to fail silently with a
// comment saying "a proper toast/error surface can replace this once the
// endpoint is confirmed" (it's been confirmed a while now), and Inventory's
// restock/retrain flows only ever showed success by the row quietly
// closing, which is easy to miss. This gives every page one shared,
// consistent way to say "that worked" / "that didn't work" without
// blocking the UI or requiring the user to spot a small inline banner.
//
// Mounted once in App.jsx, above the router, same pattern as
// TrainingJobsContext/AddItemDraftContext — so a toast fired from any
// page (or from a background poll tick) always has somewhere to land.

import { createContext, useCallback, useContext, useRef, useState } from "react";

const ToastContext = createContext(null);
const DEFAULT_DURATION_MS = 4200;

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const idRef = useRef(0);

  const dismiss = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const push = useCallback(
    (message, { tone = "success", duration = DEFAULT_DURATION_MS } = {}) => {
      const id = ++idRef.current;
      setToasts((prev) => [...prev, { id, message, tone }]);
      if (duration > 0) {
        setTimeout(() => dismiss(id), duration);
      }
      return id;
    },
    [dismiss]
  );

  const toast = {
    success: (message, opts) => push(message, { ...opts, tone: "success" }),
    error: (message, opts) => push(message, { ...opts, tone: "error", duration: opts?.duration ?? 6000 }),
    info: (message, opts) => push(message, { ...opts, tone: "info" }),
  };

  return (
    <ToastContext.Provider value={{ toast, dismiss }}>
      {children}
      <div className="bb-toast-stack" aria-live="polite" aria-atomic="true">
        {toasts.map((t) => (
          <div key={t.id} className={`bb-toast bb-toast-${t.tone}`} role="status">
            <span className="bb-toast-icon" aria-hidden="true">
              {t.tone === "success" ? "✓" : t.tone === "error" ? "!" : "ℹ"}
            </span>
            <p>{t.message}</p>
            <button
              type="button"
              className="bb-toast-close"
              onClick={() => dismiss(t.id)}
              aria-label="Dismiss notification"
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used inside a ToastProvider");
  }
  return ctx.toast;
}
