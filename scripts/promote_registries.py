#!/usr/bin/env python3
"""
Promote registry records to the leads table.

For each registry record where promoted_at IS NULL:
  - Maps segment: cannabis_grower → 'cannabis', hemp_producer → 'hemp'
  - Deduplicates by (business_name, state) — skips if lead already exists
  - Inserts lead and back-fills registries.promoted_at + registries.lead_id

Usage:
  python3 scripts/promote_registries.py --dry-run   # preview counts
  python3 scripts/promote_registries.py             # live run
  python3 scripts/promote_registries.py --source or_olcc  # filter by source
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from database.models import get_db_connection, migrate_db

SEGMENT_MAP = {
    'cannabis_grower': 'cannabis',
    'hemp_producer': 'hemp',
}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def promote(dry_run: bool = False, source_filter: str = '', summary_json: str = ''):
    migrate_db()

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Fetch unpromoted registries
    query = 'SELECT * FROM registries WHERE promoted_at IS NULL'
    params: list = []
    if source_filter:
        query += ' AND registry_source = ?'
        params.append(source_filter)

    cur.execute(query, params)
    rows = cur.fetchall()

    total = len(rows)
    inserted = 0
    skipped_dup = 0
    skipped_no_name = 0
    skipped_unknown_segment = 0
    errors = 0

    print(f'[promote_registries] {"DRY RUN — " if dry_run else ""}Found {total} unpromoted registries')

    ts = now_iso()

    for row in rows:
        business_name = (row['business_name'] or '').strip()
        if not business_name:
            skipped_no_name += 1
            continue

        raw_segment = (row['segment'] or '').strip()
        lead_segment = SEGMENT_MAP.get(raw_segment)
        if lead_segment is None:
            print(f'  [WARN] Unknown segment "{raw_segment}" for {business_name} — skipping')
            skipped_unknown_segment += 1
            continue

        state = (row['state'] or '').strip()
        city = (row['city'] or '').strip()
        zip_code = (row['zip'] or '').strip()
        phone = (row['phone'] or '').strip()
        website = (row['website'] or '').strip()
        contact_name = (row['contact_name'] or '').strip() or business_name
        registry_id = row['id']

        # Dedup check: (business_name, state) in leads
        cur.execute(
            'SELECT id FROM leads WHERE business_name = ? AND state = ? LIMIT 1',
            (business_name, state),
        )
        existing = cur.fetchone()
        if existing:
            if not dry_run:
                # Still back-fill the lead_id / promoted_at so we don't revisit
                existing_lead_id = existing['id']
                cur.execute(
                    'UPDATE registries SET promoted_at = ?, lead_id = ? WHERE id = ?',
                    (ts, existing_lead_id, registry_id),
                )
            skipped_dup += 1
            continue

        if dry_run:
            inserted += 1
            if inserted <= 5:
                print(f'  [DRY] Would insert: {business_name} | {state} | {lead_segment}')
            continue

        try:
            cur.execute(
                '''INSERT INTO leads
                   (business_name, city, state, zip, phone, website,
                    owner_name, segment, registry_id,
                    created_at, updated_at,
                    enrichment_status, scrape_status, gemini_status,
                    personalization_status, data_source)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?,
                           ?, ?,
                           'pending', 'pending', 'pending',
                           'pending', ?)''',
                (
                    business_name, city, state, zip_code, phone, website,
                    contact_name, lead_segment, registry_id,
                    ts, ts,
                    row['registry_source'],
                ),
            )
            lead_id = cur.lastrowid

            # Back-fill registry
            cur.execute(
                'UPDATE registries SET promoted_at = ?, lead_id = ? WHERE id = ?',
                (ts, lead_id, registry_id),
            )
            inserted += 1

        except sqlite3.Error as e:
            print(f'  [ERROR] {business_name}: {e}')
            errors += 1

    if not dry_run:
        conn.commit()
    conn.close()

    print(f'\n[promote_registries] Results (dry_run={dry_run}):')
    print(f'  Total unpromoted:       {total}')
    print(f'  ✅ Inserted (or would): {inserted}')
    print(f'  ⏭️  Skipped (dup):       {skipped_dup}')
    print(f'  ⚠️  Skipped (no name):   {skipped_no_name}')
    print(f'  ⚠️  Skipped (bad seg):   {skipped_unknown_segment}')
    print(f'  ❌ Errors:              {errors}')

    payload = {
        'script': 'promote_registries',
        'dry_run': dry_run,
        'source_filter': source_filter or 'all',
        'total_unpromoted': total,
        'inserted': inserted,
        'skipped_dup': skipped_dup,
        'skipped_no_name': skipped_no_name,
        'skipped_unknown_segment': skipped_unknown_segment,
        'errors': errors,
        'timestamp': ts,
    }

    if summary_json:
        out = Path(summary_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
        print(f'  📄 Summary → {summary_json}')

    return payload


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Promote registry records to leads table')
    parser.add_argument('--dry-run', action='store_true', help='Preview only — no writes')
    parser.add_argument('--source', default='', help='Filter by registry_source (e.g. or_olcc)')
    parser.add_argument('--summary-json', default='', help='Write JSON summary to this path')
    args = parser.parse_args()

    result = promote(
        dry_run=args.dry_run,
        source_filter=args.source,
        summary_json=args.summary_json,
    )
    sys.exit(0 if result['errors'] == 0 else 1)
