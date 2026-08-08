# BillBro — Frontend Context (for project knowledge)

Drop this file into the shared project's knowledge/context so anyone
(teammates or Claude, in any chat on this project) has the current state
of the frontend without re-explaining it. Keep it updated as things change
— this is a snapshot, not a changelog.

## 🔧 Backend audit session — 4 real bugs found, Admin built, all in Person A's worktree

Pulled `Person-A` into a local worktree and read every route directly
rather than trusting docs. Found and fixed four previously-unknown bugs
(`POST /checkout/bill`'s body-format, `PATCH /inventory/{id}`'s
query-param bug, an unhandled 500 on duplicate item names, a missing
`status` field), plus one **critical** one: training upload was
completely non-functional — `item_name` was never sent by the frontend
at all, and the multipart form fields were being misread as query
params server-side. Fixed on both sides (backend `Form(...)`
annotations, frontend now sends `item_name` via a new `toClassName()`
slugify helper in `AddItem.jsx`). Also **built out the entire Admin
backend** (`GET`/`PUT /admin/settings`, `POST /admin/bulk_upload`) that
was previously just a speculative shape in `api.js`, and applied the
`GET /models/active` fix that was previously just written-but-not-applied.
Full detail in `API_CONTRACT.md`. None of this is pushed anywhere — it's
sitting in a local `Bill-Bro-PersonA` worktree, ready for Person A to
review and push when he's back on it.

## ✅ `/checkout/bill`'s critical matching bug: confirmed fixed for real

`process_checkout()` used to match detections to DB items with
`Item.name.ilike(item_name)`, which never actually matched ("Diet Coke"
vs "diet_coke", "Dragon Fruit" vs "dragonfruit" with no separator at
all) — every checkout silently returned an empty cart. Person B found
and wrote up the fix; **pulled Person A's branch directly and confirmed
it's genuinely implemented in the pushed `api_app.py`**, not just
claimed. Nothing wrong in `Checkout.jsx` at any point.

