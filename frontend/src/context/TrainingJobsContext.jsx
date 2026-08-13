// src/context/TrainingJobsContext.jsx
//
// Training runs on CPU and can take up to an hour (per Person B's
// original estimate). Before this context existed, all polling state
// (jobId, progress, stage, elapsed time) lived inside AddItem.jsx's own
// useState/useRef — which React tears down the moment you navigate to
// another page, since react-router unmounts the route's component.
// The backend job itself kept running fine (it's a Python background
// thread, fully decoupled from any browser tab), but the UI's
// connection to it was gone: come back to Add Item and you'd see the
// wizard reset to "details", with no way to tell a job was even still
// running until it finished changing the item's status behind your back.
//
// Fix: move job state + the poll loop itself up here, into a Provider
// mounted once above the router (see App.jsx) — so it survives page
// navigation. AddItem.jsx and Inventory's Retrain flow both read/write
// through this same context, keyed by item id, so either page can watch
// (or resume watching) any item's training progress regardless of which
// page originally started it.

import { createContext, useCallback, useContext, useRef, useState } from "react";
import { uploadTrainingImages, getTrainingJob, retrainFromExistingPhotos } from "../api.js";
import { STORE_ID, API_BASE_URL } from "../config.js";
import { useToast } from "./ToastContext.jsx";

const POLL_INTERVAL_MS = 5000;

// Same locked shape as before (RESPONSES_TO_PERSON_B_AND_C.md) — status
// is one of pending | running | success | failed. Extra synonyms kept
// as harmless safety.
const SUCCESS_STATUSES = new Set(["success", "complete", "completed", "shelved"]);
const FAILURE_STATUSES = new Set(["failed", "error"]);

function normalizeJobStatus(raw) {
  return {
    status: raw.status,
    progress: raw.progress ?? raw.progress_percent ?? 0,
    epoch: raw.current_epoch ?? raw.epoch ?? null,
    stage: raw.stage ?? null,
    metrics: raw.metrics ?? null,
    errorMessage: raw.error_message ?? raw.reason ?? null,
  };
}

const TrainingJobsContext = createContext(null);

