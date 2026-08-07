"""
training.py — Auto-labeling + fine-tuning pipeline for adding new items.

This is the "Add New Item" feature's ML core (Scenario 2 in the project
brief). It does NOT run a web server or job queue — Person A's API layer
owns that. Instead it exposes plain functions plus a small file-based job
status tracker (models/jobs/{job_id}.json) that Person A's threading/async
layer can poll to satisfy:

    POST /training/upload_images   -> calls run_training_job() in a thread
    GET  /training/job/{job_id}    -> reads read_job_status(job_id)

Pipeline for a new item:
  1. auto_label_images()     — bootstrap bounding boxes for the new item's
                                 photos using class-agnostic detection
                                 (the base model has never seen this item,
                                 so we can't trust its class prediction —
                                 only its box regressor).
  2. prepare_finetune_dataset() — combine the new item's labeled images
                                 with a small sample of existing classes'
                                 images, so fine-tuning doesn't erase what
                                 the model already knows (catastrophic
                                 forgetting).
  3. retrain_model()         — fine-tune from the store's current model,
                                 freezing early (backbone) layers, validate,
                                 and only deploy if accuracy clears the bar.

Target latency per project spec: ~15 min on GPU (5 epochs), ~1 hr on CPU.
"""

from __future__ import annotations

import json
import random
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from PIL import Image
from ultralytics import YOLO

from predict import GroceryDetector, StoreModelManager

DEFAULT_ACCURACY_THRESHOLD = 0.80  # mAP50; below this, ask staff for more images
DEFAULT_EPOCHS = 5
DEFAULT_FREEZE_LAYERS = 10  # freeze backbone, fine-tune head only
OLD_CLASS_SAMPLES_PER_CLASS = 30  # replay buffer to avoid forgetting


# ─────────────────────────────────────────────────────────────────────────────
# Step 1 — Auto-labeling
# ─────────────────────────────────────────────────────────────────────────────

def auto_label_images(
    image_paths: list[str],
    detector: GroceryDetector,
    item_name: str,
    output_dir: str,
    min_box_area_frac: float = 0.02,
) -> dict[str, Any]:
    """Bootstrap YOLO-format labels for a brand-new item's photos.

    The base/store model has never seen `item_name`, so its class
    prediction is meaningless here. What we can trust is its box
    regressor: run class-agnostic detection (detector.detect_generic) to
    find "the salient object in frame", and assign it item_name directly,
    since staff photographed exactly one item per shot.

    Images where no confident box is found are skipped and reported —
    those need a retake (better lighting / plain background / item more
    centered).

    Args:
        image_paths: Paths to the staff-captured photos (typically 15).
        detector: A GroceryDetector loaded with the store's CURRENT model
            (used only for its box regressor, not its class head).
        item_name: The new item's label, e.g. "maggi_noodles". Should
            already be lowercase/underscored by the caller.
        output_dir: Directory to write auto_label_images/ + labels/ into.
        min_box_area_frac: Discard boxes smaller than this fraction of
            image area — usually noise, not the actual item.

    Returns:
        {
            "item_name": str,
            "labeled": [{"image_path": str, "bbox_coordinates": [[x1,y1,x2,y2]]}],
            "skipped": [str],   # image paths with no usable detection
            "output_dir": str,
        }
    """
    out = Path(output_dir)
    (out / "images").mkdir(parents=True, exist_ok=True)
    (out / "labels").mkdir(parents=True, exist_ok=True)

    labeled: list[dict[str, Any]] = []
    skipped: list[str] = []

    for i, img_path in enumerate(image_paths):
        with Image.open(img_path) as im:
            w, h = im.size

        bbox = detector.detect_generic(_load_rgb(img_path))
        if not bbox:
            skipped.append(img_path)
            continue

        x1, y1, x2, y2 = bbox
        area_frac = ((x2 - x1) * (y2 - y1)) / (w * h)
        if area_frac < min_box_area_frac:
            skipped.append(img_path)
            continue

        dest_name = f"{item_name}_{i:03d}.jpg"
        dest_img = out / "images" / dest_name
        shutil.copy(img_path, dest_img)

        # YOLO label format: class_id x_center y_center width height (normalized)
        xc = ((x1 + x2) / 2) / w
        yc = ((y1 + y2) / 2) / h
        bw = (x2 - x1) / w
        bh = (y2 - y1) / h
        label_path = out / "labels" / f"{item_name}_{i:03d}.txt"
        # class_id 0 is a placeholder here — prepare_finetune_dataset()
        # remaps it to the item's real new class index once that's known.
        label_path.write_text(f"0 {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}\n")

        labeled.append({
            "image_path": str(dest_img),
            "bbox_coordinates": [[x1, y1, x2, y2]],
        })

    return {
        "item_name": item_name,
        "labeled": labeled,
        "skipped": skipped,
        "output_dir": str(out),
    }


