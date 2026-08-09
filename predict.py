"""
predict.py — YOLOv8 detection wrapper for BillBro.

Owns two responsibilities:
  1. GroceryDetector    — loads a single .pt model and runs inference,
                           returning (name, confidence, bbox) tuples plus
                           an annotated image for display.
  2. StoreModelManager  — resolves which model file is "active" for a
                           given store, and tracks version history so
                           training.py can register newly fine-tuned
                           models without stepping on a store that's
                           mid-checkout.

Model naming convention (per project spec):
    models/{store_id}_v{N}.pt      — versioned store models
    models/{store_id}_latest.pt    — symlink/copy of the active version
    models/grocery_yolov8.pt       — fallback base model (no store_id)
"""

from __future__ import annotations

import base64
import json
import shutil
import time
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from ultralytics import YOLO

Detection = tuple[str, float, list[int]]  # (class_name, confidence, [x1, y1, x2, y2])


class GroceryDetector:
    """Loads a YOLOv8 .pt model once and runs repeated inference.

    Usage mirrors the original ONNX-based detector so app.py doesn't need
    to change: construct with a model path, call .detect() per frame.

    Attributes:
        model_path: Path to the .pt weights file.
        model: Loaded ultralytics.YOLO instance.
        class_names: dict[int, str] mapping class index to label.
    """

    def __init__(self, model_path: str) -> None:
        """Load a YOLOv8 model for inference.

        Args:
            model_path: Path to a .pt (PyTorch) model file. ONNX is not
                supported here — ONNX is inference-only and does not
                expose the training API training.py needs, so the whole
                project standardizes on .pt.

        Raises:
            FileNotFoundError: If model_path does not exist.
        """
        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(f"Model not found: {model_path}")

        self.model_path = str(path)
        self.model = YOLO(self.model_path)
        self.class_names: dict[int, str] = self.model.names

    def detect(
        self,
        image: np.ndarray,
        conf: float = 0.5,
        iou: float = 0.45,
    ) -> tuple[list[Detection], np.ndarray]:
        """Run detection on a single RGB image array.

        Args:
            image: RGB image as a numpy array (H, W, 3).
            conf: Confidence threshold — detections below this are dropped.
            iou: IoU threshold used for non-max suppression.

        Returns:
            A tuple of:
              - detections: list of (class_name, confidence, [x1,y1,x2,y2])
              - annotated: RGB numpy array with boxes/labels drawn on it
        """
        results = self.model.predict(
            source=image,
            conf=conf,
            iou=iou,
            verbose=False,
        )
        result = results[0]

        detections: list[Detection] = []
        for box in result.boxes:
            cls_id = int(box.cls[0])
            name = self.class_names.get(cls_id, f"class_{cls_id}")
            confidence = float(box.conf[0])
            x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
            detections.append((name, confidence, [x1, y1, x2, y2]))

        # result.plot() returns BGR; caller/app expects RGB throughout.
        annotated_bgr = result.plot()
        annotated = annotated_bgr[:, :, ::-1].copy()

        return detections, annotated

    def detect_generic(
        self,
        image: np.ndarray,
        conf: float = 0.15,
    ) -> list[list[int]]:
        """Class-agnostic detection — used by training.py for auto-labeling.

        When a brand-new item is being added, the model has never seen it
        and cannot classify it correctly. But YOLO's box regressor still
        tends to draw a box around *something* salient in frame, even if
        the class guess is wrong. We use the single highest-confidence box
        as a bounding-box proposal and let the caller assign the real label.

        Args:
            image: RGB image as a numpy array (H, W, 3).
            conf: Low threshold since we only need the objectness/box, not
                the (necessarily wrong) class prediction.

        Returns:
            The single best bounding box as [x1, y1, x2, y2], or an empty
            list if nothing was detected above threshold.
        """
        results = self.model.predict(source=image, conf=conf, verbose=False)
        boxes = results[0].boxes
        if len(boxes) == 0:
            return []

        best_idx = int(np.argmax(boxes.conf.cpu().numpy()))
        x1, y1, x2, y2 = (int(v) for v in boxes.xyxy[best_idx].tolist())
        return [x1, y1, x2, y2]

    def detect_from_base64(
        self,
        image_b64: str,
        confidence_threshold: float = 0.5,
    ) -> dict[str, Any]:
        """Run detection on a base64-encoded image — matches the confirmed
        `POST /detect` wire contract in API_CONTRACT.md exactly, so Person
        A's FastAPI handler can call this directly:

            @app.post("/detect")
            def detect(body: DetectRequest):
                return detector.detect_from_base64(
                    body.image, body.confidence_threshold or 0.5
                )

        Args:
            image_b64: Base64-encoded image bytes, WITHOUT a data-URL
                prefix (i.e. not "data:image/jpeg;base64,...", just the
                base64 payload itself — matches what frontend/src/api.js
                sends).
            confidence_threshold: Passed straight to detect()'s conf arg.

        Returns:
            {
                "detections": [
                    {"item_name": str, "confidence": float, "bbox": [x1,y1,x2,y2]},
                    ...
                ],
                "processing_time_ms": int,
            }
            One entry per detected object (raw, ungrouped) — the frontend's
            aggregateDetections() groups these into {item_name, confidence,
            quantity} before calling /checkout/bill. This function does not
            group; grouping is intentionally the caller's job per the
            contract.

        Raises:
            ValueError: If image_b64 cannot be decoded as an image.
        """
        start = time.perf_counter()

        try:
            image_bytes = base64.b64decode(image_b64)
            image_array = np.frombuffer(image_bytes, dtype=np.uint8)
            bgr_image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
            if bgr_image is None:
                raise ValueError("Decoded bytes are not a valid image")
            rgb_image = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)
        except Exception as e:
            raise ValueError(f"Could not decode base64 image: {e}") from e

        detections, _annotated = self.detect(rgb_image, conf=confidence_threshold)
        elapsed_ms = int((time.perf_counter() - start) * 1000)

        return {
            "detections": [
                {"item_name": name, "confidence": round(confidence, 4), "bbox": bbox}
                for name, confidence, bbox in detections
            ],
            "processing_time_ms": elapsed_ms,
        }


