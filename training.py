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
# Replay pool — persistent, grows with every shelved item
# ─────────────────────────────────────────────────────────────────────────────

class ReplayPool:
    """Per-store replay buffer, used to fight catastrophic forgetting.

    Since "Add Item -> Train -> Shelve" is now the core loop (not a
    Week-4 add-on per BillBro_TeamUpdates.md), a store's class list grows
    one item at a time, indefinitely. A replay buffer that only knew about
    the original 6 base classes would stop protecting older *shelved*
    items the moment a second custom item gets added. This pool fixes
    that: every time an item is successfully shelved, a small sample of
    its own labeled images is added to the pool, so every future retrain
    replays ALL previously shelved classes, not just the original 6.

    On-disk layout:
        training_data/{store_id}/replay_pool/
            classes.json                — ordered list of class names
            {class_name}/images/*.jpg
            {class_name}/labels/*.txt   — YOLO format, class_id 0 always
                                           (this class's own local id;
                                           prepare_finetune_dataset()
                                           remaps to the current run's ids)
    """

    def __init__(self, store_id: str, base_dir: str = "training_data") -> None:
        self.store_id = store_id
        self.root = Path(base_dir) / store_id / "replay_pool"
        self.root.mkdir(parents=True, exist_ok=True)
        self.registry_path = self.root / "classes.json"

    def class_names(self) -> list[str]:
        """Ordered list of every class currently in the pool."""
        if not self.registry_path.exists():
            return []
        return json.loads(self.registry_path.read_text())["names"]

    def bootstrap_from_base(self, base_data_yaml: str, samples_per_class: int = 30) -> None:
        """One-time seed: sample the original base model's classes into the pool.

        No-op if the pool has already been bootstrapped (registry exists) —
        safe to call at the top of every retrain_model() run.

        Args:
            base_data_yaml: The base model's data.yaml.
            samples_per_class: How many images per base class to seed with.

        Raises:
            FileNotFoundError: If base_data_yaml's train/labels directory
                doesn't exist, or exists but contributes zero images to
                every class. This used to fail silently — it would still
                write the registry with an empty pool, which permanently
                (registry-exists = no-op on every future call) disables
                catastrophic-forgetting protection for this store without
                any error surfacing anywhere. Loud failure here is much
                cheaper than a silently-broken replay pool discovered
                weeks later.
        """
        if self.registry_path.exists():
            return

        with open(base_data_yaml) as f:
            base_cfg = yaml.safe_load(f)

        base_names: list[str] = list(base_cfg["names"])
        base_root = Path(base_cfg["path"])
        base_train_images = base_root / base_cfg["train"]
        base_train_labels = base_train_images.parent / "labels"

        if not base_train_labels.exists():
            raise FileNotFoundError(
                f"ReplayPool.bootstrap_from_base: labels directory "
                f"{base_train_labels} does not exist (resolved from "
                f"base_data_yaml={base_data_yaml!r}, path={base_cfg.get('path')!r}, "
                f"train={base_cfg.get('train')!r}). The base model's actual "
                f"training images/labels need to be present at this path on "
                f"whichever machine runs retrain_model() — a data.yaml file "
                f"alone isn't enough, it has to resolve to real files."
            )

        by_class: dict[int, list[Path]] = {i: [] for i in range(len(base_names))}
        for label_file in base_train_labels.glob("*.txt"):
            lines = label_file.read_text().splitlines()
            if not lines:
                continue
            cls_id = int(lines[0].split()[0])
            if cls_id in by_class:
                by_class[cls_id].append(label_file)

        if not any(by_class.values()):
            raise FileNotFoundError(
                f"ReplayPool.bootstrap_from_base: {base_train_labels} exists "
                f"but contributed zero usable images to any class — check "
                f"that label files there actually have class ids matching "
                f"base_data_yaml's names list ({base_names})."
            )

        for cls_id, name in enumerate(base_names):
            label_files = by_class.get(cls_id, [])
            sample = random.sample(label_files, min(samples_per_class, len(label_files)))
            self._write_class_samples(name, [
                (self._sibling_image(lf, base_train_images), lf) for lf in sample
            ], remap_class_id=0)

        self.registry_path.write_text(json.dumps({"names": base_names}, indent=2))

    def add_class_samples(
        self,
        item_name: str,
        labeled_images_dir: str,
        sample_size: int = 15,
    ) -> None:
        """Add a sample of a newly shelved item's own images to the pool.

        Call this once retrain_model() has confirmed the new item cleared
        the accuracy threshold — future retrains will now replay it too.

        Args:
            item_name: The class name to register (idempotent — if it's
                already in the pool, its samples are refreshed).
            labeled_images_dir: The auto_label_images() output dir for
                this item (has images/ and labels/, class_id 0 throughout).
            sample_size: How many of this item's images to keep long-term.
        """
        src = Path(labeled_images_dir)
        images = sorted((src / "images").glob("*"))
        sample = random.sample(images, min(sample_size, len(images)))
        pairs = [(img, src / "labels" / f"{img.stem}.txt") for img in sample]
        self._write_class_samples(item_name, pairs, remap_class_id=0)

        names = self.class_names()
        if item_name not in names:
            names.append(item_name)
            self.registry_path.write_text(json.dumps({"names": names}, indent=2))

    def sample_for_replay(
        self,
        exclude: str | None = None,
        per_class: int = OLD_CLASS_SAMPLES_PER_CLASS,
    ) -> dict[str, list[tuple[Path, Path]]]:
        """Return a sample of (image_path, label_path) pairs per pooled class.

        Args:
            exclude: Class name to skip (typically the item currently
                being trained, to avoid double-counting it).
            per_class: Max images to return per class.

        Returns:
            {class_name: [(image_path, label_path), ...]}
        """
        result: dict[str, list[tuple[Path, Path]]] = {}
        for name in self.class_names():
            if name == exclude:
                continue
            class_dir = self.root / name
            images = sorted((class_dir / "images").glob("*"))
            sample = random.sample(images, min(per_class, len(images)))
            result[name] = [
                (img, class_dir / "labels" / f"{img.stem}.txt") for img in sample
            ]
        return result

    def _write_class_samples(
        self,
        class_name: str,
        pairs: list[tuple[Path, Path]],
        remap_class_id: int,
    ) -> None:
        class_dir = self.root / class_name
        (class_dir / "images").mkdir(parents=True, exist_ok=True)
        (class_dir / "labels").mkdir(parents=True, exist_ok=True)
        for img_path, label_path in pairs:
            if img_path is None or not label_path.exists():
                continue
            shutil.copy(img_path, class_dir / "images" / img_path.name)
            lines = []
            for line in label_path.read_text().splitlines():
                parts = line.split()
                if len(parts) < 5:
                    continue
                lines.append(" ".join([str(remap_class_id), *parts[1:]]))
            (class_dir / "labels" / f"{img_path.stem}.txt").write_text("\n".join(lines) + "\n")

    @staticmethod
    def _sibling_image(label_path: Path, images_dir: Path) -> Path | None:
        candidates = list(images_dir.glob(f"{label_path.stem}.*"))
        return candidates[0] if candidates else None


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — Dataset assembly (new item + replay sample of ALL shelved classes)
# ─────────────────────────────────────────────────────────────────────────────

