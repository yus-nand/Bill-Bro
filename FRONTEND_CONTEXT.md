# BillBro — Frontend Context (for project knowledge)

Drop this file into the shared project's knowledge/context so anyone
(teammates or Claude, in any chat on this project) has the current state
of the frontend without re-explaining it. Keep it updated as things change
— this is a snapshot, not a changelog.

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

🚩 **Possible misalignment:** a later doc from Person A
(`FOR_PERSON_C_CHECKOUT_INTEGRATION.md`) frames Checkout as Week 1 and
Add Item as "Week 2 Preview" — the *original* order, not the reversed
one. Not clear if he's seen the team update. Doesn't block anything since
both pages are built either way, but worth a quick sync to confirm
what's actually current. Full detail in `API_CONTRACT.md`.

New schema implications: items now carry `batch_number`, and have a
status lifecycle (`pending → training → shelved`, or `failed`) — an item
is only checkout-detectable once `shelved`. This is a new
constraint; item creation and checkout-availability used to be the same
event.

Note: `barcode` was also mentioned in the team update but was deliberately
dropped from the Add Item form — most of the catalog is loose produce
without real scannable barcodes, and there's no scanner integration, so
it would've just been an unreliable manually-typed field. SKU remains
the trustworthy identifier. Full reasoning in `API_CONTRACT.md`.

## Backend status: 3 of 6 pages genuinely live, Add Item built ahead of backend

- API at `http://localhost:8000`, docs at `/docs`
- **Live and integrated:** Checkout (photo → `/detect` → editable cart →
  `/checkout/bill` → receipt), Inventory (`/inventory`), Alerts
  (`/alerts`, resolve action)
- **Built on the frontend, waiting on backend endpoints:** Add Item
  (details form → photo capture → training progress → shelved/failed) —
  will error until `POST /training/upload_images` and
  `GET /training/job/{id}` exist on Person A's side
- **Confirmed, not wired up yet:** `GET/POST /items`,
  `PATCH /inventory/{id}` (manual adjust UI not built), `GET /models/active`,
  `GET /health`
- **Still placeholders — no backend endpoints exist yet:** Admin (Week 7),
  the fuller Models page beyond "current active model" (Week 8)

## Detection flow (now resolved — Option A)

Person A's API owns `POST /detect`: frontend sends a base64 image, gets
back raw per-instance detections `{item_name, confidence, bbox}`. The
frontend aggregates those into `{item_name, confidence, quantity}`
(`utils.js` → `aggregateDetections()`, averages confidence per item) before
calling `POST /checkout/bill`. The backend response is the source of truth
for the receipt — the frontend doesn't recompute totals locally, it just
renders what `/checkout/bill` returns.

⚠️ **No GPU acceleration by default — Person B's own notes say inference
can take up to ~2 minutes per image on CPU.** The frontend's axios client
overrides its default 15s timeout to 3 minutes specifically for
`/detect`, and the Checkout UI shows a "still detecting" message once the
wait passes 8 seconds so staff aren't left staring at a frozen screen.
Worth confirming with Person A whether the deployed backend actually has
GPU access — if so, both of those can come back down.

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

- Minor inconsistency in Person A's docs: one section says `/items` has no
  stock info, another says it "includes current_count." Not blocking
  (Inventory correctly uses `/inventory`), just worth a sanity check.
- Production CORS origin, once a deploy target exists.
- Auth — none mentioned yet; assumed open on local network for now.
- `FRONTEND_INTEGRATION_GUIDE.md` has been referenced multiple times but
  never actually shared (it's sitting on Person A's local machine).
- Admin and the fuller model-management endpoints — genuinely not built
  yet (Weeks 7, 8).
- Whether the deployed backend actually has GPU access (affects /detect
  latency — see above).
- Whether `GET /models` will expose Person B's `v1`/`v2` string version
  ids as-is or wrap them in something else — matters for the Models page.
- `GET /training/job/{id}`'s exact field names — two docs disagree
  (`BillBro_TeamUpdates.md` vs `PERSON_B_DELIVERABLES_ANALYSIS.md`); the
  frontend reads both possible shapes defensively, but Person A should
  confirm which one his endpoint returns. Full detail in
  `API_CONTRACT.md`.
- Whether `batch_number` is the exact field name Person A's `POST /items`
  expects — frontend's best guess, unconfirmed. Also whether his
  validation requires `barcode` (frontend omits it by decision) — would
  need revisiting if his backend rejects items without one.
- Manual vs. automatic shelving confirmation, and cumulative vs.
  fresh-from-base retraining strategy — open questions raised in
  `BillBro_TeamUpdates.md` itself, between Person A and Person B.
