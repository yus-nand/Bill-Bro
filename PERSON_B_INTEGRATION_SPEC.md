# Person B Integration Specification - Detection & Training Pipeline

Person A (Backend) → Person B (ML) → Person C (Frontend)

---

## Executive Summary

**Person B, here's exactly what Person A needs from you for the BillBro system:**

There are **TWO separate flows** you need to support:
1. **Real-time Detection** (Checkout flow) - Use existing billbro_v3.onnx model
2. **Model Training Pipeline** (Add New Item flow) - Convert ONNX to PyTorch and train

---

## FLOW 1: Real-Time Detection (Checkout)

### Current State
- You have: `billbro_v3.onnx` model (trained on 6 classes)
- You have: `predict.py` with `GroceryDetector` class
- It already works in Streamlit

### What Person A Needs
Person A needs a **detection service** that takes an image and returns detections.

### Option A: Backend Wraps Detection (Recommended)

**Person A builds endpoint:**
```
POST /detect
```

**Request:**
```json
{
  "image": "base64_encoded_image",
  "confidence_threshold": 0.7  // optional
}
```

**Response:**
```json
{
  "detections": [
    {
      "item_name": "apple",
      "confidence": 0.95,
      "bbox": [100, 50, 200, 150]  // x1, y1, x2, y2
    },
    {
      "item_name": "diet_coke",
      "confidence": 0.92,
      "bbox": [250, 75, 350, 225]
    }
  ],
  "processing_time_ms": 45
}
```

**What You Provide:**
```python
# Person B's code that Person A calls
def detect_items(image_path, confidence_threshold=0.7):
    """
    Args:
        image_path: Path to image file or base64 string
        confidence_threshold: Min confidence to return detections
    
    Returns:
        List of dicts: [{"item_name": str, "confidence": float, "bbox": [x1, y1, x2, y2]}, ...]
    """
    detector = GroceryDetector(model_path="billbro_v3.onnx")
    detections = detector.predict(image_path, confidence_threshold)
    return detections
```

**Timeline:** Week 1 (This week) - Just needs to work with existing model

---

### Option B: Frontend Calls Detection Directly

**Alternative:** Person C's frontend calls your detection service directly.

**Frontend sends image → Your model service → Returns detections**

**Person A then processes:** `/checkout/bill` receives detections from frontend

**Advantage:** Simpler for Person A
**Disadvantage:** Requires separate service management

**Decision:** Discuss with Person A which option is better

---

## FLOW 2: Model Training Pipeline (Add New Item)

This is the **complex workflow** in the project spec.

### Scenario (from spec):
1. Store manager: "We just got Maggi Noodles"
2. Staff captures 15 images
3. Images sent to backend: `POST /training/upload_images`
4. **Person A's backend:**
   - Saves images to disk
   - Creates `training_job` record
   - Calls **YOUR** auto-labeling function
5. **You auto-label** the 15 images (2 minutes)
6. **You train** a fine-tuned model (15 minutes on GPU)
7. Backend polls `/training/job/{job_id}` for progress
8. When done, return metrics + new model path
9. Backend deploys new model to store

---

## What Person A Needs From You

### 1. Existing Model Wrapper (URGENT - This Week)

Make `GroceryDetector.predict()` work and expose it:

```python
# predict.py (already have this)
from ultralytics import YOLO

class GroceryDetector:
    def __init__(self, model_path="billbro_v3.onnx"):
        self.model = YOLO(model_path)  # or load ONNX
    
    def predict(self, image_path, confidence_threshold=0.7):
        """
        Returns:
            [
              {"item_name": "apple", "confidence": 0.95, "bbox": [x1, y1, x2, y2]},
              {"item_name": "diet_coke", "confidence": 0.92, "bbox": [x1, y1, x2, y2]},
            ]
        """
        results = self.model.predict(image_path, conf=confidence_threshold)
        
        detections = []
        for result in results:
            for box in result.boxes:
                class_id = int(box.cls[0])
                class_name = self.model.names[class_id]
                confidence = float(box.conf[0])
                bbox = box.xyxy[0].tolist()  # [x1, y1, x2, y2]
                
                detections.append({
                    "item_name": class_name,
                    "confidence": confidence,
                    "bbox": bbox
                })
        
        return detections
```

**Person A will call this in `/detect` endpoint.**

