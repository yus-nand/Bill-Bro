# For Person A — `/detect` route, ready to paste

## First, a heads-up

I pulled the actual pushed code on `origin/Person-A` (`api_app.py`) to check
this against `RESPONSES_TO_PERSON_B_AND_C.md`, which says `/detect` is
"✅ LIVE". It isn't in that file yet — `api_app.py`'s routes are still just
the original 9 (`/items` x3, `/inventory` x2, `/alerts` x2,
`/checkout/bill`, `/models/active`, `/health`). No `/detect`, and no
`feat/detect-endpoint` branch exists in the repo for me to check either.
Consistent with your own doc's last section admitting the numpy/torch
issue is still blocking you from testing it — makes sense, since it's not
written yet. No blame here, just flagging so the team's status tracking
matches reality; not a big deal to fix.

## The numpy/torch issue — likely root cause

Your `requirements.txt` pins `torch==2.1.1` / `ultralytics==8.0.217`, but
your repo's `__pycache__/database.cpython-312.pyc` shows you're running
**Python 3.12**. `torch==2.1.1` doesn't ship Python 3.12 wheels — that
support landed in torch 2.2. Pip either fails outright or resolves to
something that ends up numpy-ABI-mismatched with the rest of the pins,
which matches the error you're describing.

**Fix:** bump the ML deps to versions with real 3.12 support:

```diff
- torch==2.1.1
- torchvision==0.16.1
- ultralytics==8.0.217
- numpy==1.24.3
+ torch>=2.2.0
+ torchvision>=0.17.0
+ ultralytics>=8.2.0
+ numpy>=1.26.0,<2.0.0
```

(Capped `numpy<2.0.0` deliberately — torch 2.2's official wheels still
expect NumPy 1.x; a bare `numpy>=1.26.0` would let pip pull 2.x and
reintroduce the same ABI mismatch from the other direction.)

## The route itself

Assumes `predict.py` sits next to `api_app.py` (copy it over from
`Person B/BillBro (FYP)/predict.py`, or adjust the import path) and
`models/grocery_yolov8.pt` is reachable from wherever `api_app.py` runs.

```python
# ── add to imports at the top of api_app.py ──
from pydantic import BaseModel
from predict import GroceryDetector

# ── add near Setup, after `app = FastAPI(...)` — load once at startup,
#    not per-request (model load is the ~2-3s "cold start" cost) ──
detector = GroceryDetector("models/grocery_yolov8.pt")


# ============================================================================
# DETECTION ENDPOINT (Person B's model)
# ============================================================================

class DetectRequest(BaseModel):
    image: str  # base64, no data-URL prefix
    confidence_threshold: float | None = None


@app.post("/detect", tags=["Detection"])
def detect(body: DetectRequest):
    """Run YOLOv8 detection on a base64-encoded image"""
    try:
        return detector.detect_from_base64(
            body.image, body.confidence_threshold or 0.5
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

Note this uses a Pydantic model (`DetectRequest`) rather than your usual
plain-scalar-args style (like `create_item`) — necessary here since a
base64 image is way too large for query params, and the frontend
(`api.js`'s `detectImage()`) already sends it as a JSON body per
`API_CONTRACT.md`.

`detect_from_base64()` returns `{"detections": [...], "processing_time_ms": int}`
directly — matches the confirmed response shape exactly, no reshaping
needed on your end.

## Once it's in

Run `uvicorn api_app:app --reload`, hit `/docs`, try `/detect` with a
base64-encoded test image. If pepsi comes back wrong/missing, that's the
known dataset gap (retraining now) — not a bug in this route.
