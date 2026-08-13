// src/components/TrainingProgressCard.jsx
// Shared "training in progress" card — reads a job entry from
// TrainingJobsContext (see that file's header comment for why job state
// lives there instead of per-page). Used by AddItem's training step and
// Inventory's Retrain flow, so both look and behave identically.

export default function TrainingProgressCard({ entry }) {
  const job = entry?.job;
  const elapsedSec = entry?.elapsedSec || 0;
  const pollError = entry?.pollError || "";

  return (
    <div className="bb-card">
      {pollError && <p className="bb-form-error">{pollError}</p>}
      <div className="bb-progress-bar">
        <div
          className="bb-progress-fill"
          style={{ width: `${Math.min(job?.progress ?? 5, 100)}%` }}
        />
      </div>
      <p className="bb-caption" style={{ marginTop: 10 }}>
        {job
          ? `Training… ${job.progress ?? 0}%${job.epoch ? ` (epoch ${job.epoch})` : ""}${
              job.stage ? ` — stage: ${job.stage}` : ""
            }${elapsedSec > 0 ? ` — ${elapsedSec}s elapsed` : ""}`
          : "Starting training… (this can take 15 min on GPU, up to an hour on CPU)"}
      </p>
      <p className="bb-caption" style={{ marginTop: 4 }}>
        Feel free to leave this page open or navigate elsewhere — training
        keeps running in the background either way, and progress picks up
        right where it left off when you come back.
      </p>
    </div>
  );
}