### 2. Model Conversion (Week 1-2)

Convert existing ONNX to PyTorch format:

```python
# training.py
from ultralytics import YOLO

def convert_onnx_to_pytorch(onnx_path, output_path):
    """
    Convert billbro_v3.onnx to .pt format
    """
    model = YOLO(onnx_path)  # YOLOv8 can load ONNX
    model.export(format='pt', imgsz=640)  # Save as .pt
    return output_path

# Usage:
convert_onnx_to_pytorch("billbro_v3.onnx", "models/billbro_v3.pt")
```

**Why:** YOLOv8 training API requires .pt format, not ONNX

### 3. Auto-Labeling Function (Week 2-3)

When Person A calls `/training/upload_images`, you auto-label:

```python
def auto_label_images(image_paths, base_model_path, output_dir):
    """
    Use base model to auto-label new images for training
    
    Args:
        image_paths: List of image file paths (15 images for new item)
        base_model_path: Path to billbro_v3.pt
        output_dir: Where to save labeled images
    
    Returns:
        {
            "labeled_count": 15,
            "processing_time_seconds": 120,
            "dataset_dir": "/path/to/labeled_images/"
        }
    """
    detector = YOLO(base_model_path)
    
    for image_path in image_paths:
        results = detector.predict(image_path)
        
        # Save results in YOLO format
        # results.save_txt(...)  # Person A stores in training_data table
    
    return {
        "labeled_count": len(image_paths),
        "processing_time_seconds": 120,
        "dataset_dir": output_dir
    }
```

### 4. Fine-Tuning Function (Week 3-5)

Person A triggers this after auto-labeling:

```python
def retrain_model(
    dataset_dir,
    base_model_path,
    epochs=5,
    device="gpu",
    job_id=None,  # For tracking progress
):
    """
    Fine-tune base model with new item images
    
    Args:
        dataset_dir: Directory with auto-labeled images (YOLO format)
        base_model_path: billbro_v3.pt
        epochs: Number of training epochs (use 5 for 15-min constraint)
        device: "gpu" or "cpu"
        job_id: For Person A to track progress
    
    Returns:
        {
            "success": True,
            "model_path": "/path/to/new_model.pt",
            "metrics": {
                "mAP50": 0.88,
                "mAP": 0.83,
                "accuracy": 0.85,
                "loss": 0.12
            },
            "training_time_seconds": 900  # 15 minutes
        }
    """
    model = YOLO(base_model_path)
    
    # Track progress for job_id
    results = model.train(
        data=f"{dataset_dir}/data.yaml",
        epochs=epochs,
        device=device,
        project="runs/detect",
        name=f"store_001_v{job_id}",
        # Callbacks to report progress back
    )
    
    return {
        "success": results.results is not None,
        "model_path": results.save_dir,  # .pt file location
        "metrics": {
            "mAP50": results.results.box.map50,
            "mAP": results.results.box.map,
            "accuracy": results.results.metrics.get("accuracy", 0),
            "loss": results.results.loss.cpu()
        },
        "training_time_seconds": results.training_time
    }
```

### 5. Training Progress Callback (Week 3-5)

Person A needs to track training progress. Provide callback:

```python
def create_progress_callback(job_id, update_callback):
    """
    Callback function for YOLOv8 training
    
    update_callback is called with:
        {
            "job_id": "job_12345",
            "status": "running",
            "current_epoch": 2,
            "total_epochs": 5,
            "progress": 40,  # 0-100
            "loss": 0.15,
            "learning_rate": 0.001
        }
    """
    def on_train_batch_end(trainer):
        progress = int((trainer.epoch / trainer.epochs) * 100)
        update_callback({
            "job_id": job_id,
            "status": "running",
            "current_epoch": trainer.epoch + 1,
            "total_epochs": trainer.epochs,
            "progress": progress,
            "loss": trainer.loss,
        })
    
    return on_train_batch_end
```

---

## Integration Points with Person A's API

### Person A Builds These Endpoints:

**1. Detection endpoint (Week 1):**
```
POST /detect
Input: image (base64)
Output: detections
```

**2. Training upload endpoint (Week 2):**
```
POST /training/upload_images
Input: item_name, images
Output: job_id
(Internally calls your auto_label_images())
```

