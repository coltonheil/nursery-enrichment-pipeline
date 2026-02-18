#!/usr/bin/env python3
"""
USDA hemp importer for target states: MN/WI/MI/IL/IA/IN/OH.

Notes:
- USDA HeMP producer-level registry is behind authenticated HeMP portal flows.
- This importer supports direct CSV ingestion when a USDA-exported CSV is provided,
  and documents the blocking reason when no CSV source is available.

Registry source: usda_hemp
Segment: hemp_producer
"""

import argparse
import csv
import io
import json
import os
import sqlite3
import sys

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from database.models import get_db_connection, migrate_db

REGISTRY_SOURCE = 'usda_hemp'
SEGMENT = 'hemp_producer'
TARGET_STATES = {'MN', 'WI', 'MI', 'IL', 'IA', 'IN', 'OH'}

# Placeholder for direct USDA-export CSV URL when available.
DEFAULT_CSV_URL = os.environ.get('USDA_HEMP_CSV_URL', '').strip()


def fetch_csv_rows(csv_url: str):
    if not csv_url:
        return None, (
            'USDA HeMP producer-level public CSV URL not configured. '
            'Portal endpoints are authenticated/JS-driven. Set USDA_HEMP_CSV_URL '
            'or pass --csv-url with an exported USDA producer CSV.'
        )

    r = requests.get(csv_url, timeout=90)
    r.raise_for_status()
    text = r.text
    reader = csv.DictReader(io.StringIO(text))
    return list(reader), None


def normalize_row(row: dict):
    # Flexible field mapping for various USDA export styles
    name = (row.get('producer_name') or row.get('business_name') or row.get('name') or '').strip()
    state = (row.get('state') or row.get('producer_state') or '').strip().upper()
    city = (row.get('city') or row.get('producer_city') or '').strip()
    county = (row.get('county') or row.get('producer_county') or '').strip()
    zip_code = (row.get('zip') or row.get('postal_code') or '').strip()
    license_number = (row.get('license_number') or row.get('registration_number') or '').strip() or None
    license_status = (row.get('status') or row.get('license_status') or 'active').strip().lower()
    license_type = (row.get('license_type') or 'hemp_producer').strip().lower()
    acreage = (row.get('acreage') or row.get('total_acres') or '').strip()

    if state and state not in TARGET_STATES:
        return None
    if not name or not state:
        return None

    raw = dict(row)
    if acreage:
        raw['acreage'] = acreage

    return {
        'business_name': name,
        'license_number': license_number,
        'license_type': license_type,
        'license_status': license_status,
        'address': (row.get('address') or row.get('street') or '').strip(),
        'city': city,
        'state': state,
        'zip': zip_code,
        'county': county,
        'raw_data': json.dumps(raw),
    }


def insert_records(records, dry_run=False):
    conn = get_db_connection()
    cur = conn.cursor()

    new_count = 0
    existing_count = 0
    error_count = 0

    for rec in records:
        name = rec['business_name']
        city = rec.get('city', '')
        license_number = rec.get('license_number')

        if license_number:
            cur.execute(
                'SELECT 1 FROM registries WHERE license_number = ? AND registry_source = ? LIMIT 1',
                (license_number, REGISTRY_SOURCE),
            )
        else:
            cur.execute(
                'SELECT 1 FROM registries WHERE business_name = ? AND city = ? AND state = ? AND registry_source = ? LIMIT 1',
                (name, city, rec['state'], REGISTRY_SOURCE),
            )
        if cur.fetchone():
            existing_count += 1
            continue

        if dry_run:
            new_count += 1
            continue

        try:
            cur.execute(
                '''INSERT OR IGNORE INTO registries
                   (business_name, license_number, license_type, license_status,
                    address, city, state, zip, county,
                    registry_source, segment, raw_data, imported_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)''',
                (
                    name,
                    license_number,
                    rec.get('license_type', 'hemp_producer'),
                    rec.get('license_status', 'active'),
                    rec.get('address', ''),
                    city,
                    rec['state'],
                    rec.get('zip', ''),
                    rec.get('county', ''),
                    REGISTRY_SOURCE,
                    SEGMENT,
                    rec.get('raw_data', '{}'),
                ),
            )
            if cur.rowcount > 0:
                new_count += 1
            else:
                existing_count += 1
        except sqlite3.Error:
            error_count += 1

    if not dry_run:
        conn.commit()
    conn.close()
    return {'new': new_count, 'existing': existing_count, 'errors': error_count}


def main(dry_run=False, csv_url=DEFAULT_CSV_URL):
    print(f'[USDA HEMP] Starting import (dry_run={dry_run})')
    migrate_db()

    rows, blocking_reason = fetch_csv_rows(csv_url)
    if rows is None:
        print(f'[USDA HEMP] BLOCKED: {blocking_reason}')
        print('[USDA HEMP] No DB writes performed.')
        return

    normalized = []
    for row in rows:
        rec = normalize_row(row)
        if rec:
            normalized.append(rec)

    print(f'[USDA HEMP] Parsed {len(normalized)} records for target states {sorted(TARGET_STATES)}')
    stats = insert_records(normalized, dry_run=dry_run)

    print(f'\n[USDA HEMP] Import complete (dry_run={dry_run}):')
    print(f'  ✅ New records:     {stats["new"]}')
    print(f'  ⏭️  Already existed: {stats["existing"]}')
    print(f'  ❌ Errors:          {stats["errors"]}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Import USDA hemp producer registry CSV for Midwest states')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--csv-url', default=DEFAULT_CSV_URL, help='Direct USDA/export CSV URL')
    args = parser.parse_args()
    main(dry_run=args.dry_run, csv_url=args.csv_url)
