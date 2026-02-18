#!/usr/bin/env python3
"""
Import Oregon OLCC (now OCM) cannabis producer/cultivator licenses into registries table.

Source: Oregon OLCC Tableau dashboard / direct CSV export
URL: https://www.oregon.gov/olcc/marijuana/Pages/Recreational-Marijuana-Licensee-Reports.aspx
Data: Tableau endpoint at data.olcc.state.or.us

Segment: cannabis_grower
Registry source: or_olcc
"""

import argparse
import json
import os
import sqlite3
import sys
import time
import re
from datetime import datetime

import requests

# Ensure project root is in path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from database.models import get_db_connection, migrate_db

REGISTRY_SOURCE = 'or_olcc'
SEGMENT = 'cannabis_grower'

# Producer/cultivator license type keywords to filter
CULTIVATOR_TYPES = {
    'producer', 'cultivator', 'craft cannabis', 'craft marijuana',
    'producer tier i', 'producer tier ii', 'marijuana producer',
    'cannabis producer',
}

# OLCC Tableau data URL - try multiple approaches
TABLEAU_CSV_URL = (
    'https://data.olcc.state.or.us/t/OLCCPublic/views/'
    'CannabisBusinessLicensesEndorsements/CannabisLicensesEndorsements.csv'
)

# Alternative: OLCC CAMP eLicensing public API
ELICENSING_BASE = 'https://camp.olcc.online/prod/api/public'

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}


def fetch_olcc_via_tableau():
    """Try to get data from OLCC Tableau export."""
    session = requests.Session()
    session.headers.update(HEADERS)

    print('[OR OLCC] Trying Tableau CSV endpoint...')
    try:
        # First get the view to establish session
        view_url = (
            'https://data.olcc.state.or.us/t/OLCCPublic/views/'
            'CannabisBusinessLicensesEndorsements/CannabisLicensesEndorsements'
        )
        r = session.get(view_url, timeout=30)

        # Now try CSV download
        csv_url = view_url + '.csv'
        r2 = session.get(csv_url, timeout=60, params={':showVizHome': 'no'})

        if r2.status_code == 200 and 'License Number' in r2.text[:2000]:
            print(f'[OR OLCC] Tableau CSV: got {len(r2.text)} bytes')
            return parse_tableau_csv(r2.text)
        else:
            print(f'[OR OLCC] Tableau CSV returned {r2.status_code}, content-type: {r2.headers.get("content-type")}')
            return []
    except Exception as e:
        print(f'[OR OLCC] Tableau error: {e}')
        return []


def parse_tableau_csv(csv_text):
    """Parse CSV from Tableau export."""
    import csv
    import io

    records = []
    reader = csv.DictReader(io.StringIO(csv_text))

    for row in reader:
        # Map field names (Tableau may use different names)
        license_type = (
            row.get('License Type', '')
            or row.get('license_type', '')
            or row.get('License_Type', '')
        ).lower()

        # Filter for producers/cultivators
        is_cultivator = any(t in license_type for t in CULTIVATOR_TYPES)
        if not is_cultivator:
            continue

        records.append({
            'business_name': (
                row.get('Trade Name', '')
                or row.get('Business Name', '')
                or row.get('trade_name', '')
                or ''
            ).strip(),
            'license_number': (
                row.get('License Number', '')
                or row.get('license_number', '')
                or ''
            ).strip(),
            'license_type': license_type,
            'license_status': (
                row.get('Status', '')
                or row.get('status', '')
                or 'active'
            ).strip(),
            'city': (
                row.get('City', '')
                or row.get('city', '')
                or ''
            ).strip(),
            'zip': (
                row.get('Zip', '')
                or row.get('zip', '')
                or row.get('Zip Code', '')
                or ''
            ).strip(),
            'county': (
                row.get('County', '')
                or row.get('county', '')
                or ''
            ).strip(),
            'address': (
                row.get('Address', '')
                or row.get('address', '')
                or ''
            ).strip(),
            'raw_data': json.dumps(dict(row)),
        })

    return records


def fetch_olcc_via_elicensing():
    """Try OLCC CAMP eLicensing public search API."""
    print('[OR OLCC] Trying CAMP eLicensing API...')
    session = requests.Session()
    session.headers.update(HEADERS)

    records = []
    page = 0
    page_size = 100

    # Producer license type IDs — these are Oregon-specific
    license_type_names = ['Marijuana Producer', 'Cannabis Producer']

    for license_type_name in license_type_names:
        page = 0
        while True:
            try:
                params = {
                    'licenseTypeName': license_type_name,
                    'status': 'Active',
                    'page': page,
                    'pageSize': page_size,
                }
                r = session.get(
                    f'{ELICENSING_BASE}/licenses',
                    params=params,
                    timeout=30,
                )

                if r.status_code == 429:
                    print('[OR OLCC] Rate limited, sleeping 60s...')
                    time.sleep(60)
                    continue
                elif r.status_code != 200:
                    print(f'[OR OLCC] eLicensing returned {r.status_code}')
                    break

                data = r.json()
                items = data if isinstance(data, list) else data.get('results', data.get('data', []))

                if not items:
                    break

                for item in items:
                    records.append({
                        'business_name': (
                            item.get('tradeName', '')
                            or item.get('businessName', '')
                            or item.get('name', '')
                            or ''
                        ).strip(),
                        'license_number': str(item.get('licenseNumber', '') or item.get('license', '') or '').strip(),
                        'license_type': license_type_name.lower(),
                        'license_status': str(item.get('status', 'active')).lower(),
                        'city': (item.get('city', '') or '').strip(),
                        'zip': str(item.get('zip', '') or item.get('zipCode', '') or '').strip(),
                        'county': (item.get('county', '') or '').strip(),
                        'address': (item.get('address', '') or '').strip(),
                        'raw_data': json.dumps(item),
                    })

                if len(items) < page_size:
                    break

                page += 1
                time.sleep(1)

            except Exception as e:
                print(f'[OR OLCC] eLicensing error page {page}: {e}')
                break

    print(f'[OR OLCC] eLicensing fetched {len(records)} records')
    return records


