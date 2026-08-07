"""
app.py — Automated Grocery Checkout  (v2)
Changes in this version
───────────────────────
• GST fixed at 18% — no slider, shown as a constant on all receipts
• AUTO-ADD: items are added to cart automatically on every input type:
    - Image upload  → detect + add instantly, no button press
    - Webcam (Live) → StableDetectionTracker fires after item is stable
                      for 15 consecutive detection runs (~1 s)
    - Camera Snap   → st.camera_input captures one frame → detect + add
    - Video         → deduplicated unique items added after processing
• Accuracy improvements from predict.py:
    - conf default lowered to 0.45
    - iou  default lowered to 0.40
    - preprocessing (contrast/sharpness) enabled by default
    - TTA toggle in sidebar (disabled by default for speed)

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
    GST_RATE,
    GST_LABEL,
    StableDetectionTracker,
    build_cart,
    calculate_total,
    confidence_stats,
    deduplicate_detections,
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

# ─── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
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
.gst-badge {
    display: inline-block;
    background: #e8f5e9;
    color: #2e7d32;
    border-radius: 6px;
    padding: 3px 10px;
    font-size: 12px;
    font-weight: 600;
    margin-bottom: 8px;
}
.auto-add-banner {
    background: #e8f5e9;
    border: 1px solid #a5d6a7;
    border-radius: 10px;
    padding: 10px 14px;
    color: #1b5e20;
    font-size: 14px;
    margin-bottom: 12px;
}
.stable-bar-wrap {
    background: #e0e0e0;
    border-radius: 6px;
    height: 8px;
    margin: 6px 0 2px;
    overflow: hidden;
}
.stable-bar-fill {
    height: 8px;
    border-radius: 6px;
    background: linear-gradient(90deg, #43a047, #66bb6a);
    transition: width 0.2s;
}
.receipt {
    font-family: 'Courier New', monospace;
    background: #fffef2;
    border: 2px dashed #ccc;
    border-radius: 10px;
    padding: 20px;
    white-space: pre-wrap;
    font-size: 12px;
}
.price-not-found {
    color: #e65100;
    font-size: 12px;
}
</style>
""", unsafe_allow_html=True)


