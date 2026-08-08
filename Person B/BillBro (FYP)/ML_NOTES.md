# ML Notes — Person B

## Update — real-world test: pepsi/diet_coke confuse each other; found a checkout-breaking bug

User tested the swapped-in model directly: single Pepsi can detects
correctly at ~30% confidence; a Diet Coke alone gets labeled "pepsi";
Pepsi + Diet Coke together in one frame both detect but with labels
swapped. Makes sense given the training numbers already on record —
diet_coke and pepsi are the two most visually similar classes (both
cylindrical cans) and by far the smallest val sets (31 and 50 instances
vs 148-412 for the fruit classes), so they're the most likely pair to
get confused. Call made: acceptable for proof-of-concept, revisit
training later. Not re-opening this now per that decision.

While starting on Add Item/Inventory/Alerts, found the actual root
blocker for testing any of them: `process_checkout()`'s
`Item.name.ilike(item_name)` can never match, because `Item.name` is
Title Case with spaces ("Diet Coke") while the model's class names are
snake_case/joined ("diet_coke", and "dragonfruit" has no separator at
all against "Dragon Fruit"). Every checkout has been silently dropping
every detected item — zero inventory decrements, zero alerts, ever,
regardless of what's actually in the photo. Wrote up the bug + a
normalize-and-compare fix in `FOR_PERSON_A_CHECKOUT_MATCHING_BUG.md` —
this needs to land before Inventory/Alerts can be meaningfully tested at
all, since they're both downstream of checkout actually resolving items.

## Update — Person A's model-path bug fix verified; data.yaml blocker is deeper than the file

Verified `CONTEXT_FOR_PERSON_B_v2.md`'s claims against `origin/Person-A`
directly (commit `6e45836`): `models/grocery_yolov8.pt` SHA-256 matches
my swapped-in file exactly, training routes from `b09f19e` match what
was described (plus a nice try/except safety net he added beyond what I
drafted), `Item.status` genuinely still unfiltered in `/detect` and
`/checkout/bill` as he said. All checks out.

Sent back confirmed pepsi numbers (AP50 0.885, recall 0.780 — recommend
Person C soften rather than remove the Checkout warning, given ~1-in-5
miss rate). On `data.yaml`: gave him the file, but flagged it won't
actually unblock training — `ReplayPool.bootstrap_from_base()` needs the
*actual* base training images/labels reachable from his server, and
those were only ever on Colab/local machines, never committed to the
shared repo. Fixed the silent-failure bug this would've caused
(`bootstrap_from_base` used to write a "complete" empty registry if the
label dir was missing, permanently disabling replay protection with zero
error — now raises `FileNotFoundError` loudly instead). Real fix needs a
team decision on where a ~180-image representative sample should live
(repo/git-LFS/cloud bucket) — flagged back rather than guessing at
infra that isn't mine to decide.

## Update — pepsi genuinely fixed, model swapped in (real numbers this time)

Got the actual cell 10 training log for `billbro_v3_best.pt`. Real
per-class metrics (not the stale template table from
`PERSON_B_NEXT_STEPS.md`, which still said `pepsi AP50=0.00` and was
wrong — flagged and corrected in `TRAINING_RESULTS.md`):

- Overall: mAP50 0.956, mAP50-95 0.789, precision 0.965, recall 0.930
- **pepsi: AP50 0.885** (was 0.000), precision 0.944, recall 0.780 —
  real, working class now, not a "detect as diet_coke" workaround
- Weakest class: diet_coke (AP50-95 0.510, smallest val set at 31
  instances) — worth watching, not blocking

Run was on Colab (Tesla T4), not Jupyter — worth noting since the plan
was to move training locally, but it worked fine so not raising it as a
problem. Swapped the verified model into `models/grocery_yolov8.pt` and
`billbro_v3.pt`, checksums confirmed matching the upload. `classes.json`
unchanged — same 6 classes, same order, no remap needed.

## Update — frontend is React/Vite (not Flask), found a real `/models` bug