def _load_rgb(image_path: str):
    """Load an image file as an RGB numpy array."""
    import cv2
    import numpy as np

    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Could not read image: {image_path}")
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — Dataset assembly (new item + replay sample of old classes)
# ─────────────────────────────────────────────────────────────────────────────

def prepare_finetune_dataset(
    item_name: str,
    auto_labeled_dir: str,
    base_data_yaml: str,
    output_dir: str,
    samples_per_old_class: int = OLD_CLASS_SAMPLES_PER_CLASS,
    val_holdout: int = 3,
) -> str:
    """Assemble a small YOLO dataset combining the new item with old classes.

    Fine-tuning on ONLY the new item's images would let the model forget
    the other 6 classes (catastrophic forgetting). We counter this with a
    replay buffer: a random sample of each existing class's training
    images, copied in alongside the new item.

    Args:
        item_name: The new item's class name.
        auto_labeled_dir: Output of auto_label_images() — has images/ and
            labels/ subdirs, with placeholder class_id 0 in every label.
        base_data_yaml: The base model's data.yaml (has the old classes'
            train/images path and names list).
        output_dir: Where to write the merged dataset.
        samples_per_old_class: How many old-class images to replay.
        val_holdout: How many of the new item's own images to hold out
            for validation (rest go to train).

    Returns:
        Path to the newly written data.yaml for this fine-tune run.

    Raises:
        ValueError: If auto_labeled_dir has fewer images than val_holdout + 1
            (nothing left to train on after the validation split).
    """
    with open(base_data_yaml) as f:
        base_cfg = yaml.safe_load(f)

    old_names: list[str] = list(base_cfg["names"])
    new_class_id = len(old_names)
    all_names = old_names + [item_name]

    out = Path(output_dir)
    for split in ("train", "valid"):
        (out / split / "images").mkdir(parents=True, exist_ok=True)
        (out / split / "labels").mkdir(parents=True, exist_ok=True)

    # ── New item's own images: remap class_id 0 -> new_class_id, split train/val
    src = Path(auto_labeled_dir)
    new_images = sorted((src / "images").glob("*"))
    if len(new_images) <= val_holdout:
        raise ValueError(
            f"Only {len(new_images)} labeled images for '{item_name}' — "
            f"need more than {val_holdout} (val_holdout) to train at all."
        )

    random.shuffle(new_images)
    val_imgs = new_images[:val_holdout]
    train_imgs = new_images[val_holdout:]

    for split, imgs in (("train", train_imgs), ("valid", val_imgs)):
        for img_path in imgs:
            label_path = src / "labels" / f"{img_path.stem}.txt"
            shutil.copy(img_path, out / split / "images" / img_path.name)

            remapped_lines = []
            for line in label_path.read_text().splitlines():
                parts = line.split()
                if len(parts) < 5:
                    continue
                remapped_lines.append(" ".join([str(new_class_id), *parts[1:]]))
            (out / split / "labels" / f"{img_path.stem}.txt").write_text(
                "\n".join(remapped_lines) + "\n"
            )

    # ── Replay buffer: sample old classes from the base dataset's train split
    base_root = Path(base_cfg["path"])
    base_train_images = base_root / base_cfg["train"]
    base_train_labels = base_train_images.parent / "labels"

    by_class: dict[int, list[Path]] = {i: [] for i in range(len(old_names))}
    if base_train_labels.exists():
        for label_file in base_train_labels.glob("*.txt"):
            first_line = label_file.read_text().splitlines()
            if not first_line:
                continue
            cls_id = int(first_line[0].split()[0])
            if cls_id in by_class:
                by_class[cls_id].append(label_file)

    replayed = 0
    for cls_id, label_files in by_class.items():
        sample = random.sample(label_files, min(samples_per_old_class, len(label_files)))
        for label_file in sample:
            img_candidates = list(base_train_images.glob(f"{label_file.stem}.*"))
            if not img_candidates:
                continue
            img_path = img_candidates[0]
            shutil.copy(img_path, out / "train" / "images" / img_path.name)
            shutil.copy(label_file, out / "train" / "labels" / label_file.name)
            replayed += 1

    data_yaml_path = out / "data.yaml"
    with open(data_yaml_path, "w") as f:
        yaml.dump({
            "path": str(out),
            "train": "train/images",
            "val": "valid/images",
            "nc": len(all_names),
            "names": all_names,
        }, f, default_flow_style=False)

    print(
        f"Dataset ready: {len(train_imgs)} new-item train images, "
        f"{len(val_imgs)} val images, {replayed} replayed old-class images "
        f"across {len(old_names)} classes."
    )

    return str(data_yaml_path)


