# Resolution: Person A ↔ Person B Integration

## The Confusion Resolved

**Original Question:** "Should Person A build a `/detect` endpoint or should Person C's frontend call Person B's model directly?"

**Answer:** It depends on the architecture, but here's the recommended solution:

---

## ✅ Recommended Approach: Backend Wraps Detection (Option A)

### Why This Is Better:
1. **Person C (Frontend)** only talks to Person A (Backend)
2. **Person A** manages all ML integration in one place
3. **Cleaner separation of concerns** - frontend doesn't need to know about ML
4. **Easier to swap/upgrade** Person B's model later
5. **Consistent error handling** and timeout management

### Architecture:
```
Frontend (React/Streamlit)
    ↓ POST /detect
    ↓
Backend API (Person A)
    ↓ calls
    ↓
Person B's Detection Service
    ↓ returns detections
    ↓
Backend formats response
    ↓
Frontend displays results
```

---

## Two Separate Flows You Need to Manage

### FLOW 1: Real-Time Detection (Checkout)
**Timeline:** Week 1 (This week!)

**Person A Builds:**
```
POST /detect
- Input: image (base64)
- Output: detections [{"item_name": "apple", "confidence": 0.95, "bbox": [...]}]
- Processing time: ~50ms
```

**Person B Provides:**
```python
# predictpy - GroceryDetector.predict() function
detector = GroceryDetector("billbro_v3.pt")  # Already have ONNX, just convert to .pt
detections = detector.predict(image_path)
# Returns: [{"item_name": "apple", "confidence": 0.95, "bbox": [100, 50, 200, 150]}, ...]
```

**Person C Uses:**
```javascript
// In checkout flow
const response = await fetch('http://localhost:8000/detect', {
  method: 'POST',
  body: JSON.stringify({ image: base64_image })
});
const detections = response.json().detections;
// Display to staff: ["apple (95%)", "diet_coke (92%)"]
```

### FLOW 2: Model Training Pipeline (Add New Item)
**Timeline:** Week 2-3

**The Full Workflow:**
```
1. Staff captures 15 images of new item
   ↓
2. Frontend sends to: POST /training/upload_images
   ↓
3. Backend calls Person B's auto_label_images()
   - Auto-labels 15 images (2 minutes)
   - Stores labeled dataset
   ↓
4. Backend triggers async training job
   ↓
5. Person B's retrain_model() fine-tunes model
   - Takes ~15 minutes on GPU
   - Trains on 5 epochs with new item + old items
   ↓
6. Returns new model + metrics
   ↓
7. Backend deploys new model
   ↓
8. Frontend polls GET /training/job/{job_id} for progress
   ↓
9. Staff can now detect new item in next checkout
```

---

## What Each Person Needs to Do

### Person A (Backend) - Your Tasks:

**Week 1:**
```python
# Endpoint 1: Real-time detection
@app.post("/detect")
def detect_items(image_base64: str):
    # Call Person B's detector
    detector = GroceryDetector("models/billbro_v3.pt")
    detections = detector.predict(image_base64)
    return {"detections": detections}
```

**Week 2-3:**
```python
# Endpoint 2: Upload training images
@app.post("/training/upload_images")
def upload_training_images(item_name: str, images: List[bytes]):
    # 1. Save images
    # 2. Call Person B's auto_label_images()
    # 3. Create training job in database
    # 4. Return job_id
    
    job_id = create_training_job()
    trigger_async_training(job_id)
    return {"job_id": job_id}

# Endpoint 3: Check training progress
@app.get("/training/job/{job_id}")
def get_training_status(job_id: str):
    job = get_job_from_database(job_id)
    return {
        "status": job.status,  # pending/running/success/failed
        "progress": job.progress,  # 0-100
        "current_epoch": job.current_epoch,
        "metrics": job.metrics if done else None
    }
```

### Person B (ML) - Your Tasks:

**Week 1 (URGENT):**
- [ ] Convert `billbro_v3.onnx` → `billbro_v3.pt` (PyTorch format)
- [ ] Test `GroceryDetector.predict()` works with .pt file
- [ ] Confirm detection output format with Person A

**Week 2-3:**
- [ ] Implement `auto_label_images(image_paths, base_model, output_dir)`
  - Use base model to label new images
  - Return labeled dataset in YOLO format
  
