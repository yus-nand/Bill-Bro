// src/context/TourContext.jsx
//
// A lightweight, dependency-free guided tour — no Shepherd.js/Intro.js,
// since this sandbox has no network access to install new npm packages
// and the whole thing is small enough not to need one. Steps can span
// different pages: each step names a route, and the tour navigates there
// (via react-router's navigate, same SPA transition as clicking a nav
// link) before it goes looking for that step's target element.
//
// Mounted once in App.jsx, above the router content (same tier as the
// other Providers), so it survives whatever route the tour itself
// navigates to instead of being torn down mid-tour.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { useNavigate, useLocation } from "react-router-dom";

const SEEN_KEY = "billbro-tour-seen";

// Each step: which page it lives on, a CSS selector for the element to
// spotlight, and the copy to show next to it. Selectors point at
// data-tour="..." attributes sprinkled through the pages specifically
// for this — see PageShell.jsx (page-header/page-status, present on
// every page) and the per-page ones (checkout-upload, inventory-search,
// additem-form, admin-settings, topnav).
const STEPS = [
  {
    route: "/checkout",
    target: '[data-tour="topnav"]',
    title: "Getting around",
    body: "Every part of BillBro lives up here — Checkout, Inventory, Alerts, and the catalog tools. On a small screen, the same links are behind the menu button.",
  },
  {
    route: "/checkout",
    target: '[data-tour="checkout-upload"]',
    title: "Ring up a sale",
    body: "Take or upload a photo — or use the webcam for a live view — and items are detected and added to the cart automatically.",
  },
  {
    route: "/inventory",
    target: '[data-tour="inventory-search"]',
    title: "Find anything fast",
    body: "Search narrows the table as you type. Each row has Restock (log a new batch) and Retrain (teach the model this item again) actions.",
  },
  {
    route: "/alerts",
    target: '[data-tour="page-status"]',
    title: "Stay ahead of stockouts",
    body: "Low-stock and out-of-stock alerts land here automatically as sales come through. Resolve one once you've acted on it.",
  },
  {
    route: "/add-item",
    target: '[data-tour="additem-form"]',
    title: "Add a new product",
    body: "Fill in the basics, then capture a handful of photos from different angles — that's what trains the model to recognize it at checkout.",
  },
  {
    route: "/admin",
    target: '[data-tour="admin-settings"]',
    title: "Store settings",
    body: "Set your tax rate, currency, and default low-stock threshold — or bulk-import your whole catalog from a CSV further down this page.",
  },
  {
    route: "/models",
    target: '[data-tour="page-status"]',
    title: "Track model accuracy",
    body: "Every trained version shows up here with its accuracy — activate an older one instantly if a retrain doesn't go well.",
  },
];

const TourContext = createContext(null);

export function TourProvider({ children }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [active, setActive] = useState(false);
  const [index, setIndex] = useState(0);
  const [rect, setRect] = useState(null); // target's bounding box, or null while it settles
  const [seen, setSeen] = useState(() => {
    if (typeof window === "undefined") return true;
    return window.localStorage.getItem(SEEN_KEY) === "true";
  });
  const settleTimerRef = useRef(null);

  const markSeen = useCallback(() => {
    setSeen(true);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(SEEN_KEY, "true");
    }
  }, []);

  const stop = useCallback(() => {
    setActive(false);
    setRect(null);
    markSeen();
  }, [markSeen]);

  const start = useCallback(() => {
    setIndex(0);
    setActive(true);
    setRect(null);
    if (location.pathname !== STEPS[0].route) navigate(STEPS[0].route);
  }, [navigate, location.pathname]);

  const goTo = useCallback(
    (nextIndex) => {
      if (nextIndex < 0) return;
      if (nextIndex >= STEPS.length) {
        stop();
        return;
      }
      setRect(null);
      setIndex(nextIndex);
      const step = STEPS[nextIndex];
      if (location.pathname !== step.route) navigate(step.route);
    },
    [navigate, location.pathname, stop]
  );

  const next = useCallback(() => goTo(index + 1), [goTo, index]);
  const prev = useCallback(() => goTo(index - 1), [goTo, index]);

  // After navigation (or on the very first step), the target may not be
  // in the DOM yet — the route just changed, or the section is further
  // down the page. Poll briefly rather than assuming it's there on the
  // next render; give up gracefully (tooltip just centers on screen)
  // rather than getting stuck if a selector ever goes stale.
  useEffect(() => {
    if (!active) return;
    const step = STEPS[index];
    let cancelled = false;
    let attempts = 0;

    const tryLocate = () => {
      if (cancelled) return;
      const el = document.querySelector(step.target);
      if (el) {
        el.scrollIntoView({ block: "center", behavior: "smooth" });
        // Give the smooth scroll a moment to actually land before measuring.
        settleTimerRef.current = setTimeout(() => {
          if (!cancelled) setRect(el.getBoundingClientRect());
        }, 220);
        return;
      }
      attempts += 1;
      if (attempts < 30) {
        settleTimerRef.current = setTimeout(tryLocate, 50);
      } else {
        setRect(undefined); // give up — tooltip falls back to screen-centered
      }
    };

    tryLocate();
    return () => {
      cancelled = true;
      if (settleTimerRef.current) clearTimeout(settleTimerRef.current);
    };
  }, [active, index]);

  // Keep the spotlight glued to its target through resizes/scroll while
  // a step is showing (e.g. the user manually scrolls to read more).
  useEffect(() => {
    if (!active || !rect) return;
    const step = STEPS[index];
    const reposition = () => {
      const el = document.querySelector(step.target);
      if (el) setRect(el.getBoundingClientRect());
    };
    window.addEventListener("resize", reposition);
    window.addEventListener("scroll", reposition, true);
    return () => {
      window.removeEventListener("resize", reposition);
      window.removeEventListener("scroll", reposition, true);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, index, Boolean(rect)]);

  const value = {
    active,
    index,
    total: STEPS.length,
    step: STEPS[index],
    rect,
    start,
    next,
    prev,
    stop,
    seen,
    markSeen,
  };

  return <TourContext.Provider value={value}>{children}</TourContext.Provider>;
}

export function useTour() {
  const ctx = useContext(TourContext);
  if (!ctx) {
    throw new Error("useTour must be used inside a TourProvider");
  }
  return ctx;
}
