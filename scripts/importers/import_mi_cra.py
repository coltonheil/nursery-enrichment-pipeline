#!/usr/bin/env python3
"""
Import Michigan CRA cannabis grower licenses into registries table.

Source: Michigan Cannabis Regulatory Agency (CRA) Accela Portal
URL: https://aca-prod.accela.com/MIMM/Cap/CapHome.aspx?module=Licenses

License types:
  - Grower License A (Class A, up to 100 plants)
  - Grower License B (Class B, up to 500 plants)
  - Grower License C (Class C, up to 2000 plants)

Segment: cannabis_grower
Registry source: mi_cra
"""

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from database.models import get_db_connection, migrate_db

REGISTRY_SOURCE = 'mi_cra'
SEGMENT = 'cannabis_grower'

BASE_URL = 'https://aca-prod.accela.com/MIMM'
SEARCH_URL = f'{BASE_URL}/Cap/CapHome.aspx'

# Accela dropdown option values for grower types
GROWER_LICENSE_TYPES = [
    ('Licenses/Grower License A/License/NA', 'grower_class_a'),
    ('Licenses/Grower License B/License/NA', 'grower_class_b'),
    ('Licenses/Grower License C/License/NA', 'grower_class_c'),
]

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': SEARCH_URL,
    'Origin': BASE_URL,
}


def get_initial_form_state(session):
    """GET the search page and extract ASP.NET form state values."""
    params = {'module': 'Licenses', 'TabName': 'Adult-Use Establishment Licensing'}
    r = session.get(SEARCH_URL, params=params, timeout=30)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, 'lxml')

    state = {}
    for field in soup.find_all('input', attrs={'type': 'hidden'}):
        name = field.get('name', '')
        value = field.get('value', '') or ''
        if name:
            state[name] = value

    return state, r.cookies


def search_by_license_type(session, initial_state, license_type_value, license_type_name):
    """
    POST to search for a specific license type with Search All Records enabled.
    Returns list of records from the first page + handles pagination.
    """
    records = []
    page_num = 1
    current_state = dict(initial_state)

    while True:
        # Build POST payload
        payload = dict(current_state)

        if page_num == 1:
            # First search — set license type and click search
            payload.update({
                '__EVENTTARGET': '',
                '__EVENTARGUMENT': '',
                'ctl00$PlaceHolderMain$generalSearchForm$ddlGSPermitType': license_type_value,
                'ctl00$PlaceHolderMain$generalSearchForm$chkGSAllRecords': 'on',  # Search All Records
                'ctl00$PlaceHolderMain$generalSearchForm$txtGSEndDate': '',
                'ctl00$PlaceHolderMain$btnNewSearch': 'Search',
            })
        else:
            # Subsequent pages — use pagination EventTarget
            payload.update({
                '__EVENTTARGET': f'ctl00$PlaceHolderMain$CapList$gdvPermitList',
                '__EVENTARGUMENT': f'Page${page_num}',
            })
            # Remove the search button trigger for pagination
            payload.pop('ctl00$PlaceHolderMain$btnNewSearch', None)

        params = {'module': 'Licenses', 'TabName': 'Adult-Use Establishment Licensing'}

        try:
            r = session.post(
                SEARCH_URL,
                data=payload,
                params=params,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=45,
            )

            if r.status_code == 429:
                print(f'[MI CRA] Rate limited, sleeping 60s...')
                time.sleep(60)
                continue
            elif r.status_code != 200:
                print(f'[MI CRA] Search returned {r.status_code} for {license_type_name}')
                break

            soup = BeautifulSoup(r.text, 'lxml')

            # Update form state for next pagination call
            for field in soup.find_all('input', attrs={'type': 'hidden'}):
                name = field.get('name', '')
                value = field.get('value', '') or ''
                if name:
                    current_state[name] = value

            # Find the results table
            # Accela uses a GridView with ID 'gdvPermitList'
            table = (
                soup.find('table', attrs={'id': re.compile(r'gdvPermitList|CapList')})
                or soup.find('table', class_=re.compile(r'ACA_Grid|PermitList'))
            )

            if not table:
                # Try any table in results area
                result_div = soup.find('div', id=re.compile(r'PageResult|CapList'))
                if result_div:
                    table = result_div.find('table')

            if not table:
                if page_num == 1:
                    print(f'[MI CRA] No results table found for {license_type_name}')
                break

            page_records = parse_results_table(table, license_type_name)
            records.extend(page_records)

            print(f'[MI CRA] {license_type_name} page {page_num}: {len(page_records)} records')

            if len(page_records) == 0:
                break

            # Check for next page link
            pagination = soup.find('tr', class_=re.compile(r'ACA_Pagination|pager', re.I))
            if not pagination:
                break

            next_page_link = None
            for link in (pagination.find_all('a') if pagination else []):
                if link.get_text(strip=True) == str(page_num + 1):
                    next_page_link = link
                    break

            if not next_page_link:
                break

            page_num += 1
            time.sleep(1)  # Respect rate limits

        except requests.RequestException as e:
            print(f'[MI CRA] Request error page {page_num}: {e}')
            break

    return records


