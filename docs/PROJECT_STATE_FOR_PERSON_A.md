# BillBro — Project State for Person A (Backend)

Consolidated snapshot as of 2026-08-09. Replaces the old back-and-forth
RESPONSE_TO_*/FOR_PERSON_C*/SYNC_* docs that used to live in your
worktree — those were cleared out since the code + this doc are now the
source of truth, not a chain of messages. `API_CONTRACT.md` in this same
folder is still the full endpoint-by-endpoint reference; this is the
shorter "what's actually going on right now" version.

## What's confirmed working in your pushed code

- `/detect` — both historical bugs (merge-conflict markers, then the
  wrong model path) are fixed and pushed. Live against Person B's
  retrained model (`billbro_v3_best.pt`).
- `POST /items` — JSON-body bug fixed and pushed.
- `process_checkout()` — the `_normalize_name()` item-matching fix is
  genuinely in your pushed `api_app.py`, confirmed by reading the code
  directly and by simulation against real seeded data.
- `TrainingJob`/`Item` schema — `metrics`, `current_epoch` (String),
  `Item.status` all present in your pushed `database.py`.
- `migrate_items_training_columns.py` — well-designed, backfills
  existing items to `status='shelved'` so they don't vanish from
  checkout the moment status-filtering went live.

## What's sitting in a local worktree, not pushed — your call to review/apply

A full line-by-line audit this session found four additional bugs plus
one critical one, and built out the Admin backend you hadn't started.
All of this lives in a local `Bill-Bro-PersonA` git worktree (not
pushed anywhere — your branch, not something to push without your
review). Syntax-verified, core logic hand-simulated against your real
`billbro_mvp.db`, but never runtime-tested (no FastAPI/uvicorn
available on this side).

1. **`POST /checkout/bill` body-format bug** — `detections: List[dict]`
   as the sole bare body param means FastAPI expects the raw array to
   BE the body, not `{"detections": [...]}`. Fixed with a
   `CheckoutRequest(BaseModel)` wrapper.
2. **`PATCH /inventory/{item_id}` query-param bug** — same root cause
   as the `POST /items` bug: bare scalar args read as query params
   instead of JSON body. Fixed with `AdjustInventoryRequest`.
3. **Duplicate item name → unhandled 500** — `create_item()` only
   pre-checked SKU, not name (also DB-unique). Added a pre-check.
4. **Missing `status` in `Item.to_dict()`** — added.
5. **CRITICAL: training upload was completely non-functional** —
   `item_name` was never sent by the frontend at all, and
   `item_id`/`item_name`/`store_id` were bare scalars in a
   `File(...)`-containing route (FastAPI doesn't auto-promote those to
   form fields). Fixed on both sides: your params now use `Form(...)`,
   frontend now sends `item_name`.
6. **`GET /models/active`** — rewritten to read from
   `StoreModelManager`/`models/versions.json` instead of the dead SQL
   table. `GET /models` + activate/rollback added too.
7. **Admin backend, built from nothing** — new `StoreSettings` table,
   `GET`/`PUT /admin/settings`, `POST /admin/bulk_upload` (CSV
   upsert-by-SKU, per-row error collection). `migrate_items_training_columns.py`
   extended to create the `store_settings` table.

Full request/response shapes for all of the above: see `API_CONTRACT.md`.

## Still genuinely blocked, not a code issue

- **Base training dataset** — `ReplayPool.bootstrap_from_base()` needs
  real base-model training images (~180, 30/class), never committed to
  the shared repo. Needs a team decision on where they live (repo, Git
  LFS, cloud bucket) before Add Item can be tested end-to-end for real.
- **Real end-to-end test** — `/detect` + `/checkout/bill` against a
  live running server hasn't happened from the frontend side yet.
  Waiting on you to review/push the worktree fixes above first.
- `main` merge — intentionally on hold pending a team sync.

## What would help most right now

Review the worktree fixes (especially #5, the training-upload one — that
was completely broken end-to-end) and push what looks right. Once
that's live, the real `/detect` + `/checkout/bill` + Add Item test can
finally happen from Person C's side.
