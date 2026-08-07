# pages/admin.py
import streamlit as st


def show():
    st.title("⚙️ Admin Panel")
    st.caption("Store settings, bulk uploads, and manual overrides.")

    st.info("Admin features will appear here in Week 7.")

    # TODO (Week 7):
    # - Bulk price/inventory upload (CSV)
    # - Manual stock adjustments
    # - Store-level settings (tax rate, store ID, etc.)
