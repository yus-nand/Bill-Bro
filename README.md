# BillBro — Integrated local working copy

This is not a git branch and it's not been pushed anywhere. It's a
locally assembled copy that pulls the current best version of each
file from all three people's branches, so the whole app can actually
be run together from one place while everyone keeps working on their
own branch separately. Treat it as a scratch/testing area, not a
source of truth — `Person-A`, `Person-B`, `Person-C` on GitHub remain
that.

## What came from where

**Backend** (`api_app.py`, `database.py`, `migrate_items_training_columns.py`,
`billbro_mvp.db`, `billbro_database_schema.sql`, `billbro_sample_data.sql`)
— from Person A's worktree, including this session's audit fixes
(checkout body-format bug, inventory query-param bug, duplicate-name
500, missing `status` field, the critical training-upload fix,
`/models/active` fix, and the new Admin endpoints).

**ML pipeline** (`predict.py`, `training.py`, `data.yaml`, `classes.json`,
`ml_utils.py`, `benchmark_inference.py`, `ML_NOTES.md`,
`TRAINING_RESULTS.md`) — from Person B's worktree. `training.py` here
is Person B's newer version — it has a fix Person A's copy didn't
(`ReplayPool.bootstrap_from_base()` raises `FileNotFoundError` loudly
instead of silently producing a permanently broken replay pool).
`predict.py` was identical between the two worktrees, so no
reconciliation was needed there. `ml_utils.py` is Person B's `utils.py`,
renamed here only to avoid confusion with the frontend's own
`utils.js` — the actual file content is untouched.

**`models/`** — `grocery_yolov8.pt` (Person A's base model, confirmed
byte-identical to Person B's `billbro_v3_best.pt` retrain — both are
here, same file, different name, matching what each person's own code
expects to find) and `versions.json` (seeded this session with real
Pepsi-retrain metrics).

**`frontend/`** — Person C's full frontend, `node_modules`/`dist`/`.env`
excluded (regenerate `node_modules` locally with `npm install` before
running).

**`docs/`** — `API_CONTRACT.md` and the three `PROJECT_STATE_FOR_*.md`
summaries written this session.

## Known real gap, not fixed by this integration

`data.yaml` here still points to `path: /content/merged_dataset` — a
Colab-local path from Person B's training environment. The actual base
training images (~180, 30/class) it references were never committed to
any branch. This integration puts the file in the right *location* for
`api_app.py`'s `BASE_DATA_YAML = "data.yaml"` to find it, but doesn't
solve the underlying missing-dataset blocker — that's still a real team
infra decision (repo, Git LFS, cloud bucket), not something a file copy
can fix.

## Running this

`backend-requirements.txt` already anticipated needing Person B's ML
deps (`torch`, `ultralytics`, `opencv-python`, `numpy`, `pandas`,
`pillow` are all in there, just with different version pins than
`ml-requirements.txt` — no hard conflicts found, `pip install -r
backend-requirements.txt` alone should cover both the API and the
detection/training pipeline). `ml-requirements.txt` is kept here for
reference but has one thing worth knowing: it still lists `streamlit`
and `roboflow`, leftovers from Person B's original prototype/dataset-
download workflow — neither is needed to run `api_app.py`, don't
install them unless specifically working on that older prototype.

Frontend needs `cd frontend && npm install`. Point `frontend/.env`'s
`VITE_API_BASE_URL` at wherever the backend actually runs
(`http://localhost:8000` by default).

Not verified end-to-end here — this environment has no network access
to install `fastapi`/`ultralytics`/etc., so this is an assembled,
syntax-checked copy, not a runtime-tested one. Worth doing that real
run once this is on a machine with package-install access.
