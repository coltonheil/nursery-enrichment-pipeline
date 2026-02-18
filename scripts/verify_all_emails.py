#!/usr/bin/env python3
"""
verify_all_emails.py — Run Reoon email verification on all leads with emails.

Updates:
  - email_verified (1=yes, 0=no)
  - email_verification_result (JSON string)
  - email_confidence (0-100)

Skips leads already verified (email_verified IS NOT NULL).

Usage:
    cd ~/repos/nursery-enrichment-pipeline
    python3 scripts/verify_all_emails.py [--limit N] [--dry-run]
"""

import argparse
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

# Load secrets
SECRETS_FILE = Path.home() / ".openclaw" / ".secrets" / "master.env"
PROJECT_ENV = Path(__file__).parent.parent / ".env"


def load_env(path: Path) -> None:
    if not path.exists():
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export "):]
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


# Load env files (project .env first, then master.env for overrides)
load_env(PROJECT_ENV)
load_env(SECRETS_FILE)

# Now import after env is loaded
sys.path.insert(0, str(Path(__file__).parent.parent))
from enrichment.email_verifier_api import verify_email, ReoonProvider


DB_PATH = Path(__file__).parent.parent / "data" / "leads.db"
DELAY_SECONDS = 0.5   # Reoon rate limit buffer
BATCH_COMMIT = 10     # Commit to DB every N records


def load_pending_leads(db_path: Path, limit: int = 0) -> list[dict]:
    """Load leads that need verification."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    query = """
        SELECT id, business_name, owner_email, email_verified
        FROM leads
        WHERE owner_email IS NOT NULL
          AND owner_email != ''
          AND email_verified IS NULL
        ORDER BY COALESCE(tier_override, tier) ASC, score DESC
    """
    if limit:
        query += f" LIMIT {limit}"

    cur.execute(query)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def update_lead(conn: sqlite3.Connection, lead_id: int, result) -> None:
    """Update verification results in SQLite."""
    # email_verified: 1 if valid or catch_all (usable), 0 otherwise
    is_verified = 1 if result.is_usable() else 0

    cur = conn.cursor()
    cur.execute(
        """
        UPDATE leads SET
            email_verified = ?,
            email_verification_result = ?,
            email_confidence = ?,
            updated_at = datetime('now')
        WHERE id = ?
        """,
        (
            is_verified,
            json.dumps(result.to_dict()),
            result.confidence,
            lead_id,
        ),
    )


def main():
    parser = argparse.ArgumentParser(description="Run Reoon email verification on all pending leads")
    parser.add_argument("--limit", type=int, default=0, help="Max leads to process (0=all)")
    parser.add_argument("--dry-run", action="store_true", help="Test API but don't write to DB")
    args = parser.parse_args()

    # Verify Reoon is configured
    reoon = ReoonProvider()
    if not reoon.is_configured():
        print("[error] REOON_API_KEY not configured. Check .env or master.env.")
        sys.exit(1)
    print(f"✓ Reoon API key configured")

    # Load pending leads
    leads = load_pending_leads(DB_PATH, args.limit)
    total = len(leads)
    print(f"Leads to verify: {total}")
    if not leads:
        print("Nothing to do — all leads already verified.")
        return

    if args.dry_run:
        print("[DRY RUN] Testing with first 3 leads...")
        leads = leads[:3]

    # Counters
    counts = {"valid": 0, "catch_all": 0, "invalid": 0, "unknown": 0, "error": 0}

    # Connect to DB
    conn = sqlite3.connect(str(DB_PATH))

    try:
        for i, lead in enumerate(leads, 1):
            email = lead["owner_email"].strip()
            biz = lead["business_name"] or "Unknown"

            print(f"[{i:3}/{len(leads)}] {email:<45} ({biz[:30]})", end=" ", flush=True)

            result = verify_email(email)

            # Categorize
            status = result.status
            if status == "valid":
                counts["valid"] += 1
                marker = "✓ valid"
            elif status in ("catch_all", "catch-all"):
                counts["catch_all"] += 1
                marker = "~ catch-all"
            elif status == "invalid":
                counts["invalid"] += 1
                marker = "✗ invalid"
            else:
                if result.error:
                    counts["error"] += 1
                    marker = f"? error: {result.error[:30]}"
                else:
                    counts["unknown"] += 1
                    marker = f"? {status}"

            print(f"{marker} (conf: {result.confidence})")

            if not args.dry_run:
                update_lead(conn, lead["id"], result)

                # Batch commit
                if i % BATCH_COMMIT == 0:
                    conn.commit()
                    print(f"  → committed batch at {i}/{len(leads)}")

            # Rate limit delay
            if i < len(leads):
                time.sleep(DELAY_SECONDS)

        if not args.dry_run:
            conn.commit()

    finally:
        conn.close()

    # Final summary
    print()
    print("=" * 60)
    print("VERIFICATION RESULTS")
    print("=" * 60)
    print(f"  Total processed : {len(leads)}")
    print(f"  ✓ Valid         : {counts['valid']}")
    print(f"  ~ Catch-all     : {counts['catch_all']}")
    print(f"  ✗ Invalid       : {counts['invalid']}")
    print(f"  ? Unknown       : {counts['unknown']}")
    print(f"  ! Errors        : {counts['error']}")
    usable = counts['valid'] + counts['catch_all']
    print(f"  → Usable (v+ca) : {usable}")
    if args.dry_run:
        print()
        print("[DRY RUN] No DB writes performed.")
    print("=" * 60)


if __name__ == "__main__":
    main()
