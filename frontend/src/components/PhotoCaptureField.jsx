// src/components/PhotoCaptureField.jsx
// Shared photo-capture UI: drag-and-drop dropzone + file input (camera-
// capable on mobile) + thumbnail grid + per-photo remove. Used by Add Item
// and Inventory's Retrain flow so both get the same HEIC-safe re-encoding
// (see imageUtils.js) without duplicating the capture UI twice.
//
// Drag-and-drop added on top of the original click-to-browse button —
// dropping files anywhere on the zone runs them through the exact same
// addFiles() path (re-encode, thumbnail, error handling) as picking them
// from the file dialog, so there's only one code path to keep correct.
//
// Deliberately no capture="environment" on the file input here (unlike
// Checkout.jsx's single-photo one). Found via real testing: combined
// with multiple, it made Safari silently no-op the whole picker — click
// "Browse files" and nothing happened at all, no dialog, no error. Makes
// sense in hindsight too: capture is meant to jump straight into the
// camera for one shot, which doesn't fit a "pick several training
// photos at once" flow anyway. Dropping it doesn't lose camera access on
// mobile — "Take Photo" is still one of the options in the native picker
// sheet, it's just no longer forced.

import { useRef, useState } from "react";
import { reencodeImageFile } from "../imageUtils.js";
import { IconUpload, IconCamera } from "./Icons.jsx";

export default function PhotoCaptureField({
  images,
  setImages,
  error,
  setError,
  inputId = "photo-capture-input",
}) {
  const fileInputRef = useRef(null);
  const [dragActive, setDragActive] = useState(false);
  const dragCounter = useRef(0);

  const addFiles = async (fileList) => {
    const files = Array.from(fileList || []).filter((f) => f.type.startsWith("image/"));
    if (files.length === 0) return;

    setError("");
    const results = await Promise.allSettled(files.map(reencodeImageFile));
    const converted = [];
    let failCount = 0;
    for (const r of results) {
      if (r.status === "fulfilled") {
        converted.push(r.value);
      } else {
        failCount += 1;
      }
    }

    setImages((prev) => [
      ...prev,
      ...converted.map((file) => ({ file, previewUrl: URL.createObjectURL(file) })),
    ]);

    if (failCount > 0) {
      setError(
        `${failCount} photo${failCount === 1 ? "" : "s"} couldn't be read and ${
          failCount === 1 ? "was" : "were"
        } skipped — try re-taking ${failCount === 1 ? "it" : "them"}.`
      );
    }
  };

  const handleAddPhotos = async (e) => {
    const files = e.target.files;
    if (fileInputRef.current) fileInputRef.current.value = "";
    await addFiles(files);
  };

  const handleDragEnter = (e) => {
    e.preventDefault();
    dragCounter.current += 1;
    if (e.dataTransfer?.types?.includes("Files")) setDragActive(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    dragCounter.current -= 1;
    if (dragCounter.current <= 0) {
      dragCounter.current = 0;
      setDragActive(false);
    }
  };

  const handleDragOver = (e) => {
    // Required for onDrop to fire at all — browsers block drops by default.
    e.preventDefault();
  };

  const handleDrop = async (e) => {
    e.preventDefault();
    dragCounter.current = 0;
    setDragActive(false);
    await addFiles(e.dataTransfer?.files);
  };

  const removePhoto = (index) => {
    setImages((prev) => {
      URL.revokeObjectURL(prev[index].previewUrl);
      return prev.filter((_, i) => i !== index);
    });
  };

  return (
    <>
      {error && <p className="bb-form-error">{error}</p>}

      <div
        className={`bb-dropzone${dragActive ? " bb-dropzone-active" : ""}`}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          multiple
          onChange={handleAddPhotos}
          id={inputId}
          className="bb-visually-hidden"
        />
        <span className="bb-dropzone-icon" aria-hidden="true">
          {dragActive ? <IconUpload width={24} height={24} /> : <IconCamera width={24} height={24} />}
        </span>
        <p className="bb-dropzone-text">
          {dragActive ? "Drop to add" : "Drag photos here, or"}
        </p>
        <label htmlFor={inputId} className="bb-btn bb-btn-secondary bb-btn-small">
          Browse files
        </label>
      </div>

      {images.length > 0 && (
        <div className="bb-image-grid">
          {images.map((img, i) => (
            <div className="bb-image-thumb" key={img.previewUrl}>
              <img src={img.previewUrl} alt={`Capture ${i + 1}`} />
              <button type="button" onClick={() => removePhoto(i)} aria-label="Remove photo">
                ×
              </button>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
