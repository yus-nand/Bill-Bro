# config.py
"""
Centralized configuration for the BillBro Streamlit frontend.
Reads from environment variables (via .env) with sensible local defaults.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Backend / API (Person A) ───────────────────────────────────────────────
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:5000")

# ── ML Model (Person B) ────────────────────────────────────────────────────
MODEL_PATH = os.getenv("MODEL_PATH", "models/grocery_yolov8.pt")

# ── Store / Local data ─────────────────────────────────────────────────────
STORE_ID    = os.getenv("STORE_ID", "store_001")
PRICES_PATH = os.getenv("PRICES_PATH", "prices.json")

# ── Streamlit page config ──────────────────────────────────────────────────
PAGE_TITLE  = "BillBro Smart Checkout"
PAGE_ICON   = "🛍️"
PAGE_LAYOUT = "wide"

# ── Detection defaults ─────────────────────────────────────────────────────
DEFAULT_CONF_THRESHOLD = 0.50
DEFAULT_TAX_RATE_PCT   = 18  # GST %

APP_VERSION = "0.1.0 (Alpha) — Week 1 skeleton"
