

import json
import random
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageEnhance


# ─── Price Database ────────────────────────────────────────────────────────────

def load_prices(path: str = "prices.json") -> dict[str, float]:
    """Load item → price mapping from a JSON file."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"prices.json not found at '{path}'. "
            "Create one or copy the template from the repo."
        )
    with open(p) as f:
        data = json.load(f)

    prices = {}
    for k, v in data.items():
        try:
            prices[k.lower().replace(" ", "_")] = float(v)
        except (ValueError, TypeError):
            pass   # skip comment/description string entries
    return prices


def get_price(item_name: str, prices: dict, fallback: float = 0.0) -> float:
    """Return the price for an item, with an optional fallback."""
    key = item_name.lower().replace(" ", "_")
    return prices.get(key, fallback)


def save_prices(prices: dict, path: str = "prices.json") -> None:
    """Persist the price dictionary back to JSON."""
    with open(path, "w") as f:
        json.dump(prices, f, indent=2)


# ─── Cart Operations ───────────────────────────────────────────────────────────

def build_cart(detections: list[tuple]) -> dict[str, int]:
    """
    Aggregate detections into a cart (item → count).

    Args:
        detections: list of (class_name, confidence, xyxy)
    Returns:
        dict  {'apple': 2, 'banana': 1, ...}
    """
    cart: dict[str, int] = defaultdict(int)
    for item_name, _conf, _box in detections:
        cart[item_name] += 1
    return dict(cart)


def merge_carts(existing: dict, new_items: dict) -> dict:
    """Merge two carts, summing quantities."""
    merged = dict(existing)
    for item, count in new_items.items():
        merged[item] = merged.get(item, 0) + count
    return merged


def remove_item(cart: dict, item: str, quantity: int = 1) -> dict:
    """Remove one (or more) units of an item from the cart."""
    cart = dict(cart)
    if item in cart:
        cart[item] = max(0, cart[item] - quantity)
        if cart[item] == 0:
            del cart[item]
    return cart


def calculate_total(
    cart: dict[str, int],
    prices: dict[str, float],
    tax_rate: float = 0.0,
) -> dict:
    """
    Calculate subtotals, tax, and grand total.

    Returns:
        {
            'line_items': [{'name', 'qty', 'unit_price', 'subtotal'}, ...],
            'subtotal':   float,
            'tax':        float,
            'total':      float,
        }
    """
    line_items = []
    subtotal = 0.0

    for item, qty in sorted(cart.items()):
        unit_price = get_price(item, prices)
        sub = unit_price * qty
        subtotal += sub
        line_items.append({
            "name":       item.replace("_", " ").title(),
            "qty":        qty,
            "unit_price": unit_price,
            "subtotal":   sub,
        })

    tax   = subtotal * tax_rate
    total = subtotal + tax

    return {
        "line_items": line_items,
        "subtotal":   round(subtotal, 2),
        "tax":        round(tax, 2),
        "total":      round(total, 2),
    }


# ─── Receipt Formatting ────────────────────────────────────────────────────────

STORE_NAME    = "Smart Mart"
STORE_ADDRESS = "123 Vision Street, Mumbai"
STORE_PHONE   = "+91 98765 43210"


def format_receipt(
    cart: dict[str, int],
    prices: dict[str, float],
    tax_rate: float = 0.05,
    width: int = 40,
) -> str:
    """
    Generate a plain-text receipt string.

    Args:
        cart     : {'apple': 2, ...}
        prices   : price lookup dict
        tax_rate : e.g. 0.05 = 5 % GST
        width    : character width of the receipt
    """
    sep  = "─" * width
    dsep = "═" * width
    now  = datetime.now().strftime("%d %b %Y  %H:%M")

    lines = [
        dsep,
        STORE_NAME.center(width),
        STORE_ADDRESS.center(width),
        STORE_PHONE.center(width),
        dsep,
        f"Date: {now}".center(width),
        f"Receipt #: {_receipt_number()}".center(width),
        sep,
        f"{'ITEM':<22}{'QTY':>4}{'PRICE':>7}{'AMT':>7}",
        sep,
    ]

    bill = calculate_total(cart, prices, tax_rate)

    for li in bill["line_items"]:
        name = li["name"][:20]
        lines.append(
            f"{name:<22}{li['qty']:>4}{li['unit_price']:>7.2f}{li['subtotal']:>7.2f}"
        )
        if li["unit_price"] == 0.0:
            lines.append("  * Price not found - assumed Rs.0.00")

    subtotal_str = "Rs." + f"{bill['subtotal']:.2f}"
    tax_str      = "Rs." + f"{bill['tax']:.2f}"
    total_str    = "Rs." + f"{bill['total']:.2f}"
    tax_label    = f"GST ({tax_rate:.0%})"

    lines += [
        sep,
        f"{'Subtotal':<28}{subtotal_str:>12}",
        f"{tax_label:<28}{tax_str:>12}",
        dsep,
        f"{'TOTAL':<28}{total_str:>12}",
        dsep,
        "",
        "Thank you for shopping at Smart Mart!".center(width),
        "Powered by YOLOv8 Computer Vision".center(width),
        dsep,
    ]

    return "\n".join(lines)


def _receipt_number() -> str:
    return f"RC{random.randint(100000, 999999)}"


# ─── Image Preprocessing ──────────────────────────────────────────────────────

def preprocess_image(
    image: np.ndarray,
    target_size: tuple[int, int] = (640, 640),
    enhance: bool = True,
) -> np.ndarray:
    """
    Resize + optionally enhance brightness/contrast before inference.
    Returns an RGB numpy array.
    """
    pil_img = Image.fromarray(image)

    if enhance:
        pil_img = ImageEnhance.Contrast(pil_img).enhance(1.2)
        pil_img = ImageEnhance.Sharpness(pil_img).enhance(1.1)

    pil_img = pil_img.resize(target_size, Image.LANCZOS)
    return np.array(pil_img)


def resize_for_display(image: np.ndarray, max_width: int = 800) -> np.ndarray:
    """Scale image down if wider than max_width, preserving aspect ratio."""
    h, w = image.shape[:2]
    if w <= max_width:
        return image
    scale  = max_width / w
    new_wh = (int(w * scale), int(h * scale))
    return cv2.resize(image, new_wh, interpolation=cv2.INTER_AREA)


def load_image_from_path(path: str) -> np.ndarray:
    """Load an image from disk and return as RGB numpy array."""
    img = cv2.imread(path)
    if img is None:
        raise FileNotFoundError(f"Cannot load image at '{path}'")
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


# ─── Stats & Analytics ────────────────────────────────────────────────────────

def detection_summary(detections: list[tuple]) -> dict:
    """
    Summarise a list of detections.

    Returns:
        {'total': int, 'unique_items': int, 'by_class': {'apple': 2, ...}}
    """
    counts: dict[str, int] = defaultdict(int)
    for name, _, _ in detections:
        counts[name] += 1
    return {
        "total":        len(detections),
        "unique_items": len(counts),
        "by_class":     dict(counts),
    }


def confidence_stats(detections: list[tuple]) -> dict:
    """Return mean, min, max confidence across all detections."""
    if not detections:
        return {"mean": 0.0, "min": 0.0, "max": 0.0}
    confs = [c for _, c, _ in detections]
    return {
        "mean": round(sum(confs) / len(confs), 3),
        "min":  round(min(confs), 3),
        "max":  round(max(confs), 3),
    }
