#!/usr/bin/env python3
"""
Montana Revenue cannabis cultivator importer.

Phase 1 importer with explicit blocker behavior and manual-source support:
- Accepts PDF URL/path (best-effort parsing)
- Accepts manual CSV/JSON input (`--input-file`) as fallback source
- Returns clear blocked status when no source is provided

Registry source: mt_revenue
Segment: cannabis_grower
"""

import argparse
import csv
import json
import os
import re
import sqlite3
import sys
import tempfile
from pathlib import Path

import pdfplumber
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from database.models import get_db_connection, migrate_db

REGISTRY_SOURCE = 'mt_revenue'
SEGMENT = 'cannabis_grower'


def _load_pdf_path(pdf_source: str):
    if not pdf_source:
        return None
    if pdf_source.startswith('http://') or pdf_source.startswith('https://'):
        r = requests.get(pdf_source, timeout=60)
        r.raise_for_status()
        fd, path = tempfile.mkstemp(prefix='mt_revenue_', suffix='.pdf')
        os.close(fd)
        with open(path, 'wb') as f:
            f.write(r.content)
        return path
    if os.path.exists(pdf_source):
        return pdf_source
    raise FileNotFoundError(pdf_source)


def _normalize_manual_row(row: dict):
    name = (row.get('business_name') or row.get('name') or '').strip()
    if not name:
        return None, 'reject_missing_name'

    state = (row.get('state') or 'MT').strip().upper()
    if state != 'MT':
        return None, 'filtered_non_mt_state'

    license_number = (row.get('license_number') or row.get('license') or '').strip() or None
    city = (row.get('city') or '').strip()
    zip_code = (row.get('zip') or row.get('postal_code') or '').strip()

    rec = {
        'business_name': name,
        'license_number': license_number,
        'license_type': (row.get('license_type') or 'cannabis_cultivator').strip().lower(),
        'license_status': (row.get('status') or row.get('license_status') or 'active').strip().lower(),
        'address': (row.get('address') or '').strip(),
        'city': city,
        'state': 'MT',
        'zip': zip_code,
        'county': (row.get('county') or '').strip(),
        'raw_data': json.dumps(dict(row)),
    }
    return rec, 'accepted_manual'


def parse_manual_input(input_file: str):
    path = Path(input_file)
    if not path.exists():
        raise FileNotFoundError(input_file)

    diagnostics = {'accepted_manual': 0}
    records = []

    if path.suffix.lower() == '.json':
        payload = json.loads(path.read_text(encoding='utf-8'))
        rows = payload if isinstance(payload, list) else payload.get('rows', [])
    elif path.suffix.lower() == '.csv':
        with path.open('r', encoding='utf-8', newline='') as f:
            rows = list(csv.DictReader(f))
    else:
        raise RuntimeError('Manual input must be .csv or .json')

    for row in rows:
        rec, reason = _normalize_manual_row(row)
        diagnostics[reason] = diagnostics.get(reason, 0) + 1
        if rec:
            records.append(rec)

    return records, diagnostics


def parse_pdf(pdf_path: str):
    records = []
    diagnostics = {
        'lines_total': 0,
        'matched_pdf': 0,
        'unmatched_pdf': 0,
        'reject_missing_name_pdf': 0,
    }

    # Column geometry from official MT PDF:
    # Licensee Name | City | Location Name | Phone
    NAME_MAX_X = 216
    CITY_MIN_X, CITY_MAX_X = 216, 288
    LOC_MIN_X, LOC_MAX_X = 288, 522
    PHONE_MIN_X = 522

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            words = page.extract_words() or []
            rows = {}
            for w in words:
                top = round(float(w.get('top', 0)), 1)
                rows.setdefault(top, []).append(w)

            pending_name = ''
            for _, row_words in sorted(rows.items(), key=lambda kv: kv[0]):
                row_words = sorted(row_words, key=lambda x: x['x0'])
                texts = [w['text'] for w in row_words]
                line = ' '.join(texts).strip()
                if not line:
                    continue
                diagnostics['lines_total'] += 1

                # Skip header/footer/noise lines
                lower = line.lower()
                if any(k in lower for k in [
                    'governor', 'director', 'cannabis control division', 'licensed cultivator locations',
                    'licensee’s name city location name phone', 'page of', 'revenue.mt.gov', 'montana relay'
                ]):
                    continue

                has_phone = any(w['x0'] >= PHONE_MIN_X for w in row_words)
                if not has_phone:
                    # Wrapped continuation line for long business names
                    if all(w['x0'] < NAME_MAX_X for w in row_words):
                        pending_name = (pending_name + ' ' + line).strip() if pending_name else line
                    diagnostics['unmatched_pdf'] += 1
                    continue

                name_tokens = [w['text'] for w in row_words if w['x0'] < NAME_MAX_X]
                city_tokens = [w['text'] for w in row_words if CITY_MIN_X <= w['x0'] < CITY_MAX_X]
                loc_tokens = [w['text'] for w in row_words if LOC_MIN_X <= w['x0'] < LOC_MAX_X]
                phone_tokens = [w['text'] for w in row_words if w['x0'] >= PHONE_MIN_X]

                name = (' '.join(name_tokens)).strip()
                if pending_name:
                    name = (pending_name + ' ' + name).strip() if name else pending_name
                    pending_name = ''

                city = (' '.join(city_tokens)).strip()
                if not city:
                    # fallback: first token from location column
                    city = (loc_tokens[0] if loc_tokens else '').strip()

                phone = ' '.join(phone_tokens).strip()

                if not name:
                    diagnostics['reject_missing_name_pdf'] += 1
                    continue

                diagnostics['matched_pdf'] += 1
                records.append({
                    'business_name': name,
                    'license_number': None,
                    'license_type': 'cannabis_cultivator',
                    'license_status': 'active',
                    'address': ' '.join(loc_tokens).strip(),
                    'city': city,
                    'state': 'MT',
                    'zip': '',
                    'county': '',
                    'raw_data': json.dumps({'line': line, 'phone': phone, 'source': os.path.basename(pdf_path)}),
                })

    return records, diagnostics


