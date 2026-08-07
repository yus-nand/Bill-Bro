#!/usr/bin/env python3
"""
Test script for /detect endpoint
Tests that the endpoint loads correctly and can handle requests
"""

import base64
import requests
import time
from pathlib import Path
from PIL import Image
import numpy as np

def create_test_image():
    """Create a simple test image"""
    # Create a 640x480 RGB image with some color
    img_array = np.zeros((480, 640, 3), dtype=np.uint8)

    # Add a red rectangle in the middle (simulates an item)
    img_array[150:300, 200:400] = [255, 0, 0]

    img = Image.fromarray(img_array, 'RGB')
    return img

def image_to_base64(img: Image.Image) -> str:
    """Convert PIL Image to base64 string"""
    import io
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    img_bytes = buffer.getvalue()
    return base64.b64encode(img_bytes).decode('utf-8')

def test_detect_endpoint():
    """Test the /detect endpoint"""
    print("=" * 70)
    print("Testing /detect Endpoint")
    print("=" * 70)

    # Check if API is running
    print("\n1. Checking if API is running on localhost:8000...")
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        print(f"   ✅ API is running: {response.json()}")
    except Exception as e:
        print(f"   ❌ API not running: {e}")
        print("   → Start the API with: python api_app.py")
        return False

    # Check if model file exists
    print("\n2. Checking if model file exists...")
    model_path = Path("models/grocery_yolov8.pt")
    if model_path.exists():
        size_mb = model_path.stat().st_size / (1024 * 1024)
        print(f"   ✅ Model found: {model_path} ({size_mb:.1f} MB)")
    else:
        print(f"   ❌ Model not found at {model_path}")
        return False

    # Check if predict.py can be imported
    print("\n3. Checking if predict.py can be imported...")
    try:
        from predict import GroceryDetector
        print(f"   ✅ GroceryDetector imported successfully")
    except Exception as e:
        print(f"   ❌ Cannot import GroceryDetector: {e}")
        return False

    # Create test image
    print("\n4. Creating test image...")
    try:
        test_img = create_test_image()
        img_b64 = image_to_base64(test_img)
        print(f"   ✅ Test image created and encoded to base64 ({len(img_b64)} chars)")
    except Exception as e:
        print(f"   ❌ Failed to create test image: {e}")
        return False

    # Test /detect endpoint
    print("\n5. Testing /detect endpoint...")
    try:
        response = requests.post(
            "http://localhost:8000/detect",
            json={
                "image": img_b64,
                "confidence_threshold": 0.5
            },
            timeout=30  # Model loading can take time
        )

        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ /detect returned 200 OK")
            print(f"   Response shape:")
            print(f"     - detections: {len(result.get('detections', []))} objects")
            print(f"     - processing_time_ms: {result.get('processing_time_ms')} ms")

            # Show detected items
            if result.get('detections'):
                print(f"\n   Detected items:")
                for det in result['detections']:
                    print(f"     - {det['item_name']:20} confidence={det['confidence']:.2f} bbox={det['bbox']}")
            else:
                print(f"\n   (No items detected in test image - this is OK)")

            return True
        else:
            print(f"   ❌ /detect returned {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    except requests.exceptions.Timeout:
        print(f"   ❌ Request timed out (model loading took >30s)")
        return False
    except Exception as e:
        print(f"   ❌ Request failed: {e}")
        return False

if __name__ == "__main__":
    success = test_detect_endpoint()

    print("\n" + "=" * 70)
    if success:
        print("✅ All tests passed! /detect endpoint is working.")
        print("\nYou can now:")
        print("  1. Open http://localhost:8000/docs")
        print("  2. Try the /detect endpoint with a real image")
        print("  3. Share with Person C for Checkout integration")
    else:
        print("❌ Some tests failed. Check the errors above.")
    print("=" * 70)
