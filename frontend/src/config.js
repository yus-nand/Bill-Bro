// src/config.js
// Centralized configuration for the BillBro React frontend.
// Mirrors config.py — reads from Vite env vars (.env) with local defaults.

// Person A's FastAPI backend runs on :8000 by default (see FOR_PERSON_C.md).
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
export const STORE_ID = import.meta.env.VITE_STORE_ID || "store_001";

export const PAGE_TITLE = "BillBro Smart Checkout";
export const PAGE_ICON = "🛍️";

export const DEFAULT_CONF_THRESHOLD = 0.5;
export const DEFAULT_TAX_RATE_PCT = 18; // GST %

export const APP_VERSION = "0.1.0 (Alpha) — React skeleton";