**3. Training progress polling (Week 3):**
```
GET /training/job/{job_id}
Output: status, progress, metrics, or error
(Internally calls your retrain_model())
```

**4. Model deployment endpoint (Week 3):**
```
POST /models/deploy/{job_id}
(Internally: moves .pt file to active location)
```

---

## Timeline & Responsibilities

### Week 1 (This Week)
**Person B:** Convert ONNX to .pt format
- [ ] Create `training.py` with `convert_onnx_to_pytorch()`
- [ ] Verify `predict.py` works with .pt format
- [ ] Document detection output format

**Person A:** Build detection endpoint
- [ ] Create `POST /detect` endpoint
- [ ] Test with your GroceryDetector
- [ ] Document detection response format

**Person C:** Can use detection endpoint for checkout UI
- [ ] Build checkout flow using `/detect`
- [ ] Display detections to user

### Week 2-3
**Person B:** Auto-labeling + fine-tuning
- [ ] `auto_label_images()` function
- [ ] `retrain_model()` function
- [ ] Test with sample dataset

**Person A:** Training endpoints
- [ ] `POST /training/upload_images`
- [ ] `GET /training/job/{job_id}`
- [ ] Async job queue integration

**Person C:** Can use for "Add New Item" flow

### Week 4+
**Person B:** Optimization + monitoring
- [ ] Model quantization
- [ ] Inference speed optimization
- [ ] Model versioning + rollback

---

## Key Questions to Answer Together

### For Person B:
- [ ] When will base model (billbro_v3) be converted to .pt?
- [ ] What's the exact detection output format from your model?
- [ ] How long does inference take (for timeout settings)?
- [ ] Can you provide mock functions for testing?

### For Person A:
- [ ] Should I wrap Person B's detection in `/detect` endpoint (Option A)?
- [ ] Or should frontend call Person B's model directly (Option B)?
- [ ] How should I manage training job queue (Celery, threading, etc.)?
- [ ] Where should trained models be stored?

### For Person C:
- [ ] Can you start building checkout with detection endpoint?
- [ ] Do you need detection format different from what Person B provides?

---

## File Structure Proposal

```
billbro/
├── backend/
│   ├── api_app.py              # Endpoints calling Person B functions
│   ├── database.py
│   └── training_jobs/           # Job queue management
│
├── ml/
│   ├── predict.py              # GroceryDetector (existing)
│   ├── training.py             # NEW: conversion + auto-label + retrain
│   ├── models/
│   │   ├── billbro_v3.pt       # Converted from ONNX
│   │   ├── billbro_v4.pt       # Fine-tuned versions
│   │   └── store_001_v1.pt
│   └── datasets/               # Training datasets
│
└── frontend/
    └── app.py                  # Calls /detect + training endpoints
```

---

## Quick Decision Matrix

| Scenario | Person A | Person B | Person C |
|----------|----------|----------|----------|
| **Week 1: Checkout** | Build `/detect` endpoint | Provide `GroceryDetector.predict()` | Use `/detect` in UI |
| **Week 2: Auto-label** | Build `/training/upload_images` | Implement `auto_label_images()` | Show upload progress |
| **Week 3: Train** | Build `/training/job/{id}` | Implement `retrain_model()` | Show training progress |
| **Week 4+: Deploy** | Build `/models/deploy` | Optimize + version models | Show model history |

---

## Next Step

**Person B:** Reply with:
- [ ] When can you have billbro_v3.pt ready?
- [ ] Can you provide a sample `GroceryDetector.predict()` function?
- [ ] Do you have the auto-labeling code ready, or do you need help implementing it?
- [ ] What's your preferred way to track training progress (callbacks, polling, etc.)?

**Person A:** Once Person B confirms:
- [ ] Start building `/detect` endpoint
- [ ] Design job queue for training
- [ ] Plan async architecture

**Person C:** Can start:
- [ ] Building checkout UI to use `/detect`
- [ ] Designing training progress UI

---

## Success Criteria

- [x] Detection works in checkout (Week 1)
- [x] Auto-labeling works on new images (Week 2)
- [x] Fine-tuning trains new model in <20 min (Week 3)
- [x] New model deploys + detects new items (Week 3)
- [x] Full "Add New Item" workflow works end-to-end (Week 4)

---

**Person B: This is your integration spec. Let's align on timeline and details!**
