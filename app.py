# app.py
"""
BillBro — Streamlit Frontend Entry Point
Week 1: Skeleton app with sidebar navigation across 6 tabs.

Owner: Anshul (Person C, Frontend Lead)

Run with:   streamlit run app.py
"""

import streamlit as st

import config
from pages import checkout, inventory, alerts, admin, add_item, models

# ─── Page config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title=config.PAGE_TITLE,
    page_icon=config.PAGE_ICON,
    layout=config.PAGE_LAYOUT,
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ─────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    .metric-card {
        background: #f0f8ff;
        border-radius: 12px;
        padding: 16px;
        text-align: center;
        border: 1px solid #dce8f5;
    }
    .total-banner {
        background: linear-gradient(135deg, #1a73e8, #0d47a1);
        color: white;
        border-radius: 12px;
        padding: 18px;
        text-align: center;
        font-size: 22px;
        font-weight: 700;
        margin: 12px 0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─── Sidebar navigation ─────────────────────────────────────────────────────
st.sidebar.title("🛍️ BillBro")
st.sidebar.write("Smart Grocery Checkout & Inventory")
st.sidebar.divider()

PAGES = {
    "🛒 Checkout": checkout,
    "📦 Inventory": inventory,
    "🚨 Alerts": alerts,
    "⚙️ Admin": admin,
    "➕ Add Item": add_item,
    "🤖 Models": models,
}

page_name = st.sidebar.radio("Navigate to:", list(PAGES.keys()), index=0)

st.sidebar.divider()
st.sidebar.caption(f"Store: `{config.STORE_ID}`")
st.sidebar.caption(f"API: `{config.API_BASE_URL}`")
st.sidebar.info(f"Version: {config.APP_VERSION}")

# ─── Route to selected page ─────────────────────────────────────────────────
PAGES[page_name].show()
