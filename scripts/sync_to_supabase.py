#!/usr/bin/env python3
"""
sync_to_supabase.py — Sync enriched leads from SQLite to Supabase prospects table.

Deduplicates on email (skip existing). Batch inserts 50 at a time.
NEVER sends emails. Data sync only.

Usage:
    python3 scripts/sync_to_supabase.py [--dry-run]
"""

import argparse
import json
import os
import sqlite3
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "data" / "leads.db"
SECRETS_FILE = Path.home() / ".openclaw" / ".secrets" / "master.env"

BATCH_SIZE = 50


# ---------------------------------------------------------------------------
# Env loading
# ---------------------------------------------------------------------------
def load_env(path: Path) -> None:
    """Load KEY=VALUE pairs from a shell env file (skip comments/blanks/exports)."""
    if not path.exists():
        print(f"[warn] Secrets file not found: {path} — relying on existing env vars")
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Strip leading 'export '
            if line.startswith("export "):
                line = line[len("export "):]
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


# ---------------------------------------------------------------------------
# Supabase helpers (urllib only — no requests)
# ---------------------------------------------------------------------------
def supabase_headers(service_role_key: str) -> dict:
    return {
        "apikey": service_role_key,
        "Authorization": f"Bearer {service_role_key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }


def fetch_existing_emails(base_url: str, key: str) -> set:
    """Fetch all emails already in the prospects table."""
    emails = set()
    limit = 1000
    offset = 0

    while True:
        url = (
            f"{base_url}/rest/v1/prospects"
            f"?select=email&limit={limit}&offset={offset}"
        )
        req = urllib.request.Request(
            url,
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
                if not data:
                    break
                for row in data:
                    if row.get("email"):
                        emails.add(row["email"].strip().lower())
                if len(data) < limit:
                    break
                offset += limit
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            print(f"[error] Failed to fetch existing emails: {e.code} {body}")
            sys.exit(1)

    return emails


def batch_insert(
    base_url: str,
    key: str,
    rows: list,
    dry_run: bool,
) -> tuple[int, int]:
    """
    Insert a batch of rows into prospects. Returns (inserted, errors).
    Uses ignoreDuplicates via Prefer header — skips silently on email conflict.
    """
    if dry_run:
        return len(rows), 0

    url = f"{base_url}/rest/v1/prospects?on_conflict=email"
    payload = json.dumps(rows).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers=supabase_headers(key),
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            # 200/201 = success; with ignore-duplicates + return=minimal body is empty
            return len(rows), 0
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  [error] Batch insert failed: {e.code} — {body[:300]}")
        return 0, len(rows)


# ---------------------------------------------------------------------------
# SQLite query
# ---------------------------------------------------------------------------
SEGMENT_ALIASES: dict[str, tuple[str, ...]] = {
    "hemp_producer":   ("hemp", "hemp_producer"),
    "cannabis_grower": ("cannabis", "cannabis_grower"),
}


def load_leads(db_path: Path, segment: str | None = None) -> list[dict]:
    """Load qualifying leads from SQLite, optionally filtered by segment.

    Handles aliases: 'hemp_producer' matches both 'hemp' and 'hemp_producer' in DB.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    base_query = """
        SELECT
            business_name,
            owner_name,
            phone,
            owner_email,
            city,
            state,
            zip,
            score,
            tier,
            tier_override,
            segment,
            registry_id,
            business_type,
            production_method,
            is_organic_certified,
            organic_focus,
            acreage,
            personalization_status,
            custom_line,
            email_angle
        FROM leads
        WHERE (
            (tier_override IS NOT NULL AND tier_override IN ('A', 'B'))
            OR (tier IN ('A', 'B'))
        )
        AND owner_email IS NOT NULL
        AND owner_email != ''
    """
    params: list = []
    if segment and segment != "all":
        aliases = SEGMENT_ALIASES.get(segment)
        if aliases:
            placeholders = ", ".join("?" * len(aliases))
            base_query += f" AND segment IN ({placeholders})"
            params.extend(aliases)
        else:
            base_query += " AND segment = ?"
            params.append(segment)
    base_query += " ORDER BY score DESC"

    cur.execute(base_query, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


# ---------------------------------------------------------------------------
# Row mapping
# ---------------------------------------------------------------------------
def map_row(lead: dict) -> dict:
    """Map a SQLite lead dict to a Supabase prospects row."""
    effective_tier = lead.get("tier_override") or lead.get("tier") or ""
    score = lead.get("score") or 0

    row: dict = {
        "company_name": lead.get("business_name") or "",
        "contact_name": lead.get("owner_name") or "",
        "phone": lead.get("phone") or "",
        "email": (lead.get("owner_email") or "").strip().lower(),
        "city": lead.get("city") or "",
        "state": lead.get("state") or "",
        "zip": lead.get("zip") or "",
        "status": "prospect",
        "notes": f"Score: {score}, Tier: {effective_tier}",
        "source": "pipeline_sync",
        "enrichment_tier": effective_tier,
        "segment": lead.get("segment") or "nursery",
        # Enrichment fields — Gemini/pipeline data
        "business_type": lead.get("business_type") or None,
        "production_method": lead.get("production_method") or None,
        "is_organic_certified": lead.get("is_organic_certified"),
        "organic_focus": lead.get("organic_focus"),
        "acreage": lead.get("acreage") or None,
        # custom_line = Gemini personalization notes; email_angle = unique outreach hook
        "personalization_notes": lead.get("custom_line") or None,
        "unique_hook": lead.get("email_angle") or None,
    }

    # SQLite stores booleans as 0/1 integers — convert to Python bool for JSON
    for bool_field in ("is_organic_certified", "organic_focus"):
        val = row[bool_field]
        if isinstance(val, int):
            row[bool_field] = bool(val)

    return row


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync enriched leads from SQLite → Supabase prospects"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would sync without writing to Supabase",
    )
    parser.add_argument(
        "--segment",
        default=None,
        help="Filter to a specific segment (e.g. hemp, nursery, cannabis_grower)",
    )
    args = parser.parse_args()

    # Load secrets
    load_env(SECRETS_FILE)

    # Support both SUPABASE_URL and NEXT_PUBLIC_SUPABASE_URL (either may be set)
    supabase_url = (
        os.environ.get("SUPABASE_URL")
        or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
        or ""
    ).rstrip("/")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

    if not supabase_url or not service_key:
        print("[error] SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set.")
        sys.exit(1)

    seg_label = f" [segment={args.segment}]" if args.segment else " [all segments]"
    print(f"{'[DRY RUN] ' if args.dry_run else ''}sync_to_supabase starting at {datetime.now():%Y-%m-%d %H:%M:%S}{seg_label}")
    print(f"  Source DB : {DB_PATH}")
    print(f"  Target    : {supabase_url}/rest/v1/prospects")

    # Load leads
    leads = load_leads(DB_PATH, segment=args.segment)
    print(f"\n  Qualifying leads in SQLite : {len(leads)}")

    if not leads:
        print("  Nothing to sync.")
        return

    # Build upsert list (all qualifying leads — merge-duplicates handles existing records)
    seen_emails: set = set()
    to_upsert = []
    for lead in leads:
        email = (lead.get("owner_email") or "").strip().lower()
        if not email or email in seen_emails:
            continue
        seen_emails.add(email)
        to_upsert.append(map_row(lead))

    print(f"  Leads to upsert           : {len(to_upsert)}")

    if args.dry_run and to_upsert:
        print("\n  [dry-run] Sample rows (first 3):")
        for row in to_upsert[:3]:
            print(f"    • {row['email']} | {row['company_name']} | Tier {row['enrichment_tier']} | biz={row.get('business_type')} | prod={row.get('production_method')}")

    if not to_upsert:
        print("\nSynced 0 leads, 0 errors")
        return

    to_insert = to_upsert  # alias for loop below

    # Batch insert
    total_synced = 0
    total_errors = 0

    for i in range(0, len(to_insert), BATCH_SIZE):
        batch = to_insert[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (len(to_insert) + BATCH_SIZE - 1) // BATCH_SIZE

        if not args.dry_run:
            print(f"  Batch {batch_num}/{total_batches} ({len(batch)} rows)…", end=" ", flush=True)

        inserted, errors = batch_insert(supabase_url, service_key, batch, args.dry_run)
        total_synced += inserted
        total_errors += errors

        if not args.dry_run:
            status = "✓" if errors == 0 else f"✗ {errors} errors"
            print(status)

    print(
        f"\nSynced {total_synced} leads (upserted), "
        f"{total_errors} errors"
    )


if __name__ == "__main__":
    main()