Went through Person C's actual folder to confirm the stack: it's a React
+ Vite SPA (`frontend/`, axios), not Flask — `app.py`/`pages/*.py` at
the repo root are the old, explicitly-deprecated Streamlit skeleton.
While mapping `frontend/src/api.js` against the backend, found that
`GET /models/active` reads a SQL `ModelVersion` table that nothing ever
writes to — `StoreModelManager.register_version()` writes to
`models/versions.json` instead, by design (keeps the DB out of the ML
code). The route will 404 forever as currently wired. Wrote up the fix
(read from `StoreModelManager` directly) plus `GET /models` and
activate/rollback routes in `FOR_PERSON_A_MODELS_ENDPOINTS.md` — also
resolves Person C's open question in `API_CONTRACT.md` about whether
model versions are strings (`v1`/`v2`) or numeric ids: they're strings.

## Update — new `billbro_v3_best.pt` structurally verified, pepsi accuracy still unconfirmed

Uploaded model checked without torch (sandbox has none) by reading the
`.pt`'s zip contents directly (`unzip -l` + `strings` on `data.pkl`,
the pickle inside every PyTorch checkpoint):

- **Genuinely a new file this time** — MD5 differs from the currently
  integrated `models/grocery_yolov8.pt` (unlike the earlier "retrained"
  upload, which was checksum-identical to the old one).
- **All 6 class names present and distinct**, including `pepsi` as its
  own class (not merged into `diet_coke`) — `apple`, `banana`,
  `dragonfruit`, `custard_apple`, `diet_coke`, `pepsi` all found in the
  pickled `names` dict. This is the fix that was missing before.
- Architecture/layer shapes match the existing model (YOLOv8m-sized),
  `ultralytics` version `8.4.116` embedded, saved
  `2026-08-08T15:37:09 UTC` — consistent with "just finished training."
  `epoch=-1` / `best_fitness=None` are expected for a stripped
  `best.pt`, not a red flag.
- **Inconsistency found:** the checkpoint's embedded `data.yaml` path is
  `/content/merged_dataset/data.yaml` — a Colab path, even though the
  plan was to move training to Jupyter for GPU reasons. Worth asking
  whether this run actually happened on Colab.
- **Can't verify from the weights file alone:** actual mAP50/per-class
  AP isn't stored in a `best.pt` checkpoint (only in `results.csv` /
  training logs), so accuracy has to come from the notebook's own
  validation output, not this file.

**Contradiction in `PERSON_B_NEXT_STEPS.md`'s own numbers:** its dataset
summary lists 484 Pepsi images used, but its per-class table still shows
`pepsi: AP50 = 0.00` with "Known issue: generic soda-can dataset, not
real Pepsi" — that's the OLD bug's explanation, and doesn't square with
484 dedicated Pepsi images being listed as part of this run. Likely a
stale template table that wasn't updated with this run's real numbers,
but flagged back to the user rather than assumed — need the actual
cell 10 per-class output (or `results.csv`) to confirm real pepsi AP50
before swapping this model in.

## Update — work done ahead of retrain finishing

While the pepsi retrain runs locally: checked Person A's `database.py`
against what `training.py` actually produces for the two training
endpoints he's about to build. Found two real mismatches before he hits
them — `TrainingJob` has no `metrics` column (only a single `accuracy`
float; `retrain_model()` returns a full dict with per-class AP50) and
`current_epoch` is typed `Integer` but `training.py` writes `"3/5"`-style
strings. Also: `Item` has no `status` column at all yet, so the
pending→training→shelved gate described in `BillBro_TeamUpdates.md`
has nowhere to live. Wrote up all three plus ready-to-paste
`POST /training/upload_images` / `GET /training/job/{id}` routes in
`FOR_PERSON_A_TRAINING_ROUTES.md`.

Also added `benchmark_inference.py` — measures `GroceryDetector.detect()`
latency (mean/p50/p95/p99) against the <100ms target flagged as open
below. Can't run it in this sandbox (no torch), ready to run locally once
the new model lands.

## Update — build order flipped (per `BillBro_TeamUpdates.md`)

