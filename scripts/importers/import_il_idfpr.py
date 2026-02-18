#!/usr/bin/env python3
"""
Import Illinois cannabis growers (craft growers + cultivation centers) into registries.

Primary source (public PDF):
  https://agr.illinois.gov/content/dam/soi/en/web/agr/documents/idoa-licensee-list.pdf

Registry source: il_idfpr
Segment: cannabis_grower
"""

import argparse
import json
import os
import re
import sqlite3
import sys
import tempfile
from urllib.parse import urlparse

import pdfplumber
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from database.models import get_db_connection, migrate_db

REGISTRY_SOURCE = 'il_idfpr'
SEGMENT = 'cannabis_grower'
DEFAULT_URL = 'https://agr.illinois.gov/content/dam/soi/en/web/agr/documents/idoa-licensee-list.pdf'


def _download_pdf(url: str) -> str:
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    if 'pdf' not in (r.headers.get('content-type', '').lower()) and not url.lower().endswith('.pdf'):
        raise RuntimeError(f'URL did not return a PDF content-type: {r.headers.get("content-type")}')
    fd, path = tempfile.mkstemp(prefix='il_licensees_', suffix='.pdf')
    os.close(fd)
    with open(path, 'wb') as f:
        f.write(r.content)
    return path


def _extract_city_state_zip(location: str):
    # Expected formats include: "..., Springfield IL, 62711" or "..., Cary,IL 60013"
    m = re.search(r'([A-Za-z .\'-]+),?\s*IL\s*,?\s*(\d{5})?', location)
    if m:
        city = m.group(1).strip(' ,')
        zip_code = (m.group(2) or '').strip()
        return city, 'IL', zip_code
    return '', 'IL', ''


def _guess_license_type(line: str, section: str) -> str:
    if 'cultivation center' in section.lower():
        return 'cultivation_center'
    if 'craft grower' in section.lower():
        return 'craft_grower'
    lower = line.lower()
    if 'cultivation center' in lower:
        return 'cultivation_center'
    if 'craft' in lower:
        return 'craft_grower'
    return 'cannabis_grower'


def parse_pdf(pdf_path: str):
    records = []
    current_section = ''

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ''
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

            for ln in lines:
                low = ln.lower()
                if 'craft growers' in low:
                    current_section = 'Craft Growers'
                    continue
                if 'cultivation centers' in low or 'medical cultivation centers' in low:
                    current_section = 'Cultivation Centers'
                    continue
                if low in {'applicant name current location', 'licensee current location'}:
                    continue
                if len(ln) < 8:
                    continue

                # Split on first obvious location cue (number/address/PIN)
                match = re.match(r'^(.*?)\s{2,}(.*)$', ln)
                if match:
                    name = match.group(1).strip(' -')
                    location = match.group(2).strip()
                else:
                    # fallback: split where address starts with digit or PIN marker
                    m2 = re.match(r'^(.*?)(\b(?:PIN:|\d{1,6}\b).*)$', ln)
                    if not m2:
                        continue
                    name = m2.group(1).strip(' -')
                    location = m2.group(2).strip()

                if not name or name.lower() in {'craft growers', 'cultivation centers'}:
                    continue

                city, state, zip_code = _extract_city_state_zip(location)
                license_type = _guess_license_type(ln, current_section)

                raw = {
                    'name': name,
                    'location': location,
                    'section': current_section,
                    'source_pdf': os.path.basename(pdf_path),
                }

                records.append({
                    'business_name': name,
                    'license_number': None,
                    'license_type': license_type,
                    'license_status': 'active',
                    'address': location,
                    'city': city,
                    'state': state,
                    'zip': zip_code,
                    'county': '',
                    'raw_data': json.dumps(raw),
                })

    # Deduplicate within scrape run
    deduped = {}
    for rec in records:
        key = (rec['business_name'].strip().lower(), rec['city'].strip().lower(), rec['address'].strip().lower())
        deduped[key] = rec
    return list(deduped.values())


def insert_records(records, dry_run=False):
    conn = get_db_connection()
    cur = conn.cursor()

    new_count = 0
    existing_count = 0
    error_count = 0

    for rec in records:
        name = (rec.get('business_name') or '').strip()
        city = (rec.get('city') or '').strip()
        if not name:
            error_count += 1
            continue

        cur.execute(
            'SELECT 1 FROM registries WHERE business_name = ? AND city = ? AND registry_source = ? LIMIT 1',
            (name, city, REGISTRY_SOURCE),
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
                    None,
                    rec.get('license_type', 'cannabis_grower'),
                    rec.get('license_status', 'active'),
                    rec.get('address', ''),
                    city,
                    rec.get('state', 'IL'),
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


def main(dry_run=False, source_url=DEFAULT_URL):
    print(f'[IL IDFPR] Starting import (dry_run={dry_run})')
    migrate_db()
    pdf_path = _download_pdf(source_url)
    try:
        records = parse_pdf(pdf_path)
    finally:
        try:
            os.remove(pdf_path)
        except OSError:
            pass

    print(f'[IL IDFPR] Parsed {len(records)} candidate records')
    stats = insert_records(records, dry_run=dry_run)

    print(f'\n[IL IDFPR] Import complete (dry_run={dry_run}):')
    print(f'  ✅ New records:     {stats["new"]}')
    print(f'  ⏭️  Already existed: {stats["existing"]}')
    print(f'  ❌ Errors:          {stats["errors"]}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Import Illinois cannabis growers (craft + cultivation)')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--source-url', default=DEFAULT_URL)
    args = parser.parse_args()
    main(dry_run=args.dry_run, source_url=args.source_url)
