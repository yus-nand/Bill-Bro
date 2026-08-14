// src/components/TourOverlay.jsx
// Visual half of the guided tour — a spotlight cutout around the current
// step's target (four dimmed panels around it, rather than an SVG mask,
// so it works with zero extra dependencies) plus a small tooltip card
// with the step copy and Back/Next/Skip controls.

import { useTour } from "../context/TourContext.jsx";

const PAD = 8;

export default function TourOverlay() {
  const { active, index, total, step, rect, next, prev, stop, seen, start, markSeen } = useTour();

  if (!active) {
    // First-visit nudge — small dismissible card, not a blocking modal.
    // Only shown once ever (per browser), tracked the same localStorage
    // flag the tour itself sets when finished or skipped.
    if (seen) return null;
    return (
      <div className="bb-tour-prompt">
        <p className="bb-tour-prompt-title">New to BillBro?</p>
        <p className="bb-tour-prompt-body">Take a 2-minute tour of the main features.</p>
        <div className="bb-tour-prompt-actions">
          <button type="button" className="bb-btn bb-btn-secondary bb-btn-small" onClick={markSeen}>
            Maybe later
          </button>
          <button type="button" className="bb-btn bb-btn-primary bb-btn-small" onClick={start}>
            Take the tour
          </button>
        </div>
      </div>
    );
  }

  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const box = rect
    ? {
        top: Math.max(0, rect.top - PAD),
        left: Math.max(0, rect.left - PAD),
        width: Math.min(vw, rect.width + PAD * 2),
        height: Math.min(vh, rect.height + PAD * 2),
      }
    : null;

  // Tooltip placement: below the target if there's room, otherwise above;
  // centered on screen entirely when the target couldn't be located.
  let tooltipStyle;
  if (box) {
    const spaceBelow = vh - (box.top + box.height);
    const placeBelow = spaceBelow > 180 || spaceBelow > box.top;
    const left = Math.min(Math.max(12, box.left), vw - 332);
    tooltipStyle = placeBelow
      ? { top: box.top + box.height + 14, left }
      : { top: Math.max(12, box.top - 14), left, transform: "translateY(-100%)" };
  }

  return (
    <div className="bb-tour-root" role="dialog" aria-label="Guided tour">
      {box ? (
        <>
          <div className="bb-tour-dim" style={{ top: 0, left: 0, right: 0, height: box.top }} />
          <div
            className="bb-tour-dim"
            style={{ top: box.top + box.height, left: 0, right: 0, bottom: 0 }}
          />
          <div
            className="bb-tour-dim"
            style={{ top: box.top, left: 0, width: box.left, height: box.height }}
          />
          <div
            className="bb-tour-dim"
            style={{
              top: box.top,
              left: box.left + box.width,
              right: 0,
              height: box.height,
            }}
          />
          <div className="bb-tour-ring" style={box} />
        </>
      ) : (
        <div className="bb-tour-dim" style={{ inset: 0 }} />
      )}

      <div
        className="bb-tour-tooltip"
        style={tooltipStyle || { top: "50%", left: "50%", transform: "translate(-50%, -50%)" }}
      >
        <p className="bb-tour-progress">
          Step {index + 1} of {total}
        </p>
        <h3>{step.title}</h3>
        <p>{step.body}</p>
        <div className="bb-tour-actions">
          <button type="button" className="bb-btn bb-btn-secondary bb-btn-small" onClick={stop}>
            Skip
          </button>
          <div style={{ display: "flex", gap: 8 }}>
            {index > 0 && (
              <button type="button" className="bb-btn bb-btn-secondary bb-btn-small" onClick={prev}>
                Back
              </button>
            )}
            <button type="button" className="bb-btn bb-btn-primary bb-btn-small" onClick={next}>
              {index === total - 1 ? "Done" : "Next"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
