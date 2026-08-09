# Update for Person C (you) — integration + live testing session

Summary of everything built and fixed while actually running the full
stack locally for the first time — `Integrated/` went from "assembled
but never run" to "genuinely tested against a live backend and a real
camera." This is the record of that session.

## Environment setup, real snags and fixes

- `psycopg2-binary`/`celery`/`redis` in `backend-requirements.txt` failed
  to install (psycopg2 needs a local PostgreSQL install for its build,
  celery/redis are entirely unused — training runs on a plain
  `threading.Thread`, not a task queue). Removed all three, plus
  loosened the exact version pins on `torch`/`ultralytics`/etc. since
  they were pinned against an older Python than what's actually
  installed. `pip install -r backend-requirements.txt` now succeeds
  clean.
- Port 8000 was taken by another local project — backend moved to 8001,
  frontend's `.env` (`VITE_API_BASE_URL`) updated to match. Vite itself
  fell back to 5174 when 5173 was also taken.
- **CORS broke because of the port fallback** — `allow_origins` only had
  the default ports hardcoded. Added 5174/5175/8001 as fallbacks in
  `api_app.py`.

## Real bugs found only by actually clicking through the app

1. **HEIC photos failed to decode.** iPhone photos default to HEIC;
   the browser previews them fine but OpenCV's `cv2.imdecode` on the
   backend can't read HEIC at all — `POST /detect` failed with "Could
   not decode base64 image" on every real iPhone photo. Fixed by
   re-encoding through a `<canvas>` to JPEG client-side before sending,
   regardless of source format (`fileToBase64()` in `Checkout.jsx`).
2. **A held-up product photo (Pepsi can, tile floor, glare) got zero
   detections at the default 0.5 confidence threshold.** Not a bug —
   genuine model behavior on an off-angle, non-studio photo. See the
   webcam feature below for how this got worked around for live use.
3. **Leftover test data ("Jesus" item, sku 211) was polluting the
   Inventory page** — removed directly from the DB (no delete endpoint
   exists yet).

## New features built this session

- **Webcam detection on Checkout**, in two iterations: first a
  manual-capture live preview, then upgraded to **continuous live
  detection** — camera stays open, sends a frame to `/detect` every 2
  seconds, cart shows whatever the current frame sees (not
  accumulated), "Lock cart" freezes it and moves into the existing
  review/bill flow. Uses a lower confidence threshold (0.25) than the
  file-upload path (0.5) specifically because real-world handheld
  frames need it — see `UPDATE_FOR_PERSON_B.md` for why. Guards against
  overlapping `/detect` calls if one tick runs long. Properly stops the
  camera stream on cancel/lock/unmount so the camera light doesn't stay
  on.
- **Restock now captures expiry date**, not just batch number/arrival
  date — added `expiry_date` to `PATCH /items/{id}/restock`'s optional
  fields, both backend and the Inventory page's restock form.
- **Inventory table now shows batch number + expiry date** per row —
  `GET /inventory` previously didn't return these at all even though
  they were being written by restock; added them to the response and a
  new table column.

## What's genuinely confirmed working end-to-end now

Backend boots, migration runs clean, `/health` responds,
`/detect` returns real detections from both uploaded photos and live
camera frames, Inventory's restock flow (including the new expiry
field) round-trips correctly through the real database.

## Still not tested

Add Item's full upload-photos-and-train flow (blocked on the missing
base dataset), the Admin bulk-CSV/settings endpoints (built, not yet
exercised with real data through a running server), and Alerts'
resolve flow.