def fetch_olcc_via_html_scrape():
    """
    Scrape OLCC CAMP portal HTML search results.
    Fallback when APIs are unavailable.
    """
    print('[OR OLCC] Trying CAMP portal HTML scrape...')
    from bs4 import BeautifulSoup

    session = requests.Session()
    session.headers.update(HEADERS)

    records = []
    base_url = 'https://camp.olcc.online/prod/webui/'

    try:
        # Load the main search page
        r = session.get(base_url, timeout=30)
        if r.status_code != 200:
            print(f'[OR OLCC] CAMP portal returned {r.status_code}')
            return []

        # This is a JS-heavy portal — HTML scraping won't work well here
        # Return empty and let caller handle fallback
        print('[OR OLCC] CAMP portal requires JS rendering, skipping HTML scrape')
        return []

    except Exception as e:
        print(f'[OR OLCC] HTML scrape error: {e}')
        return []


def fetch_records():
    """
    Main fetch function. Tries multiple sources in order:
    1. Tableau CSV export
    2. CAMP eLicensing API
    3. Scrape (last resort)
    """
    # Try Tableau first
    records = fetch_olcc_via_tableau()
    if records:
        print(f'[OR OLCC] Got {len(records)} records from Tableau')
        return records

    # Try eLicensing API
    records = fetch_olcc_via_elicensing()
    if records:
        print(f'[OR OLCC] Got {len(records)} records from eLicensing')
        return records

    print('[OR OLCC] All fetch methods exhausted')
    return []


def insert_records(records, dry_run=False):
    """Insert records into registries table using INSERT OR IGNORE for idempotency."""
    if not records:
        print('[OR OLCC] No records to insert.')
        return {'new': 0, 'existing': 0, 'errors': 0}

    conn = get_db_connection()
    cursor = conn.cursor()

    new_count = 0
    existing_count = 0
    error_count = 0

    for rec in records:
        business_name = rec.get('business_name', '').strip()
        license_number = rec.get('license_number', '').strip()
        city = rec.get('city', '').strip()

        if not business_name:
            error_count += 1
            continue

        if not license_number:
            cursor.execute(
                'SELECT 1 FROM registries WHERE business_name = ? AND city = ? AND registry_source = ? LIMIT 1',
                (business_name, city, REGISTRY_SOURCE),
            )
            if cursor.fetchone():
                existing_count += 1
                continue

        if dry_run:
            if license_number:
                cursor.execute(
                    'SELECT 1 FROM registries WHERE license_number = ? AND registry_source = ? LIMIT 1',
                    (license_number, REGISTRY_SOURCE),
                )
                if cursor.fetchone():
                    existing_count += 1
                else:
                    new_count += 1
            else:
                new_count += 1
            continue

        try:
            cursor.execute(
                '''INSERT OR IGNORE INTO registries
                   (business_name, license_number, license_type, license_status,
                    address, city, state, zip, county,
                    registry_source, segment, raw_data, imported_at)
                   VALUES (?, ?, ?, ?, ?, ?, 'OR', ?, ?,
                           ?, ?, ?, CURRENT_TIMESTAMP)''',
                (
                    business_name,
                    license_number or None,
                    rec.get('license_type', ''),
                    rec.get('license_status', 'active'),
                    rec.get('address', ''),
                    city,
                    rec.get('zip', ''),
                    rec.get('county', ''),
                    REGISTRY_SOURCE,
                    SEGMENT,
                    rec.get('raw_data', '{}'),
                ),
            )
            if cursor.rowcount > 0:
                new_count += 1
            else:
                existing_count += 1
        except sqlite3.Error as e:
            print(f'[OR OLCC] DB error for {business_name}: {e}')
            error_count += 1

    if not dry_run:
        conn.commit()
    conn.close()
    return {'new': new_count, 'existing': existing_count, 'errors': error_count}


def import_records(dry_run=False):
    """Main import entry point."""
    print(f'[OR OLCC] Starting import (dry_run={dry_run})')

    # Ensure DB schema is up to date
    migrate_db()

    records = fetch_records()

    if not records:
        print('[OR OLCC] ⚠️  No records fetched. Possible causes:')
        print('           - Tableau endpoint requires authentication')
        print('           - CAMP eLicensing API changed')
        print('           - Network error')
        print('           Try running with browser scrape or manual CSV download.')
        return

    print(f'[OR OLCC] Fetched {len(records)} cultivator records')

    stats = insert_records(records, dry_run=dry_run)

    print(f'\n[OR OLCC] Import complete (dry_run={dry_run}):')
    print(f'  ✅ New records:     {stats["new"]}')
    print(f'  ⏭️  Already existed: {stats["existing"]}')
    print(f'  ❌ Errors:          {stats["errors"]}')

    if dry_run:
        for rec in records[:3]:
            print(f'  Sample: {rec["business_name"]} | {rec["license_number"]} | {rec["city"]}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Import Oregon OLCC cannabis cultivator licenses')
    parser.add_argument('--dry-run', action='store_true', help='Print stats without writing to DB')
    args = parser.parse_args()
    import_records(dry_run=args.dry_run)