def prepare_finetune_dataset(
    item_name: str,
    auto_labeled_dir: str,
    replay_pool: "ReplayPool",
    output_dir: str,
    samples_per_old_class: int = OLD_CLASS_SAMPLES_PER_CLASS,
    val_holdout: int = 3,
) -> str:
    """Assemble a small YOLO dataset: the new item + a replay sample of
    every previously shelved class (base classes + any custom items added
    since).

    Fine-tuning on ONLY the new item's images would let the model forget
    everything shelved before it (catastrophic forgetting) — confirmed as
    the recommended MVP strategy in BillBro_TeamUpdates.md. This pulls the
    replay sample from `replay_pool`, which grows every time an item is
    successfully shelved (see ReplayPool.add_class_samples), rather than
    a fixed one-time base dataset.

    Args:
        item_name: The new item's class name.
        auto_labeled_dir: Output of auto_label_images() — has images/ and
            labels/ subdirs, with placeholder class_id 0 in every label.
        replay_pool: A ReplayPool already bootstrapped for this store.
        output_dir: Where to write the merged dataset.
        samples_per_old_class: How many images per old class to replay.
        val_holdout: How many of the new item's own images to hold out
            for validation (rest go to train).

    Returns:
        Path to the newly written data.yaml for this fine-tune run.

    Raises:
        ValueError: If auto_labeled_dir has fewer images than val_holdout + 1
            (nothing left to train on after the validation split).
    """
    old_names = replay_pool.class_names()
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

    # ── Replay buffer: pull a sample of every previously shelved class
    replayed = 0
    replay_samples = replay_pool.sample_for_replay(exclude=item_name, per_class=samples_per_old_class)
    for cls_id, name in enumerate(old_names):
        for img_path, label_path in replay_samples.get(name, []):
            if not label_path.exists():
                continue
            shutil.copy(img_path, out / "train" / "images" / img_path.name)
            lines = []
            for line in label_path.read_text().splitlines():
                parts = line.split()
                if len(parts) < 5:
                    continue
                # Pool stores everything as local class_id 0 -> remap to
                # this run's actual id for `name`.
                lines.append(" ".join([str(cls_id), *parts[1:]]))
            (out / "train" / "labels" / f"{img_path.stem}.txt").write_text(
                "\n".join(lines) + "\n"
            )
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
        f"{len(val_imgs)} val images, {replayed} replayed images across "
        f"{len(old_names)} previously shelved classes."
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
    item_id: int | str | None = None,
) -> dict[str, Any]:
    """Full pipeline: auto-label -> assemble dataset -> fine-tune -> validate -> shelve.

    Implements the "Add Item -> Train -> Shelve" loop from
    BillBro_TeamUpdates.md — this is the core feature now, not a Week-4
    add-on. Two build-order decisions from that doc are resolved here
    (see CONTEXT_FOR_PERSON_A.md for the write-up):
      - Cumulative fine-tuning: always starts from the store's current
        active model (via StoreModelManager), not fresh from base_model.pt
        each time. Faster, and the replay pool (below) controls forgetting.
      - Automatic shelving: this function IS the gate — "success" means
        "clear to shelve", "failed" means stay in "training"/"failed"
        status. No separate manual-confirm step is assumed on the ML side.

    Mirrors Person A's TrainingJob table shape (id, item_id, status,
    progress, current_epoch, metrics, error_message, created_at,
    completed_at) via the job status file, if job_id is given — an API
    layer can poll read_job_status(job_id) independently of this
    function's return value (useful when called from a background thread).

    Args:
        store_id: Store identifier, e.g. "store_001".
        item_name: New item's class name (lowercase, underscored).
        image_paths: Paths to the staff-captured photos of the new item.
        base_data_yaml: data.yaml describing the base model's classes —
            only used to bootstrap the replay pool the first time a store
            trains anything; ignored on every call after that.
        models_dir: Where StoreModelManager and ReplayPool keep state.
        work_dir: Scratch space for auto-labeling and dataset assembly.
        epochs: Fine-tune epochs (default 5, per 15-min latency target).
        freeze: Number of leading layers to freeze (backbone), reducing
            both training time and catastrophic forgetting risk.
        accuracy_threshold: Minimum mAP50 to shelve; below this, the item
            stays unshelved and the run reports why.
        job_id: Optional job id for status file mirroring.
        item_id: Optional item id (Person A's Item.id) — threaded through
            to the job status file so GET /training/job/{job_id} can join
            back to the item without a name lookup.

    Returns:
        On success:
          {"status": "success", "store_id", "item_name", "item_id",
           "version", "metrics": {...}, "model_path": str}
        On failure:
          {"status": "failed", "reason": str, "metrics": {...} | None}
    """
    manager = StoreModelManager(models_dir=models_dir)
    current_model_path = manager.active_model_path(store_id)

    pool = ReplayPool(store_id, base_dir=str(Path(models_dir) / ".." / "training_data"))
    pool.bootstrap_from_base(base_data_yaml)

    _update_job(job_id, status="running", progress=5, stage="auto_labeling", item_id=item_id)

    detector = GroceryDetector(current_model_path)
    label_dir = str(Path(work_dir) / f"{store_id}_{item_name}_labels")
    labeling_result = auto_label_images(image_paths, detector, item_name, label_dir)

    if len(labeling_result["labeled"]) < 5:
        _update_job(job_id, status="failed", progress=10, item_id=item_id,
                     error_message="Too few usable images after auto-labeling")
        return {
            "status": "failed",
            "reason": (
                f"Only {len(labeling_result['labeled'])} of "
                f"{len(image_paths)} images produced a usable bounding box. "
                "Retake photos: plain background, item centered, good lighting."
            ),
            "metrics": None,
        }

    _update_job(job_id, status="running", progress=25, stage="dataset_prep", item_id=item_id)

    dataset_dir = str(Path(work_dir) / f"{store_id}_{item_name}_dataset")
    data_yaml_path = prepare_finetune_dataset(
        item_name=item_name,
        auto_labeled_dir=labeling_result["output_dir"],
        replay_pool=pool,
        output_dir=dataset_dir,
    )

    _update_job(job_id, status="running", progress=35, stage="training",
                current_epoch=f"0/{epochs}", item_id=item_id)

    model = YOLO(current_model_path)
    run_name = f"{store_id}_{item_name}_{_timestamp_slug()}"
    train_results = model.train(
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

    _update_job(job_id, status="running", progress=85, stage="validating", item_id=item_id)

    # Don't reconstruct where YOLO saved the run — ask it directly via
    # train_results.save_dir. Manually rebuilding this path as
    # `Path(work_dir) / "runs" / run_name / ...` broke on ultralytics
    # 8.4.116: that version silently nests a relative `project` path
    # under its own `runs/<task>/` directory (here:
    # "<cwd>/runs/detect/training_runs/runs/<run_name>/weights/best.pt"
    # instead of the literal "training_runs/runs/<run_name>/weights/best.pt"
    # this used to assume), so the reconstructed path pointed at a
    # directory that never existed and crashed with a bare
    # FileNotFoundError right after validation had already run
    # successfully. save_dir is what ultralytics itself actually used,
    # so this is correct regardless of how any given version resolves
    # relative project paths.
    best_weights = Path(train_results.save_dir) / "weights" / "best.pt"
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
                     item_id=item_id,
                     error_message=f"mAP50 {map50:.2f} below threshold {accuracy_threshold:.2f}")
        return {
            "status": "failed",
            "reason": (
                f"mAP50 {map50:.2f} is below the {accuracy_threshold:.2f} "
                f"shelving threshold. Capture 30+ more images of '{item_name}' "
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

    # Item cleared the bar — add it to the replay pool so it's protected
    # in every future retrain, then it's clear to shelve.
    pool.add_class_samples(item_name, labeling_result["output_dir"])

    _update_job(job_id, status="success", progress=100, metrics=result_metrics,
                item_id=item_id, model_version=version_record.version,
                completed_at=datetime.now(timezone.utc).isoformat())

    return {
        "status": "success",
        "store_id": store_id,
        "item_name": item_name,
        "item_id": item_id,
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
    """Mirrors Person A's TrainingJob table columns exactly (see
    BillBro_TeamUpdates.md): id, item_id, status, progress, current_epoch,
    metrics, error_message, created_at, completed_at. `job_id` maps to
    their `id`; `stage` and `model_version` are extras beyond that table,
    harmless to ignore if unused.
    """

    job_id: str
    status: str = "pending"  # pending | running | success | failed
    progress: int = 0
    item_id: int | str | None = None
    stage: str | None = None  # extra: auto_labeling | dataset_prep | training | validating
    current_epoch: str | None = None
    metrics: dict[str, Any] | None = None
    error_message: str | None = None
    model_version: str | None = None  # extra: set once shelved
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: str | None = None
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def _jobs_dir(models_dir: str = "models") -> Path:
    d = Path(models_dir) / "jobs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _update_job(job_id: str | None, **fields: Any) -> None:
    """Write/merge job status to models/jobs/{job_id}.json. No-op if job_id is None.

    Field names match JobStatus / Person A's TrainingJob table. `created_at`
    is set once on the job's first write and never overwritten;
    `updated_at` changes on every call; `completed_at` is left untouched
    unless the caller explicitly passes it (i.e. on success/failure).
    """
    if job_id is None:
        return
    path = _jobs_dir() / f"{job_id}.json"
    existing = {}
    is_new = not path.exists()
    if not is_new:
        existing = json.loads(path.read_text())

    existing.update({k: v for k, v in fields.items() if v is not None})
    existing["job_id"] = job_id
    if is_new:
        existing["created_at"] = datetime.now(timezone.utc).isoformat()
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
