# BillBro — Project State for Person B (ML)

Consolidated snapshot as of 2026-08-09. Replaces the old FOR_PERSON_A_*/
RESPONSE_TO_PERSON_A_* handoff docs that used to live in your worktree —
those were cleared out since your fixes are confirmed landed and the
code + this doc are now the source of truth.

## Your fixes — confirmed applied on Person A's side

- **Checkout item-matching bug** — your suggested `_normalize_name()`
  fix (strip all non-alphanumerics before comparing "Diet Coke" against
  "diet_coke", "Dragon Fruit" against "dragonfruit") is genuinely
  implemented in Person A's pushed `api_app.py`. Confirmed by reading
  the real code, and separately re-verified by simulating the exact
  matching logic against a freshly-seeded real database.
- **`TrainingJob`/`Item` schema gaps you flagged** — `metrics` column,
  `current_epoch` as `String(20)`, `Item.status` — all present in
  Person A's pushed `database.py`.
- **`GET /models/active` fix** — your `FOR_PERSON_A_MODELS_ENDPOINTS.md`
  writeup (reading from `StoreModelManager`/`models/versions.json`
  instead of the dead SQL table) has been applied directly in a local
  Person A worktree this session — not pushed yet, but the code matches
  your spec exactly, including the `GET /models` + activate/rollback
  routes you outlined.

## Pepsi retrain — confirmed via your real training log

AP50 0.000 → **0.885**, precision 0.944, recall 0.780 (`billbro_v3_best.pt`,
YOLOv8m, 5,435 images including your 202-image real Pepsi set). This is
live in the frontend's Checkout warning copy (softened per your
recommendation, not removed — 0.780 recall still means real misses) and
seeded into `models/versions.json` with the full per-class breakdown so
the fixed `/models/active` route has real data to return.

Your separately-noted Pepsi/Diet Coke confusion (both cylindrical,
smallest val sets) is documented as an accepted proof-of-concept
limitation, not being re-opened right now.

## Still open on your end

- **Base training dataset for `ReplayPool.bootstrap_from_base()`** — this
  is the one real remaining blocker for Add Item end-to-end testing.
  `data.yaml` alone isn't enough; the ~180 base-model images/labels it
  points to were never committed to the shared repo. Your fail-fast fix
  (`FileNotFoundError` instead of a silent empty replay pool) is good
  and confirmed in place — but the actual unblock needs a team decision
  on where a representative sample should live (repo, Git LFS, cloud
  bucket).
- Manual vs. automatic shelving on training success — still an open
  question between you and Person A, not yet resolved.

## What's new since your last sync

Person A's worktree got a full backend audit this session (Person C
pulled the branch directly and read every route). Four bugs unrelated
to your ML pipeline were found and fixed (checkout body-format,
inventory query-param, duplicate-name 500, missing status field), plus
the training-upload endpoint was found to be completely broken
(frontend never sent `item_name`, and your training route's form fields
were being read as query params server-side) — both sides fixed. None
of this changes anything in `training.py`/`predict.py` on your end;
purely an `api_app.py` + frontend issue. Full detail in
`PROJECT_STATE_FOR_PERSON_A.md` and `API_CONTRACT.md` in this folder.
