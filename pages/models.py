# pages/models.py
import streamlit as st


def show():
    st.title("🤖 Model Dashboard")
    st.caption("Model version history, metrics, and rollout controls.")

    st.info("Model version info will appear here in Week 8.")

    # TODO (Week 8):
    # - Version history table (trained_at, accuracy, num_classes)
    # - Metrics display (per-class precision/recall if available)
    # - Activate / rollback a model version