@dataclass
class ModelVersion:
    """Metadata for a single trained model version."""

    store_id: str
    version: str
    model_path: str
    metrics: dict[str, Any] = field(default_factory=dict)
    is_active: bool = False
    trained_at: str | None = None
    deployed_at: str | None = None


class StoreModelManager:
    """Resolves and tracks per-store model files and version history.

    Reads/writes a small JSON index (models/versions.json) so the API layer
    (Person A) and training pipeline (this file's owner, Person B) agree on
    which model is currently deployed for each store — without needing a
    database dependency in the ML code.
    """

    def __init__(self, models_dir: str = "models") -> None:
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.models_dir / "versions.json"

    def _load_index(self) -> dict[str, list[dict[str, Any]]]:
        if not self.index_path.exists():
            return {}
        with open(self.index_path) as f:
            return json.load(f)

    def _save_index(self, index: dict[str, list[dict[str, Any]]]) -> None:
        with open(self.index_path, "w") as f:
            json.dump(index, f, indent=2)

    def active_model_path(self, store_id: str) -> str:
        """Return the path to use for a given store, falling back sensibly.

        Resolution order:
          1. models/{store_id}_latest.pt  (an active fine-tuned model)
          2. models/grocery_yolov8.pt     (shared base model)

        Args:
            store_id: Store identifier, e.g. "store_001".

        Returns:
            Path to the model file to load.
        """
        store_specific = self.models_dir / f"{store_id}_latest.pt"
        if store_specific.exists():
            return str(store_specific)

        base = self.models_dir / "grocery_yolov8.pt"
        if base.exists():
            return str(base)

        raise FileNotFoundError(
            f"No model found for '{store_id}' and no base model at {base}"
        )

    def register_version(
        self,
        store_id: str,
        source_model_path: str,
        metrics: dict[str, Any],
        trained_at: str,
        deploy: bool = True,
    ) -> ModelVersion:
        """Register a newly trained model as a new version for a store.

        Copies source_model_path into models/{store_id}_v{N}.pt, updates
        the version index, and — if deploy=True — points
        {store_id}_latest.pt at the new version so the next checkout uses
        it.

        Args:
            store_id: Store identifier.
            source_model_path: Path to the freshly trained .pt weights
                (e.g. the output of a training.py run).
            metrics: Validation metrics dict, e.g. {"mAP50": 0.92}.
            trained_at: ISO timestamp string for when training finished.
            deploy: If True, also update the '_latest.pt' pointer.

        Returns:
            The ModelVersion record that was written to the index.
        """
        index = self._load_index()
        history = index.get(store_id, [])
        next_n = len(history) + 1
        version_str = f"v{next_n}"

        dest = self.models_dir / f"{store_id}_{version_str}.pt"
        shutil.copy(source_model_path, dest)

        record = ModelVersion(
            store_id=store_id,
            version=version_str,
            model_path=str(dest),
            metrics=metrics,
            is_active=deploy,
            trained_at=trained_at,
            deployed_at=trained_at if deploy else None,
        )

        if deploy:
            for h in history:
                h["is_active"] = False
            latest_path = self.models_dir / f"{store_id}_latest.pt"
            shutil.copy(dest, latest_path)

        history.append(record.__dict__)
        index[store_id] = history
        self._save_index(index)

        return record

    def list_versions(self, store_id: str) -> list[dict[str, Any]]:
        """Return version history for a store, newest last."""
        return self._load_index().get(store_id, [])

    def rollback(self, store_id: str, version: str) -> None:
        """Point {store_id}_latest.pt back at an earlier version.

        Args:
            store_id: Store identifier.
            version: Version string to roll back to, e.g. "v2".

        Raises:
            ValueError: If the version doesn't exist in history.
        """
        history = self.list_versions(store_id)
        match = next((h for h in history if h["version"] == version), None)
        if match is None:
            raise ValueError(f"No version '{version}' found for {store_id}")

        latest_path = self.models_dir / f"{store_id}_latest.pt"
        shutil.copy(match["model_path"], latest_path)

        index = self._load_index()
        for h in index[store_id]:
            h["is_active"] = h["version"] == version
        self._save_index(index)