- [ ] Implement `retrain_model(dataset_dir, base_model, epochs=5)`
  - Fine-tune on new dataset
  - Return new model path + metrics
  - Should take ~15 minutes on GPU

- [ ] Implement progress callback for training
  - Report: current epoch, loss, progress %

**Week 4+:**
- [ ] Model optimization (quantization, speed)
- [ ] Model versioning + rollback

### Person C (Frontend) - Your Tasks:

**Week 1:**
- [ ] Build checkout UI using `/detect` endpoint
- [ ] Display detections to staff
- [ ] Send to `/checkout/bill` with confirmed detections

**Week 2-3:**
- [ ] Build "Add New Item" workflow
  - Upload 15 images
  - Poll `/training/job/{job_id}` for progress
  - Show training progress bar
  - Show results when done

**Week 4+:**
- [ ] Build model dashboard (version history, rollback)

---

## Communication Protocol

### Person A → Person B:
- "What's the exact format of your detection output?"
- "How long does inference take? (for timeout settings)"
- "Can you provide mock functions for testing?"
- "How should we report training progress?"

### Person B → Person A:
- "Here's `GroceryDetector.predict()` - takes image, returns detections"
- "Fine-tuning takes 15 min on GPU, auto-labeling 2 min"
- "Detection output: {item_name, confidence, bbox}"
- "Use this callback to track training progress"

### Person A → Person C:
- "Here's `/detect` endpoint - send image, get detections"
- "Here's `/training/upload_images` and `/training/job/{id}`"
- "Detection format is: [{item_name, confidence, bbox}]"

### Person C → Person A:
- "What happens if detection confidence is low?"
- "Do you have timeout/error handling?"
- "How often should I poll job status?"

---

## Decision Tree

```
Does Person B have billbro_v3.pt ready?
├─ YES → Person A builds /detect endpoint (Week 1)
└─ NO  → Person B converts ONNX to .pt first

Can Person B provide auto_label_images() function?
├─ YES → Person A integrates for /training/upload_images (Week 2)
└─ NO  → Person B builds it first

Can Person B provide retrain_model() function?
├─ YES → Person A builds async job queue (Week 2-3)
└─ NO  → Person B builds it first
```

---

## Weekly Sync Questions

### Week 1 Standup:
- [ ] Person B: "Is billbro_v3.pt ready?"
- [ ] Person A: "Can I start building /detect endpoint?"
- [ ] Person C: "Can I use /detect in checkout flow?"

### Week 2 Standup:
- [ ] Person B: "Is auto_label_images() ready to test?"
- [ ] Person A: "Should I build /training/upload_images now?"
- [ ] Person C: "Can I show upload progress UI?"

### Week 3 Standup:
- [ ] Person B: "Is retrain_model() ready?"
- [ ] Person A: "Can I wire up async training?"
- [ ] Person C: "Can I show training progress?"

---

## Success Metrics

- [x] **Week 1:** Detection works (can detect existing items in checkout)
- [x] **Week 2:** Auto-labeling works (can label 15 images in 2 min)
- [x] **Week 3:** Training works (can train new model in 15 min)
- [x] **Week 3:** New items detectable (trained model deployed and active)
- [x] **Week 4:** Full workflow end-to-end (staff can add item → detect in checkout)

---

## TL;DR

**Person A:** Build these endpoints:
1. `POST /detect` - wraps Person B's detector
2. `POST /training/upload_images` - starts training job
3. `GET /training/job/{id}` - checks progress

**Person B:** Provide these functions:
1. `GroceryDetector.predict()` - real-time detection (Week 1)
2. `auto_label_images()` - auto-labels images (Week 2)
3. `retrain_model()` - fine-tunes model (Week 3)

**Person C:** Use these endpoints:
1. `/detect` - for checkout
2. `/training/upload_images` + `/training/job/{id}` - for add item flow

**All:** Sync weekly on dependencies + blockers

---

## Next Action

**All Team Members:**
1. Read this document
2. Confirm your timeline (can you deliver by your Week X milestone?)
3. List blockers or concerns
4. Set up dedicated Slack channel for ml-backend-frontend sync

**Person B specifically:** Respond to `PERSON_B_INTEGRATION_SPEC.md` with:
- When billbro_v3.pt will be ready
- Detection output format confirmation
- Timeline for auto_label_images() and retrain_model()
- Preferred way to track training progress

Let's ship this! 🚀
