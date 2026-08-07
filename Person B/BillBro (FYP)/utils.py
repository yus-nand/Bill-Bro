"""
utils.py — Cart, pricing, and receipt helpers for the BillBro checkout UI.

Reconstructed to match the interface app.py expects:
    load_prices, build_cart, merge_carts, remove_item, calculate_total,
    format_receipt, detection_summary, confidence_stats, resize_for_display

All money values are treated as INR (₹) floats. Cart shape is a plain
dict[str, int]: {"apple": 2, "banana": 1, ...}. Detections shape matches
predict.GroceryDetector.detect(): list[(name, confidence, bbox)].
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

Detection = tuple[str, float, list[int]]


def load_prices(path: str) -> dict[str, float]:
    """Load the item → price lookup table.

    Args:
        path: Path to a JSON file of {item_name: price}.

    Returns:
        dict mapping item name to price in rupees.

    Raises:
        FileNotFoundError: If path does not exist.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Prices file not found: {path}")
    with open(p) as f:
        return json.load(f)


def build_cart(detections: list[Detection]) -> dict[str, int]:
    """Turn a list of detections into a {item_name: quantity} cart.

    Args:
        detections: List of (name, confidence, bbox) tuples.

    Returns:
        dict counting how many of each class appeared.
    """
    cart: dict[str, int] = {}
    for name, _confidence, _bbox in detections:
        cart[name] = cart.get(name, 0) + 1
    return cart


def merge_carts(cart_a: dict[str, int], cart_b: dict[str, int]) -> dict[str, int]:
    """Merge two carts by summing quantities per item.

    Args:
        cart_a: Existing cart.
        cart_b: Cart to merge in (e.g. newly scanned items).

    Returns:
        A new merged dict; inputs are not mutated.
    """
    merged = dict(cart_a)
    for name, qty in cart_b.items():
        merged[name] = merged.get(name, 0) + qty
    return merged


def remove_item(cart: dict[str, int], item_name: str) -> dict[str, int]:
    """Remove one unit of item_name from the cart (drop key if it hits 0).

    Args:
        cart: Current cart.
        item_name: Key to decrement. Matched case-insensitively against
            the cart's existing keys since the UI passes a lower-cased,
            underscore-joined string.

    Returns:
        A new cart dict; input is not mutated.
    """
    new_cart = dict(cart)
    key = item_name if item_name in new_cart else next(
        (k for k in new_cart if k.lower() == item_name.lower()), item_name
    )
    if key in new_cart:
        new_cart[key] -= 1
        if new_cart[key] <= 0:
            del new_cart[key]
    return new_cart


def calculate_total(
    cart: dict[str, int],
    prices: dict[str, float],
    tax_rate: float = 0.0,
) -> dict[str, Any]:
    """Compute line items, subtotal, tax, and grand total for a cart.

    Args:
        cart: {item_name: quantity}.
        prices: {item_name: unit_price}. Missing items default to ₹0 —
            callers should treat a 0-priced line item as a data gap to
            fix in prices.json, not a valid free item.
        tax_rate: Fractional GST rate, e.g. 0.18 for 18%.

    Returns:
        {
            "line_items": [{"name", "qty", "price", "subtotal"}, ...],
            "subtotal": float,
            "tax": float,
            "total": float,
        }
    """
    line_items = []
    subtotal = 0.0

    for name, qty in cart.items():
        unit_price = prices.get(name, 0.0)
        line_subtotal = unit_price * qty
        subtotal += line_subtotal
        line_items.append({
            "name": name.replace("_", " ").title(),
            "qty": qty,
            "price": unit_price,
            "subtotal": line_subtotal,
        })

    tax = subtotal * tax_rate
    total = subtotal + tax

    return {
        "line_items": line_items,
        "subtotal": subtotal,
        "tax": tax,
        "total": total,
    }


def format_receipt(
    cart: dict[str, int],
    prices: dict[str, float],
    tax_rate: float = 0.0,
    store_name: str = "BillBro",
) -> str:
    """Render a monospace, receipt-style text block for display.

    Args:
        cart: {item_name: quantity}.
        prices: {item_name: unit_price}.
        tax_rate: Fractional GST rate.
        store_name: Header line for the receipt.

    Returns:
        A newline-joined string suitable for a <pre>-style container.
    """
    bill = calculate_total(cart, prices, tax_rate=tax_rate)
    width = 40
    lines = [
        store_name.center(width),
        "=" * width,
    ]
    for li in bill["line_items"]:
        name = li["name"][:20]
        qty_price = f"x{li['qty']} @ Rs{li['price']:.2f}"
        line1 = f"{name}"
        line2 = f"  {qty_price:<24}{'Rs' + format(li['subtotal'], '.2f'):>10}"
        lines.append(line1)
        lines.append(line2)

    lines.append("-" * width)
    lines.append(f"{'Subtotal':<28}{'Rs' + format(bill['subtotal'], '.2f'):>12}")
    lines.append(f"{'GST (' + format(tax_rate, '.0%') + ')':<28}{'Rs' + format(bill['tax'], '.2f'):>12}")
    lines.append("=" * width)
    lines.append(f"{'TOTAL':<28}{'Rs' + format(bill['total'], '.2f'):>12}")
    lines.append("=" * width)
    lines.append("Thank you for shopping!".center(width))

    return "\n".join(lines)


def detection_summary(detections: list[Detection]) -> dict[str, Any]:
    """Summarize a batch of detections for display metrics.

    Args:
        detections: List of (name, confidence, bbox) tuples.

    Returns:
        {
            "total": int,                    # total detections
            "unique_items": int,              # distinct classes seen
            "by_class": dict[str, int],       # count per class
        }
    """
    by_class: dict[str, int] = {}
    for name, _confidence, _bbox in detections:
        by_class[name] = by_class.get(name, 0) + 1

    return {
        "total": len(detections),
        "unique_items": len(by_class),
        "by_class": by_class,
    }


def confidence_stats(detections: list[Detection]) -> dict[str, float]:
    """Compute basic confidence statistics for a batch of detections.

    Args:
        detections: List of (name, confidence, bbox) tuples.

    Returns:
        {"mean": float, "min": float, "max": float}. All zero if empty.
    """
    if not detections:
        return {"mean": 0.0, "min": 0.0, "max": 0.0}

    confidences = [c for _name, c, _bbox in detections]
    return {
        "mean": sum(confidences) / len(confidences),
        "min": min(confidences),
        "max": max(confidences),
    }


def resize_for_display(image: np.ndarray, max_width: int = 700) -> np.ndarray:
    """Downscale an image for display, preserving aspect ratio.

    Args:
        image: RGB or BGR numpy array (H, W, C).
        max_width: Target width in pixels; images narrower than this are
            returned unchanged.

    Returns:
        The resized (or original) image array.
    """
    h, w = image.shape[:2]
    if w <= max_width:
        return image

    scale = max_width / w
    new_size = (max_width, int(h * scale))
    return cv2.resize(image, new_size, interpolation=cv2.INTER_AREA)
