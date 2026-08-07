# BillBro — Backend Context (for Person A's Claude)

Paste this into your own Claude chat/project for context on where things
stand with the frontend.

## Code is pushed — you can look at it directly

Frontend is on `Person-C` on GitHub:
`https://github.com/yus-nand/Bill-Bro/tree/Person-C` (latest commit
`frontend-2`). `frontend/src/api.js` is the actual client code calling
your endpoints. `API_CONTRACT.md` at the repo root is the living doc of
what's confirmed vs. still open — check that first before re-explaining
anything, it's kept current.

## Checkout, Inventory, Alerts: done, live, working

Confirmed via your `FOR_PERSON_C_CHECKOUT_INTEGRATION.md` that `/detect`
is actually live (not just spec'd) — Checkout is fully wired end to end:
photo → `/detect` → staff-editable quantities → `/checkout/bill` →
receipt rendered straight from your response. Inventory and Alerts are
live against `/inventory` and `/alerts`. Timeout on `/detect` was
originally set defensively at 3 minutes based on Person B's "~2min on
CPU" worst case, then dialed back to 30 seconds once your doc reported
real measured latency (~2-3s cold start, ~100-200ms after). No open
issues on any of these three.

## Add Item is fully built too — ahead of your endpoints

Per `BillBro_TeamUpdates.md`, Add Item got reprioritized as the
first-feature loop (item → train → shelve) rather than a Week 4 add-on. I
built the whole frontend flow ahead of your backend landing: details form
→ photo capture (15 recommended, 5 min) → `POST /training/upload_images`
→ polls `GET /training/job/{id}` every 5s → shelved/failed result
screen. It'll error on submit until those two endpoints exist — expected,
built ahead of time on purpose so testing can start the moment you ship
them.

**One decision you should know about: `barcode` was dropped from the
item form.** `BillBro_TeamUpdates.md` listed it as a new field alongside
`batch_number`, but most of the actual catalog (apple, banana, dragon
fruit, custard apple) is loose produce that doesn't have real scannable
barcodes at retail, and there's no scanner integration built — so it
would've just been an unreliable manually-typed field. `batch_number`
is still sent. **If your `POST /items` validation requires `barcode`,
item creation will start failing the moment we test against it** — worth
telling me now if that's the case, cheap to add back if needed.

## 🚩 Possible mismatch worth a quick sync

Your `FOR_PERSON_C_CHECKOUT_INTEGRATION.md` frames Checkout as Week 1 and
Add Item as "Week 2 Preview" — the original order. `BillBro_TeamUpdates.md`
says Add Item comes first, ahead of checkout. Not sure which is actually
current on your end, or if you've seen the team update doc. Doesn't block
me either way (both are built), but figured you'd want to know the two
docs disagree.

## Smaller open items, no rush

1. **`/items` vs `/inventory` doc inconsistency** — one of your docs said
   `/items` has no stock info, another said it "includes current_count."
   Inventory page uses `/inventory` regardless (confirmed correct
   multiple times), just flagging in case it points at something else
   being off.
2. **`FRONTEND_INTEGRATION_GUIDE.md`** — referenced a few times, still
   don't think it's actually been shared. Send whenever, mostly curious
   if there's deployment guidance in there ahead of picking an nginx
   target.
3. **`POST /items` request body** — I'm guessing at `batch_number` as the
   field name since it wasn't in your original examples. Confirm once the
   endpoint exists.
4. **`GET /training/job/{id}` shape** — two of your/Person B's docs
   disagree on field names (`current_epoch` vs `epoch`,
   `error_message` vs `reason`, etc.). Frontend reads both defensively
   for now, but worth confirming which one your endpoint actually
   returns so I can simplify.

## What's next on my end

1. Whatever comes back on the barcode/build-order questions above.
2. nginx deploy target still not picked — `frontend/nginx.conf` is ready,
   just not pointed at anything real yet.
3. Testing Add Item for real once your training endpoints exist.

## How to respond

Same as always — tell me directly, update `FOR_PERSON_C.md`, or drop a
note in the group chat. `API_CONTRACT.md` stays the source of truth.
