# pages/inventory.py
import streamlit as st


def show():
    st.title("📦 Inventory Dashboard")
    st.caption("Live stock levels across all tracked items.")

    st.info("Stock levels will appear here once the inventory API is connected.")

    # TODO (Week 5):
    # - GET /inventory from Person A's backend
    # - Display as st.dataframe with search & filter (category, low-stock)
    # - Summary metrics: total SKUs, low-stock count, out-of-stock count
    # - Manual adjust: PATCH /inventory/adjust
