"""
benchmark_inference.py — measure GroceryDetector latency locally.

This sandbox has no torch/ultralytics (no network access to install), so
this can't be run here. Run it yourself once the retrain finishes:

    python benchmark_inference.py --model models/grocery_yolov8.pt --n 50

Addresses the open "<100ms target" item from ML_NOTES.md and gives an
independent number against Person A's claimed ~100-200ms warm latency
(FRONTEND_CONTEXT.md) — his number is measured at the API layer (network +
JSON + model), this measures the model call alone, so the two together
show how much overhead the API adds.
"""

from __future__ import annotations

import argparse
import statistics
import time
from pathlib import Path

import numpy as np

from predict import GroceryDetector


def make_test_image(size: int = 640) -> np.ndarray:
    """A random RGB frame — good enough for timing, not accuracy."""
    return np.random.randint(0, 255, (size, size, 3), dtype=np.uint8)


def benchmark(model_path: str, n: int, warmup: int, real_image: str | None) -> None:
    print(f"Loading {model_path} ...")
    detector = GroceryDetector(model_path)

    if real_image:
        import cv2
        img = cv2.imread(real_image)
        if img is None:
            raise SystemExit(f"Could not read {real_image}")
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    else:
        img = make_test_image()

    print(f"Warming up ({warmup} runs — first call always pays model/CUDA init cost)...")
    for _ in range(warmup):
        detector.detect(img)

    print(f"Timing {n} runs...")
    times_ms = []
    for _ in range(n):
        start = time.perf_counter()
        detector.detect(img)
        times_ms.append((time.perf_counter() - start) * 1000)

    times_ms.sort()
    p50 = statistics.median(times_ms)
    p95 = times_ms[int(len(times_ms) * 0.95)]
    p99 = times_ms[min(int(len(times_ms) * 0.99), len(times_ms) - 1)]

    print()
    print(f"  n:       {n}")
    print(f"  mean:    {statistics.mean(times_ms):.1f} ms")
    print(f"  median:  {p50:.1f} ms")
    print(f"  p95:     {p95:.1f} ms")
    print(f"  p99:     {p99:.1f} ms")
    print(f"  min/max: {min(times_ms):.1f} / {max(times_ms):.1f} ms")
    print()
    target = 100
    verdict = "MEETS" if p50 <= target else "MISSES"
    print(f"  {verdict} the <{target}ms target at p50.")
    if not real_image:
        print("  (Ran on a random test frame — rerun with --image for a real photo.)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="models/grocery_yolov8.pt")
    parser.add_argument("--n", type=int, default=50, help="Number of timed runs")
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--image", default=None, help="Path to a real photo instead of random noise")
    args = parser.parse_args()

    if not Path(args.model).exists():
        raise SystemExit(f"Model not found: {args.model}")

    benchmark(args.model, args.n, args.warmup, args.image)
