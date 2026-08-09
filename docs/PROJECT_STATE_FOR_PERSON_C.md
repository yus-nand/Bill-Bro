# BillBro — Project State for Person C (Frontend, this side)

Consolidated snapshot as of 2026-08-09. `FRONTEND_CONTEXT.md` and
`API_CONTRACT.md` in this folder remain the detailed references — this
is the short version of where things actually stand right now.

## Live and integrated

Checkout (photo → `/detect` → editable cart → `/checkout/bill` →
receipt), Inventory (`/inventory` + Restock), Alerts, Add Item (details
→ photo capture → training → shelved/failed). All endpoints exist and
are wired. Checkout-matching bug, both `/detect` bugs, and the training
upload bug are all confirmed fixed in real code — but **no full
end-to-end run against a live backend has happened from this side yet**.

## This session: backend audit + Admin build (in Person A's worktree, not pushed)

Pulled `Person-A` into a local worktree and read every route
line-by-line rather than trusting doc claims. Found and fixed four
previously-unknown bugs (checkout body-format, inventory query-param,
duplicate-name 500, missing status field), one critical one (training
upload was completely non-functional — fixed on both sides, including
a new `toClassName()` slugify helper in `AddItem.jsx`), applied the
`/models/active` fix, and built the entire Admin backend
(`GET`/`PUT /admin/settings`, `POST /admin/bulk_upload`) from scratch.
None of the backend-side fixes are pushed — sitting in the worktree for
Person A to review.

## What's actually blocking a real end-to-end test

1. Person A reviewing/pushing the worktree fixes above.
2. The base training dataset infra decision (Person B's
   `ReplayPool.bootstrap_from_base()` needs ~180 real images never
   committed to the repo) — blocks Add Item specifically, not Checkout.

## Not yet built on this side

- **`Admin.jsx`** — still a roadmap placeholder. The backend now has
  real endpoints to wire it up against (`GET`/`PUT /admin/settings`,
  `POST /admin/bulk_upload`) — this is the next natural frontend task.
- **Fuller Models page** — `GET /models`, activate, rollback now exist
  in the worktree too, currently unused by any page.
- `PATCH /inventory/{id}` manual-adjust UI — endpoint exists (and just
  had its query-param bug fixed), no UI calls it yet.

## Housekeeping done this session

Cleared 17 stale handoff/sync docs (`RESPONSE_TO_*`, `FOR_PERSON_*`,
`CONTEXT_FOR_PERSON_A*`, `SYNC_*`, junk files) from the Person A and
Person B worktrees — those were superseded by direct code reads and
this doc. `Context/` folder itself was left untouched; this file and
its two siblings (`PROJECT_STATE_FOR_PERSON_A.md`,
`PROJECT_STATE_FOR_PERSON_B.md`) are new additions, not replacements.