def insert_records(records, dry_run=False):
    conn = get_db_connection()
    cur = conn.cursor()
    new_count = existing_count = error_count = 0

    for rec in records:
        name = rec['business_name']
        city = rec.get('city', '')
        lic = rec.get('license_number')

        if lic:
            cur.execute('SELECT 1 FROM registries WHERE license_number = ? AND registry_source = ? LIMIT 1', (lic, REGISTRY_SOURCE))
        else:
            cur.execute('SELECT 1 FROM registries WHERE business_name = ? AND city = ? AND registry_source = ? LIMIT 1', (name, city, REGISTRY_SOURCE))
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
                    name, lic, rec['license_type'], rec['license_status'], rec.get('address', ''),
                    city, 'MT', rec.get('zip', ''), rec.get('county', ''),
                    REGISTRY_SOURCE, SEGMENT, rec.get('raw_data', '{}')
                )
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


def main(dry_run=False, pdf_source='', input_file='', summary_json='', fail_on_empty_fetch=True):
    print(f'[MT REVENUE] Starting import (dry_run={dry_run})')
    migrate_db()

    records = []
    diagnostics = {}

    if input_file:
        print(f'[MT REVENUE] Using manual fallback input: {input_file}')
        records, diagnostics = parse_manual_input(input_file)
    elif pdf_source:
        pdf_path = _load_pdf_path(pdf_source)
        cleanup = pdf_source.startswith('http')
        try:
            records, diagnostics = parse_pdf(pdf_path)
        finally:
            if cleanup and pdf_path and os.path.exists(pdf_path):
                os.remove(pdf_path)
    else:
        blocking_reason = 'no stable public CSV/API endpoint identified and no source file provided'
        print(f'[MT REVENUE] BLOCKED: {blocking_reason}.')
        print('[MT REVENUE] Provide --pdf-url <url-or-path> or --input-file <csv|json>.')
        print('[MT REVENUE] No DB writes performed.')
        summary = {
            'importer': 'mt_revenue',
            'dry_run': dry_run,
            'fetched': 0,
            'new': 0,
            'existing': 0,
            'errors': 1,
            'blocked': True,
            'status': 'blocked_no_source',
            'blocking_reason': blocking_reason,
            'pdf_source': pdf_source,
            'input_file': input_file,
        }
        _write_summary(summary_json, summary)
        return 3

    fetched_count = len(records)
    print(f'[MT REVENUE] Parsed {fetched_count} records')
    if diagnostics:
        print(f'[MT REVENUE] Parse diagnostics: {json.dumps(diagnostics, sort_keys=True)}')

    if fetched_count == 0:
        print('[MT REVENUE] ⚠️  Zero records parsed from provided source.')
        summary = {
            'importer': 'mt_revenue',
            'dry_run': dry_run,
            'fetched': 0,
            'new': 0,
            'existing': 0,
            'errors': 1,
            'blocked': False,
            'status': 'failed_empty_fetch',
            'pdf_source': pdf_source,
            'input_file': input_file,
            'diagnostics': diagnostics,
        }
        _write_summary(summary_json, summary)
        return 2 if fail_on_empty_fetch else 0

    stats = insert_records(records, dry_run=dry_run)
    print(f'\n[MT REVENUE] Import complete (dry_run={dry_run}):')
    print(f'  ✅ New records:     {stats["new"]}')
    print(f'  ⏭️  Already existed: {stats["existing"]}')
    print(f'  ❌ Errors:          {stats["errors"]}')

    summary = {
        'importer': 'mt_revenue',
        'dry_run': dry_run,
        'fetched': fetched_count,
        'new': stats['new'],
        'existing': stats['existing'],
        'errors': stats['errors'],
        'blocked': False,
        'status': 'ok',
        'pdf_source': pdf_source,
        'input_file': input_file,
        'diagnostics': diagnostics,
    }
    _write_summary(summary_json, summary)
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Import Montana cannabis cultivators from PDF/manual fallback')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--pdf-url', default='', help='PDF URL or local path')
    parser.add_argument('--input-file', default='', help='Manual fallback path (.csv or .json)')
    parser.add_argument('--summary-json', '--json', dest='summary_json', default='', help='Write machine-readable run summary JSON')
    parser.add_argument('--allow-empty-fetch', action='store_true', help='Do not exit non-zero when parse returns zero records')
    args = parser.parse_args()
    raise SystemExit(main(
        dry_run=args.dry_run,
        pdf_source=args.pdf_url,
        input_file=args.input_file,
        summary_json=args.summary_json,
        fail_on_empty_fetch=not args.allow_empty_fetch,
    ))
