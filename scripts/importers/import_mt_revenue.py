#!/usr/bin/env python3
"""
Montana Revenue cannabis cultivator importer.

Phase 1 importer with explicit blocker behavior and manual-source support:
- Accepts PDF URL/path (best-effort parsing)
- Returns clear blocked status when no source is provided

Registry source: mt_revenue
Segment: cannabis_grower
"""

import argparse
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


def parse_pdf(pdf_path: str):
    records = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ''
            for ln in [x.strip() for x in text.splitlines() if x.strip()]:
                m = re.search(r'^(.*?)\s+([A-Za-z .\'-]+),\s*MT\s*(\d{5})?.*?(LIC\w+|\d{4,})?$', ln)
                if not m:
                    continue
                name = m.group(1).strip(' -')
                city = (m.group(2) or '').strip()
                zip_code = (m.group(3) or '').strip()
                lic = (m.group(4) or '').strip() or None
                if not name:
                    continue
                records.append({
                    'business_name': name,
                    'license_number': lic,
                    'license_type': 'cannabis_cultivator',
                    'license_status': 'active',
                    'address': '',
                    'city': city,
                    'state': 'MT',
                    'zip': zip_code,
                    'county': '',
                    'raw_data': json.dumps({'line': ln, 'source': os.path.basename(pdf_path)}),
                })
    return records


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


def main(dry_run=False, pdf_source='', summary_json='', fail_on_empty_fetch=True):
    print(f'[MT REVENUE] Starting import (dry_run={dry_run})')
    migrate_db()

    if not pdf_source:
        blocking_reason = 'no stable public CSV/API endpoint identified and no source file provided'
        print(f'[MT REVENUE] BLOCKED: {blocking_reason}.')
        print('[MT REVENUE] Provide --pdf-url <url-or-path> to run best-effort parse.')
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
        }
        _write_summary(summary_json, summary)
        return 3

    pdf_path = _load_pdf_path(pdf_source)
    cleanup = pdf_source.startswith('http')
    try:
        records = parse_pdf(pdf_path)
    finally:
        if cleanup and pdf_path and os.path.exists(pdf_path):
            os.remove(pdf_path)

    fetched_count = len(records)
    print(f'[MT REVENUE] Parsed {fetched_count} records from PDF')

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
    }
    _write_summary(summary_json, summary)
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Import Montana cannabis cultivators from PDF (best effort)')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--pdf-url', default='', help='PDF URL or local path')
    parser.add_argument('--summary-json', '--json', dest='summary_json', default='', help='Write machine-readable run summary JSON')
    parser.add_argument('--allow-empty-fetch', action='store_true', help='Do not exit non-zero when parse returns zero records')
    args = parser.parse_args()
    raise SystemExit(main(
        dry_run=args.dry_run,
        pdf_source=args.pdf_url,
        summary_json=args.summary_json,
        fail_on_empty_fetch=not args.allow_empty_fetch,
    ))
