# pages/add_item.py
import streamlit as st


def show():
    st.title("➕ Add New Item")
    st.caption("Onboard a new product: capture images, train, and deploy.")

    st.info("The new-item workflow will appear here in Week 4.")

    # TODO (Week 4):
    # - Item info form (name, category, price)
    # - Image capture / upload for training samples
    # - POST /training/upload_images
    # - Poll GET /training/job/{job_id} for training progress
