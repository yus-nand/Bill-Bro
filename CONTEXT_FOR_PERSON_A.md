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

## Checkout, Inventory, Alerts: built and wired to spec

Checkout is fully wired end to end: photo → `/detect` → staff-editable
quantities → `/checkout/bill` → receipt rendered straight from your
response. Inventory and Alerts are live against `/inventory` and
`/alerts`. Timeout on `/detect` was originally set defensively at 3
minutes based on Person B's "~2min on CPU" worst case, then dialed back
to 30 seconds once your doc reported real measured latency (~2-3s cold
start, ~100-200ms after).

⚠️ **One thing worth flagging back to you:** your `RESPONSES_TO_PERSON_B_AND_C.md`
headlines `/detect` as "LIVE," but its own last section says you're still
resolving a numpy/torch dependency issue and haven't pushed the code yet
(sitting on `feat/detect-endpoint` locally). So from where I sit,
Checkout is wired up correctly against the documented contract, but I
can't actually confirm it works against a running instance of your API
yet — let me know once the dependency issue's sorted and it's pushed, and
I'll do a real end-to-end test.

Also flagging: Pepsi has AP = 0.000 per your doc (dataset gap — only a
generic soda-can image in training data). Not something I need to fix on
my end, just noting Checkout's UI now tells staff not to trust Pepsi
detections specifically, separate from the other five items.

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
would've just been an unreliable manually-typed field. Your confirmed
`POST /items` example in `RESPONSES_TO_PERSON_B_AND_C.md` doesn't include
`barcode` either, so that's settled — no action needed there.

**But that same example also doesn't show `batch_number`** — not in the
request, not in the response. Could just be an abbreviated example, could
mean it's not actually a field your endpoint accepts. I'm still sending
it from the frontend, but if your validation silently drops it (or
rejects unknown fields), let me know either way so I can stop guessing.

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
3. **`batch_number` on `POST /items`** — see above, your confirmed example
   doesn't show it. Worth a direct answer.

Resolved since last time, no action needed from you: `GET
/training/job/{id}`'s shape (thanks for locking that down — using `id`,
`status`, `progress`, `current_epoch` as a `"N/M"` string, `metrics`,
`error_message`, `created_at`, `completed_at` now), and `barcode` (your
example confirms it's not needed).

## What's next on my end

1. Whatever comes back on the `batch_number`/build-order questions above.
2. Real end-to-end test of `/detect` once your numpy/torch issue is fixed
   and the code's pushed — right now I'm only confident it's correct
   against the documented shape, not against a running instance.
3. nginx deploy target still not picked — `frontend/nginx.conf` is ready,
   just not pointed at anything real yet.
4. Testing Add Item for real once your training endpoints exist
   (`POST /training/upload_images`, `GET /training/job/{id}`).

## How to respond

Same as always — tell me directly, update `FOR_PERSON_C.md`, or drop a
note in the group chat. `API_CONTRACT.md` stays the source of truth.