def parse_results_table(table, license_type_name):
    """Parse an Accela results table into record dicts."""
    records = []
    rows = table.find_all('tr')

    if not rows:
        return records

    # Find header row to map column positions
    header_row = None
    for row in rows:
        cells = row.find_all(['th', 'td'])
        cell_text = [c.get_text(strip=True).lower() for c in cells]
        if any(
            keyword in ' '.join(cell_text)
            for keyword in ['license', 'business', 'name', 'status', 'city']
        ):
            header_row = cells
            break

    if not header_row:
        # Use first row as header
        header_row = rows[0].find_all(['th', 'td'])

    headers = [c.get_text(strip=True).lower() for c in header_row]

    # Column index mapping
    col_map = {}
    for i, h in enumerate(headers):
        if 'license' in h and 'number' in h or 'license #' in h:
            col_map['license_number'] = i
        elif 'license' in h and 'type' in h:
            col_map['license_type'] = i
        elif 'business' in h and 'name' in h or 'name of business' in h:
            col_map['business_name'] = i
        elif 'dba' in h or 'doing business' in h:
            col_map['dba_name'] = i
        elif 'status' in h:
            col_map['status'] = i
        elif 'city' in h:
            col_map['city'] = i
        elif 'state' in h and len(h) < 10:
            col_map['state'] = i
        elif 'zip' in h:
            col_map['zip'] = i
        elif 'county' in h:
            col_map['county'] = i
        elif 'address' in h:
            col_map['address'] = i

    # Parse data rows
    for row in rows:
        cells = row.find_all('td')
        if len(cells) < 2:
            continue

        def get_cell(key, default=''):
            idx = col_map.get(key)
            if idx is not None and idx < len(cells):
                return cells[idx].get_text(strip=True)
            return default

        business_name = get_cell('business_name') or get_cell('dba_name')
        license_number = get_cell('license_number')
        status = get_cell('status', 'active').lower()
        city = get_cell('city')
        state = get_cell('state', 'MI')
        zip_code = get_cell('zip')
        county = get_cell('county')
        address = get_cell('address')

        if not business_name or business_name.lower() in ('', '-', 'n/a'):
            continue

        # Try to get the detail link for more data
        detail_url = ''
        first_link = row.find('a', href=True)
        if first_link:
            href = first_link.get('href', '')
            if href and not href.startswith('javascript'):
                detail_url = BASE_URL + href if not href.startswith('http') else href

        raw = {
            'business_name': business_name,
            'license_number': license_number,
            'license_type': license_type_name,
            'status': status,
            'city': city,
            'state': state or 'MI',
            'zip': zip_code,
            'county': county,
            'address': address,
            'detail_url': detail_url,
            'cells': [c.get_text(strip=True) for c in cells[:10]],
        }

        records.append({
            'business_name': business_name,
            'license_number': license_number,
            'license_type': license_type_name,
            'license_status': status,
            'city': city,
            'state': state or 'MI',
            'zip': zip_code,
            'county': county,
            'address': address,
            'raw_data': json.dumps(raw),
        })

    return records