# ─────────────────────────────────────────────────────────────────────────────
# Step 3 — Fine-tune, validate, conditionally deploy
# ─────────────────────────────────────────────────────────────────────────────

def retrain_model(
    store_id: str,
    item_name: str,
    image_paths: list[str],
    base_data_yaml: str,
    models_dir: str = "models",
    work_dir: str = "training_runs",
    epochs: int = DEFAULT_EPOCHS,
    freeze: int = DEFAULT_FREEZE_LAYERS,
    accuracy_threshold: float = DEFAULT_ACCURACY_THRESHOLD,
    job_id: str | None = None,
) -> dict[str, Any]:
    """Full pipeline: auto-label -> assemble dataset -> fine-tune -> validate -> deploy.

    Mirrors the API contract in the project spec's GET /training/job/{job_id}:
    returns {"status": "success", ...} or {"status": "failed", "reason": ...}.
    If job_id is given, progress is also mirrored to
    models/jobs/{job_id}.json so an API layer can poll it independently of
    this function's return value (useful when called from a background
    thread).

    Args:
        store_id: Store identifier, e.g. "store_001".
        item_name: New item's class name (lowercase, underscored).
        image_paths: Paths to the staff-captured photos of the new item.
        base_data_yaml: data.yaml describing the store's current classes.
        models_dir: Where StoreModelManager reads/writes versioned models.
        work_dir: Scratch space for auto-labeling and dataset assembly.
        epochs: Fine-tune epochs (default 5, per 15-min latency target).
        freeze: Number of leading layers to freeze (backbone), reducing
            both training time and catastrophic forgetting risk.
        accuracy_threshold: Minimum mAP50 to auto-deploy; below this,
            the run fails and asks for more images instead of shipping a
            weak model.
        job_id: Optional job id for status file mirroring.

    Returns:
        On success:
          {"status": "success", "store_id", "item_name", "version",
           "metrics": {...}, "model_path": str}
        On failure:
          {"status": "failed", "reason": str, "metrics": {...} | None}
    """
    manager = StoreModelManager(models_dir=models_dir)
    current_model_path = manager.active_model_path(store_id)

    _update_job(job_id, status="running", progress=5, stage="auto_labeling")

    detector = GroceryDetector(current_model_path)
    label_dir = str(Path(work_dir) / f"{store_id}_{item_name}_labels")
    labeling_result = auto_label_images(image_paths, detector, item_name, label_dir)

    if len(labeling_result["labeled"]) < 5:
        _update_job(job_id, status="failed", progress=10,
                     reason="Too few usable images after auto-labeling")
        return {
            "status": "failed",
            "reason": (
                f"Only {len(labeling_result['labeled'])} of "
                f"{len(image_paths)} images produced a usable bounding box. "
                "Retake photos: plain background, item centered, good lighting."
            ),
            "metrics": None,
        }

    _update_job(job_id, status="running", progress=25, stage="dataset_prep")

    dataset_dir = str(Path(work_dir) / f"{store_id}_{item_name}_dataset")
    data_yaml_path = prepare_finetune_dataset(
        item_name=item_name,
        auto_labeled_dir=labeling_result["output_dir"],
        base_data_yaml=base_data_yaml,
        output_dir=dataset_dir,
    )

    _update_job(job_id, status="running", progress=35, stage="training", epoch=f"0/{epochs}")

    model = YOLO(current_model_path)
    run_name = f"{store_id}_{item_name}_{_timestamp_slug()}"
    model.train(
        data=data_yaml_path,
        epochs=epochs,
        freeze=freeze,
        imgsz=640,
        patience=3,
        project=str(Path(work_dir) / "runs"),
        name=run_name,
        exist_ok=True,
        verbose=False,
        # Conservative augmentation — small dataset, don't distort the
        # one real item class further than necessary.
        mosaic=0.3,
        mixup=0.0,
        copy_paste=0.0,
    )

    _update_job(job_id, status="running", progress=85, stage="validating")

    best_weights = Path(work_dir) / "runs" / run_name / "weights" / "best.pt"
    val_model = YOLO(str(best_weights))
    metrics = val_model.val(data=data_yaml_path, imgsz=640, verbose=False)

    map50 = float(metrics.box.map50)
    map_all = float(metrics.box.map)
    per_class_ap = _per_class_ap(val_model, metrics)

    result_metrics = {
        "mAP50": round(map50, 4),
        "mAP50-95": round(map_all, 4),
        "precision": round(float(metrics.box.mp), 4),
        "recall": round(float(metrics.box.mr), 4),
        "per_class_AP50": per_class_ap,
        "epochs": epochs,
        "new_item_train_images": len(labeling_result["labeled"]),
    }

    if map50 < accuracy_threshold:
        _update_job(job_id, status="failed", progress=100, metrics=result_metrics,
                     reason=f"mAP50 {map50:.2f} below threshold {accuracy_threshold:.2f}")
        return {
            "status": "failed",
            "reason": (
                f"mAP50 {map50:.2f} is below the {accuracy_threshold:.2f} "
                f"deploy threshold. Capture 30+ more images of '{item_name}' "
                "and retry — auto-labeling from a single-item frame works "
                "best with varied angles and backgrounds."
            ),
            "metrics": result_metrics,
        }

    version_record = manager.register_version(
        store_id=store_id,
        source_model_path=str(best_weights),
        metrics=result_metrics,
        trained_at=datetime.now(timezone.utc).isoformat(),
        deploy=True,
    )

    _update_job(job_id, status="success", progress=100, metrics=result_metrics,
                model_version=version_record.version)

    return {
        "status": "success",
        "store_id": store_id,
        "item_name": item_name,
        "version": version_record.version,
        "metrics": result_metrics,
        "model_path": version_record.model_path,
    }


