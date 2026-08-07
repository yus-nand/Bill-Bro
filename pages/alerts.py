# pages/alerts.py
import streamlit as st


def show():
    st.title("🚨 Active Alerts")
    st.caption("Low stock, out-of-stock, and system alerts needing attention.")

    st.info("Active alerts will appear here once the alerts API is connected.")

    # TODO (Week 6):
    # - GET /alerts from Person A's backend
    # - Group by severity (critical / warning / info)
    # - Dismiss / acknowledge action per alert
