// src/imageUtils.js
// Shared image-handling helpers, pulled out of Checkout.jsx/AddItem.jsx
// so both pages (and Inventory's Retrain flow) use the exact same fix
// rather than three slightly-drifting copies.

// Re-encodes any browser-displayable image (including HEIC — the default
// format for iPhone photos) into a real JPEG File/data-URL before it's
// staged for upload or detection. Safari can display/preview a raw HEIC
// file fine, but cv2 on the backend cannot decode HEIC at all — it
// returns None/null, and every server-side consumer (detect_from_base64,
// training.py's _load_rgb) raises on it. Re-encoding through a canvas
// normalizes ANY source format to real JPEG bytes regardless of what the
// browser was originally handed.
export function reencodeImageFile(file) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    const objectUrl = URL.createObjectURL(file);

    img.onload = () => {
      URL.revokeObjectURL(objectUrl);
      const canvas = document.createElement("canvas");
      canvas.width = img.naturalWidth;
      canvas.height = img.naturalHeight;
      const ctx = canvas.getContext("2d");
      ctx.drawImage(img, 0, 0);
      canvas.toBlob(
        (blob) => {
          if (!blob) {
            reject(new Error("Couldn't re-encode this photo."));
            return;
          }
          const jpegName = file.name.replace(/\.\w+$/, "") + ".jpg";
          resolve(new File([blob], jpegName, { type: "image/jpeg" }));
        },
        "image/jpeg",
        0.9
      );
    };
    img.onerror = () => {
      URL.revokeObjectURL(objectUrl);
      reject(
        new Error(
          "Couldn't read this photo — the format may not be supported by this browser."
        )
      );
    };
    img.src = objectUrl;
  });
}

// training.py uses this directly as the new model class label (e.g.
// "Maggi Noodles" -> "maggi_noodles").
export function toClassName(name) {
  return name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}
