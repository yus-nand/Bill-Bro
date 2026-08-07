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

## Training endpoints — `training.py` is ready when you want to wire it up

`API_CONTRACT.md` lists `POST /training/upload_images` and
`GET /training/job/{job_id}` as not built yet (Weeks 2-3). `training.py`
in this folder has the pipeline those endpoints would call into:

- `retrain_model(store_id, item_name, image_paths, base_data_yaml, ..., job_id=...)`
  — runs auto-labeling → fine-tuning → validation → conditional deploy,
  and (if you pass a `job_id`) mirrors progress to
  `models/jobs/{job_id}.json` as it goes.
- `read_job_status(job_id)` — reads that file back. You could call this
  directly from `GET /training/job/{job_id}` without needing to share
  process memory with wherever `retrain_model()` is actually running
  (background thread, separate process, whatever you pick).

No fixed contract exists yet for this endpoint's response shape (unlike
`/detect`, which API_CONTRACT.md nailed down) — happy to adjust field
names in `JobStatus` to match whatever you land on, just flag it.

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
