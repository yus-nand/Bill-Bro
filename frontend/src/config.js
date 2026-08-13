// src/config.js
// Centralized configuration for the BillBro React frontend.
// Mirrors config.py — reads from Vite env vars (.env) with local defaults.

// Person A's FastAPI backend runs on :8000 by default (see FOR_PERSON_C.md),
// but locally it's often on :8001 instead (see api_app.py's CORS comment —
// "when 8000 is taken locally"). VITE_API_PORT lets that be set once
// without re-hardcoding a host.
//
// The fallback below used to be a hardcoded "http://localhost:8000" —
// worked fine from the same machine, but "localhost" means something
// different on every device. Open the app from a phone at
// http://192.168.1.42:5173 and a hardcoded localhost fallback would send
// every API call to the *phone's own* loopback address, not the Mac
// running the backend — every request just fails. Deriving the API host
// from wherever the page itself was loaded from fixes that automatically:
// load the app via localhost, calls go to localhost:<port>; load it via a
// LAN IP, calls go to that same IP's <port>. Still fully overridable via
// VITE_API_BASE_URL in .env for anything that needs a wholly different
// target (a staging server on another domain, etc).
const apiPort = import.meta.env.VITE_API_PORT || "8000";
const inferredApiBaseUrl =
  typeof window !== "undefined"
    ? `${window.location.protocol}//${window.location.hostname}:${apiPort}`
    : `http://localhost:${apiPort}`;
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || inferredApiBaseUrl;
export const STORE_ID = import.meta.env.VITE_STORE_ID || "store_001";

export const PAGE_TITLE = "BillBro Smart Checkout";
export const PAGE_ICON = "🛍️";

export const DEFAULT_CONF_THRESHOLD = 0.5;
export const DEFAULT_TAX_RATE_PCT = 18; // GST %

export const APP_VERSION = "0.1.0 (Alpha) — React skeleton";