# ─── Session state ────────────────────────────────────────────────────────────
def _init_state():
    defaults = {
        "cart":         {},
        "scan_count":   0,
        "show_receipt": False,
        "tracker":      StableDetectionTracker(required_frames=15, cooldown_frames=40),
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()


# ─── Model loader ─────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner="Loading YOLOv8 model…")
def load_detector(model_path: str, prices_path: str, use_tta: bool):
    detector = GroceryDetector(model_path, use_tta=use_tta)
    prices   = load_prices(prices_path)
    return detector, prices


# ─── Cart helpers ─────────────────────────────────────────────────────────────
def add_to_cart(detections: list[dict]) -> int:
    """Add detections to cart. Returns number of items added."""
    new_items = build_cart(detections)
    st.session_state.cart = merge_carts(st.session_state.cart, new_items)
    st.session_state.scan_count += 1
    return sum(new_items.values())


def render_sidebar(prices: dict):
    """Render the persistent cart sidebar."""
    st.sidebar.header("🛒 Shopping Cart")
    st.sidebar.markdown(
        f'<span class="gst-badge">GST 18% included on all items</span>',
        unsafe_allow_html=True,
    )

    if not st.session_state.cart:
        st.sidebar.info("Cart is empty. Items are added automatically when detected.")
        return

    bill = calculate_total(st.session_state.cart, prices)

    # Line items with remove buttons
    for li in bill["line_items"]:
        key = li["name"].lower().replace(" ", "_")
        col1, col2, col3, col4 = st.sidebar.columns([3, 1, 2, 1])
        col1.write(f"**{li['name']}**")
        col2.write(f"×{li['qty']}")
        col3.write(f"₹{li['subtotal']:.2f}")
        if col4.button("−", key=f"rm_{key}"):
            st.session_state.cart = remove_item(st.session_state.cart, key)
            st.rerun()

    st.sidebar.divider()

    # Totals
    st.sidebar.write(f"Subtotal: ₹{bill['subtotal']:.2f}")
    st.sidebar.write(f"{bill['tax_label']}: ₹{bill['tax']:.2f}")
    st.sidebar.markdown(
        f"<div class='total-banner'>₹ {bill['total']:.2f}</div>",
        unsafe_allow_html=True,
    )

    col_r, col_c = st.sidebar.columns(2)
    if col_r.button("🧾 Receipt", use_container_width=True):
        st.session_state.show_receipt = not st.session_state.show_receipt
    if col_c.button("🗑️ Clear", use_container_width=True):
        st.session_state.cart = {}
        st.session_state.tracker.reset()
        st.rerun()

    if st.session_state.show_receipt:
        receipt = format_receipt(st.session_state.cart, prices)
        st.sidebar.markdown(
            f"<div class='receipt'>{receipt}</div>",
            unsafe_allow_html=True,
        )


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    st.title("🛒 Smart Grocery Checkout")
    st.caption("Items are detected and added to cart automatically • GST 18% applied")

    # ── Sidebar config ────────────────────────────────────────────────────────
    with st.sidebar:
        st.header("⚙️ Settings")
        model_path  = st.text_input("Model path",  value="models/grocery_yolov8.pt")
        prices_path = st.text_input("Prices file", value="prices.json")

        st.divider()
        st.subheader("Detection")
        conf_thresh = st.slider(
            "Confidence threshold", 0.10, 0.95, 0.45, 0.05,
            help="Lower = more detections. Raise if you see false positives."
        )
        use_tta = st.toggle(
            "Test-Time Augmentation (TTA)",
            value=False,
            help="More accurate but ~2× slower. Disable for webcam use."
        )
        st.caption(f"TTA: {'ON ✓' if use_tta else 'OFF'} | GST: 18% (fixed)")
        st.divider()

    # ── Load model ────────────────────────────────────────────────────────────
    if not Path(model_path).exists():
        st.warning(
            "⚠️ Model file not found. Train with `train_colab.py` "
            "and place `best.pt` at `models/grocery_yolov8.pt`."
        )
        _demo_mode(prices_path)
        return

    try:
        detector, prices = load_detector(model_path, prices_path, use_tta)
    except Exception as e:
        st.error(f"Failed to load model: {e}")
        return

    render_sidebar(prices)

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📁 Upload Image",
        "📸 Camera Snap",
        "📷 Live Webcam",
        "🎥 Video",
        "📊 Analytics",
    ])

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # TAB 1 — Upload Image (auto-add)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    with tab1:
        st.subheader("Upload a grocery image")
        st.markdown(
            "<div class='auto-add-banner'>"
            "⚡ Items are added to your cart <strong>automatically</strong> as soon as the image is processed."
            "</div>",
            unsafe_allow_html=True,
        )

        uploaded = st.file_uploader(
            "Drop an image or click to browse",
            type=["jpg", "jpeg", "png", "webp"],
        )

        if uploaded:
            pil_img   = Image.open(uploaded).convert("RGB")
            img_array = np.array(pil_img)

            with st.spinner("🔍 Detecting items…"):
                dets, annotated = detector.detect(img_array, conf=conf_thresh)

            col_img, col_info = st.columns([3, 2])

            with col_img:
                st.image(
                    resize_for_display(annotated, 720),
                    caption=f"{len(dets)} item(s) detected",
                    use_container_width=True,
                )

            with col_info:
                if dets:
                    # ── AUTO-ADD ──────────────────────────────────
                    n_added = add_to_cart(dets)
                    st.success(f"✅ **{n_added} item(s) automatically added to cart!**")

                    summary = detection_summary(dets)
                    cstats  = confidence_stats(dets)

                    c1, c2, c3 = st.columns(3)
                    c1.metric("Detected",     summary["total"])
                    c2.metric("Unique",       summary["unique_items"])
                    c3.metric("Avg Conf",     f"{cstats['mean']:.0%}")

                    # Detected items table
                    det_df = pd.DataFrame([
                        {
                            "Item":       d["name"].replace("_", " ").title(),
                            "Confidence": f"{d['confidence']:.0%}",
                            "Price":      f"₹{prices.get(d['name'], 0):.2f}",
                        }
                        for d in dets
                    ])
                    st.dataframe(det_df, hide_index=True, use_container_width=True)

                    # Show items with missing prices
                    missing = [
                        d["name"] for d in dets if prices.get(d["name"], 0) == 0
                    ]
                    if missing:
                        st.warning(
                            f"⚠️ No price found for: "
                            f"{', '.join(m.replace('_',' ').title() for m in missing)}. "
                            "Add them to `prices.json`."
                        )
                else:
                    st.warning(
                        "No items detected. Try lowering the confidence threshold "
                        "or improve lighting."
                    )

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # TAB 2 — Camera Snap (capture + auto-add in one click)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    with tab2:
        st.subheader("Camera snapshot")
        st.markdown(
            "<div class='auto-add-banner'>"
            "📸 Click the capture button below. Items are detected and added to cart instantly."
            "</div>",
            unsafe_allow_html=True,
        )

        captured = st.camera_input(
            "Point camera at items, then click the capture button",
            key="camera_snap",
        )

        if captured:
            pil_snap  = Image.open(captured).convert("RGB")
            snap_arr  = np.array(pil_snap)

            with st.spinner("🔍 Detecting…"):
                dets, annotated = detector.detect(snap_arr, conf=conf_thresh)

            col_a, col_b = st.columns([3, 2])

            with col_a:
                st.image(annotated, caption="Detection result", use_container_width=True)

            with col_b:
                if dets:
                    n_added = add_to_cart(dets)
                    st.success(f"✅ **{n_added} item(s) added to cart!**")

                    for d in dets:
                        price = prices.get(d["name"], 0)
                        flag  = "" if price > 0 else " ⚠️ price missing"
                        st.write(
                            f"• **{d['name'].replace('_',' ').title()}** "
                            f"({d['confidence']:.0%}) — ₹{price:.2f}{flag}"
                        )
                else:
                    st.warning("No items detected. Retake with better lighting or angle.")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # TAB 3 — Live Webcam (stable-detection auto-add)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    with tab3:
        st.subheader("Live webcam — continuous scanning")
        st.markdown(
            "<div class='auto-add-banner'>"
            "🎯 Hold an item steady in front of the camera. "
            "Once it's stably detected for ~1 second, it's <strong>auto-added</strong> to the cart. "
            "Remove the item, show the next one."
            "</div>",
            unsafe_allow_html=True,
        )

        run_webcam   = st.toggle("▶ Start Webcam", key="webcam_toggle")
        col_feed, col_status = st.columns([3, 2])
        frame_holder = col_feed.empty()
        prog_holder  = col_status.empty()
        status_holder = col_status.empty()

        if run_webcam:
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                st.error("Cannot access webcam. Check your browser camera permissions.")
            else:
                tracker    = st.session_state.tracker
                frame_idx  = 0
                webcam_dets = []

                try:
                    while st.session_state.get("webcam_toggle", False):
                        ret, frame = cap.read()
                        if not ret:
                            break

                        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                        if frame_idx % 3 == 0:   # run inference every 3rd frame
                            webcam_dets, annotated = detector.detect(
                                frame_rgb, conf=conf_thresh
                            )
                            # Check stable detection
                            should_add, stable_dets = tracker.update(webcam_dets)
                            if should_add and stable_dets:
                                n = add_to_cart(stable_dets)
                                names = ", ".join(
                                    set(d["name"].replace("_"," ").title()
                                        for d in stable_dets)
                                )
                                status_holder.success(f"✅ Added: **{names}** ({n} item{'s' if n>1 else ''})")
                        else:
                            annotated = frame_rgb

                        frame_holder.image(
                            annotated, channels="RGB", use_container_width=True
                        )

                        # Stability progress bar
                        if webcam_dets and not tracker.in_cooldown:
                            pct = int(tracker.progress * 100)
                            prog_holder.markdown(
                                f"**Stabilising… {pct}%**\n"
                                f"<div class='stable-bar-wrap'>"
                                f"<div class='stable-bar-fill' style='width:{pct}%'></div>"
                                f"</div>",
                                unsafe_allow_html=True,
                            )
                        elif tracker.in_cooldown:
                            prog_holder.info("⏳ Cooldown — remove item and show the next one.")
                        else:
                            prog_holder.empty()
                            status_holder.empty()

                        frame_idx += 1
                        time.sleep(0.03)
                finally:
                    cap.release()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # TAB 4 — Video (auto-add unique items after processing)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    with tab4:
        st.subheader("Process a video file")
        st.markdown(
            "<div class='auto-add-banner'>"
            "🎬 Upload a video of your grocery items. "
            "Unique items are <strong>auto-added</strong> to the cart after processing."
            "</div>",
            unsafe_allow_html=True,
        )

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
            cap.release()

            st.info(f"Video: **{total_frames}** frames @ **{fps:.0f}** fps")

            if st.button("▶ Process & Auto-Add to Cart", type="primary"):
                cap       = cv2.VideoCapture(tfile.name)
                stframe   = st.empty()
                progress  = st.progress(0, text="Processing video…")
                all_dets  = []
                frame_idx = 0
                skip      = max(1, int(fps // 5))   # analyse 5 frames / sec

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
                        stframe.image(annotated, channels="RGB", use_container_width=True)

                    pct = min(frame_idx / max(total_frames, 1), 1.0)
                    progress.progress(pct, text=f"Frame {frame_idx}/{total_frames}")
                    frame_idx += 1

                cap.release()
                progress.progress(1.0, text="Done!")

                if all_dets:
                    # Deduplicate: one entry per unique class (best confidence)
                    unique_dets = deduplicate_detections(all_dets)
                    n_added     = add_to_cart(unique_dets)

                    names_added = ", ".join(
                        d["name"].replace("_", " ").title() for d in unique_dets
                    )
                    st.success(
                        f"✅ **{n_added} unique item(s) auto-added:** {names_added}"
                    )
                    st.caption(
                        f"({len(all_dets)} total detections across video frames — "
                        f"deduplicated to {len(unique_dets)} unique items)"
                    )
                else:
                    st.warning("No items detected in the video.")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # TAB 5 — Analytics
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    with tab5:
        st.subheader("Session analytics")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Scans",          st.session_state.scan_count)
        c2.metric("Cart items",     sum(st.session_state.cart.values()))
        c3.metric("Unique products", len(st.session_state.cart))
        c4.metric("GST rate",       "18%")

        if st.session_state.cart:
            bill = calculate_total(st.session_state.cart, prices)

            st.markdown("### Bill breakdown")
            bill_df = pd.DataFrame([
                {
                    "Item":         li["name"],
                    "Qty":          li["qty"],
                    "Unit (₹)":     f"₹{li['unit_price']:.2f}",
                    "Subtotal (₹)": f"₹{li['subtotal']:.2f}",
                    "Price found":  "✓" if li["found"] else "✗ missing",
                }
                for li in bill["line_items"]
            ])
            st.dataframe(bill_df, hide_index=True, use_container_width=True)

            ca, cb, cc = st.columns(3)
            ca.metric("Subtotal",      f"₹{bill['subtotal']:.2f}")
            cb.metric(bill["tax_label"], f"₹{bill['tax']:.2f}")
            cc.metric("Grand Total",   f"₹{bill['total']:.2f}")

        st.divider()
        st.markdown("### Price list")
        price_df = pd.DataFrame([
            {"Item": k.replace("_", " ").title(), "Price (₹)": f"₹{v:.2f}"}
            for k, v in sorted(prices.items())
        ])
        st.dataframe(price_df, hide_index=True, use_container_width=True)

        st.markdown("### Model info")
        try:
            info = detector.info()
            st.json(info)
        except Exception:
            pass


# ─── Demo mode ────────────────────────────────────────────────────────────────
def _demo_mode(prices_path: str):
    st.info("🔔 **Demo mode** — model not found. Showing sample cart.")
    try:
        prices = load_prices(prices_path)
    except FileNotFoundError:
        st.error("prices.json also not found. Check the project directory.")
        return

    demo_cart = {"apple": 2, "banana": 3, "milk": 1, "bread": 1, "chips": 2}
    bill      = calculate_total(demo_cart, prices)

    st.subheader("Sample bill (18% GST)")
    col1, col2 = st.columns(2)
    with col1:
        for li in bill["line_items"]:
            st.write(f"**{li['name']}** ×{li['qty']} — ₹{li['subtotal']:.2f}")
    with col2:
        st.metric("Subtotal",        f"₹{bill['subtotal']:.2f}")
        st.metric(bill["tax_label"], f"₹{bill['tax']:.2f}")
        st.metric("Grand Total",     f"₹{bill['total']:.2f}")


if __name__ == "__main__":
    main()
