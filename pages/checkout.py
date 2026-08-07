# pages/checkout.py
import streamlit as st


def show():
    st.title("🛒 Smart Checkout")
    st.caption("Detect grocery items via camera or upload and bill them out.")

    st.info(
        "Checkout detection isn't wired up yet — this tab is a placeholder "
        "for Week 2."
    )

    # TODO (Week 2):
    # - Image upload (st.file_uploader) / camera input (st.camera_input)
    # - Run GroceryDetector.detect() from predict.py on the image
    # - Show annotated image + detected items table
    # - "Add to Cart" button -> build_cart() from utils.py
    # - POST /checkout/bill to Person A's API once it's ready
    # - Show format_receipt() output
