#!/usr/bin/env python3
"""
USDA hemp importer for target states: MN/WI/MI/IL/IA/IN/OH.

Acquisition strategy (reproducible):
1) Discover source via USDA HeMP public search/program pages:
   - https://hemp.ams.usda.gov/s/PublicSearchTool
   - https://www.ams.usda.gov/rules-regulations/hemp/information-for-hemp-growers
2) Ingest only a direct USDA-exported CSV supplied by:
   - env var `USDA_HEMP_CSV_URL`, or
   - CLI flag `--csv-url`
3) If no direct CSV is configured, importer exits blocked with explicit reason.

Reference snapshot dataset (FOIA PDF, non-CSV):
- https://www.ams.usda.gov/sites/default/files/media/FOIAUSDAHempLicensees.pdf

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
from pathlib import Path

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from database.models import get_db_connection, migrate_db

REGISTRY_SOURCE = 'usda_hemp'
SEGMENT = 'hemp_producer'
TARGET_STATES = {'MN', 'WI', 'MI', 'IL', 'IA', 'IN', 'OH'}

DEFAULT_CSV_URL = os.environ.get('USDA_HEMP_CSV_URL', '').strip()
NAME_FIELDS = ['producer_name', 'business_name', 'name']
STATE_FIELDS = ['state', 'producer_state']


def _norm_header(h: str) -> str:
    return (h or '').strip().lower().replace(' ', '_')


def validate_schema(rows: list[dict]):
    if not rows:
        return False, [], ['CSV contained zero rows after header parse']

    headers = {_norm_header(k) for k in rows[0].keys()}
    warnings = []
    errors = []

    has_name = any(f in headers for f in NAME_FIELDS)
    has_state = any(f in headers for f in STATE_FIELDS)

    if not has_name:
        errors.append(f'Missing required name field. Acceptable columns: {NAME_FIELDS}')
    if not has_state:
        errors.append(f'Missing required state field. Acceptable columns: {STATE_FIELDS}')

    optional_expected = ['license_number', 'registration_number', 'status', 'license_status', 'city', 'county', 'postal_code', 'zip']
    missing_optional = [c for c in optional_expected if c not in headers]
    if missing_optional:
        warnings.append(f'Missing optional columns: {missing_optional}')

    return len(errors) == 0, warnings, errors


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


def parse_input_file(input_file: str):
    path = Path(input_file)
    if not path.exists():
        raise FileNotFoundError(input_file)
    if path.suffix.lower() == '.json':
        payload = json.loads(path.read_text(encoding='utf-8'))
        return payload if isinstance(payload, list) else payload.get('rows', [])
    if path.suffix.lower() == '.csv':
        with path.open('r', encoding='utf-8', newline='') as f:
            return list(csv.DictReader(f))
    raise RuntimeError('Manual input must be .csv or .json')


def normalize_row(row: dict):
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
        return None, 'filtered_non_target_state'
    if not name:
        return None, 'reject_missing_name'
    if not state:
        return None, 'reject_missing_state'

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
    }, 'accepted'


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


def _write_summary(summary_path: str, payload: dict):
    if not summary_path:
        return
    out = Path(summary_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')


def main(dry_run=False, csv_url=DEFAULT_CSV_URL, summary_json='', fail_on_empty_fetch=True, input_file=''):
    print(f'[USDA HEMP] Starting import (dry_run={dry_run})')
    migrate_db()

    if input_file:
        rows = parse_input_file(input_file)
        blocking_reason = None
    else:
        rows, blocking_reason = fetch_csv_rows(csv_url)
    if rows is None:
        print(f'[USDA HEMP] BLOCKED: {blocking_reason}')
        print('[USDA HEMP] HINT: discover source at https://hemp.ams.usda.gov/s/PublicSearchTool')
        print('[USDA HEMP] HINT: set USDA_HEMP_CSV_URL or pass --csv-url <usda-export.csv>')
        print('[USDA HEMP] No DB writes performed.')
        summary = {
            'importer': 'usda_hemp',
            'dry_run': dry_run,
            'fetched': 0,
            'new': 0,
            'existing': 0,
            'errors': 1,
            'blocked': True,
            'status': 'blocked_no_source',
            'blocking_reason': blocking_reason,
            'csv_url': csv_url,
            'input_file': input_file,
        }
        _write_summary(summary_json, summary)
        return 3

    schema_ok, schema_warnings, schema_errors = validate_schema(rows)
    for w in schema_warnings:
        print(f'[USDA HEMP] WARNING: {w}')
    if not schema_ok:
        for e in schema_errors:
            print(f'[USDA HEMP] ERROR: {e}')
        summary = {
            'importer': 'usda_hemp',
            'dry_run': dry_run,
            'fetched': 0,
            'new': 0,
            'existing': 0,
            'errors': len(schema_errors),
            'blocked': False,
            'status': 'schema_invalid',
            'schema_warnings': schema_warnings,
            'schema_errors': schema_errors,
            'csv_url': csv_url,
            'input_file': input_file,
        }
        _write_summary(summary_json, summary)
        return 4

    normalized = []
    diagnostics = {}
    for row in rows:
        rec, reason = normalize_row(row)
        diagnostics[reason] = diagnostics.get(reason, 0) + 1
        if rec:
            normalized.append(rec)

    fetched_count = len(normalized)
    print(f'[USDA HEMP] Parsed {fetched_count} records for target states {sorted(TARGET_STATES)}')

    if fetched_count == 0:
        print('[USDA HEMP] ⚠️  Zero records after normalization/filtering.')
        summary = {
            'importer': 'usda_hemp',
            'dry_run': dry_run,
            'fetched': 0,
            'new': 0,
            'existing': 0,
            'errors': 1,
            'blocked': False,
            'status': 'failed_empty_fetch',
            'csv_url': csv_url,
            'input_file': input_file,
            'schema_warnings': schema_warnings,
            'diagnostics': diagnostics,
        }
        _write_summary(summary_json, summary)
        return 2 if fail_on_empty_fetch else 0

    stats = insert_records(normalized, dry_run=dry_run)

    print(f'\n[USDA HEMP] Import complete (dry_run={dry_run}):')
    print(f'  ✅ New records:     {stats["new"]}')
    print(f'  ⏭️  Already existed: {stats["existing"]}')
    print(f'  ❌ Errors:          {stats["errors"]}')

    summary = {
        'importer': 'usda_hemp',
        'dry_run': dry_run,
        'fetched': fetched_count,
        'new': stats['new'],
        'existing': stats['existing'],
        'errors': stats['errors'],
        'blocked': False,
        'status': 'ok',
        'csv_url': csv_url,
            'input_file': input_file,
        'schema_warnings': schema_warnings,
        'diagnostics': diagnostics,
    }
    _write_summary(summary_json, summary)
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Import USDA hemp producer registry CSV for Midwest states')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--csv-url', default=DEFAULT_CSV_URL, help='Direct USDA/export CSV URL')
    parser.add_argument('--input-file', default='', help='Manual fallback path (.csv or .json)')
    parser.add_argument('--summary-json', '--json', dest='summary_json', default='', help='Write machine-readable run summary JSON')
    parser.add_argument('--allow-empty-fetch', action='store_true', help='Do not exit non-zero when zero rows are parsed')
    args = parser.parse_args()
    raise SystemExit(main(
        dry_run=args.dry_run,
        csv_url=args.csv_url,
        summary_json=args.summary_json,
        fail_on_empty_fetch=not args.allow_empty_fetch,
        input_file=args.input_file,
    ))
