# BillBro — Backend Context (for Person A's Claude)

Paste this into your own Claude chat/project for full context on where
things stand with the frontend, without needing to read the frontend code
yourself. Updated after your `RESPONSE_TO_PERSON_C.md` — thanks for the
quick turnaround on the first three items.

## Resolved (nothing needed from you here)

- **CORS** — confirmed working for `localhost:5173`. One thing to
  remember: whatever origin nginx ends up serving the built frontend from
  in production isn't `localhost:5173`, so that'll need adding to your CORS
  config once a deploy target is picked. Not urgent now.
- **`/items` vs `/inventory`** — documented and the frontend's Inventory
  page is now live against `GET /inventory` using the shape you gave.
- **`PATCH /alerts/{id}`** — confirmed no request body; Alerts page is
  live against it, including the resolve action.

## The one thing still blocking us: detect endpoint decision

This is the only thing actually stopping frontend work right now
(Checkout). Your doc said you're choosing between:
- **Option A** — your API gets a `/detect` endpoint wrapping Person B's model
- **Option B** — frontend calls Person B's model service directly

Whichever way you land, I need three things to wire up Checkout:
1. The URL/base path to call (yours, or Person B's service)
2. The exact response shape — raw per-instance detections (one entry per
   detected object) or something pre-grouped by item+quantity
3. Whether the frontend or your API does the aggregation into
   `{item_name, confidence, quantity}` before `/checkout/bill` gets called

No rush if you said "this week" — just flagging it's the one thing
actively blocking a page, everything else on my end can proceed without
you.

## Still not built (no rush — flagging for Weeks 4/7/8)

- Bulk CSV upload + store settings (Admin, Week 7)
- Training image upload + job status polling (Add Item, Week 4)
- Model version history + activate/rollback beyond `GET /models/active`
  (Models, Week 8)

## Minor — only if you have a spare minute

- `POST /items` request body shape wasn't shown in your docs — assuming
  it mirrors the `GET /items` response minus `id`, but worth confirming
  before I wire up Add Item.
- `GET /models/active` and `GET /health` response shapes also weren't
  shown — not blocking anything yet, just noting for later.
- You mentioned a `FRONTEND_INTEGRATION_GUIDE.md` — haven't seen that one,
  send it over if it exists.

## How to respond

Same as before — tell me directly, update `FOR_PERSON_C.md`, or drop a
note in the group chat. I'm keeping `API_CONTRACT.md` as the single source
of truth and updating it as things resolve.
