# YOLOv8m Training Results — `billbro_v3_best.pt`

Extracted directly from the real cell 10 training/validation log (not
copy-pasted from a template) — see below for why that distinction
mattered this time.

## Run config

- Model: YOLOv8m, pretrained (`yolov8m.pt`), 25.86M params
- Epochs: 50, imgsz 640, batch 32, AdamW (lr0=0.001)
- Device: Colab, Tesla T4 (CUDA), `ultralytics` 8.4.116
- Data: `/content/merged_dataset/data.yaml` — **this run was on Colab**,
  not Jupyter, despite the earlier plan to move training locally.
  Worked fine (2.39 hrs for 50 epochs on the T4), just flagging the
  environment doesn't match the stated plan.
- Train: 4,689 images / 39 backgrounds (4,728 total). Val: 368 images /
  4 backgrounds (372 total).

## Overall (on val set)

| Metric | Value |
|---|---|
| Precision | 0.965 |
| Recall | 0.930 |
| mAP50 | **0.956** |
| mAP50-95 | 0.789 |
| Inference speed | 12.3ms/image (GPU) |

## Per-class (real numbers, from `results_dict`/`maps` in the checkpoint's own log)

| Class | Val instances | Precision | Recall | AP50 | AP50-95 |
|---|---|---|---|---|---|
| apple | 201 | 0.985 | 1.000 | 0.995 | 0.921 |
| banana | 412 | 0.988 | 0.994 | 0.994 | 0.889 |
| dragonfruit | 148 | 0.976 | 0.939 | 0.981 | 0.928 |
| custard_apple | 205 | 0.998 | 0.995 | 0.995 | 0.906 |
| diet_coke | 31 | 0.897 | 0.871 | 0.889 | 0.510 |
| **pepsi** | 50 | 0.944 | 0.780 | **0.885** | 0.579 |

## Pepsi is fixed

AP50 went from **0.000 → 0.885**. The class exists as its own trained
label now (confirmed independently from the `.pt`'s weights before this
log was even available) and the numbers back it up — precision 0.944
means when it says "pepsi" it's right 94% of the time; recall 0.780
means it'll still miss roughly 1 in 5 real pepsi cans, likely due to the
smaller sample (50 val instances vs 200-400 for the fruit classes) and
real-world angle/lighting variation the training set didn't fully cover.
Worth capturing more pepsi photos in a future retrain if checkout misses
turn out to be common in practice, but this is a real, working class now
— not the "detect as diet_coke" workaround suggested when it was broken.

**Correction to `PERSON_B_NEXT_STEPS.md`:** that doc's per-class table
listed `pepsi: AP50 = 0.00` with the old "generic soda-can, not real
Pepsi" explanation. That was stale — copied from the previous broken
run's template and never updated for this one. The real log (above)
shows the fix worked. Flagging so nobody reads that doc and assumes
Pepsi is still broken.

## Weakest class: diet_coke

Lowest AP50-95 (0.510) despite a solid AP50 (0.889) — the gap between
those two usually means boxes are landing in roughly the right place
(good at IoU 0.5) but not tightly (worse at stricter IoU). Also has the
smallest val set (31 instances) of any class, so this number carries
more uncertainty than the others. Not a blocker, just the one to watch
if checkout accuracy complaints come in.

## Status

Model verified from real training output (not just structurally, this
time) and swapped into `models/grocery_yolov8.pt` + `billbro_v3.pt`,
checksums confirmed matching the upload. `classes.json` unchanged (same
6 classes, same order) — no remapping needed.
