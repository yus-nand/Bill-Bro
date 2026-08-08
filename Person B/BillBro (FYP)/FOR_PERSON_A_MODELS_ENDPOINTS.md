# For Person A — Models endpoints (`GET /models/active`, `GET /models`, activate/rollback)

## Correction on the frontend stack first

Looked through Person C's folder. It's **not Flask** — it's a React +
Vite single-page app (`frontend/`, axios client in `frontend/src/api.js`,
built with `npm run build`, served as static files, presumably behind
nginx per `frontend/nginx.conf`). Talks to your FastAPI backend over
plain REST at `:8000`. `app.py` / `pages/*.py` / `config.py` at the repo
root are the *old*, explicitly-deprecated Streamlit skeleton — kept for
reference only, not run. So there's no Flask anywhere in this project;
if that's what you'd heard, it's a mix-up somewhere upstream.

## The real gap: `GET /models/active` will 404 forever as currently wired

Checked `database.py`'s `ModelVersion` table against `predict.py`'s
`StoreModelManager`. Your `get_active_model()` route queries the SQL
`ModelVersion` table — but nothing ever writes a row into it.
`StoreModelManager.register_version()` (called at the end of every
successful `retrain_model()` run) writes to its own file,
`models/versions.json`, by design — `training.py`'s docstring says so
explicitly: *"so the API layer and training pipeline agree on which
model is currently deployed... without needing a database dependency in
the ML code."* Two parallel, unsynced sources of truth. Right now your
`/models/active` route will return 404 no matter how many models get
trained, because the DB table stays empty forever.

Person C already flagged this as an open question in `API_CONTRACT.md`
("worth confirming whether `GET /models` returns the same v1/v2 string
scheme or wraps it in numeric ids") — so this isn't a surprise fix,
just confirming the answer: **read from `StoreModelManager`, not the SQL
table.** Simplest fix, two options:

**Option A (recommended) — drop the SQL `ModelVersion` table, read the JSON directly:**

```python
from predict import StoreModelManager

@app.get("/models/active", tags=["Models"])
def get_active_model(store_id: str = "store_001"):
    manager = StoreModelManager(models_dir="models")
    history = manager.list_versions(store_id)
    active = next((v for v in reversed(history) if v["is_active"]), None)
    if not active:
        raise HTTPException(status_code=404, detail="No active model found")
    return active


@app.get("/models", tags=["Models"])
def list_models(store_id: str = "store_001"):
    """Version history, newest last — matches API_CONTRACT.md's Week 8 note."""
    manager = StoreModelManager(models_dir="models")
    return manager.list_versions(store_id)


@app.post("/models/{version}/activate", tags=["Models"])
@app.post("/models/{version}/rollback", tags=["Models"])
def activate_model(version: str, store_id: str = "store_001"):
    """Same operation either way — StoreModelManager doesn't distinguish
    'activate an older version' from 'roll back to it', both just point
    {store_id}_latest.pt at the chosen version."""
    manager = StoreModelManager(models_dir="models")
    try:
        manager.rollback(store_id, version)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "success", "store_id": store_id, "active_version": version}
```

Note `version` is a **string like `"v1"`/`"v2"`, not a numeric id** —
confirms Person C's open question. The frontend's `activateModel(versionId)` /
`rollbackModel(versionId)` proposals in `api.js` should pass that string
straight through in the URL, nothing to convert.

**Option B** — keep the SQL table and have `register_version()` write to
it too, but that means threading a DB session into `training.py`, which
was deliberately avoided so the ML code has zero database dependency
(training can run standalone/offline). Option A is less work and matches
the original design intent — only switch to B if there's a reason the
Models page specifically needs SQL-side joins (e.g. against `Item`).

## Quick contract check — everything else

Cross-referenced `frontend/src/api.js`'s CONFIRMED section against what's
actually live:
- `/detect`, `/checkout/bill`, `/items`, `/inventory`, `/alerts` — all
  match what's already shipped, nothing new here.
- `/training/upload_images` + `/training/job/{id}` — covered in
  `FOR_PERSON_A_TRAINING_ROUTES.md` (sent separately, still pending on
  your end along with the `TrainingJob.metrics`/`current_epoch`/`Item.status`
  schema fixes flagged there).
- `/admin/*`, `/prices` — nothing on Person B's side feeds these, no
  action needed from ML.
