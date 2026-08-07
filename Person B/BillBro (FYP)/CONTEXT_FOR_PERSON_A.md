# BillBro — ML Context (for Person A's Claude / Person A)

Paste this into your own chat for context on where the ML side stands.
Matches the convention Person C used in their own `CONTEXT_FOR_PERSON_A.md`
— same idea, from Person B this time.

## Model conversion — done

`billbro_v3.onnx` → PyTorch is complete. `models/grocery_yolov8.pt` is the
trained model (6 classes: apple, banana, dragonfruit, custard_apple,
diet_coke, pepsi). If your `/detect` endpoint is currently pointed at a
placeholder or an older model, swap in this file — should be a drop-in
`YOLO(path)` load, same interface either way.

## `POST /detect` — a ready-to-use implementation, in case it helps

Per `API_CONTRACT.md`, your `/detect` is already live and matches the
contract, so this may be redundant with what you've already built. But
`predict.py` (this folder) now has `GroceryDetector.detect_from_base64()`
that implements the exact contract end-to-end:

```python
detector = GroceryDetector("models/grocery_yolov8.pt")

# body.image = "<base64, no data-URL prefix>" (matches frontend/src/api.js)
result = detector.detect_from_base64(body.image, body.confidence_threshold or 0.5)
# -> {"detections": [{"item_name", "confidence", "bbox": [x1,y1,x2,y2]}, ...],
#     "processing_time_ms": int}
```

Tested against a mocked model (this sandbox has no `torch`/network access
to install `ultralytics` for a full runtime test — verify locally). Raises
`ValueError` on bad base64/image input, which you'll want to catch and
turn into a 400.

## Training endpoints — `training.py` is ready, now aligned to your `TrainingJob` table

Saw `BillBro_TeamUpdates.md` — Add Item → Train → Shelve is the core loop
now, and I've updated `training.py` accordingly. `retrain_model()` runs
auto-labeling → fine-tuning → validation → conditional shelve, and (if you
pass a `job_id`) mirrors progress to `models/jobs/{job_id}.json` as it
goes. `read_job_status(job_id)` reads that file back — you could call it
directly from `GET /training/job/{job_id}` without sharing process memory
with wherever `retrain_model()` actually runs (thread, process, whatever
you pick).

`JobStatus` now mirrors your `TrainingJob` columns 1:1:

| Your table | My `JobStatus` | Notes |
|---|---|---|
| `id` | `job_id` | pass whatever id you generate as `job_id=` |
| `item_id` | `item_id` | pass through from `POST /items` |
| `status` | `status` | `pending \| running \| success \| failed` |
| `progress` | `progress` | int 0-100 |
| `current_epoch` | `current_epoch` | e.g. `"2/5"` |
| `metrics` | `metrics` | JSON — `mAP50`, `mAP50-95`, `precision`, `recall`, `per_class_AP50` |
| `error_message` | `error_message` | set on failure |
| `created_at` | `created_at` | set once, on first write |
| `completed_at` | `completed_at` | set on success/failure |

Two extra fields beyond your table (`stage`, `model_version`) — ignore if
you don't need them, they're just nice-to-haves for a progress UI.

`retrain_model()` now also takes `item_id=` so it flows straight into the
job file — call it like:

```python
retrain_model(
    store_id=store_id, item_name=item_name, image_paths=image_paths,
    base_data_yaml="data.yaml", job_id=job_id, item_id=item.id,
)
```

## Resolved: the three coupling points from `BillBro_TeamUpdates.md`

1. **`GET /training/job/{job_id}` shape** — see table above, locked to
   your `TrainingJob` columns.

2. **Cumulative fine-tuning vs. fresh-from-base each time** — going with
   **cumulative**: every retrain starts from the store's current active
   model (`StoreModelManager.active_model_path(store_id)`), not
   `base_model.pt`. Reasoning: fresh-from-base would mean retraining on
   *every* item ever shelved, every single time — that stops fitting the
   15-min latency target after a handful of items. Catastrophic
   forgetting is instead handled by a new `ReplayPool` (in `training.py`):
   every successfully shelved item contributes a small image sample
   (~15 images) to a persistent per-store pool, and every future retrain
   replays a sample from *every* previously shelved class, not just the
   original 6. This is the "Replay strategy" your doc flagged as
   recommended for MVP — it's implemented now, tested with a 3-item
   simulation (base classes → item 1 → item 2, confirming item 1 gets
   replayed correctly when item 2 trains).

3. **Automatic vs. manual shelving** — recommending **automatic**:
   `retrain_model()` already only returns `"status": "success"` if mAP50
   clears the threshold; treat that as the shelve signal directly
   (`status="shelved"`), no separate staff-confirm step needed on the ML
   side. Open to a manual review step in the UI on top of this if the team
   wants a human in the loop, but the accuracy gate itself doesn't need one.

4. **Accuracy threshold** — confirming **0.80 mAP50** as the shelve gate
   (`DEFAULT_ACCURACY_THRESHOLD` in `training.py`), matching what the
   original context doc mentioned.

## ⚠️ One thing that affects Checkout accuracy directly

`pepsi` currently has **0.000 AP** — not a training bug, a dataset gap
(the source dataset only had a generic `soda-can` class, so no pepsi
images ever made it into training; full root-cause writeup in
`ML_NOTES.md`). Detection will silently fail on real Pepsi cans at
checkout until this is fixed with real data. Not blocking your endpoint
working — just flagging since you'll see it in the pilot if not sooner.

## How to respond

Same as the rest of the team — tell me directly, update this doc, or drop
a note in the group chat.
