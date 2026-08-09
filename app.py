"""
app.py — Automated Grocery Checkout
Streamlit-based front-end that uses YOLOv8 for real-time item detection.

Features:
  - Manual "Add to Cart" button — items are NOT added automatically
  - GST slider (0–28%) — adjustable by the user
  - Image upload, Webcam, Video, and Analytics tabs

Run with:   streamlit run app.py
"""

import tempfile
import time
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image

from predict import GroceryDetector
from utils import (
    build_cart,
    calculate_total,
    confidence_stats,
    detection_summary,
    format_receipt,
    load_prices,
    merge_carts,
    remove_item,
    resize_for_display,
)

# ─── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Smart Grocery Checkout",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
.metric-card {
    background: #f0f8ff;
    border-radius: 12px;
    padding: 16px;
    text-align: center;
    border: 1px solid #dce8f5;
}
.metric-value { font-size: 28px; font-weight: 700; color: #1a73e8; }
.metric-label { font-size: 13px; color: #555; margin-top: 4px; }
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
.receipt {
    font-family: 'Courier New', monospace;
    background: #fffef2;
    border: 2px dashed #ccc;
    border-radius: 10px;
    padding: 20px;
    white-space: pre-wrap;
    font-size: 13px;
}
</style>
""", unsafe_allow_html=True)


# ─── Session state defaults ───────────────────────────────────────────────────
def _init_state():
    defaults = {
        "cart":            {},
        "detector":        None,
        "prices":          {},
        "scan_count":      0,
        "last_detections": [],
        "show_receipt":    False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()


# ─── Model loader (cached) ────────────────────────────────────────────────────
@st.cache_resource(show_spinner="Loading YOLOv8 model…")
def load_detector(model_path: str, _prices_path: str) -> tuple:
    detector = GroceryDetector(model_path)
    prices   = load_prices(_prices_path)
    return detector, prices


# ─── Helpers ──────────────────────────────────────────────────────────────────
def add_to_cart(detections: list):
    new_items = build_cart(detections)
    st.session_state.cart = merge_carts(st.session_state.cart, new_items)
    st.session_state.scan_count += 1
    st.session_state.last_detections = detections


def render_cart_sidebar(prices: dict, tax_rate: float):
    st.sidebar.header("🛒 Shopping Cart")

    if not st.session_state.cart:
        st.sidebar.info("Cart is empty. Detect items and click 'Add to Cart'.")
        return

    bill = calculate_total(st.session_state.cart, prices, tax_rate=tax_rate)

    for li in bill["line_items"]:
        col1, col2, col3, col4 = st.sidebar.columns([3, 1, 2, 1])
        col1.write(f"**{li['name']}**")
        col2.write(f"×{li['qty']}")
        col3.write(f"₹{li['subtotal']:.2f}")
        if col4.button("−", key=f"rm_{li['name']}"):
            st.session_state.cart = remove_item(
                st.session_state.cart,
                li["name"].lower().replace(" ", "_")
            )
            st.rerun()

    st.sidebar.divider()
    st.sidebar.write(f"Subtotal: ₹{bill['subtotal']:.2f}")
    st.sidebar.write(f"GST ({tax_rate:.0%}): ₹{bill['tax']:.2f}")
    st.sidebar.markdown(
        f"<div class='total-banner'>Total: ₹{bill['total']:.2f}</div>",
        unsafe_allow_html=True,
    )

    col_r, col_c = st.sidebar.columns(2)
    if col_r.button("🖨️ Receipt", use_container_width=True):
        st.session_state.show_receipt = not st.session_state.show_receipt
    if col_c.button("🗑️ Clear", use_container_width=True):
        st.session_state.cart = {}
        st.rerun()

    if st.session_state.show_receipt:
        receipt_text = format_receipt(
            st.session_state.cart, prices, tax_rate=tax_rate
        )
        st.sidebar.markdown(
            f"<div class='receipt'>{receipt_text}</div>",
            unsafe_allow_html=True,
        )


# ─── Main app ─────────────────────────────────────────────────────────────────
def main():
    st.title("🛒 Smart Grocery Checkout")
    st.caption("Automated item detection & billing — powered by YOLOv8")

    # ── Sidebar config ─────────────────────────────────────────────────────────
    with st.sidebar:
        st.header("⚙️ Configuration")
        model_path  = st.text_input("Model path",  value="models/grocery_yolov8.pt")
        prices_path = st.text_input("Prices file", value="prices.json")
        conf_thresh = st.slider(
            "Confidence threshold", 0.10, 0.95, 0.50, 0.05,
            help="Lower = more detections; Higher = fewer but more accurate"
        )
        tax_rate = st.slider("GST (%)", 0, 28, 18) / 100.0
        st.divider()

    # ── Load model ─────────────────────────────────────────────────────────────
    if not Path(model_path).exists():
        st.warning(
            "⚠️ Model file not found. Train a model with the Colab notebook first, "
            "then place it at `models/grocery_yolov8.pt`."
        )
        _demo_mode(prices_path, tax_rate)
        return

    try:
        detector, prices = load_detector(model_path, prices_path)
        st.session_state.prices = prices
    except Exception as e:
        st.error(f"Failed to load model: {e}")
        return

    render_cart_sidebar(prices, tax_rate)

    # ── Input tabs ─────────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs(
        ["📁 Upload Image", "📷 Webcam", "🎥 Video", "📊 Analytics"]
    )

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # TAB 1 — Image upload
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    with tab1:
        st.subheader("Upload a grocery image")
        uploaded = st.file_uploader(
            "Drag and drop or browse", type=["jpg", "jpeg", "png", "webp"]
        )

        if uploaded:
            pil_img   = Image.open(uploaded).convert("RGB")
            img_array = np.array(pil_img)

            col_img, col_info = st.columns([3, 2])

            with st.spinner("🔍 Running detection…"):
                dets, annotated = detector.detect(img_array, conf=conf_thresh)

            with col_img:
                st.image(
                    resize_for_display(annotated, max_width=700),
                    caption=f"{len(dets)} item(s) detected",
                    use_container_width=True,
                )

            with col_info:
                if dets:
                    st.success(f"✅ Found **{len(dets)}** item(s)")
                    summary = detection_summary(dets)
                    cstats  = confidence_stats(dets)

                    c1, c2, c3 = st.columns(3)
                    c1.metric("Detections",   summary["total"])
                    c2.metric("Unique Items", summary["unique_items"])
                    c3.metric("Avg Conf",     f"{cstats['mean']:.0%}")

                    st.write("**Detected items:**")
                    det_df = pd.DataFrame([
                        {
                            "Item":       n.replace("_", " ").title(),
                            "Confidence": f"{c:.0%}",
                            "Price (₹)":  f"₹{prices.get(n, 0):.2f}",
                        }
                        for n, c, _ in dets
                    ])
                    st.dataframe(det_df, hide_index=True, use_container_width=True)

                    if st.button("➕ Add All to Cart", type="primary"):
                        add_to_cart(dets)
                        st.success("Added to cart!")
                        st.rerun()
                else:
                    st.warning(
                        "No items detected. Try lowering the confidence threshold."
                    )

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # TAB 2 — Webcam
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    with tab2:
        st.subheader("Live webcam detection")
        st.info(
            "💡 Hold items clearly in front of the camera. "
            "Click **Add Detected Items** after scanning."
        )

        run_webcam   = st.toggle("▶ Start Webcam", key="webcam_toggle")
        frame_holder = st.empty()
        status_bar   = st.empty()
        webcam_dets  = []

        if run_webcam:
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                st.error("Cannot access webcam. Check permissions.")
            else:
                frame_count = 0
                try:
                    while st.session_state.get("webcam_toggle", False):
                        ret, frame = cap.read()
                        if not ret:
                            break

                        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                        # Run inference every 3 frames to stay smooth
                        if frame_count % 3 == 0:
                            webcam_dets, annotated = detector.detect(
                                frame_rgb, conf=conf_thresh
                            )
                        else:
                            annotated = frame_rgb

                        frame_holder.image(
                            annotated, channels="RGB", use_container_width=True
                        )

                        if webcam_dets:
                            names = ", ".join(
                                set(n.replace("_", " ").title()
                                    for n, _, _ in webcam_dets)
                            )
                            status_bar.success(f"Seeing: {names}")
                        else:
                            status_bar.info("Scanning…")

                        frame_count += 1
                        time.sleep(0.03)
                finally:
                    cap.release()

            if webcam_dets:
                if st.button("➕ Add Detected Items to Cart", type="primary"):
                    add_to_cart(webcam_dets)
                    st.rerun()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # TAB 3 — Video
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    with tab3:
        st.subheader("Process a video file")
        video_file = st.file_uploader(
            "Upload video", type=["mp4", "avi", "mov", "mkv"]
        )

        if video_file:
            tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
            tfile.write(video_file.read())
            tfile.close()

            cap          = cv2.VideoCapture(tfile.name)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps          = cap.get(cv2.CAP_PROP_FPS) or 25

            st.info(f"Video: {total_frames} frames at {fps:.0f} fps")
            process_btn = st.button("▶ Process Video", type="primary")

            if process_btn:
                stframe     = st.empty()
                progress    = st.progress(0)
                all_dets    = []
                frame_idx   = 0
                skip        = max(1, int(fps // 5))   # analyse 5 frames/sec

                with st.spinner("Processing video…"):
                    while cap.isOpened():
                        ret, frame = cap.read()
                        if not ret:
                            break

                        if frame_idx % skip == 0:
                            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            dets, annotated = detector.detect(
                                frame_rgb, conf=conf_thresh
                            )
                            all_dets.extend(dets)
                            stframe.image(
                                annotated, channels="RGB", use_container_width=True
                            )

                        progress.progress(
                            min(frame_idx / max(total_frames, 1), 1.0)
                        )
                        frame_idx += 1

                cap.release()
                st.success("✅ Video processed!")

                if all_dets:
                    summary = detection_summary(all_dets)
                    st.write(f"**Total detections:** {summary['total']}")
                    st.write(
                        f"**Unique items found:** "
                        f"{', '.join(summary['by_class'].keys())}"
                    )

                    if st.button("➕ Add Video Items to Cart"):
                        # Deduplicate — take unique items, not every frame
                        unique_dets = []
                        seen = set()
                        for d in all_dets:
                            if d[0] not in seen:
                                unique_dets.append(d)
                                seen.add(d[0])
                        add_to_cart(unique_dets)
                        st.rerun()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # TAB 4 — Analytics
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    with tab4:
        st.subheader("Session analytics")

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Scans",     st.session_state.scan_count)
        c2.metric("Cart Items",      sum(st.session_state.cart.values()))
        c3.metric("Unique Products", len(st.session_state.cart))

        if st.session_state.cart:
            bill = calculate_total(
                st.session_state.cart, prices, tax_rate=tax_rate
            )
            st.markdown("### Bill breakdown")
            bill_df = pd.DataFrame(bill["line_items"])
            bill_df.columns = ["Item", "Qty", "Unit Price (₹)", "Subtotal (₹)"]
            st.dataframe(bill_df, hide_index=True, use_container_width=True)

            col_a, col_b, col_c = st.columns(3)
            col_a.metric("Subtotal",            f"₹{bill['subtotal']:.2f}")
            col_b.metric(f"GST ({tax_rate:.0%})", f"₹{bill['tax']:.2f}")
            col_c.metric("Grand Total",         f"₹{bill['total']:.2f}")

        st.markdown("### Price list")
        price_df = pd.DataFrame([
            {"Item": k.replace("_", " ").title(), "Price (₹)": f"₹{v:.2f}"}
            for k, v in sorted(prices.items())
        ])
        st.dataframe(price_df, hide_index=True, use_container_width=True)


# ─── Demo mode (no model) ─────────────────────────────────────────────────────
def _demo_mode(prices_path: str, tax_rate: float):
    """Show UI with mock data when no model is present."""
    st.info(
        "🔔 Running in **Demo Mode** — train and add your model to enable live detection."
    )
    try:
        prices = load_prices(prices_path)
    except FileNotFoundError:
        st.error(
            "prices.json not found either. Make sure you have the full project files."
        )
        return

    st.subheader("Sample cart preview")
    demo_cart = {"apple": 2, "banana": 3, "milk": 1, "bread": 1, "chips": 2}
    bill      = calculate_total(demo_cart, prices, tax_rate=tax_rate)

    col1, col2 = st.columns(2)
    with col1:
        for li in bill["line_items"]:
            st.write(f"**{li['name']}** ×{li['qty']} — ₹{li['subtotal']:.2f}")
    with col2:
        st.metric("Subtotal",            f"₹{bill['subtotal']:.2f}")
        st.metric(f"GST ({tax_rate:.0%})", f"₹{bill['tax']:.2f}")
        st.metric("Grand Total",         f"₹{bill['total']:.2f}")


if __name__ == "__main__":
    main()
