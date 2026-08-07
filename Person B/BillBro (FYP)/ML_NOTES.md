# ML Notes — Person B

## Update — build order flipped (per `BillBro_TeamUpdates.md`)

Team decided "Add Item → Train → Shelve" is now the first feature, ahead
of checkout/billing. Items go `pending → training → shelved` (or
`failed`), and only `shelved` items are detectable at checkout. This
session's work responds to that:

- **`ReplayPool`** (new, in `training.py`) — replaces the old "replay from
  the original 6 base classes only" logic. Now persistent per-store: every
  time an item is successfully shelved, a sample of its own images joins
  the pool, so every future retrain protects *all* previously shelved
  items, not just the launch classes. Tested with a 3-generation
  simulation (base → item 1 → item 2), confirming item 1 gets correctly
  replayed (and remapped to its class id) when item 2 trains.
- **`JobStatus`** fields renamed to match Person A's new `TrainingJob`
  table exactly (`item_id`, `current_epoch`, `error_message`,
  `created_at`, `completed_at`) — see `CONTEXT_FOR_PERSON_A.md` for the
  full mapping table.
- Three open decisions from the team doc answered and documented in
  `CONTEXT_FOR_PERSON_A.md`: cumulative fine-tuning (yes, from the
  store's current model, not fresh-from-base), automatic shelving (yes,
  the mAP50 gate already implemented is the shelve signal), and the 0.80
  mAP50 threshold (confirmed as-is).
- `barcode` / `batch_number` are new `Item` fields — Person A's schema,
  no ML-side action needed.

---

# Original notes (Week 1-2)

## What was broken

`predict.py` and `utils.py` were missing from disk — only stale `.pyc`
cache remained, meaning `app.py` could not run at all (`ImportError` on
`from predict import GroceryDetector`). Both have been rebuilt to match
the interface `app.py` already expects. No changes were made to `app.py`.

## Critical finding: pepsi has 0.000 AP — root cause identified

`BillBroAgain.ipynb` cell 10's validation output shows:

```
✅ diet_coke   AP=0.885
⚠️  pepsi       AP=0.000
```

This is **not a training bug** — it's a dataset gap. In cell 3, the `soda`
dataset (`cyberwarriorstemcamp/soda-can-qr4c4`) downloaded with **only one
raw class**: `nc=1, names=['soda-can']`. `MANUAL_NAME_MAP` in cell 6 maps
`{0: "diet_coke", 1: "pepsi"}`, but index `1` never existed in this
dataset — every soda-can annotation collapsed into `diet_coke`. The merge
step (cell 8) confirms it: `soda: 119 imgs, 163 annots` all went to
`diet_coke`. **Zero pepsi images ever entered training.** `billbro_v3.onnx`
/ `models/grocery_yolov8.pt` cannot detect pepsi no matter how it's
retrained without new data — the class is currently undetectable at
checkout.

**Fix needed before pilot:** source a dataset (or capture your own ~50-100
images) that actually contains Pepsi cans as a distinct class, then rerun
the merge + train cells with a corrected `MANUAL_NAME_MAP`.

## Secondary finding: `prices.json` was missing 3 of 6 model classes

`dragonfruit`, `custard_apple`, and `pepsi` had no price entry, so any
correct detection of those items would checkout at ₹0.00. Patched with
placeholder prices (₹180, ₹90, ₹40) — confirm with the team before pilot.

## New files

- **`predict.py`** — `GroceryDetector` (inference, matches old interface)
  + `StoreModelManager` (per-store model resolution, versioning,
  rollback — implements `models/{store_id}_v{N}.pt` / `_latest.pt`
  convention from the project spec).
- **`utils.py`** — cart/pricing/receipt helpers, rebuilt from `app.py`'s
  usage since no reference source existed.
- **`training.py`** — the "Add New Item" pipeline:
  - `auto_label_images()` — bootstraps bounding boxes for a new item's
    photos using class-agnostic detection (the model's box regressor,
    not its class head, since it's never seen the item).
  - `prepare_finetune_dataset()` — combines the new item with a replay
    sample of existing classes to reduce catastrophic forgetting.
  - `retrain_model()` — fine-tunes (backbone frozen, 5 epochs default),
    validates, and auto-deploys via `StoreModelManager` only if mAP50
    clears 0.80 — otherwise returns a "capture more images" reason.
  - Job status is mirrored to `models/jobs/{job_id}.json` so Person A's
    API layer can poll `GET /training/job/{job_id}` without needing to
    share process memory with a background thread.

All three files pass `py_compile`. `utils.py` and the non-YOLO logic in
`predict.py`/`training.py` (versioning, dataset assembly, class
remapping) were unit-tested in this session. **`GroceryDetector.detect()`
and `retrain_model()`'s actual YOLO training call are not yet
runtime-tested** — this sandbox has no `torch`/`ultralytics` install
(no network access). Run locally with your venv (note: `venv/` in this
repo is Mac-specific and won't work as-is in a fresh clone/CI — it's
symlinked to an absolute path) before merging:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Not yet done (next up)

- Verify `models/grocery_yolov8.pt` is actually the `billbro_v3` run's
  `best.pt` (file exists, untested in this session — no torch available).
- Fix the pepsi dataset gap and retrain.
- Model card (`Week 12` deliverable, per team brief) — not started.
- Inference speed benchmarking (<100ms target) — not started.