def fetch_records():
    """Fetch all grower license records from Michigan CRA Accela portal."""
    session = requests.Session()
    session.headers.update(HEADERS)

    print('[MI CRA] Fetching initial form state...')
    try:
        initial_state, cookies = get_initial_form_state(session)
    except Exception as e:
        print(f'[MI CRA] Failed to load initial form: {e}')
        return []

    all_records = []

    for license_type_value, license_type_name in GROWER_LICENSE_TYPES:
        print(f'[MI CRA] Searching: {license_type_name}')
        try:
            records = search_by_license_type(
                session, initial_state, license_type_value, license_type_name
            )
            print(f'[MI CRA] {license_type_name}: {len(records)} total records')
            all_records.extend(records)
        except Exception as e:
            print(f'[MI CRA] Error fetching {license_type_name}: {e}')

        time.sleep(2)  # Pause between license type searches

    return all_records


def insert_records(records, dry_run=False):
    """Insert records into registries table using INSERT OR IGNORE."""
    if not records:
        print('[MI CRA] No records to insert.')
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

        # Fallback dedupe for NULL/blank license numbers (SQLite UNIQUE allows multiple NULLs)
        if not license_number:
            cursor.execute(
                'SELECT 1 FROM registries WHERE business_name = ? AND city = ? AND registry_source = ? LIMIT 1',
                (business_name, city, REGISTRY_SOURCE),
            )
            if cursor.fetchone():
                existing_count += 1
                continue

        if dry_run:
            # For non-empty license numbers, check exact unique key
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
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?,
                           ?, ?, ?, CURRENT_TIMESTAMP)''',
                (
                    business_name,
                    license_number or None,
                    rec.get('license_type', ''),
                    rec.get('license_status', 'active'),
                    rec.get('address', ''),
                    city,
                    rec.get('state', 'MI'),
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
            print(f'[MI CRA] DB error for {business_name}: {e}')
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


def import_records(dry_run=False, summary_json='', fail_on_empty_fetch=True):
    """Main import entry point."""
    print(f'[MI CRA] Starting import (dry_run={dry_run})')
    migrate_db()

    records = fetch_records()
    fetched_count = len(records)

    if not records:
        print('[MI CRA] ⚠️  No records fetched.')
        print('          Possible causes:')
        print('          - Accela portal blocked bot traffic')
        print('          - Form POST structure changed')
        print('          - Results table structure changed')
        print('          Try running manually or check portal accessibility.')
        summary = {
            'importer': 'mi_cra',
            'dry_run': dry_run,
            'fetched': fetched_count,
            'new': 0,
            'existing': 0,
            'errors': 1,
            'blocked': False,
            'status': 'failed_empty_fetch',
        }
        _write_summary(summary_json, summary)
        return 2 if fail_on_empty_fetch else 0

    print(f'[MI CRA] Fetched {len(records)} grower records total')

    stats = insert_records(records, dry_run=dry_run)

    print(f'\n[MI CRA] Import complete (dry_run={dry_run}):')
    print(f'  ✅ New records:     {stats["new"]}')
    print(f'  ⏭️  Already existed: {stats["existing"]}')
    print(f'  ❌ Errors:          {stats["errors"]}')

    if dry_run:
        for rec in records[:5]:
            print(
                f'  Sample: {rec["business_name"][:50]} | '
                f'{rec["license_number"]} | {rec["license_type"]} | {rec["city"]}'
            )

    summary = {
        'importer': 'mi_cra',
        'dry_run': dry_run,
        'fetched': fetched_count,
        'new': stats['new'],
        'existing': stats['existing'],
        'errors': stats['errors'],
        'blocked': False,
        'status': 'ok',
    }
    _write_summary(summary_json, summary)
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Import Michigan CRA cannabis grower licenses')
    parser.add_argument('--dry-run', action='store_true', help='Print stats without writing to DB')
    parser.add_argument('--summary-json', '--json', dest='summary_json', default='', help='Write machine-readable run summary JSON')
    parser.add_argument('--allow-empty-fetch', action='store_true', help='Do not exit non-zero when fetch returns zero records')
    args = parser.parse_args()
    raise SystemExit(import_records(
        dry_run=args.dry_run,
        summary_json=args.summary_json,
        fail_on_empty_fetch=not args.allow_empty_fetch,
    ))
