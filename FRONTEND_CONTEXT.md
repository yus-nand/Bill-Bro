# BillBro — Frontend Context (for project knowledge)

Drop this file into the shared project's knowledge/context so anyone
(teammates or Claude, in any chat on this project) has the current state
of the frontend without re-explaining it. Keep it updated as things change
— this is a snapshot, not a changelog.

## Team

- **Person A** — Backend API (FastAPI + SQLite, real and running)
- **Person B** — ML model (grocery detection). As of Person A's last
  status update, Person B still needs to convert `billbro_v3.onnx` →
  `.pt` and deliver a `GroceryDetector.predict()` function — that's what
  `POST /detect` wraps, so detection accuracy depends on that landing.
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

## Backend status: 3 of 6 pages are genuinely live now

- API at `http://localhost:8000`, docs at `/docs`
- **Live and integrated:** Checkout (photo → `/detect` → editable cart →
  `/checkout/bill` → receipt), Inventory (`/inventory`), Alerts
  (`/alerts`, resolve action)
- **Confirmed, not wired up yet:** `GET/POST /items`,
  `PATCH /inventory/{id}` (manual adjust UI not built), `GET /models/active`,
  `GET /health`
- **Still placeholders — no backend endpoints exist yet:** Add Item
  (needs training endpoints, Weeks 2-3), Admin (Week 7), the fuller
  Models page beyond "current active model" (Week 8)

## Detection flow (now resolved — Option A)

Person A's API owns `POST /detect`: frontend sends a base64 image, gets
back raw per-instance detections `{item_name, confidence, bbox}`. The
frontend aggregates those into `{item_name, confidence, quantity}`
(`utils.js` → `aggregateDetections()`, averages confidence per item) before
calling `POST /checkout/bill`. The backend response is the source of truth
for the receipt — the frontend doesn't recompute totals locally, it just
renders what `/checkout/bill` returns.

## Frontend structure & design

Six pages, grouped into two nav sections:
- **Store Operations** — Checkout, Inventory, Alerts (all three live)
- **Catalog & Management** — Add Item, Admin, Models (still placeholders)

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
- Admin, training/add-item, and fuller model-management endpoints —
  genuinely not built yet, per Person A's own Week 2/7/8 timeline.
- Detection accuracy depends on Person B delivering the converted model —
  worth checking in on that separately from the API contract itself.
