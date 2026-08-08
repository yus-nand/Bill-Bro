# Critical: `/checkout/bill` never matches any detected item

Found this while starting on Add Item/Inventory/Alerts — it's the actual
root blocker for testing any of the three, so flagging it first.

## The bug

`process_checkout()` matches detections to items with:
```python
Item.name.ilike(item_name)
```

But these two never have the same shape:
- `Item.name` in the DB is human-entered Title Case with spaces:
  `"Diet Coke"`, `"Dragon Fruit"`, `"Custard Apple"` (see
  `billbro_sample_data.sql`).
- `item_name` from a detection is the model's raw class name:
  `"diet_coke"`, `"dragonfruit"`, `"custard_apple"` (see `classes.json`).

`ilike` is case-insensitive but not separator-insensitive —
`"diet_coke"` and `"Diet Coke"` are different strings (underscore vs
space), so the query never matches. **Every single checkout silently
drops every detected item** — `if not item: continue` swallows it with
no error. Net effect: every checkout returns an empty cart, ₹0 total,
zero inventory decrements, zero alerts triggered, no matter what's in
the photo. This has been true since `process_checkout()` was written —
worth checking whether any prior "Checkout works" testing was actually
verified end-to-end against real item rows, or just checked that the
endpoint responds.

## Why a simple `.replace(' ', '_')` won't fully fix it either

Five of six class names are exactly `name.lower().replace(' ', '_')` of
their Title Case counterpart (`diet_coke`, `custard_apple`, etc.) — but
`dragonfruit` is a single joined word with **no** separator, while its
`Item.name` is `"Dragon Fruit"` (two words). A space→underscore swap
still leaves `"dragon_fruit"` ≠ `"dragonfruit"`. This came from how the
Roboflow dataset happened to be labeled, not a typo — so the matching
logic needs to be robust to "no separator at all," not just "underscore
vs space."

## Fix — strip all non-alphanumerics on both sides before comparing

```python
import re

def _normalize_name(s: str) -> str:
    """'Dragon Fruit', 'dragon_fruit', and 'dragonfruit' all normalize to
    the same string — handles both the underscore/space mismatch and the
    no-separator case (dragonfruit) in one pass, since neither Item.name
    nor the model's class names follow one consistent convention."""
    return re.sub(r"[^a-z0-9]", "", s.lower())
```

In `process_checkout()`, replace the `ilike` filter:
```python
# Was:
#   item = db.query(Item).filter(
#       Item.store_id == store_id, Item.name.ilike(item_name)
#   ).first()

candidates = db.query(Item).filter(Item.store_id == store_id).all()
item = next(
    (c for c in candidates if _normalize_name(c.name) == _normalize_name(item_name)),
    None,
)
```

Fetching all of a store's items and comparing in Python is fine at this
scale (a handful to a few dozen items per store) — no need for SQL-side
string manipulation.

Verified this normalization actually reconciles all 6 current classes
against their DB names: apple/banana/pepsi match trivially,
`custard_apple`↔"Custard Apple" and `diet_coke`↔"Diet Coke" both
normalize to the same string, and `dragonfruit`↔"Dragon Fruit" also
matches once spaces are stripped rather than swapped for underscores.
Future items added via Add Item should be fine either way, since
`training.py`'s `item_name` and whatever gets typed into `POST /items`
are both under staff's control at creation time — just flagging this
fix should stay in place rather than being removed once it "seems" to
work for the current 6.

## Where else to check

Any other place that matches an ML-provided name string against
`Item.name` should use the same `_normalize_name()` helper. Places keyed
by `item_id` (Inventory, Alerts) aren't affected — this only bites where
a raw detection name gets compared against the DB.
