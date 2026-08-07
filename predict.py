

import cv2
import numpy as np
from pathlib import Path
from ultralytics import YOLO
from PIL import Image
import torch


# ─── Colour palette for bounding boxes ────────────────────────────────────────
COLORS = [
    (255, 87, 87),   (87, 196, 255),  (131, 255, 87),  (255, 196, 87),
    (196, 87, 255),  (87, 255, 196),  (255, 87, 196),  (87, 87, 255),
    (255, 165, 0),   (0, 200, 150),   (200, 100, 50),  (50, 150, 200),
]


class GroceryDetector:
    """
    YOLOv8-based grocery item detector.

    Usage:
        detector = GroceryDetector("models/grocery_yolov8.pt")
        results, annotated_img = detector.detect(image_array, conf=0.5)
    """

    def __init__(self, model_path: str, device: str = "auto"):
        self.model_path = Path(model_path)
        self.device = self._resolve_device(device)
        self.model = self._load_model()
        self.class_names = self.model.names   # {0: 'apple', 1: 'banana', ...}
        self.color_map = {
            cls_id: COLORS[i % len(COLORS)]
            for i, cls_id in enumerate(self.class_names)
        }

    # ── Private helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _resolve_device(device: str) -> str:
        if device == "auto":
            return "cuda" if torch.cuda.is_available() else "cpu"
        return device

    def _load_model(self) -> YOLO:
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Model not found at '{self.model_path}'. "
                "Train a model first with the Colab notebook."
            )
        model = YOLO(str(self.model_path))
        model.to(self.device)
        print(f"✅ Model loaded on {self.device} | {len(model.names)} classes")
        return model

    # ── Public API ─────────────────────────────────────────────────────────────

    def detect(
        self,
        image: np.ndarray,
        conf: float = 0.50,
        iou: float = 0.45,
        max_det: int = 50,
    ) -> tuple[list[tuple[str, float, list]], np.ndarray]:
        """
        Run inference on an image.

        Args:
            image      : RGB numpy array (H, W, 3)
            conf       : Confidence threshold (0–1)
            iou        : NMS IoU threshold
            max_det    : Maximum detections per image

        Returns:
            detections : list of (class_name, confidence, [x1,y1,x2,y2])
            annotated  : RGB numpy array with drawn boxes and labels
        """
        results = self.model(
            image,
            conf=conf,
            iou=iou,
            max_det=max_det,
            verbose=False,
        )

        detections = []
        annotated = image.copy()

        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                cls_id    = int(box.cls[0])
                conf_val  = float(box.conf[0])
                xyxy      = box.xyxy[0].tolist()        # [x1, y1, x2, y2]
                cls_name  = self.class_names[cls_id]

                detections.append((cls_name, conf_val, xyxy))
                annotated = self._draw_box(annotated, cls_name, conf_val, xyxy, cls_id)

        return detections, annotated

    def detect_pil(self, pil_image: Image.Image, **kwargs):
        """Convenience wrapper that accepts a PIL Image."""
        img_array = np.array(pil_image.convert("RGB"))
        detections, annotated_array = self.detect(img_array, **kwargs)
        return detections, Image.fromarray(annotated_array)

    # ── Drawing ────────────────────────────────────────────────────────────────

    def _draw_box(
        self,
        image: np.ndarray,
        label: str,
        conf: float,
        xyxy: list,
        cls_id: int,
    ) -> np.ndarray:
        """Draw a single bounding box with label on the image."""
        x1, y1, x2, y2 = map(int, xyxy)
        color = self.color_map[cls_id]
        display = f"{label.replace('_', ' ').title()}  {conf:.0%}"

        # Box
        cv2.rectangle(image, (x1, y1), (x2, y2), color, thickness=2)

        # Label background
        font_scale, thickness = 0.55, 1
        (tw, th), baseline = cv2.getTextSize(
            display, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness
        )
        label_y1 = max(y1 - th - baseline - 6, 0)
        cv2.rectangle(
            image,
            (x1, label_y1),
            (x1 + tw + 8, label_y1 + th + baseline + 6),
            color,
            thickness=-1,
        )

        # Label text (black for readability)
        cv2.putText(
            image,
            display,
            (x1 + 4, label_y1 + th + 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            (0, 0, 0),
            thickness,
            lineType=cv2.LINE_AA,
        )
        return image

    # ── Batch inference ────────────────────────────────────────────────────────

    def detect_batch(
        self, images: list[np.ndarray], conf: float = 0.50
    ) -> list[list[tuple]]:
        """Run inference on a list of images. Returns detections per image."""
        all_results = []
        for img in images:
            dets, _ = self.detect(img, conf=conf)
            all_results.append(dets)
        return all_results

    # ── Model info ─────────────────────────────────────────────────────────────

    def info(self) -> dict:
        return {
            "model_path": str(self.model_path),
            "device":     self.device,
            "classes":    self.class_names,
            "num_classes":len(self.class_names),
        }
