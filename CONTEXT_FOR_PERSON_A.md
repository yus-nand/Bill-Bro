# BillBro — Backend Context (for Person A's Claude)

Paste this into your own Claude chat/project for context on where things
stand with the frontend. Thanks for closing out all the open items —
Checkout, Inventory, and Alerts are all genuinely working now.

## Everything's resolved — nothing blocking right now

- **`POST /detect`** — built to spec, integrated into Checkout. Frontend
  sends base64 image, gets back detections, aggregates them, sends to
  `/checkout/bill`. Working end-to-end on my side.
- **CORS, `/items` vs `/inventory`, `/alerts/{id}` body, `POST /items`
  shape, `/models/active`, `/health`** — all confirmed and either
  integrated or ready to wire up when those pages get built.

Nothing urgent needed from you right now. Two small things whenever
convenient, not blocking anything:

## 1. Minor doc inconsistency (not urgent)

Your first doc said `/items` has no stock info (`/inventory` is separate
for that). A later section said `GET /items` "Response: List of items with
current_count... Use for: ...inventory page." Those don't match — I've
kept the Inventory page on `/inventory` since that's been explicitly
confirmed multiple times as the right one, but wanted to flag the
inconsistency in case it's a sign of a different underlying discrepancy
(e.g. does `/items` actually return current_count now and the example
response is just stale?).

## 2. `FRONTEND_INTEGRATION_GUIDE.md`

You've referenced this a few times as having CORS config, deployment
steps, etc., but it's listed as living at
`C:\Users\Admin\Desktop\BE Project\...` on your machine — I don't think
it's actually been shared yet. Send it over whenever, no rush, mostly
curious if there's deployment guidance in there I should know about ahead
of picking an nginx target.

## What's next on my end

Building out Add Item once your training endpoints
(`POST /training/upload_images`, `GET /training/job/{id}`) land — no rush,
I know that's Week 2-3 for you. Same for Admin (Week 7) and the fuller
Models page (Week 8).

One thing worth a heads-up if you talk to Person B before I do: detection
*accuracy* in Checkout depends on the model conversion
(`billbro_v3.onnx` → `.pt`) landing — the endpoint itself works regardless,
but worth knowing if that's still pending on their end.

## How to respond

Same as always — tell me directly, update `FOR_PERSON_C.md`, or drop a
note in the group chat. `API_CONTRACT.md` stays the source of truth.
