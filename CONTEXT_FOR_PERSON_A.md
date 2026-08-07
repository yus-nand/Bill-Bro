# BillBro — Backend Context (for Person A's Claude)

Person C (frontend) put this together after reconciling `FOR_PERSON_C.md`
against the actual frontend build. Paste this into your own Claude
chat/project so it has full context on what the frontend needs from your
API — no need to go read the frontend code yourself.

## What's already confirmed and working

Your handoff doc (`FOR_PERSON_C.md`) is being used as-is for these, and the
frontend is already calling them (or ready to):

| Endpoint | Frontend usage |
|---|---|
| `GET /items` | Inventory page — live, working off this today |
| `GET /items/{id}` | not called yet |
| `POST /items` | Add Item page (not built yet) |
| `PATCH /inventory/{id}` `{quantity, reason}` | Inventory manual adjust (not wired yet) |
| `GET /alerts` | Alerts page — live, working off this today |
| `POST /checkout/bill` `{detections: [{item_name, confidence, quantity}]}` | Checkout (blocked, see below) |
| `GET /models/active` | Models page (not built yet) |
| `GET /health` | not called yet |

No changes needed on your side for these — just flagging what's actually
in use so you know what a breaking change would affect.

## 4 things I need from you

### 1. CORS — probably the first thing that'll break testing

The frontend runs on a different origin than your API (`localhost:5173` in
dev, wherever nginx serves it in prod; your API is `localhost:8000`).
Browser fetches will fail with a CORS error even though `curl`/Postman/your
`/docs` page work perfectly fine — that's expected, not a bug in either of
our code. Can you confirm `CORSMiddleware` is (or will be) configured to
allow the frontend's origin? If you're using FastAPI:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # add prod origin once known
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 2. No detection endpoint exists — this blocks Checkout entirely

Your doc shows `POST /checkout/bill` expecting detections to already exist
as `{item_name, confidence, quantity}`, but there's no endpoint anywhere
that takes a photo and returns detections (no `/checkout/detect`,
`/predict`, etc.). I need to know:

- Are you adding a detect endpoint that wraps Person B's model? Or does
  the frontend call Person B's model service directly, separately from
  your API?
- If it's a separate service, what URL/port, so I can add it to the
  frontend's env config?
- What shape does it return — raw per-instance detections (one entry per
  detected object, like `predict.py`'s `(class_name, confidence, xyxy)`
  tuples) or something pre-grouped? If it's per-instance, the frontend
  will aggregate into the `{item_name, confidence, quantity}` shape your
  `/checkout/bill` expects before sending — just confirm that's the right
  division of responsibility.

### 3. Two response/request shapes weren't shown in your doc — need confirming

- `GET /inventory` — you listed this as a separate endpoint from
  `GET /items`, but only gave a response example for `/items`. What does
  `/inventory` actually return, and should the frontend use it instead of
  `/items`, or are they interchangeable?
- `PATCH /alerts/{id}` (resolve an alert) — no request body shown. The
  frontend is currently sending `{"resolved": true}` as a guess — is that
  right, or does it expect something else?

### 4. Endpoints that don't exist yet, needed for later weeks

Not urgent, but these pages are blocked without them:
- Bulk CSV upload + store settings (Admin page, Week 7)
- Training image upload + job status polling (Add Item page, Week 4)
- Model version history + activate/rollback (Models page, Week 8, beyond
  the `GET /models/active` you already have)

No rush on these — just flagging so they're on your radar before those
weeks arrive.

## How to respond

Whatever you confirm, the easiest path is: tell Person C directly, or
update `FOR_PERSON_C.md` / say it in the group chat. Person C is keeping
`API_CONTRACT.md` (in the shared project) as the single source of truth
and will update it once each of these is answered.