Team decided "Add Item → Train → Shelve" is now the first feature, ahead
of checkout/billing. Items go `pending → training → shelved` (or
`failed`), and only `shelved` items are detectable at checkout. This
session's work responds to that:

- **`ReplayPool`** (new, in `training.py`) — replaces the old "replay from
  the original 6 base classes only" logic. Now persistent per-store: every
  time an item is successfully shelved, a sample of its own images joins
  the pool, so every future retrain protects *all* previously shelved
  items, not just the launch classes. Tested with a 3-generation
  simulation (base → item 1 → item 2), confirming item 1 gets correctly
  replayed (and remapped to its class id) when item 2 trains.
- **`JobStatus`** fields renamed to match Person A's new `TrainingJob`
  table exactly (`item_id`, `current_epoch`, `error_message`,
  `created_at`, `completed_at`) — see `CONTEXT_FOR_PERSON_A.md` for the
  full mapping table.
- Three open decisions from the team doc answered and documented in
  `CONTEXT_FOR_PERSON_A.md`: cumulative fine-tuning (yes, from the
  store's current model, not fresh-from-base), automatic shelving (yes,
  the mAP50 gate already implemented is the shelve signal), and the 0.80
  mAP50 threshold (confirmed as-is).
- `barcode` / `batch_number` are new `Item` fields — Person A's schema,
  no ML-side action needed.

## Update — `/detect` doesn't actually exist in Person A's pushed code yet

`RESPONSES_TO_PERSON_B_AND_C.md` says `/detect` is "✅ LIVE", but checking
`origin/Person-A`'s real `api_app.py` shows only the original 9 routes —
no `/detect`, and no `feat/detect-endpoint` branch exists anywhere in the
repo. Consistent with that same doc's own admission of an unresolved
numpy/torch install issue. Wrote the actual route
(`FOR_PERSON_A_DETECT_ROUTE.md`) ready to paste in, plus a likely fix for
the dependency issue: `requirements.txt` pins `torch==2.1.1` /
`ultralytics==8.0.217`, but his repo's `.pyc` cache shows Python 3.12 —
torch 2.1.1 has no 3.12 wheels (that landed in 2.2). Sanity-checked
against `frontend/src/pages/Checkout.jsx` — it already sends/expects
exactly the shape `detect_from_base64()` produces, so once the route's
pasted in this should just work end-to-end.

## Update — pepsi retrain complete, model swapped in

`billbro_v3.pt` / `billbro_v3.onnx` / `classes.json` added directly to the
repo (retrained via the patched notebook). `classes.json` confirms all 6
classes present. Copied `billbro_v3.pt` → `models/grocery_yolov8.pt`
(checksums match — clean swap, this is now the active model app.py and
`StoreModelManager` will load).

**Not yet verified:** actual pepsi AP50 / accuracy numbers, and detection
on a fresh out-of-dataset photo. This sandbox still has no
torch/ultralytics (no network access to install), so I can't run
inference or re-validate myself — need the numbers from cell 10's output
and confirmation the fresh-photo test worked.

## Update — Person A's follow-up commit has unresolved merge conflicts

He pushed the route (and it's good — matches my suggestion plus better
error handling/caching), `predict.py` (verified byte-identical to mine),
and `training.py`. But `api_app.py` and `requirements-minimal.txt` both
have literal `<<<<<<< Updated upstream` / `>>>>>>> Stashed changes`
conflict markers committed into the code — a `git stash pop` that was
never resolved. File won't even import as-is. Every hunk in both files
follows the same pattern (`Stashed changes` = correct, `Updated upstream`
= stale) — wrote exact fix instructions in
`RESPONSE_TO_PERSON_A_MERGE_CONFLICTS.md`.

---

# Original notes (Week 1-2)

## What was broken

`predict.py` and `utils.py` were missing from disk — only stale `.pyc`
cache remained, meaning `app.py` could not run at all (`ImportError` on
`from predict import GroceryDetector`). Both have been rebuilt to match
the interface `app.py` already expects. No changes were made to `app.py`.

## Critical finding: pepsi has 0.000 AP — root cause identified