export function TrainingJobsProvider({ children }) {
  // Keyed by item id (string). Each entry:
  // { jobId, itemName, phase: "uploading"|"training"|"shelved"|"failed",
  //   job: normalized status | null, pollError, elapsedSec, startedAt }
  const [jobs, setJobs] = useState({});
  const intervalsRef = useRef({}); // itemId -> { poll, elapsed }
  const toast = useToast();

  const patchJob = useCallback((itemId, patch) => {
    setJobs((prev) => ({
      ...prev,
      [itemId]: { ...(prev[itemId] || {}), ...patch },
    }));
  }, []);

  const stopPolling = useCallback((itemId) => {
    const handles = intervalsRef.current[itemId];
    if (handles) {
      clearInterval(handles.poll);
      clearInterval(handles.elapsed);
      delete intervalsRef.current[itemId];
    }
  }, []);

  const beginPolling = useCallback(
    (itemId, jobId) => {
      stopPolling(itemId);
      patchJob(itemId, { jobId, elapsedSec: 0, pollError: "" });

      const tick = async () => {
        try {
          const res = await getTrainingJob(jobId);
          const normalized = normalizeJobStatus(res.data);
          patchJob(itemId, { job: normalized, pollError: "" });
          if (
            SUCCESS_STATUSES.has(normalized.status) ||
            FAILURE_STATUSES.has(normalized.status)
          ) {
            stopPolling(itemId);
            const succeeded = SUCCESS_STATUSES.has(normalized.status);
            patchJob(itemId, { phase: succeeded ? "shelved" : "failed" });
            // Fires no matter which page the user's currently on — the
            // whole point of moving this state up into a Provider was so
            // a job started from Add Item (or Inventory's Retrain) keeps
            // being tracked after you navigate away, so the completion
            // notice needs to follow you too, not just live in a row
            // that's no longer on screen.
            setJobs((prev) => {
              const name = prev[itemId]?.itemName || "Item";
              if (succeeded) {
                toast.success(
                  `${name} finished training and is back on the shelf.` +
                    (normalized.metrics?.mAP50 != null
                      ? ` mAP50: ${Math.round(normalized.metrics.mAP50 * 100)}%.`
                      : "")
                );
              } else {
                toast.error(
                  `${name} failed to train${normalized.errorMessage ? `: ${normalized.errorMessage}` : "."}`
                );
              }
              return prev;
            });
          }
        } catch {
          patchJob(itemId, {
            pollError: `Lost contact with GET /training/job/${jobId} — will keep retrying.`,
          });
        }
      };

      tick();
      const pollHandle = setInterval(tick, POLL_INTERVAL_MS);
      const elapsedHandle = setInterval(() => {
        setJobs((prev) => {
          const entry = prev[itemId];
          if (!entry) return prev;
          return {
            ...prev,
            [itemId]: { ...entry, elapsedSec: (entry.elapsedSec || 0) + 1 },
          };
        });
      }, 1000);
      intervalsRef.current[itemId] = { poll: pollHandle, elapsed: elapsedHandle };
    },
    [patchJob, stopPolling]
  );

  // Kicks off a fresh-photos training run for itemId (works identically
  // whether the item is brand new — Add Item's flow — or already exists
  // — Inventory's "capture new photos" retrain choice. The backend
  // endpoint itself has no notion of "first time" vs "again", it just
  // re-labels + fine-tunes from whatever files are sent).
  const startTraining = useCallback(
    async (itemId, itemName, files) => {
      patchJob(itemId, {
        phase: "uploading",
        itemName,
        job: null,
        pollError: "",
        errorAtUpload: "",
        startedAt: Date.now(),
      });
      try {
        const res = await uploadTrainingImages(itemId, itemName, files, STORE_ID);
        const jobId = res.data.job_id;
        patchJob(itemId, { phase: "training" });
        beginPolling(itemId, jobId);
        return { ok: true };
      } catch (err) {
        const message =
          err?.response?.data?.detail ||
          `Couldn't reach POST /training/upload_images at ${API_BASE_URL}.`;
        patchJob(itemId, { phase: "upload_failed", errorAtUpload: message });
        return { ok: false, error: message };
      }
    },
    [patchJob, beginPolling]
  );

  // Retrain flow's "reuse existing photos" path — no file upload step,
  // the backend finds whatever's already on disk from a prior run and
  // starts training directly (POST /items/{id}/retrain).
  const startRetrainFromExisting = useCallback(
    async (itemId, itemName) => {
      patchJob(itemId, {
        phase: "uploading",
        itemName,
        job: null,
        pollError: "",
        errorAtUpload: "",
        startedAt: Date.now(),
      });
      try {
        const res = await retrainFromExistingPhotos(itemId);
        const jobId = res.data.job_id;
        patchJob(itemId, { phase: "training" });
        beginPolling(itemId, jobId);
        return { ok: true, photosUsed: res.data.photos_used };
      } catch (err) {
        const message =
          err?.response?.data?.detail ||
          `Couldn't reach POST /items/${itemId}/retrain at ${API_BASE_URL}.`;
        patchJob(itemId, { phase: "upload_failed", errorAtUpload: message });
        return { ok: false, error: message };
      }
    },
    [patchJob, beginPolling]
  );

  const dismissJob = useCallback(
    (itemId) => {
      stopPolling(itemId);
      setJobs((prev) => {
        const next = { ...prev };
        delete next[itemId];
        return next;
      });
    },
    [stopPolling]
  );

  const getJob = useCallback((itemId) => jobs[itemId] || null, [jobs]);

  const value = {
    jobs,
    getJob,
    startTraining,
    startRetrainFromExisting,
    dismissJob,
  };

  return (
    <TrainingJobsContext.Provider value={value}>{children}</TrainingJobsContext.Provider>
  );
}

export function useTrainingJobs() {
  const ctx = useContext(TrainingJobsContext);
  if (!ctx) {
    throw new Error("useTrainingJobs must be used inside a TrainingJobsProvider");
  }
  return ctx;
}
