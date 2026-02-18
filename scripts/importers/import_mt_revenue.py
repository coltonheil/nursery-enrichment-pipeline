#!/usr/bin/env python3
"""
Montana Revenue cannabis cultivator importer.

Phase 1 placeholder with explicit blocking reason:
- Montana DOR publishes license data in PDF/portal formats that vary and are often
  non-tabular scans. No stable direct CSV/API endpoint was identified in this pass.

This script supports importing from a provided PDF URL/path when available.
If none is provided, it exits with a documented BLOCKED reason (no DB writes).

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
                # Best-effort parse: Name ... City, MT ZIP ... LIC####
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


def main(dry_run=False, pdf_source=''):
    print(f'[MT REVENUE] Starting import (dry_run={dry_run})')
    migrate_db()

    if not pdf_source:
        print('[MT REVENUE] BLOCKED: no stable public CSV/API endpoint identified and no PDF source provided.')
        print('[MT REVENUE] Provide --pdf-url <url-or-path> to run best-effort parse.')
        print('[MT REVENUE] No DB writes performed.')
        return

    pdf_path = _load_pdf_path(pdf_source)
    cleanup = pdf_source.startswith('http')
    try:
        records = parse_pdf(pdf_path)
    finally:
        if cleanup and pdf_path and os.path.exists(pdf_path):
            os.remove(pdf_path)

    print(f'[MT REVENUE] Parsed {len(records)} records from PDF')
    stats = insert_records(records, dry_run=dry_run)
    print(f'\n[MT REVENUE] Import complete (dry_run={dry_run}):')
    print(f'  ✅ New records:     {stats["new"]}')
    print(f'  ⏭️  Already existed: {stats["existing"]}')
    print(f'  ❌ Errors:          {stats["errors"]}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Import Montana cannabis cultivators from PDF (best effort)')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--pdf-url', default='', help='PDF URL or local path')
    args = parser.parse_args()
    main(dry_run=args.dry_run, pdf_source=args.pdf_url)