`BillBroAgain.ipynb` cell 10's validation output shows:

```
✅ diet_coke   AP=0.885
⚠️  pepsi       AP=0.000
```

This is **not a training bug** — it's a dataset gap. In cell 3, the `soda`
dataset (`cyberwarriorstemcamp/soda-can-qr4c4`) downloaded with **only one
raw class**: `nc=1, names=['soda-can']`. `MANUAL_NAME_MAP` in cell 6 maps
`{0: "diet_coke", 1: "pepsi"}`, but index `1` never existed in this
dataset — every soda-can annotation collapsed into `diet_coke`. The merge
step (cell 8) confirms it: `soda: 119 imgs, 163 annots` all went to
`diet_coke`. **Zero pepsi images ever entered training.** `billbro_v3.onnx`
/ `models/grocery_yolov8.pt` cannot detect pepsi no matter how it's
retrained without new data — the class is currently undetectable at
checkout.

**Fix prepared, not yet retrained:** `BillBroAgain.ipynb` cell 3 (`DATASETS`)
now includes
[`project-pepsi/pepsi-can-detection-krjyn`](https://universe.roboflow.com/project-pepsi/pepsi-can-detection-krjyn)
— 202 images, single `pepsi` class, CC BY 4.0, spot-checked (consistent
single-instance annotations across sampled images). Cell 6
(`MANUAL_NAME_MAP`) has a matching entry. This needs a GPU to actually run
(Colab, per the notebook's original design) — rerun cells 3 → 4 → 6 → 8 →
10 (download → validate images → merge → train → evaluate) and confirm
pepsi's AP50 clears a reasonable bar before replacing
`models/grocery_yolov8.pt`. Not done in this session since this sandbox
has no GPU/torch.

## Secondary finding: `prices.json` was missing 3 of 6 model classes

`dragonfruit`, `custard_apple`, and `pepsi` had no price entry, so any
correct detection of those items would checkout at ₹0.00. Patched with
placeholder prices (₹180, ₹90, ₹40) — confirm with the team before pilot.

## New files

- **`predict.py`** — `GroceryDetector` (inference, matches old interface)
  + `StoreModelManager` (per-store model resolution, versioning,
  rollback — implements `models/{store_id}_v{N}.pt` / `_latest.pt`
  convention from the project spec).
- **`utils.py`** — cart/pricing/receipt helpers, rebuilt from `app.py`'s
  usage since no reference source existed.
- **`training.py`** — the "Add New Item" pipeline:
  - `auto_label_images()` — bootstraps bounding boxes for a new item's
    photos using class-agnostic detection (the model's box regressor,
    not its class head, since it's never seen the item).
  - `prepare_finetune_dataset()` — combines the new item with a replay
    sample of existing classes to reduce catastrophic forgetting.
  - `retrain_model()` — fine-tunes (backbone frozen, 5 epochs default),
    validates, and auto-deploys via `StoreModelManager` only if mAP50
    clears 0.80 — otherwise returns a "capture more images" reason.
  - Job status is mirrored to `models/jobs/{job_id}.json` so Person A's
    API layer can poll `GET /training/job/{job_id}` without needing to
    share process memory with a background thread.

All three files pass `py_compile`. `utils.py` and the non-YOLO logic in
`predict.py`/`training.py` (versioning, dataset assembly, class
remapping) were unit-tested in this session. **`GroceryDetector.detect()`
and `retrain_model()`'s actual YOLO training call are not yet
runtime-tested** — this sandbox has no `torch`/`ultralytics` install
(no network access). Run locally with your venv (note: `venv/` in this
repo is Mac-specific and won't work as-is in a fresh clone/CI — it's
symlinked to an absolute path) before merging:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Not yet done (next up)

- Verify `models/grocery_yolov8.pt` is actually the `billbro_v3` run's
  `best.pt` (file exists, untested in this session — no torch available).
- Fix the pepsi dataset gap and retrain.
- Model card (`Week 12` deliverable, per team brief) — not started.
- Inference speed benchmarking (<100ms target) — not started.