**New caveat that shipped alongside the fix:** checkout now also filters
on `item.status == "shelved"` — items have to be shelved to ring up.
This depends on `migrate_items_training_columns.py` having been run
against the live DB (it backfills existing items to `shelved` so they
don't vanish). Worth confirming before assuming a real test will work.
Full detail in `API_CONTRACT.md`.

## Team

- **Person A** — Backend API (FastAPI + SQLite, real and running)
- **Person B** — ML model (grocery detection). Delivered: base YOLOv8
  model trained on 6 items (Apple, Banana, Dragon Fruit, Custard Apple,
  Diet Coke, Pepsi), `GroceryDetector.detect_from_base64()` (what
  `POST /detect` wraps — shape matches the contract exactly, no
  surprises), plus the full training pipeline
  (`auto_label_images`, `retrain_model`, job status tracking,
  `StoreModelManager` for versioning) ready for Person A to wire up in
  Weeks 2-4/8.
- **Person C** — Frontend/UI (owns this file)

## Key decision: frontend is React, not Streamlit

The original plan was a Streamlit app (`app.py`, `pages/*.py`, `utils.py`).
That's been converted to a React + Vite single-page app, deployed as static
files behind nginx. Doesn't change anything for Person A or Person B.

**Where things live:**
- `App/` — original Python/Streamlit files (unused now, kept for reference)
- `App/frontend/` — the real frontend (React/Vite)
- `App/API_CONTRACT.md` — endpoint-by-endpoint contract, source of truth
- `App/FOR_PERSON_C.md`, `RESPONSE_TO_PERSON_C_FINAL.md`,
  `FINAL_STATUS_WEEK_1.md` — Person A's handoff docs
- `BillBro_TeamUpdates.md` (project knowledge) — the build-order reversal
  described below; append to it as more decisions get made

## ⚠️ Build order reversed: Add Item is now the priority feature

Per `BillBro_TeamUpdates.md`, the team dropped the original Week 1→12
phase order. **"Add Item → Train → Shelve" is the first core feature now,
ahead of checkout/billing.** Checkout was already built before this came
to light and stays live — that work wasn't wasted — but Add Item has now
been built out too, ahead of Person A's backend endpoints existing, so
it's ready the moment he ships them.

🚩 **Misalignment, confirmed harmless:** a later doc from Person A
(`FOR_PERSON_C_CHECKOUT_INTEGRATION.md`) frames Checkout as Week 1 and
Add Item as "Week 2 Preview" — the *original* order, not the reversed
one. Per `SYNC_FOR_PERSON_C.md`, Person A confirms this is just a doc
sync issue, no strong opinion either way — both pages are built
regardless. Full detail in `API_CONTRACT.md`.

New schema implications: items have a status lifecycle
(`pending → training → shelved`, or `failed`) — an item is only
checkout-detectable once `shelved`. This is a new constraint; item
creation and checkout-availability used to be the same event.

Note: `barcode` was dropped by frontend decision (loose produce has no
real scannable barcode, no scanner integration exists) and confirmed
still absent from Person A's schema. `batch_number` had a back-and-forth:
briefly confirmed gone, then found to be real again (plus a new
`batch_arrival_date`) — but scoped to the new restock flow, not Add
Item. See "Restock" below. Full reasoning in `API_CONTRACT.md`.

## New: Restock flow (Inventory page)

Found directly in Person A's pushed `api_app.py` — a
`PATCH /items/{id}/restock` endpoint he built but hadn't documented yet.
Covers "a new batch of an existing item arrived" (quantity + optional
batch number/arrival date), separate from item creation since SKUs are
unique. Built on the Inventory page: a "Restock" button per row opens an
inline form. Full shape in `API_CONTRACT.md`.

## Backend status: 4 of 6 pages genuinely live, endpoints all exist now

- API at `http://localhost:8000`, docs at `/docs`
- **Live and integrated:** Checkout (photo → `/detect` → editable cart →
  `/checkout/bill` → receipt), Inventory (`/inventory` + new Restock
  action), Alerts (`/alerts`, resolve action), Add Item (details → photo
  capture → training → shelved/failed) — all endpoints exist and are
  wired up
- **Spec-complete and now confirmed bug-free in the real code, but still
  not run end-to-end from this side:** Checkout (`/detect`'s two bugs and
  `/checkout/bill`'s matching bug are all confirmed fixed by reading
  Person A's actual pushed code) and Add Item (endpoints live and their
  DB schema mismatches confirmed fixed, but still blocked on a real
  base-dataset infra decision, not just a missing file)
- **Confirmed, not wired up yet:** `PATCH /inventory/{id}` (manual adjust
  UI not built, and had its own query-param bug just fixed), `GET
  /models/active` (fixed this session, worktree-only), `GET /health`
- **Endpoints now exist (built this session, in Person A's worktree, not
  pushed) but no frontend UI built yet:** Admin (`GET`/`PUT
  /admin/settings`, `POST /admin/bulk_upload`), fuller Models page
  (`GET /models`, activate, rollback) — `Admin.jsx` is still a roadmap
  placeholder, needs to actually be wired up now that there's something
  real to call

## Detection flow (Option A, shape confirmed — but see caveat below)

Person A's API owns `POST /detect`: frontend sends a base64 image, gets
back raw per-instance detections `{item_name, confidence, bbox}`. The
frontend aggregates those into `{item_name, confidence, quantity}`
(`utils.js` → `aggregateDetections()`, averages confidence per item) before
calling `POST /checkout/bill`. The backend response is the source of truth
for the receipt — the frontend doesn't recompute totals locally, it just
renders what `/checkout/bill` returns.

**Real measured latency** (per Person A, supersedes the earlier "~2 min
on CPU" worst case): ~2-3s cold start, ~100-200ms after. `detectImage()`'s
timeout is 30s, and Checkout's "still detecting" message now only kicks
in after 5s with copy about the first-request model load, not a
multi-minute wait.

✅ **Resolved, twice over:** first, the gap between "/detect is LIVE" and
Person A's own admission of an unresolved numpy/torch issue + unpushed
code (real cause: a `git stash pop` merge conflict left
uncommitted-resolved in `api_app.py`). Then, a second, separate bug found
while preparing for the real test: the model path was hardcoded to
`models/grocery_yolov8.pt` but the file had been committed at the repo
root — `/detect` had likely been 503ing since the commit that introduced
it, for reasons that had nothing to do with the frontend. Fixed with
`git mv`, and Person B's retrained model (`billbro_v3_best.pt`, mAP50
~0.92) swapped in at the same time. Still true: "Integrated" means
"wired up to the documented shape," not "confirmed via an actual run" —
that end-to-end test hasn't happened from this side yet, but should
behave differently now that both bugs are fixed.

✅ **Pepsi fixed, real numbers.** Was AP50 0.000 (dataset gap, zero real
Pepsi images ever trained on). Retrained with a real 202-image Pepsi
dataset: AP50 **0.885**, precision 0.944, recall 0.780. Genuinely working
now, not a workaround — but recall 0.78 still means ~1-in-5 real cans
missed (smallest val set of the six classes), so per Person B's own
recommendation, the Checkout warning was softened rather than removed.
Also worth knowing: Pepsi and Diet Coke (the two most visually similar
classes) can still get confused with each other in real-world testing —
accepted as fine for proof-of-concept, not being re-opened right now.

## Frontend structure & design

Six pages, grouped into two nav sections:
- **Store Operations** — Checkout, Inventory, Alerts (all three live)
- **Catalog & Management** — Add Item (UI built, waiting on backend),
  Admin, Models (still placeholders)

Dark mode (Discord-style grey + purple) and light mode (soft pink + dark
violet) are both done, plus a collapsible sidebar.

## Workflow

1. Person A/B build against `API_CONTRACT.md`. If a shape doesn't fit,
   edit that doc and flag it.
2. When something's confirmed, update `API_CONTRACT.md`'s status tracker.
3. Person C wires up the page/call in `frontend/src/api.js` and flips
   status to `Integrated`.

## Open questions (unresolved as of this snapshot)

- Production CORS origin, once a deploy target exists.
- Auth — none mentioned yet; assumed open on local network for now.
- Admin and the fuller model-management endpoints — genuinely not built
  yet (Weeks 7, 8).
- Whether the deployed backend actually has GPU access (affects /detect
  latency — see above).
- Manual vs. automatic shelving confirmation — still open, raised in
  `BillBro_TeamUpdates.md` between Person A and Person B (Person B
  recommends automatic, gated on the existing mAP50 threshold — not yet
  confirmed as final).
- **Not yet done from this side:** a real end-to-end test of `/detect` +
  `/checkout/bill` against a running `Person-A` backend — both bugs that
  were blocking it are now confirmed fixed in real code, but no one's
  actually run the full flow yet. Only remaining prerequisite: confirm
  `migrate_items_training_columns.py` was run against the live DB.
- ~~`GET /models/active` 404~~ — **fixed this session**, applied directly
  in Person A's worktree (worktree-only, not pushed).
- Real schema mismatches Person B found in `database.py` for the
  training endpoints — **now confirmed fixed** in his pushed
  `database.py`: `TrainingJob.metrics` column added, `current_epoch` is
  `String(20)`, `Item.status` column exists. A migration script
  (`migrate_items_training_columns.py`) handles bringing the live `.db`
  file up to date with these — needs to have actually been run.
- `data.yaml` alone won't unblock Add Item testing — the base training
  images it points to were never committed to the repo. Still needs a
  team decision on where a ~180-image sample should live. Person A did
  add a clean fail-fast `503` if the yaml itself is missing, at least.
- `main` merge — intentionally on hold pending a team sync, per Person A.

Resolved this round: `/checkout/bill`'s item-matching bug (confirmed
fixed in real code), `TrainingJob`/`Item` schema mismatches (confirmed
fixed), `/items` vs `/inventory` inconsistency, `GET
/training/job/{id}`'s field names (locked), `barcode` (confirmed
unnecessary), `/detect`'s two backend bugs (merge conflict, then wrong
model path — both fixed), `POST /items`'s query-param bug (fixed),
`FRONTEND_INTEGRATION_GUIDE.md` (read directly, confirmed stale — wrong
framework/port, ignore it), model version scheme (confirmed strings, not
numeric ids), Pepsi's AP=0.000 (fixed, real numbers above), and
`FRONTEND_INTEGRATION_GUIDE.md` (confirmed to exist, not yet pulled).
