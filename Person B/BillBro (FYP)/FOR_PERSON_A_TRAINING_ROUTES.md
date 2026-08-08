# For Person A — `/training/upload_images` + `/training/job/{id}` routes

You said this is next up. Checked your `database.py` against what `training.py` actually produces — found two real mismatches, plus the ready-to-paste routes below (same pattern as `/detect`).

## ⚠️ Fix these in `database.py` first, or the routes below will break

1. **`TrainingJob` has no `metrics` column.** You've got `accuracy: Float` and `total_epochs: Integer`, but `retrain_model()` returns a `metrics` dict — `mAP50`, `mAP50-95`, `precision`, `recall`, `per_class_AP50` (per-item breakdown), `epochs`, `new_item_train_images`. A single float loses most of it (the per-class breakdown especially matters for the Models page later). Add:
   ```python
   metrics = Column(Text)  # JSON — same pattern as your ModelVersion.metrics
   ```
   and drop/ignore `accuracy` + `total_epochs`, or keep them as denormalized convenience fields populated from `metrics["mAP50"]` / `metrics["epochs"]` if you want them queryable.

2. **`current_epoch` is typed `Integer`, but `training.py` writes strings like `"3/5"`** (`_update_job(..., current_epoch=f"0/{epochs}")` and later `"3/5"` etc. — it's progress-through-a-run, not just a number). Change the column to `String(20)`, or if you want a true int, I can change `training.py` to emit `current_epoch` and `total_epochs` as two separate int fields instead — your call, just flag which you want.

3. **`Item` has no `status` column.** The whole shelve gate (`pending → training → shelved`/`failed`) that `BillBroAgain`/`TeamUpdates.md` describes has nowhere to live yet. Needs:
   ```python
   status = Column(String(20), default='pending')  # pending | training | shelved | failed
   ```
   Checkout/detection should only ever query `status == 'shelved'` once this exists.

## Routes — paste into `api_app.py`

Uses `retrain_model()` / `read_job_status()` from `training.py` exactly as they are today (see `RESPONSE_TO_PERSON_A_SYNC.md` — signatures haven't changed since your copy). Runs training in a background thread since `retrain_model()` is a blocking call (5 epochs, ~15 min GPU / ~1 hr CPU) — don't run it in the request handler itself.

```python
import threading
import uuid
from fastapi import UploadFile, File, Form
from training import retrain_model, read_job_status

BASE_DATA_YAML = "data.yaml"  # the 6-class base model's data.yaml, repo root


@app.post("/training/upload_images", tags=["Training"])
def upload_training_images(
    item_id: int,
    item_name: str,
    store_id: str = "store_001",
    images: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """Save staff-captured photos, kick off fine-tuning in the background.

    item_name should already be lowercase/underscored (e.g. "maggi_noodles")
    — training.py uses it directly as the new class label.
    """
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    upload_dir = Path("training_uploads") / f"item_{item_id}"
    upload_dir.mkdir(parents=True, exist_ok=True)
    image_paths = []
    for i, img in enumerate(images):
        dest = upload_dir / f"{item_name}_{i:03d}.jpg"
        with open(dest, "wb") as f:
            f.write(img.file.read())
        image_paths.append(str(dest))

    if len(image_paths) < 5:
        raise HTTPException(status_code=400, detail="Need at least 5 photos")

    job_id = str(uuid.uuid4())

    def run():
        retrain_model(
            store_id=store_id,
            item_name=item_name,
            image_paths=image_paths,
            base_data_yaml=BASE_DATA_YAML,
            job_id=job_id,
            item_id=item_id,
        )
        # Flip item status once the job file settles — poll instead of
        # blocking here so this thread doesn't hang on DB access from
        # outside the request's session scope.
        result = read_job_status(job_id)
        db2 = SessionLocal()
        try:
            it = db2.query(Item).filter(Item.id == item_id).first()
            if it:
                it.status = "shelved" if result.get("status") == "success" else "failed"
                db2.commit()
        finally:
            db2.close()

    item.status = "training"
    db.commit()
    threading.Thread(target=run, daemon=True).start()

    return {"job_id": job_id, "item_id": item_id, "status": "training"}


@app.get("/training/job/{job_id}", tags=["Training"])
def get_training_job(job_id: str):
    """Poll status — matches TrainingJob shape once the metrics/current_epoch
    schema fix above is in."""
    result = read_job_status(job_id)
    if result.get("status") == "unknown":
        raise HTTPException(status_code=404, detail="Job not found")
    return result
```

Notes:
- `read_job_status()` returns the exact `JobStatus` field names you already locked in with Person C (`status, progress, item_id, current_epoch, metrics, error_message, created_at, completed_at`, plus `stage`/`model_version` as harmless extras) — no translation layer needed in the route.
- `BASE_DATA_YAML` only matters on a store's *first ever* training run (bootstraps the replay pool); every run after that ignores it and uses the pool. Point it at the repo's `data.yaml` (6 base classes) and you're done — no per-store config needed.
- Runs are 15 img minimum in this draft (`training.py` itself needs >3, but under 5 usable auto-labels the pipeline already fails with a clear message — 5 is a reasonable floor to check before even starting a job).
