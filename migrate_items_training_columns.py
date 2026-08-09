"""
migrate_items_training_columns.py — one-time schema sync for billbro_mvp.db.

Why this exists: api_app.py never calls Base.metadata.create_all(), and
the live database was set up via billbro_database_schema.sql through
TablePlus (per TABLEPLUS_SETUP_GUIDE.md), not via the SQLAlchemy ORM.
database.py's Item/TrainingJob models picked up new columns
(status, batch_number, batch_arrival_date, metrics) over several changes,
but the actual .db file was never updated to match — every endpoint
touching those fields would raise "no such column" against the real
database.

Safe to re-run: checks each column's existence before adding, so running
this twice is a no-op the second time.

Usage:
    python migrate_items_training_columns.py [path/to/billbro_mvp.db]

Defaults to billbro_mvp.db in the current directory if no path given.
"""

import sqlite3
import sys


def _existing_columns(cur: sqlite3.Cursor, table: str) -> set[str]:
    cur.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cur.fetchall()}


def migrate(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    print(f"Migrating: {db_path}\n")

    # ── items: status, batch_number, batch_arrival_date ──────────────────
    items_cols = _existing_columns(cur, "items")

    if "status" not in items_cols:
        cur.execute("ALTER TABLE items ADD COLUMN status TEXT DEFAULT 'pending'")
        # Rows that already existed before this column existed predate the
        # whole Add Item -> Train -> Shelve concept entirely — per
        # API_CONTRACT.md, "item creation and checkout-availability used to
        # be the same event" before this column was introduced. Backfill
        # them to 'shelved' so they don't silently vanish from Checkout
        # the moment status-based filtering goes live. Rows created AFTER
        # this migration via POST /items correctly start 'pending' — the
        # ALTER TABLE ... DEFAULT above only affects the backfill for rows
        # that existed at migration time, not future inserts.
        cur.execute("UPDATE items SET status = 'shelved'")
        print("  items.status: added (backfilled existing rows to 'shelved')")
    else:
        print("  items.status: already present, skipped")

    if "batch_number" not in items_cols:
        cur.execute("ALTER TABLE items ADD COLUMN batch_number TEXT")
        print("  items.batch_number: added")
    else:
        print("  items.batch_number: already present, skipped")

    if "batch_arrival_date" not in items_cols:
        cur.execute("ALTER TABLE items ADD COLUMN batch_arrival_date DATE")
        print("  items.batch_arrival_date: added")
    else:
        print("  items.batch_arrival_date: already present, skipped")

    # ── training_jobs: metrics ────────────────────────────────────────────
    job_cols = _existing_columns(cur, "training_jobs")

    if "metrics" not in job_cols:
        cur.execute("ALTER TABLE training_jobs ADD COLUMN metrics TEXT")
        print("  training_jobs.metrics: added")
    else:
        print("  training_jobs.metrics: already present, skipped")

    # Note on training_jobs.current_epoch: the live column is still
    # declared INTEGER (database.py's ORM model uses String(20)), but this
    # is NOT altered here. SQLite uses type affinity, not strict typing —
    # storing a string like "3/5" in an INTEGER-affinity column works
    # correctly and round-trips as TEXT storage class (verified directly:
    # a test insert of '3/5' into an INTEGER column comes back as '3/5',
    # typeof() 'text'). SQLite also doesn't support ALTER COLUMN type
    # changes without a full table rebuild, so leaving the declared type
    # as-is is the lower-risk choice here — it's a cosmetic mismatch
    # against the ORM model, not a functional bug.

    # ── store_settings: new table entirely (Week 7, Admin page) ──────────
    # Whole table is new, not just a column, so this is a CREATE TABLE IF
    # NOT EXISTS rather than an ALTER TABLE — same idempotent, safe-to-
    # rerun spirit as the rest of this script. Column defaults mirror
    # database.py's StoreSettings model exactly. No backfill needed since
    # GET /admin/settings upserts a default row on first read anyway
    # (_get_or_create_settings in api_app.py) — this just makes sure the
    # table itself exists before that first read happens.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS store_settings (
            store_id TEXT PRIMARY KEY,
            tax_rate_pct REAL DEFAULT 18.0,
            currency_symbol TEXT DEFAULT '₹',
            low_stock_default_threshold INTEGER DEFAULT 5,
            updated_at TIMESTAMP
        )
    """)
    print("  store_settings: table created (or already existed)")

    conn.commit()
    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "billbro_mvp.db"
    migrate(db_path)