def _per_class_ap(model: YOLO, metrics: Any) -> dict[str, float]:
    """Extract per-class AP50 as a plain dict for the training-job payload."""
    names = list(model.names.values())
    ap50 = getattr(metrics.box, "ap50", [])
    return {
        names[i]: round(float(ap50[i]), 4)
        for i in range(min(len(names), len(ap50)))
    }


def _timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


# ─────────────────────────────────────────────────────────────────────────────
# Job status file — bridge to Person A's API layer (GET /training/job/{id})
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class JobStatus:
    job_id: str
    status: str = "pending"  # pending | running | success | failed
    progress: int = 0
    stage: str | None = None
    epoch: str | None = None
    metrics: dict[str, Any] | None = None
    reason: str | None = None
    model_version: str | None = None
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def _jobs_dir(models_dir: str = "models") -> Path:
    d = Path(models_dir) / "jobs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _update_job(job_id: str | None, **fields: Any) -> None:
    """Write/merge job status to models/jobs/{job_id}.json. No-op if job_id is None."""
    if job_id is None:
        return
    path = _jobs_dir() / f"{job_id}.json"
    existing = {}
    if path.exists():
        existing = json.loads(path.read_text())
    existing.update({k: v for k, v in fields.items() if v is not None})
    existing["job_id"] = job_id
    existing["updated_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(existing, indent=2))


def read_job_status(job_id: str, models_dir: str = "models") -> dict[str, Any]:
    """Read back a training job's current status — for GET /training/job/{job_id}.

    Args:
        job_id: The job identifier passed to retrain_model().
        models_dir: Same models_dir the job was run with.

    Returns:
        The job status dict, or {"status": "unknown"} if no such job exists.
    """
    path = _jobs_dir(models_dir) / f"{job_id}.json"
    if not path.exists():
        return {"status": "unknown", "job_id": job_id}
    return json.loads(path.read_text())
